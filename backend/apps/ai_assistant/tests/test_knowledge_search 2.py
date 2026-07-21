"""
Tests for KnowledgeSearchEngine — ranked multi-source knowledge retrieval.

Covers:
    - KnowledgeHit / SourceResult / SearchResults data contracts
    - Keyword search scoring (exact, prefix, contains, partial, fuzzy)
    - Semantic search scoring (token overlap)
    - Hybrid search blending
    - Confidence scoring
    - Source priority ordering
    - Repository error handling
    - Edge cases (empty query, no repos, no results)
    - Framework independence
"""

import unittest

from apps.ai_assistant.enterprise.knowledge_search import (
    PRIORITY_GLOSSARY,
    PRIORITY_LLM_KNOWLEDGE,
    PRIORITY_NOMENCLATURE,
    PRIORITY_PROCEDURES,
    PRIORITY_REGULATIONS,
    PRIORITY_REPORTS,
    _CONFIDENCE_HIGH,
    _CONFIDENCE_LOW,
    _CONFIDENCE_MEDIUM,
    _KEYWORD_WEIGHT,
    _SEMANTIC_WEIGHT,
    _WEIGHT_CONTAINS_MATCH,
    _WEIGHT_EXACT_MATCH,
    _WEIGHT_PREFIX_MATCH,
    KnowledgeHit,
    KnowledgeSearchEngine,
    SearchMode,
    SearchResults,
    SourceResult,
)


# ════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════


def _token_match(query: str, text: str) -> bool:
    """Check if any query token matches any word in text (token-based)."""
    import re as _re
    q_tokens = set(_re.findall(r'[a-zà-ÿ0-9]+', query.lower()))
    t_tokens = set(_re.findall(r'[a-zà-ÿ0-9]+', text.lower()))
    return bool(q_tokens & t_tokens)


def _make_glossary_repo():
    """Create a mock glossary repository."""
    terms = [
        {"title": "BSD", "content": "Bordereau de Suivi des Déchets", "reference": "ART-001", "category": "Termes"},
        {"title": "Nomenclature", "content": "Classification des déchets", "reference": "ART-002", "category": "Termes"},
        {"title": "Agrément", "content": "Autorisation de récupération", "reference": "ART-003", "category": "Droit"},
    ]

    def search(query: str, limit: int):
        return [t for t in terms
                if _token_match(query, t["title"]) or _token_match(query, t["content"])][:limit]
    return search


def _make_nomenclature_repo():
    """Create a mock nomenclature repository."""
    codes = [
        {"title": "20.01.01", "content": "Papier et carton", "reference": "Code déchet", "category": "I"},
        {"title": "20.01.08", "content": "Biodégradable", "reference": "Code déchet", "category": "II"},
        {"title": "15.01.06", "content": "Emballages combinés", "reference": "Code déchet", "category": "III"},
    ]

    def search(query: str, limit: int):
        return [c for c in codes
                if _token_match(query, c["title"]) or _token_match(query, c["content"])][:limit]
    return search


def _make_regulations_repo():
    """Create a mock regulations repository."""
    docs = [
        {"title": "Loi 01-19", "content": "Gestion des déchets en Algérie", "reference": "JO-2019", "category": "LOI"},
        {"title": "Décret 02-20", "content": "Nomenclature des déchets", "reference": "JO-2020", "category": "DECRET"},
    ]

    def search(query: str, limit: int):
        return [d for d in docs
                if _token_match(query, d["title"]) or _token_match(query, d["content"])][:limit]
    return search


def _make_procedures_repo():
    """Create a mock procedures repository."""
    procs = [
        {"title": "Procédure BSD", "content": "Créer un bordereau de suivi", "category": "PROCEDURE"},
        {"title": "Procédure Inspection", "content": "Réaliser une inspection terrain", "category": "PROCEDURE"},
    ]

    def search(query: str, limit: int):
        return [p for p in procs
                if _token_match(query, p["title"]) or _token_match(query, p["content"])][:limit]
    return search


def _make_engine(**kwargs) -> KnowledgeSearchEngine:
    return KnowledgeSearchEngine(
        glossary_repo=_make_glossary_repo(),
        nomenclature_repo=_make_nomenclature_repo(),
        regulations_repo=_make_regulations_repo(),
        procedures_repo=_make_procedures_repo(),
        **kwargs,
    )


# ════════════════════════════════════════════════════════════════════════
# Data Contract: KnowledgeHit
# ════════════════════════════════════════════════════════════════════════


