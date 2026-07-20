"""
Tests for EnterpriseConversationMemory — unified production-grade conversation store.

Covers:
    - MemoryTurn / MemorySummary / MemorySnapshot / MemoryMetadata data contracts
    - Store / retrieve / delete
    - Sliding window + auto-summarization
    - Context compression (manual)
    - Retrieval: by conversation, by user, by entity, recent
    - Context string and LLM message generation
    - Expiration: TTL, LRU, turn-count, manual
    - Query: exists, metadata, counts, stats, list
    - Edge cases, concurrency, framework independence
"""

import time
import threading
import unittest

from apps.ai_assistant.enterprise.conversation_memory import (
    _DEFAULT_MAX_CONVERSATIONS,
    _DEFAULT_MAX_TURNS,
    _DEFAULT_SUMMARY_THRESHOLD,
    _DEFAULT_TTL_SECONDS,
    EnterpriseConversationMemory,
    ExpirationPolicy,
    MemoryMetadata,
    MemorySnapshot,
    MemorySummary,
    MemoryTurn,
)


# ════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════


def _make_turn(
    role: str = "user",
    content: str = "test message",
    intent: str = "",
    entities: dict = None,
    references: list = None,
    tool_name: str = "",
    tool_action: str = "",
    tool_result_summary: str = "",
    confidence: float = 0.0,
) -> MemoryTurn:
    return MemoryTurn(
        role=role,
        content=content,
        intent=intent,
        entities=entities or {},
        references=references or [],
        tool_name=tool_name,
        tool_action=tool_action,
        tool_result_summary=tool_result_summary,
        confidence=confidence,
    )


def _make_conversation(
    mem: EnterpriseConversationMemory,
    conv_id: str = "conv_1",
    n: int = 4,
    user_id: str = "",
) -> None:
    """Store n alternating user/assistant turns."""
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"Message {i}" if role == "user" else f"Response {i}"
        turn = _make_turn(role=role, content=content)
        mem.store(conv_id, turn, user_id=user_id)


def _make_memory(**kwargs) -> EnterpriseConversationMemory:
    return EnterpriseConversationMemory(**kwargs)


# ════════════════════════════════════════════════════════════════════════
# Data Contract: MemoryTurn
# ════════════════════════════════════════════════════════════════════════


class TestMemoryTurn(unittest.TestCase):

    def test_creation_minimal(self):
        t = MemoryTurn(role="user", content="hello")
        self.assertEqual(t.role, "user")
        self.assertEqual(t.content, "hello")
        self.assertEqual(t.intent, "")
        self.assertEqual(t.entities, {})
        self.assertEqual(t.references, [])
        self.assertEqual(t.tool_name, "")

    def test_creation_full(self):
        t = MemoryTurn(
            role="user", content="query",
            intent="waste_search", confidence=0.95,
            entities={"waste": "20.01.01"},
            references=["BSD-2026-001"],
            tool_name="waste_tool", tool_action="search",
            tool_result_summary="Found 5 results",
        )
        self.assertEqual(t.intent, "waste_search")
        self.assertAlmostEqual(t.confidence, 0.95)
        self.assertEqual(t.entities["waste"], "20.01.01")
        self.assertEqual(t.references, ["BSD-2026-001"])

    def test_to_dict_minimal(self):
        t = MemoryTurn(role="user", content="hello")
        d = t.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "hello")
        self.assertIn("timestamp", d)
        self.assertNotIn("intent", d)
        self.assertNotIn("entities", d)

    def test_to_dict_full(self):
        t = MemoryTurn(
            role="user", content="q",
            intent="search", confidence=0.8,
            entities={"w": "20.01.01"},
            references=["R1"],
            tool_name="waste_tool", tool_action="search",
            tool_result_summary="ok",
        )
        d = t.to_dict()
        self.assertEqual(d["intent"], "search")
        self.assertEqual(d["confidence"], 0.8)
        self.assertEqual(d["entities"], {"w": "20.01.01"})
        self.assertEqual(d["references"], ["R1"])
        self.assertEqual(d["tool_name"], "waste_tool")

    def test_to_llm_dict(self):
        t = MemoryTurn(role="user", content="hi")
        d = t.to_llm_dict()
        self.assertEqual(d, {"role": "user", "content": "hi"})

    def test_frozen(self):
        t = MemoryTurn(role="user", content="x")
        with self.assertRaises(AttributeError):
            t.role = "assistant"


