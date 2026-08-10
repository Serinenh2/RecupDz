"""
Knowledge Adapters — bridge Django repositories to KnowledgeSearchEngine callables.

Each adapter is a callable with signature:
    (query: str, limit: int) -> List[Dict[str, Any]]

Returned dicts must contain at minimum: {"title": str, "content": str}
Optional keys: "reference", "category", "metadata"

All Django imports are lazy (inside the callable) to preserve Clean Architecture.
Repositories are instantiated on each call — stateless and thread-safe.

Usage in Container:
    from apps.ai_assistant.enterprise.knowledge_adapters import (
        make_glossary_adapter,
        make_nomenclature_adapter,
        ...
    )
    engine = KnowledgeSearchEngine(
        glossary_repo=make_glossary_adapter(),
        nomenclature_repo=make_nomenclature_adapter(),
    )
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

SourceRepository = Callable[[str, int], List[Dict[str, Any]]]


# ══════════════════════════════════════════════════════════════════════
# Adapter Factory Functions
# ══════════════════════════════════════════════════════════════════════


def make_glossary_adapter() -> SourceRepository:
    """Create an adapter that bridges GlossaryRepository to the search engine.

    GlossaryRepository.search() returns dicts with keys:
        terme_fr, definition_fr, categorie, score, etc.
    We map these to {title, content, reference, category}.
    """

    def _adapter(query: str, limit: int) -> List[Dict[str, Any]]:
        try:
            from apps.ai_assistant.repositories.glossary_repository import (
                GlossaryRepository,
            )
            repo = GlossaryRepository()
            raw = repo.search(query, limit=limit)
            results: List[Dict[str, Any]] = []
            for item in raw:
                terme = item.get("terme_fr", "")
                definition = item.get("definition_fr", "")
                if not terme and not definition:
                    continue
                results.append({
                    "title": terme,
                    "content": definition,
                    "reference": terme,
                    "category": item.get("categorie", "glossary"),
                    "metadata": {
                        "score": item.get("score", 0),
                        "source": "glossary",
                    },
                })
            return results
        except Exception as exc:
            logger.debug("Glossary adapter failed: %s", exc)
            return []

    return _adapter


def make_nomenclature_adapter() -> SourceRepository:
    """Create an adapter that bridges NomenclatureRepository.

    NomenclatureRepository.search() returns dicts with keys:
        code, designation_fr, designation_ar, etc.
    """

    def _adapter(query: str, limit: int) -> List[Dict[str, Any]]:
        try:
            from apps.ai_assistant.repositories.nomenclature_repository import (
                NomenclatureRepository,
            )
            repo = NomenclatureRepository()
            raw = repo.search(query, limit=limit)
            results: List[Dict[str, Any]] = []
            for item in raw:
                code = item.get("code", "")
                designation = item.get("designation_fr", "")
                if not code and not designation:
                    continue
                results.append({
                    "title": f"{code} — {designation}" if code else designation,
                    "content": designation,
                    "reference": code,
                    "category": "nomenclature",
                    "metadata": {
                        "code": code,
                        "source": "nomenclature",
                    },
                })
            return results
        except Exception as exc:
            logger.debug("Nomenclature adapter failed: %s", exc)
            return []

    return _adapter


def make_regulations_adapter() -> SourceRepository:
    """Create an adapter for regulations (KnowledgeBase with LOI/DECRET/REFERENTIEL categories).

    Queries KnowledgeBaseRepository filtered to regulation categories.
    """

    def _adapter(query: str, limit: int) -> List[Dict[str, Any]]:
        try:
            from apps.ai_assistant.repositories.knowledge_repository import (
                KnowledgeBaseRepository,
            )
            repo = KnowledgeBaseRepository()
            results: List[Dict[str, Any]] = []

            for cat in ("LOI", "DECRET", "REFERENTIEL"):
                raw = repo.filter_by_category(cat, limit=limit // 3 + 1)
                for item in raw:
                    titre = item.get("titre", "")
                    contenu = item.get("contenu", "")
                    if not titre and not contenu:
                        continue
                    results.append({
                        "title": titre,
                        "content": contenu[:500] if contenu else "",
                        "reference": item.get("reference_reglementaire", ""),
                        "category": cat.lower(),
                        "metadata": {
                            "categorie": cat,
                            "source": "regulation",
                        },
                    })
            return results[:limit]
        except Exception as exc:
            logger.debug("Regulations adapter failed: %s", exc)
            return []

    return _adapter


def make_procedures_adapter() -> SourceRepository:
    """Create an adapter for procedures (KnowledgeBase with PROCEDURE/GUIDE categories)."""

    def _adapter(query: str, limit: int) -> List[Dict[str, Any]]:
        try:
            from apps.ai_assistant.repositories.knowledge_repository import (
                KnowledgeBaseRepository,
            )
            repo = KnowledgeBaseRepository()
            results: List[Dict[str, Any]] = []

            for cat in ("PROCEDURE", "GUIDE"):
                raw = repo.filter_by_category(cat, limit=limit // 2 + 1)
                for item in raw:
                    titre = item.get("titre", "")
                    contenu = item.get("contenu", "")
                    if not titre and not contenu:
                        continue
                    results.append({
                        "title": titre,
                        "content": contenu[:500] if contenu else "",
                        "reference": item.get("reference_reglementaire", ""),
                        "category": cat.lower(),
                        "metadata": {
                            "categorie": cat,
                            "source": "procedure",
                        },
                    })
            return results[:limit]
        except Exception as exc:
            logger.debug("Procedures adapter failed: %s", exc)
            return []

    return _adapter


def make_internal_docs_adapter() -> SourceRepository:
    """Create an adapter for internal documents (KnowledgeBase with FAQ/AUTRE categories)."""

    def _adapter(query: str, limit: int) -> List[Dict[str, Any]]:
        try:
            from apps.ai_assistant.repositories.knowledge_repository import (
                KnowledgeBaseRepository,
            )
            repo = KnowledgeBaseRepository()
            results: List[Dict[str, Any]] = []

            for cat in ("FAQ", "AUTRE", "DECHETS_HOSPITALIERS", "DECLARATION_TRIMESTRIELLE"):
                raw = repo.filter_by_category(cat, limit=limit // 4 + 1)
                for item in raw:
                    titre = item.get("titre", "")
                    contenu = item.get("contenu", "")
                    if not titre and not contenu:
                        continue
                    results.append({
                        "title": titre,
                        "content": contenu[:500] if contenu else "",
                        "reference": item.get("reference_reglementaire", ""),
                        "category": cat.lower(),
                        "metadata": {
                            "categorie": cat,
                            "source": "internal_document",
                        },
                    })
            return results[:limit]
        except Exception as exc:
            logger.debug("Internal docs adapter failed: %s", exc)
            return []

    return _adapter


def make_reports_adapter() -> SourceRepository:
    """Create an adapter for reports (KnowledgeBase with GLOSSAIRE category used as reports fallback).

    In a real deployment this would connect to a report repository.
    Currently returns empty — placeholder for future implementation.
    """

    def _adapter(query: str, limit: int) -> List[Dict[str, Any]]:
        # Placeholder — no report repository exists yet
        return []

    return _adapter
