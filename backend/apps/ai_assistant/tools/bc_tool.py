"""
BCTool — manages Bons de Commande (purchase orders, proformas, invoices).

Actions: search, get, get_by_numero, list, filter_by_type, filter_by_status, filter_by_recuperateur
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class BCTool(BaseTool):
    """Tool for purchase order (Bon de Commande) queries."""

    name = "bc_tool"
    description = (
        "Gestion des Bons de Commande (BC), proformas et factures. "
        "Permet de consulter, rechercher et filtrer les documents "
        "commerciaux liés aux récupérateurs."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.bc_repository import BonCommandeRepository
            self._repo = BonCommandeRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des BC par mot-clé. Paramètre requis: query (str)",
            "get": "Obtenir un BC par son ID. Paramètre requis: bc_id (int)",
            "get_by_numero": "Obtenir un BC par son numéro. Paramètre requis: numero (str)",
            "list": "Lister tous les BC. Aucun paramètre requis",
            "filter_by_type": "Filtrer par type document. Paramètre requis: type_document (str parmi: BC, PROFORMA, FACTURE)",
            "filter_by_status": "Filtrer par statut. Paramètre requis: statut (str parmi: BROUILLON, EMIS, VALIDE, ARCHIVE)",
            "filter_by_recuperateur": "Filtrer par récupérateur. Paramètre requis: recuperateur_id (int)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "get", "get_by_numero", "list",
                "filter_by_type", "filter_by_status", "filter_by_recuperateur",
            ], description="Action à effectuer")
            .field("query", "str", required=False, description="Terme de recherche (pour action=search)")
            .field("bc_id", "int", required=False, description="ID du BC (pour action=get)")
            .field("numero", "str", required=False, description="Numéro du BC (pour action=get_by_numero)")
            .field("type_document", "str", required=False, enum=["BC", "PROFORMA", "FACTURE"],
                   description="Type de document (pour action=filter_by_type)")
            .field("statut", "str", required=False, enum=["BROUILLON", "EMIS", "VALIDE", "ARCHIVE"],
                   description="Statut du BC (pour action=filter_by_status)")
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
            "filter_by_type": self._filter_by_type,
            "filter_by_status": self._filter_by_status,
            "filter_by_recuperateur": self._filter_by_recuperateur,
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
            data={"bons_de_commande": results, "count": len(results)},
            message=f"{len(results)} Bon(s) de commande trouvé(s)",
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        bc_id = params.get("bc_id")
        if not bc_id:
            return ToolResultResponse.fail("Paramètre 'bc_id' requis")
        result = self._repository.get(bc_id)
        if result is None:
            return ToolResultResponse.fail(f"BC {bc_id} non trouvé")
        return ToolResultResponse.ok(data=result, message="Bon de commande trouvé")

    def _get_by_numero(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        numero = params.get("numero", "")
        if not numero:
            return ToolResultResponse.fail("Paramètre 'numero' requis")
        result = self._repository.get_by_numero(numero)
        if result is None:
            return ToolResultResponse.fail(f"BC numéro {numero} non trouvé")
        return ToolResultResponse.ok(data=result, message=f"BC {numero} trouvé")

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._repository.list(limit=params.get("limit", 20))
        total = self._repository.count()
        return ToolResultResponse.ok(
            data={"bons_de_commande": results, "total": total, "count": len(results)},
            message=f"{total} Bon(s) de commande au total",
        )

    def _filter_by_type(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        type_doc = params.get("type_document", "")
        if not type_doc:
            return ToolResultResponse.fail("Paramètre 'type_document' requis")
        results = self._repository.filter_by_type(type_doc, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"bons_de_commande": results, "count": len(results), "type_document": type_doc},
            message=f"{len(results)} document(s) de type '{type_doc}'",
        )

    def _filter_by_status(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        statut = params.get("statut", "")
        if not statut:
            return ToolResultResponse.fail("Paramètre 'statut' requis")
        results = self._repository.filter_by_status(statut, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"bons_de_commande": results, "count": len(results), "statut": statut},
            message=f"{len(results)} BC en statut '{statut}'",
        )

    def _filter_by_recuperateur(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Paramètre 'recuperateur_id' requis")
        results = self._repository.filter_by_recuperateur(recuperateur_id, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"bons_de_commande": results, "count": len(results)},
            message=f"{len(results)} BC pour ce récupérateur",
        )