# ════════════════════════════════════════════════════════════════════════
# Data Contract: MemorySummary
# ════════════════════════════════════════════════════════════════════════


class TestMemorySummary(unittest.TestCase):

    def test_creation(self):
        s = MemorySummary(
            summary_text="3 questions posées",
            turns_compressed=3,
            intents=["waste_search"],
            entities_mentioned=["20.01.01"],
            tools_used=["waste_tool"],
            user_questions=["Q1", "Q2", "Q3"],
        )
        self.assertEqual(s.turns_compressed, 3)
        self.assertEqual(s.intents, ["waste_search"])

    def test_to_dict(self):
        s = MemorySummary(
            summary_text="summary",
            turns_compressed=2,
            intents=["search"],
            entities_mentioned=["E1"],
            tools_used=["T1"],
            user_questions=["Q1"],
        )
        d = s.to_dict()
        self.assertEqual(d["summary_text"], "summary")
        self.assertEqual(d["turns_compressed"], 2)
        self.assertEqual(d["intents"], ["search"])
        self.assertEqual(d["entities_mentioned"], ["E1"])
        self.assertEqual(d["tools_used"], ["T1"])
        self.assertEqual(d["user_questions"], ["Q1"])

    def test_to_dict_omits_empty(self):
        s = MemorySummary(summary_text="x")
        d = s.to_dict()
        self.assertNotIn("intents", d)
        self.assertNotIn("entities_mentioned", d)

    def test_to_context_string_with_data(self):
        s = MemorySummary(
            summary_text="test",
            turns_compressed=5,
            intents=["search", "greeting"],
            entities_mentioned=["E1", "E2"],
            tools_used=["tool_a"],
            user_questions=["Q1", "Q2"],
        )
        ctx = s.to_context_string()
        self.assertIn("5 ancien(s)", ctx)
        self.assertIn("2 question(s)", ctx)
        self.assertIn("search", ctx)
        self.assertIn("tool_a", ctx)
        self.assertIn("E1", ctx)

    def test_to_context_string_empty(self):
        s = MemorySummary(summary_text="x")
        ctx = s.to_context_string()
        self.assertIn("Résumé de conversation", ctx)

    def test_frozen(self):
        s = MemorySummary(summary_text="x")
        with self.assertRaises(AttributeError):
            s.summary_text = "y"


# ════════════════════════════════════════════════════════════════════════
# Data Contract: MemorySnapshot
# ════════════════════════════════════════════════════════════════════════


class TestMemorySnapshot(unittest.TestCase):

    def test_empty(self):
        snap = MemorySnapshot()
        self.assertFalse(snap.has_data)
        self.assertEqual(snap.turn_count, 0)
        self.assertEqual(snap.summary_count, 0)

    def test_has_data_with_turns(self):
        t = MemoryTurn(role="user", content="hi")
        snap = MemorySnapshot(turns=[t])
        self.assertTrue(snap.has_data)
        self.assertEqual(snap.turn_count, 1)

    def test_has_data_with_summaries(self):
        s = MemorySummary(summary_text="x")
        snap = MemorySnapshot(summaries=[s])
        self.assertTrue(snap.has_data)
        self.assertEqual(snap.summary_count, 1)

    def test_to_dict(self):
        t = MemoryTurn(role="user", content="hi")
        s = MemorySummary(summary_text="x")
        snap = MemorySnapshot(
            turns=[t], summaries=[s],
            total_turns=10, total_summaries=2, compressed_turns=8,
        )
        d = snap.to_dict()
        self.assertEqual(d["total_turns"], 10)
        self.assertEqual(d["total_summaries"], 2)
        self.assertEqual(d["compressed_turns"], 8)
        self.assertEqual(len(d["turns"]), 1)
        self.assertEqual(len(d["summaries"]), 1)

    def test_to_context_string(self):
        t = MemoryTurn(role="user", content="Bonjour")
        s = MemorySummary(
            summary_text="Résumé", turns_compressed=3,
        )
        snap = MemorySnapshot(turns=[t], summaries=[s])
        ctx = snap.to_context_string()
        self.assertIn("[Résumé]", ctx)
        self.assertIn("Utilisateur: Bonjour", ctx)

    def test_frozen(self):
        snap = MemorySnapshot()
        with self.assertRaises(AttributeError):
            snap.turns = []


