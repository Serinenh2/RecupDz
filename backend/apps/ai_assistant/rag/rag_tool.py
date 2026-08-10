"""
RAG Knowledge Tool — semantic search across company knowledge base.

Searches glossary, nomenclature, regulations, procedures, PDFs, and DOCX files.
Company knowledge is searched BEFORE model knowledge.

Actions: search, search_source, get_stats, index
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema

logger = logging.getLogger(__name__)


class RAGKnowledgeTool(BaseTool):
    """Tool for semantic search across the company knowledge base (RAG)."""

    name = "rag_knowledge_tool"
    description = (
        "Recherche semantique dans la base de connaissances entreprise: "
        "glossaire, nomenclature, reglementations, procedures internes, PDF, DOCX. "
        "La connaissance de l'entreprise est toujours recherchee en premier."
    )

    def __init__(self) -> None:
        super().__init__()
        self._search_engine = None

    @property
    def _engine(self):
        if self._search_engine is None:
            from apps.ai_assistant.rag.search_engine import SearchEngine
            self._search_engine = SearchEngine()
            self._search_engine.load()
        return self._search_engine

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "search": (
                "Recherche semantique dans toute la base de connaissances. "
                "Parametre requis: query (str). Retourne les fragments les plus pertinents."
            ),
            "search_source": (
                "Recherche dans une source specifique. "
                "Parametres requis: query (str), source_type (str parmi: glossary, waste_code, regulation, procedure, pdf, docx)"
            ),
            "get_stats": (
                "Obtenir les statistiques de l'index RAG: nombre de fragments, sources indexees."
            ),
            "index": (
                "Indexer ou re-indexer les sources de connaissances. "
                "Parametre optionnel: sources (list[str]) pour indexer des sources specifiques."
            ),
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "search", "search_source", "get_stats", "index",
            ], description="Action a effectuer")
            .field("query", "str", required=False,
                   description="Terme de recherche semantique (pour action=search ou search_source)")
            .field("source_type", "str", required=False, enum=[
                "glossary", "waste_code", "regulation", "procedure", "pdf", "docx",
            ], description="Type de source (pour action=search_source)")
            .field("top_k", "int", required=False, default=5, min_value=1, max_value=20,
                   description="Nombre max de resultats")
            .field("min_score", "float", required=False, default=0.1, min_value=0.0, max_value=1.0,
                   description="Score minimum de pertinence")
            .field("sources", "list", required=False,
                   description="Sources a indexer (pour action=index)")
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]
        handlers = {
            "search": self._search,
            "search_source": self._search_source,
            "get_stats": self._get_stats,
            "index": self._index,
        }
        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")
        return handler(parameters, context)

    def _search(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        if not query:
            return ToolResultResponse.fail("Parametre 'query' requis")

        top_k = params.get("top_k", 5)
        min_score = params.get("min_score", 0.1)

        result = self._engine.search(
            query=query,
            top_k=top_k,
            min_score=min_score,
        )

        if not result.has_results:
            return ToolResultResponse.ok(
                data={
                    "results": [],
                    "count": 0,
                    "query": query,
                    "context_text": "",
                    "sources_indexed": self._engine.stats().get("total_chunks", 0),
                },
                message=f"Aucune connaissance entreprise trouvee pour « {query} »",
            )

        results_data = []
        for chunk, score in zip(result.chunks, result.scores):
            results_data.append({
                "text": chunk.text[:500],
                "source": chunk.source,
                "source_type": chunk.source_type,
                "score": round(score, 4),
                "metadata": chunk.metadata,
            })

        return ToolResultResponse.ok(
            data={
                "results": results_data,
                "count": len(results_data),
                "query": query,
                "context_text": result.context_text,
                "sources_used": result.sources_used,
                "total_chunks_indexed": result.total_chunks,
            },
            message=f"{len(results_data)} fragment(s) pertinent(s) pour « {query} »",
        )

    def _search_source(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        query = params.get("query", "")
        source_type = params.get("source_type", "")
        if not query:
            return ToolResultResponse.fail("Parametre 'query' requis")
        if not source_type:
            return ToolResultResponse.fail("Parametre 'source_type' requis")

        top_k = params.get("top_k", 5)
        min_score = params.get("min_score", 0.1)

        result = self._engine.search(
            query=query,
            top_k=top_k,
            source_type=source_type,
            min_score=min_score,
        )

        if not result.has_results:
            return ToolResultResponse.ok(
                data={"results": [], "count": 0, "query": query, "source_type": source_type},
                message=f"Aucun resultat dans la source « {source_type} » pour « {query} »",
            )

        results_data = []
        for chunk, score in zip(result.chunks, result.scores):
            results_data.append({
                "text": chunk.text[:500],
                "source": chunk.source,
                "source_type": chunk.source_type,
                "score": round(score, 4),
                "metadata": chunk.metadata,
            })

        return ToolResultResponse.ok(
            data={
                "results": results_data,
                "count": len(results_data),
                "query": query,
                "source_type": source_type,
                "context_text": result.context_text,
            },
            message=f"{len(results_data)} fragment(s) dans « {source_type} » pour « {query} »",
        )

    def _get_stats(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        stats = self._engine.stats()
        return ToolResultResponse.ok(
            data=stats,
            message=f"Index: {stats.get('total_chunks', 0)} fragments",
        )

    def _index(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        sources = params.get("sources")
        count = self._engine.index_knowledge_base(sources=sources)
        stats = self._engine.stats()
        return ToolResultResponse.ok(
            data={
                "indexed_count": count,
                "total_chunks": stats.get("total_chunks", 0),
                "sources": stats.get("sources", {}),
            },
            message=f"{count} fragment(s) indexe(s)",
        )
