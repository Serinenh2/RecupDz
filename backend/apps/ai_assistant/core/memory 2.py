"""
Conversation memory — short-term buffer + long-term store + structured tracker.

Short-term: in-memory sliding window of recent messages.
Long-term: pluggable MemoryStore backed by Django ORM or vector DB.
Tracker: structured per-turn memory with intent, entities, tool history + auto-summarization.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.config import MemoryConfig
from apps.ai_assistant.core.interfaces import (
    MemoryEntry,
    MemoryStore,
    MemoryType,
    Message,
    Role,
)
from apps.ai_assistant.memory.conversation_tracker import (
    ConversationSummary,
    ConversationTracker,
    ConversationTurn,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Short-Term Memory (In-Memory Sliding Window)
# ---------------------------------------------------------------------------

class ShortTermMemory:
    """Per-conversation sliding window of recent messages."""

    def __init__(self, max_messages: int = 20) -> None:
        self._max = max_messages
        self._buffers: Dict[str, deque[Message]] = {}

    def add(self, conversation_id: str, message: Message) -> None:
        if conversation_id not in self._buffers:
            self._buffers[conversation_id] = deque(maxlen=self._max)
        self._buffers[conversation_id].append(message)
        logger.debug(
            "ShortTerm[%s]: added %s message (%d total)",
            conversation_id, message.role.value, len(self._buffers[conversation_id]),
        )

    def get_history(self, conversation_id: str, limit: Optional[int] = None) -> List[Message]:
        buf = self._buffers.get(conversation_id, deque())
        if limit:
            return list(buf)[-limit:]
        return list(buf)

    def get_context_window(self, conversation_id: str, window_size: int = 10) -> List[Message]:
        buf = self._buffers.get(conversation_id, deque())
        return list(buf)[-window_size:]

    def clear(self, conversation_id: str) -> int:
        if conversation_id in self._buffers:
            count = len(self._buffers[conversation_id])
            del self._buffers[conversation_id]
            return count
        return 0

    def clear_all(self) -> int:
        count = sum(len(b) for b in self._buffers.values())
        self._buffers.clear()
        return count

    @property
    def active_conversations(self) -> List[str]:
        return list(self._buffers.keys())

    def message_count(self, conversation_id: str) -> int:
        return len(self._buffers.get(conversation_id, deque()))


# ---------------------------------------------------------------------------
# Long-Term Memory (Pluggable Store)
# ---------------------------------------------------------------------------

class LongTermMemory:
    """Semantic long-term memory backed by a MemoryStore implementation."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def remember(self, key: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry = MemoryEntry(
            key=key,
            content=content,
            memory_type=MemoryType.LONG_TERM,
            metadata=metadata or {},
        )
        self._store.save(entry)
        logger.debug("LongTerm: stored key='%s'", key)

    def recall(
        self,
        query: str,
        *,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> List[MemoryEntry]:
        return self._store.retrieve(query, memory_type=MemoryType.LONG_TERM, limit=limit, min_score=min_score)

    def forget(self, key: str) -> bool:
        return self._store.delete(key)

    def purge(self) -> int:
        return self._store.clear(memory_type=MemoryType.LONG_TERM)


# ---------------------------------------------------------------------------
# Memory Manager (Composite)
# ---------------------------------------------------------------------------

class MemoryManager:
    """Unified interface over short-term, long-term, and structured conversation memory."""

    def __init__(self, config: MemoryConfig, long_term_store: Optional[MemoryStore] = None) -> None:
        self._config = config
        self._short_term = ShortTermMemory(max_messages=config.short_term_max_messages)
        self._long_term: Optional[LongTermMemory] = (
            LongTermMemory(long_term_store) if long_term_store and config.enable_long_term else None
        )
        self._tracker = ConversationTracker(
            max_turns=config.conversation_max_turns,
            auto_summarize=config.auto_summarize,
        )
        logger.info(
            "MemoryManager initialized: short_term_max=%d, tracker_max_turns=%d, auto_summarize=%s, long_term=%s",
            config.short_term_max_messages,
            config.conversation_max_turns,
            config.auto_summarize,
            "enabled" if self._long_term else "disabled",
        )

    @property
    def short_term(self) -> ShortTermMemory:
        return self._short_term

    @property
    def long_term(self) -> Optional[LongTermMemory]:
        return self._long_term

    @property
    def tracker(self) -> ConversationTracker:
        return self._tracker

    # ── Short-term message storage ────────────────────────────────────

    def store_user_message(self, conversation_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        msg = Message(role=Role.USER, content=content, metadata=metadata or {})
        self._short_term.add(conversation_id, msg)

    def store_assistant_message(self, conversation_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        msg = Message(role=Role.ASSISTANT, content=content, metadata=metadata or {})
        self._short_term.add(conversation_id, msg)

    def get_conversation_history(self, conversation_id: str, limit: Optional[int] = None) -> List[Message]:
        return self._short_term.get_history(conversation_id, limit)

    def get_context_messages(self, conversation_id: str) -> List[Message]:
        return self._short_term.get_context_window(
            conversation_id,
            window_size=self._config.context_window_messages,
        )

    # ── Structured turn storage (ConversationTracker) ─────────────────

    def store_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        intent: str = "",
        selection_source: str = "",
        entities: Optional[Dict[str, Any]] = None,
        tool_used: Optional[str] = None,
        tool_action: str = "",
        tool_needed: bool = False,
        hermes_confidence: float = 0.0,
    ) -> ConversationTurn:
        """
        Store a structured conversation turn with full metadata.

        This is the primary write method for the new conversation memory.
        It stores to the ConversationTracker which maintains the sliding
        window and auto-summarization.
        """
        return self._tracker.add_turn(
            conversation_id,
            role,
            content,
            intent=intent,
            selection_source=selection_source,
            entities=entities,
            tool_used=tool_used,
            tool_action=tool_action,
            tool_needed=tool_needed,
            hermes_confidence=hermes_confidence,
        )

    def get_tracked_turns(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[ConversationTurn]:
        """Get structured turns from the tracker."""
        return self._tracker.get_turns(conversation_id, limit)

    def get_tracker_summary(self, conversation_id: str) -> Optional[ConversationSummary]:
        """Get the auto-generated conversation summary if it exists."""
        return self._tracker.get_summary(conversation_id)

    def get_tracker_llm_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get LLM-ready messages from the tracker.

        If a summary exists, it is prepended as a system message.
        """
        return self._tracker.get_llm_messages(conversation_id, limit)

    def get_tool_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get the rolling tool call history for a conversation."""
        return self._tracker.get_tool_history(conversation_id)

    def should_auto_summarize(self, conversation_id: str) -> bool:
        """Check if the tracker should auto-summarize."""
        return self._tracker.should_summarize(conversation_id)

    # ── Summary management ────────────────────────────────────────────

    def should_summarize(self, conversation_id: str) -> bool:
        return self._short_term.message_count(conversation_id) >= self._config.summary_threshold

    # ── Long-term memory ─────────────────────────────────────────────

    def store_long_term(self, key: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if self._long_term:
            self._long_term.remember(key, content, metadata)

    def recall_long_term(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        if self._long_term:
            return self._long_term.recall(query, limit=limit)
        return []

    # ── Clear / Reset ─────────────────────────────────────────────────

    def clear_conversation(self, conversation_id: str) -> int:
        short_count = self._short_term.clear(conversation_id)
        self._tracker.clear_conversation(conversation_id)
        return short_count

    def clear_all(self) -> Dict[str, int]:
        short_count = self._short_term.clear_all()
        long_count = self._long_term.purge() if self._long_term else 0
        tracker_count = self._tracker.clear_all()
        return {"short_term": short_count, "long_term": long_count, "tracker": tracker_count}
