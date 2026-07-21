"""
AuthenticationTool — manages user authentication and profile.

Actions: get_user, list_users, by_role, by_wilaya, profile
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class AuthenticationTool(BaseTool):
    """Tool for user authentication and profile queries."""

    name = "authentification_tool"
    description = (
        "Consultation des profils utilisateurs et gestion de l'authentification. "
        "Permet de rechercher des utilisateurs, consulter les profils, "
        "et lister par role ou wilaya."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.user_repository import UserRepository
            self._repo = UserRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "get_user": "Consulter un utilisateur par son ID ou son nom d'utilisateur. Parametres requis: user_id (int) ou username (str)",
            "search": "Rechercher des utilisateurs par mot-cle. Parametre requis: query (str)",
            "by_role": "Filtrer les utilisateurs par role. Parametre requis: role (str parmi: SUPERADMIN, ADMIN, RECUPERATEUR, RESPONSABLE_COLLECTE, AGENT_COLLECTE, RESPONSABLE_DECHARGE, OBSERVATEUR)",
            "by_wilaya": "Filtrer les utilisateurs par wilaya. Parametre requis: wilaya (str, ex: '16')",
            "profile": "Consulter le profil de l'utilisateur connecte. Aucun parametre requis",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "get_user", "search", "by_role", "by_wilaya", "profile"
            ], description="Action a effectuer")
            .field("query", "str", required=False, description="Terme de recherche")
            .field("user_id", "int", required=False, description="ID utilisateur")
            .field("username", "str", required=False, description="Nom d'utilisateur")
            .field("role", "str", required=False, enum=[
                "SUPERADMIN", "ADMIN", "RECUPERATEUR",
                "RESPONSABLE_COLLECTE", "AGENT_COLLECTE",
                "RESPONSABLE_DECHARGE", "OBSERVATEUR"
            ], description="Role utilisateur")
            .field("wilaya", "str", required=False, description="Code wilaya")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "get_user": self._get_user,
            "search": self._search,
            "by_role": self._by_role,
            "by_wilaya": self._by_wilaya,
            "profile": self._profile,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _get_user(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        user_id = params.get("user_id")
        username = params.get("username")

        if user_id:
            result = self._repository.get(user_id)
        elif username:
            result = self._repository.get_by_username(username)
        else:
            return ToolResultResponse.fail("Parametre 'user_id' ou 'username' requis")

        if result is None:
            return ToolResultResponse.fail("Utilisateur non trouve")

        # Sanitize sensitive fields
        result.pop("password", None)
        result.pop("last_login", None)

        return ToolResultResponse.ok(data=result, message="Utilisateur trouve")

    def _search(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        if not query:
            return ToolResultResponse.fail("Parametre 'query' requis")

        results = self._repository.search(query, limit=params.get("limit", 20))

        # Sanitize
        for r in results:
            r.pop("password", None)
            r.pop("last_login", None)

        return ToolResultResponse.ok(
            data={"utilisateurs": results, "count": len(results)},
            message=f"{len(results)} utilisateur(s) trouve(s)"
        )

    def _by_role(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        role = params.get("role", "")
        if not role:
            return ToolResultResponse.fail("Parametre 'role' requis")

        results = self._repository.filter_by_role(role, limit=params.get("limit", 50))

        # Sanitize
        for r in results:
            r.pop("password", None)
            r.pop("last_login", None)

        return ToolResultResponse.ok(
            data={"utilisateurs": results, "role": role, "count": len(results)},
            message=f"{len(results)} utilisateur(s) avec role {role}"
        )

    def _by_wilaya(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        wilaya = params.get("wilaya", "")
        if not wilaya:
            return ToolResultResponse.fail("Parametre 'wilaya' requis")

        results = self._repository.filter_by_wilaya(wilaya, limit=params.get("limit", 50))

        # Sanitize
        for r in results:
            r.pop("password", None)
            r.pop("last_login", None)

        return ToolResultResponse.ok(
            data={"utilisateurs": results, "wilaya": wilaya, "count": len(results)},
            message=f"{len(results)} utilisateur(s) en wilaya {wilaya}"
        )

    def _profile(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        if not ctx.user_id:
            return ToolResultResponse.fail("Aucun utilisateur connecte")

        result = self._repository.get(ctx.user_id)
        if result is None:
            return ToolResultResponse.fail("Profil non trouve")

        # Sanitize
        result.pop("password", None)
        result.pop("last_login", None)

        return ToolResultResponse.ok(data=result, message="Votre profil")
