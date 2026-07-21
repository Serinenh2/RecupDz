"""
TraceabilityTool — manages waste recovery operations tracking.

Actions: search, get, get_by_numero, list, filter_by_status, filter_by_waste_code,
         filter_by_date_range, sum_quantities, count_by_status, count_by_waste_class
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class TraceabilityTool(BaseTool):
    """Tool for waste traceability operations."""

    name = "traceability_tool"
    description = (
        "Suivi de la traçabilité des opérations de collecte et traitement de déchets. "
        "Permet de consulter les opérations, filtrer par statut, code déchet, "
        "période, et obtenir des agrégats de quantités."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.traceability_repository import TraceabilityRepository
            self._repo = TraceabilityRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des opérations par mot-clé. Paramètre requis: query (str)",
            "get": "Obtenir une opération par son ID. Paramètre requis: operation_id (int)",
            "get_by_numero": "Obtenir une opération par son numéro. Paramètre requis: numero (str)",
            "list": "Lister les opérations. Aucun paramètre requis",
            "filter_by_status": "Filtrer par statut. Paramètre requis: statut (str parmi: EN_COURS, ENLEVEMENT, TRANSPORT, RECEPTION, TRAITEMENT, TERMINEE, ANNULEE)",
            "filter_by_waste_code": "Filtrer par code déchet. Paramètre requis: code_dechet (str)",
            "filter_by_date_range": "Filtrer par période. Paramètres requis: date_from (str), date_to (str)",
            "sum_quantities": "Somme des quantités. Paramètres optionnels: date_from, date_to",
            "count_by_status": "Compter les opérations par statut. Aucun paramètre requis",
            "count_by_waste_class": "Compter les opérations par classe de déchet. Aucun paramètre requis",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "get", "get_by_numero", "list",
                "filter_by_status", "filter_by_waste_code", "filter_by_date_range",
                "sum_quantities", "count_by_status", "count_by_waste_class",
            ], description="Action à effectuer")
            .field("query", "str", required=False, description="Terme de recherche (pour action=search)")
            .field("operation_id", "int", required=False, description="ID opération (pour action=get)")
            .field("numero", "str", required=False, description="Numéro opération (pour action=get_by_numero)")
            .field("statut", "str", required=False, enum=[
                "EN_COURS", "ENLEVEMENT", "TRANSPORT", "RECEPTION", "TRAITEMENT", "TERMINEE", "ANNULEE",
            ], description="Statut (pour action=filter_by_status)")
            .field("code_dechet", "str", required=False, description="Code déchet (pour action=filter_by_waste_code)")
            .field("date_from", "str", required=False, description="Date début YYYY-MM-DD (pour action=filter_by_date_range ou sum_quantities)")
            .field("date_to", "str", required=False, description="Date fin YYYY-MM-DD (pour action=filter_by_date_range ou sum_quantities)")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]
        handlers = {
            "search": self._search,
            "get": self._get,
            "get_by_numero": self._get_by_numero,
            "list": self._list,
            "filter_by_status": self._filter_by_status,
            "filter_by_waste_code": self._filter_by_waste_code,
            "filter_by_date_range": self._filter_by_date_range,
            "sum_quantities": self._sum_quantities,
            "count_by_status": self._count_by_status,
            "count_by_waste_class": self._count_by_waste_class,
        }
        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")
        return handler(parameters, context)

    def _search(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        if not query:
            return ToolResultResponse.fail("Paramètre 'query' requis")
        results = self._repository.search(query, limit=params.get("limit", 20))
        return ToolResultResponse.ok(
            data={"operations": results, "count": len(results)},
            message=f"{len(results)} opération(s) trouvée(s)",
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        operation_id = params.get("operation_id")
        if not operation_id:
            return ToolResultResponse.fail("Paramètre 'operation_id' requis")
        result = self._repository.get(operation_id)
        if result is None:
            return ToolResultResponse.fail(f"Opération {operation_id} non trouvée")
        return ToolResultResponse.ok(data=result, message="Opération trouvée")

    def _get_by_numero(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        numero = params.get("numero", "")
        if not numero:
            return ToolResultResponse.fail("Paramètre 'numero' requis")
        result = self._repository.get_by_numero(numero)
        if result is None:
            return ToolResultResponse.fail(f"Opération numéro {numero} non trouvée")
        return ToolResultResponse.ok(data=result, message=f"Opération {numero} trouvée")

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._repository.list(limit=params.get("limit", 20))
        total = self._repository.count()
        return ToolResultResponse.ok(
            data={"operations": results, "total": total, "count": len(results)},
            message=f"{total} opération(s) au total",
        )

    def _filter_by_status(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        statut = params.get("statut", "")
        if not statut:
            return ToolResultResponse.fail("Paramètre 'statut' requis")
        results = self._repository.filter_by_status(statut, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"operations": results, "count": len(results), "statut": statut},
            message=f"{len(results)} opération(s) en statut '{statut}'",
        )

    def _filter_by_waste_code(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        code = params.get("code_dechet", "")
        if not code:
            return ToolResultResponse.fail("Paramètre 'code_dechet' requis")
        results = self._repository.filter_by_waste_code(code, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"operations": results, "count": len(results), "code_dechet": code},
            message=f"{len(results)} opération(s) pour le code '{code}'",
        )

    def _filter_by_date_range(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        date_from = params.get("date_from", "")
        date_to = params.get("date_to", "")
        if not date_from or not date_to:
            return ToolResultResponse.fail("Paramètres 'date_from' et 'date_to' requis")
        results = self._repository.filter_by_date_range(date_from, date_to, limit=params.get("limit", 100))
        return ToolResultResponse.ok(
            data={"operations": results, "count": len(results), "date_from": date_from, "date_to": date_to},
            message=f"{len(results)} opération(s) du {date_from} au {date_to}",
        )

    def _sum_quantities(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        total = self._repository.sum_quantities(
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
        )
        return ToolResultResponse.ok(
            data={"total_quantity": total, "unit": "kg"},
            message=f"Total: {total} kg",
        )

    def _count_by_status(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        counts = self._repository.count_by_status()
        return ToolResultResponse.ok(
            data={"counts": counts},
            message=f"Répartition par statut: {counts}",
        )

    def _count_by_waste_class(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        counts = self._repository.count_by_waste_class()
        return ToolResultResponse.ok(
            data={"counts": counts},
            message=f"Répartition par classe: {counts}",
        )