# ════════════════════════════════════════════════════════════════════════
# Data Contract: MemoryMetadata
# ════════════════════════════════════════════════════════════════════════


class TestMemoryMetadata(unittest.TestCase):

    def test_creation(self):
        m = MemoryMetadata(conversation_id="c1", user_id="u1")
        self.assertEqual(m.conversation_id, "c1")
        self.assertEqual(m.user_id, "u1")
        self.assertEqual(m.turn_count, 0)

    def test_to_dict(self):
        m = MemoryMetadata(
            conversation_id="c1", user_id="u1",
            turn_count=5, intents=["search"],
            entities=["E1"], tools_used=["T1"],
        )
        d = m.to_dict()
        self.assertEqual(d["conversation_id"], "c1")
        self.assertEqual(d["turn_count"], 5)
        self.assertEqual(d["intents"], ["search"])

    def test_to_dict_omits_empty(self):
        m = MemoryMetadata(conversation_id="c1")
        d = m.to_dict()
        self.assertNotIn("intents", d)
        self.assertNotIn("entities", d)


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Store
# ════════════════════════════════════════════════════════════════════════


class TestMemoryStore(unittest.TestCase):

    def test_store_single_turn(self):
        mem = _make_memory()
        mem.store("c1", _make_turn())
        self.assertTrue(mem.exists("c1"))
        self.assertEqual(mem.conversation_count(), 1)

    def test_store_multiple_turns(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=6)
        self.assertEqual(mem.total_turns(), 6)

    def test_store_tracks_user_id(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(), user_id="alice")
        meta = mem.get_metadata("c1")
        self.assertEqual(meta.user_id, "alice")

    def test_store_tracks_intents(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(intent="waste_search"))
        mem.store("c1", _make_turn(intent="greeting"))
        meta = mem.get_metadata("c1")
        self.assertEqual(meta.intents, ["waste_search", "greeting"])

    def test_store_deduplicates_intents(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(intent="waste_search"))
        mem.store("c1", _make_turn(intent="waste_search"))
        meta = mem.get_metadata("c1")
        self.assertEqual(meta.intents, ["waste_search"])

    def test_store_tracks_entities(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(entities={"waste": "20.01.01"}))
        meta = mem.get_metadata("c1")
        self.assertIn("20.01.01", meta.entities)

    def test_store_tracks_entities_list(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(entities={"items": ["A", "B"]}))
        meta = mem.get_metadata("c1")
        self.assertIn("A", meta.entities)
        self.assertIn("B", meta.entities)

    def test_store_tracks_tools(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(tool_name="waste_tool"))
        mem.store("c1", _make_turn(tool_name="bsd_tool"))
        meta = mem.get_metadata("c1")
        self.assertEqual(meta.tools_used, ["waste_tool", "bsd_tool"])

    def test_store_updates_last_active(self):
        mem = _make_memory()
        mem.store("c1", _make_turn())
        meta1 = mem.get_metadata("c1")
        t1 = meta1.last_active
        time.sleep(0.01)
        mem.store("c1", _make_turn())
        meta2 = mem.get_metadata("c1")
        self.assertGreaterEqual(meta2.last_active, t1)


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Sliding Window + Auto-Summarization
# ════════════════════════════════════════════════════════════════════════


