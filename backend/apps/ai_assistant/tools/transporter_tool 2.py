"""
TransporterTool — manages waste transporters (transporteurs).

Actions: search, list, get, by_wilaya, by_recuperateur
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class TransporterTool(BaseTool):
    """Tool for managing waste transporters."""

    name = "transporteur_tool"
    description = (
        "Recherche et consultation des transporteurs de dechets. "
        "Permet de lister, consulter et filtrer les transporteurs "
        "par wilaya ou par recuperateur."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.operateur_repository import OperateurRepository
            self._repo = OperateurRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des transporteurs par mot-cle. Parametre requis: query (str)",
            "list": "Lister tous les transporteurs. Aucun parametre requis",
            "get": "Consulter un transporteur par son ID. Parametre requis: operateur_id (int)",
            "by_wilaya": "Filtrer les transporteurs par wilaya. Parametre requis: wilaya (str, ex: '16')",
            "by_recuperateur": "Filtrer les transporteurs associes a un recuperateur. Parametre requis: recuperateur_id (int)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "list", "get", "by_wilaya", "by_recuperateur"
            ], description="Action a effectuer")
            .field("query", "str", required=False, description="Terme de recherche")
            .field("operateur_id", "int", required=False, description="ID du transporteur")
            .field("wilaya", "str", required=False, description="Code wilaya")
            .field("recuperateur_id", "int", required=False, description="ID recuperateur")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .field("offset", "int", required=False, default=0, min_value=0)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "search": self._search,
            "list": self._list,
            "get": self._get,
            "by_wilaya": self._by_wilaya,
            "by_recuperateur": self._by_recuperateur,
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
            data={"transporteurs": results, "count": len(results)},
            message=f"{len(results)} transporteur(s) trouve(s)"
        )

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._repository.filter_transporteurs(limit=params.get("limit", 20))
        return ToolResultResponse.ok(
            data={"transporteurs": results, "count": len(results)},
            message=f"{len(results)} transporteur(s)"
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        operateur_id = params.get("operateur_id")
        if not operateur_id:
            return ToolResultResponse.fail("Parametre 'operateur_id' requis")

        result = self._repository.get(operateur_id)
        if result is None:
            return ToolResultResponse.fail(f"Transporteur {operateur_id} non trouve")
        return ToolResultResponse.ok(data=result, message="Transporteur trouve")

    def _by_wilaya(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        wilaya = params.get("wilaya", "")
        if not wilaya:
            return ToolResultResponse.fail("Parametre 'wilaya' requis")

        results = self._repository.filter_by_wilaya(wilaya, "TRANSPORTEUR", limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"transporteurs": results, "wilaya": wilaya, "count": len(results)},
            message=f"{len(results)} transporteur(s) en wilaya {wilaya}"
        )

    def _by_recuperateur(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Parametre 'recuperateur_id' requis")

        results = self._repository.filter_by_recuperateur(recuperateur_id, "TRANSPORTEUR")
        return ToolResultResponse.ok(
            data={"transporteurs": results, "count": len(results)},
            message=f"{len(results)} transporteur(s) pour ce recuperateur"
        )