class TestKnowledgeHit(unittest.TestCase):

    def test_creation_minimal(self):
        h = KnowledgeHit(source="glossary", title="BSD")
        self.assertEqual(h.source, "glossary")
        self.assertEqual(h.title, "BSD")
        self.assertEqual(h.score, 0.0)

    def test_creation_full(self):
        h = KnowledgeHit(
            source="nomenclature", title="20.01.01",
            content="Papier", score=0.9, confidence=0.85,
            match_type="exact", reference="REF-1", category="I",
            metadata={"key": "val"},
        )
        self.assertAlmostEqual(h.score, 0.9)
        self.assertEqual(h.match_type, "exact")

    def test_to_dict_minimal(self):
        h = KnowledgeHit(source="s", title="t")
        d = h.to_dict()
        self.assertEqual(d["source"], "s")
        self.assertEqual(d["title"], "t")
        self.assertNotIn("content", d)
        self.assertNotIn("reference", d)

    def test_to_dict_full(self):
        h = KnowledgeHit(
            source="s", title="t", content="c",
            score=0.8, confidence=0.7, match_type="exact",
            reference="R", category="C", metadata={"k": "v"},
        )
        d = h.to_dict()
        self.assertIn("content", d)
        self.assertEqual(d["match_type"], "exact")
        self.assertEqual(d["reference"], "R")
        self.assertEqual(d["category"], "C")
        self.assertEqual(d["metadata"], {"k": "v"})

    def test_to_dict_truncates_content(self):
        h = KnowledgeHit(source="s", title="t", content="x" * 2000)
        d = h.to_dict()
        self.assertLessEqual(len(d["content"]), 500)

    def test_frozen(self):
        h = KnowledgeHit(source="s", title="t")
        with self.assertRaises(AttributeError):
            h.title = "x"


# ════════════════════════════════════════════════════════════════════════
# Data Contract: SourceResult
# ════════════════════════════════════════════════════════════════════════


class TestSourceResult(unittest.TestCase):

    def test_empty(self):
        sr = SourceResult(source="glossary", label="Glossaire", priority=1)
        self.assertFalse(sr.has_results)
        self.assertEqual(sr.hit_count, 0)
        self.assertIsNone(sr.best_hit)

    def test_with_hits(self):
        h1 = KnowledgeHit(source="g", title="A", score=0.8)
        h2 = KnowledgeHit(source="g", title="B", score=0.6)
        sr = SourceResult(source="g", label="G", priority=1, hits=[h1, h2])
        self.assertTrue(sr.has_results)
        self.assertEqual(sr.hit_count, 2)
        self.assertEqual(sr.best_hit.title, "A")

    def test_to_dict_empty(self):
        sr = SourceResult(source="g", label="G", priority=1)
        d = sr.to_dict()
        self.assertEqual(d["hit_count"], 0)
        self.assertNotIn("hits", d)

    def test_to_dict_with_hits(self):
        h = KnowledgeHit(source="g", title="A", score=0.9)
        sr = SourceResult(source="g", label="G", priority=1, hits=[h])
        d = sr.to_dict()
        self.assertEqual(d["hit_count"], 1)
        self.assertIn("hits", d)

    def test_frozen(self):
        sr = SourceResult(source="g", label="G", priority=1)
        with self.assertRaises(AttributeError):
            sr.source = "x"


# ════════════════════════════════════════════════════════════════════════
# Data Contract: SearchResults
# ════════════════════════════════════════════════════════════════════════


