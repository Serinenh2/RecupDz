"""
Tests for ResponseOrchestrator.

Covers:
    - ResponseInput / ResponseOutput dataclasses
    - generate() happy path with PromptBuilder + LLM
    - generate_with_trace() returns PromptContext
    - Fallbacks when LLM unavailable / PromptBuilder fails
    - Follow-up generation and parsing
    - Validation: hallucination markers, internal leaks, length truncation
    - Safety output check via AISafetyLayer
    - Deterministic responses: greeting, no tool data, tool data
    - Error handling: never raises, safe fallback
    - Container wiring
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from apps.ai_assistant.enterprise.response_orchestrator import (
    ResponseInput,
    ResponseOrchestrator,
    ResponseOutput,
)


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _make_input(**overrides) -> ResponseInput:
    defaults = dict(
        message="Quels sont les codes déchets dangereux ?",
        tool_results=None,
        tool_name="",
        knowledge_context="",
        conversation_history=[],
        user_id="u1",
        user_language="fr",
        user_role="agent_collecte",
    )
    defaults.update(overrides)
    return ResponseInput(**defaults)


def _make_prompt_context(system_prompt="SYSTEM", history=None, message="msg"):
    ctx = MagicMock()
    ctx.system_prompt = system_prompt
    ctx.history = history or []
    ctx.message = message
    return ctx


def _make_tool_results(messages=None):
    tr = MagicMock()
    tr.messages = messages or ["Résultat : 5 codes dangereux trouvés"]
    return tr


def _make_container(prompt_builder=None, ollama=None, safety_layer=None):
    c = MagicMock()
    c.prompt_builder = prompt_builder
    c.ollama = ollama
    c.safety_layer = safety_layer
    return c


# ══════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════

class TestResponseInput(unittest.TestCase):

    def test_defaults(self):
        ri = ResponseInput(message="hi")
        self.assertEqual(ri.message, "hi")
        self.assertIsNone(ri.tool_results)
        self.assertEqual(ri.tool_name, "")
        self.assertFalse(ri.has_tool_results)
        self.assertFalse(ri.has_knowledge)
        self.assertFalse(ri.has_history)

    def test_has_tool_results_true(self):
        ri = ResponseInput(message="x", tool_results="something")
        self.assertTrue(ri.has_tool_results)

    def test_has_knowledge_true(self):
        ri = ResponseInput(message="x", knowledge_context="some knowledge")
        self.assertTrue(ri.has_knowledge)

    def test_has_history_true(self):
        ri = ResponseInput(message="x", conversation_history=[{"role": "user", "content": "hi"}])
        self.assertTrue(ri.has_history)

    def test_to_dict_truncates_message(self):
        ri = ResponseInput(message="x" * 200, tool_name="greeting")
        d = ri.to_dict()
        self.assertEqual(len(d["message"]), 100)
        self.assertEqual(d["tool_name"], "greeting")

    def test_immutable(self):
        ri = ResponseInput(message="hi")
        with self.assertRaises(AttributeError):
            ri.message = "bye"  # type: ignore[misc]


class TestResponseOutput(unittest.TestCase):

    def test_defaults(self):
        ro = ResponseOutput(success=True, response_text="hello")
        self.assertTrue(ro.success)
        self.assertEqual(ro.response_text, "hello")
        self.assertEqual(ro.followups, [])
        self.assertEqual(ro.meta, {})

    def test_to_dict(self):
        ro = ResponseOutput(
            success=True,
            response_text="hi",
            followups=["q1", "q2"],
            meta={"tool_name": "greeting"},
        )
        d = ro.to_dict()
        self.assertEqual(d["response_text"], "hi")
        self.assertEqual(len(d["followups"]), 2)
        self.assertEqual(d["meta"]["tool_name"], "greeting")

    def test_immutable(self):
        ro = ResponseOutput(success=True, response_text="x")
        with self.assertRaises(AttributeError):
            ro.success = False  # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════
# Happy path — generate()
# ══════════════════════════════════════════════════════════════════════

class TestGenerateHappyPath(unittest.TestCase):

    def test_full_pipeline(self):
        pb = MagicMock()
        pb.build_response_prompt.return_value = _make_prompt_context()
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value="Voici la réponse sur les déchets dangereux."
        llm.chat.side_effect = [
            "Voici la réponse sur les déchets dangereux.",
            json.dumps(["Qu'est-ce que le CID ?", "Comment classer ?"]),
        ]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(prompt_builder=pb, ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        inp = _make_input(
            tool_results=_make_tool_results(),
            tool_name="waste_tool",
            knowledge_context="Codes dangereux : 13.10*, 15.01*",
        )
        result = ro.generate(inp)

        self.assertTrue(result.success)
        self.assertIn("déchets dangereux", result.response_text)
        self.assertIsInstance(result.followups, list)
        self.assertFalse(result.meta.get("fallback", False))

    def test_generate_returns_response_output(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertIsInstance(result, ResponseOutput)

    def test_generate_with_trace_returns_tuple(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        output, ctx = ro.generate_with_trace(_make_input())
        self.assertIsInstance(output, ResponseOutput)
        # ctx is None when PromptBuilder unavailable
        self.assertIsNone(ctx)

    def test_generate_with_trace_full(self):
        pb = MagicMock()
        pb.build_response_prompt.return_value = _make_prompt_context()
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = "Réponse complète."
        llm.chat.side_effect = ["Réponse complète.", "[]"]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(prompt_builder=pb, ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        output, ctx = ro.generate_with_trace(_make_input(tool_results=_make_tool_results()))

        self.assertTrue(output.success)
        self.assertIsNotNone(ctx)


# ══════════════════════════════════════════════════════════════════════
# Fallbacks
# ══════════════════════════════════════════════════════════════════════

class TestFallbacks(unittest.TestCase):

    def test_llm_unavailable_returns_deterministic(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        inp = _make_input(tool_results=_make_tool_results())
        result = ro.generate(inp)
        self.assertTrue(result.success)
        self.assertIn("codes dangereux", result.response_text)

    def test_llm_unavailable_greeting(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        inp = _make_input(tool_name="greeting")
        result = ro.generate(inp)
        self.assertIn("RECUP-DZ", result.response_text)

    def test_prompt_builder_fails_uses_fallback_prompt(self):
        pb = MagicMock()
        pb.build_response_prompt.side_effect = Exception("PB crash")
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = "Réponse depuis LLM."
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(prompt_builder=pb, ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_results=_make_tool_results()))
        self.assertTrue(result.success)
        self.assertEqual(result.response_text, "Réponse depuis LLM.")

    def test_llm_returns_empty_falls_back_to_deterministic(self):
        pb = MagicMock()
        pb.build_response_prompt.return_value = _make_prompt_context()
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = ""
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(prompt_builder=pb, ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_results=_make_tool_results()))
        self.assertTrue(result.success)
        self.assertIn("codes dangereux", result.response_text)

    def test_llm_exception_falls_back(self):
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.side_effect = Exception("LLM timeout")
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertTrue(result.success)

    def test_total_failure_returns_fallback(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        # Force an error in _build_prompt
        with patch.object(ResponseOrchestrator, '_build_prompt', side_effect=Exception("boom")):
            result = ro.generate(_make_input())
        self.assertFalse(result.success)
        self.assertTrue(result.meta.get("fallback"))


# ══════════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════════

class TestValidation(unittest.TestCase):

    def test_truncation(self):
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = "x" * 5000
        llm.chat.side_effect = ["x" * 5000, "[]"]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container, max_response_length=2000)
        result = ro.generate(_make_input())
        self.assertIn("tronquée", result.response_text)

    def test_hallucination_markers_detected(self):
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = "Je ne sais pas vraiment."
        llm.chat.side_effect = ["Je ne sais pas vraiment.", "[]"]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertTrue(result.success)

    def test_internal_leaks_filtered(self):
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = 'Voici le résultat : {"tool": "waste_tool", "data": "x"}'
        llm.chat.side_effect = ['Voici le résultat : {"tool": "waste_tool", "data": "x"}', "[]"]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertNotIn('"tool":', result.response_text)

    def test_safety_layer_sanitizes(self):
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = "Contenu approprié."
        llm.chat.side_effect = ["Contenu approprié.", "[]"]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = True
        sl.check_output.return_value = check
        sl.sanitize_output.return_value = "Contenu filtré par la couche de sécurité."
        container = _make_container(ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertIn("filtré", result.response_text)
        sl.sanitize_output.assert_called_once()

    def test_safety_layer_exception_does_not_block(self):
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = "Réponse normale."
        llm.chat.side_effect = ["Réponse normale.", "[]"]
        sl = MagicMock()
        sl.check_output.side_effect = Exception("safety crash")
        container = _make_container(ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertTrue(result.success)
        self.assertEqual(result.response_text, "Réponse normale.")

    def test_empty_response_returns_fallback(self):
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = ""
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertTrue(result.success)


# ══════════════════════════════════════════════════════════════════════
# Follow-ups
# ══════════════════════════════════════════════════════════════════════

class TestFollowups(unittest.TestCase):

    def test_greeting_followups(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        inp = _make_input(tool_name="greeting")
        result = ro.generate(inp)
        self.assertEqual(len(result.followups), 3)
        self.assertIn("code déchet", result.followups[0])

    def test_llm_followups_json_array(self):
        pb = MagicMock()
        pb.build_followup_prompt.return_value = _make_prompt_context()
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.side_effect = [
            "Réponse principale.",
            json.dumps(["Question 1 ?", "Question 2 ?", "Question 3 ?"]),
        ]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(prompt_builder=pb, ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_results=_make_tool_results()))
        self.assertEqual(len(result.followups), 3)

    def test_followup_parse_markdown_fences(self):
        raw = '```json\n["Q1 ?", "Q2 ?"]\n```'
        parsed = ResponseOrchestrator._parse_followups(raw)
        self.assertEqual(parsed, ["Q1 ?", "Q2 ?"])

    def test_followup_parse_plain_json(self):
        parsed = ResponseOrchestrator._parse_followups('["A ?", "B ?"]')
        self.assertEqual(parsed, ["A ?", "B ?"])

    def test_followup_parse_invalid(self):
        parsed = ResponseOrchestrator._parse_followups("not json at all")
        self.assertEqual(parsed, [])

    def test_followup_parse_empty(self):
        self.assertEqual(ResponseOrchestrator._parse_followups(""), [])
        self.assertEqual(ResponseOrchestrator._parse_followups(None), [])

    def test_followup_limit_3(self):
        parsed = ResponseOrchestrator._parse_followups(
            json.dumps([f"Q{i}?" for i in range(10)])
        )
        self.assertEqual(len(parsed), 3)

    def test_no_followups_when_llm_unavailable(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_name="waste_tool", tool_results=_make_tool_results()))
        self.assertEqual(result.followups, [])


# ══════════════════════════════════════════════════════════════════════
# Deterministic responses
# ══════════════════════════════════════════════════════════════════════

class TestDeterministicResponses(unittest.TestCase):

    def test_greeting_response(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_name="greeting"))
        self.assertIn("RECUP-DZ", result.response_text)
        self.assertIn("assistant IA", result.response_text)

    def test_no_tool_results(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertIn("réponse précise", result.response_text)

    def test_tool_results_with_messages(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        tr = _make_tool_results(messages=["BSD-2025-001 créé", "Signature validée"])
        result = ro.generate(_make_input(tool_results=tr))
        self.assertIn("BSD-2025-001", result.response_text)

    def test_tool_results_as_dict(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_results={"total": 42, "type": "dangereux"}))
        self.assertIn("42", result.response_text)

    def test_tool_results_as_list(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_results=["item1", "item2"]))
        self.assertIn("item1", result.response_text)

    def test_tool_results_generic(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_results="raw string"))
        self.assertIn("données", result.response_text)


# ══════════════════════════════════════════════════════════════════════
# Meta / output assembly
# ══════════════════════════════════════════════════════════════════════

class TestOutputAssembly(unittest.TestCase):

    def test_meta_fields(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        inp = _make_input(
            tool_results=_make_tool_results(),
            tool_name="waste_tool",
            knowledge_context="some knowledge",
        )
        result = ro.generate(inp)
        self.assertEqual(result.meta["tool_name"], "waste_tool")
        self.assertTrue(result.meta["has_tool_results"])
        self.assertTrue(result.meta["has_knowledge"])
        self.assertIn("elapsed_ms", result.meta)
        self.assertIn("response_length", result.meta)

    def test_followup_count_in_meta(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input(tool_name="greeting"))
        self.assertEqual(result.meta["followup_count"], 3)

    def test_max_followups_configurable(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container, max_followups=1)
        result = ro.generate(_make_input(tool_name="greeting"))
        self.assertEqual(len(result.followups), 1)

    def test_to_dict(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        d = result.to_dict()
        self.assertIn("success", d)
        self.assertIn("response_text", d)
        self.assertIn("followups", d)
        self.assertIn("meta", d)


# ══════════════════════════════════════════════════════════════════════
# LLM call specifics
# ══════════════════════════════════════════════════════════════════════

class TestLLMCall(unittest.TestCase):

    def test_llm_call_uses_prompt_context(self):
        pb = MagicMock()
        ctx = _make_prompt_context(system_prompt="SYSTEM PROMPT", history=[{"role": "user", "content": "prev"}])
        pb.build_response_prompt.return_value = ctx
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = "Réponse."
        llm.chat.side_effect = ["Réponse.", "[]"]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(prompt_builder=pb, ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        ro.generate(_make_input(tool_results=_make_tool_results()))

        llm.chat.assert_any_call(
            message="Quels sont les codes déchets dangereux ?",
            history=[{"role": "user", "content": "prev"}],
            system_prompt="SYSTEM PROMPT",
        )

    def test_llm_call_fallback_prompt(self):
        llm = MagicMock()
        llm.is_available.return_value = True
        llm.chat.return_value = "Réponse."
        llm.chat.side_effect = ["Réponse.", "[]"]
        sl = MagicMock()
        check = MagicMock()
        check.blocked = False
        sl.check_output.return_value = check
        container = _make_container(ollama=llm, safety_layer=sl)

        ro = ResponseOrchestrator(container=container)
        ro.generate(_make_input())

        # Called with fallback system prompt
        call_args = llm.chat.call_args_list[0]
        self.assertIn("RECUP-DZ", call_args.kwargs.get("system_prompt", ""))


# ══════════════════════════════════════════════════════════════════════
# Error handling — never raises
# ══════════════════════════════════════════════════════════════════════

class TestErrorHandling(unittest.TestCase):

    def test_never_raises(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        # Should not raise even with minimal input
        result = ro.generate(_make_input())
        self.assertIsInstance(result, ResponseOutput)

    def test_exception_in_generate_returns_fallback(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        with patch.object(ResponseOrchestrator, '_build_prompt', side_effect=Exception("boom")):
            result = ro.generate(_make_input())
        self.assertFalse(result.success)
        self.assertIn("error", result.meta)

    def test_exception_in_trace_returns_fallback(self):
        container = _make_container()
        ro = ResponseOrchestrator(container=container)
        with patch.object(ResponseOrchestrator, '_build_prompt', side_effect=Exception("boom")):
            output, ctx = ro.generate_with_trace(_make_input())
        self.assertFalse(output.success)
        self.assertIsNone(ctx)

    def test_llm_available_check_exception(self):
        llm = MagicMock()
        llm.is_available.side_effect = Exception("health crash")
        container = _make_container(ollama=llm)
        ro = ResponseOrchestrator(container=container)
        result = ro.generate(_make_input())
        self.assertTrue(result.success)


# ══════════════════════════════════════════════════════════════════════
# Container wiring
# ══════════════════════════════════════════════════════════════════════

class TestContainerWiring(unittest.TestCase):

    def test_container_has_response_orchestrator(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        ro = c.response_orchestrator
        self.assertIsInstance(ro, ResponseOrchestrator)

    def test_container_response_orchestrator_singleton(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        ro1 = c.response_orchestrator
        ro2 = c.response_orchestrator
        self.assertIs(ro1, ro2)


if __name__ == "__main__":
    unittest.main()
