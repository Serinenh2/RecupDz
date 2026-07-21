"""
Audit Logger — immutable audit trail for all AI operations.

Supports in-memory storage with optional file-based persistence.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    LOGIN = "login"
    LOGOUT = "logout"
    SEARCH = "search"
    EXPORT = "export"
    CHAT = "chat"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    ERROR = "error"
    ACCESS_DENIED = "access_denied"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit event."""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    action: AuditAction = AuditAction.READ
    user_id: str = ""
    user_roles: List[str] = field(default_factory=list)
    resource_type: str = ""
    resource_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    request_id: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "action": self.action.value,
            "user_id": self.user_id,
            "user_roles": self.user_roles,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "duration_ms": round(self.duration_ms, 1),
            "success": self.success,
            "error_message": self.error_message,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class AuditLogger:
    """
    Production audit logger with configurable sinks.

    Supports:
        - In-memory storage with LRU eviction
        - Optional file-based persistence (JSONL format)
        - Callback notifications for real-time consumers
    """

    def __init__(
        self,
        max_events: int = 10000,
        sink: Optional[str] = None,
        persist: bool = False,
    ) -> None:
        self._events: List[AuditEvent] = []
        self._max_events = max_events
        self._sink = sink
        self._persist = persist
        self._callbacks: List[callable] = []
        self._file_lock = threading.Lock()
        if self._persist and self._sink:
            os.makedirs(os.path.dirname(self._sink), exist_ok=True)

    def log(self, event: AuditEvent) -> None:
        """Record an audit event."""
        self._events.append(event)

        # Evict oldest if at capacity
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        # Persist to file if configured
        if self._persist and self._sink:
            self._write_to_file(event)

        # Notify callbacks
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass

        # Log to Python logger
        logger.info(
            "AUDIT: %s user=%s resource=%s/%s success=%s",
            event.action.value,
            event.user_id or "anonymous",
            event.resource_type,
            event.resource_id,
            event.success,
        )

    def _write_to_file(self, event: AuditEvent) -> None:
        """Append an audit event to the persistence file."""
        try:
            with self._file_lock:
                with open(self._sink, "a", encoding="utf-8") as f:
                    f.write(event.to_json() + "\n")
        except Exception as exc:
            logger.warning("Failed to persist audit event: %s", exc)

    def log_simple(
        self,
        action: AuditAction,
        user_id: str = "",
        resource_type: str = "",
        resource_id: str = "",
        **details: Any,
    ) -> AuditEvent:
        """Convenience method for simple audit events."""
        event = AuditEvent(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        self.log(event)
        return event

    def on_event(self, callback: callable) -> None:
        """Register a callback for new events."""
        self._callbacks.append(callback)

    def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
        results = self._events

        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if action:
            results = [e for e in results if e.action == action]
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]
        if since:
            results = [e for e in results if e.timestamp >= since]

        return results[-limit:]

    def count(self, **filters: Any) -> int:
        return len(self.query(**filters))

    def clear(self) -> int:
        count = len(self._events)
        self._events.clear()
        return count

    def stats(self) -> Dict[str, Any]:
        from collections import Counter
        action_counts = Counter(e.action.value for e in self._events)
        return {
            "total_events": len(self._events),
            "by_action": dict(action_counts),
            "max_events": self._max_events,
        }