class TestMemorySlidingWindow(unittest.TestCase):

    def test_window_not_exceeded(self):
        mem = _make_memory(max_turns=10)
        _make_conversation(mem, "c1", n=5)
        snap = mem.retrieve("c1")
        self.assertEqual(snap.turn_count, 5)
        self.assertEqual(snap.total_summaries, 0)

    def test_auto_summarize_triggers(self):
        mem = _make_memory(max_turns=5, auto_summarize=True)
        _make_conversation(mem, "c1", n=8)
        snap = mem.retrieve("c1")
        self.assertLessEqual(snap.turn_count, 5)
        self.assertGreater(snap.total_summaries, 0)

    def test_auto_summarize_disabled(self):
        mem = _make_memory(max_turns=5, auto_summarize=False)
        _make_conversation(mem, "c1", n=8)
        snap = mem.retrieve("c1")
        self.assertEqual(snap.turn_count, 8)
        self.assertEqual(snap.total_summaries, 0)

    def test_summary_preserves_recent_turns(self):
        mem = _make_memory(max_turns=3)
        _make_conversation(mem, "c1", n=6)
        snap = mem.retrieve("c1")
        # Recent turns should be the last 3: [Response 3, Message 4, Response 5]
        self.assertEqual(snap.turn_count, 3)
        self.assertEqual(snap.turns[0].content, "Response 3")
        self.assertEqual(snap.turns[2].content, "Response 5")

    def test_compressed_turns_tracked(self):
        mem = _make_memory(max_turns=3)
        _make_conversation(mem, "c1", n=6)
        meta = mem.get_metadata("c1")
        self.assertGreater(meta.compressed_turns, 0)

    def test_summary_contains_intents(self):
        mem = _make_memory(max_turns=3)
        mem.store("c1", _make_turn(content="Q1", intent="waste_search"))
        mem.store("c1", _make_turn(content="A1"))
        mem.store("c1", _make_turn(content="Q2", intent="bsd_search"))
        mem.store("c1", _make_turn(content="A2"))
        mem.store("c1", _make_turn(content="Q3"))
        snap = mem.retrieve("c1")
        if snap.summaries:
            self.assertIn("waste_search", snap.summaries[0].intents)

    def test_summary_contains_tools(self):
        mem = _make_memory(max_turns=3)
        mem.store("c1", _make_turn(tool_name="waste_tool"))
        mem.store("c1", _make_turn())
        mem.store("c1", _make_turn(tool_name="bsd_tool"))
        mem.store("c1", _make_turn())
        mem.store("c1", _make_turn())
        snap = mem.retrieve("c1")
        if snap.summaries:
            self.assertIn("waste_tool", snap.summaries[0].tools_used)


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Manual Compression
# ════════════════════════════════════════════════════════════════════════


class TestMemoryCompression(unittest.TestCase):

    def test_compress_manually(self):
        mem = _make_memory(max_turns=100, auto_summarize=False)
        _make_conversation(mem, "c1", n=8)
        summary = mem.compress("c1", keep_recent=3)
        self.assertIsNotNone(summary)
        self.assertEqual(summary.turns_compressed, 5)
        snap = mem.retrieve("c1")
        self.assertEqual(snap.turn_count, 3)

    def test_compress_nothing_to_compress(self):
        mem = _make_memory(max_turns=100)
        _make_conversation(mem, "c1", n=3)
        summary = mem.compress("c1", keep_recent=5)
        self.assertIsNone(summary)

    def test_compress_nonexistent_conversation(self):
        mem = _make_memory()
        summary = mem.compress("nonexistent")
        self.assertIsNone(summary)

    def test_compress_preserves_recent(self):
        mem = _make_memory(max_turns=100, auto_summarize=False)
        _make_conversation(mem, "c1", n=6)
        # n=6: [Msg 0, Resp 1, Msg 2, Resp 3, Msg 4, Resp 5]
        mem.compress("c1", keep_recent=2)
        # Remaining: [Msg 4, Resp 5]
        snap = mem.retrieve("c1")
        self.assertEqual(snap.turn_count, 2)
        self.assertEqual(snap.turns[0].content, "Message 4")
        self.assertEqual(snap.turns[1].content, "Response 5")


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Retrieve
# ════════════════════════════════════════════════════════════════════════


