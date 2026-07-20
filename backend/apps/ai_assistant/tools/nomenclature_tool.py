"""
NomenclatureTool — hierarchical waste nomenclature code navigation.

Actions: search, search_by_code, search_similar, list_children
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class NomenclatureTool(BaseTool):
    """Tool for navigating the hierarchical waste nomenclature code tree."""

    name = "nomenclature_tool"
    description = (
        "Navigation hierarchique de la nomenclature des dechets. "
        "Permet de chercher des codes, explorer l'arbre de classification "
        "(famille > sous-famille > code), trouver des codes similaires, "
        "et lister les sous-codes d'un parent."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.nomenclature_repository import NomenclatureRepository
            self._repo = NomenclatureRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": "Rechercher des codes nomenclature par mot-cle ou par code partiel. Parametre requis: term (str)",
            "search_by_code": "Obtenir une nomenclature exacte par son code complet (ex: 15.01.06). Parametre requis: code (str)",
            "search_similar": "Trouver les codes de la meme famille que le code ou terme donne. Parametre requis: term (str)",
            "list_children": "Lister les sous-codes d'un parent (ex: 15.01 donne 15.01.01, 15.01.02...). Parametre requis: parent (str)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "search_by_code", "search_similar", "list_children",
            ], description="Action a effectuer")
            .field("term", "str", required=False,
                   description="Terme de recherche (pour action=search ou search_similar)")
            .field("code", "str", required=False,
                   description="Code nomenclature exact ex: 15.01.06 (pour action=search_by_code)")
            .field("parent", "str", required=False,
                   description="Code parent ex: 15.01 (pour action=list_children)")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100,
                   description="Nombre max de resultats")
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "search": self._search,
            "search_by_code": self._search_by_code,
            "search_similar": self._search_similar,
            "list_children": self._list_children,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _search(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        term = params.get("term", "")
        if not term:
            return ToolResultResponse.fail("Parametre 'term' requis")

        results = self._repository.search(term, limit=params.get("limit", 20))
        return ToolResultResponse.ok(
            data={"nomenclatures": results, "count": len(results), "query": term},
            message=f"{len(results)} code(s) trouve(s) pour '{term}'"
        )

    def _search_by_code(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        code = params.get("code", "")
        if not code:
            return ToolResultResponse.fail("Parametre 'code' requis")

        result = self._repository.get_by_code(code)
        if result is None:
            return ToolResultResponse.fail(
                f"Code '{code}' non trouve dans la nomenclature. "
                "Utilisez search pour une recherche par mot-cle."
            )

        parent_code = self._derive_parent(code)
        children = self._repository.list_children(code, limit=50)
        siblings = self._repository.search_similar(code, limit=5)

        return ToolResultResponse.ok(
            data={
                "nomenclature": result,
                "parent_code": parent_code,
                "children_count": len(children),
                "children": children[:20],
                "siblings": siblings,
            },
            message=f"Code {code} — {result.get('designation_fr', '')[:60]}"
        )

    def _search_similar(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        term = params.get("term", "")
        if not term:
            return ToolResultResponse.fail("Parametre 'term' requis")

        results = self._repository.search_similar(term, limit=params.get("limit", 20))
        return ToolResultResponse.ok(
            data={"nomenclatures": results, "count": len(results), "query": term},
            message=f"{len(results)} code(s) similaire(s) a '{term}'"
        )

    def _list_children(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        parent = params.get("parent", "")
        if not parent:
            return ToolResultResponse.fail("Parametre 'parent' requis")

        parent_code = parent.replace(" ", ".")
        parent_obj = self._repository.get_by_code(parent_code)
        children = self._repository.list_children(parent_code, limit=params.get("limit", 50))

        if not children and parent_obj is None:
            return ToolResultResponse.fail(
                f"Code parent '{parent}' non trouve. "
                "Verifiez le code et reessayez."
            )

        grandparent = self._derive_parent(parent_code) if parent_obj else None
        depth = parent_code.count(".") + 1

        return ToolResultResponse.ok(
            data={
                "parent_code": parent_code,
                "parent_designation": parent_obj.get("designation_fr", "") if parent_obj else "",
                "parent_classe": parent_obj.get("classe", "") if parent_obj else "",
                "grandparent_code": grandparent,
                "depth": depth,
                "children": children,
                "count": len(children),
            },
            message=f"{len(children)} sous-code(s) sous '{parent_code}'"
        )

    @staticmethod
    def _derive_parent(code: str) -> Optional[str]:
        """Derive the parent code by removing the last segment.

        "01.01.01" → "01.01"
        "01.01"    → "01"
        "01"       → None (top-level)
        """
        parts = code.rstrip(".").split(".")
        if len(parts) <= 1:
            return None
        return ".".join(parts[:-1])
