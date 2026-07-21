"""
Unit Tests — Knowledge Adapters.

Tests adapter functions that bridge Django repositories to KnowledgeSearchEngine callables.
All Django imports are mocked — no database required.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from apps.ai_assistant.enterprise.knowledge_adapters import (
    make_glossary_adapter,
    make_nomenclature_adapter,
    make_regulations_adapter,
    make_procedures_adapter,
    make_internal_docs_adapter,
    make_reports_adapter,
)


# ══════════════════════════════════════════════════════════════════════
# Glossary Adapter
# ══════════════════════════════════════════════════════════════════════


class TestGlossaryAdapter(unittest.TestCase):

    @patch("apps.ai_assistant.repositories.glossary_repository.GlossaryRepository")
    def test_search_returns_formatted_results(self, MockRepo):
        mock_repo = MagicMock()
        mock_repo.search.return_value = [
            {
                "terme_fr": "BSD",
                "definition_fr": "Bordereau de Suivi des Déchets",
                "categorie": "terminologie",
                "score": 10,
            },
            {
                "terme_fr": "Nomenclature",
                "definition_fr": "Classification des déchets",
                "categorie": "classification",
                "score": 8,
            },
        ]
        MockRepo.return_value = mock_repo

        adapter = make_glossary_adapter()
        results = adapter("BSD", 5)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "BSD")
        self.assertEqual(results[0]["content"], "Bordereau de Suivi des Déchets")
        self.assertEqual(results[0]["reference"], "BSD")
        self.assertEqual(results[0]["category"], "terminologie")
        self.assertEqual(results[0]["metadata"]["source"], "glossary")

    @patch("apps.ai_assistant.repositories.glossary_repository.GlossaryRepository")
    def test_search_filters_empty_entries(self, MockRepo):
        mock_repo = MagicMock()
        mock_repo.search.return_value = [
            {"terme_fr": "", "definition_fr": "", "categorie": ""},
            {"terme_fr": "OK", "definition_fr": "Definition", "categorie": "cat"},
        ]
        MockRepo.return_value = mock_repo

        adapter = make_glossary_adapter()
        results = adapter("test", 5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "OK")

    def test_search_handles_exception(self):
        """When GlossaryRepository import fails, adapter returns empty list."""
        # The adapter catches all exceptions internally
        with patch(
            "apps.ai_assistant.repositories.glossary_repository.GlossaryRepository",
            side_effect=RuntimeError("DB down"),
        ):
            adapter = make_glossary_adapter()
            results = adapter("test", 5)
            self.assertEqual(results, [])

    @patch("apps.ai_assistant.repositories.glossary_repository.GlossaryRepository")
    def test_search_handles_empty_results(self, MockRepo):
        mock_repo = MagicMock()
        mock_repo.search.return_value = []
        MockRepo.return_value = mock_repo

        adapter = make_glossary_adapter()
        results = adapter("nonexistent", 5)

        self.assertEqual(results, [])


# ══════════════════════════════════════════════════════════════════════
# Nomenclature Adapter
# ══════════════════════════════════════════════════════════════════════


class TestNomenclatureAdapter(unittest.TestCase):

    @patch("apps.ai_assistant.repositories.nomenclature_repository.NomenclatureRepository")
    def test_search_returns_formatted_results(self, MockRepo):
        mock_repo = MagicMock()
        mock_repo.search.return_value = [
            {
                "code": "01.01.01",
                "designation_fr": "Papier et carton",
                "designation_ar": "ورق وكرتون",
            },
        ]
        MockRepo.return_value = mock_repo

        adapter = make_nomenclature_adapter()
        results = adapter("papier", 5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "01.01.01 — Papier et carton")
        self.assertEqual(results[0]["content"], "Papier et carton")
        self.assertEqual(results[0]["reference"], "01.01.01")
        self.assertEqual(results[0]["category"], "nomenclature")
        self.assertEqual(results[0]["metadata"]["code"], "01.01.01")

    def test_search_handles_exception(self):
        with patch(
            "apps.ai_assistant.repositories.nomenclature_repository.NomenclatureRepository",
            side_effect=RuntimeError("DB down"),
        ):
            adapter = make_nomenclature_adapter()
            results = adapter("test", 5)
            self.assertEqual(results, [])


# ══════════════════════════════════════════════════════════════════════
# Regulations Adapter
# ══════════════════════════════════════════════════════════════════════


class TestRegulationsAdapter(unittest.TestCase):

    @patch("apps.ai_assistant.repositories.knowledge_repository.KnowledgeBaseRepository")
    def test_search_returns_formatted_results(self, MockRepo):
        mock_repo = MagicMock()
        mock_repo.filter_by_category.side_effect = [
            [{"titre": "Loi 01-19", "contenu": "Loi relative à la gestion...", "reference_reglementaire": "Loi 01-19"}],
            [{"titre": "Décret 06-104", "contenu": "Décret portant...", "reference_reglementaire": "Décret 06-104"}],
            [],
        ]
        MockRepo.return_value = mock_repo

        adapter = make_regulations_adapter()
        results = adapter("loi", 9)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Loi 01-19")
        self.assertEqual(results[0]["category"], "loi")
        self.assertEqual(results[0]["metadata"]["source"], "regulation")

    def test_search_handles_exception(self):
        with patch(
            "apps.ai_assistant.repositories.knowledge_repository.KnowledgeBaseRepository",
            side_effect=RuntimeError("DB down"),
        ):
            adapter = make_regulations_adapter()
            results = adapter("test", 5)
            self.assertEqual(results, [])


# ══════════════════════════════════════════════════════════════════════
# Procedures Adapter
# ══════════════════════════════════════════════════════════════════════


class TestProceduresAdapter(unittest.TestCase):

    @patch("apps.ai_assistant.repositories.knowledge_repository.KnowledgeBaseRepository")
    def test_search_returns_formatted_results(self, MockRepo):
        mock_repo = MagicMock()
        mock_repo.filter_by_category.side_effect = [
            [{"titre": "Procédure BSD", "contenu": "Comment créer un BSD...", "reference_reglementaire": ""}],
            [],
        ]
        MockRepo.return_value = mock_repo

        adapter = make_procedures_adapter()
        results = adapter("bsd", 4)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Procédure BSD")
        self.assertEqual(results[0]["category"], "procedure")

    def test_search_handles_exception(self):
        with patch(
            "apps.ai_assistant.repositories.knowledge_repository.KnowledgeBaseRepository",
            side_effect=RuntimeError("DB down"),
        ):
            adapter = make_procedures_adapter()
            results = adapter("test", 5)
            self.assertEqual(results, [])


# ══════════════════════════════════════════════════════════════════════
# Internal Docs Adapter
# ══════════════════════════════════════════════════════════════════════


class TestInternalDocsAdapter(unittest.TestCase):

    @patch("apps.ai_assistant.repositories.knowledge_repository.KnowledgeBaseRepository")
    def test_search_returns_formatted_results(self, MockRepo):
        mock_repo = MagicMock()
        mock_repo.filter_by_category.side_effect = [
            [{"titre": "FAQ BSD", "contenu": "Questions fréquentes...", "reference_reglementaire": ""}],
            [],
            [],
            [],
        ]
        MockRepo.return_value = mock_repo

        adapter = make_internal_docs_adapter()
        results = adapter("faq", 8)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "FAQ BSD")
        self.assertEqual(results[0]["category"], "faq")

    def test_search_handles_exception(self):
        with patch(
            "apps.ai_assistant.repositories.knowledge_repository.KnowledgeBaseRepository",
            side_effect=RuntimeError("DB down"),
        ):
            adapter = make_internal_docs_adapter()
            results = adapter("test", 5)
            self.assertEqual(results, [])


# ══════════════════════════════════════════════════════════════════════
# Reports Adapter
# ══════════════════════════════════════════════════════════════════════


class TestReportsAdapter(unittest.TestCase):

    def test_returns_empty_list(self):
        adapter = make_reports_adapter()
        results = adapter("test", 5)
        self.assertEqual(results, [])


# ══════════════════════════════════════════════════════════════════════
# Adapter Callable Protocol
# ══════════════════════════════════════════════════════════════════════


class TestAdapterProtocol(unittest.TestCase):

    def test_all_adapters_are_callable(self):
        adapters = [
            make_glossary_adapter(),
            make_nomenclature_adapter(),
            make_regulations_adapter(),
            make_procedures_adapter(),
            make_internal_docs_adapter(),
            make_reports_adapter(),
        ]
        for adapter in adapters:
            self.assertTrue(callable(adapter))
            result = adapter("test", 5)
            self.assertIsInstance(result, list)

    def test_all_adapters_return_list_of_dicts(self):
        adapters = [
            make_glossary_adapter(),
            make_nomenclature_adapter(),
            make_regulations_adapter(),
            make_procedures_adapter(),
            make_internal_docs_adapter(),
            make_reports_adapter(),
        ]
        for adapter in adapters:
            result = adapter("nonexistent_query_xyz", 5)
            self.assertIsInstance(result, list)
            for item in result:
                self.assertIsInstance(item, dict)
                self.assertIn("title", item)
                self.assertIn("content", item)


if __name__ == "__main__":
    unittest.main()
