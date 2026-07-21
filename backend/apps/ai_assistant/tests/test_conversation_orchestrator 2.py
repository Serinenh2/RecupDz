"""
Unit Tests — ConversationOrchestrator.

Tests the full conversation lifecycle: create, load, context, delegate,
persist, summarize, close, delete, expire.

All dependencies (Container, AgentOrchestrator, memory backends) are mocked.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, call

from apps.ai_assistant.enterprise.conversation_orchestrator import (
    ConversationContext,
    ConversationOrchestrator,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _success_agent_result():
    """Standard AgentOrchestrator.orchestrate() return value."""
    return {
        "success": True,
        "message": "Le code 01.01.01 correspond à 'Papier et carton'.",
        "data": {"code": "01.01.01", "name": "Papier et carton"},
        "followups": ["Voulez-vous d'autres codes ?"],
        "meta": {
            "tool_used": "nomenclature_tool",
            "tool_action": "search",
            "entities": {"type": "waste_code", "id": "01.01.01"},
            "elapsed_ms": 150.3,
        },
    }


def _error_agent_result():
    """AgentOrchestrator returns an error."""
    return {
        "success": False,
        "message": "Une erreur est survenue.",
        "data": {},
        "followups": [],
        "meta": {"error": "boom"},
    }


def _mock_container(
    conversation_memory=None,
    session_memory=None,
    user_memory=None,
    orchestrator=None,
):
    """Build a mock Container with all required properties."""
    c = MagicMock()
    c.conversation_memory = conversation_memory
    c.session_memory = session_memory
    c.user_memory = user_memory
    c.orchestrator = orchestrator
    return c


def _mock_conversation_memory(
    exists=True,
    llm_messages=None,
    total_turns=0,
    summaries=None,
    stats=None,
):
    """Build a mock EnterpriseConversationMemory."""
    mem = MagicMock()
    mem.exists.return_value = exists
    mem.get_llm_messages.return_value = llm_messages or [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Bonjour ! Comment puis-je vous aider ?"},
    ]
    mem.total_turns.return_value = total_turns
    mem.list_conversations.return_value = ["conv_abc123", "conv_def456"]

    # For _load_summaries: mem.retrieve() returns a snapshot
    snapshot = MagicMock()
    if summaries:
        snapshot.summaries = summaries
    else:
        snapshot.summaries = []
    mem.retrieve.return_value = snapshot

    mem.stats.return_value = stats or {
        "conversations": 2,
        "total_turns": 10,
        "total_summaries": 1,
    }
    mem.delete.return_value = True
    mem.expire.return_value = 3
    return mem


def _mock_session_memory(session_exists=True):
    """Build a mock SessionMemory."""
    sm = MagicMock()
    if session_exists:
        session = MagicMock()
        sm.get.return_value = session
        sm.get_entity.return_value = {"type": "waste_code", "id": "01.01.01"}
        sm.get_company.return_value = {"name": "Entreprise Test"}
        sm.get_declaration.return_value = None
        sm.get_recent_actions.return_value = []
        sm.get_mode.return_value = "standard"
    else:
        sm.get.return_value = None
        sm.get_entity.return_value = None
        sm.get_company.return_value = None
        sm.get_declaration.return_value = None
        sm.get_recent_actions.return_value = []
        sm.get_mode.return_value = "standard"
    return sm


def _mock_user_memory(has_profile=True):
    """Build a mock UserMemory."""
    um = MagicMock()
    if has_profile:
        profile = MagicMock()
        profile.to_dict.return_value = {
            "user_id": "u1",
            "username": "testuser",
            "display_name": "Test User",
        }
        um.get_profile.return_value = profile
        prefs = MagicMock()
        prefs.to_dict.return_value = {
            "output_format": "text",
            "language": "fr",
        }
        um.get_preferences.return_value = prefs
        um.get_frequent_entities.return_value = [
            {"type": "waste_code", "id": "01.01.01", "count": 5}
        ]
    else:
        um.get_profile.return_value = None
        um.get_preferences.return_value = None
        um.get_frequent_entities.return_value = []
    return um


# ══════════════════════════════════════════════════════════════════════
# Tests — ConversationContext
# ══════════════════════════════════════════════════════════════════════


class TestConversationContext(unittest.TestCase):

    def test_defaults(self):
        ctx = ConversationContext()
        self.assertEqual(ctx.conversation_id, "")
        self.assertEqual(ctx.user_id, "")
        self.assertEqual(ctx.history, [])
        self.assertEqual(ctx.summaries, [])
        self.assertFalse(ctx.has_history)
        self.assertFalse(ctx.has_summaries)
        self.assertEqual(ctx.turn_count, 0)

    def test_has_history(self):
        ctx = ConversationContext(history=[{"role": "user", "content": "hi"}])
        self.assertTrue(ctx.has_history)
        self.assertEqual(ctx.turn_count, 1)

    def test_has_summaries(self):
        ctx = ConversationContext(summaries=["Résumé de la conversation."])
        self.assertTrue(ctx.has_summaries)

    def test_to_dict(self):
        ctx = ConversationContext(
            conversation_id="conv_123",
            user_id="u1",
            history=[{"role": "user", "content": "hi"}],
            summaries=["Résumé"],
            is_new_conversation=True,
        )
        d = ctx.to_dict()
        self.assertEqual(d["conversation_id"], "conv_123")
        self.assertEqual(d["user_id"], "u1")
        self.assertEqual(d["history_length"], 1)
        self.assertEqual(d["summary_count"], 1)
        self.assertTrue(d["is_new_conversation"])


# ══════════════════════════════════════════════════════════════════════
# Tests — Constructor & Properties
# ══════════════════════════════════════════════════════════════════════


class TestConversationOrchestratorInit(unittest.TestCase):

    def test_defaults(self):
        co = ConversationOrchestrator()
        self.assertIsNone(co._container)
        self.assertEqual(co._summary_threshold, 10)
        self.assertEqual(co._max_history_turns, 20)

    def test_with_container(self):
        c = _mock_container()
        co = ConversationOrchestrator(container=c)
        self.assertIs(co._container, c)

    def test_custom_thresholds(self):
        co = ConversationOrchestrator(summary_threshold=5, max_history_turns=10)
        self.assertEqual(co._summary_threshold, 5)
        self.assertEqual(co._max_history_turns, 10)


# ══════════════════════════════════════════════════════════════════════
# Tests — handle() — Full lifecycle
# ══════════════════════════════════════════════════════════════════════


class TestHandleLifecycle(unittest.TestCase):

    def test_full_happy_path(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        um = _mock_user_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            user_memory=um,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("code 01.01.01", user_id="u1", conversation_id="conv_123")

        self.assertTrue(result["success"])
        self.assertIn("Papier", result["message"])
        self.assertEqual(result["meta"]["conversation_id"], "conv_123")

    def test_creates_conversation_if_missing(self):
        cm = _mock_conversation_memory(exists=False)
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", user_id="u1")

        self.assertTrue(result["success"])
        self.assertIn("conv_", result["meta"]["conversation_id"])
        self.assertTrue(result["meta"].get("new_conversation", False))

    def test_generates_conversation_id_if_empty(self):
        cm = _mock_conversation_memory(exists=False)
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", user_id="u1")

        self.assertTrue(result["success"])
        self.assertIn("conv_", result["meta"]["conversation_id"])

    def test_delegates_to_agent_orchestrator(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        co.handle("code 01.01.01", user_id="u1", conversation_id="conv_123")

        orch.orchestrate.assert_called_once_with(
            message="code 01.01.01",
            user_id="u1",
            conversation_id="conv_123",
            contexte_supp=None,
        )

    def test_passes_contexte_supp(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        co.handle("test", user_id="u1", contexte_supp={"extra": "data"})

        orch.orchestrate.assert_called_once()
        call_kwargs = orch.orchestrate.call_args[1]
        self.assertEqual(call_kwargs["contexte_supp"], {"extra": "data"})

    def test_loads_history_before_delegation(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        co.handle("test", conversation_id="conv_123")

        cm.get_llm_messages.assert_called_once_with("conv_123", max_turns=20)

    def test_persists_turns_after_delegation(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        co.handle("code 01.01.01", user_id="u1", conversation_id="conv_123")

        # store() called twice: once for user turn, once for assistant turn
        self.assertEqual(cm.store.call_count, 2)
        first_call = cm.store.call_args_list[0]
        self.assertEqual(first_call[0][0], "conv_123")
        self.assertEqual(first_call[1]["user_id"], "u1")

    def test_persists_session_after_delegation(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        co.handle("code 01.01.01", user_id="u1", conversation_id="conv_123")

        sm.get_or_create.assert_called_once_with("conv_123", "u1")
        sm.set_entity.assert_called_once()

    def test_persists_user_action(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        um = _mock_user_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            user_memory=um,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        co.handle("code 01.01.01", user_id="u1", conversation_id="conv_123")

        um.record_action.assert_called_once()
        call_kwargs = um.record_action.call_args[1]
        self.assertEqual(call_kwargs["user_id"], "u1")
        self.assertEqual(call_kwargs["session_id"], "conv_123")

    def test_auto_summarize_called(self):
        cm = _mock_conversation_memory(total_turns=15)
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c, summary_threshold=10)
        co.handle("test", conversation_id="conv_123")

        cm.compress.assert_called_once_with("conv_123", keep_recent=20)

    def test_no_auto_summarize_below_threshold(self):
        cm = _mock_conversation_memory(total_turns=5)
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c, summary_threshold=10)
        co.handle("test", conversation_id="conv_123")

        cm.compress.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# Tests — handle() — Error handling
# ══════════════════════════════════════════════════════════════════════


class TestHandleErrors(unittest.TestCase):

    def test_agent_orchestrator_exception_returns_safe_error(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.side_effect = RuntimeError("boom")
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", conversation_id="conv_123")

        self.assertFalse(result["success"])
        self.assertIn("erreur", result["message"].lower())

    def test_agent_returns_error_passthrough(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _error_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", conversation_id="conv_123")

        self.assertFalse(result["success"])
        self.assertIn("erreur", result["message"].lower())

    def test_no_container_returns_error(self):
        co = ConversationOrchestrator(container=None)
        result = co.handle("test")
        self.assertFalse(result["success"])
        self.assertTrue(len(result["message"]) > 0)

    def test_no_agent_orchestrator_returns_error(self):
        c = _mock_container(orchestrator=None)
        co = ConversationOrchestrator(container=c)
        result = co.handle("test")
        self.assertFalse(result["success"])

    def test_memory_exception_does_not_crash(self):
        cm = _mock_conversation_memory()
        cm.get_llm_messages.side_effect = RuntimeError("memory boom")
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", conversation_id="conv_123")
        self.assertTrue(result["success"])

    def test_persist_exception_does_not_crash(self):
        cm = _mock_conversation_memory()
        cm.store.side_effect = RuntimeError("persist boom")
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", conversation_id="conv_123")
        self.assertTrue(result["success"])


# ══════════════════════════════════════════════════════════════════════
# Tests — Context building
# ══════════════════════════════════════════════════════════════════════


class TestContextBuilding(unittest.TestCase):

    def test_context_includes_history(self):
        cm = _mock_conversation_memory(
            llm_messages=[
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour !"},
            ],
        )
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)

        # Capture the context by inspecting the call
        ctx = co._build_context(
            conversation_id="conv_123",
            user_id="u1",
            history=[{"role": "user", "content": "Bonjour"}],
            summaries=[],
            session_state={},
            user_profile={},
            is_new=False,
        )
        self.assertTrue(ctx.has_history)
        self.assertEqual(ctx.turn_count, 1)

    def test_context_includes_session_state(self):
        sm = _mock_session_memory()
        state = co._load_session("u1", "conv_123") if False else {}
        # Direct test of _build_context
        co = ConversationOrchestrator()
        ctx = co._build_context(
            conversation_id="conv_123",
            user_id="u1",
            history=[],
            summaries=[],
            session_state={"entity": {"type": "waste_code"}},
            user_profile={},
            is_new=False,
        )
        self.assertEqual(ctx.session_state["entity"]["type"], "waste_code")

    def test_context_marks_new_conversation(self):
        co = ConversationOrchestrator()
        ctx = co._build_context(
            conversation_id="conv_new",
            user_id="u1",
            history=[],
            summaries=[],
            session_state={},
            user_profile={},
            is_new=True,
        )
        self.assertTrue(ctx.is_new_conversation)


# ══════════════════════════════════════════════════════════════════════
# Tests — Conversation lifecycle operations
# ══════════════════════════════════════════════════════════════════════


class TestConversationLifecycle(unittest.TestCase):

    def test_create_conversation(self):
        co = ConversationOrchestrator()
        cid = co.create_conversation(user_id="u1")
        self.assertTrue(cid.startswith("conv_"))
        self.assertEqual(len(cid), 13)  # "conv_" + 8 hex

    def test_conversation_exists_true(self):
        cm = _mock_conversation_memory(exists=True)
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        self.assertTrue(co.conversation_exists("conv_123"))

    def test_conversation_exists_false(self):
        cm = _mock_conversation_memory(exists=False)
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        self.assertFalse(co.conversation_exists("conv_xyz"))

    def test_conversation_exists_no_memory(self):
        co = ConversationOrchestrator()
        self.assertFalse(co.conversation_exists("conv_123"))

    def test_get_turn_count(self):
        cm = _mock_conversation_memory(total_turns=15)
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        self.assertEqual(co.get_turn_count("conv_123"), 15)

    def test_list_conversations(self):
        cm = _mock_conversation_memory()
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        convs = co.list_conversations()
        self.assertEqual(convs, ["conv_abc123", "conv_def456"])

    def test_close_conversation(self):
        sm = _mock_session_memory()
        c = _mock_container(session_memory=sm)
        co = ConversationOrchestrator(container=c)
        co.close_conversation("conv_123")
        sm.delete.assert_called_once_with("conv_123")

    def test_delete_conversation(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        c = _mock_container(conversation_memory=cm, session_memory=sm)
        co = ConversationOrchestrator(container=c)
        result = co.delete_conversation("conv_123")
        self.assertTrue(result)
        cm.delete.assert_called_once_with("conv_123")
        sm.delete.assert_called_once_with("conv_123")

    def test_expire_conversations(self):
        cm = _mock_conversation_memory()
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        expired = co.expire_conversations()
        self.assertEqual(expired, 3)

    def test_get_stats(self):
        cm = _mock_conversation_memory()
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        stats = co.get_stats()
        self.assertTrue(stats["available"])
        self.assertEqual(stats["conversations"], 2)


# ══════════════════════════════════════════════════════════════════════
# Tests — History & Summaries loading
# ══════════════════════════════════════════════════════════════════════


class TestHistoryLoading(unittest.TestCase):

    def test_load_history(self):
        cm = _mock_conversation_memory(
            llm_messages=[
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour !"},
            ],
        )
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        history = co._load_history("conv_123")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")

    def test_load_history_no_memory(self):
        co = ConversationOrchestrator()
        history = co._load_history("conv_123")
        self.assertEqual(history, [])

    def test_load_history_exception_returns_empty(self):
        cm = _mock_conversation_memory()
        cm.get_llm_messages.side_effect = RuntimeError("boom")
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        history = co._load_history("conv_123")
        self.assertEqual(history, [])

    def test_load_summaries(self):
        summary = MagicMock()
        summary.to_context_string.return_value = "Résumé: conversation sur les déchets."
        cm = _mock_conversation_memory(summaries=[summary])
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        summaries = co._load_summaries("conv_123")
        self.assertEqual(len(summaries), 1)
        self.assertIn("déchets", summaries[0])

    def test_load_summaries_empty(self):
        cm = _mock_conversation_memory()
        c = _mock_container(conversation_memory=cm)
        co = ConversationOrchestrator(container=c)
        summaries = co._load_summaries("conv_123")
        self.assertEqual(summaries, [])


# ══════════════════════════════════════════════════════════════════════
# Tests — Memory loading
# ══════════════════════════════════════════════════════════════════════


class TestMemoryLoading(unittest.TestCase):

    def test_load_session_with_data(self):
        sm = _mock_session_memory(session_exists=True)
        c = _mock_container(session_memory=sm)
        co = ConversationOrchestrator(container=c)
        state = co._load_session("u1", "conv_123")
        self.assertIn("entity", state)
        self.assertIn("company", state)

    def test_load_session_no_session(self):
        sm = _mock_session_memory(session_exists=False)
        c = _mock_container(session_memory=sm)
        co = ConversationOrchestrator(container=c)
        state = co._load_session("u1", "conv_123")
        self.assertEqual(state, {})

    def test_load_session_no_memory(self):
        co = ConversationOrchestrator()
        state = co._load_session("u1", "conv_123")
        self.assertEqual(state, {})

    def test_load_user_profile_with_data(self):
        um = _mock_user_memory(has_profile=True)
        c = _mock_container(user_memory=um)
        co = ConversationOrchestrator(container=c)
        profile = co._load_user_profile("u1")
        self.assertIn("profile", profile)
        self.assertIn("preferences", profile)

    def test_load_user_profile_no_user_id(self):
        um = _mock_user_memory(has_profile=True)
        c = _mock_container(user_memory=um)
        co = ConversationOrchestrator(container=c)
        profile = co._load_user_profile("")
        self.assertEqual(profile, {})

    def test_load_user_profile_no_memory(self):
        co = ConversationOrchestrator()
        profile = co._load_user_profile("u1")
        self.assertEqual(profile, {})


# ══════════════════════════════════════════════════════════════════════
# Tests — Response formatting
# ══════════════════════════════════════════════════════════════════════


class TestResponseFormatting(unittest.TestCase):

    def test_format_response_adds_conversation_id(self):
        result = _success_agent_result()
        formatted = ConversationOrchestrator._format_response(
            result, "conv_123", is_new=False,
        )
        self.assertEqual(formatted["meta"]["conversation_id"], "conv_123")
        self.assertTrue(formatted["success"])

    def test_format_response_marks_new(self):
        result = _success_agent_result()
        formatted = ConversationOrchestrator._format_response(
            result, "conv_123", is_new=True,
        )
        self.assertTrue(formatted["meta"]["new_conversation"])

    def test_format_response_preserves_all_fields(self):
        result = _success_agent_result()
        formatted = ConversationOrchestrator._format_response(
            result, "conv_123", is_new=False,
        )
        self.assertEqual(formatted["message"], result["message"])
        self.assertEqual(formatted["data"], result["data"])
        self.assertEqual(formatted["followups"], result["followups"])


# ══════════════════════════════════════════════════════════════════════
# Tests — Edge cases
# ══════════════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):

    def test_empty_message(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("", user_id="u1")
        self.assertTrue(result["success"])

    def test_long_message(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("x" * 10000, user_id="u1")
        self.assertTrue(result["success"])

    def test_concurrent_same_conversation(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        r1 = co.handle("test1", conversation_id="conv_123")
        r2 = co.handle("test2", conversation_id="conv_123")
        self.assertTrue(r1["success"])
        self.assertTrue(r2["success"])
        self.assertEqual(orch.orchestrate.call_count, 2)

    def test_multiple_conversations(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        r1 = co.handle("test1", user_id="u1", conversation_id="conv_a")
        r2 = co.handle("test2", user_id="u2", conversation_id="conv_b")
        self.assertTrue(r1["success"])
        self.assertTrue(r2["success"])

    def test_summaries_loaded_into_context(self):
        summary = MagicMock()
        summary.to_context_string.return_value = "Résumé des tours précédents."
        cm = _mock_conversation_memory(summaries=[summary])
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", conversation_id="conv_123")
        self.assertTrue(result["success"])
        # Verify summary was retrieved
        cm.retrieve.assert_called_once_with("conv_123", include_summaries=True)

    def test_no_user_memory_skips_action(self):
        cm = _mock_conversation_memory()
        sm = _mock_session_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=sm,
            user_memory=None,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", user_id="u1", conversation_id="conv_123")
        self.assertTrue(result["success"])

    def test_no_session_memory_skips_persistence(self):
        cm = _mock_conversation_memory()
        orch = MagicMock()
        orch.orchestrate.return_value = _success_agent_result()
        c = _mock_container(
            conversation_memory=cm,
            session_memory=None,
            orchestrator=orch,
        )
        co = ConversationOrchestrator(container=c)
        result = co.handle("test", user_id="u1", conversation_id="conv_123")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
