"""
CompanyTool — manages recuperateur companies.

Actions: search, list, get, get_full, by_status, by_wilaya
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class CompanyTool(BaseTool):
    """Tool for managing recuperateur companies."""

    name = "entreprise_tool"
    description = (
        "Recherche et consultation des recuperateurs (entreprises de recyclage). "
        "Permet de consulter les informationslegales, les agrements, "
        "et les specialisations d'un recuperateur."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None
        self._agrement_repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.recuperateur_repository import RecuperateurRepository
            self._repo = RecuperateurRepository()
        return self._repo

    @property
    def _agrement_repository(self):
        if self._agrement_repo is None:
            from apps.ai_assistant.repositories.recuperateur_repository import AgrementRepository
            self._agrement_repo = AgrementRepository()
        return self._agrement_repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des recuperateurs par mot-cle. Parametre requis: query (str)",
            "list": "Lister les recuperateurs avec filtres optionnels. Parametres optionnels: statut (str), wilaya (str), limit (int), offset (int)",
            "get": "Consulter les informations d'un recuperateur par son ID. Parametre requis: recuperateur_id (int)",
            "get_full": "Consulter un recuperateur avec ses agrements. Parametre requis: recuperateur_id (int)",
            "by_status": "Filtrer les recuperateurs par statut. Parametre requis: statut (str parmi: ACTIF, SUSPENDU, EXPIRE, ARCHIVE, EN_ATTENTE)",
            "by_wilaya": "Filtrer les recuperateurs par wilaya. Parametre requis: wilaya (str, ex: '16')",
            "agrements_expiring": "Lister les agrements proches de l'expiration. Parametre optionnel: days (int, defaut 60)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "list", "get", "get_full", "by_status",
                "by_wilaya", "agrements_expiring"
            ], description="Action a effectuer")
            .field("query", "str", required=False, description="Terme de recherche")
            .field("recuperateur_id", "int", required=False, description="ID du recuperateur")
            .field("numero_id", "str", required=False, description="Numero ID (REC-...)")
            .field("statut", "str", required=False, enum=[
                "ACTIF", "SUSPENDU", "EXPIRE", "ARCHIVE", "EN_ATTENTE"
            ], description="Statut du recuperateur")
            .field("wilaya", "str", required=False, description="Code wilaya")
            .field("days", "int", required=False, default=60, description="Jours pour expiration")
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
            "get_full": self._get_full,
            "by_status": self._by_status,
            "by_wilaya": self._by_wilaya,
            "agrements_expiring": self._agrements_expiring,
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
            data={"recuperateurs": results, "count": len(results)},
            message=f"{len(results)} recuperateur(s) trouve(s)"
        )

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        filters = {}
        if params.get("statut"):
            filters["statut"] = params["statut"]
        if params.get("wilaya"):
            filters["wilaya"] = params["wilaya"]

        results = self._repository.list(
            limit=params.get("limit", 20),
            offset=params.get("offset", 0),
            **filters
        )
        total = self._repository.count(**filters)
        return ToolResultResponse.ok(
            data={"recuperateurs": results, "total": total, "count": len(results)},
            message=f"{total} recuperateur(s) au total"
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Parametre 'recuperateur_id' requis")

        result = self._repository.get(recuperateur_id)
        if result is None:
            return ToolResultResponse.fail(f"Recuperateur {recuperateur_id} non trouve")
        return ToolResultResponse.ok(data=result, message="Recuperateur trouve")

    def _get_full(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Parametre 'recuperateur_id' requis")

        result = self._repository.get_with_agrements(recuperateur_id)
        if result is None:
            return ToolResultResponse.fail(f"Recuperateur {recuperateur_id} non trouve")
        return ToolResultResponse.ok(data=result, message="Recuperateur avec agrements")

    def _by_status(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        statut = params.get("statut", "")
        if not statut:
            return ToolResultResponse.fail("Parametre 'statut' requis")

        results = self._repository.filter_by_status(statut, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"recuperateurs": results, "statut": statut, "count": len(results)},
            message=f"{len(results)} recuperateur(s) avec statut {statut}"
        )

    def _by_wilaya(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        wilaya = params.get("wilaya", "")
        if not wilaya:
            return ToolResultResponse.fail("Parametre 'wilaya' requis")

        results = self._repository.filter_by_wilaya(wilaya, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"recuperateurs": results, "wilaya": wilaya, "count": len(results)},
            message=f"{len(results)} recuperateur(s) en wilaya {wilaya}"
        )

    def _agrements_expiring(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        days = params.get("days", 60)
        results = self._agrement_repository.filter_expiring_soon(days=days, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"agrements": results, "days": days, "count": len(results)},
            message=f"{len(results)} agrement(s) expirent dans {days} jours"
        )
