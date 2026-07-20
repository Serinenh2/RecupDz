"""
Session Memory — ephemeral state for the current interaction.

Tracks the live context of a single user session:
    - Current entity being discussed
    - Current company / organisation
    - Current declaration / operation
    - Recent actions taken
    - Active flags / mode
"""

from __future__ import annotations

import logging
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Action Record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionRecord:
    """A single action taken during the session."""
    action_type: str       # e.g. "search", "create_bsd", "view_declaration"
    description: str
    entity_type: str = ""
    entity_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "description": self.description,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    """Mutable state for a single session."""
    session_id: str
    user_id: str = ""

    # current entity context
    current_entity_type: str = ""
    current_entity_id: str = ""
    current_entity_data: Dict[str, Any] = field(default_factory=dict)

    # current company
    current_company_id: str = ""
    current_company_name: str = ""
    current_company_data: Dict[str, Any] = field(default_factory=dict)

    # current declaration
    current_declaration_id: str = ""
    current_declaration_data: Dict[str, Any] = field(default_factory=dict)

    # recent actions ring buffer
    recent_actions: Deque = field(default_factory=lambda: deque(maxlen=20))

    # flags / mode
    flags: Dict[str, Any] = field(default_factory=dict)
    mode: str = ""  # e.g. "normal", "guided", "wizard"

    # timestamps
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()


# ---------------------------------------------------------------------------
# Session Memory
# ---------------------------------------------------------------------------

