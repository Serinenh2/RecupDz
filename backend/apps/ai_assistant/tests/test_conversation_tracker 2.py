"""
Unit tests for ConversationTracker — structured conversation memory with auto-summarization.

Tests cover:
  - ConversationTurn: creation, to_dict, to_llm_dict
  - ConversationSummary: creation, to_dict, to_context_string
  - ConversationTracker: add_turn, sliding window, auto-summarize
  - ConversationTracker: get_turns, get_llm_messages, get_summary
  - ConversationTracker: tool history, entities, intents
  - ConversationTracker: clear, delete, stats, thread safety
  - MemoryManager integration: store_turn, get_tracker_summary, get_tool_history
"""

from __future__ import annotations

import threading
import time
import unittest

from apps.ai_assistant.memory.conversation_tracker import (
    ConversationSummary,
    ConversationTracker,
    ConversationTurn,
)


# ── ConversationTurn ─────────────────────────────────────────────────


class TestConversationTurn(unittest.TestCase):
    """ConversationTurn dataclass."""

    def test_basic_creation(self):
        turn = ConversationTurn(role="user", content="Bonjour")
        self.assertEqual(turn.role, "user")
        self.assertEqual(turn.content, "Bonjour")
        self.assertIsInstance(turn.timestamp, float)
        self.assertEqual(turn.intent, "")
        self.assertEqual(turn.entities, {})
        self.assertIsNone(turn.tool_used)
        self.assertEqual(turn.tool_history, [])

    def test_full_creation(self):
        turn = ConversationTurn(
            role="assistant",
            content="Voici les résultats",
            intent="waste_tool",
            selection_source="hermes+ai_router",
            entities={"waste_codes": ["15.01.01"]},
            tool_used="waste_tool",
            tool_action="search",
            tool_needed=True,
            hermes_confidence=0.9,
            tool_history=[{"tool": "nomenclature_tool", "action": "search"}],
        )
        self.assertEqual(turn.intent, "waste_tool")
        self.assertEqual(turn.tool_used, "waste_tool")
        self.assertTrue(turn.tool_needed)
        self.assertEqual(turn.hermes_confidence, 0.9)
        self.assertEqual(len(turn.tool_history), 1)

    def test_to_dict_minimal(self):
        turn = ConversationTurn(role="user", content="test")
        d = turn.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "test")
        self.assertIn("timestamp", d)
        self.assertNotIn("intent", d)
        self.assertNotIn("entities", d)

    def test_to_dict_full(self):
        turn = ConversationTurn(
            role="user",
            content="test",
            intent="waste_tool",
            entities={"waste_codes": ["15.01.01"]},
            tool_used="waste_tool",
            tool_action="search",
            tool_history=[{"tool": "waste_tool"}],
        )
        d = turn.to_dict()
        self.assertEqual(d["intent"], "waste_tool")
        self.assertEqual(d["entities"], {"waste_codes": ["15.01.01"]})
        self.assertEqual(d["tool_used"], "waste_tool")
        self.assertEqual(d["tool_action"], "search")
        self.assertEqual(len(d["tool_history"]), 1)

    def test_to_llm_dict(self):
        turn = ConversationTurn(role="user", content="Bonjour", intent="waste_tool")
        d = turn.to_llm_dict()
        self.assertEqual(d, {"role": "user", "content": "Bonjour"})
        self.assertNotIn("intent", d)
        self.assertNotIn("timestamp", d)

    def test_frozen(self):
        turn = ConversationTurn(role="user", content="test")
        with self.assertRaises(AttributeError):
            turn.content = "modified"


# ── ConversationSummary ──────────────────────────────────────────────


