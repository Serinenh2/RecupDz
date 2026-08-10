"""
InspectionTool — manages regulatory inspections.

Actions: get, list, filter_by_recuperateur, filter_by_resultat, filter_by_type, get_stats
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class InspectionTool(BaseTool):
    """Tool for regulatory inspection queries."""

    name = "inspection_tool"
    description = (
        "Gestion des inspections réglementaires. "
        "Permet de consulter les inspections, filtrer par résultat "
        "et par type (routine, surprise, plainte, suivi)."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.inspection_repository import InspectionRepository
            self._repo = InspectionRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "get": "Obtenir une inspection par son ID. Paramètre requis: inspection_id (int)",
            "list": "Lister toutes les inspections. Aucun paramètre requis",
            "filter_by_recuperateur": "Filtrer par récupérateur. Paramètre requis: recuperateur_id (int)",
            "filter_by_resultat": "Filtrer par résultat. Paramètre requis: resultat (str parmi: CONFORME, NON_CONFORME, EN_COURS)",
            "filter_by_type": "Filtrer par type d'inspection. Paramètre requis: type_inspection (str parmi: ROUTINE, SURPRISE, PLAINTE, SUIVI)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "get", "list", "filter_by_recuperateur",
                "filter_by_resultat", "filter_by_type",
            ], description="Action à effectuer")
            .field("inspection_id", "int", required=False, description="ID de l'inspection (pour action=get)")
            .field("recuperateur_id", "int", required=False, description="ID récupérateur (pour action=filter_by_recuperateur)")
            .field("resultat", "str", required=False, enum=["CONFORME", "NON_CONFORME", "EN_COURS"],
                   description="Résultat (pour action=filter_by_resultat)")
            .field("type_inspection", "str", required=False, enum=["ROUTINE", "SURPRISE", "PLAINTE", "SUIVI"],
                   description="Type d'inspection (pour action=filter_by_type)")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]
        handlers = {
            "get": self._get,
            "list": self._list,
            "filter_by_recuperateur": self._filter_by_recuperateur,
            "filter_by_resultat": self._filter_by_resultat,
            "filter_by_type": self._filter_by_type,
        }
        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")
        return handler(parameters, context)

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        inspection_id = params.get("inspection_id")
        if not inspection_id:
            return ToolResultResponse.fail("Paramètre 'inspection_id' requis")
        result = self._repository.get(inspection_id)
        if result is None:
            return ToolResultResponse.fail(f"Inspection {inspection_id} non trouvée")
        return ToolResultResponse.ok(data=result, message="Inspection trouvée")

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._repository.list(limit=params.get("limit", 20))
        total = self._repository.count()
        return ToolResultResponse.ok(
            data={"inspections": results, "total": total, "count": len(results)},
            message=f"{total} inspection(s) au total",
        )

    def _filter_by_recuperateur(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Paramètre 'recuperateur_id' requis")
        results = self._repository.filter_by_recuperateur(recuperateur_id, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"inspections": results, "count": len(results)},
            message=f"{len(results)} inspection(s) pour ce récupérateur",
        )

    def _filter_by_resultat(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        resultat = params.get("resultat", "")
        if not resultat:
            return ToolResultResponse.fail("Paramètre 'resultat' requis")
        results = self._repository.filter_by_resultat(resultat, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"inspections": results, "count": len(results), "resultat": resultat},
            message=f"{len(results)} inspection(s) avec résultat '{resultat}'",
        )

    def _filter_by_type(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        type_insp = params.get("type_inspection", "")
        if not type_insp:
            return ToolResultResponse.fail("Paramètre 'type_inspection' requis")
        results = self._repository.list(limit=params.get("limit", 50), type_inspection=type_insp)
        return ToolResultResponse.ok(
            data={"inspections": results, "count": len(results), "type_inspection": type_insp},
            message=f"{len(results)} inspection(s) de type '{type_insp}'",
        )
