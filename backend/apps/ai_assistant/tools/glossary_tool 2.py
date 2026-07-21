"""
GlossaryTool — glossary lookups for waste management terminology.

Actions: search, get_definition, search_similar

Bridges the existing glossaire_data.py (48 bilingual terms) and
KnowledgeBase model (categorie='GLOSSAIRE') without duplicating data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class GlossaryTool(BaseTool):
    """Tool for waste management glossary lookups."""

    name = "glossaire_tool"
    description = (
        "Consultation du glossaire bilingue (français/arabe) de la gestion des déchets. "
        "Recherche de termes techniques, définitions, abréviations (BSD, DSD, CET, etc.) "
        "et réglementations de référence (Loi 01-19, Décret 06-104)."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.glossary_repository import GlossaryRepository
            self._repo = GlossaryRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": (
                "Recherche scored d'un terme dans le glossaire. "
                "Gère les abréviations (BSD→bordereau de suivi), le français et l'arabe. "
                "Paramètre requis: query (str)"
            ),
            "get_definition": (
                "Obtenir la définition exacte d'un terme. "
                "Retourne la définition bilingue, la catégorie et la référence légale. "
                "Paramètre requis: term (str)"
            ),
            "search_similar": (
                "Trouver les termes liés (même catégorie ou abréviations proches). "
                "Paramètre requis: term (str)"
            ),
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "get_definition", "search_similar",
            ], description="Action à effectuer")
            .field("query", "str", required=False, description="Terme de recherche (pour action=search)")
            .field("term", "str", required=False, description="Terme exact (pour action=get_definition ou search_similar)")
            .field("limit", "int", required=False, default=5, min_value=1, max_value=20)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]
        handlers = {
            "search": self._search,
            "get_definition": self._get_definition,
            "search_similar": self._search_similar,
        }
        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")
        return handler(parameters, context)

    def _search(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        if not query:
            return ToolResultResponse.fail("Paramètre 'query' requis")
        results = self._repository.search(query, limit=params.get("limit", 5))
        if not results:
            return ToolResultResponse.ok(
                data={"results": [], "count": 0, "query": query},
                message=f"Aucun terme trouvé pour « {query} »",
            )
        return ToolResultResponse.ok(
            data={"results": results, "count": len(results), "query": query},
            message=f"{len(results)} terme(s) trouvé(s) pour « {query} »",
        )

    def _get_definition(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        term = params.get("term", "")
        if not term:
            return ToolResultResponse.fail("Paramètre 'term' requis")
        result = self._repository.get_definition(term)
        if result is None:
            return ToolResultResponse.fail(
                f"Aucune définition trouvée pour « {term} »"
            )
        return ToolResultResponse.ok(
            data=result,
            message=f"Définition de « {result.get('terme_fr', term)} »",
        )

    def _search_similar(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        term = params.get("term", "")
        if not term:
            return ToolResultResponse.fail("Paramètre 'term' requis")
        results = self._repository.search_similar(term, limit=params.get("limit", 5))
        if not results:
            return ToolResultResponse.ok(
                data={"results": [], "count": 0, "term": term},
                message=f"Aucun terme similaire à « {term} »",
            )
        return ToolResultResponse.ok(
            data={"results": results, "count": len(results), "term": term},
            message=f"{len(results)} terme(s) similaire(s) à « {term} »",
        )
