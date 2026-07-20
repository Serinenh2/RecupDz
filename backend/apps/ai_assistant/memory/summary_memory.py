"""
Summary Memory — conversation summaries for long-term context.

Stores condensed summaries of past conversations, indexed by:
    - Conversation ID
    - User ID
    - Entity type/id
    - Time range

Used to give the LLM context about past interactions without
replaying the full message history.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@dataclass
class Summary:
    """A single conversation summary."""
    summary_id: str
    conversation_id: str
    user_id: str = ""
    title: str = ""
    content: str = ""
    key_entities: List[Dict[str, str]] = field(default_factory=list)   # [{"type": "recuperateur", "id": "42"}]
    key_decisions: List[str] = field(default_factory=list)
    message_count: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "title": self.title,
            "content": self.content,
            "key_entities": self.key_entities,
            "key_decisions": self.key_decisions,
            "message_count": self.message_count,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def to_context_string(self) -> str:
        """Format as a string suitable for LLM context injection."""
        parts = [f"Conversation: {self.title or self.conversation_id}"]
        parts.append(f"Résumé: {self.content}")
        if self.key_entities:
            ents = ", ".join(f"{e.get('type', '?')}/{e.get('id', '?')}" for e in self.key_entities)
            parts.append(f"Entités: {ents}")
        if self.key_decisions:
            parts.append("Décisions: " + "; ".join(self.key_decisions))
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# Summary Memory
# ---------------------------------------------------------------------------

class SummaryMemory:
    """
    In-memory store for conversation summaries.

    Features:
        - Indexed by conversation_id, user_id, entity
        - Time-range queries
        - LRU eviction
        - Export as LLM context
    """

    def __init__(self, max_summaries: int = 200) -> None:
        self._max = max_summaries
        self._summaries: OrderedDict[str, Summary] = OrderedDict()
        self._by_conversation: Dict[str, str] = {}   # conv_id → summary_id
        self._by_user: Dict[str, List[str]] = {}      # user_id → [summary_ids]
        self._by_entity: Dict[str, List[str]] = {}    # "type:id" → [summary_ids]
        self._counter = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(
        self,
        conversation_id: str,
        content: str,
        *,
        user_id: str = "",
        title: str = "",
        key_entities: Optional[List[Dict[str, str]]] = None,
        key_decisions: Optional[List[str]] = None,
        message_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Summary:
        with self._lock:
            self._counter += 1
            sid = f"summ_{self._counter}"

            summary = Summary(
                summary_id=sid,
                conversation_id=conversation_id,
                user_id=user_id,
                title=title,
                content=content,
                key_entities=key_entities or [],
                key_decisions=key_decisions or [],
                message_count=message_count,
                metadata=metadata or {},
            )

            # Evict if full
            while len(self._summaries) >= self._max:
                self._evict_oldest()

            self._summaries[sid] = summary

            # Index by conversation
            self._by_conversation[conversation_id] = sid

            # Index by user
            if user_id:
                self._by_user.setdefault(user_id, []).append(sid)

            # Index by entity
            for ent in (key_entities or []):
                key = f"{ent.get('type', '')}:{ent.get('id', '')}"
                self._by_entity.setdefault(key, []).append(sid)

            logger.debug("Summary saved: %s (conv=%s, user=%s)", sid, conversation_id, user_id)
            return summary

    def update(
        self,
        summary_id: str,
        *,
        content: Optional[str] = None,
        title: Optional[str] = None,
        key_entities: Optional[List[Dict[str, str]]] = None,
        key_decisions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Summary]:
        with self._lock:
            summary = self._summaries.get(summary_id)
            if summary is None:
                return None
            if content is not None:
                summary.content = content
            if title is not None:
                summary.title = title
            if key_entities is not None:
                summary.key_entities = key_entities
            if key_decisions is not None:
                summary.key_decisions = key_decisions
            if metadata:
                summary.metadata.update(metadata)
            return summary

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, summary_id: str) -> Optional[Summary]:
        with self._lock:
            return self._summaries.get(summary_id)

    def get_by_conversation(self, conversation_id: str) -> Optional[Summary]:
        with self._lock:
            sid = self._by_conversation.get(conversation_id)
            if sid:
                return self._summaries.get(sid)
            return None

    def get_by_user(self, user_id: str, limit: int = 10) -> List[Summary]:
        with self._lock:
            sids = self._by_user.get(user_id, [])
            results = [self._summaries[sid] for sid in sids if sid in self._summaries]
            return results[-limit:]

    def get_by_entity(self, entity_type: str, entity_id: str, limit: int = 10) -> List[Summary]:
        key = f"{entity_type}:{entity_id}"
        with self._lock:
            sids = self._by_entity.get(key, [])
            results = [self._summaries[sid] for sid in sids if sid in self._summaries]
            return results[-limit:]

    def get_recent(self, limit: int = 10) -> List[Summary]:
        with self._lock:
            return list(self._summaries.values())[-limit:]

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._summaries.values()]

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 10) -> List[Summary]:
        query_lower = query.lower()
        with self._lock:
            results = [
                s for s in self._summaries.values()
                if query_lower in s.content.lower()
                or query_lower in s.title.lower()
            ]
        return results[:limit]

    def search_by_entity_type(self, entity_type: str, limit: int = 10) -> List[Summary]:
        with self._lock:
            results = [
                s for s in self._summaries.values()
                if any(e.get("type") == entity_type for e in s.key_entities)
            ]
        return results[:limit]

    # ------------------------------------------------------------------
    # Context assembly
    # ------------------------------------------------------------------

    def get_context_string(
        self,
        *,
        user_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        max_summaries: int = 5,
    ) -> str:
        """
        Build a context string from relevant summaries.
        Designed for injection into LLM system prompts.
        """
        summaries: List[Summary] = []

        if user_id:
            summaries.extend(self.get_by_user(user_id, limit=max_summaries))
        if entity_type and entity_id:
            entity_summaries = self.get_by_entity(entity_type, entity_id, limit=max_summaries)
            existing_ids = {s.summary_id for s in summaries}
            for es in entity_summaries:
                if es.summary_id not in existing_ids:
                    summaries.append(es)

        if not summaries:
            summaries = self.get_recent(limit=max_summaries)

        if not summaries:
            return ""

        parts = ["CONVERSATIONS PASSÉES:"]
        for s in summaries:
            parts.append(f"- {s.to_context_string()}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Delete / Clear
    # ------------------------------------------------------------------

    def delete(self, summary_id: str) -> bool:
        with self._lock:
            summary = self._summaries.pop(summary_id, None)
            if summary is None:
                return False
            self._rebuild_indices()
            return True

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._summaries)
            self._summaries.clear()
            self._by_conversation.clear()
            self._by_user.clear()
            self._by_entity.clear()
            return count

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._summaries)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_oldest(self) -> None:
        if self._summaries:
            oldest_id, _ = self._summaries.popitem(last=False)
            self._rebuild_indices()

    def _rebuild_indices(self) -> None:
        self._by_conversation.clear()
        self._by_user.clear()
        self._by_entity.clear()
        for sid, s in self._summaries.items():
            self._by_conversation[s.conversation_id] = sid
            if s.user_id:
                self._by_user.setdefault(s.user_id, []).append(sid)
            for ent in s.key_entities:
                key = f"{ent.get('type', '')}:{ent.get('id', '')}"
                self._by_entity.setdefault(key, []).append(sid)