class SessionMemory:
    """
    Manages ephemeral session state — the "what are we doing right now" memory.

    One SessionState per session_id. Auto-expires stale sessions.
    No database access.
    """

    def __init__(self, max_sessions: int = 50, session_ttl_seconds: float = 3600.0) -> None:
        self._max_sessions = max_sessions
        self._ttl = session_ttl_seconds
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def get_or_create(self, session_id: str, user_id: str = "") -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                self._evict_expired()
                if len(self._sessions) >= self._max_sessions:
                    self._evict_oldest()
                self._sessions[session_id] = SessionState(session_id=session_id, user_id=user_id)
                logger.debug("Session created: %s (user=%s)", session_id, user_id)
            state = self._sessions[session_id]
            state.touch()
            return state

    def get(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            state = self._sessions.get(session_id)
            if state:
                state.touch()
            return state

    def delete(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "mode": s.mode,
                    "current_entity": f"{s.current_entity_type}/{s.current_entity_id}" if s.current_entity_type else "",
                    "current_company": s.current_company_name or s.current_company_id,
                    "actions_count": len(s.recent_actions),
                    "created_at": s.created_at,
                    "last_active": s.last_active,
                }
                for s in self._sessions.values()
            ]

    # ------------------------------------------------------------------
    # Entity context
    # ------------------------------------------------------------------

    def set_entity(self, session_id: str, entity_type: str, entity_id: str, data: Optional[Dict[str, Any]] = None) -> None:
        state = self.get(session_id)
        if state:
            state.current_entity_type = entity_type
            state.current_entity_id = entity_id
            state.current_entity_data = data or {}
            logger.debug("Session %s: entity set to %s/%s", session_id, entity_type, entity_id)

    def get_entity(self, session_id: str) -> Optional[Dict[str, Any]]:
        state = self.get(session_id)
        if state and state.current_entity_type:
            return {
                "type": state.current_entity_type,
                "id": state.current_entity_id,
                "data": state.current_entity_data,
            }
        return None

    def clear_entity(self, session_id: str) -> None:
        state = self.get(session_id)
        if state:
            state.current_entity_type = ""
            state.current_entity_id = ""
            state.current_entity_data = {}

    # ------------------------------------------------------------------
    # Company context
    # ------------------------------------------------------------------

    def set_company(self, session_id: str, company_id: str, name: str = "", data: Optional[Dict[str, Any]] = None) -> None:
        state = self.get(session_id)
        if state:
            state.current_company_id = company_id
            state.current_company_name = name
            state.current_company_data = data or {}
            logger.debug("Session %s: company set to %s (%s)", session_id, company_id, name)

    def get_company(self, session_id: str) -> Optional[Dict[str, Any]]:
        state = self.get(session_id)
        if state and state.current_company_id:
            return {
                "id": state.current_company_id,
                "name": state.current_company_name,
                "data": state.current_company_data,
            }
        return None

    # ------------------------------------------------------------------
    # Declaration context
    # ------------------------------------------------------------------

    def set_declaration(self, session_id: str, declaration_id: str, data: Optional[Dict[str, Any]] = None) -> None:
        state = self.get(session_id)
        if state:
            state.current_declaration_id = declaration_id
            state.current_declaration_data = data or {}

    def get_declaration(self, session_id: str) -> Optional[Dict[str, Any]]:
        state = self.get(session_id)
        if state and state.current_declaration_id:
            return {
                "id": state.current_declaration_id,
                "data": state.current_declaration_data,
            }
        return None

    # ------------------------------------------------------------------
    # Recent actions
    # ------------------------------------------------------------------

    def record_action(
        self,
        session_id: str,
        action_type: str,
        description: str,
        entity_type: str = "",
        entity_id: str = "",
        **metadata: Any,
    ) -> ActionRecord:
        action = ActionRecord(
            action_type=action_type,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
        )
        state = self.get(session_id)
        if state:
            state.recent_actions.append(action)
        return action

    def get_recent_actions(self, session_id: str, limit: int = 10) -> List[ActionRecord]:
        state = self.get(session_id)
        if state is None:
            return []
        actions = list(state.recent_actions)
        return actions[-limit:]

    def get_actions_by_type(self, session_id: str, action_type: str) -> List[ActionRecord]:
        state = self.get(session_id)
        if state is None:
            return []
        return [a for a in state.recent_actions if a.action_type == action_type]

    def clear_actions(self, session_id: str) -> int:
        state = self.get(session_id)
        if state is None:
            return 0
        count = len(state.recent_actions)
        state.recent_actions.clear()
        return count

    # ------------------------------------------------------------------
    # Flags / mode
    # ------------------------------------------------------------------

    def set_flag(self, session_id: str, key: str, value: Any = True) -> None:
        state = self.get(session_id)
        if state:
            state.flags[key] = value

    def get_flag(self, session_id: str, key: str, default: Any = None) -> Any:
        state = self.get(session_id)
        if state is None:
            return default
        return state.flags.get(key, default)

    def clear_flag(self, session_id: str, key: str) -> None:
        state = self.get(session_id)
        if state:
            state.flags.pop(key, None)

    def set_mode(self, session_id: str, mode: str) -> None:
        state = self.get(session_id)
        if state:
            state.mode = mode

    def get_mode(self, session_id: str) -> str:
        state = self.get(session_id)
        return state.mode if state else ""

    # ------------------------------------------------------------------
    # Dump / context snapshot
    # ------------------------------------------------------------------

    def snapshot(self, session_id: str) -> Dict[str, Any]:
        """Return the full session state as a serialisable dict."""
        state = self.get(session_id)
        if state is None:
            return {}
        return {
            "session_id": state.session_id,
            "user_id": state.user_id,
            "entity": self.get_entity(session_id),
            "company": self.get_company(session_id),
            "declaration": self.get_declaration(session_id),
            "recent_actions": [a.to_dict() for a in state.recent_actions],
            "flags": dict(state.flags),
            "mode": state.mode,
            "created_at": state.created_at,
            "last_active": state.last_active,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_active > self._ttl]
        for sid in expired:
            del self._sessions[sid]

    def _evict_oldest(self) -> None:
        if self._sessions:
            oldest = min(self._sessions, key=lambda s: self._sessions[s].last_active)
            del self._sessions[oldest]
