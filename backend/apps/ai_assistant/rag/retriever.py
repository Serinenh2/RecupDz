"""
Retriever — retrieves relevant document chunks for a query.

Combines VectorStore search with metadata filtering and reranking.
Provides the bridge between the search engine and the LLM context builder.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apps.ai_assistant.rag.vector_store import DocumentChunk, SearchResult, VectorStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retrieval Result
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """Structured retrieval result with context."""
    chunks: List[DocumentChunk]
    scores: List[float]
    query: str
    total_chunks: int = 0
    sources_used: List[str] = field(default_factory=list)

    @property
    def context_text(self) -> str:
        """Combine all chunks into a single context string."""
        parts = []
        for i, chunk in enumerate(self.chunks):
            source_label = f"[Source: {chunk.source}]" if chunk.source else ""
            parts.append(f"--- Document {i+1} {source_label} ---\n{chunk.text}")
        return "\n\n".join(parts)

    @property
    def has_results(self) -> bool:
        return len(self.chunks) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunks": [c.to_dict() for c in self.chunks],
            "scores": [round(s, 4) for s in self.scores],
            "query": self.query,
            "total_chunks": self.total_chunks,
            "sources_used": self.sources_used,
        }


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class Retriever:
    """
    Retrieves relevant chunks from the VectorStore.

    Features:
        - Top-k retrieval
        - Source type filtering
        - Minimum score threshold
        - Context window (max total characters)
        - Source deduplication

    Usage:
        retriever = Retriever(vector_store)
        result = retriever.retrieve("quels sont les déchets dangereux ?")
        print(result.context_text)
    """

    def __init__(
        self,
        vector_store: VectorStore,
        top_k: int = 5,
        min_score: float = 0.1,
        max_context_chars: int = 4000,
    ) -> None:
        self._store = vector_store
        self._top_k = top_k
        self._min_score = min_score
        self._max_context_chars = max_context_chars

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        source_type: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> RetrievalResult:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: Search query.
            top_k: Override default top_k.
            source_type: Filter by source type.
            min_score: Override default min_score.

        Returns:
            RetrievalResult with chunks and scores.
        """
        k = top_k or self._top_k
        score = min_score if min_score is not None else self._min_score

        # Search
        results = self._store.search(
            query=query,
            top_k=k * 2,  # fetch more for deduplication
            source_type=source_type,
            min_score=score,
        )

        # Deduplicate by source (keep highest scoring chunk per source)
        deduplicated = self._deduplicate(results, max_per_source=2)

        # Trim to top_k
        final = deduplicated[:k]

        # Build result
        chunks = [r.chunk for r in final]
        scores = [r.score for r in final]

        # Fit within context window
        chunks, scores = self._fit_context_window(chunks, scores)

        sources_used = list(set(c.source for c in chunks if c.source))

        result = RetrievalResult(
            chunks=chunks,
            scores=scores,
            query=query,
            total_chunks=self._store.count(),
            sources_used=sources_used,
        )

        logger.info(
            "Retrieved %d chunks for '%s' (score >= %.2f, sources: %s)",
            len(chunks), query[:50], score, sources_used,
        )

        return result

    def retrieve_for_agent(
        self,
        query: str,
        intent: str = "",
    ) -> RetrievalResult:
        """
        Retrieve with intent-aware filtering.

        Maps intents to source types for more targeted retrieval.
        """
        # Map intent to source type
        intent_source_map = {
            "nomenclature": "waste_code",
            "waste_search": "waste_code",
            "regulation": "regulation",
        }

        source_type = intent_source_map.get(intent)
        return self.retrieve(query, source_type=source_type)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _deduplicate(
        self,
        results: List[SearchResult],
        max_per_source: int = 2,
    ) -> List[SearchResult]:
        """Keep at most max_per_source chunks per source."""
        source_counts: Dict[str, int] = {}
        deduplicated = []

        for result in results:
            source = result.chunk.source
            count = source_counts.get(source, 0)
            if count < max_per_source:
                deduplicated.append(result)
                source_counts[source] = count + 1

        return deduplicated

    def _fit_context_window(
        self,
        chunks: List[DocumentChunk],
        scores: List[float],
    ) -> tuple:
        """Trim chunks to fit within the max context character limit."""
        total_chars = 0
        final_chunks = []
        final_scores = []

        for chunk, score in zip(chunks, scores):
            chunk_chars = len(chunk.text)
            if total_chars + chunk_chars > self._max_context_chars:
                break
            final_chunks.append(chunk)
            final_scores.append(score)
            total_chars += chunk_chars

        return final_chunks, final_scores