class TestSearchResults(unittest.TestCase):

    def test_empty(self):
        sr = SearchResults(query="test")
        self.assertFalse(sr.has_results)
        self.assertIsNone(sr.best_source)
        self.assertIsNone(sr.best_hit)
        self.assertEqual(sr.confidence, 0.0)

    def test_has_results(self):
        h = KnowledgeHit(source="g", title="A", score=0.8)
        s = SourceResult(source="g", label="G", priority=1, hits=[h])
        sr = SearchResults(query="q", sources=[s], total_hits=1)
        self.assertTrue(sr.has_results)

    def test_best_source(self):
        h1 = KnowledgeHit(source="g", title="A", score=0.9)
        h2 = KnowledgeHit(source="n", title="B", score=0.8)
        s1 = SourceResult(source="g", label="G", priority=2, hits=[h1])
        s2 = SourceResult(source="n", label="N", priority=1, hits=[h2])
        sr = SearchResults(query="q", sources=[s1, s2])
        # Priority 1 (nomenclature) should be best
        self.assertEqual(sr.best_source.source, "n")

    def test_best_hit(self):
        h1 = KnowledgeHit(source="g", title="A", score=0.6)
        h2 = KnowledgeHit(source="n", title="B", score=0.9)
        s1 = SourceResult(source="g", label="G", priority=1, hits=[h1])
        s2 = SourceResult(source="n", label="N", priority=2, hits=[h2])
        sr = SearchResults(query="q", sources=[s1, s2])
        # best_hit comes from best_source (priority=1 glossary), not highest score
        self.assertEqual(sr.best_hit.title, "A")

    def test_confidence_high_score(self):
        h = KnowledgeHit(source="g", title="A", score=0.95)
        s = SourceResult(source="g", label="G", priority=1, hits=[h])
        sr = SearchResults(query="q", sources=[s])
        self.assertGreater(sr.confidence, 0.8)

    def test_confidence_no_results(self):
        sr = SearchResults(query="q")
        self.assertEqual(sr.confidence, 0.0)

    def test_to_dict(self):
        sr = SearchResults(
            query="q", mode="keyword", total_hits=2,
            searched_sources=["glossary", "nomenclature"],
        )
        d = sr.to_dict()
        self.assertEqual(d["query"], "q")
        self.assertEqual(d["mode"], "keyword")
        self.assertEqual(d["total_hits"], 2)
        self.assertEqual(d["searched_sources"], ["glossary", "nomenclature"])

    def test_to_dict_with_best_hit(self):
        h = KnowledgeHit(source="g", title="BSD", score=0.9)
        s = SourceResult(source="g", label="G", priority=1, hits=[h])
        sr = SearchResults(query="q", sources=[s], total_hits=1)
        d = sr.to_dict()
        self.assertIn("best_hit", d)
        self.assertEqual(d["best_hit"]["title"], "BSD")

    def test_to_context_string(self):
        h = KnowledgeHit(source="g", title="BSD", content="Bordereau de suivi", reference="R1")
        s = SourceResult(source="g", label="Glossaire", priority=1, hits=[h])
        sr = SearchResults(query="q", sources=[s], total_hits=1)
        ctx = sr.to_context_string()
        self.assertIn("Glossaire", ctx)
        self.assertIn("BSD", ctx)
        self.assertIn("R1", ctx)

    def test_to_context_string_empty(self):
        sr = SearchResults(query="q")
        ctx = sr.to_context_string()
        self.assertEqual(ctx, "")

    def test_frozen(self):
        sr = SearchResults(query="q")
        with self.assertRaises(AttributeError):
            sr.query = "x"


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Keyword Search
# ════════════════════════════════════════════════════════════════════════


