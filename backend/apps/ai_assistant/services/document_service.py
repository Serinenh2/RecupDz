"""
Document Service — business logic for RAG document loading.

Responsibilities:
    - Text formatting for each knowledge source type
    - LoadedDocument creation with metadata
    - Source-specific transformations

Does NOT access Django ORM or import Django models.
Uses DocumentRepository for data access.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Business logic for converting raw data into LoadedDocuments.

    Handles text formatting and metadata extraction for:
        - Regulations (KnowledgeBase articles)
        - Waste Codes (Nomenclature entries)
        - Procedures (Archive documents)
        - Glossary (in-memory terms)
    """

    def __init__(self, repository=None) -> None:
        self._repository = repository

    @property
    def repository(self):
        if self._repository is None:
            from apps.ai_assistant.repositories.document_repository import DocumentRepository
            self._repository = DocumentRepository()
        return self._repository

    # ------------------------------------------------------------------
    # Public API — load each source type
    # ------------------------------------------------------------------

    def load_regulations(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Load regulation articles and return formatted documents.

        Returns list of dicts with keys: text, source, source_type, metadata.
        """
        articles = self._repository.get_regulations(limit=limit)
        documents = []

        for article in articles:
            title = article.get("titre", "")
            content = article.get("contenu", "")
            categorie = article.get("categorie", "")
            reference = article.get("reference", "")

            text = f"{title}\n\n{content}"
            if reference:
                text = f"Référence: {reference}\n{text}"

            documents.append({
                "text": text,
                "source": f"regulation:{article.get('id', '')}",
                "source_type": "regulation",
                "metadata": {
                    "categorie": categorie,
                    "reference": reference,
                    "titre": title,
                },
            })

        logger.info("Formatted %d regulation documents", len(documents))
        return documents

    def load_waste_codes(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Load waste codes and return formatted documents.

        Returns list of dicts with keys: text, source, source_type, metadata.
        """
        codes = self._repository.get_waste_codes(limit=limit)
        documents = []

        for code in codes:
            text = (
                f"Code: {code.get('code', '')}\n"
                f"Famille: {code.get('famille', '')} - {code.get('sous_famille', '')}\n"
                f"Désignation FR: {code.get('designation_fr', '')}\n"
                f"Désignation AR: {code.get('designation_ar', '')}\n"
                f"Classe: {code.get('classe', '')}\n"
                f"Dangerosité: {code.get('dangerosite_fr', '')}\n"
                f"Annexe: {code.get('annexe', '')}\n"
                f"BSD obligatoire: {code.get('bsd_obligatoire', '')}\n"
                f"Agrément requis: {code.get('agrement_requis', '')}"
            )

            documents.append({
                "text": text,
                "source": f"waste_code:{code.get('id', '')}",
                "source_type": "waste_code",
                "metadata": {
                    "code": code.get("code", ""),
                    "famille": code.get("famille", ""),
                    "classe": code.get("classe", ""),
                },
            })

        logger.info("Formatted %d waste code documents", len(documents))
        return documents

    def load_procedures(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Load internal procedures and return formatted documents.

        Returns list of dicts with keys: text, source, source_type, metadata.
        """
        docs = self._repository.get_procedures(limit=limit)
        documents = []

        for doc in docs:
            title = doc.get("titre", doc.get("name", ""))
            description = doc.get("description", "")
            content = doc.get("contenu", doc.get("content", ""))

            text = f"{title}\n\n{description}"
            if content:
                text += f"\n\n{content}"

            if text.strip():
                documents.append({
                    "text": text,
                    "source": f"procedure:{doc.get('pk', 'unknown')}",
                    "source_type": "procedure",
                    "metadata": {
                        "title": title,
                        "categorie": doc.get("categorie", ""),
                    },
                })

        logger.info("Formatted %d procedure documents", len(documents))
        return documents

    def load_glossary(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Load glossary terms and return formatted documents.

        Returns list of dicts with keys: text, source, source_type, metadata.
        """
        entries = self._repository.get_glossary(limit=limit)
        documents = []

        for entry in entries:
            term_fr = entry.get("terme_fr", "")
            term_ar = entry.get("terme_ar", "")
            def_fr = entry.get("definition_fr", "")
            def_ar = entry.get("definition_ar", "")
            reference = entry.get("reference", "")
            categorie = entry.get("categorie", "")

            text = f"Terme: {term_fr}"
            if term_ar:
                text += f" ({term_ar})"
            text += f"\nDéfinition: {def_fr}"
            if def_ar:
                text += f"\nالتعريف: {def_ar}"
            if reference:
                text += f"\nRéférence: {reference}"

            documents.append({
                "text": text,
                "source": f"glossary:{term_fr}",
                "source_type": "glossary",
                "metadata": {
                    "term_fr": term_fr,
                    "term_ar": term_ar,
                    "categorie": categorie,
                    "reference": reference,
                },
            })

        logger.info("Formatted %d glossary documents", len(documents))
        return documents

    def load_all(self, sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Load all knowledge sources and return formatted documents.

        Args:
            sources: Which sources to load. None = all sources.
                Options: glossary, nomenclature, regulations, procedures
        """
        all_sources = sources or ["glossary", "nomenclature", "regulations", "procedures"]
        all_documents: List[Dict[str, Any]] = []

        if "regulations" in all_sources:
            all_documents.extend(self.load_regulations())
        if "nomenclature" in all_sources:
            all_documents.extend(self.load_waste_codes())
        if "glossary" in all_sources:
            all_documents.extend(self.load_glossary())
        if "procedures" in all_sources:
            all_documents.extend(self.load_procedures())

        logger.info("Loaded %d total documents from: %s", len(all_documents), all_sources)
        return all_documents