class TestMemoryRetrieve(unittest.TestCase):

    def test_retrieve_empty(self):
        mem = _make_memory()
        snap = mem.retrieve("nonexistent")
        self.assertFalse(snap.has_data)
        self.assertEqual(snap.turn_count, 0)

    def test_retrieve_basic(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=4)
        snap = mem.retrieve("c1")
        self.assertEqual(snap.turn_count, 4)
        self.assertTrue(snap.has_data)

    def test_retrieve_max_turns(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=6)
        snap = mem.retrieve("c1", max_turns=3)
        self.assertEqual(snap.turn_count, 3)

    def test_retrieve_exclude_summaries(self):
        mem = _make_memory(max_turns=3)
        _make_conversation(mem, "c1", n=6)
        snap = mem.retrieve("c1", include_summaries=False)
        self.assertEqual(snap.summary_count, 0)

    def test_retrieve_by_user(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=3, user_id="alice")
        _make_conversation(mem, "c2", n=3, user_id="bob")
        _make_conversation(mem, "c3", n=3, user_id="alice")
        results = mem.retrieve_by_user("alice")
        self.assertEqual(len(results), 2)

    def test_retrieve_by_user_max(self):
        mem = _make_memory()
        for i in range(5):
            _make_conversation(mem, f"c{i}", n=2, user_id="alice")
        results = mem.retrieve_by_user("alice", max_conversations=2)
        self.assertEqual(len(results), 2)

    def test_retrieve_by_entity(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(entities={"waste": "20.01.01"}))
        mem.store("c1", _make_turn())
        mem.store("c2", _make_turn(entities={"waste": "15.01.01"}))
        mem.store("c2", _make_turn())
        results = mem.retrieve_by_entity("20.01.01")
        self.assertEqual(len(results), 1)

    def test_retrieve_by_entity_max(self):
        mem = _make_memory()
        for i in range(5):
            mem.store(f"c{i}", _make_turn(entities={"w": "E1"}))
            mem.store(f"c{i}", _make_turn())
        results = mem.retrieve_by_entity("E1", max_conversations=3)
        self.assertEqual(len(results), 3)

    def test_retrieve_recent(self):
        mem = _make_memory()
        for i in range(5):
            _make_conversation(mem, f"c{i}", n=2)
        results = mem.retrieve_recent(max_conversations=3, max_turns_per=2)
        self.assertEqual(len(results), 3)

    def test_retrieve_total_turns(self):
        mem = _make_memory(max_turns=100)
        _make_conversation(mem, "c1", n=6)
        _make_conversation(mem, "c2", n=4)
        self.assertEqual(mem.total_turns(), 10)


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Context
# ════════════════════════════════════════════════════════════════════════


class TestMemoryContext(unittest.TestCase):

    def test_get_context_string(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=4)
        ctx = mem.get_context_string("c1")
        self.assertIn("Message 0", ctx)
        self.assertIn("Response 1", ctx)
        self.assertIn("Message 2", ctx)
        self.assertIn("Response 3", ctx)

    def test_get_context_string_empty(self):
        mem = _make_memory()
        ctx = mem.get_context_string("nonexistent")
        self.assertEqual(ctx, "")

    def test_get_llm_messages(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=4)
        msgs = mem.get_llm_messages("c1")
        self.assertEqual(len(msgs), 4)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

    def test_get_llm_messages_with_summaries(self):
        mem = _make_memory(max_turns=3)
        _make_conversation(mem, "c1", n=6)
        msgs = mem.get_llm_messages("c1")
        # Should have at least one system message (summary) + recent turns
        self.assertGreater(len(msgs), 3)
        self.assertEqual(msgs[0]["role"], "system")

    def test_get_llm_messages_max_turns(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=6)
        msgs = mem.get_llm_messages("c1", max_turns=2)
        self.assertEqual(len(msgs), 2)


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Expiration
# ════════════════════════════════════════════════════════════════════════


