"""
WasteTool — manages nomenclature codes and waste designations.

Actions: search, get, list, get_designations, filter_by_class, dangerous
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class WasteTool(BaseTool):
    """Tool for nomenclature and waste classification queries."""

    name = "waste_tool"
    description = (
        "Recherche et consultation de la nomenclature des dechets. "
        "Permet de consulter les codes, les designations, les classes "
        "de dangerosite, et les filieres de valorisation."
    )

    def __init__(self) -> None:
        super().__init__()
        self._nom_repo = None
        self._des_repo = None

    @property
    def _nomenclature_repository(self):
        if self._nom_repo is None:
            from apps.ai_assistant.repositories.nomenclature_repository import NomenclatureRepository
            self._nom_repo = NomenclatureRepository()
        return self._nom_repo

    @property
    def _designation_repository(self):
        if self._des_repo is None:
            from apps.ai_assistant.repositories.nomenclature_repository import DesignationDechetRepository
            self._des_repo = DesignationDechetRepository()
        return self._des_repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des codes nomenclature par mot-cle. Parametre requis: query (str)",
            "get": "Obtenir une nomenclature par son ID. Parametre requis: nomenclature_id (int)",
            "get_by_code": "Obtenir une nomenclature par son code. Parametre requis: code (str, ex: '15.01.06')",
            "list": "Lister tous les codes nomenclature. Aucun parametre requis",
            "get_designations": "Obtenir les designations d'une nomenclature. Parametre requis: nomenclature_id (int)",
            "filter_by_class": "Filtrer par classe de dangerosite. Parametre requis: classe (str parmi: MA, I, S, SD)",
            "dangerous": "Lister tous les dechets dangereux (classes S et SD). Aucun parametre requis",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "get", "list", "get_designations",
                "filter_by_class", "dangerous", "get_by_code"
            ], description="Action a effectuer")
            .field("query", "str", required=False, description="Terme de recherche (pour action=search)")
            .field("code", "str", required=False, description="Code nomenclature ex: 15.01.06 (pour action=get_by_code)")
            .field("nomenclature_id", "int", required=False, description="ID nomenclature (pour action=get ou get_designations)")
            .field("classe", "str", required=False, enum=["MA", "I", "S", "SD"],
                   description="Classe de dangerosite (pour action=filter_by_class)")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "search": self._search,
            "get": self._get,
            "get_by_code": self._get_by_code,
            "list": self._list,
            "get_designations": self._get_designations,
            "filter_by_class": self._filter_by_class,
            "dangerous": self._dangerous,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _search(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        if not query:
            return ToolResultResponse.fail("Parametre 'query' requis")

        results = self._nomenclature_repository.search(query, limit=params.get("limit", 20))
        return ToolResultResponse.ok(
            data={"nomenclatures": results, "count": len(results)},
            message=f"{len(results)} nomenclature(s) trouvee(s)"
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        nomenclature_id = params.get("nomenclature_id")
        if not nomenclature_id:
            return ToolResultResponse.fail("Parametre 'nomenclature_id' requis")

        result = self._nomenclature_repository.get_with_designations(nomenclature_id)
        if result is None:
            return ToolResultResponse.fail(f"Nomenclature {nomenclature_id} non trouvee")
        return ToolResultResponse.ok(data=result, message="Nomenclature trouvee")

    def _get_by_code(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        code = params.get("code", "")
        if not code:
            return ToolResultResponse.fail("Parametre 'code' requis")

        result = self._nomenclature_repository.get_by_code(code)
        if result is None:
            return ToolResultResponse.fail(f"Code {code} non trouve dans la nomenclature")
        return ToolResultResponse.ok(data=result, message=f"Code {code} trouve")

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._nomenclature_repository.list(limit=params.get("limit", 20))
        total = self._nomenclature_repository.count()
        return ToolResultResponse.ok(
            data={"nomenclatures": results, "total": total, "count": len(results)},
            message=f"{total} code(s) nomenclature au total"
        )

    def _get_designations(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        nomenclature_id = params.get("nomenclature_id")
        if not nomenclature_id:
            return ToolResultResponse.fail("Parametre 'nomenclature_id' requis")

        results = self._designation_repository.filter_by_nomenclature(nomenclature_id)
        return ToolResultResponse.ok(
            data={"designations": results, "count": len(results)},
            message=f"{len(results)} designation(s) pour ce code"
        )

    def _filter_by_class(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        classe = params.get("classe", "")
        if not classe:
            return ToolResultResponse.fail("Parametre 'classe' requis")

        results = self._nomenclature_repository.filter_by_class(classe, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"nomenclatures": results, "classe": classe, "count": len(results)},
            message=f"{len(results)} code(s) en classe {classe}"
        )

    def _dangerous(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._nomenclature_repository.filter_dangerous(limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"nomenclatures": results, "count": len(results)},
            message=f"{len(results)} dechet(s) dangereux (S/SD)"
        )