class TestConversationSummary(unittest.TestCase):
    """ConversationSummary dataclass."""

    def test_basic_creation(self):
        summary = ConversationSummary(
            summary_text="3 questions posées",
            turns_summarized=3,
        )
        self.assertEqual(summary.summary_text, "3 questions posées")
        self.assertEqual(summary.turns_summarized, 3)
        self.assertEqual(summary.entities_mentioned, [])
        self.assertEqual(summary.tools_used, [])
        self.assertEqual(summary.intents, [])
        self.assertIsInstance(summary.created_at, float)

    def test_full_creation(self):
        summary = ConversationSummary(
            summary_text="User asked about waste codes",
            turns_summarized=5,
            entities_mentioned=["15.01.01", "20.01.01"],
            tools_used=["waste_tool", "nomenclature_tool"],
            intents=["waste_tool", "nomenclature_tool"],
        )
        self.assertEqual(len(summary.entities_mentioned), 2)
        self.assertEqual(len(summary.tools_used), 2)
        self.assertEqual(len(summary.intents), 2)

    def test_to_dict(self):
        summary = ConversationSummary(
            summary_text="test",
            turns_summarized=2,
            entities_mentioned=["15.01.01"],
            tools_used=["waste_tool"],
            intents=["waste_tool"],
        )
        d = summary.to_dict()
        self.assertEqual(d["summary_text"], "test")
        self.assertEqual(d["turns_summarized"], 2)
        self.assertEqual(d["entities_mentioned"], ["15.01.01"])
        self.assertEqual(d["tools_used"], ["waste_tool"])
        self.assertEqual(d["intents"], ["waste_tool"])
        self.assertIn("created_at", d)

    def test_to_context_string(self):
        summary = ConversationSummary(
            summary_text="3 questions posées sur les déchets",
            turns_summarized=3,
            entities_mentioned=["15.01.01", "20.01.01"],
            tools_used=["waste_tool"],
            intents=["waste_tool"],
        )
        ctx = summary.to_context_string()
        self.assertIn("3 échange(s)", ctx)
        self.assertIn("3 questions posées", ctx)
        self.assertIn("15.01.01", ctx)
        self.assertIn("waste_tool", ctx)

    def test_to_context_string_no_entities(self):
        summary = ConversationSummary(
            summary_text="General questions",
            turns_summarized=2,
        )
        ctx = summary.to_context_string()
        self.assertIn("2 échange(s)", ctx)
        self.assertIn("General questions", ctx)

    def test_to_context_string_deduplicates_entities(self):
        summary = ConversationSummary(
            summary_text="test",
            turns_summarized=1,
            entities_mentioned=["15.01.01", "15.01.01", "20.01.01"],
        )
        ctx = summary.to_context_string()
        self.assertEqual(ctx.count("15.01.01"), 1)


# ── ConversationTracker ──────────────────────────────────────────────


class TestConversationTrackerBasic(unittest.TestCase):
    """Basic add/read operations."""

    def setUp(self):
        self.tracker = ConversationTracker(max_turns=10, auto_summarize=False)

    def test_add_user_turn(self):
        turn = self.tracker.add_user_turn("conv1", "Bonjour")
        self.assertEqual(turn.role, "user")
        self.assertEqual(turn.content, "Bonjour")

    def test_add_assistant_turn(self):
        turn = self.tracker.add_assistant_turn("conv1", "Bonjour !")
        self.assertEqual(turn.role, "assistant")

    def test_add_turn_with_metadata(self):
        turn = self.tracker.add_turn(
            "conv1", "user", "Quels sont les déchets ?",
            intent="waste_tool",
            entities={"waste_codes": ["15.01.01"]},
            tool_used="waste_tool",
            tool_action="search",
            tool_needed=True,
            hermes_confidence=0.9,
        )
        self.assertEqual(turn.intent, "waste_tool")
        self.assertEqual(turn.entities, {"waste_codes": ["15.01.01"]})
        self.assertEqual(turn.tool_used, "waste_tool")
        self.assertTrue(turn.tool_needed)

    def test_get_turns_empty(self):
        turns = self.tracker.get_turns("nonexistent")
        self.assertEqual(turns, [])

    def test_get_turns_returns_all(self):
        self.tracker.add_user_turn("conv1", "msg1")
        self.tracker.add_assistant_turn("conv1", "reply1")
        self.tracker.add_user_turn("conv1", "msg2")
        turns = self.tracker.get_turns("conv1")
        self.assertEqual(len(turns), 3)

    def test_get_turns_with_limit(self):
        for i in range(5):
            self.tracker.add_user_turn("conv1", f"msg{i}")
        turns = self.tracker.get_turns("conv1", limit=3)
        self.assertEqual(len(turns), 3)
        self.assertEqual(turns[0].content, "msg2")

    def test_exists(self):
        self.assertFalse(self.tracker.exists("conv1"))
        self.tracker.add_user_turn("conv1", "hi")
        self.assertTrue(self.tracker.exists("conv1"))

    def test_message_count(self):
        self.assertEqual(self.tracker.message_count("conv1"), 0)
        self.tracker.add_user_turn("conv1", "msg1")
        self.assertEqual(self.tracker.message_count("conv1"), 1)
        self.tracker.add_assistant_turn("conv1", "reply1")
        self.assertEqual(self.tracker.message_count("conv1"), 2)