class TestMemoryExpiration(unittest.TestCase):

    def test_expire_ttl(self):
        mem = _make_memory(
            expiration_policy=ExpirationPolicy.TTL,
            ttl_seconds=0.01,
        )
        mem.store("c1", _make_turn())
        time.sleep(0.02)
        expired = mem.expire()
        self.assertEqual(expired, 1)
        self.assertFalse(mem.exists("c1"))

    def test_expire_ttl_not_yet(self):
        mem = _make_memory(
            expiration_policy=ExpirationPolicy.TTL,
            ttl_seconds=10.0,
        )
        mem.store("c1", _make_turn())
        expired = mem.expire()
        self.assertEqual(expired, 0)
        self.assertTrue(mem.exists("c1"))

    def test_expire_lru(self):
        mem = _make_memory(
            max_conversations=5,
            expiration_policy=ExpirationPolicy.LRU,
        )
        for i in range(6):
            mem.store(f"c{i}", _make_turn())
        # LRU eviction happened during store — now expire should clean any residual
        expired = mem.expire()
        # After store enforcement, we're at max or below
        self.assertLessEqual(mem.conversation_count(), 5)

    def test_expire_turn_count(self):
        mem = _make_memory(
            max_turns=3,
            expiration_policy=ExpirationPolicy.TURN_COUNT,
        )
        _make_conversation(mem, "c1", n=20)
        expired = mem.expire()
        self.assertGreaterEqual(expired, 1)

    def test_expire_manual(self):
        mem = _make_memory(
            expiration_policy=ExpirationPolicy.MANUAL,
        )
        mem.store("c1", _make_turn())
        expired = mem.expire()
        self.assertEqual(expired, 0)
        self.assertTrue(mem.exists("c1"))

    def test_delete(self):
        mem = _make_memory()
        mem.store("c1", _make_turn())
        result = mem.delete("c1")
        self.assertTrue(result)
        self.assertFalse(mem.exists("c1"))

    def test_delete_nonexistent(self):
        mem = _make_memory()
        result = mem.delete("nonexistent")
        self.assertFalse(result)


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Query
# ════════════════════════════════════════════════════════════════════════


class TestMemoryQuery(unittest.TestCase):

    def test_exists(self):
        mem = _make_memory()
        self.assertFalse(mem.exists("c1"))
        mem.store("c1", _make_turn())
        self.assertTrue(mem.exists("c1"))

    def test_get_metadata(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(), user_id="alice")
        meta = mem.get_metadata("c1")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.user_id, "alice")

    def test_get_metadata_nonexistent(self):
        mem = _make_memory()
        meta = mem.get_metadata("nonexistent")
        self.assertIsNone(meta)

    def test_conversation_count(self):
        mem = _make_memory()
        self.assertEqual(mem.conversation_count(), 0)
        mem.store("c1", _make_turn())
        mem.store("c2", _make_turn())
        self.assertEqual(mem.conversation_count(), 2)

    def test_total_turns(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=3)
        _make_conversation(mem, "c2", n=2)
        self.assertEqual(mem.total_turns(), 5)

    def test_total_summaries(self):
        mem = _make_memory(max_turns=3)
        _make_conversation(mem, "c1", n=6)
        self.assertGreater(mem.total_summaries(), 0)

    def test_list_conversations(self):
        mem = _make_memory()
        mem.store("c1", _make_turn())
        mem.store("c2", _make_turn())
        convs = mem.list_conversations()
        self.assertEqual(len(convs), 2)
        self.assertIn("c1", convs)
        self.assertIn("c2", convs)

    def test_stats(self):
        mem = _make_memory(max_turns=5, max_conversations=50)
        _make_conversation(mem, "c1", n=3)
        s = mem.stats()
        self.assertEqual(s["conversations"], 1)
        self.assertEqual(s["total_turns"], 3)
        self.assertEqual(s["max_turns"], 5)
        self.assertEqual(s["max_conversations"], 50)
        self.assertEqual(s["expiration_policy"], "lru")
        self.assertTrue(s["auto_summarize"])


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Edge Cases
# ════════════════════════════════════════════════════════════════════════


