"""
Enterprise Conversation Memory — unified, production-grade conversation store.

Responsibilities:
    - Store conversation history with per-turn metadata (intents,
      entities, references, tools, results).
    - Automatic summarization of evicted turns (deterministic,
      template-based — no LLM call).
    - Sliding context window with configurable max turns.
    - Context compression: merge old turns into compact summaries.
    - Memory retrieval: query by conversation, user, entity, time range.
    - Memory expiration policies: TTL, LRU, turn-count, manual.

Architecture:
    EnterpriseConversationMemory is a thread-safe, in-memory store.
    Each conversation is identified by a conversation_id and holds an
    ordered list of MemoryTurn objects.  When the sliding window is
    exceeded, oldest turns are compressed into MemorySummary objects.

    ┌──────────────────────────────────────────────────┐
    │           EnterpriseConversationMemory            │
    │                                                  │
    │  conversation_id ──► [MemoryTurn, ..., MemoryTurn]│
    │                     + [MemorySummary, ...]        │
    │                     + MemoryMetadata              │
    └──────────────────────────────────────────────────┘

Design rules:
    - Zero Django imports.
    - Zero repository access.
    - Zero business logic — only storage, retrieval, and compression.
    - Thread-safe via threading.Lock.
    - All dataclasses have to_dict() for serialisation.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

_DEFAULT_MAX_TURNS: int = 20
_DEFAULT_MAX_CONVERSATIONS: int = 100
_DEFAULT_SUMMARY_THRESHOLD: int = 5
_DEFAULT_TTL_SECONDS: float = 3600.0  # 1 hour
_MAX_TURNS_IN_SUMMARY: int = 10


# ══════════════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════════════


class ExpirationPolicy(str, Enum):
    """Strategies for evicting old conversations from memory."""

    TTL = "ttl"
    LRU = "lru"
    TURN_COUNT = "turn_count"
    MANUAL = "manual"


# ══════════════════════════════════════════════════════════════════════
# Data Contracts
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class MemoryTurn:
    """
    A single conversation turn with full metadata.

    Captures everything about one user/assistant exchange:
    message content, detected intent, extracted entities,
    tool execution details, and references.
    """

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)

    # Intent & routing
    intent: str = ""
    confidence: float = 0.0

    # Entities extracted from the user message
    entities: Dict[str, Any] = field(default_factory=dict)

    # References (BSD numbers, waste codes, etc.)
    references: List[str] = field(default_factory=list)

    # Tool execution details
    tool_name: str = ""
    tool_action: str = ""
    tool_result_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.intent:
            d["intent"] = self.intent
        if self.confidence:
            d["confidence"] = round(self.confidence, 3)
        if self.entities:
            d["entities"] = self.entities
        if self.references:
            d["references"] = self.references
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.tool_action:
            d["tool_action"] = self.tool_action
        if self.tool_result_summary:
            d["tool_result_summary"] = self.tool_result_summary
        return d

    def to_llm_dict(self) -> Dict[str, Any]:
        """Minimal dict for LLM prompt assembly."""
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class MemorySummary:
    """
    A compressed summary of older turns.

    Created when turns are evicted from the sliding window.
    Deterministic, template-based — no LLM call.
    """

    summary_text: str
    turns_compressed: int = 0
    first_timestamp: float = 0.0
    last_timestamp: float = 0.0
    intents: List[str] = field(default_factory=list)
    entities_mentioned: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    user_questions: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "summary_text": self.summary_text,
            "turns_compressed": self.turns_compressed,
            "created_at": self.created_at,
        }
        if self.first_timestamp:
            d["first_timestamp"] = self.first_timestamp
        if self.last_timestamp:
            d["last_timestamp"] = self.last_timestamp
        if self.intents:
            d["intents"] = self.intents
        if self.entities_mentioned:
            d["entities_mentioned"] = self.entities_mentioned
        if self.tools_used:
            d["tools_used"] = self.tools_used
        if self.user_questions:
            d["user_questions"] = self.user_questions
        return d

    def to_context_string(self) -> str:
        """Render as a human-readable block for LLM system prompt injection."""
        parts: List[str] = []
        if self.turns_compressed:
            parts.append(
                f"{self.turns_compressed} ancien(s) tour(s) résumé(s)"
            )
        if self.user_questions:
            q_count = len(self.user_questions)
            parts.append(
                f"{q_count} question(s) posée(s) par l'utilisateur"
            )
        if self.intents:
            parts.append(f"Intentions: {', '.join(self.intents[:5])}")
        if self.tools_used:
            parts.append(f"Outils utilisés: {', '.join(self.tools_used[:5])}")
        if self.entities_mentioned:
            unique = list(dict.fromkeys(self.entities_mentioned))
            parts.append(f"Entités: {', '.join(unique[:10])}")
        return ". ".join(parts) if parts else "Résumé de conversation."


@dataclass(frozen=True)
class MemorySnapshot:
    """
    Result of a memory retrieval query.

    Contains the requested turns, any applicable summaries,
    and statistics about the retrieval.
    """

    turns: List[MemoryTurn] = field(default_factory=list)
    summaries: List[MemorySummary] = field(default_factory=list)
    total_turns: int = 0
    total_summaries: int = 0
    compressed_turns: int = 0

    @property
    def has_data(self) -> bool:
        return bool(self.turns or self.summaries)

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def summary_count(self) -> int:
        return len(self.summaries)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "turns": [t.to_dict() for t in self.turns],
            "summaries": [s.to_dict() for s in self.summaries],
            "total_turns": self.total_turns,
            "total_summaries": self.total_summaries,
            "compressed_turns": self.compressed_turns,
            "turn_count": self.turn_count,
            "summary_count": self.summary_count,
        }
        return d

    def to_context_string(self) -> str:
        """Render as a block suitable for LLM system prompt injection."""
        parts: List[str] = []
        for summary in self.summaries:
            ctx = summary.to_context_string()
            if ctx:
                parts.append(f"[Résumé] {ctx}")
        for turn in self.turns:
            role_label = "Utilisateur" if turn.role == "user" else "Assistant"
            content = turn.content[:200]
            parts.append(f"{role_label}: {content}")
        return "\n".join(parts)


@dataclass
class MemoryMetadata:
    """Metadata for a single conversation stored in memory."""

    conversation_id: str
    user_id: str = ""
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    turn_count: int = 0
    summary_count: int = 0
    compressed_turns: int = 0
    intents: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "turn_count": self.turn_count,
            "summary_count": self.summary_count,
            "compressed_turns": self.compressed_turns,
        }
        if self.intents:
            d["intents"] = self.intents
        if self.entities:
            d["entities"] = self.entities
        if self.tools_used:
            d["tools_used"] = self.tools_used
        return d


# ══════════════════════════════════════════════════════════════════════
# Enterprise Conversation Memory
# ══════════════════════════════════════════════════════════════════════


class EnterpriseConversationMemory:
    """
    Unified, production-grade conversation memory.

    Thread-safe, in-memory store with sliding window, auto-summarization,
    context compression, retrieval, and expiration policies.

    Usage:
        mem = EnterpriseConversationMemory(max_turns=20)
        mem.store("conv_1", MemoryTurn(role="user", content="Bonjour"))
        mem.store("conv_1", MemoryTurn(role="assistant", content="Bonjour!"))
        snapshot = mem.retrieve("conv_1")
        ctx = snapshot.to_context_string()
    """

    def __init__(
        self,
        *,
        max_turns: int = _DEFAULT_MAX_TURNS,
        max_conversations: int = _DEFAULT_MAX_CONVERSATIONS,
        summary_threshold: int = _DEFAULT_SUMMARY_THRESHOLD,
        expiration_policy: ExpirationPolicy = ExpirationPolicy.LRU,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
        auto_summarize: bool = True,
        compression_ratio: float = 0.5,
    ) -> None:
        self._max_turns = max_turns
        self._max_conversations = max_conversations
        self._summary_threshold = summary_threshold
        self._expiration_policy = expiration_policy
        self._ttl_seconds = ttl_seconds
        self._auto_summarize = auto_summarize
        self._compression_ratio = compression_ratio

        # Storage: conversation_id → deque of MemoryTurn
        self._turns: OrderedDict[str, deque] = OrderedDict()
        # Summaries: conversation_id → list of MemorySummary
        self._summaries: Dict[str, List[MemorySummary]] = {}
        # Metadata: conversation_id → MemoryMetadata
        self._metadata: Dict[str, MemoryMetadata] = {}

        self._lock = threading.Lock()

    # ════════════════════════════════════════════════════════════════
    # Public API — Store
    # ════════════════════════════════════════════════════════════════

    def store(
        self,
        conversation_id: str,
        turn: MemoryTurn,
        *,
        user_id: str = "",
    ) -> None:
        """
        Store a conversation turn.

        Appends the turn to the sliding window.  When the window is
        exceeded and auto_summarize is enabled, oldest turns are
        compressed into a MemorySummary.

        Args:
            conversation_id: Unique conversation identifier.
            turn: The turn to store.
            user_id: Optional user identifier for cross-user queries.
        """
        with self._lock:
            self._ensure_conversation(conversation_id, user_id)
            turns = self._turns[conversation_id]
            turns.append(turn)

            # Update metadata
            meta = self._metadata[conversation_id]
            meta.last_active = time.time()
            meta.turn_count += 1
            if turn.intent and turn.intent not in meta.intents:
                meta.intents.append(turn.intent)
            for entity_val in turn.entities.values():
                if isinstance(entity_val, str) and entity_val not in meta.entities:
                    meta.entities.append(entity_val)
                elif isinstance(entity_val, list):
                    for ev in entity_val:
                        s_ev = str(ev)
                        if s_ev not in meta.entities:
                            meta.entities.append(s_ev)
            if turn.tool_name and turn.tool_name not in meta.tools_used:
                meta.tools_used.append(turn.tool_name)

            # Auto-summarize if window exceeded
            if self._auto_summarize and len(turns) > self._max_turns:
                self._compress_turns(conversation_id)

            # Enforce conversation count limit
            self._enforce_conversation_limit()

            logger.debug(
                "Memory[%s]: stored turn (total=%d)",
                conversation_id, meta.turn_count,
            )

    # ════════════════════════════════════════════════════════════════
    # Public API — Retrieve
    # ════════════════════════════════════════════════════════════════

    def retrieve(
        self,
        conversation_id: str,
        *,
        max_turns: Optional[int] = None,
        include_summaries: bool = True,
    ) -> MemorySnapshot:
        """
        Retrieve turns and summaries for a conversation.

        Args:
            conversation_id: Conversation to retrieve.
            max_turns: Override max turns to return (default: all in window).
            include_summaries: Whether to include compressed summaries.

        Returns:
            MemorySnapshot with turns and summaries.
        """
        with self._lock:
            turns = list(self._turns.get(conversation_id, []))
            summaries = list(self._summaries.get(conversation_id, []))
            meta = self._metadata.get(conversation_id)

            if max_turns is not None and max_turns > 0:
                turns = turns[-max_turns:]

            compressed = meta.compressed_turns if meta else 0
            total = meta.turn_count if meta else 0

            return MemorySnapshot(
                turns=turns,
                summaries=summaries if include_summaries else [],
                total_turns=total,
                total_summaries=len(summaries),
                compressed_turns=compressed,
            )

    def retrieve_by_user(
        self,
        user_id: str,
        *,
        max_conversations: int = 10,
    ) -> List[MemorySnapshot]:
        """
        Retrieve snapshots for all conversations belonging to a user.

        Args:
            user_id: User to search for.
            max_conversations: Max conversations to return.

        Returns:
            List of MemorySnapshot, most recent first.
        """
        with self._lock:
            results: List[MemorySnapshot] = []
            for conv_id, meta in reversed(self._metadata.items()):
                if meta.user_id != user_id:
                    continue
                snap = self._retrieve_unlocked(conv_id)
                results.append(snap)
                if len(results) >= max_conversations:
                    break
            return results

    def retrieve_by_entity(
        self,
        entity_value: str,
        *,
        max_conversations: int = 10,
    ) -> List[MemorySnapshot]:
        """
        Retrieve snapshots for conversations mentioning a specific entity.

        Args:
            entity_value: Entity value to search for.
            max_conversations: Max conversations to return.

        Returns:
            List of MemorySnapshot, most recent first.
        """
        with self._lock:
            results: List[MemorySnapshot] = []
            for conv_id, meta in reversed(self._metadata.items()):
                if entity_value not in meta.entities:
                    continue
                snap = self._retrieve_unlocked(conv_id)
                results.append(snap)
                if len(results) >= max_conversations:
                    break
            return results

    def retrieve_recent(
        self,
        *,
        max_conversations: int = 5,
        max_turns_per: int = 10,
    ) -> List[MemorySnapshot]:
        """
        Retrieve the most recent conversations.

        Args:
            max_conversations: Max conversations to return.
            max_turns_per: Max turns per conversation.

        Returns:
            List of MemorySnapshot, most recent first.
        """
        with self._lock:
            results: List[MemorySnapshot] = []
            for conv_id in reversed(list(self._turns.keys())):
                snap = self._retrieve_unlocked(conv_id, max_turns=max_turns_per)
                results.append(snap)
                if len(results) >= max_conversations:
                    break
            return results

    # ════════════════════════════════════════════════════════════════
    # Public API — Context
    # ════════════════════════════════════════════════════════════════

    def get_context_string(
        self,
        conversation_id: str,
        *,
        max_turns: int = 10,
    ) -> str:
        """
        Get a context string for LLM system prompt injection.

        Combines summaries and recent turns into a single string
        suitable for injection into a prompt.

        Args:
            conversation_id: Conversation to render.
            max_turns: Max recent turns to include.

        Returns:
            Formatted context string.
        """
        snapshot = self.retrieve(
            conversation_id, max_turns=max_turns,
        )
        return snapshot.to_context_string()

    def get_llm_messages(
        self,
        conversation_id: str,
        *,
        max_turns: int = 10,
    ) -> List[Dict[str, str]]:
        """
        Get conversation as a list of LLM-compatible message dicts.

        Summaries are prepended as system messages, followed by
        the most recent turns.

        Args:
            conversation_id: Conversation to render.
            max_turns: Max recent turns to include.

        Returns:
            List of {"role": ..., "content": ...} dicts.
        """
        with self._lock:
            messages: List[Dict[str, str]] = []

            # Prepend summaries as system messages
            summaries = self._summaries.get(conversation_id, [])
            for summary in summaries:
                ctx = summary.to_context_string()
                if ctx:
                    messages.append({"role": "system", "content": ctx})

            # Append recent turns
            turns = list(self._turns.get(conversation_id, []))
            if max_turns > 0:
                turns = turns[-max_turns:]
            for turn in turns:
                messages.append(turn.to_llm_dict())

            return messages

    # ════════════════════════════════════════════════════════════════
    # Public API — Compression
    # ════════════════════════════════════════════════════════════════

    def compress(
        self,
        conversation_id: str,
        *,
        keep_recent: int = 5,
    ) -> Optional[MemorySummary]:
        """
        Manually compress older turns into a summary.

        Args:
            conversation_id: Conversation to compress.
            keep_recent: Number of recent turns to keep uncompressed.

        Returns:
            The created MemorySummary, or None if nothing to compress.
        """
        with self._lock:
            if conversation_id not in self._turns:
                return None
            return self._compress_to(conversation_id, keep_recent)

    # ════════════════════════════════════════════════════════════════
    # Public API — Expiration
    # ════════════════════════════════════════════════════════════════

    def expire(self) -> int:
        """
        Expire conversations based on the configured policy.

        Returns:
            Number of conversations expired.
        """
        with self._lock:
            if self._expiration_policy == ExpirationPolicy.TTL:
                return self._expire_by_ttl()
            elif self._expiration_policy == ExpirationPolicy.LRU:
                return self._expire_by_lru()
            elif self._expiration_policy == ExpirationPolicy.TURN_COUNT:
                return self._expire_by_turn_count()
            return 0

    def delete(self, conversation_id: str) -> bool:
        """
        Manually delete a conversation from memory.

        Args:
            conversation_id: Conversation to delete.

        Returns:
            True if the conversation existed and was deleted.
        """
        with self._lock:
            existed = conversation_id in self._turns
            self._turns.pop(conversation_id, None)
            self._summaries.pop(conversation_id, None)
            self._metadata.pop(conversation_id, None)
            if existed:
                logger.info("Memory[%s]: manually deleted", conversation_id)
            return existed

    # ════════════════════════════════════════════════════════════════
    # Public API — Query
    # ════════════════════════════════════════════════════════════════

    def exists(self, conversation_id: str) -> bool:
        """Check if a conversation exists in memory."""
        with self._lock:
            return conversation_id in self._turns

    def get_metadata(
        self,
        conversation_id: str,
    ) -> Optional[MemoryMetadata]:
        """Get metadata for a conversation."""
        with self._lock:
            meta = self._metadata.get(conversation_id)
            return meta

    def conversation_count(self) -> int:
        """Return the number of active conversations."""
        with self._lock:
            return len(self._turns)

    def total_turns(self) -> int:
        """Return the total number of turns across all conversations."""
        with self._lock:
            return sum(
                meta.turn_count for meta in self._metadata.values()
            )

    def total_summaries(self) -> int:
        """Return the total number of summaries across all conversations."""
        with self._lock:
            return sum(
                len(s) for s in self._summaries.values()
            )

    def list_conversations(self) -> List[str]:
        """Return all active conversation IDs, most recent first."""
        with self._lock:
            return list(reversed(list(self._turns.keys())))

    def stats(self) -> Dict[str, Any]:
        """Return memory statistics."""
        with self._lock:
            total_t = sum(m.turn_count for m in self._metadata.values())
            total_s = sum(len(s) for s in self._summaries.values())
            return {
                "conversations": len(self._turns),
                "total_turns": total_t,
                "total_summaries": total_s,
                "max_turns": self._max_turns,
                "max_conversations": self._max_conversations,
                "summary_threshold": self._summary_threshold,
                "expiration_policy": self._expiration_policy.value,
                "auto_summarize": self._auto_summarize,
            }

    # ════════════════════════════════════════════════════════════════
    # Internal — Compression
    # ════════════════════════════════════════════════════════════════

    def _compress_turns(self, conversation_id: str) -> None:
        """
        Compress oldest turns when sliding window is exceeded.

        Keeps the most recent turns.  Evicted turns are compressed
        into a MemorySummary.  Must be called under lock.
        """
        turns = self._turns.get(conversation_id)
        if not turns or len(turns) <= self._max_turns:
            return

        excess = len(turns) - self._max_turns
        keep = self._max_turns
        compress_count = min(excess, self._summary_threshold)

        self._compress_to(conversation_id, keep_recent=keep)

    def _compress_to(
        self,
        conversation_id: str,
        keep_recent: int,
    ) -> Optional[MemorySummary]:
        """
        Compress turns older than keep_recent into a summary.

        Must be called under lock.  Returns the created summary.
        """
        turns = self._turns.get(conversation_id)
        if not turns or len(turns) <= keep_recent:
            return None

        # Split: turns to compress vs turns to keep
        to_compress: List[MemoryTurn] = []
        while len(turns) > keep_recent:
            to_compress.append(turns.popleft())

        if not to_compress:
            return None

        summary = self._build_summary(to_compress)

        # Store summary
        if conversation_id not in self._summaries:
            self._summaries[conversation_id] = []
        self._summaries[conversation_id].append(summary)

        # Update metadata
        meta = self._metadata.get(conversation_id)
        if meta:
            meta.summary_count = len(self._summaries[conversation_id])
            meta.compressed_turns += len(to_compress)

        logger.info(
            "Memory[%s]: compressed %d turns → '%s'",
            conversation_id,
            len(to_compress),
            summary.summary_text[:80],
        )
        return summary

    def _build_summary(self, turns: List[MemoryTurn]) -> MemorySummary:
        """
        Build a deterministic summary from a list of turns.

        No LLM call — purely template-based.  Fast and predictable.
        """
        if not turns:
            return MemorySummary(summary_text="Résumé vide.")

        entities: List[str] = []
        tools: List[str] = []
        intents: List[str] = []
        questions: List[str] = []

        first_ts = turns[0].timestamp
        last_ts = turns[-1].timestamp

        for turn in turns:
            # Collect entities
            for entity_val in turn.entities.values():
                if isinstance(entity_val, str):
                    entities.append(entity_val)
                elif isinstance(entity_val, list):
                    entities.extend(str(e) for e in entity_val)

            # Collect tools
            if turn.tool_name and turn.tool_name not in tools:
                tools.append(turn.tool_name)

            # Collect intents
            if turn.intent and turn.intent not in intents:
                intents.append(turn.intent)

            # Collect user questions (truncated)
            if turn.role == "user":
                questions.append(turn.content[:80])

        # Build summary text
        parts: List[str] = []

        if questions:
            parts.append(
                f"{len(questions)} question(s) posée(s) par l'utilisateur"
            )
        if intents:
            parts.append(f"Intentions: {', '.join(intents[:5])}")
        if tools:
            parts.append(f"Outils utilisés: {', '.join(tools[:5])}")
        if entities:
            unique = list(dict.fromkeys(entities))
            parts.append(f"Entités: {', '.join(unique[:10])}")

        summary_text = (
            ". ".join(parts)
            if parts
            else "Conversation sans intention métier détectée."
        )

        return MemorySummary(
            summary_text=summary_text,
            turns_compressed=len(turns),
            first_timestamp=first_ts,
            last_timestamp=last_ts,
            intents=intents,
            entities_mentioned=entities,
            tools_used=tools,
            user_questions=questions,
        )

    # ════════════════════════════════════════════════════════════════
    # Internal — Expiration
    # ════════════════════════════════════════════════════════════════

    def _expire_by_ttl(self) -> int:
        """Expire conversations older than TTL.  Must be called under lock."""
        now = time.time()
        expired = 0
        to_remove: List[str] = []
        for conv_id, meta in self._metadata.items():
            if now - meta.last_active > self._ttl_seconds:
                to_remove.append(conv_id)
        for conv_id in to_remove:
            self._remove_conversation(conv_id)
            expired += 1
        return expired

    def _expire_by_lru(self) -> int:
        """Expire oldest conversations when over limit.  Must be called under lock."""
        expired = 0
        while len(self._turns) > self._max_conversations:
            # OrderedDict: first item is oldest (least recently used)
            oldest_id = next(iter(self._turns))
            self._remove_conversation(oldest_id)
            expired += 1
        return expired

    def _expire_by_turn_count(self) -> int:
        """Expire conversations that have exceeded max turns.  Must be called under lock."""
        expired = 0
        to_remove: List[str] = []
        for conv_id, meta in self._metadata.items():
            if meta.turn_count > self._max_turns * 3:
                to_remove.append(conv_id)
        for conv_id in to_remove:
            self._remove_conversation(conv_id)
            expired += 1
        return expired

    # ════════════════════════════════════════════════════════════════
    # Internal — Helpers
    # ════════════════════════════════════════════════════════════════

    def _ensure_conversation(
        self,
        conversation_id: str,
        user_id: str = "",
    ) -> None:
        """Create a conversation entry if it doesn't exist.  Must be called under lock."""
        if conversation_id not in self._turns:
            self._turns[conversation_id] = deque()
            self._summaries[conversation_id] = []
            self._metadata[conversation_id] = MemoryMetadata(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            # Touch LRU
            self._turns.move_to_end(conversation_id)
        else:
            # Touch LRU
            self._turns.move_to_end(conversation_id)

    def _remove_conversation(self, conversation_id: str) -> None:
        """Remove a conversation entirely.  Must be called under lock."""
        self._turns.pop(conversation_id, None)
        self._summaries.pop(conversation_id, None)
        self._metadata.pop(conversation_id, None)

    def _enforce_conversation_limit(self) -> None:
        """Enforce max_conversations limit via LRU.  Must be called under lock."""
        while len(self._turns) > self._max_conversations:
            oldest_id = next(iter(self._turns))
            self._remove_conversation(oldest_id)
            logger.debug("Memory: LRU evicted '%s'", oldest_id)

    def _retrieve_unlocked(
        self,
        conversation_id: str,
        max_turns: Optional[int] = None,
    ) -> MemorySnapshot:
        """Retrieve without acquiring lock.  Must be called under lock."""
        turns = list(self._turns.get(conversation_id, []))
        summaries = list(self._summaries.get(conversation_id, []))
        meta = self._metadata.get(conversation_id)

        if max_turns is not None and max_turns > 0:
            turns = turns[-max_turns:]

        compressed = meta.compressed_turns if meta else 0
        total = meta.turn_count if meta else 0

        return MemorySnapshot(
            turns=turns,
            summaries=summaries,
            total_turns=total,
            total_summaries=len(summaries),
            compressed_turns=compressed,
        )
