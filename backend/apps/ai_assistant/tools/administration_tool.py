"""
AdministrationTool — queries environmental administration offices.

Actions: search, get, by_type, by_wilaya, by_status
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class AdministrationTool(BaseTool):
    """Tool for querying environmental administration offices (ministries, directions, AND)."""

    name = "administration_tool"
    description = (
        "Consultation des administrations de l'environnement. "
        "Permet de rechercher les ministères, directions wilaya et agences nationales des déchets (AND). "
        "Recherche par nom, wilaya, type ou statut."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.administration_repository import AdministrationRepository
            self._repo = AdministrationRepository()
        return self._repo

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "get", "by_type", "by_wilaya", "by_status"
            ], description="Action a effectuer")
            .field("query", "str", required=False, description="Terme de recherche (nom, wilaya, directeur, email)")
            .field("administration_id", "int", required=False, description="ID de l'administration")
            .field("type_administration", "str", required=False, enum=[
                "MINISTERE", "DIR_WILAYA", "AND"
            ], description="Type d'administration")
            .field("wilaya", "str", required=False, description="Code wilaya (ex: '16')")
            .field("statut", "str", required=False, enum=[
                "ACTIF", "INACTIF", "SUSPENDU"
            ], description="Statut de l'administration")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "search": self._search,
            "get": self._get,
            "by_type": self._by_type,
            "by_wilaya": self._by_wilaya,
            "by_status": self._by_status,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _search(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        if not query:
            return ToolResultResponse.fail("Parametre 'query' requis")

        results = self._repository.search(query, limit=params.get("limit", 20))

        return ToolResultResponse.ok(
            data={"administrations": results, "count": len(results)},
            message=f"{len(results)} administration(s) trouvee(s)"
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        admin_id = params.get("administration_id")
        if not admin_id:
            return ToolResultResponse.fail("Parametre 'administration_id' requis")

        result = self._repository.get(admin_id)
        if result is None:
            return ToolResultResponse.fail("Administration non trouvee")

        return ToolResultResponse.ok(data=result, message="Administration trouvee")

    def _by_type(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        type_admin = params.get("type_administration", "")
        if not type_admin:
            return ToolResultResponse.fail("Parametre 'type_administration' requis")

        results = self._repository.filter_by_type(type_admin, limit=params.get("limit", 50))

        type_labels = {
            "MINISTERE": "Ministere de l'Environnement",
            "DIR_WILAYA": "Direction de l'Environnement de Wilaya",
            "AND": "Agence Nationale des Dechets",
        }
        label = type_labels.get(type_admin, type_admin)

        return ToolResultResponse.ok(
            data={"administrations": results, "type": type_admin, "count": len(results)},
            message=f"{len(results)} {label} trouve(es)"
        )

    def _by_wilaya(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        wilaya = params.get("wilaya", "")
        if not wilaya:
            return ToolResultResponse.fail("Parametre 'wilaya' requis")

        results = self._repository.filter_by_wilaya(wilaya, limit=params.get("limit", 50))

        return ToolResultResponse.ok(
            data={"administrations": results, "wilaya": wilaya, "count": len(results)},
            message=f"{len(results)} administration(s) en wilaya {wilaya}"
        )

    def _by_status(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        statut = params.get("statut", "")
        if not statut:
            return ToolResultResponse.fail("Parametre 'statut' requis")

        results = self._repository.filter_by_status(statut, limit=params.get("limit", 50))

        return ToolResultResponse.ok(
            data={"administrations": results, "statut": statut, "count": len(results)},
            message=f"{len(results)} administration(s) avec statut {statut}"
        )
