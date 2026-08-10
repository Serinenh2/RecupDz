"""
RAG Module — Retrieval Augmented Generation for RECUP-DZ.

Components:
    - EmbeddingService: TF-IDF + numpy vectorization
    - VectorStore: In-memory vector store with cosine similarity
    - DocumentLoader: PDF, DOCX, TXT, Markdown, glossary, procedures parsing
    - Retriever: Top-k chunk retrieval
    - SearchEngine: Orchestrates the full RAG pipeline
    - RAGKnowledgeTool: Semantic search tool for the AI agent

The assistant answers from company knowledge BEFORE general knowledge.
"""

from apps.ai_assistant.rag.embedding_service import EmbeddingService
from apps.ai_assistant.rag.vector_store import VectorStore, DocumentChunk
from apps.ai_assistant.rag.document_loader import DocumentLoader, LoadedDocument
from apps.ai_assistant.rag.retriever import Retriever
from apps.ai_assistant.rag.search_engine import SearchEngine
from apps.ai_assistant.rag.rag_tool import RAGKnowledgeTool

__all__ = [
    "EmbeddingService",
    "VectorStore",
    "DocumentChunk",
    "DocumentLoader",
    "LoadedDocument",
    "Retriever",
    "SearchEngine",
    "RAGKnowledgeTool",
]
