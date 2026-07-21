"""
Glossary Repository — unified access to glossary data.

Bridges two existing data sources without duplicating either:
  1. In-memory GLOSSAIRE (48 terms with scoring, abbreviations, bilingual defs)
  2. KnowledgeBase model (DB entries with categorie='GLOSSAIRE')

Tools NEVER import glossaire_data.py or Django models directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GlossaryRepository:
    """
    Unified glossary data access.

    search(query)         — scored full-text search across both sources
    get_definition(term)  — exact match lookup (in-memory primary, DB fallback)
    search_similar(term)  — related terms via abbreviation expansion + category
    list_categories()     — all glossary categories
    """

    def __init__(self) -> None:
        self._memory = None
        self._kb_repo = None

    @property
    def _glossaire(self):
        if self._memory is None:
            from apps.ai_assistant.glossaire_data import GLOSSAIRE
            self._memory = GLOSSAIRE
        return self._memory

    @property
    def _knowledge_repo(self):
        if self._kb_repo is None:
            from apps.ai_assistant.repositories.knowledge_repository import KnowledgeBaseRepository
            self._kb_repo = KnowledgeBaseRepository()
        return self._kb_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Scored search across in-memory glossary + DB KnowledgeBase."""
        results = self._search_memory(query, limit)
        db_results = self._search_database(query, limit)
        results.extend(db_results)
        results = self._deduplicate(results)
        return results[:limit]

    def get_definition(self, term: str) -> Optional[Dict[str, Any]]:
        """Exact match lookup. Returns single best match or None."""
        from apps.ai_assistant.glossaire_data import _normaliser
        term_norm = _normaliser(term)

        for entry in self._glossaire:
            if _normaliser(entry["terme_fr"]) == term_norm:
                return self._format_memory_entry(entry, score=10)

        for entry in self._glossaire:
            if term_norm in _normaliser(entry["terme_fr"]):
                return self._format_memory_entry(entry, score=8)

        db_results = self._search_database(term, limit=1)
        if db_results:
            return db_results[0]

        return None

    def search_similar(self, term: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find related terms via abbreviation expansion + category matching."""
        from apps.ai_assistant.glossaire_data import _normaliser, ABREVIATIONS
        term_norm = _normaliser(term)

        category = None
        for entry in self._glossaire:
            if _normaliser(entry["terme_fr"]) == term_norm:
                category = entry.get("categorie")
                break

        expanded_terms = set()
        for abbr, full in ABREVIATIONS.items():
            if abbr == term_norm or abbr in term_norm.split():
                expanded_terms.update(full.split())
            elif term_norm in full:
                expanded_terms.add(abbr)

        results = []
        seen = set()
        for entry in self._glossaire:
            entry_norm = _normaliser(entry["terme_fr"])
            if entry_norm == term_norm:
                continue

            score = 0
            if category and entry.get("categorie") == category:
                score += 4

            entry_words = set(entry_norm.split())
            if expanded_terms and entry_words & expanded_terms:
                score += 6
            elif expanded_terms and any(w in entry_norm for w in expanded_terms if len(w) >= 3):
                score += 3

            if score > 0 and entry_norm not in seen:
                seen.add(entry_norm)
                results.append((score, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [self._format_memory_entry(e, s) for s, e in results[:limit]]

    def list_categories(self) -> List[str]:
        """Return all distinct glossary categories."""
        cats = set()
        for entry in self._glossaire:
            cats.add(entry.get("categorie", "general"))
        return sorted(cats)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _search_memory(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Use the existing scoring engine from glossaire_data.py."""
        from apps.ai_assistant.glossaire_data import rechercher_glossaire
        raw = rechercher_glossaire(query)
        return [self._format_memory_entry(e, score=8 - i) for i, e in enumerate(raw[:limit])]

    def _search_database(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search KnowledgeBase glossary entries."""
        try:
            results = self._knowledge_repo.search(query, limit=limit)
            return [self._format_db_entry(r) for r in results]
        except Exception as exc:
            logger.warning("DB glossary search failed: %s", exc)
            return []

    def _format_memory_entry(self, entry: Dict[str, Any], score: int = 0) -> Dict[str, Any]:
        return {
            "source": "glossaire",
            "terme_fr": entry.get("terme_fr", ""),
            "terme_ar": entry.get("terme_ar", ""),
            "definition_fr": entry.get("definition_fr", ""),
            "definition_ar": entry.get("definition_ar", ""),
            "reference": entry.get("reference", ""),
            "categorie": entry.get("categorie", ""),
            "classe": entry.get("classe", ""),
            "score": score,
        }

    def _format_db_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "source": "knowledge_base",
            "terme_fr": entry.get("titre", ""),
            "terme_ar": "",
            "definition_fr": entry.get("contenu", ""),
            "definition_ar": "",
            "reference": entry.get("reference_reglementaire", ""),
            "categorie": entry.get("categorie", ""),
            "classe": "",
            "score": 5,
        }

    @staticmethod
    def _deduplicate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        result = []
        for item in items:
            key = item.get("terme_fr", "")
            if key and key not in seen:
                seen.add(key)
                result.append(item)
            elif not key:
                result.append(item)
        return result
