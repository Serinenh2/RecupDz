"""
Search Engine — orchestrates the full RAG pipeline.

Pipeline:
    1. Load documents (PDF, DOCX, regulations, waste codes)
    2. Index into VectorStore
    3. Retrieve relevant chunks for a query
    4. Build LLM context with company knowledge FIRST
    5. Fall back to general knowledge if no company results

The assistant MUST answer from company knowledge before general knowledge.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from apps.ai_assistant.rag.document_loader import DocumentLoader
from apps.ai_assistant.rag.embedding_service import EmbeddingService
from apps.ai_assistant.rag.retriever import RetrievalResult, Retriever
from apps.ai_assistant.rag.vector_store import DocumentChunk, VectorStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Search Engine
# ---------------------------------------------------------------------------

class SearchEngine:
    """
    RAG Search Engine — the single entry point for knowledge retrieval.

    Usage:
        engine = SearchEngine()
        engine.index_directory("/path/to/regulations/")
        engine.index_knowledge_base()  # from database

        result = engine.search("quels sont les déchets dangereux ?")
        print(result.context_text)
    """

    def __init__(
        self,
        persist_directory: str = "",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        top_k: int = 5,
        min_score: float = 0.1,
        max_context_chars: int = 4000,
    ) -> None:
        self._embedding_service = EmbeddingService()
        self._vector_store = VectorStore(self._embedding_service)
        self._document_loader = DocumentLoader(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._retriever = Retriever(
            self._vector_store,
            top_k=top_k,
            min_score=min_score,
            max_context_chars=max_context_chars,
        )
        self._persist_directory = persist_directory
        self._indexed = False

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_file(self, path: str) -> int:
        """Load and index a single file. Returns number of chunks added."""
        chunks = self._document_loader.load_file(path)
        if chunks:
            count = self._vector_store.add_many(chunks)
            self._indexed = True
            logger.info("Indexed %s: %d chunks", path, count)
            return count
        return 0

    def index_directory(self, directory: str) -> int:
        """Load and index all files from a directory. Returns total chunks."""
        chunks = self._document_loader.load_directory(directory)
        if chunks:
            count = self._vector_store.add_many(chunks)
            self._indexed = True
            logger.info("Indexed %s: %d chunks", directory, count)
            return count
        return 0

    def index_knowledge_base(self, sources: Optional[List[str]] = None) -> int:
        """Load and index all knowledge sources from the database.

        Args:
            sources: Which sources to load. None = all sources.
        """
        chunks = self._document_loader.load_all(sources=sources)
        if chunks:
            count = self._vector_store.add_many(chunks)
            self._indexed = True
            logger.info("Indexed knowledge base: %d chunks", count)
            return count
        return 0

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Index pre-made chunks directly."""
        if chunks:
            count = self._vector_store.add_many(chunks)
            self._indexed = True
            return count
        return 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_type: Optional[str] = None,
        min_score: float = 0.1,
    ) -> RetrievalResult:
        """
        Search for relevant chunks.

        Returns a RetrievalResult with chunks, scores, and context_text.
        """
        return self._retriever.retrieve(
            query=query,
            top_k=top_k,
            source_type=source_type,
            min_score=min_score,
        )

    def search_for_agent(
        self,
        query: str,
        intent: str = "",
    ) -> RetrievalResult:
        """Intent-aware search for the AI Agent."""
        return self._retriever.retrieve_for_agent(query, intent)

    def build_context(
        self,
        query: str,
        intent: str = "",
        system_prompt: str = "",
    ) -> str:
        """
        Build a complete context string for the LLM.

        Company knowledge comes FIRST. General knowledge is added as fallback.
        """
        result = self.search_for_agent(query, intent)

        parts = []

        # System prompt
        if system_prompt:
            parts.append(f"System Instructions:\n{system_prompt}")

        # Company knowledge (FIRST priority)
        if result.has_results:
            company_context = (
                "=== COMPANY KNOWLEDGE (RECUP-DZ) ===\n"
                "Use this information first. Only use general knowledge if "
                "the company knowledge doesn't answer the question.\n\n"
                f"{result.context_text}"
            )
            parts.append(company_context)
        else:
            parts.append(
                "=== COMPANY KNOWLEDGE ===\n"
                "No specific company knowledge found for this query. "
                "Use your general knowledge to answer, but note that "
                "the information may not reflect RECUP-DZ's specific procedures."
            )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: Optional[str] = None) -> None:
        """Save the index to disk."""
        dir_path = directory or self._persist_directory
        if not dir_path:
            logger.warning("No persist directory specified")
            return
        self._vector_store.save(dir_path)

    def load(self, directory: Optional[str] = None) -> bool:
        """Load the index from disk. Returns True if successful."""
        dir_path = directory or self._persist_directory
        if not dir_path:
            return False

        path = Path(dir_path)
        if not (path / "chunks.json").exists():
            logger.info("No saved index found at %s", dir_path)
            return False

        try:
            self._vector_store.load(dir_path)
            self._indexed = self._vector_store.count() > 0
            logger.info("Loaded index: %d chunks", self._vector_store.count())
            return True
        except Exception as exc:
            logger.error("Failed to load index: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_chunks": self._vector_store.count(),
            "sources": self._vector_store.list_sources(),
            "indexed": self._indexed,
        }
