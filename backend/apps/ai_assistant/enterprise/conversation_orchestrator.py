"""
Conversation Orchestrator — conversation lifecycle, memory, context, and persistence.

Responsibilities:
    1. Conversation lifecycle  — create, load, close, expire, delete
    2. Conversation history    — load/retrieve from EnterpriseConversationMemory
    3. Memory retrieval        — assemble context from session, user, conversation memory
    4. Memory summarization    — auto-compress when turn threshold is reached
    5. Context loading         — build full request context for downstream processing
    6. Context persistence     — persist turns, session state, user actions after processing
    7. Entry point             — every AI request goes through handle()

Architecture:
    ConversationOrchestrator sits ABOVE AgentOrchestrator.
    It owns conversation lifecycle and memory, then delegates the
    actual AI workflow (Hermes gate, tool selection, execution) to
    AgentOrchestrator.orchestrate().

    Gateway → ConversationOrchestrator → AgentOrchestrator → Hermes / Tools → Response

    ┌─────────────────────────────────────────────────┐
    │           ConversationOrchestrator               │
    │                                                  │
    │  Lifecycle: create / load / close / expire       │
    │  Memory:    conversation + session + user        │
    │  Context:   assemble full request context        │
    │  Persist:   store turns + session + user actions  │
    │  Delegate:  → AgentOrchestrator.orchestrate()    │
    └─────────────────────────────────────────────────┘

Constraints:
    - Zero Django imports
    - Zero repository access
    - All dependencies injected via constructor (DI)
    - Never re-raises exceptions — always returns safe fallback
    - French error messages throughout
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════

_DEFAULT_SUMMARY_THRESHOLD = 10
_DEFAULT_MAX_HISTORY_TURNS = 20


class ConversationContext:
    """Full context assembled for a single AI request.

    Aggregates conversation history, summaries, session state,
    and user profile into a single object for downstream processing.
    """

    __slots__ = (
        "conversation_id",
        "user_id",
        "history",
        "summaries",
        "session_state",
        "user_profile",
        "is_new_conversation",
        "metadata",
    )

    def __init__(
        self,
        *,
        conversation_id: str = "",
        user_id: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        summaries: Optional[List[str]] = None,
        session_state: Optional[Dict[str, Any]] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        is_new_conversation: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.history = history or []
        self.summaries = summaries or []
        self.session_state = session_state or {}
        self.user_profile = user_profile or {}
        self.is_new_conversation = is_new_conversation
        self.metadata = metadata or {}

    @property
    def has_history(self) -> bool:
        return len(self.history) > 0

    @property
    def has_summaries(self) -> bool:
        return len(self.summaries) > 0

    @property
    def turn_count(self) -> int:
        return len(self.history)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "history_length": len(self.history),
            "summary_count": len(self.summaries),
            "is_new_conversation": self.is_new_conversation,
            "has_session_state": bool(self.session_state),
            "has_user_profile": bool(self.user_profile),
        }


# ══════════════════════════════════════════════════════════════════════
# Main orchestrator
# ══════════════════════════════════════════════════════════════════════


class ConversationOrchestrator:
    """Entry point for every AI request.

    Manages conversation lifecycle, memory retrieval, context assembly,
    and post-processing persistence.  Delegates the actual AI workflow
    to AgentOrchestrator.

    Never exposes Python exceptions — all errors return safe fallback results.
    """

    def __init__(
        self,
        *,
        container: Any = None,
        summary_threshold: int = _DEFAULT_SUMMARY_THRESHOLD,
        max_history_turns: int = _DEFAULT_MAX_HISTORY_TURNS,
    ) -> None:
        self._container = container
        self._summary_threshold = summary_threshold
        self._max_history_turns = max_history_turns

    # ------------------------------------------------------------------
    # Lazy-resolved dependencies (DI via container)
    # ------------------------------------------------------------------

    @property
    def _conversation_memory(self) -> Any:
        if self._container is None:
            return None
        try:
            return self._container.conversation_memory
        except Exception:
            return None

    @property
    def _session_memory(self) -> Any:
        if self._container is None:
            return None
        try:
            return self._container.session_memory
        except Exception:
            return None

    @property
    def _user_memory(self) -> Any:
        if self._container is None:
            return None
        try:
            return self._container.user_memory
        except Exception:
            return None

    @property
    def _agent_orchestrator(self) -> Any:
        if self._container is None:
            return None
        try:
            return self._container.orchestrator
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Public API — Main entry point
    # ------------------------------------------------------------------

    def handle(
        self,
        message: str,
        user_id: str = "",
        conversation_id: str = "",
        contexte_supp: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a user message through the full conversation lifecycle.

        Steps:
            1. Create or retrieve conversation
            2. Load history + memory context
            3. Build ConversationContext
            4. Delegate to AgentOrchestrator.orchestrate()
            5. Persist turns + session state + user actions
            6. Auto-summarize if threshold reached
            7. Return response with conversation metadata

        Returns: {"success", "message", "data", "meta", "followups"}
        """
        request_id = uuid.uuid4().hex[:12]
        start = time.monotonic()
        is_new = False

        try:
            # ── Step 1: Conversation lifecycle ──────────────────────
            conversation_id, is_new = self._get_or_create_conversation(
                conversation_id, user_id,
            )

            # ── Step 2: Load history + memory ──────────────────────
            history = self._load_history(conversation_id)
            summaries = self._load_summaries(conversation_id)
            session_state = self._load_session(user_id, conversation_id)
            user_profile = self._load_user_profile(user_id)

            # ── Step 3: Build context ──────────────────────────────
            ctx = self._build_context(
                conversation_id=conversation_id,
                user_id=user_id,
                history=history,
                summaries=summaries,
                session_state=session_state,
                user_profile=user_profile,
                is_new=is_new,
            )

            # ── Step 4: Delegate to AgentOrchestrator ──────────────
            result = self._delegate(message, user_id, conversation_id, contexte_supp)

            # ── Step 5: Persist ────────────────────────────────────
            self._persist_turns(
                conversation_id, user_id, message, result,
            )
            self._persist_session(user_id, conversation_id, result)
            self._persist_user_action(user_id, conversation_id, message, result)

            # ── Step 6: Auto-summarize ─────────────────────────────
            self._auto_summarize(conversation_id)

            # ── Step 7: Format response ────────────────────────────
            return self._format_response(result, conversation_id, is_new)

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.exception("ConversationOrchestrator error: %s", exc)
            return {
                "success": False,
                "message": "Une erreur est survenue. Veuillez réessayer.",
                "data": {},
                "followups": [],
                "meta": {
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "error": str(exc),
                    "elapsed_ms": round(elapsed, 1),
                },
            }

    # ------------------------------------------------------------------
    # Public API — Conversation lifecycle
    # ------------------------------------------------------------------

    def create_conversation(
        self,
        user_id: str = "",
    ) -> str:
        """Create a new conversation and return its ID."""
        conversation_id = f"conv_{uuid.uuid4().hex[:8]}"
        logger.debug("Created conversation: %s (user=%s)", conversation_id, user_id)
        return conversation_id

    def conversation_exists(self, conversation_id: str) -> bool:
        """Check if a conversation has any stored data."""
        mem = self._conversation_memory
        if mem is None:
            return False
        try:
            return mem.exists(conversation_id)
        except Exception:
            return False

    def get_turn_count(self, conversation_id: str) -> int:
        """Return the total number of turns in a conversation."""
        mem = self._conversation_memory
        if mem is None:
            return 0
        try:
            return mem.total_turns(conversation_id)
        except Exception:
            return 0

    def list_conversations(self) -> List[str]:
        """Return all conversation IDs with stored data."""
        mem = self._conversation_memory
        if mem is None:
            return []
        try:
            return mem.list_conversations()
        except Exception:
            return []

    def close_conversation(self, conversation_id: str) -> None:
        """Mark a conversation as closed (clears session state)."""
        try:
            sm = self._session_memory
            if sm is not None:
                sm.delete(conversation_id)
            logger.debug("Closed conversation: %s", conversation_id)
        except Exception as exc:
            logger.debug("close_conversation failed: %s", exc)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its data."""
        deleted = False
        try:
            mem = self._conversation_memory
            if mem is not None:
                deleted = mem.delete(conversation_id)
        except Exception as exc:
            logger.debug("delete_conversation memory failed: %s", exc)
        try:
            sm = self._session_memory
            if sm is not None:
                sm.delete(conversation_id)
        except Exception as exc:
            logger.debug("delete_conversation session failed: %s", exc)
        return deleted

    def expire_conversations(self) -> int:
        """Expire old conversations based on TTL/LRU policies."""
        mem = self._conversation_memory
        if mem is None:
            return 0
        try:
            return mem.expire()
        except Exception:
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Return conversation memory statistics."""
        mem = self._conversation_memory
        if mem is None:
            return {"available": False}
        try:
            return {"available": True, **mem.stats()}
        except Exception:
            return {"available": False}

    # ------------------------------------------------------------------
    # Internal — Conversation lifecycle
    # ------------------------------------------------------------------

    def _get_or_create_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> Tuple[str, bool]:
        """Return (conversation_id, is_new)."""
        if conversation_id and self.conversation_exists(conversation_id):
            return conversation_id, False
        if not conversation_id:
            conversation_id = self.create_conversation(user_id)
        return conversation_id, True

    # ------------------------------------------------------------------
    # Internal — History loading
    # ------------------------------------------------------------------

    def _load_history(
        self,
        conversation_id: str,
    ) -> List[Dict[str, str]]:
        """Load conversation history as LLM-compatible message dicts.

        Returns [{"role": "user"|"assistant", "content": "..."}, ...].
        """
        mem = self._conversation_memory
        if mem is None:
            return []
        try:
            return mem.get_llm_messages(
                conversation_id, max_turns=self._max_history_turns,
            )
        except Exception as exc:
            logger.debug("_load_history failed: %s", exc)
            return []

    def _load_summaries(
        self,
        conversation_id: str,
    ) -> List[str]:
        """Load compressed summary context strings."""
        mem = self._conversation_memory
        if mem is None:
            return []
        try:
            snapshot = mem.retrieve(
                conversation_id, include_summaries=True,
            )
            if not snapshot or not snapshot.summaries:
                return []
            return [s.to_context_string() for s in snapshot.summaries]
        except Exception as exc:
            logger.debug("_load_summaries failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal — Memory retrieval
    # ------------------------------------------------------------------

    def _load_session(
        self,
        user_id: str,
        conversation_id: str,
    ) -> Dict[str, Any]:
        """Load ephemeral session state."""
        sm = self._session_memory
        if sm is None:
            return {}
        try:
            session = sm.get(conversation_id)
            if session is None:
                return {}
            return {
                "entity": sm.get_entity(conversation_id),
                "company": sm.get_company(conversation_id),
                "declaration": sm.get_declaration(conversation_id),
                "recent_actions": [
                    a.to_dict() for a in sm.get_recent_actions(conversation_id, limit=5)
                ],
                "mode": sm.get_mode(conversation_id),
            }
        except Exception as exc:
            logger.debug("_load_session failed: %s", exc)
            return {}

    def _load_user_profile(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Load user profile and preferences."""
        um = self._user_memory
        if um is None or not user_id:
            return {}
        try:
            profile = um.get_profile(user_id)
            prefs = um.get_preferences(user_id)
            return {
                "profile": profile.to_dict() if profile else {},
                "preferences": prefs.to_dict() if prefs else {},
                "frequent_entities": um.get_frequent_entities(user_id, limit=5),
            }
        except Exception as exc:
            logger.debug("_load_user_profile failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Internal — Context building
    # ------------------------------------------------------------------

    def _build_context(
        self,
        *,
        conversation_id: str,
        user_id: str,
        history: List[Dict[str, str]],
        summaries: List[str],
        session_state: Dict[str, Any],
        user_profile: Dict[str, Any],
        is_new: bool,
    ) -> ConversationContext:
        """Assemble the full ConversationContext for this request."""
        return ConversationContext(
            conversation_id=conversation_id,
            user_id=user_id,
            history=history,
            summaries=summaries,
            session_state=session_state,
            user_profile=user_profile,
            is_new_conversation=is_new,
            metadata={
                "history_turns": len(history),
                "summary_count": len(summaries),
                "has_session": bool(session_state),
                "has_profile": bool(user_profile),
            },
        )

    # ------------------------------------------------------------------
    # Internal — Delegation
    # ------------------------------------------------------------------

    def _delegate(
        self,
        message: str,
        user_id: str,
        conversation_id: str,
        contexte_supp: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Delegate to AgentOrchestrator.orchestrate().

        Returns the standard {"success", "message", "data", "meta", "followups"} dict.
        """
        orch = self._agent_orchestrator
        if orch is None:
            return {
                "success": False,
                "message": "Agent indisponible.",
                "data": {},
                "followups": [],
                "meta": {},
            }
        try:
            return orch.orchestrate(
                message=message,
                user_id=user_id,
                conversation_id=conversation_id,
                contexte_supp=contexte_supp,
            )
        except Exception as exc:
            logger.debug("_delegate failed: %s", exc)
            return {
                "success": False,
                "message": "Erreur du workflow agent.",
                "data": {},
                "followups": [],
                "meta": {"error": str(exc)},
            }

    # ------------------------------------------------------------------
    # Internal — Persistence
    # ------------------------------------------------------------------

    def _persist_turns(
        self,
        conversation_id: str,
        user_id: str,
        user_message: str,
        result: Dict[str, Any],
    ) -> None:
        """Store user and assistant turns in conversation memory."""
        mem = self._conversation_memory
        if mem is None:
            return
        try:
            from apps.ai_assistant.enterprise.conversation_memory import MemoryTurn

            meta = result.get("meta", {})
            user_turn = MemoryTurn(
                role="user",
                content=user_message,
                intent=meta.get("tool_used", ""),
                entities=meta.get("entities", {}),
            )
            mem.store(conversation_id, user_turn, user_id=user_id)

            assistant_turn = MemoryTurn(
                role="assistant",
                content=result.get("message", ""),
                intent=meta.get("tool_used", ""),
                tool_name=meta.get("tool_used", ""),
                tool_action=meta.get("tool_action", ""),
                tool_result_summary=str(result.get("data", ""))[:200],
            )
            mem.store(conversation_id, assistant_turn, user_id=user_id)
        except Exception as exc:
            logger.debug("_persist_turns failed: %s", exc)

    def _persist_session(
        self,
        user_id: str,
        conversation_id: str,
        result: Dict[str, Any],
    ) -> None:
        """Persist session state after processing."""
        sm = self._session_memory
        if sm is None:
            return
        try:
            sm.get_or_create(conversation_id, user_id)
            meta = result.get("meta", {})
            entities = meta.get("entities", {})
            if entities:
                entity_type = entities.get("type", "")
                entity_id = entities.get("id", "")
                if entity_type and entity_id:
                    sm.set_entity(
                        conversation_id, entity_type, entity_id, entities,
                    )
        except Exception as exc:
            logger.debug("_persist_session failed: %s", exc)

    def _persist_user_action(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        result: Dict[str, Any],
    ) -> None:
        """Record user action in user memory."""
        um = self._user_memory
        if um is None or not user_id:
            return
        try:
            meta = result.get("meta", {})
            entities = meta.get("entities", {})
            um.record_action(
                user_id=user_id,
                action_type=meta.get("tool_used", "chat"),
                description=user_message[:200],
                entity_type=entities.get("type", ""),
                entity_id=entities.get("id", ""),
                session_id=conversation_id,
            )
        except Exception as exc:
            logger.debug("_persist_user_action failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal — Auto-summarization
    # ------------------------------------------------------------------

    def _auto_summarize(self, conversation_id: str) -> None:
        """Compress old turns into summaries when threshold is reached."""
        mem = self._conversation_memory
        if mem is None:
            return
        try:
            count = mem.total_turns(conversation_id)
            if count >= self._summary_threshold:
                summary = mem.compress(
                    conversation_id,
                    keep_recent=self._max_history_turns,
                )
                if summary:
                    logger.debug(
                        "Auto-summarized %s: compressed %d turns",
                        conversation_id, summary.turns_compressed,
                    )
        except Exception as exc:
            logger.debug("_auto_summarize failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal — Response formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_response(
        result: Dict[str, Any],
        conversation_id: str,
        is_new: bool,
    ) -> Dict[str, Any]:
        """Add conversation metadata to the result."""
        meta = dict(result.get("meta", {}))
        meta["conversation_id"] = conversation_id
        if is_new:
            meta["new_conversation"] = True
        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "data": result.get("data", {}),
            "followups": result.get("followups", []),
            "meta": meta,
        }
