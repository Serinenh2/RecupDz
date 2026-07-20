"""
Vector Store — in-memory vector storage with cosine similarity search.

Uses numpy for fast vector operations. Persists to disk via JSON.
Supports add, search, delete, and bulk operations.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from apps.ai_assistant.rag.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Document Chunk
# ---------------------------------------------------------------------------

@dataclass
class DocumentChunk:
    """A chunk of text from a document, with metadata and embedding."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str = ""
    source: str = ""           # file path or "database"
    source_type: str = ""      # "pdf", "docx", "txt", "regulation", "waste_code", "procedure"
    chunk_index: int = 0       # position within the source document
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("embedding", None)
        return d


# ---------------------------------------------------------------------------
# Search Result
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result with score."""
    chunk: DocumentChunk
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "score": round(self.score, 4),
        }


# ---------------------------------------------------------------------------
# Vector Store
# ---------------------------------------------------------------------------

class VectorStore:
    """
    In-memory vector store with cosine similarity search.

    Usage:
        store = VectorStore()
        store.add(DocumentChunk(text="Loi 01-19 sur les déchets", source="regulation.pdf"))
        results = store.search("déchets dangereux", top_k=5)
    """

    def __init__(self, embedding_service: Optional[EmbeddingService] = None) -> None:
        self._embedding_service = embedding_service or EmbeddingService()
        self._chunks: Dict[str, DocumentChunk] = {}
        self._embeddings: Optional[np.ndarray] = None
        self._chunk_ids: List[str] = []
        self._dirty = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, chunk: DocumentChunk) -> str:
        """Add a single chunk to the store. Returns the chunk ID."""
        self._chunks[chunk.id] = chunk
        self._dirty = True
        return chunk.id

    def add_many(self, chunks: List[DocumentChunk]) -> int:
        """Add multiple chunks. Returns the number added."""
        for chunk in chunks:
            self._chunks[chunk.id] = chunk
        self._dirty = True
        return len(chunks)

    def remove(self, chunk_id: str) -> bool:
        """Remove a chunk by ID."""
        if chunk_id in self._chunks:
            del self._chunks[chunk_id]
            self._dirty = True
            return True
        return False

    def remove_by_source(self, source: str) -> int:
        """Remove all chunks from a specific source. Returns count removed."""
        to_remove = [cid for cid, c in self._chunks.items() if c.source == source]
        for cid in to_remove:
            del self._chunks[cid]
        if to_remove:
            self._dirty = True
        return len(to_remove)

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_type: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """
        Search for the most relevant chunks.

        Args:
            query: Search query text.
            top_k: Number of results to return.
            source_type: Filter by source type (e.g., "regulation", "waste_code").
            min_score: Minimum similarity score (0-1).

        Returns:
            List of SearchResult objects, sorted by score descending.
        """
        if not self._chunks:
            return []

        self._rebuild_index()

        # Encode query
        query_vec = self._embedding_service.encode_query(query)

        # Filter by source type if specified
        if source_type:
            filtered_ids = [
                cid for cid, c in self._chunks.items()
                if c.source_type == source_type
            ]
            if not filtered_ids:
                return []
            filtered_vectors = np.array([
                self._embeddings[self._chunk_ids.index(cid)]
                for cid in filtered_ids
            ])
            filtered_chunks = [self._chunks[cid] for cid in filtered_ids]
        else:
            filtered_vectors = self._embeddings
            filtered_chunks = [self._chunks[cid] for cid in self._chunk_ids]

        if filtered_vectors.shape[0] == 0:
            return []

        # Compute similarities
        similarities = self._embedding_service.similarity(query_vec, filtered_vectors)

        # Sort by score
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= min_score:
                results.append(SearchResult(
                    chunk=filtered_chunks[idx],
                    score=score,
                ))

        return results

    def get(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Get a chunk by ID."""
        return self._chunks.get(chunk_id)

    def get_by_source(self, source: str) -> List[DocumentChunk]:
        """Get all chunks from a specific source."""
        return [c for c in self._chunks.values() if c.source == source]

    def list_sources(self) -> Dict[str, int]:
        """List all sources and their chunk counts."""
        sources: Dict[str, int] = {}
        for chunk in self._chunks.values():
            key = f"{chunk.source_type}:{chunk.source}"
            sources[key] = sources.get(key, 0) + 1
        return sources

    def count(self) -> int:
        """Total number of chunks."""
        return len(self._chunks)

    def clear(self) -> None:
        """Remove all chunks."""
        self._chunks.clear()
        self._embeddings = None
        self._chunk_ids = []
        self._dirty = True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str) -> None:
        """Save the store to a directory."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        # Save chunks (without embeddings)
        chunks_data = []
        for chunk in self._chunks.values():
            d = chunk.to_dict()
            chunks_data.append(d)

        with open(path / "chunks.json", "w") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)

        # Save embeddings
        if self._embeddings is not None:
            np.save(str(path / "embeddings.npy"), self._embeddings)

        with open(path / "chunk_ids.json", "w") as f:
            json.dump(self._chunk_ids, f)

        # Save embedding service
        self._embedding_service.save(str(path / "embedding_service.json"))

        logger.info("VectorStore saved to %s (%d chunks)", directory, len(self._chunks))

    def load(self, directory: str) -> None:
        """Load the store from a directory."""
        path = Path(directory)

        # Load chunks
        with open(path / "chunks.json") as f:
            chunks_data = json.load(f)

        self._chunks = {}
        for d in chunks_data:
            chunk = DocumentChunk(**d)
            self._chunks[chunk.id] = chunk

        # Load embeddings
        emb_path = path / "embeddings.npy"
        if emb_path.exists():
            self._embeddings = np.load(str(emb_path))

        # Load chunk IDs
        ids_path = path / "chunk_ids.json"
        if ids_path.exists():
            with open(ids_path) as f:
                self._chunk_ids = json.load(f)

        # Load embedding service
        svc_path = path / "embedding_service.json"
        if svc_path.exists():
            self._embedding_service.load(str(svc_path))

        self._dirty = False
        logger.info("VectorStore loaded from %s (%d chunks)", directory, len(self._chunks))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild_index(self) -> None:
        """Rebuild the embedding index if dirty."""
        if not self._dirty and self._embeddings is not None:
            return

        if not self._chunks:
            self._embeddings = np.array([])
            self._chunk_ids = []
            return

        self._chunk_ids = list(self._chunks.keys())
        texts = [self._chunks[cid].text for cid in self._chunk_ids]

        # Fit and encode
        self._embedding_service.fit(texts)
        self._embeddings = self._embedding_service.encode_documents(texts)

        # Store embeddings in chunks
        for i, cid in enumerate(self._chunk_ids):
            self._chunks[cid].embedding = self._embeddings[i].tolist()

        self._dirty = False
        logger.debug("Index rebuilt: %d chunks, %d vocab", len(self._chunk_ids), self._embedding_service.vocab_size)
