"""
PartnerTool — manages external partners (operateurs: eliminateurs, valoriseurs, CET).

Actions: search, list, get, by_type, by_wilaya
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class PartnerTool(BaseTool):
    """Tool for managing external partners (eliminators, valorizers, CETs)."""

    name = "partner_tool"
    description = (
        "Recherche et consultation des partenaires externes : "
        "eliminateurs, valoriseurs, CET, directions wilaya, ministeres. "
        "Permet de lister, consulter et filtrer par type et wilaya."
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
            "search": "Rechercher des partenaires par mot-cle. Parametre requis: query (str)",
            "list": "Lister les partenaires avec filtres optionnels. Parametres optionnels: recuperateur_id (int), type_operateur (str), wilaya (str), limit (int), offset (int)",
            "get": "Consulter un partenaire par son ID. Parametre requis: operateur_id (int)",
            "by_type": "Filtrer les partenaires par type. Parametre requis: type_operateur (str parmi: ELIMINATEUR, VALORISATEUR, CET, DIR_WILAYA, MINISTERE)",
            "by_wilaya": "Filtrer les partenaires par wilaya. Parametre requis: wilaya (str, ex: '16'). Parametre optionnel: type_operateur (str)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "list", "get", "by_type", "by_wilaya"
            ], description="Action a effectuer")
            .field("query", "str", required=False, description="Terme de recherche")
            .field("operateur_id", "int", required=False, description="ID du partenaire")
            .field("type_operateur", "str", required=False, enum=[
                "ELIMINATEUR", "VALORISATEUR", "CET", "DIR_WILAYA", "MINISTERE"
            ], description="Type de partenaire")
            .field("wilaya", "str", required=False, description="Code wilaya (ex: 16)")
            .field("recuperateur_id", "int", required=False, description="ID recuperateur proprietaire")
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
            "by_type": self._by_type,
            "by_wilaya": self._by_wilaya,
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
            data={"partenaires": results, "count": len(results)},
            message=f"{len(results)} partenaire(s) trouve(s)"
        )

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        filters = {}
        if params.get("recuperateur_id"):
            filters["recuperateur_id"] = params["recuperateur_id"]
        if params.get("type_operateur"):
            filters["type_operateur"] = params["type_operateur"]
        if params.get("wilaya"):
            filters["wilaya"] = params["wilaya"]

        results = self._repository.list(
            limit=params.get("limit", 20),
            offset=params.get("offset", 0),
            **filters
        )
        total = self._repository.count(**filters)
        return ToolResultResponse.ok(
            data={"partenaires": results, "total": total, "count": len(results)},
            message=f"{total} partenaire(s) au total"
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        operateur_id = params.get("operateur_id")
        if not operateur_id:
            return ToolResultResponse.fail("Parametre 'operateur_id' requis")

        result = self._repository.get(operateur_id)
        if result is None:
            return ToolResultResponse.fail(f"Partenaire {operateur_id} non trouve")
        return ToolResultResponse.ok(data=result, message="Partenaire trouve")

    def _by_type(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        type_operateur = params.get("type_operateur", "")
        if not type_operateur:
            return ToolResultResponse.fail("Parametre 'type_operateur' requis")

        results = self._repository.filter_by_type(type_operateur, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"partenaires": results, "type": type_operateur, "count": len(results)},
            message=f"{len(results)} partenaire(s) de type {type_operateur}"
        )

    def _by_wilaya(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        wilaya = params.get("wilaya", "")
        if not wilaya:
            return ToolResultResponse.fail("Parametre 'wilaya' requis")

        type_operateur = params.get("type_operateur")
        results = self._repository.filter_by_wilaya(wilaya, type_operateur, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"partenaires": results, "wilaya": wilaya, "count": len(results)},
            message=f"{len(results)} partenaire(s) en wilaya {wilaya}"
        )
