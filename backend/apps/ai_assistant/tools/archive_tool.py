"""
ArchiveTool — manages archived documents.

Actions: search, get, list, filter_by_categorie, get_recent
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class ArchiveTool(BaseTool):
    """Tool for archived document queries."""

    name = "archive_tool"
    description = (
        "Gestion des documents archivés. "
        "Permet de rechercher, consulter et filtrer les documents "
        "archivés par catégorie (agrément, contrat, rapport, etc.)."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.archive_repository import ArchiveRepository
            self._repo = ArchiveRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des documents par mot-clé. Paramètre requis: query (str)",
            "get": "Obtenir un document par son ID. Paramètre requis: document_id (int)",
            "list": "Lister tous les documents. Aucun paramètre requis",
            "filter_by_categorie": "Filtrer par catégorie. Paramètre requis: categorie (str parmi: AGREMENT, AUTORISATION, CONTRAT, RAPPORT, DECLARATION, CORRESPONDANCE, JURIDIQUE, TECHNIQUE, AUTRE)",
            "get_recent": "Obtenir les documents les plus récents. Aucun paramètre requis",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "get", "list", "filter_by_categorie", "get_recent",
            ], description="Action à effectuer")
            .field("query", "str", required=False, description="Terme de recherche (pour action=search)")
            .field("document_id", "int", required=False, description="ID du document (pour action=get)")
            .field("categorie", "str", required=False, enum=[
                "AGREMENT", "AUTORISATION", "CONTRAT", "RAPPORT",
                "DECLARATION", "CORRESPONDANCE", "JURIDIQUE", "TECHNIQUE", "AUTRE",
            ], description="Catégorie du document (pour action=filter_by_categorie)")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]
        handlers = {
            "search": self._search,
            "get": self._get,
            "list": self._list,
            "filter_by_categorie": self._filter_by_categorie,
            "get_recent": self._get_recent,
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
            data={"documents": results, "count": len(results)},
            message=f"{len(results)} document(s) trouvé(s)",
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        document_id = params.get("document_id")
        if not document_id:
            return ToolResultResponse.fail("Paramètre 'document_id' requis")
        result = self._repository.get(document_id)
        if result is None:
            return ToolResultResponse.fail(f"Document {document_id} non trouvé")
        return ToolResultResponse.ok(data=result, message="Document trouvé")

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._repository.list(limit=params.get("limit", 20))
        total = self._repository.count()
        return ToolResultResponse.ok(
            data={"documents": results, "total": total, "count": len(results)},
            message=f"{total} document(s) au total",
        )

    def _filter_by_categorie(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        categorie = params.get("categorie", "")
        if not categorie:
            return ToolResultResponse.fail("Paramètre 'categorie' requis")
        results = self._repository.filter_by_categorie(categorie, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"documents": results, "count": len(results), "categorie": categorie},
            message=f"{len(results)} document(s) en catégorie '{categorie}'",
        )

    def _get_recent(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        results = self._repository.get_recent(limit=params.get("limit", 10))
        return ToolResultResponse.ok(
            data={"documents": results, "count": len(results)},
            message=f"{len(results)} document(s) récent(s)",
        )
