"""
Document Loader — loads and chunks documents from various sources.

Supports:
    - PDF (via PyPDF2)
    - DOCX (via python-docx)
    - TXT / Markdown (plain text)
    - Regulations (from database)
    - Waste Codes (from database)
    - Internal Procedures (from database)

Each document is split into overlapping chunks for retrieval.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from apps.ai_assistant.rag.vector_store import DocumentChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Loaded Document
# ---------------------------------------------------------------------------

@dataclass
class LoadedDocument:
    """A loaded document before chunking."""
    text: str
    source: str
    source_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Text Chunker
# ---------------------------------------------------------------------------

class TextChunker:
    """
    Splits text into overlapping chunks.

    Args:
        chunk_size: Maximum characters per chunk.
        overlap: Number of overlapping characters between chunks.
    """

    def __init__(self, chunk_size: int = 1000, overlap: int = 200) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        if not text or not text.strip():
            return []

        text = text.strip()
        if len(text) <= self._chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self._chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end in the last 200 chars
                search_start = max(start + self._chunk_size - 200, start)
                last_period = -1
                for punct in ["\n\n", "\n", ". ", "! ", "? ", "؛", "。"]:
                    pos = text.rfind(punct, search_start, end + 100)
                    if pos > last_period:
                        last_period = pos + len(punct)

                if last_period > start:
                    end = last_period

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self._overlap
            if start >= len(text):
                break

        return chunks


# ---------------------------------------------------------------------------
# Document Loader
# ---------------------------------------------------------------------------

class DocumentLoader:
    """
    Loads documents from files and databases, splits into chunks.

    Usage:
        loader = DocumentLoader()
        chunks = loader.load_file("regulation.pdf")
        chunks = loader.load_directory("/path/to/docs/")
        chunks = loader.load_regulations()
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self._chunker = TextChunker(chunk_size=chunk_size, overlap=chunk_overlap)

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def load_file(self, path: str, source_type: Optional[str] = None) -> List[DocumentChunk]:
        """Load a single file and return chunks."""
        file_path = Path(path)
        if not file_path.exists():
            logger.warning("File not found: %s", path)
            return []

        suffix = file_path.suffix.lower()
        if source_type is None:
            source_type = self._detect_type(suffix)

        try:
            if suffix == ".pdf":
                doc = self._load_pdf(str(file_path))
            elif suffix == ".docx":
                doc = self._load_docx(str(file_path))
            elif suffix in (".txt", ".md", ".markdown", ".rst"):
                doc = self._load_text(str(file_path))
            else:
                logger.warning("Unsupported file type: %s", suffix)
                return []

            return self._to_chunks(doc)

        except Exception as exc:
            logger.error("Failed to load %s: %s", path, exc)
            return []

    def load_directory(self, directory: str, extensions: Optional[List[str]] = None) -> List[DocumentChunk]:
        """Load all supported files from a directory."""
        if extensions is None:
            extensions = [".pdf", ".docx", ".txt", ".md"]

        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning("Directory not found: %s", directory)
            return []

        all_chunks = []
        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                chunks = self.load_file(str(file_path))
                all_chunks.extend(chunks)
                logger.info("Loaded %s: %d chunks", file_path.name, len(chunks))

        return all_chunks

    # ------------------------------------------------------------------
    # Database loading
    # ------------------------------------------------------------------

    def load_regulations(self, limit: int = 500) -> List[DocumentChunk]:
        """Load regulations from the KnowledgeBase."""
        try:
            from apps.ai_assistant.repositories.knowledge_repository import KnowledgeBaseRepository
            repo = KnowledgeBaseRepository()
            articles = repo.list(limit=limit)

            chunks = []
            for article in articles:
                title = article.get("titre", "")
                content = article.get("contenu", "")
                categorie = article.get("categorie", "")
                reference = article.get("reference", "")

                full_text = f"{title}\n\n{content}"
                if reference:
                    full_text = f"Référence: {reference}\n{full_text}"

                loaded = LoadedDocument(
                    text=full_text,
                    source=f"regulation:{article.get('id', '')}",
                    source_type="regulation",
                    metadata={
                        "categorie": categorie,
                        "reference": reference,
                        "titre": title,
                    },
                )
                chunks.extend(self._to_chunks(loaded))

            logger.info("Loaded %d regulation chunks", len(chunks))
            return chunks

        except Exception as exc:
            logger.error("Failed to load regulations: %s", exc)
            return []

    def load_waste_codes(self, limit: int = 1000) -> List[DocumentChunk]:
        """Load waste codes from the Nomenclature."""
        try:
            from apps.ai_assistant.repositories.nomenclature_repository import NomenclatureRepository
            repo = NomenclatureRepository()
            codes = repo.list(limit=limit)

            chunks = []
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

                loaded = LoadedDocument(
                    text=text,
                    source=f"waste_code:{code.get('id', '')}",
                    source_type="waste_code",
                    metadata={
                        "code": code.get("code", ""),
                        "famille": code.get("famille", ""),
                        "classe": code.get("classe", ""),
                    },
                )
                chunks.extend(self._to_chunks(loaded))

            logger.info("Loaded %d waste code chunks", len(chunks))
            return chunks

        except Exception as exc:
            logger.error("Failed to load waste codes: %s", exc)
            return []

    def load_glossary(self, limit: int = 200) -> List[DocumentChunk]:
        """Load glossary terms from the in-memory GLOSSAIRE + KnowledgeBase."""
        try:
            from apps.ai_assistant.glossaire_data import GLOSSAIRE

            chunks = []
            for entry in GLOSSAIRE[:limit]:
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

                loaded = LoadedDocument(
                    text=text,
                    source=f"glossary:{term_fr}",
                    source_type="glossary",
                    metadata={
                        "term_fr": term_fr,
                        "term_ar": term_ar,
                        "categorie": categorie,
                        "reference": reference,
                    },
                )
                chunks.extend(self._to_chunks(loaded))

            logger.info("Loaded %d glossary chunks", len(chunks))
            return chunks

        except ImportError:
            logger.warning("glossaire_data.py not found — skipping glossary indexing")
            return []
        except Exception as exc:
            logger.error("Failed to load glossary: %s", exc)
            return []

    def load_procedures(self, limit: int = 200) -> List[DocumentChunk]:
        """Load internal procedures from the archive.Document model.

        Looks for documents categorized as procedures, guides, or SOPs.
        """
        try:
            from django.apps import apps

            DocumentModel = apps.get_model("archive", "Document")
            qs = DocumentModel.objects.filter(
                categorie__in=["PROCEDURE", "GUIDE", "SOP", "MANUAL", "PROCÉDURE"]
            )[:limit]

            chunks = []
            for doc in qs:
                title = getattr(doc, "titre", getattr(doc, "name", ""))
                description = getattr(doc, "description", "")
                content = getattr(doc, "contenu", getattr(doc, "content", ""))

                text = f"{title}\n\n{description}"
                if content:
                    text += f"\n\n{content}"

                if text.strip():
                    loaded = LoadedDocument(
                        text=text,
                        source=f"procedure:{getattr(doc, 'pk', 'unknown')}",
                        source_type="procedure",
                        metadata={
                            "title": title,
                            "categorie": getattr(doc, "categorie", ""),
                        },
                    )
                    chunks.extend(self._to_chunks(loaded))

            logger.info("Loaded %d procedure chunks", len(chunks))
            return chunks

        except LookupError:
            logger.info("archive.Document model not available — skipping procedures")
            return []
        except Exception as exc:
            logger.error("Failed to load procedures: %s", exc)
            return []

    def load_all(self, sources: Optional[List[str]] = None) -> List[DocumentChunk]:
        """Load all knowledge sources.

        Args:
            sources: Which sources to load. None = all sources.
                Options: glossary, nomenclature, regulations, procedures
        """
        all_sources = sources or ["glossary", "nomenclature", "regulations", "procedures"]
        chunks: List[DocumentChunk] = []

        if "regulations" in all_sources:
            chunks.extend(self.load_regulations())
        if "nomenclature" in all_sources:
            chunks.extend(self.load_waste_codes())
        if "glossary" in all_sources:
            chunks.extend(self.load_glossary())
        if "procedures" in all_sources:
            chunks.extend(self.load_procedures())

        logger.info("Loaded %d total chunks from sources: %s", len(chunks), all_sources)
        return chunks

    # ------------------------------------------------------------------
    # File format loaders
    # ------------------------------------------------------------------

    def _load_pdf(self, path: str) -> LoadedDocument:
        """Load a PDF file."""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return LoadedDocument(
                text="\n\n".join(text_parts),
                source=path,
                source_type="pdf",
                metadata={"pages": len(reader.pages)},
            )
        except ImportError:
            logger.error("PyPDF2 not installed")
            return LoadedDocument(text="", source=path, source_type="pdf")

    def _load_docx(self, path: str) -> LoadedDocument:
        """Load a DOCX file."""
        try:
            from docx import Document
            doc = Document(path)
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)

            return LoadedDocument(
                text="\n\n".join(text_parts),
                source=path,
                source_type="docx",
                metadata={"paragraphs": len(doc.paragraphs)},
            )
        except ImportError:
            logger.error("python-docx not installed")
            return LoadedDocument(text="", source=path, source_type="docx")

    def _load_text(self, path: str) -> LoadedDocument:
        """Load a plain text file."""
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()

        return LoadedDocument(
            text=text,
            source=path,
            source_type="txt",
            metadata={"size_bytes": len(text.encode())},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_chunks(self, doc: LoadedDocument) -> List[DocumentChunk]:
        """Convert a LoadedDocument into DocumentChunks."""
        if not doc.text or not doc.text.strip():
            return []

        text_chunks = self._chunker.chunk(doc.text)
        chunks = []
        for i, text in enumerate(text_chunks):
            chunks.append(DocumentChunk(
                text=text,
                source=doc.source,
                source_type=doc.source_type,
                chunk_index=i,
                metadata=doc.metadata,
            ))

        return chunks

    def _detect_type(self, suffix: str) -> str:
        """Detect source type from file extension."""
        mapping = {
            ".pdf": "pdf",
            ".docx": "docx",
            ".txt": "txt",
            ".md": "txt",
            ".markdown": "txt",
            ".rst": "txt",
        }
        return mapping.get(suffix, "unknown")
