"""
Conversation Tracker — structured conversation memory with auto-summarization.

Maintains a sliding window of the last N conversation turns.  When the window
is exceeded, older turns are automatically summarized into a compact text
record that is prepended to the context sent to the LLM.

Stored per turn:
    - Message content + role
    - Intent (tool name or "none" / "greeting")
    - Extracted entities (waste codes, BSD numbers, etc.)
    - Tool used + action + result summary

Thread-safe. No database access. Pure in-memory.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data Contracts ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConversationTurn:
    """A single turn in the conversation — user message + assistant response + metadata."""

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)

    # Intent & routing
    intent: str = ""
    selection_source: str = ""

    # Entities extracted from the user message
    entities: Dict[str, Any] = field(default_factory=dict)

    # Tool execution details
    tool_used: Optional[str] = None
    tool_action: str = ""
    tool_needed: bool = False
    hermes_confidence: float = 0.0

    # Rolling tool history — list of tool calls in this conversation up to this turn
    tool_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.intent:
            d["intent"] = self.intent
        if self.entities:
            d["entities"] = self.entities
        if self.tool_used:
            d["tool_used"] = self.tool_used
        if self.tool_action:
            d["tool_action"] = self.tool_action
        if self.tool_history:
            d["tool_history"] = self.tool_history
        return d

    def to_llm_dict(self) -> Dict[str, Any]:
        """Minimal dict for LLM prompt assembly."""
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class ConversationSummary:
    """Auto-generated summary of older conversation turns."""

    summary_text: str
    turns_summarized: int
    entities_mentioned: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    intents: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_text": self.summary_text,
            "turns_summarized": self.turns_summarized,
            "entities_mentioned": self.entities_mentioned,
            "tools_used": self.tools_used,
            "intents": self.intents,
            "created_at": self.created_at,
        }

    def to_context_string(self) -> str:
        """Render summary as a context string for LLM injection."""
        parts = [f"Résumé de {self.turns_summarized} échange(s) précédent(s):"]
        parts.append(self.summary_text)
        if self.entities_mentioned:
            unique_entities = list(dict.fromkeys(self.entities_mentioned))
            parts.append(f"Entités mentionnées: {', '.join(unique_entities[:10])}")
        if self.tools_used:
            unique_tools = list(dict.fromkeys(self.tools_used))
            parts.append(f"Outils utilisés: {', '.join(unique_tools)}")
        return " | ".join(parts)


# ── Conversation Tracker ─────────────────────────────────────────────


class ConversationTracker:
    """
    Production conversation memory with sliding window + auto-summarization.

    Behaviour:
        - Stores the last ``max_turns`` ConversationTurns per conversation.
        - When the window is exceeded, the oldest turns are summarized into a
          deterministic ``ConversationSummary`` (no LLM call).
        - The summary is available via ``get_summary()`` and can be injected
          into the LLM context by the orchestrator.

    Thread-safe. No database access.
    """

    def __init__(
        self,
        max_turns: int = 10,
        auto_summarize: bool = True,
        max_conversations: int = 200,
    ) -> None:
        self._max_turns = max_turns
        self._auto_summarize = auto_summarize
        self._max_conversations = max_conversations

        # conversation_id → deque of ConversationTurn (OrderedDict for LRU)
        self._turns: OrderedDict[str, deque[ConversationTurn]] = OrderedDict()
        # conversation_id → ConversationSummary (latest)
        self._summaries: Dict[str, ConversationSummary] = {}
        # conversation_id → total turns ever stored (including summarized)
        self._total_turns: Dict[str, int] = {}
        # conversation_id → list of all tool calls (rolling history)
        self._tool_histories: Dict[str, List[Dict[str, Any]]] = {}

        self._lock = threading.Lock()

    # ==================================================================
    # Write
    # ==================================================================

    def add_turn(
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
        Add a turn to the conversation.  Returns the created turn.

        If the sliding window is full and ``auto_summarize`` is enabled,
        the oldest turn is summarized before being evicted.
        """
        turn = ConversationTurn(
            role=role,
            content=content,
            intent=intent,
            selection_source=selection_source,
            entities=entities or {},
            tool_used=tool_used,
            tool_action=tool_action,
            tool_needed=tool_needed,
            hermes_confidence=hermes_confidence,
            tool_history=list(self._tool_histories.get(conversation_id, [])),
        )

        with self._lock:
            if conversation_id not in self._turns:
                self._turns[conversation_id] = deque(maxlen=self._max_turns)
                self._total_turns[conversation_id] = 0
                self._tool_histories[conversation_id] = []

            # Track tool calls in rolling history
            if tool_used:
                self._tool_histories[conversation_id].append({
                    "tool": tool_used,
                    "action": tool_action,
                    "intent": intent,
                    "timestamp": turn.timestamp,
                })
                # Keep last 20 tool calls
                if len(self._tool_histories[conversation_id]) > 20:
                    self._tool_histories[conversation_id] = \
                        self._tool_histories[conversation_id][-20:]

            buf = self._turns[conversation_id]

            # Auto-summarize before eviction
            if (
                self._auto_summarize
                and len(buf) == self._max_turns
                and buf.maxlen is not None
                and buf.maxlen > 0
            ):
                turns_to_summarize = list(buf)
                self._summarize_turns(conversation_id, turns_to_summarize)

            # Add new turn (deque evicts oldest automatically)
            buf.append(turn)
            self._total_turns[conversation_id] += 1

            # Move to end for LRU
            self._turns.move_to_end(conversation_id)

            # Evict oldest conversations if over capacity
            while len(self._turns) > self._max_conversations:
                oldest_cid = next(iter(self._turns))
                self._evict_conversation(oldest_cid)

            logger.debug(
                "Tracker[%s]: added %s turn (%d total, %d in window)",
                conversation_id, role, self._total_turns[conversation_id], len(buf),
            )

        return turn

    def add_user_turn(
        self,
        conversation_id: str,
        content: str,
        **kwargs: Any,
    ) -> ConversationTurn:
        return self.add_turn(conversation_id, "user", content, **kwargs)

    def add_assistant_turn(
        self,
        conversation_id: str,
        content: str,
        **kwargs: Any,
    ) -> ConversationTurn:
        return self.add_turn(conversation_id, "assistant", content, **kwargs)

    # ==================================================================
    # Read
    # ==================================================================

    def get_turns(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[ConversationTurn]:
        """Get turns from the sliding window."""
        with self._lock:
            buf = self._turns.get(conversation_id)
            if buf is None:
                return []
            self._touch(conversation_id)
            if limit:
                return list(buf)[-limit:]
            return list(buf)

    def get_llm_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get turns as LLM-ready dicts, with optional summary prefix."""
        turns = self.get_turns(conversation_id, limit)
        messages: List[Dict[str, Any]] = []

        # Prepend summary if available
        summary = self.get_summary(conversation_id)
        if summary:
            messages.append({
                "role": "system",
                "content": summary.to_context_string(),
            })

        for turn in turns:
            messages.append(turn.to_llm_dict())

        return messages

    def get_summary(self, conversation_id: str) -> Optional[ConversationSummary]:
        with self._lock:
            return self._summaries.get(conversation_id)

    def get_total_turns(self, conversation_id: str) -> int:
        with self._lock:
            return self._total_turns.get(conversation_id, 0)

    def get_tool_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            self._touch(conversation_id)
            return list(self._tool_histories.get(conversation_id, []))

    def should_summarize(self, conversation_id: str) -> bool:
        """Check if the conversation has exceeded the window and needs summarization."""
        with self._lock:
            buf = self._turns.get(conversation_id)
            if buf is None:
                return False
            return len(buf) >= self._max_turns

    def get_entities_collected(self, conversation_id: str) -> List[str]:
        """Get all unique entities mentioned across all turns."""
        with self._lock:
            entities: List[str] = []
            buf = self._turns.get(conversation_id, deque())
            for turn in buf:
                for entity_list in turn.entities.values():
                    if isinstance(entity_list, list):
                        entities.extend(str(e) for e in entity_list)
            return list(dict.fromkeys(entities))

    def get_intents_collected(self, conversation_id: str) -> List[str]:
        """Get all unique intents across all turns."""
        with self._lock:
            intents: List[str] = []
            buf = self._turns.get(conversation_id, deque())
            for turn in buf:
                if turn.intent and turn.intent not in intents:
                    intents.append(turn.intent)
            return intents

    def get_tools_collected(self, conversation_id: str) -> List[str]:
        """Get all unique tools used across all turns."""
        with self._lock:
            tools: List[str] = []
            buf = self._turns.get(conversation_id, deque())
            for turn in buf:
                if turn.tool_used and turn.tool_used not in tools:
                    tools.append(turn.tool_used)
            return tools

    # ==================================================================
    # Delete / Clear
    # ==================================================================

    def clear_conversation(self, conversation_id: str) -> int:
        """Clear all data for a conversation. Returns number of turns removed."""
        with self._lock:
            count = len(self._turns.get(conversation_id, deque()))
            self._turns.pop(conversation_id, None)
            self._summaries.pop(conversation_id, None)
            self._total_turns.pop(conversation_id, None)
            self._tool_histories.pop(conversation_id, None)
            return count

    def clear_all(self) -> int:
        """Clear all conversations. Returns total turns removed."""
        with self._lock:
            total = sum(len(b) for b in self._turns.values())
            self._turns.clear()
            self._summaries.clear()
            self._total_turns.clear()
            self._tool_histories.clear()
            return total

    def delete_conversation(self, conversation_id: str) -> bool:
        return self.clear_conversation(conversation_id) > 0

    # ==================================================================
    # Query / Stats
    # ==================================================================

    def exists(self, conversation_id: str) -> bool:
        with self._lock:
            return conversation_id in self._turns

    def conversation_count(self) -> int:
        with self._lock:
            return len(self._turns)

    def message_count(self, conversation_id: str) -> int:
        with self._lock:
            return len(self._turns.get(conversation_id, deque()))

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "conversations": len(self._turns),
                "total_turns_in_window": sum(len(b) for b in self._turns.values()),
                "total_turns_all_time": sum(self._total_turns.values()),
                "summaries": len(self._summaries),
                "max_turns_per_conversation": self._max_turns,
            }

    # ==================================================================
    # Helpers
    # ==================================================================

    def _touch(self, conversation_id: str) -> None:
        """Refresh LRU position for a conversation (must be called under lock)."""
        if conversation_id in self._turns:
            self._turns.move_to_end(conversation_id)

    def _summarize_turns(
        self,
        conversation_id: str,
        turns: List[ConversationTurn],
    ) -> None:
        """
        Create a deterministic summary from turns being evicted.

        No LLM call — purely template-based.  This keeps the summarization
        fast and predictable.  LLM-based summarization can be layered on top
        by overriding this method.
        """
        if not turns:
            return

        entities: List[str] = []
        tools: List[str] = []
        intents: List[str] = []
        user_questions: List[str] = []

        for turn in turns:
            # Collect entities
            for entity_list in turn.entities.values():
                if isinstance(entity_list, list):
                    entities.extend(str(e) for e in entity_list)

            # Collect tools
            if turn.tool_used and turn.tool_used not in tools:
                tools.append(turn.tool_used)

            # Collect intents
            if turn.intent and turn.intent not in intents:
                intents.append(turn.intent)

            # Collect user questions (truncated)
            if turn.role == "user":
                user_questions.append(turn.content[:80])

        # Build summary text
        parts: List[str] = []

        if user_questions:
            q_count = len(user_questions)
            parts.append(
                f"{q_count} question(s) posée(s) par l'utilisateur"
            )

        if intents:
            intent_str = ", ".join(intents[:5])
            parts.append(f"Intentions: {intent_str}")

        if tools:
            tool_str = ", ".join(tools[:5])
            parts.append(f"Outils utilisés: {tool_str}")

        if entities:
            unique_entities = list(dict.fromkeys(entities))
            parts.append(
                f"Entités: {', '.join(unique_entities[:10])}"
            )

        summary_text = ". ".join(parts) if parts else "Conversation sans intention métier détectée."

        summary = ConversationSummary(
            summary_text=summary_text,
            turns_summarized=len(turns),
            entities_mentioned=entities,
            tools_used=tools,
            intents=intents,
        )

        self._summaries[conversation_id] = summary
        logger.info(
            "Tracker[%s]: summarized %d turns → '%s'",
            conversation_id, len(turns), summary_text[:80],
        )

    def _evict_conversation(self, conversation_id: str) -> None:
        """Remove a conversation entirely (LRU eviction)."""
        self._turns.pop(conversation_id, None)
        self._summaries.pop(conversation_id, None)
        self._total_turns.pop(conversation_id, None)
        self._tool_histories.pop(conversation_id, None)

    @property
    def total_conversations(self) -> int:
        return self.conversation_count()

    @property
    def total_messages(self) -> int:
        with self._lock:
            return sum(len(b) for b in self._turns.values())
