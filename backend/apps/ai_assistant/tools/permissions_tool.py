"""
PermissionsTool — RBAC roles and permissions queries.

Actions: list_roles, role_detail, user_permissions, check_permission

Uses PermissionRepository for ALL database access.
No direct Django ORM imports.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema

# Canonical role labels (maps internal group name → display label)
_ROLE_LABELS = {
    "super_administrateur": "Super Administrateur",
    "administrateur": "Administrateur",
    "recuperateur": "Recuperateur",
    "responsable_collecte": "Responsable Collecte",
    "agent_collecte": "Agent de Collecte",
    "responsable_decharge": "Responsable Decharge",
    "observateur": "Observateur",
}

# Role hierarchy levels (mirrors User.ROLE_HIERARCHY)
_ROLE_LEVELS = {
    "SUPERADMIN": 100,
    "ADMIN": 80,
    "RECUPERATEUR": 60,
    "RESPONSABLE_COLLECTE": 60,
    "AGENT_COLLECTE": 40,
    "RESPONSABLE_DECHARGE": 40,
    "OBSERVATEUR": 10,
}


class PermissionsTool(BaseTool):
    """Tool for querying RBAC roles, permissions, and access control."""

    name = "permissions_tool"
    description = (
        "Gestion des roles et permissions RBAC. "
        "Permet de lister les roles, consulter les permissions d'un role ou d'un utilisateur, "
        "et verifier si un utilisateur a une permission specifique."
    )

    @property
    def required_permissions(self) -> List[str]:
        return ["ai.view_permissions"]

    def __init__(self) -> None:
        super().__init__()
        self._perm_repo = None

    @property
    def _repository(self):
        if self._perm_repo is None:
            from apps.ai_assistant.repositories.permission_repository import PermissionRepository
            self._perm_repo = PermissionRepository()
        return self._perm_repo

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "list_roles", "role_detail", "user_permissions", "check_permission"
            ], description="Action a effectuer")
            .field("role", "str", required=False, enum=[
                "SUPERADMIN", "ADMIN", "RECUPERATEUR",
                "RESPONSABLE_COLLECTE", "AGENT_COLLECTE",
                "RESPONSABLE_DECHARGE", "OBSERVATEUR"
            ], description="Role a consulter")
            .field("username", "str", required=False, description="Nom d'utilisateur")
            .field("user_id", "int", required=False, description="ID utilisateur")
            .field("permission", "str", required=False, description="Permission a verifier (ex: 'view_bsd')")
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "list_roles": self._list_roles,
            "role_detail": self._role_detail,
            "user_permissions": self._user_permissions,
            "check_permission": self._check_permission,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _list_roles(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        groups = self._repository.list_groups()

        roles = []
        for group in groups:
            label = _ROLE_LABELS.get(group["name"], group["name"])
            level = _ROLE_LEVELS.get(group["name"].upper(), 0)
            roles.append({
                "nom": group["name"],
                "label": label,
                "niveau": level,
                "nombre_permissions": group["permission_count"],
                "nombre_utilisateurs": group["user_count"],
            })

        roles.sort(key=lambda r: -r["niveau"])

        return ToolResultResponse.ok(
            data={"roles": roles, "count": len(roles)},
            message=f"{len(roles)} role(s) disponible(s)"
        )

    def _role_detail(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        role_name = params.get("role", "")
        if not role_name:
            return ToolResultResponse.fail("Parametre 'role' requis")

        group = self._repository.get_group_by_name(role_name)

        if group is None:
            return ToolResultResponse.fail(f"Role '{role_name}' non trouve")

        label = _ROLE_LABELS.get(group["name"], group["name"])
        level = _ROLE_LEVELS.get(group["name"].upper(), 0)

        return ToolResultResponse.ok(
            data={
                "nom": group["name"],
                "label": label,
                "niveau": level,
                "permissions": group["permissions"],
                "nombre_permissions": group["permission_count"],
                "nombre_utilisateurs": group["user_count"],
            },
            message=f"Role {label} — {group['permission_count']} permission(s), {group['user_count']} utilisateur(s)"
        )

    def _user_permissions(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        user_id = params.get("user_id")
        username = params.get("username")

        if user_id:
            user_data = self._repository.get_user_permissions(int(user_id))
        elif username:
            user_obj = self._repository.get_user_by_username(username)
            if user_obj is None:
                return ToolResultResponse.fail("Utilisateur non trouve")
            user_data = self._repository.get_user_permissions(user_obj["pk"])
        else:
            return ToolResultResponse.fail("Parametre 'username' ou 'user_id' requis")

        if user_data is None:
            return ToolResultResponse.fail("Utilisateur non trouve")

        return ToolResultResponse.ok(
            data={
                "username": user_data["username"],
                "role": user_data["role"],
                "roles": user_data["groups"],
                "permissions": user_data["permissions"],
                "permissions_directes": user_data["permissions_direct"],
                "permissions_via_groupe": user_data["permissions_via_group"],
                "nombre_permissions": user_data["permission_count"],
            },
            message=f"{user_data['username']} — {user_data['permission_count']} permission(s)"
        )

    def _check_permission(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        user_id = params.get("user_id")
        username = params.get("username")
        permission = params.get("permission", "")

        if not permission:
            return ToolResultResponse.fail("Parametre 'permission' requis")

        if user_id:
            user_obj = self._repository.get_user(int(user_id))
        elif username:
            user_obj = self._repository.get_user_by_username(username)
        else:
            return ToolResultResponse.fail("Parametre 'username' ou 'user_id' requis")

        if user_obj is None:
            return ToolResultResponse.fail("Utilisateur non trouve")

        result = self._repository.check_user_permission(user_obj["pk"], permission)

        if result is None:
            return ToolResultResponse.fail("Utilisateur non trouve")

        return ToolResultResponse.ok(
            data={
                "username": result["username"],
                "permission": result["permission"],
                "autorise": result["autorise"],
            },
            message=f"{result['username']} {'a' if result['autorise'] else 'n\'a pas'} la permission '{permission}'"
        )
