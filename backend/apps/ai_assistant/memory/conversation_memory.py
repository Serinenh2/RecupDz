"""
Conversation Memory — multi-turn chat history with metadata.

Stores per-conversation message threads with:
    - Role-based messages (user / assistant / system / tool)
    - Attached metadata per message
    - Automatic eviction (sliding window)
    - Full-text keyword search across history
    - Export for LLM prompt assembly
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChatMessage:
    """Immutable chat message."""
    role: str          # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    def to_llm_dict(self) -> Dict[str, Any]:
        """Minimal dict for LLM prompt assembly (no metadata)."""
        return {"role": self.role, "content": self.content}


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------

@dataclass
class Conversation:
    """A single conversation thread."""
    conversation_id: str
    messages: deque = field(default_factory=deque)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    title: str = ""

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def last_message(self) -> Optional[ChatMessage]:
        if self.messages:
            return self.messages[-1]
        return None

    def get_messages(self, limit: Optional[int] = None) -> List[ChatMessage]:
        if limit:
            return list(self.messages)[-limit:]
        return list(self.messages)

    def get_llm_messages(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Export for LLM prompt assembly."""
        return [m.to_llm_dict() for m in self.get_messages(limit)]


# ---------------------------------------------------------------------------
# Conversation Memory
# ---------------------------------------------------------------------------

class ConversationMemory:
    """
    In-memory store for multi-turn conversation histories.

    Thread-safe. No database access.
    """

    def __init__(self, max_messages_per_conversation: int = 50, max_conversations: int = 100) -> None:
        self._max_messages = max_messages_per_conversation
        self._max_conversations = max_conversations
        self._conversations: OrderedDict[str, Conversation] = OrderedDict()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatMessage:
        msg = ChatMessage(role=role, content=content, metadata=metadata or {})
        with self._lock:
            conv = self._get_or_create(conversation_id)
            conv.messages.append(msg)
            conv.updated_at = time.time()
            # Evict oldest if over limit
            while len(conv.messages) > self._max_messages:
                conv.messages.popleft()
            # Evict oldest conversation if over limit
            while len(self._conversations) > self._max_conversations:
                self._conversations.popitem(last=False)
        return msg

    def add_user_message(self, conversation_id: str, content: str, **extra: Any) -> ChatMessage:
        return self.add_message(conversation_id, "user", content, metadata=extra or None)

    def add_assistant_message(self, conversation_id: str, content: str, **extra: Any) -> ChatMessage:
        return self.add_message(conversation_id, "assistant", content, metadata=extra or None)

    def add_system_message(self, conversation_id: str, content: str, **extra: Any) -> ChatMessage:
        return self.add_message(conversation_id, "system", content, metadata=extra or None)

    def add_tool_message(self, conversation_id: str, content: str, **extra: Any) -> ChatMessage:
        return self.add_message(conversation_id, "tool", content, metadata=extra or None)

    def set_title(self, conversation_id: str, title: str) -> None:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                conv.title = title

    def set_metadata(self, conversation_id: str, key: str, value: Any) -> None:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                conv.metadata[key] = value

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv is None:
                return []
            return conv.get_messages(limit)

    def get_llm_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv is None:
                return []
            return conv.get_llm_messages(limit)

    def get_last_message(self, conversation_id: str) -> Optional[ChatMessage]:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            return conv.last_message if conv else None

    def get_user_messages(self, conversation_id: str) -> List[ChatMessage]:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv is None:
                return []
            return [m for m in conv.messages if m.role == "user"]

    def get_assistant_messages(self, conversation_id: str) -> List[ChatMessage]:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv is None:
                return []
            return [m for m in conv.messages if m.role == "assistant"]

    def get_metadata(self, conversation_id: str, key: str, default: Any = None) -> Any:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv is None:
                return default
            return conv.metadata.get(key, default)

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        with self._lock:
            return self._conversations.get(conversation_id)

    def list_conversations(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "conversation_id": c.conversation_id,
                    "title": c.title,
                    "message_count": c.message_count,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    "metadata": c.metadata,
                }
                for c in reversed(self._conversations.values())
            ]

    def message_count(self, conversation_id: str) -> int:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            return conv.message_count if conv else 0

    def exists(self, conversation_id: str) -> bool:
        with self._lock:
            return conversation_id in self._conversations

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        conversation_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[ChatMessage]:
        """Keyword search across messages."""
        query_lower = query.lower()
        results: List[ChatMessage] = []

        with self._lock:
            convs = (
                [self._conversations[conversation_id]]
                if conversation_id and conversation_id in self._conversations
                else list(self._conversations.values())
            )

            for conv in convs:
                for msg in conv.messages:
                    if roles and msg.role not in roles:
                        continue
                    if query_lower in msg.content.lower():
                        results.append(msg)
                        if len(results) >= limit:
                            return results
        return results

    def search_by_metadata(self, key: str, value: Any, limit: int = 10) -> List[ChatMessage]:
        results: List[ChatMessage] = []
        with self._lock:
            for conv in self._conversations.values():
                for msg in conv.messages:
                    if msg.metadata.get(key) == value:
                        results.append(msg)
                        if len(results) >= limit:
                            return results
        return results

    # ------------------------------------------------------------------
    # Delete / Clear
    # ------------------------------------------------------------------

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            if conversation_id in self._conversations:
                del self._conversations[conversation_id]
                return True
            return False

    def clear_conversation(self, conversation_id: str) -> int:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv is None:
                return 0
            count = conv.message_count
            conv.messages.clear()
            return count

    def clear_all(self) -> int:
        with self._lock:
            total = sum(c.message_count for c in self._conversations.values())
            self._conversations.clear()
            return total

    def evict(self, max_age_seconds: float) -> int:
        """Remove conversations older than max_age_seconds."""
        cutoff = time.time() - max_age_seconds
        removed = 0
        with self._lock:
            to_remove = [cid for cid, c in self._conversations.items() if c.updated_at < cutoff]
            for cid in to_remove:
                del self._conversations[cid]
                removed += 1
        return removed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, conversation_id: str) -> Conversation:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(conversation_id=conversation_id)
        else:
            self._conversations.move_to_end(conversation_id)
        return self._conversations[conversation_id]

    @property
    def total_conversations(self) -> int:
        return len(self._conversations)

    @property
    def total_messages(self) -> int:
        with self._lock:
            return sum(c.message_count for c in self._conversations.values())
