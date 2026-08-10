"""
RegulationTool — queries knowledge base and regulatory information.

Actions: search, get, by_category, by_reference, glossary
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class RegulationTool(BaseTool):
    """Tool for querying regulations, laws, and knowledge base."""

    name = "reglementation_tool"
    description = (
        "Consultation de la base de connaissances reglementaire : "
        "lois, decrets, referentiels, glossaire, FAQ, guides. "
        "Recherche par texte libre, categorie ou reference."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.knowledge_repository import KnowledgeBaseRepository
            self._repo = KnowledgeBaseRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher dans la base de connaissances reglementaire par mot-cle. Parametre requis: query (str)",
            "get": "Consulter une entree reglementaire par son ID. Parametre requis: entry_id (int)",
            "by_category": "Filtrer les articles par categorie reglementaire. Parametre requis: categorie (str parmi: LOI, DECRET, REFERENTIEL, GLOSSAIRE, FAQ, GUIDE, PROCEDURE, DECHETS_HOSPITALIERS, DECLARATION_TRIMESTRIELLE, AUTRE)",
            "by_reference": "Rechercher un article par sa reference reglementaire exacte. Parametre requis: reference (str)",
            "glossary": "Consulter le glossaire ou rechercher un terme. Parametre optionnel: query (str) pour filtrer par mot-cle",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "get", "by_category", "by_reference", "glossary"
            ], description="Action a effectuer")
            .field("query", "str", required=False, description="Terme de recherche")
            .field("entry_id", "int", required=False, description="ID de l'entree")
            .field("categorie", "str", required=False, enum=[
                "LOI", "DECRET", "REFERENTIEL", "GLOSSAIRE", "FAQ",
                "GUIDE", "PROCEDURE", "DECHETS_HOSPITALIERS",
                "DECLARATION_TRIMESTRIELLE", "AUTRE"
            ], description="Categorie de la connaissance")
            .field("reference", "str", required=False, description="Reference reglementaire exacte")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "search": self._search,
            "get": self._get,
            "by_category": self._by_category,
            "by_reference": self._by_reference,
            "glossary": self._glossary,
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
            data={"articles": results, "count": len(results)},
            message=f"{len(results)} article(s) trouve(s)"
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        entry_id = params.get("entry_id")
        if not entry_id:
            return ToolResultResponse.fail("Parametre 'entry_id' requis")

        result = self._repository.get(entry_id)
        if result is None:
            return ToolResultResponse.fail(f"Entree {entry_id} non trouvee")
        return ToolResultResponse.ok(data=result, message="Article trouve")

    def _by_category(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        categorie = params.get("categorie", "")
        if not categorie:
            return ToolResultResponse.fail("Parametre 'categorie' requis")

        results = self._repository.filter_by_category(categorie, limit=params.get("limit", 50))
        return ToolResultResponse.ok(
            data={"articles": results, "categorie": categorie, "count": len(results)},
            message=f"{len(results)} article(s) en categorie {categorie}"
        )

    def _by_reference(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        reference = params.get("reference", "")
        if not reference:
            return ToolResultResponse.fail("Parametre 'reference' requis")

        result = self._repository.get_by_reference(reference)
        if result is None:
            return ToolResultResponse.fail(f"Reference '{reference}' non trouvee")
        return ToolResultResponse.ok(data=result, message=f"Reference '{reference}' trouvee")

    def _glossary(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        if query:
            results = self._repository.search(query, limit=params.get("limit", 20))
        else:
            results = self._repository.filter_by_category("GLOSSAIRE", limit=params.get("limit", 50))

        return ToolResultResponse.ok(
            data={"glossary": results, "count": len(results)},
            message=f"{len(results)} terme(s) glossaire"
        )