class TestMemoryEdgeCases(unittest.TestCase):

    def test_same_conversation_id_reuses(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(content="A"))
        mem.store("c1", _make_turn(content="B"))
        snap = mem.retrieve("c1")
        self.assertEqual(snap.turn_count, 2)

    def test_many_conversations(self):
        mem = _make_memory(max_conversations=50)
        for i in range(30):
            _make_conversation(mem, f"c{i}", n=2)
        self.assertEqual(mem.conversation_count(), 30)

    def test_special_characters_in_content(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(content="Déchets: 20.01.01 €100"))
        snap = mem.retrieve("c1")
        self.assertIn("Déchets", snap.turns[0].content)

    def test_empty_content(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(content=""))
        snap = mem.retrieve("c1")
        self.assertEqual(snap.turns[0].content, "")

    def test_unicode_content(self):
        mem = _make_memory()
        mem.store("c1", _make_turn(content="العربية 日本語"))
        snap = mem.retrieve("c1")
        self.assertIn("العربية", snap.turns[0].content)


# ════════════════════════════════════════════════════════════════════════
# EnterpriseConversationMemory — Concurrency
# ════════════════════════════════════════════════════════════════════════


class TestMemoryConcurrency(unittest.TestCase):

    def test_concurrent_stores(self):
        mem = _make_memory(max_turns=100)
        errors = []

        def writer(conv_id: str, n: int):
            try:
                for i in range(n):
                    mem.store(conv_id, _make_turn(content=f"msg_{i}"))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"c{i}", 20))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(mem.conversation_count(), 5)

    def test_concurrent_reads_writes(self):
        mem = _make_memory()
        _make_conversation(mem, "c1", n=10)
        errors = []

        def reader():
            try:
                for _ in range(50):
                    mem.retrieve("c1")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    mem.store("c1", _make_turn(content=f"new_{i}"))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)


# ════════════════════════════════════════════════════════════════════════
# Framework Independence
# ════════════════════════════════════════════════════════════════════════


class TestMemoryFrameworkIndependence(unittest.TestCase):

    def test_no_django_imports(self):
        import importlib
        import apps.ai_assistant.enterprise.conversation_memory as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    self.assertNotIn("django", stripped.lower(),
                                     f"Django import found: {stripped}")

    def test_no_repository_imports(self):
        import importlib
        import apps.ai_assistant.enterprise.conversation_memory as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    self.assertNotIn("repository", stripped.lower(),
                                     f"Repository import found: {stripped}")

    def test_no_orm_queries(self):
        import importlib
        import apps.ai_assistant.enterprise.conversation_memory as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            content = f.read()
        self.assertNotIn(".objects.", content)
        self.assertNotIn(".save(", content)
        self.assertNotIn(".filter(", content)

    def test_dataclasses_frozen(self):
        self.assertTrue(MemoryTurn.__dataclass_params__.frozen)
        self.assertTrue(MemorySummary.__dataclass_params__.frozen)
        self.assertTrue(MemorySnapshot.__dataclass_params__.frozen)

    def test_metadata_mutable(self):
        self.assertFalse(MemoryMetadata.__dataclass_params__.frozen)


# ════════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════════


class TestMemoryConstants(unittest.TestCase):

    def test_default_max_turns(self):
        self.assertEqual(_DEFAULT_MAX_TURNS, 20)

    def test_default_max_conversations(self):
        self.assertEqual(_DEFAULT_MAX_CONVERSATIONS, 100)

    def test_default_summary_threshold(self):
        self.assertEqual(_DEFAULT_SUMMARY_THRESHOLD, 5)

    def test_default_ttl(self):
        self.assertEqual(_DEFAULT_TTL_SECONDS, 3600.0)

    def test_expiration_policies(self):
        self.assertEqual(ExpirationPolicy.TTL.value, "ttl")
        self.assertEqual(ExpirationPolicy.LRU.value, "lru")
        self.assertEqual(ExpirationPolicy.TURN_COUNT.value, "turn_count")
        self.assertEqual(ExpirationPolicy.MANUAL.value, "manual")


# ════════════════════════════════════════════════════════════════════════
# Integration — Full Pipeline
# ════════════════════════════════════════════════════════════════════════


