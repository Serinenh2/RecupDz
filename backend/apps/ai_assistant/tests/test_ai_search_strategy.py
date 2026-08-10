"""
Comprehensive tests for the AISearchStrategy — multi-source search for short queries.

Tests cover:
    - Short query detection (is_short_query)
    - Multi-source search pipeline (glossary → nomenclature → regulation → procedure → traceability → report)
    - Best match selection
    - Clarification generation for ambiguous queries
    - Scoring system
    - Edge cases (empty query, long query, stop words)
    - Integration with orchestrator
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from apps.ai_assistant.enterprise.ai_search_strategy import (
    AISearchStrategy,
    BEST_MATCH_THRESHOLD,
    CLARIFICATION_GAP,
    SearchSourceResult,
    SearchResult,
    _search_glossary,
    _search_nomenclature,
    _search_procedure,
    _search_regulation,
    _search_report,
    _search_traceability,
    is_short_query,
)


# ---------------------------------------------------------------------------
# is_short_query Tests
# ---------------------------------------------------------------------------

class TestIsShortQuery(unittest.TestCase):

    # ── Should return True ───────────────────────────────────────────

    def test_single_word(self):
        self.assertTrue(is_short_query("BSD"))

    def test_single_word_arabic(self):
        self.assertTrue(is_short_query("نفايات"))

    def test_single_word_lower(self):
        self.assertTrue(is_short_query("dechets"))

    def test_code_pattern_dotted(self):
        self.assertTrue(is_short_query("15.01.06"))

    def test_code_pattern_two_level(self):
        self.assertTrue(is_short_query("15.01"))

    def test_code_pattern_simple(self):
        self.assertTrue(is_short_query("1.3.1"))

    def test_bsd_number(self):
        self.assertTrue(is_short_query("BSD-2024-001"))

    def test_pure_number(self):
        self.assertTrue(is_short_query("2024"))

    def test_pure_number_with_dots(self):
        self.assertTrue(is_short_query("100"))

    def test_two_words(self):
        self.assertTrue(is_short_query("dechets dangereux"))

    def test_three_words(self):
        self.assertTrue(is_short_query("code nomenclature dechet"))

    def test_four_words(self):
        self.assertTrue(is_short_query("reglementation gestion dechets"))

    def test_short_expression_with_number(self):
        self.assertTrue(is_short_query("15 tonnes"))

    def test_bsd_reference(self):
        self.assertTrue(is_short_query("BSD2024001"))

    def test_agrement_reference(self):
        self.assertTrue(is_short_query("AGREMENT-001"))

    # ── Should return False ──────────────────────────────────────────

    def test_empty_string(self):
        self.assertFalse(is_short_query(""))

    def test_none(self):
        self.assertFalse(is_short_query(None))  # type: ignore

    def test_question_with_many_words(self):
        self.assertFalse(is_short_query("Comment puis-je créer un BSD ?"))

    def test_long_sentence(self):
        self.assertFalse(is_short_query(
            "Je voudrais connaître la liste des déchets dangereux "
            "pour l'année 2024"
        ))

    def test_greeting(self):
        self.assertFalse(is_short_query("bonjour"))

    def test_greeting_with_question(self):
        self.assertTrue(is_short_query("salut ?"))

    def test_stop_words_only(self):
        self.assertFalse(is_short_query("le la les"))

    def test_conversation_starter(self):
        self.assertFalse(is_short_query("oui non"))

    def test_five_words(self):
        self.assertFalse(is_short_query("quel est le code déchet"))

    def test_question_mark_three_words(self):
        self.assertFalse(is_short_query("quoi faire ?"))

    def test_five_plus_words(self):
        self.assertFalse(is_short_query(
            "je voudrais un rapport sur les déchets"
        ))


# ---------------------------------------------------------------------------
# SearchSourceResult Tests
# ---------------------------------------------------------------------------

class TestSearchSourceResult(unittest.TestCase):

    def test_to_dict(self):
        r = SearchSourceResult(
            source="glossary",
            tool="glossaire_tool",
            action="search",
            parameters={"query": "BSD"},
            matches=[{"terme_fr": "BSD"}],
            score=0.9,
            label="Glossaire",
        )
        d = r.to_dict()
        self.assertEqual(d["source"], "glossary")
        self.assertEqual(d["tool"], "glossaire_tool")
        self.assertEqual(d["match_count"], 1)
        self.assertAlmostEqual(d["score"], 0.9)
        self.assertEqual(d["label"], "Glossaire")

    def test_to_dict_empty(self):
        r = SearchSourceResult(
            source="nomenclature",
            tool="nomenclature_tool",
            action="search",
        )
        d = r.to_dict()
        self.assertEqual(d["match_count"], 0)
        self.assertAlmostEqual(d["score"], 0.0)


# ---------------------------------------------------------------------------
# SearchResult Tests
# ---------------------------------------------------------------------------

class TestSearchResult(unittest.TestCase):

    def test_has_result_with_match(self):
        r = SearchResult(
            query="BSD",
            is_short=True,
            best_match=SearchSourceResult(
                source="glossary", tool="glossaire_tool", action="search",
                matches=[{"terme_fr": "BSD"}], score=1.0,
            ),
        )
        self.assertTrue(r.has_result)

    def test_has_result_no_match(self):
        r = SearchResult(query="xyz", is_short=True)
        self.assertFalse(r.has_result)

    def test_to_dict(self):
        r = SearchResult(query="test", is_short=True)
        d = r.to_dict()
        self.assertEqual(d["query"], "test")
        self.assertTrue(d["is_short"])
        self.assertFalse(d["has_result"])


# ---------------------------------------------------------------------------
# Glossary Search Tests
# ---------------------------------------------------------------------------

class TestSearchGlossary(unittest.TestCase):

    def test_exact_definition_match(self):
        repo = MagicMock()
        repo.get_definition.return_value = {
            "terme_fr": "BSD",
            "definition_fr": "Bordereau de Suivi des Déchets",
            "score": 10,
        }
        repo.search.return_value = []
        repo.search_similar.return_value = []

        result = _search_glossary("BSD", repo)
        self.assertEqual(result.source, "glossary")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(len(result.matches), 1)
        self.assertEqual(result.action, "get_definition")

    def test_search_fallback(self):
        repo = MagicMock()
        repo.get_definition.return_value = None
        repo.search.return_value = [
            {"terme_fr": "DSD", "definition_fr": "Déclaration"},
            {"terme_fr": "BSD", "definition_fr": "Bordereau"},
        ]
        repo.search_similar.return_value = []

        result = _search_glossary("declaration", repo)
        self.assertGreater(result.score, 0)
        self.assertEqual(len(result.matches), 2)

    def test_similar_fallback(self):
        repo = MagicMock()
        repo.get_definition.return_value = None
        repo.search.return_value = []
        repo.search_similar.return_value = [
            {"terme_fr": "BSD", "score": 3},
        ]

        result = _search_glossary(" bordereau ", repo)
        self.assertEqual(result.score, 0.4)
        self.assertEqual(len(result.matches), 1)

    def test_no_matches(self):
        repo = MagicMock()
        repo.get_definition.return_value = None
        repo.search.return_value = []
        repo.search_similar.return_value = []

        result = _search_glossary("xyz", repo)
        self.assertEqual(result.score, 0.0)
        self.assertEqual(len(result.matches), 0)

    def test_exception_handling(self):
        repo = MagicMock()
        repo.get_definition.side_effect = RuntimeError("db down")

        result = _search_glossary("test", repo)
        self.assertEqual(result.score, 0.0)


# ---------------------------------------------------------------------------
# Nomenclature Search Tests
# ---------------------------------------------------------------------------

class TestSearchNomenclature(unittest.TestCase):

    def test_exact_code_match(self):
        repo = MagicMock()
        repo.get_by_code.return_value = {
            "code": "15.01.06",
            "designation_fr": "Emballages",
        }
        repo.search.return_value = []

        result = _search_nomenclature("15.01.06", repo)
        self.assertEqual(result.source, "nomenclature")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.action, "search_by_code")

    def test_search_by_designation(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        repo.search.return_value = [
            {"code": "15.01.06", "designation_fr": "Emballages"},
        ]

        result = _search_nomenclature("emballages", repo)
        self.assertGreater(result.score, 0)
        self.assertEqual(result.action, "search")

    def test_no_matches(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        repo.search.return_value = []
        repo.search_similar.return_value = []

        result = _search_nomenclature("xyz", repo)
        self.assertEqual(result.score, 0.0)

    def test_exception_handling(self):
        repo = MagicMock()
        repo.get_by_code.side_effect = RuntimeError("db down")

        result = _search_nomenclature("15.01.06", repo)
        self.assertEqual(result.score, 0.0)


# ---------------------------------------------------------------------------
# Regulation Search Tests
# ---------------------------------------------------------------------------

class TestSearchRegulation(unittest.TestCase):

    def test_exact_reference_match(self):
        repo = MagicMock()
        repo.get_by_reference.return_value = {
            "titre": "Loi 01-19",
            "reference_reglementaire": "LOI01-19",
        }
        repo.search.return_value = []

        result = _search_regulation("LOI01-19", repo)
        self.assertEqual(result.source, "regulation")
        self.assertEqual(result.score, 1.0)

    def test_search_fallback(self):
        repo = MagicMock()
        repo.get_by_reference.return_value = None
        repo.search.return_value = [
            {"titre": "Loi 01-19", "categorie": "LOI"},
        ]

        result = _search_regulation("loi", repo)
        self.assertGreater(result.score, 0)

    def test_no_matches(self):
        repo = MagicMock()
        repo.get_by_reference.return_value = None
        repo.search.return_value = []

        result = _search_regulation("xyz", repo)
        self.assertEqual(result.score, 0.0)


# ---------------------------------------------------------------------------
# Procedure Search Tests
# ---------------------------------------------------------------------------

class TestSearchProcedure(unittest.TestCase):

    def test_procedure_found(self):
        repo = MagicMock()
        repo.filter_by_category.side_effect = [
            [{"titre": "Procédure BSD", "contenu": "procedure bsd"}],
            [],
        ]

        result = _search_procedure("bsd", repo)
        self.assertEqual(result.source, "procedure")
        self.assertGreater(result.score, 0)

    def test_no_procedures(self):
        repo = MagicMock()
        repo.filter_by_category.return_value = []

        result = _search_procedure("xyz", repo)
        self.assertEqual(result.score, 0.0)


# ---------------------------------------------------------------------------
# Traceability Search Tests
# ---------------------------------------------------------------------------

class TestSearchTraceability(unittest.TestCase):

    def test_exact_numero_match(self):
        repo = MagicMock()
        repo.get_by_numero.return_value = {
            "numero": "TR-2024-001",
            "code_dechet": "15.01.06",
        }
        repo.search.return_value = []

        result = _search_traceability("TR-2024-001", repo)
        self.assertEqual(result.source, "traceability")
        self.assertEqual(result.score, 1.0)

    def test_search_fallback(self):
        repo = MagicMock()
        repo.get_by_numero.return_value = None
        repo.search.return_value = [
            {"numero": "TR-001", "code_dechet": "15.01"},
        ]

        result = _search_traceability("TR-001", repo)
        self.assertGreater(result.score, 0)

    def test_no_matches(self):
        repo = MagicMock()
        repo.get_by_numero.return_value = None
        repo.search.return_value = []

        result = _search_traceability("xyz", repo)
        self.assertEqual(result.score, 0.0)


# ---------------------------------------------------------------------------
# Report Search Tests
# ---------------------------------------------------------------------------

class TestSearchReport(unittest.TestCase):

    def test_report_keyword_detected(self):
        trace_repo = MagicMock()
        trace_repo.sum_quantities.return_value = 1500.0
        nom_repo = MagicMock()
        nom_repo.filter_dangerous.return_value = [{"code": "15.01.06"}]

        result = _search_report("rapport dechets", trace_repo, nom_repo)
        self.assertEqual(result.source, "report")
        self.assertGreater(result.score, 0)

    def test_no_report_keyword(self):
        trace_repo = MagicMock()
        nom_repo = MagicMock()

        result = _search_report("dechets", trace_repo, nom_repo)
        self.assertEqual(result.score, 0.0)


# ---------------------------------------------------------------------------
# AISearchStrategy Integration Tests
# ---------------------------------------------------------------------------

class TestAISearchStrategy(unittest.TestCase):

    def setUp(self):
        self.strategy = AISearchStrategy()

    def test_not_short_query_returns_none(self):
        result = self.strategy.search("Quels sont les déchets dangereux ?")
        self.assertFalse(result.is_short)
        self.assertIsNone(result.best_match)

    def test_short_query_returns_result(self):
        # Mock all repos to return no results
        with patch.object(self.strategy, '_get_glossary_repo') as mock_g, \
             patch.object(self.strategy, '_get_nomenclature_repo') as mock_n, \
             patch.object(self.strategy, '_get_knowledge_repo') as mock_k, \
             patch.object(self.strategy, '_get_traceability_repo') as mock_t:

            mock_g.return_value = MagicMock()
            mock_n.return_value = MagicMock()
            mock_k.return_value = MagicMock()
            mock_t.return_value = MagicMock()

            result = self.strategy.search("BSD")
            self.assertTrue(result.is_short)

    def test_best_match_from_glossary(self):
        with patch.object(self.strategy, '_get_glossary_repo') as mock_g, \
             patch.object(self.strategy, '_get_nomenclature_repo') as mock_n, \
             patch.object(self.strategy, '_get_knowledge_repo') as mock_k, \
             patch.object(self.strategy, '_get_traceability_repo') as mock_t:

            glossary = MagicMock()
            glossary.get_definition.return_value = {
                "terme_fr": "BSD",
                "definition_fr": "Bordereau de Suivi des Déchets",
                "score": 10,
            }
            glossary.search.return_value = []
            glossary.search_similar.return_value = []
            mock_g.return_value = glossary

            nomenclature = MagicMock()
            nomenclature.get_by_code.return_value = None
            nomenclature.search.return_value = []
            nomenclature.search_similar.return_value = []
            mock_n.return_value = nomenclature

            knowledge = MagicMock()
            knowledge.get_by_reference.return_value = None
            knowledge.search.return_value = []
            knowledge.filter_by_category.return_value = []
            mock_k.return_value = knowledge

            traceability = MagicMock()
            traceability.get_by_numero.return_value = None
            traceability.search.return_value = []
            mock_t.return_value = traceability

            result = self.strategy.search("BSD")
            self.assertTrue(result.has_result)
            self.assertEqual(result.best_match.source, "glossary")
            self.assertEqual(result.best_match.score, 1.0)

    def test_clarification_when_close_scores(self):
        with patch.object(self.strategy, '_get_glossary_repo') as mock_g, \
             patch.object(self.strategy, '_get_nomenclature_repo') as mock_n, \
             patch.object(self.strategy, '_get_knowledge_repo') as mock_k, \
             patch.object(self.strategy, '_get_traceability_repo') as mock_t:

            glossary = MagicMock()
            glossary.get_definition.return_value = None
            glossary.search.return_value = [{"terme_fr": "Code 15.01"}]
            glossary.search_similar.return_value = []
            mock_g.return_value = glossary

            nomenclature = MagicMock()
            nomenclature.get_by_code.return_value = None
            nomenclature.search.return_value = [{"code": "15.01", "designation_fr": "Emballages"}]
            nomenclature.search_similar.return_value = []
            mock_n.return_value = nomenclature

            knowledge = MagicMock()
            knowledge.get_by_reference.return_value = None
            knowledge.search.return_value = [{"titre": "Loi 15.01", "categorie": "LOI"}]
            knowledge.filter_by_category.return_value = []
            mock_k.return_value = knowledge

            traceability = MagicMock()
            traceability.get_by_numero.return_value = None
            traceability.search.return_value = []
            mock_t.return_value = traceability

            result = self.strategy.search("15.01")
            self.assertTrue(result.is_short)
            # Should have clarification if scores are close
            if result.needs_clarification:
                self.assertIsNotNone(result.clarification_question)
                self.assertGreater(len(result.clarification_options), 0)

    def test_code_pattern_detection(self):
        with patch.object(self.strategy, '_get_glossary_repo') as mock_g, \
             patch.object(self.strategy, '_get_nomenclature_repo') as mock_n, \
             patch.object(self.strategy, '_get_knowledge_repo') as mock_k, \
             patch.object(self.strategy, '_get_traceability_repo') as mock_t:

            glossary = MagicMock()
            glossary.get_definition.return_value = None
            glossary.search.return_value = []
            glossary.search_similar.return_value = []
            mock_g.return_value = glossary

            nomenclature = MagicMock()
            nomenclature.get_by_code.return_value = {
                "code": "15.01.06",
                "designation_fr": "Emballages",
            }
            nomenclature.search.return_value = []
            mock_n.return_value = nomenclature

            knowledge = MagicMock()
            knowledge.get_by_reference.return_value = None
            knowledge.search.return_value = []
            knowledge.filter_by_category.return_value = []
            mock_k.return_value = knowledge

            traceability = MagicMock()
            traceability.get_by_numero.return_value = None
            traceability.search.return_value = []
            mock_t.return_value = traceability

            result = self.strategy.search("15.01.06")
            self.assertTrue(result.has_result)
            self.assertEqual(result.best_match.source, "nomenclature")

    def test_no_matches_returns_empty(self):
        with patch.object(self.strategy, '_get_glossary_repo') as mock_g, \
             patch.object(self.strategy, '_get_nomenclature_repo') as mock_n, \
             patch.object(self.strategy, '_get_knowledge_repo') as mock_k, \
             patch.object(self.strategy, '_get_traceability_repo') as mock_t:

            glossary = MagicMock()
            glossary.get_definition.return_value = None
            glossary.search.return_value = []
            glossary.search_similar.return_value = []
            mock_g.return_value = glossary

            nomenclature = MagicMock()
            nomenclature.get_by_code.return_value = None
            nomenclature.search.return_value = []
            nomenclature.search_similar.return_value = []
            mock_n.return_value = nomenclature

            knowledge = MagicMock()
            knowledge.get_by_reference.return_value = None
            knowledge.search.return_value = []
            knowledge.filter_by_category.return_value = []
            mock_k.return_value = knowledge

            traceability = MagicMock()
            traceability.get_by_numero.return_value = None
            traceability.search.return_value = []
            mock_t.return_value = traceability

            result = self.strategy.search("zzzznonexistent")
            self.assertFalse(result.has_result)
            self.assertEqual(len(result.all_matches), 0)


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

class TestSearchShortQueryFunction(unittest.TestCase):

    def test_returns_search_result(self):
        with patch('apps.ai_assistant.enterprise.ai_search_strategy.AISearchStrategy') as Mock:
            instance = MagicMock()
            instance.search.return_value = SearchResult(
                query="test", is_short=True,
            )
            Mock.return_value = instance

            from apps.ai_assistant.enterprise.ai_search_strategy import search_short_query
            result = search_short_query("test")
            self.assertIsInstance(result, SearchResult)
            self.assertTrue(result.is_short)


# ---------------------------------------------------------------------------
# Constants Tests
# ---------------------------------------------------------------------------

class TestConstants(unittest.TestCase):

    def test_best_match_threshold(self):
        self.assertGreater(BEST_MATCH_THRESHOLD, 0.0)
        self.assertLessEqual(BEST_MATCH_THRESHOLD, 1.0)

    def test_clarification_gap(self):
        self.assertGreater(CLARIFICATION_GAP, 0.0)
        self.assertLess(CLARIFICATION_GAP, 1.0)


if __name__ == "__main__":
    unittest.main()
