"""
BSDTool — manages Bordereau Suivi de Déchets (waste tracking sheets).

Actions: search, get, list, get_by_numero, filter_by_status, filter_by_recuperateur
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class BSDTool(BaseTool):
    """Tool for waste tracking document (BSD) queries."""

    name = "bsd_tool"
    description = (
        "Gestion des Bordereaux Suivi de Déchets (BSD). "
        "Permet de consulter, rechercher et filtrer les bordereaux "
        "de suivi des déchets dangereux."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.bsd_repository import BSDRepository
            self._repo = BSDRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des BSD par mot-clé. Paramètre requis: query (str)",
            "get": "Obtenir un BSD par son ID. Paramètre requis: bsd_id (int)",
            "get_by_numero": "Obtenir un BSD par son numéro. Paramètre requis: numero (str)",
            "list": "Lister tous les BSD. Aucun paramètre requis",
            "filter_by_status": "Filtrer par statut. Paramètre requis: statut (str parmi: BROUILLON, EMIS, EN_TRANSIT, RECEPTIONNE, SIGNE, ARCHIVE)",
            "filter_by_recuperateur": "Filtrer par récupérateur. Paramètre requis: recuperateur_id (int)",
            "count_by_status": "Compter les BSD par statut. Aucun paramètre requis",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "get", "get_by_numero", "list",
                "filter_by_status", "filter_by_recuperateur", "count_by_status",
            ], description="Action à effectuer")
            .field("query", "str", required=False, description="Terme de recherche (pour action=search)")
            .field("bsd_id", "int", required=False, description="ID du BSD (pour action=get)")
            .field("numero", "str", required=False, description="Numéro du BSD (pour action=get_by_numero)")
            .field("statut", "str", required=False, enum=[
                "BROUILLON", "EMIS", "EN_TRANSIT", "RECEPTIONNE", "SIGNE", "ARCHIVE",
            ], description="Statut du BSD (pour action=filter_by_status)")
            .field("recuperateur_id", "int", required=False, description="ID récupérateur (pour action=filter_by_recuperateur)")
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
            "filter_by_recuperateur": self._filter_by_recuperateur,
            "count_by_status": self._count_by_status,
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
            data={"bsd": results, "count": len(results)},
            message=f"{len(results)} BSD trouvé(s)",
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        bsd_id = params.get("bsd_id")
        if not bsd_id:
            return ToolResultResponse.fail("Paramètre 'bsd_id' requis")
        result = self._repository.get(bsd_id)
        if result is None:
            return ToolResultResponse.fail(f"BSD {bsd_id} non trouvé")
        return ToolResultResponse.ok(data=result, message="BSD trouvé")

    def _get_by_numero(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        numero = params.get("numero", "")
        if not numero:
            return ToolResultResponse.fail("Paramètre 'numero' requis")
        result = self._repository.get_by_numero(numero)
        if result is None:
            return ToolResultResponse.fail(f"BSD numéro {numero} non trouvé")
        return ToolResultResponse.ok(data=result, message=f"BSD {numero} trouvé")

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._repository.list(limit=params.get("limit", 20))
        total = self._repository.count()
        return ToolResultResponse.ok(
            data={"bsd": results, "total": total, "count": len(results)},
            message=f"{total} BSD au total",
        )

    def _filter_by_status(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        statut = params.get("statut", "")
        if not statut:
            return ToolResultResponse.fail("Paramètre 'statut' requis")
        results = self._repository.filter_by_status(statut, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"bsd": results, "count": len(results), "statut": statut},
            message=f"{len(results)} BSD en statut '{statut}'",
        )

    def _filter_by_recuperateur(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Paramètre 'recuperateur_id' requis")
        results = self._repository.filter_by_recuperateur(recuperateur_id, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"bsd": results, "count": len(results)},
            message=f"{len(results)} BSD pour ce récupérateur",
        )

    def _count_by_status(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        counts = self._repository.count_by_status()
        return ToolResultResponse.ok(
            data={"counts": counts},
            message=f"Répartition par statut: {counts}",
        )