class TestMemoryIntegration(unittest.TestCase):

    def test_full_lifecycle(self):
        mem = _make_memory(max_turns=5, auto_summarize=True)

        # 1. Store initial conversation
        mem.store("conv_1", _make_turn(
            content="Bonjour", intent="greeting",
        ), user_id="alice")
        mem.store("conv_1", _make_turn(
            role="assistant", content="Bonjour! Comment puis-je vous aider?",
        ))
        mem.store("conv_1", _make_turn(
            content="Combien de BSD en attente ?",
            intent="waste_search", entities={"type": "BSD"},
            tool_name="bsd_tool", tool_action="search",
        ))
        mem.store("conv_1", _make_turn(
            role="assistant", content="Il y a 12 BSD en attente.",
        ))

        # 2. Verify retrieval
        snap = mem.retrieve("conv_1")
        self.assertTrue(snap.has_data)
        self.assertEqual(snap.turn_count, 4)

        # 3. Verify context string
        ctx = mem.get_context_string("conv_1")
        self.assertIn("Bonjour", ctx)

        # 4. Verify LLM messages
        msgs = mem.get_llm_messages("conv_1")
        self.assertEqual(len(msgs), 4)
        self.assertEqual(msgs[0]["role"], "user")

        # 5. Verify metadata
        meta = mem.get_metadata("conv_1")
        self.assertEqual(meta.user_id, "alice")
        self.assertIn("greeting", meta.intents)
        self.assertIn("waste_search", meta.intents)
        self.assertIn("bsd_tool", meta.tools_used)

        # 6. Store more turns to trigger summarization
        for i in range(6):
            role = "user" if i % 2 == 0 else "assistant"
            mem.store("conv_1", _make_turn(
                role=role,
                content=f"Turn {i + 4}",
                intent="follow_up" if role == "user" else "",
            ))

        # 7. Verify summarization happened
        snap2 = mem.retrieve("conv_1")
        self.assertGreater(snap2.total_summaries, 0)
        self.assertLessEqual(snap2.turn_count, 5)

        # 8. Verify context includes summaries
        ctx2 = mem.get_context_string("conv_1")
        self.assertIn("Résumé", ctx2)

        # 9. Verify user retrieval
        user_results = mem.retrieve_by_user("alice")
        self.assertGreater(len(user_results), 0)

        # 10. Verify stats
        stats = mem.stats()
        self.assertGreater(stats["conversations"], 0)
        self.assertGreater(stats["total_turns"], 0)

    def test_multi_conversation_with_entity_search(self):
        mem = _make_memory(max_turns=10)

        # Conversation 1: waste search
        mem.store("c1", _make_turn(
            content="BSD-2026-001 status?",
            entities={"bsd": "BSD-2026-001"},
        ))
        mem.store("c1", _make_turn(
            role="assistant", content="En attente.",
        ))

        # Conversation 2: different entity
        mem.store("c2", _make_turn(
            content="Nomenclature 20.01.01?",
            entities={"nomenclature": "20.01.01"},
        ))
        mem.store("c2", _make_turn(
            role="assistant", content="Dangereux.",
        ))

        # 3. Search by entity
        results = mem.retrieve_by_entity("BSD-2026-001")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].turns[0].content, "BSD-2026-001 status?")

        results2 = mem.retrieve_by_entity("20.01.01")
        self.assertEqual(len(results2), 1)

    def test_compression_and_retrieval(self):
        mem = _make_memory(max_turns=100, auto_summarize=False)
        _make_conversation(mem, "c1", n=10)

        # Manually compress
        summary = mem.compress("c1", keep_recent=3)
        self.assertIsNotNone(summary)
        self.assertEqual(summary.turns_compressed, 7)

        # Retrieve and verify
        snap = mem.retrieve("c1")
        self.assertEqual(snap.turn_count, 3)
        self.assertEqual(snap.summary_count, 1)
        self.assertEqual(snap.compressed_turns, 7)

        # Context string includes summary
        ctx = mem.get_context_string("c1")
        self.assertIn("Résumé", ctx)


if __name__ == "__main__":
    unittest.main()