class TestConversationTrackerSlidingWindow(unittest.TestCase):
    """Sliding window behaviour."""

    def test_evicts_oldest_when_full(self):
        tracker = ConversationTracker(max_turns=3, auto_summarize=False)
        for i in range(5):
            tracker.add_user_turn("conv1", f"msg{i}")
        turns = tracker.get_turns("conv1")
        self.assertEqual(len(turns), 3)
        self.assertEqual(turns[0].content, "msg2")
        self.assertEqual(turns[2].content, "msg4")

    def test_total_turns_increments(self):
        tracker = ConversationTracker(max_turns=3, auto_summarize=False)
        for i in range(5):
            tracker.add_user_turn("conv1", f"msg{i}")
        self.assertEqual(tracker.get_total_turns("conv1"), 5)

    def test_multiple_conversations_independent(self):
        tracker = ConversationTracker(max_turns=3, auto_summarize=False)
        tracker.add_user_turn("conv1", "a1")
        tracker.add_user_turn("conv2", "b1")
        tracker.add_user_turn("conv1", "a2")
        self.assertEqual(tracker.message_count("conv1"), 2)
        self.assertEqual(tracker.message_count("conv2"), 1)

    def test_separate_windows(self):
        tracker = ConversationTracker(max_turns=2, auto_summarize=False)
        for i in range(4):
            tracker.add_user_turn("conv1", f"conv1_msg{i}")
        for i in range(4):
            tracker.add_user_turn("conv2", f"conv2_msg{i}")
        turns1 = tracker.get_turns("conv1")
        turns2 = tracker.get_turns("conv2")
        self.assertEqual(len(turns1), 2)
        self.assertEqual(len(turns2), 2)
        self.assertEqual(turns1[0].content, "conv1_msg2")
        self.assertEqual(turns2[0].content, "conv2_msg2")


class TestConversationTrackerAutoSummarize(unittest.TestCase):
    """Auto-summarization when window is exceeded."""

    def test_summarize_when_exceeded(self):
        tracker = ConversationTracker(max_turns=3, auto_summarize=True)
        for i in range(5):
            tracker.add_user_turn("conv1", f"msg{i}")
        summary = tracker.get_summary("conv1")
        self.assertIsNotNone(summary)
        self.assertEqual(summary.turns_summarized, 3)
        self.assertIn("3", summary.summary_text)

    def test_no_summarize_when_disabled(self):
        tracker = ConversationTracker(max_turns=3, auto_summarize=False)
        for i in range(5):
            tracker.add_user_turn("conv1", f"msg{i}")
        summary = tracker.get_summary("conv1")
        self.assertIsNone(summary)

    def test_summarize_collects_intents(self):
        tracker = ConversationTracker(max_turns=3, auto_summarize=True)
        tracker.add_turn("conv1", "user", "msg1", intent="waste_tool")
        tracker.add_turn("conv1", "user", "msg2", intent="nomenclature_tool")
        tracker.add_turn("conv1", "user", "msg3", intent="waste_tool")
        # This triggers summarization of the first 3 turns
        tracker.add_turn("conv1", "user", "msg4", intent="bsd_tool")
        summary = tracker.get_summary("conv1")
        self.assertIn("waste_tool", summary.intents)
        self.assertIn("nomenclature_tool", summary.intents)

    def test_summarize_collects_entities(self):
        tracker = ConversationTracker(max_turns=2, auto_summarize=True)
        tracker.add_turn("conv1", "user", "msg1", entities={"waste_codes": ["15.01.01"]})
        tracker.add_turn("conv1", "user", "msg2", entities={"waste_codes": ["20.01.01"]})
        # Triggers summarization
        tracker.add_turn("conv1", "user", "msg3", entities={})
        summary = tracker.get_summary("conv1")
        self.assertIn("15.01.01", summary.entities_mentioned)
        self.assertIn("20.01.01", summary.entities_mentioned)

    def test_summarize_collects_tools(self):
        tracker = ConversationTracker(max_turns=2, auto_summarize=True)
        tracker.add_turn("conv1", "user", "msg1", tool_used="waste_tool")
        tracker.add_turn("conv1", "user", "msg2", tool_used="nomenclature_tool")
        # Triggers summarization
        tracker.add_turn("conv1", "user", "msg3", tool_used="bsd_tool")
        summary = tracker.get_summary("conv1")
        self.assertIn("waste_tool", summary.tools_used)
        self.assertIn("nomenclature_tool", summary.tools_used)


