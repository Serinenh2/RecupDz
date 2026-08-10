"""
Tool Context — enriched execution context passed to every tool.

Wraps the core Context with tool-specific concerns:
request metadata, user permissions, timeout budget, tracing.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ToolContext:
    """
    Execution context provided to every BaseTool.execute() call.

    Carries everything a tool might need beyond its explicit parameters.
    """

    # -- core identifiers --
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    conversation_id: str = ""
    user_id: str = ""
    user_roles: List[str] = field(default_factory=list)

    # -- timeout budget --
    total_timeout_seconds: float = 30.0
    _start_time: float = field(default_factory=time.monotonic, repr=False)

    # -- permissions --
    _granted_permissions: Set[str] = field(default_factory=set, repr=False)

    # -- request metadata --
    language: str = "fr"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- tracing --
    trace_log: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def remaining_timeout(self) -> float:
        return max(0.0, self.total_timeout_seconds - self.elapsed_seconds)

    def has_permission(self, permission: str) -> bool:
        if "superadmin" in self.user_roles:
            return True
        return permission in self._granted_permissions

    def grant_permission(self, permission: str) -> None:
        self._granted_permissions.add(permission)

    def grant_permissions(self, permissions: List[str]) -> None:
        self._granted_permissions.update(permissions)

    def has_role(self, role: str) -> bool:
        return role.lower() in [r.lower() for r in self.user_roles]

    def trace(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.trace_log.append({
            "timestamp": time.monotonic(),
            "elapsed": self.elapsed_seconds,
            "event": event,
            "details": details or {},
        })

    def is_expired(self) -> bool:
        return self.elapsed_seconds >= self.total_timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "user_roles": self.user_roles,
            "language": self.language,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "remaining_timeout": round(self.remaining_timeout, 3),
            "permissions": list(self._granted_permissions),
            "metadata": self.metadata,
        }

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        user_id: str = "",
        conversation_id: str = "",
        user_roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        language: str = "fr",
        timeout: float = 30.0,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolContext:
        ctx = cls(
            user_id=user_id,
            conversation_id=conversation_id,
            user_roles=user_roles or [],
            language=language,
            total_timeout_seconds=timeout,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {},
        )
        if permissions:
            ctx.grant_permissions(permissions)
        return ctx
