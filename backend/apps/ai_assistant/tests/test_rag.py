"""
Comprehensive tests for the RAG (Retrieval Augmented Generation) system.

Covers:
  - RAGConfig (defaults, env overrides)
  - EmbeddingService (tokenize, fit, encode, similarity)
  - VectorStore (add, search, remove, persistence)
  - DocumentLoader (text chunking, glossary loading, procedures loading)
  - Retriever (top-k, deduplication, context window)
  - SearchEngine (index, search, build_context)
  - RAGKnowledgeTool (search, search_source, get_stats, index)
  - Orchestrator RAG integration (company knowledge before model knowledge)
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from apps.ai_assistant.core.config import RAGConfig
from apps.ai_assistant.rag.document_loader import DocumentLoader, LoadedDocument, TextChunker
from apps.ai_assistant.rag.embedding_service import EmbeddingService, tokenize
from apps.ai_assistant.rag.retriever import Retriever, RetrievalResult
from apps.ai_assistant.rag.rag_tool import RAGKnowledgeTool
from apps.ai_assistant.rag.search_engine import SearchEngine
from apps.ai_assistant.rag.vector_store import DocumentChunk, SearchResult, VectorStore
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse


# =========================================================================
# RAGConfig
# =========================================================================


class TestRAGConfig(unittest.TestCase):
    """Tests for RAGConfig frozen dataclass."""

    def test_defaults(self):
        cfg = RAGConfig()
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.top_k, 5)
        self.assertAlmostEqual(cfg.min_score, 0.1)
        self.assertEqual(cfg.max_context_chars, 4000)
        self.assertEqual(cfg.chunk_size, 1000)
        self.assertEqual(cfg.chunk_overlap, 200)
        self.assertTrue(cfg.search_before_model)
        self.assertIn("glossary", cfg.sources)
        self.assertIn("nomenclature", cfg.sources)
        self.assertIn("regulations", cfg.sources)
        self.assertIn("procedures", cfg.sources)

    def test_frozen(self):
        cfg = RAGConfig()
        with self.assertRaises(AttributeError):
            cfg.enabled = False  # type: ignore

    def test_custom_values(self):
        cfg = RAGConfig(
            enabled=False,
            top_k=10,
            min_score=0.3,
            max_context_chars=8000,
            sources=["glossary"],
        )
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.top_k, 10)
        self.assertAlmostEqual(cfg.min_score, 0.3)
        self.assertEqual(cfg.max_context_chars, 8000)
        self.assertEqual(cfg.sources, ["glossary"])


# =========================================================================
# Tokenization
# =========================================================================


class TestTokenize(unittest.TestCase):
    """Tests for the tokenize function."""

    def test_basic_french(self):
        tokens = tokenize("Les déchets dangereux sont réglementés")
        self.assertIn("déchets", tokens)
        self.assertIn("dangereux", tokens)
        self.assertIn("réglementés", tokens)
        self.assertNotIn("les", tokens)
        self.assertNotIn("sont", tokens)

    def test_stop_words_removed(self):
        tokens = tokenize("le la les un une des du de")
        self.assertEqual(len(tokens), 0)

    def test_arabic(self):
        tokens = tokenize("إدارة النفايات الخطرة")
        self.assertTrue(len(tokens) > 0)

    def test_empty(self):
        tokens = tokenize("")
        self.assertEqual(tokens, [])

    def test_short_tokens_removed(self):
        tokens = tokenize("a b cd")
        self.assertNotIn("a", tokens)
        self.assertNotIn("b", tokens)
        self.assertIn("cd", tokens)


# =========================================================================
# EmbeddingService
# =========================================================================


class TestEmbeddingService(unittest.TestCase):
    """Tests for TF-IDF EmbeddingService."""

    def setUp(self):
        self.emb = EmbeddingService()

    def test_fit_builds_vocab(self):
        docs = ["déchets dangereux", "nomenclature des déchets", "réglementation"]
        self.emb.fit(docs)
        self.assertTrue(self.emb.is_fitted)
        self.assertGreater(self.emb.vocab_size, 0)

    def test_encode_documents(self):
        docs = ["déchets dangereux", "nomenclature des déchets"]
        self.emb.fit(docs)
        vectors = self.emb.encode_documents(docs)
        self.assertEqual(vectors.shape[0], 2)
        self.assertEqual(vectors.shape[1], self.emb.vocab_size)

    def test_encode_query(self):
        docs = ["déchets dangereux", "nomenclature"]
        self.emb.fit(docs)
        q_vec = self.emb.encode_query("déchets")
        self.assertEqual(q_vec.shape[0], self.emb.vocab_size)

    def test_similarity(self):
        docs = ["déchets dangereux", "nomenclature des déchets", "réglementation"]
        self.emb.fit(docs)
        doc_vecs = self.emb.encode_documents(docs)
        q_vec = self.emb.encode_query("déchets dangereux")
        sims = self.emb.similarity(q_vec, doc_vecs)
        self.assertEqual(len(sims), 3)
        # First doc should be most similar
        self.assertEqual(sims.argmax(), 0)

    def test_similarity_empty_docs(self):
        self.emb.fit(["test"])
        q_vec = self.emb.encode_query("test")
        empty = self.emb.encode_documents([])
        # Empty array with shape (0, vocab_size)
        import numpy as np
        empty = np.array([]).reshape(0, self.emb.vocab_size)
        sims = self.emb.similarity(q_vec, empty)
        self.assertEqual(len(sims), 0)

    def test_save_load(self):
        docs = ["déchets dangereux", "nomenclature"]
        self.emb.fit(docs)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "emb.json")
            self.emb.save(path)

            new_emb = EmbeddingService()
            new_emb.load(path)
            self.assertTrue(new_emb.is_fitted)
            self.assertEqual(new_emb.vocab_size, self.emb.vocab_size)


# =========================================================================
# DocumentChunk & SearchResult
# =========================================================================


class TestDocumentChunk(unittest.TestCase):
    """Tests for DocumentChunk dataclass."""

    def test_creation(self):
        chunk = DocumentChunk(text="test", source="file.pdf", source_type="pdf")
        self.assertEqual(chunk.text, "test")
        self.assertEqual(chunk.source, "file.pdf")
        self.assertEqual(chunk.source_type, "pdf")
        self.assertEqual(chunk.chunk_index, 0)
        self.assertEqual(len(chunk.id), 12)

    def test_to_dict_excludes_embedding(self):
        chunk = DocumentChunk(text="test", embedding=[0.1, 0.2])
        d = chunk.to_dict()
        self.assertNotIn("embedding", d)
        self.assertIn("text", d)

    def test_search_result_to_dict(self):
        chunk = DocumentChunk(text="test")
        result = SearchResult(chunk=chunk, score=0.85)
        d = result.to_dict()
        self.assertAlmostEqual(d["score"], 0.85)
        self.assertIn("chunk", d)


# =========================================================================
# VectorStore
# =========================================================================


class TestVectorStore(unittest.TestCase):
    """Tests for in-memory VectorStore."""

    def setUp(self):
        self.store = VectorStore()

    def test_add_and_count(self):
        chunk = DocumentChunk(text="déchets dangereux")
        chunk_id = self.store.add(chunk)
        self.assertEqual(self.store.count(), 1)
        self.assertIsNotNone(self.store.get(chunk_id))

    def test_add_many(self):
        chunks = [
            DocumentChunk(text=f"document {i}")
            for i in range(5)
        ]
        count = self.store.add_many(chunks)
        self.assertEqual(count, 5)
        self.assertEqual(self.store.count(), 5)

    def test_remove(self):
        chunk = DocumentChunk(text="test")
        chunk_id = self.store.add(chunk)
        self.assertTrue(self.store.remove(chunk_id))
        self.assertEqual(self.store.count(), 0)
        self.assertFalse(self.store.remove("nonexistent"))

    def test_remove_by_source(self):
        self.store.add(DocumentChunk(text="a", source="file1.pdf"))
        self.store.add(DocumentChunk(text="b", source="file1.pdf"))
        self.store.add(DocumentChunk(text="c", source="file2.pdf"))
        removed = self.store.remove_by_source("file1.pdf")
        self.assertEqual(removed, 2)
        self.assertEqual(self.store.count(), 1)

    def test_search(self):
        self.store.add(DocumentChunk(text="déchets dangereux"))
        self.store.add(DocumentChunk(text="nomenclature des déchets"))
        self.store.add(DocumentChunk(text="réglementation environnement"))

        results = self.store.search("déchets dangereux", top_k=2)
        self.assertLessEqual(len(results), 2)
        self.assertTrue(all(isinstance(r, SearchResult) for r in results))
        # Scores should be descending
        if len(results) > 1:
            self.assertGreaterEqual(results[0].score, results[1].score)

    def test_search_empty(self):
        results = self.store.search("test")
        self.assertEqual(len(results), 0)

    def test_search_by_source_type(self):
        self.store.add(DocumentChunk(text="test", source_type="regulation"))
        self.store.add(DocumentChunk(text="test2", source_type="waste_code"))
        results = self.store.search("test", source_type="regulation")
        self.assertTrue(all(r.chunk.source_type == "regulation" for r in results))

    def test_list_sources(self):
        self.store.add(DocumentChunk(text="a", source="f1.pdf", source_type="pdf"))
        self.store.add(DocumentChunk(text="b", source="f1.pdf", source_type="pdf"))
        self.store.add(DocumentChunk(text="c", source="f2.pdf", source_type="pdf"))
        sources = self.store.list_sources()
        self.assertEqual(sources["pdf:f1.pdf"], 2)
        self.assertEqual(sources["pdf:f2.pdf"], 1)

    def test_clear(self):
        self.store.add(DocumentChunk(text="test"))
        self.store.clear()
        self.assertEqual(self.store.count(), 0)

    def test_save_load(self):
        self.store.add(DocumentChunk(text="déchets dangereux"))
        self.store.add(DocumentChunk(text="nomenclature"))

        with tempfile.TemporaryDirectory() as tmpdir:
            self.store.save(tmpdir)
            new_store = VectorStore()
            new_store.load(tmpdir)
            self.assertEqual(new_store.count(), 2)


# =========================================================================
# TextChunker
# =========================================================================


class TestTextChunker(unittest.TestCase):
    """Tests for TextChunker."""

    def test_short_text_single_chunk(self):
        chunker = TextChunker(chunk_size=1000)
        chunks = chunker.chunk("Short text")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], "Short text")

    def test_long_text_multiple_chunks(self):
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "A" * 200
        chunks = chunker.chunk(text)
        self.assertGreater(len(chunks), 1)

    def test_empty_text(self):
        chunker = TextChunker()
        self.assertEqual(chunker.chunk(""), [])
        self.assertEqual(chunker.chunk("   "), [])

    def test_sentence_boundary(self):
        chunker = TextChunker(chunk_size=40, overlap=5)
        text = "First sentence here. Second sentence here. Third sentence here."
        chunks = chunker.chunk(text)
        # Should break at sentence boundaries when text exceeds chunk_size
        self.assertGreater(len(chunks), 1)


# =========================================================================
# DocumentLoader
# =========================================================================


class TestDocumentLoader(unittest.TestCase):
    """Tests for DocumentLoader."""

    def setUp(self):
        self.loader = DocumentLoader(chunk_size=500, chunk_overlap=100)

    def test_load_text_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Ceci est un test de document texte.")
            f.flush()
            path = f.name

        try:
            chunks = self.loader.load_file(path)
            self.assertGreater(len(chunks), 0)
            self.assertEqual(chunks[0].source_type, "txt")
        finally:
            os.unlink(path)

    def test_load_nonexistent_file(self):
        chunks = self.loader.load_file("/nonexistent/file.pdf")
        self.assertEqual(chunks, [])

    def test_load_unsupported_type(self):
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"test")
            f.flush()
            path = f.name
        try:
            chunks = self.loader.load_file(path)
            self.assertEqual(chunks, [])
        finally:
            os.unlink(path)

    def test_to_chunks(self):
        doc = LoadedDocument(text="Hello world", source="test", source_type="txt")
        chunks = self.loader._to_chunks(doc)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "Hello world")
        self.assertEqual(chunks[0].source, "test")

    def test_to_chunks_empty(self):
        doc = LoadedDocument(text="", source="test", source_type="txt")
        chunks = self.loader._to_chunks(doc)
        self.assertEqual(len(chunks), 0)

    def test_detect_type(self):
        self.assertEqual(self.loader._detect_type(".pdf"), "pdf")
        self.assertEqual(self.loader._detect_type(".docx"), "docx")
        self.assertEqual(self.loader._detect_type(".txt"), "txt")
        self.assertEqual(self.loader._detect_type(".md"), "txt")
        self.assertEqual(self.loader._detect_type(".xyz"), "unknown")

    def test_load_glossary(self):
        """Test glossary loading from glossaire_data.py."""
        chunks = self.loader.load_glossary(limit=5)
        # May be empty if glossaire_data.py not available, but should not crash
        self.assertIsInstance(chunks, list)

    def test_load_procedures_graceful(self):
        """Test procedures loading when archive model not available."""
        chunks = self.loader.load_procedures()
        self.assertIsInstance(chunks, list)

    def test_load_all_with_sources(self):
        """Test load_all with specific sources."""
        chunks = self.loader.load_all(sources=["glossary"])
        self.assertIsInstance(chunks, list)


# =========================================================================
# Retriever
# =========================================================================


class TestRetriever(unittest.TestCase):
    """Tests for Retriever."""

    def setUp(self):
        self.store = VectorStore()
        self.retriever = Retriever(self.store, top_k=3, min_score=0.0)

    def test_retrieve_empty(self):
        result = self.retriever.retrieve("test")
        self.assertIsInstance(result, RetrievalResult)
        self.assertFalse(result.has_results)
        self.assertEqual(len(result.chunks), 0)

    def test_retrieve_with_data(self):
        self.store.add(DocumentChunk(text="déchets dangereux", source="reg1", source_type="regulation"))
        self.store.add(DocumentChunk(text="nomenclature des codes", source="nom1", source_type="waste_code"))
        self.store.add(DocumentChunk(text="procédure d'inspection", source="proc1", source_type="procedure"))

        result = self.retriever.retrieve("déchets")
        self.assertTrue(result.has_results)
        self.assertGreater(len(result.chunks), 0)
        self.assertTrue(len(result.context_text) > 0)

    def test_retrieve_with_source_type(self):
        self.store.add(DocumentChunk(text="test", source_type="regulation"))
        self.store.add(DocumentChunk(text="test", source_type="waste_code"))

        result = self.retriever.retrieve("test", source_type="regulation")
        for chunk in result.chunks:
            self.assertEqual(chunk.source_type, "regulation")

    def test_retrieval_result_to_dict(self):
        result = RetrievalResult(
            chunks=[DocumentChunk(text="test")],
            scores=[0.5],
            query="test",
            total_chunks=10,
            sources_used=["file.pdf"],
        )
        d = result.to_dict()
        self.assertEqual(d["total_chunks"], 10)
        self.assertEqual(len(d["chunks"]), 1)
        self.assertEqual(d["sources_used"], ["file.pdf"])

    def test_retrieve_for_agent(self):
        self.store.add(DocumentChunk(text="code déchet 15.01.01", source_type="waste_code"))
        result = self.retriever.retrieve_for_agent("quel est le code déchet", intent="nomenclature")
        self.assertIsInstance(result, RetrievalResult)

    def test_context_window_limit(self):
        retriever = Retriever(self.store, max_context_chars=100)
        long_text = "A" * 200
        self.store.add(DocumentChunk(text=long_text, source="f1"))
        self.store.add(DocumentChunk(text="B" * 50, source="f2"))
        result = retriever.retrieve("test")
        total_chars = sum(len(c.text) for c in result.chunks)
        self.assertLessEqual(total_chars, 300)  # some tolerance for multiple chunks


# =========================================================================
# SearchEngine
# =========================================================================


class TestSearchEngine(unittest.TestCase):
    """Tests for SearchEngine."""

    def setUp(self):
        self.engine = SearchEngine()

    def test_index_chunks(self):
        chunks = [
            DocumentChunk(text="déchets dangereux", source="reg1", source_type="regulation"),
            DocumentChunk(text="nomenclature code 15.01", source="nom1", source_type="waste_code"),
        ]
        count = self.engine.index_chunks(chunks)
        self.assertEqual(count, 2)
        self.assertTrue(self.engine._indexed)

    def test_search(self):
        self.engine.index_chunks([
            DocumentChunk(text="déchets dangereux", source_type="regulation"),
            DocumentChunk(text="procédure interne", source_type="procedure"),
        ])
        result = self.engine.search("déchets")
        self.assertTrue(result.has_results)

    def test_search_for_agent(self):
        self.engine.index_chunks([
            DocumentChunk(text="code déchet 15.01.01", source_type="waste_code"),
        ])
        result = self.engine.search_for_agent("code déchet", intent="nomenclature")
        self.assertIsInstance(result, RetrievalResult)

    def test_build_context_with_results(self):
        self.engine.index_chunks([
            DocumentChunk(text="Loi 01-19 sur les déchets", source_type="regulation"),
        ])
        ctx = self.engine.build_context("quelle est la loi sur les déchets")
        self.assertIn("COMPANY KNOWLEDGE", ctx)
        self.assertIn("Loi 01-19", ctx)

    def test_build_context_no_results(self):
        ctx = self.engine.build_context("question obscure sans résultat")
        self.assertIn("No specific company knowledge", ctx)

    def test_build_context_with_system_prompt(self):
        self.engine.index_chunks([
            DocumentChunk(text="test content", source_type="regulation"),
        ])
        ctx = self.engine.build_context("test", system_prompt="Be concise.")
        self.assertIn("Be concise.", ctx)

    def test_stats_empty(self):
        stats = self.engine.stats()
        self.assertEqual(stats["total_chunks"], 0)
        self.assertFalse(stats["indexed"])

    def test_stats_after_index(self):
        self.engine.index_chunks([DocumentChunk(text="test", source="f1", source_type="pdf")])
        stats = self.engine.stats()
        self.assertEqual(stats["total_chunks"], 1)
        self.assertIn("pdf:f1", stats["sources"])

    def test_save_load(self):
        self.engine.index_chunks([
            DocumentChunk(text="déchets dangereux"),
            DocumentChunk(text="nomenclature"),
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            self.engine.save(tmpdir)
            new_engine = SearchEngine()
            success = new_engine.load(tmpdir)
            self.assertTrue(success)
            self.assertEqual(new_engine.stats()["total_chunks"], 2)

    def test_load_nonexistent(self):
        success = self.engine.load("/nonexistent/dir")
        self.assertFalse(success)


# =========================================================================
# RAGKnowledgeTool
# =========================================================================


class TestRAGKnowledgeTool(unittest.TestCase):
    """Tests for RAGKnowledgeTool."""

    def setUp(self):
        self.tool = RAGKnowledgeTool()
        self.ctx = ToolContext.create(user_id="u1", conversation_id="conv1")

    def test_name_and_description(self):
        self.assertEqual(self.tool.name, "rag_knowledge_tool")
        self.assertIn("glossaire", self.tool.description.lower())

    def test_action_descriptions(self):
        actions = self.tool.action_descriptions
        self.assertIn("search", actions)
        self.assertIn("search_source", actions)
        self.assertIn("get_stats", actions)
        self.assertIn("index", actions)

    def test_parameter_schema(self):
        schema = self.tool.parameter_schema
        field_names = [f.name for f in schema.fields]
        self.assertIn("action", field_names)
        self.assertIn("query", field_names)
        self.assertIn("source_type", field_names)
        self.assertIn("top_k", field_names)

    def test_search_no_query(self):
        result = self.tool.execute({"action": "search"}, self.ctx)
        self.assertFalse(result.success)
        self.assertIn("query", result.message.lower())

    def test_search_with_results(self):
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.has_results = True
        mock_result.chunks = [
            MagicMock(text="déchets dangereux", source="reg1", source_type="regulation", metadata={}),
        ]
        mock_result.scores = [0.85]
        mock_result.sources_used = ["reg1"]
        mock_result.total_chunks = 10
        mock_result.context_text = "=== Loi 01-19 ==="
        mock_engine.search.return_value = mock_result
        mock_engine.stats.return_value = {"total_chunks": 10, "sources": {}}

        self.tool._search_engine = mock_engine
        result = self.tool.execute(
            {"action": "search", "query": "déchets dangereux"},
            self.ctx,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["count"], 1)

    def test_search_no_results(self):
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.has_results = False
        mock_engine.search.return_value = mock_result
        mock_engine.stats.return_value = {"total_chunks": 10, "sources": {}}

        self.tool._search_engine = mock_engine
        result = self.tool.execute(
            {"action": "search", "query": "obscure query"},
            self.ctx,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["count"], 0)

    def test_search_source_no_query(self):
        result = self.tool.execute(
            {"action": "search_source", "source_type": "regulation"},
            self.ctx,
        )
        self.assertFalse(result.success)

    def test_search_source_no_source_type(self):
        result = self.tool.execute(
            {"action": "search_source", "query": "test"},
            self.ctx,
        )
        self.assertFalse(result.success)

    def test_get_stats(self):
        mock_engine = MagicMock()
        mock_engine.stats.return_value = {
            "total_chunks": 42,
            "sources": {"pdf:file.pdf": 10, "regulation:reg1": 32},
        }
        self.tool._search_engine = mock_engine
        result = self.tool.execute({"action": "get_stats"}, self.ctx)
        self.assertTrue(result.success)
        self.assertEqual(result.data["total_chunks"], 42)

    def test_index(self):
        mock_engine = MagicMock()
        mock_engine.index_knowledge_base.return_value = 25
        mock_engine.stats.return_value = {"total_chunks": 25, "sources": {}}
        self.tool._search_engine = mock_engine
        result = self.tool.execute({"action": "index"}, self.ctx)
        self.assertTrue(result.success)
        self.assertEqual(result.data["indexed_count"], 25)

    def test_unknown_action(self):
        result = self.tool.execute({"action": "unknown"}, self.ctx)
        self.assertFalse(result.success)


# =========================================================================
# Orchestrator RAG Integration
# =========================================================================


class TestOrchestratorRAGIntegration(unittest.TestCase):
    """Tests for RAG integration in the AgentOrchestrator."""

    def setUp(self):
        from apps.ai_assistant.infrastructure.audit.audit import AuditLogger
        from apps.ai_assistant.infrastructure.caching.cache import CacheManager, InMemoryCache
        from apps.ai_assistant.infrastructure.metrics.collector import MetricsCollector
        from apps.ai_assistant.infrastructure.monitoring.health import HealthCheck
        from apps.ai_assistant.infrastructure.tracing.tracer import Tracer

        class _MockContainer:
            def __init__(self):
                self.cache = CacheManager(
                    backend=InMemoryCache(max_size=100, default_ttl=60.0),
                    prefix="test", default_ttl=60.0,
                )
                self.metrics = MetricsCollector(namespace="test")
                self.tracer = Tracer(service_name="test")
                self.audit = AuditLogger(max_events=1000)
                self.health = HealthCheck(version="test")
                self.ollama = MagicMock()
                self.ollama.is_available.return_value = True
                self.ollama.chat.side_effect = [
                    '{"tool_needed": false, "tool": "none"}',
                    "Réponse basée sur les connaissances.",
                    '[]',
                ]
                self.context_builder = MagicMock()
                from apps.ai_assistant.core.interfaces import Context, Message, Role
                self.context_builder.build.return_value = Context(
                    messages=[Message(role=Role.USER, content="test")],
                    user_id="u1", conversation_id="conv1",
                )
                self.executor = MagicMock()
                self.memory = MagicMock()
                self.memory.get_conversation_history.return_value = []
                self.memory.get_tracker_summary.return_value = None
                self.memory.long_term = False
                self.tool_registry = MagicMock()
                self.tool_registry.__iter__ = MagicMock(return_value=iter([]))
                # RAG
                self.search_engine = MagicMock()
                self.search_engine.stats.return_value = {"total_chunks": 5, "sources": {}}
                mock_result = MagicMock()
                mock_result.has_results = True
                mock_result.chunks = [
                    MagicMock(text="Loi 01-19 sur les déchets", source="reg1", source_type="regulation", metadata={}),
                ]
                mock_result.scores = [0.8]
                mock_result.sources_used = ["reg1"]
                mock_result.context_text = "Loi 01-19: Les déchets dangereux..."
                self.search_engine.search_for_agent.return_value = mock_result
                self.rag_config = MagicMock()
                self.rag_config.sources = ["glossary", "nomenclature", "regulations", "procedures"]

        self.container = _MockContainer()

    def test_rag_retrieves_knowledge(self):
        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(container=self.container)

        rag_context = orch._retrieve_knowledge(
            message="quelle est la loi sur les déchets",
            tool_name="none",
            hermes_up=True,
        )
        self.assertIn("COMPANY KNOWLEDGE", rag_context)
        self.assertIn("Loi 01-19", rag_context)
        self.container.search_engine.search_for_agent.assert_called_once()

    def test_rag_skips_greeting(self):
        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(container=self.container)

        rag_context = orch._retrieve_knowledge(
            message="bonjour",
            tool_name="greeting",
            hermes_up=True,
        )
        self.assertEqual(rag_context, "")
        self.container.search_engine.search_for_agent.assert_not_called()

    def test_rag_empty_index_triggers_autoindex(self):
        self.container.search_engine.stats.return_value = {"total_chunks": 0}
        self.container.search_engine.index_knowledge_base.return_value = 10
        self.container.search_engine.stats.side_effect = [
            {"total_chunks": 0},
            {"total_chunks": 10, "sources": {}},
        ]

        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(container=self.container)

        rag_context = orch._retrieve_knowledge(
            message="test", tool_name="none", hermes_up=True,
        )
        self.container.search_engine.index_knowledge_base.assert_called_once()

    def test_rag_no_results(self):
        mock_result = MagicMock()
        mock_result.has_results = False
        self.container.search_engine.search_for_agent.return_value = mock_result

        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(container=self.container)

        rag_context = orch._retrieve_knowledge(
            message="obscure query", tool_name="none", hermes_up=True,
        )
        self.assertEqual(rag_context, "")

    def test_rag_exception_returns_empty(self):
        self.container.search_engine.search_for_agent.side_effect = RuntimeError("fail")

        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(container=self.container)

        rag_context = orch._retrieve_knowledge(
            message="test", tool_name="none", hermes_up=True,
        )
        self.assertEqual(rag_context, "")

    def test_generate_response_includes_rag_context(self):
        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(container=self.container)

        response = orch._generate_response(
            message="quelle est la loi",
            tool_name="none",
            tool_result=None,
            context=MagicMock(),
            rag_context="=== COMPANY KNOWLEDGE ===\nLoi 01-19",
            hermes_up=True,
        )
        # The rag_context should be appended to the system prompt
        call_args = self.container.ollama.chat.call_args
        system_prompt = call_args.kwargs.get("system_prompt", call_args[1].get("system_prompt", ""))
        self.assertIn("Loi 01-19", system_prompt)
        self.assertIn("COMPANY KNOWLEDGE", system_prompt)

    def test_generate_response_hermes_down_with_rag(self):
        self.container.ollama.is_available.return_value = False

        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(container=self.container)

        response = orch._generate_response(
            message="test",
            tool_name="none",
            tool_result=None,
            context=MagicMock(),
            rag_context="=== COMPANY KNOWLEDGE ===\nSome knowledge",
            hermes_up=False,
        )
        self.assertIn("base de connaissances", response.lower())

    def test_format_rag_fallback(self):
        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(container=self.container)

        result = orch._format_rag_fallback("=== COMPANY KNOWLEDGE ===\nLoi 01-19")
        self.assertIn("base de connaissances", result.lower())
        self.assertIn("Loi 01-19", result)


# =========================================================================
# Integration: Full RAG Pipeline
# =========================================================================


class TestRAGPipelineIntegration(unittest.TestCase):
    """Integration test: DocumentLoader → VectorStore → Retriever → SearchEngine."""

    def test_full_pipeline(self):
        # 1. Create chunks manually
        chunks = [
            DocumentChunk(
                text="Loi 01-19 relative à la gestion des déchets. "
                     "Les producteurs de déchets dangereux doivent "
                     "établir un bordereau de suivi des déchets (BSD).",
                source="loi_01_19.pdf",
                source_type="regulation",
                metadata={"reference": "Loi 01-19"},
            ),
            DocumentChunk(
                text="Code nomenclature 15.01.06 - Déchets d'emballage. "
                     "Famille: Déchets d'emballage. "
                     "Classe: SD (Substances Dangereuses).",
                source="nomenclature_db",
                source_type="waste_code",
                metadata={"code": "15.01.06"},
            ),
            DocumentChunk(
                text="Procédure d'inspection des sites de traitement. "
                     "L'inspection comprend la vérification des registres, "
                     "la conformité des installations et les mesures de sécurité.",
                source="procedure_001.txt",
                source_type="procedure",
                metadata={"title": "Procédure d'inspection"},
            ),
            DocumentChunk(
                text="BSD signifie Bordereau de Suivi des Déchets. "
                     "Document obligatoire pour tout transport de déchets "
                     "dangereux. Référence: Décret 06-104.",
                source="glossaire",
                source_type="glossary",
                metadata={"terme_fr": "BSD"},
            ),
        ]

        # 2. Index into VectorStore
        store = VectorStore()
        store.add_many(chunks)
        self.assertEqual(store.count(), 4)

        # 3. Retrieve
        retriever = Retriever(store, top_k=3, min_score=0.0)
        result = retriever.retrieve("qu'est-ce qu'un BSD ?")
        self.assertTrue(result.has_results)
        self.assertGreater(len(result.chunks), 0)

        # 4. Build context
        engine = SearchEngine()
        engine.index_chunks(chunks)
        ctx = engine.build_context("qu'est-ce qu'un BSD ?")
        self.assertIn("COMPANY KNOWLEDGE", ctx)

        # 5. Stats
        stats = engine.stats()
        self.assertEqual(stats["total_chunks"], 4)
        self.assertGreater(len(stats["sources"]), 0)


if __name__ == "__main__":
    unittest.main()