class TestConversationTrackerLLMMessages(unittest.TestCase):
    """LLM message assembly with summary prefix."""

    def test_no_summary_no_prefix(self):
        tracker = ConversationTracker(max_turns=10, auto_summarize=True)
        tracker.add_user_turn("conv1", "Bonjour")
        tracker.add_assistant_turn("conv1", "Bonjour !")
        msgs = tracker.get_llm_messages("conv1")
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

    def test_summary_prepended_as_system(self):
        tracker = ConversationTracker(max_turns=2, auto_summarize=True)
        tracker.add_turn("conv1", "user", "msg1", intent="waste_tool")
        tracker.add_turn("conv1", "user", "msg2", intent="nomenclature_tool")
        # Triggers summary
        tracker.add_turn("conv1", "assistant", "reply")
        msgs = tracker.get_llm_messages("conv1")
        self.assertGreaterEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("échange(s)", msgs[0]["content"])

    def test_summary_with_limit(self):
        tracker = ConversationTracker(max_turns=10, auto_summarize=False)
        for i in range(5):
            tracker.add_user_turn("conv1", f"msg{i}")
        msgs = tracker.get_llm_messages("conv1", limit=2)
        self.assertEqual(len(msgs), 2)

    def test_empty_conversation(self):
        tracker = ConversationTracker(max_turns=10)
        msgs = tracker.get_llm_messages("nonexistent")
        self.assertEqual(msgs, [])