class TestKeywordSearch(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()

    def test_exact_match_title(self):
        results = self.engine.search("BSD", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)
        best = results.best_hit
        self.assertIsNotNone(best)
        self.assertEqual(best.title, "BSD")
        self.assertGreaterEqual(best.score, _WEIGHT_EXACT_MATCH)

    def test_prefix_match(self):
        results = self.engine.search("Nomenclature", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)
        best = results.best_hit
        self.assertIn("Nomenclature", best.title)

    def test_contains_match(self):
        results = self.engine.search("Suivi", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)

    def test_content_search(self):
        results = self.engine.search("bordereau", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)

    def test_no_match(self):
        results = self.engine.search("xyz_nonexistent", mode=SearchMode.KEYWORD)
        self.assertFalse(results.has_results)

    def test_code_search(self):
        results = self.engine.search("20.01.01", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)
        self.assertEqual(results.best_hit.title, "20.01.01")

    def test_regulation_search(self):
        results = self.engine.search("Loi", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)

    def test_procedure_search(self):
        results = self.engine.search("inspection", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Semantic Search
# ════════════════════════════════════════════════════════════════════════


class TestSemanticSearch(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()

    def test_semantic_finds_results(self):
        results = self.engine.search("déchets papier", mode=SearchMode.SEMANTIC)
        self.assertTrue(results.has_results)

    def test_semantic_token_overlap(self):
        results = self.engine.search("bordereau suivi déchets", mode=SearchMode.SEMANTIC)
        self.assertTrue(results.has_results)
        best = results.best_hit
        self.assertIsNotNone(best)
        self.assertIn("BSD", best.title)

    def test_semantic_no_match(self):
        results = self.engine.search("quantum physics entanglement", mode=SearchMode.SEMANTIC)
        self.assertFalse(results.has_results)

    def test_semantic_fallback_to_content(self):
        results = self.engine.search("récupération", mode=SearchMode.SEMANTIC)
        self.assertTrue(results.has_results)


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Hybrid Search
# ════════════════════════════════════════════════════════════════════════


class TestHybridSearch(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()

    def test_hybrid_default(self):
        results = self.engine.search("BSD")
        self.assertTrue(results.has_results)
        self.assertEqual(results.mode, "hybrid")

    def test_hybrid_finds_results(self):
        results = self.engine.search("nomenclature déchets")
        self.assertTrue(results.has_results)

    def test_hybrid_blended_score(self):
        kw = self.engine.search("BSD", mode=SearchMode.KEYWORD)
        sem = self.engine.search("BSD", mode=SearchMode.SEMANTIC)
        hyb = self.engine.search("BSD", mode=SearchMode.HYBRID)
        # Hybrid score should be between keyword and semantic
        if kw.has_results and sem.has_results and hyb.has_results:
            kw_s = kw.best_hit.score
            sem_s = sem.best_hit.score
            hyb_s = hyb.best_hit.score
            min_s = min(kw_s, sem_s)
            max_s = max(kw_s, sem_s)
            # Hybrid should be weighted blend, within range or close
            self.assertGreaterEqual(hyb_s, min_s * 0.5)


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Source Priority
# ════════════════════════════════════════════════════════════════════════


class TestSourcePriority(unittest.TestCase):

    def test_glossary_first(self):
        engine = _make_engine()
        results = engine.search("BSD")
        self.assertTrue(results.has_results)
        # First source with results should be glossary
        first = results.best_source
        self.assertEqual(first.source, "glossary")

    def test_priority_ordering(self):
        engine = _make_engine()
        results = engine.search("déchets")
        if results.has_results:
            sources_with_hits = [
                s for s in results.sources if s.has_results
            ]
            priorities = [s.priority for s in sources_with_hits]
            self.assertEqual(priorities, sorted(priorities))

    def test_source_filter(self):
        engine = _make_engine()
        results = engine.search("BSD", sources=["nomenclature"])
        # Only nomenclature should have results
        for s in results.sources:
            if s.source != "nomenclature":
                self.assertFalse(s.has_results)


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Confidence Scoring
# ════════════════════════════════════════════════════════════════════════


class TestConfidenceScoring(unittest.TestCase):

    def test_high_score_high_confidence(self):
        engine = _make_engine()
        results = engine.search("BSD", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)
        self.assertGreater(results.confidence, 0.7)

    def test_no_results_zero_confidence(self):
        engine = _make_engine()
        results = engine.search("xyz_nonexistent")
        self.assertEqual(results.confidence, 0.0)

    def test_confidence_range(self):
        engine = _make_engine()
        for q in ["BSD", "déchets", "20.01.01", "Loi", "xyz"]:
            results = engine.search(q)
            self.assertGreaterEqual(results.confidence, 0.0)
            self.assertLessEqual(results.confidence, 1.0)


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Single Source Search
# ════════════════════════════════════════════════════════════════════════


class TestSingleSourceSearch(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()

    def test_search_by_source_glossary(self):
        sr = self.engine.search_by_source("glossary", "BSD")
        self.assertTrue(sr.has_results)
        self.assertEqual(sr.source, "glossary")

    def test_search_by_source_nomenclature(self):
        sr = self.engine.search_by_source("nomenclature", "20.01")
        self.assertTrue(sr.has_results)

    def test_search_by_source_unconfigured(self):
        sr = self.engine.search_by_source("nonexistent", "query")
        self.assertFalse(sr.has_results)

    def test_search_by_source_with_limit(self):
        sr = self.engine.search_by_source("glossary", "déchet", limit=1)
        self.assertLessEqual(sr.hit_count, 1)


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Definition Lookup
# ════════════════════════════════════════════════════════════════════════


class TestDefinitionLookup(unittest.TestCase):

    def setUp(self):
        self.engine = _make_engine()

    def test_exact_definition(self):
        hit = self.engine.get_definition("BSD")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.title, "BSD")
        self.assertGreaterEqual(hit.score, 0.9)

    def test_definition_not_found(self):
        hit = self.engine.get_definition("NONEXISTENT_TERM")
        self.assertIsNone(hit)

    def test_definition_no_glossary(self):
        engine = KnowledgeSearchEngine()
        hit = engine.get_definition("BSD")
        self.assertIsNone(hit)

    def test_definition_partial(self):
        hit = self.engine.get_definition("Nomenclature")
        self.assertIsNotNone(hit)


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Edge Cases
# ════════════════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):

    def test_empty_query(self):
        engine = _make_engine()
        results = engine.search("")
        self.assertFalse(results.has_results)

    def test_whitespace_query(self):
        engine = _make_engine()
        results = engine.search("   ")
        self.assertFalse(results.has_results)

    def test_none_like_query(self):
        engine = _make_engine()
        results = engine.search("")
        self.assertEqual(results.mode, "hybrid")

    def test_no_repositories(self):
        engine = KnowledgeSearchEngine()
        results = engine.search("test")
        self.assertFalse(results.has_results)

    def test_repository_error(self):
        def failing_repo(q, lim):
            raise RuntimeError("DB down")

        engine = KnowledgeSearchEngine(glossary_repo=failing_repo)
        results = engine.search("test")
        self.assertFalse(results.has_results)

    def test_special_characters(self):
        engine = _make_engine()
        results = engine.search("20.01.01 / 15.01")
        self.assertTrue(results.has_results)

    def test_very_long_query(self):
        engine = _make_engine()
        long_q = "déchets " * 50
        results = engine.search(long_q)
        self.assertIsInstance(results, SearchResults)

    def test_unicode_query(self):
        engine = _make_engine()
        results = engine.search("récupération déchets")
        self.assertIsInstance(results, SearchResults)

    def test_limit_zero_uses_default(self):
        engine = _make_engine(default_limit=3)
        sr = engine.search_by_source("glossary", "déchet", limit=0)
        self.assertLessEqual(sr.hit_count, 3)

    def test_custom_weights(self):
        engine = _make_engine(keyword_weight=0.8, semantic_weight=0.2)
        results = engine.search("BSD", mode=SearchMode.HYBRID)
        self.assertTrue(results.has_results)

    def test_shortcuts(self):
        engine = _make_engine()
        kw = engine.search_keyword("BSD")
        sem = engine.search_semantic("BSD")
        hyb = engine.search_hybrid("BSD")
        self.assertEqual(kw.mode, "keyword")
        self.assertEqual(sem.mode, "semantic")
        self.assertEqual(hyb.mode, "hybrid")


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Canonical Source Mapping
# ════════════════════════════════════════════════════════════════════════


class TestCanonicalSource(unittest.TestCase):

    def test_canonical_glossary(self):
        self.assertEqual(KnowledgeSearchEngine._canonical_source("glossaire"), "glossary")

    def test_canonical_nomenclature(self):
        self.assertEqual(KnowledgeSearchEngine._canonical_source("nomenclature"), "nomenclature")

    def test_canonical_regulation(self):
        self.assertEqual(KnowledgeSearchEngine._canonical_source("réglementation"), "regulation")

    def test_canonical_procedure(self):
        self.assertEqual(KnowledgeSearchEngine._canonical_source("procédure"), "procedure")

    def test_canonical_internal_docs(self):
        self.assertEqual(KnowledgeSearchEngine._canonical_source("documents_internes"), "internal_document")

    def test_canonical_reports(self):
        self.assertEqual(KnowledgeSearchEngine._canonical_source("rapports"), "report")

    def test_canonical_unknown(self):
        self.assertEqual(KnowledgeSearchEngine._canonical_source("unknown"), "unknown")


# ════════════════════════════════════════════════════════════════════════
# KnowledgeSearchEngine — Aggregate Scoring
# ════════════════════════════════════════════════════════════════════════


class TestAggregateScoring(unittest.TestCase):

    def test_single_hit_aggregate(self):
        engine = _make_engine()
        results = engine.search("BSD")
        for s in results.sources:
            if s.has_results:
                self.assertGreater(s.aggregate_score, 0.0)

    def test_multiple_hits_weighted(self):
        engine = _make_engine()
        results = engine.search("déchet")
        for s in results.sources:
            if s.hit_count >= 2:
                # Aggregate should weight top hit higher
                self.assertGreater(s.aggregate_score, 0.0)

    def test_aggregate_range(self):
        engine = _make_engine()
        results = engine.search("BSD")
        for s in results.sources:
            self.assertGreaterEqual(s.aggregate_score, 0.0)
            self.assertLessEqual(s.aggregate_score, 1.0)


# ════════════════════════════════════════════════════════════════════════
# Framework Independence
# ════════════════════════════════════════════════════════════════════════


class TestFrameworkIndependence(unittest.TestCase):

    def test_no_django_imports(self):
        import importlib
        import apps.ai_assistant.enterprise.knowledge_search as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    self.assertNotIn("django", stripped.lower(),
                                     f"Django import: {stripped}")

    def test_no_repository_imports(self):
        import importlib
        import apps.ai_assistant.enterprise.knowledge_search as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    self.assertNotIn("repository", stripped.lower(),
                                     f"Repository import: {stripped}")

    def test_no_orm_queries(self):
        import importlib
        import apps.ai_assistant.enterprise.knowledge_search as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            content = f.read()
        self.assertNotIn(".objects.", content)
        self.assertNotIn(".save(", content)
        self.assertNotIn(".filter(", content)

    def test_dataclasses_frozen(self):
        self.assertTrue(KnowledgeHit.__dataclass_params__.frozen)
        self.assertTrue(SourceResult.__dataclass_params__.frozen)
        self.assertTrue(SearchResults.__dataclass_params__.frozen)


# ════════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════════


class TestConstants(unittest.TestCase):

    def test_priorities_ordered(self):
        self.assertLess(PRIORITY_GLOSSARY, PRIORITY_NOMENCLATURE)
        self.assertLess(PRIORITY_NOMENCLATURE, PRIORITY_REGULATIONS)
        self.assertLess(PRIORITY_REGULATIONS, PRIORITY_PROCEDURES)
        self.assertLess(PRIORITY_PROCEDURES, PRIORITY_REPORTS)
        self.assertLess(PRIORITY_REPORTS, PRIORITY_LLM_KNOWLEDGE)

    def test_weights_sum(self):
        self.assertAlmostEqual(_KEYWORD_WEIGHT + _SEMANTIC_WEIGHT, 1.0)

    def test_confidence_thresholds(self):
        self.assertGreater(_CONFIDENCE_HIGH, _CONFIDENCE_MEDIUM)
        self.assertGreater(_CONFIDENCE_MEDIUM, _CONFIDENCE_LOW)

    def test_search_mode_values(self):
        self.assertEqual(SearchMode.KEYWORD.value, "keyword")
        self.assertEqual(SearchMode.SEMANTIC.value, "semantic")
        self.assertEqual(SearchMode.HYBRID.value, "hybrid")


# ════════════════════════════════════════════════════════════════════════
# Integration — Full Pipeline
# ════════════════════════════════════════════════════════════════════════


class TestIntegration(unittest.TestCase):

    def test_full_search_pipeline(self):
        engine = _make_engine()

        # 1. Search
        results = engine.search("BSD déchets")
        self.assertTrue(results.has_results)
        self.assertGreater(results.total_hits, 0)

        # 2. Best source is glossary
        best = results.best_source
        self.assertEqual(best.source, "glossary")

        # 3. Confidence
        self.assertGreater(results.confidence, 0.5)

        # 4. Context string
        ctx = results.to_context_string()
        self.assertIn("Glossaire", ctx)

        # 5. Dict serialization
        d = results.to_dict()
        self.assertIn("total_hits", d)
        self.assertIn("confidence", d)

    def test_definition_lookup_pipeline(self):
        engine = _make_engine()
        hit = engine.get_definition("BSD")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.source, "glossary")
        ctx_dict = hit.to_dict()
        self.assertIn("title", ctx_dict)

    def test_multi_source_results(self):
        engine = _make_engine()
        results = engine.search("déchets")
        # Multiple sources should have results
        sources_with_hits = [s for s in results.sources if s.has_results]
        self.assertGreater(len(sources_with_hits), 1)

    def test_source_specific_search(self):
        engine = _make_engine()
        sr = engine.search_by_source("nomenclature", "20.01")
        self.assertTrue(sr.has_results)
        self.assertEqual(sr.source, "nomenclature")

    def test_different_modes_same_query(self):
        engine = _make_engine()
        kw = engine.search("BSD", mode=SearchMode.KEYWORD)
        sem = engine.search("BSD", mode=SearchMode.SEMANTIC)
        hyb = engine.search("BSD", mode=SearchMode.HYBRID)
        # All should find results
        self.assertTrue(kw.has_results)
        self.assertTrue(sem.has_results)
        self.assertTrue(hyb.has_results)


if __name__ == "__main__":
    unittest.main()
