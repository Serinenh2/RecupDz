"""
Document Repository — Django ORM access for all RAG knowledge sources.

All database access for regulations, waste codes, procedures, and glossary
lives HERE. The RAG package never imports Django models directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DocumentRepository:
    """
    Repository for all knowledge sources used by RAG.

    Wraps existing repositories (KnowledgeBase, Nomenclature, Archive)
    and provides a unified interface for the DocumentService.
    """

    def get_regulations(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Get regulation articles from KnowledgeBase."""
        try:
            from apps.ai_assistant.repositories.knowledge_repository import KnowledgeBaseRepository
            repo = KnowledgeBaseRepository()
            return repo.list(limit=limit)
        except Exception as exc:
            logger.error("Failed to load regulations: %s", exc)
            return []

    def get_waste_codes(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get waste codes from Nomenclature."""
        try:
            from apps.ai_assistant.repositories.nomenclature_repository import NomenclatureRepository
            repo = NomenclatureRepository()
            return repo.list(limit=limit)
        except Exception as exc:
            logger.error("Failed to load waste codes: %s", exc)
            return []

    def get_procedures(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get internal procedures from Archive."""
        try:
            from apps.ai_assistant.repositories.archive_repository import ArchiveRepository
            repo = ArchiveRepository()
            return repo.get_procedures(limit=limit)
        except Exception as exc:
            logger.error("Failed to load procedures: %s", exc)
            return []

    def get_glossary(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get glossary terms from in-memory data."""
        try:
            from apps.ai_assistant.glossaire_data import GLOSSAIRE
            return GLOSSAIRE[:limit]
        except ImportError:
            logger.warning("glossaire_data.py not found — skipping glossary")
            return []
        except Exception as exc:
            logger.error("Failed to load glossary: %s", exc)
            return []