class TestConversationTrackerToolHistory(unittest.TestCase):
    """Rolling tool history."""

    def test_tool_history_tracked(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1", tool_used="waste_tool", tool_action="search")
        tracker.add_user_turn("conv1", "msg2", tool_used="nomenclature_tool", tool_action="list")
        history = tracker.get_tool_history("conv1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["tool"], "waste_tool")
        self.assertEqual(history[1]["tool"], "nomenclature_tool")

    def test_tool_history_in_turns(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1", tool_used="waste_tool", tool_action="search")
        tracker.add_user_turn("conv1", "msg2", tool_used="nomenclature_tool", tool_action="list")
        turns = tracker.get_turns("conv1")
        # Second turn should have first tool in history
        self.assertEqual(len(turns[1].tool_history), 1)
        self.assertEqual(turns[1].tool_history[0]["tool"], "waste_tool")

    def test_tool_history_capped_at_20(self):
        tracker = ConversationTracker(max_turns=100)
        for i in range(25):
            tracker.add_user_turn("conv1", f"msg{i}", tool_used=f"tool_{i}", tool_action="act")
        history = tracker.get_tool_history("conv1")
        self.assertEqual(len(history), 20)

    def test_no_tool_not_tracked(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1")
        history = tracker.get_tool_history("conv1")
        self.assertEqual(len(history), 0)


class TestConversationTrackerEntitiesIntents(unittest.TestCase):
    """Entity and intent collection."""

    def test_get_entities_collected(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1", entities={"waste_codes": ["15.01.01"]})
        tracker.add_user_turn("conv1", "msg2", entities={"bsd_numbers": ["BSD-123"]})
        entities = tracker.get_entities_collected("conv1")
        self.assertIn("15.01.01", entities)
        self.assertIn("BSD-123", entities)

    def test_get_entities_deduplication(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1", entities={"waste_codes": ["15.01.01"]})
        tracker.add_user_turn("conv1", "msg2", entities={"waste_codes": ["15.01.01", "20.01.01"]})
        entities = tracker.get_entities_collected("conv1")
        self.assertEqual(entities.count("15.01.01"), 1)

    def test_get_intents_collected(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1", intent="waste_tool")
        tracker.add_user_turn("conv1", "msg2", intent="nomenclature_tool")
        tracker.add_user_turn("conv1", "msg3", intent="waste_tool")
        intents = tracker.get_intents_collected("conv1")
        self.assertEqual(intents, ["waste_tool", "nomenclature_tool"])

    def test_get_tools_collected(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1", tool_used="waste_tool")
        tracker.add_user_turn("conv1", "msg2", tool_used="bsd_tool")
        tools = tracker.get_tools_collected("conv1")
        self.assertEqual(tools, ["waste_tool", "bsd_tool"])


class TestConversationTrackerClearDelete(unittest.TestCase):
    """Clear and delete operations."""

    def test_clear_conversation(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1")
        tracker.add_user_turn("conv1", "msg2")
        count = tracker.clear_conversation("conv1")
        self.assertEqual(count, 2)
        self.assertFalse(tracker.exists("conv1"))
        self.assertIsNone(tracker.get_summary("conv1"))

    def test_clear_nonexistent(self):
        tracker = ConversationTracker(max_turns=10)
        count = tracker.clear_conversation("nonexistent")
        self.assertEqual(count, 0)

    def test_delete_conversation(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1")
        self.assertTrue(tracker.delete_conversation("conv1"))
        self.assertFalse(tracker.exists("conv1"))

    def test_delete_nonexistent(self):
        tracker = ConversationTracker(max_turns=10)
        self.assertFalse(tracker.delete_conversation("nonexistent"))

    def test_clear_all(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1")
        tracker.add_user_turn("conv2", "msg2")
        total = tracker.clear_all()
        self.assertEqual(total, 2)
        self.assertEqual(tracker.conversation_count(), 0)


class TestConversationTrackerStats(unittest.TestCase):
    """Stats and properties."""

    def test_stats_empty(self):
        tracker = ConversationTracker(max_turns=10)
        s = tracker.stats()
        self.assertEqual(s["conversations"], 0)
        self.assertEqual(s["total_turns_in_window"], 0)
        self.assertEqual(s["total_turns_all_time"], 0)
        self.assertEqual(s["summaries"], 0)
        self.assertEqual(s["max_turns_per_conversation"], 10)

    def test_stats_populated(self):
        tracker = ConversationTracker(max_turns=5)
        tracker.add_user_turn("conv1", "msg1")
        tracker.add_user_turn("conv1", "msg2")
        tracker.add_user_turn("conv2", "msg3")
        s = tracker.stats()
        self.assertEqual(s["conversations"], 2)
        self.assertEqual(s["total_turns_in_window"], 3)
        self.assertEqual(s["total_turns_all_time"], 3)

    def test_total_conversations_property(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1")
        tracker.add_user_turn("conv2", "msg2")
        self.assertEqual(tracker.total_conversations, 2)

    def test_total_messages_property(self):
        tracker = ConversationTracker(max_turns=10)
        tracker.add_user_turn("conv1", "msg1")
        tracker.add_user_turn("conv1", "msg2")
        self.assertEqual(tracker.total_messages, 2)

    def test_should_summarize(self):
        tracker = ConversationTracker(max_turns=3)
        self.assertFalse(tracker.should_summarize("conv1"))
        tracker.add_user_turn("conv1", "msg1")
        tracker.add_user_turn("conv1", "msg2")
        self.assertFalse(tracker.should_summarize("conv1"))
        tracker.add_user_turn("conv1", "msg3")
        self.assertTrue(tracker.should_summarize("conv1"))


class TestConversationTrackerLRUEviction(unittest.TestCase):
    """LRU eviction of oldest conversations."""

    def test_evicts_oldest_conversation(self):
        tracker = ConversationTracker(max_turns=10, max_conversations=3)
        for i in range(5):
            tracker.add_user_turn(f"conv{i}", f"msg{i}")
        self.assertEqual(tracker.conversation_count(), 3)
        self.assertFalse(tracker.exists("conv0"))
        self.assertFalse(tracker.exists("conv1"))
        self.assertTrue(tracker.exists("conv2"))

    def test_access_refreshes_lru(self):
        tracker = ConversationTracker(max_turns=10, max_conversations=3)
        tracker.add_user_turn("conv0", "msg0")
        tracker.add_user_turn("conv1", "msg1")
        tracker.add_user_turn("conv2", "msg2")
        # Access conv0 to refresh it
        tracker.get_turns("conv0")
        # Add a new conversation — should evict conv1 (oldest untouched)
        tracker.add_user_turn("conv3", "msg3")
        self.assertTrue(tracker.exists("conv0"))
        self.assertFalse(tracker.exists("conv1"))


class TestConversationTrackerThreadSafety(unittest.TestCase):
    """Thread safety under concurrent access."""

    def test_concurrent_adds(self):
        tracker = ConversationTracker(max_turns=50, max_conversations=50)
        errors: list = []

        def writer(conv_id: str, count: int):
            try:
                for i in range(count):
                    tracker.add_user_turn(conv_id, f"msg{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"conv{i}", 20))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(tracker.conversation_count(), 10)

    def test_concurrent_read_write(self):
        tracker = ConversationTracker(max_turns=20)
        for i in range(10):
            tracker.add_user_turn("conv1", f"msg{i}")
        errors: list = []

        def reader():
            try:
                for _ in range(50):
                    tracker.get_turns("conv1")
                    tracker.get_llm_messages("conv1")
                    tracker.get_summary("conv1")
                    tracker.stats()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    tracker.add_user_turn("conv1", f"new_msg{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


# ── MemoryManager Integration ────────────────────────────────────────


class TestMemoryManagerTrackerIntegration(unittest.TestCase):
    """Integration: MemoryManager → ConversationTracker."""

    def setUp(self):
        from apps.ai_assistant.core.config import MemoryConfig
        from apps.ai_assistant.core.memory import MemoryManager
        config = MemoryConfig(
            short_term_max_messages=20,
            conversation_max_turns=5,
            auto_summarize=True,
        )
        self.manager = MemoryManager(config)

    def test_tracker_property(self):
        from apps.ai_assistant.memory.conversation_tracker import ConversationTracker
        self.assertIsInstance(self.manager.tracker, ConversationTracker)

    def test_store_turn(self):
        turn = self.manager.store_turn(
            "conv1", "user", "Bonjour",
            intent="greeting",
            entities={},
        )
        self.assertEqual(turn.role, "user")
        self.assertEqual(turn.intent, "greeting")

    def test_get_tracked_turns(self):
        self.manager.store_turn("conv1", "user", "msg1", intent="waste_tool")
        self.manager.store_turn("conv1", "assistant", "reply1")
        turns = self.manager.get_tracked_turns("conv1")
        self.assertEqual(len(turns), 2)

    def test_get_tracker_summary(self):
        for i in range(6):
            self.manager.store_turn("conv1", "user", f"msg{i}", intent="waste_tool")
        summary = self.manager.get_tracker_summary("conv1")
        self.assertIsNotNone(summary)
        self.assertIn("waste_tool", summary.intents)

    def test_get_tool_history(self):
        self.manager.store_turn("conv1", "user", "msg1", tool_used="waste_tool")
        self.manager.store_turn("conv1", "user", "msg2", tool_used="bsd_tool")
        history = self.manager.get_tool_history("conv1")
        self.assertEqual(len(history), 2)

    def test_should_auto_summarize(self):
        self.assertFalse(self.manager.should_auto_summarize("conv1"))
        for i in range(5):
            self.manager.store_turn("conv1", "user", f"msg{i}")
        self.assertTrue(self.manager.should_auto_summarize("conv1"))

    def test_get_tracker_llm_messages_with_summary(self):
        for i in range(6):
            self.manager.store_turn("conv1", "user", f"msg{i}", intent="waste_tool")
        msgs = self.manager.get_tracker_llm_messages("conv1")
        self.assertGreaterEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("échange(s)", msgs[0]["content"])

    def test_clear_conversation_clears_tracker(self):
        self.manager.store_turn("conv1", "user", "msg1")
        self.manager.store_turn("conv1", "assistant", "reply1")
        self.manager.clear_conversation("conv1")
        turns = self.manager.get_tracked_turns("conv1")
        self.assertEqual(len(turns), 0)
        self.assertIsNone(self.manager.get_tracker_summary("conv1"))

    def test_clear_all_clears_tracker(self):
        self.manager.store_turn("conv1", "user", "msg1")
        self.manager.store_turn("conv2", "user", "msg2")
        result = self.manager.clear_all()
        self.assertEqual(result["tracker"], 2)


if __name__ == "__main__":
    unittest.main()
