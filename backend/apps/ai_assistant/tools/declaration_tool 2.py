"""
DeclarationTool — manages waste declarations (DSD).

Actions: search, list, get, create, update, status
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class DeclarationTool(BaseTool):
    """Tool for managing declarations des dechets speciaux dangereux."""

    name = "declaration_tool"
    description = (
        "Recherche, consultation et gestion des declarations de dechets "
        "speciaux dangereux (DSD). Permet de lister, consulter, creer "
        "et modifier les declarations d'un recuperateur."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.declaration_repository import DeclarationRepository
            self._repo = DeclarationRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des declarations par mot-cle. Parametre requis: query (str)",
            "list": "Lister les declarations avec filtres optionnels. Parametres optionnels: recuperateur_id (int), annee (str), statut (str), limit (int), offset (int)",
            "get": "Consulter une declaration par son ID. Parametre requis: declaration_id (int)",
            "create": "Creer une nouvelle declaration. Parametre requis: data (dict) contenant les donnees de la declaration",
            "update": "Mettre a jour une declaration existante. Parametres requis: declaration_id (int), data (dict) contenant les champs a modifier",
            "status": "Obtenir le resume des statuts des declarations d'un recuperateur. Parametre requis: recuperateur_id (int)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "list", "get", "create", "update", "status"
            ], description="Action a effectuer")
            .field("query", "str", required=False, description="Terme de recherche")
            .field("declaration_id", "int", required=False, description="ID de la declaration")
            .field("recuperateur_id", "int", required=False, description="ID du recuperateur")
            .field("annee", "str", required=False, description="Annee (ex: 2024)")
            .field("statut", "str", required=False, enum=[
                "BROUILLON", "SOUMISE", "VALIDEE", "ARCHIVEE"
            ], description="Statut de la declaration")
            .field("data", "dict", required=False, description="Donnees pour creation/mise a jour")
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
            "create": self._create,
            "update": self._update,
            "status": self._status,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _search(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        if not query:
            return ToolResultResponse.fail("Parametre 'query' requis pour la recherche")

        results = self._repository.search(query, limit=params.get("limit", 20))
        return ToolResultResponse.ok(
            data={"declarations": results, "count": len(results)},
            message=f"{len(results)} declaration(s) trouvee(s)"
        )

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        filters = {}
        if params.get("recuperateur_id"):
            filters["recuperateur_id"] = params["recuperateur_id"]
        if params.get("annee"):
            filters["annee"] = params["annee"]
        if params.get("statut"):
            filters["statut"] = params["statut"]

        results = self._repository.list(
            limit=params.get("limit", 20),
            offset=params.get("offset", 0),
            **filters
        )
        total = self._repository.count(**filters)
        return ToolResultResponse.ok(
            data={"declarations": results, "total": total, "count": len(results)},
            message=f"{total} declaration(s) au total"
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        declaration_id = params.get("declaration_id")
        if not declaration_id:
            return ToolResultResponse.fail("Parametre 'declaration_id' requis")

        result = self._repository.get(declaration_id)
        if result is None:
            return ToolResultResponse.fail(f"Declaration {declaration_id} non trouvee")
        return ToolResultResponse.ok(data=result, message="Declaration trouvee")

    def _create(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        data = params.get("data", {})
        if not data:
            return ToolResultResponse.fail("Parametre 'data' requis pour la creation")

        if ctx.user_id:
            data.setdefault("created_by_id", ctx.user_id)

        result = self._repository.create(data)
        return ToolResultResponse.ok(data=result, message="Declaration creee avec succes")

    def _update(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        declaration_id = params.get("declaration_id")
        data = params.get("data", {})
        if not declaration_id:
            return ToolResultResponse.fail("Parametre 'declaration_id' requis")
        if not data:
            return ToolResultResponse.fail("Parametre 'data' requis pour la mise a jour")

        result = self._repository.update(declaration_id, data)
        if result is None:
            return ToolResultResponse.fail(f"Declaration {declaration_id} non trouvee")
        return ToolResultResponse.ok(data=result, message="Declaration mise a jour")

    def _status(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Parametre 'recuperateur_id' requis pour le statut")

        total = self._repository.count(recuperateur_id=recuperateur_id)
        by_status = {}
        for statut in ["BROUILLON", "SOUMISE", "VALIDEE", "ARCHIVEE"]:
            by_status[statut] = self._repository.count(recuperateur_id=recuperateur_id, statut=statut)

        return ToolResultResponse.ok(
            data={"total": total, "by_status": by_status},
            message=f"{total} declaration(s) pour ce recuperateur"
        )
