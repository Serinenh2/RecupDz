"""
Permission Framework — role-based and attribute-based access control.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """AI module permissions."""
    # Chat
    CHAT_READ = "ai:chat:read"
    CHAT_WRITE = "ai:chat:write"
    CHAT_STREAM = "ai:chat:stream"

    # Tools
    TOOL_EXECUTE = "ai:tool:execute"
    TOOL_LIST = "ai:tool:list"

    # Knowledge
    KNOWLEDGE_READ = "ai:knowledge:read"
    KNOWLEDGE_WRITE = "ai:knowledge:write"

    # Alerts
    ALERT_READ = "ai:alert:read"
    ALERT_WRITE = "ai:alert:write"
    ALERT_MANAGE = "ai:alert:manage"

    # Recommendations
    RECOMMENDATION_READ = "ai:recommendation:read"
    RECOMMENDATION_WRITE = "ai:recommendation:write"

    # Dashboard
    DASHBOARD_READ = "ai:dashboard:read"

    # Admin
    ADMIN_CONFIG = "ai:admin:config"
    ADMIN_CACHE = "ai:admin:cache"
    ADMIN_METRICS = "ai:admin:metrics"
    ADMIN_AUDIT = "ai:admin:audit"

    # System
    SYSTEM_HEALTH = "ai:system:health"
    SYSTEM_TRACING = "ai:system:tracing"


class Role(str, Enum):
    """User roles with associated permission sets."""
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    RECUPERATEUR = "recuperateur"
    RESPONSABLE_COLLECTE = "responsable_collecte"
    AGENT_COLLECTE = "agent_collecte"
    OBSERVATEUR = "observateur"


# Role → Permission mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPERADMIN: set(Permission),  # All permissions
    Role.ADMIN: {
        Permission.CHAT_READ, Permission.CHAT_WRITE, Permission.CHAT_STREAM,
        Permission.TOOL_EXECUTE, Permission.TOOL_LIST,
        Permission.KNOWLEDGE_READ, Permission.KNOWLEDGE_WRITE,
        Permission.ALERT_READ, Permission.ALERT_WRITE, Permission.ALERT_MANAGE,
        Permission.RECOMMENDATION_READ, Permission.RECOMMENDATION_WRITE,
        Permission.DASHBOARD_READ,
        Permission.ADMIN_CONFIG, Permission.ADMIN_CACHE, Permission.ADMIN_METRICS, Permission.ADMIN_AUDIT,
        Permission.SYSTEM_HEALTH, Permission.SYSTEM_TRACING,
    },
    Role.RECUPERATEUR: {
        Permission.CHAT_READ, Permission.CHAT_WRITE, Permission.CHAT_STREAM,
        Permission.TOOL_EXECUTE, Permission.TOOL_LIST,
        Permission.KNOWLEDGE_READ,
        Permission.ALERT_READ, Permission.ALERT_WRITE,
        Permission.RECOMMENDATION_READ,
        Permission.DASHBOARD_READ,
    },
    Role.RESPONSABLE_COLLECTE: {
        Permission.CHAT_READ, Permission.CHAT_WRITE,
        Permission.TOOL_LIST,
        Permission.KNOWLEDGE_READ,
        Permission.ALERT_READ,
        Permission.RECOMMENDATION_READ,
        Permission.DASHBOARD_READ,
    },
    Role.AGENT_COLLECTE: {
        Permission.CHAT_READ, Permission.CHAT_WRITE,
        Permission.TOOL_LIST,
        Permission.KNOWLEDGE_READ,
        Permission.ALERT_READ,
        Permission.DASHBOARD_READ,
    },
    Role.OBSERVATEUR: {
        Permission.CHAT_READ,
        Permission.TOOL_LIST,
        Permission.KNOWLEDGE_READ,
        Permission.ALERT_READ,
        Permission.DASHBOARD_READ,
    },
}


@dataclass
class AccessContext:
    """Context for permission evaluation."""
    user_id: str = ""
    user_roles: List[str] = field(default_factory=list)
    resource_type: str = ""
    resource_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class PermissionManager:
    """Evaluates permissions against roles and custom rules."""

    def __init__(self) -> None:
        self._custom_rules: List[Callable[[AccessContext, Permission], bool]] = []

    def has_permission(
        self,
        context: AccessContext,
        permission: Permission,
    ) -> bool:
        """Check if a user has a specific permission."""
        # Superadmin bypasses all checks
        if Role.SUPERADMIN.value in context.user_roles:
            return True

        # Check role-based permissions
        for role_name in context.user_roles:
            try:
                role = Role(role_name)
                if permission in ROLE_PERMISSIONS.get(role, set()):
                    return True
            except ValueError:
                continue

        # Check custom rules
        for rule in self._custom_rules:
            try:
                if rule(context, permission):
                    return True
            except Exception:
                continue

        return False

    def has_any_permission(
        self,
        context: AccessContext,
        permissions: List[Permission],
    ) -> bool:
        """Check if user has any of the listed permissions."""
        return any(self.has_permission(context, p) for p in permissions)

    def has_all_permissions(
        self,
        context: AccessContext,
        permissions: List[Permission],
    ) -> bool:
        """Check if user has all listed permissions."""
        return all(self.has_permission(context, p) for p in permissions)

    def get_permissions(self, context: AccessContext) -> Set[Permission]:
        """Get all permissions for a user."""
        if Role.SUPERADMIN.value in context.user_roles:
            return set(Permission)

        perms: Set[Permission] = set()
        for role_name in context.user_roles:
            try:
                role = Role(role_name)
                perms.update(ROLE_PERMISSIONS.get(role, set()))
            except ValueError:
                continue

        return perms

    def add_custom_rule(self, rule: Callable[[AccessContext, Permission], bool]) -> None:
        """Add a custom permission rule."""
        self._custom_rules.append(rule)

    def check_tool_access(
        self,
        context: AccessContext,
        tool_name: str,
    ) -> bool:
        """Check if user can execute a specific tool."""
        if not self.has_permission(context, Permission.TOOL_EXECUTE):
            return False

        # Tool-specific restrictions
        admin_tools = {"authentification_tool", "rapport_tool"}
        if tool_name in admin_tools:
            return self.has_permission(context, Permission.ADMIN_CONFIG) or \
                   Role.SUPERADMIN.value in context.user_roles or \
                   Role.ADMIN.value in context.user_roles

        return True
