"""
Entity Extraction Stage — identifies structured entities from the question.

Extracts: codes, dates, names, IDs, categories, amounts, etc.
Pure pattern matching — no LLM dependency.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern

from apps.ai_assistant.reasoning_engine.pipeline import PipelineContext, PipelineStage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entity Type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EntityPattern:
    """A named pattern that extracts entities of a specific type."""
    entity_type: str
    pattern: Pattern[str]
    groups: Optional[List[str]] = None  # named groups to extract, None = full match
    confidence: float = 0.8


# ---------------------------------------------------------------------------
# Extracted Entity
# ---------------------------------------------------------------------------

@dataclass
class ExtractedEntity:
    """A single extracted entity."""
    type: str
    value: str
    confidence: float
    raw_match: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "value": self.value,
            "confidence": self.confidence,
            "raw": self.raw_match,
        }


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class EntityExtractionStage(PipelineStage):
    """
    Stage 2: Extract structured entities from the question.

    Uses regex patterns for codes, dates, names, IDs, amounts.
    Accepts an optional LLM extractor for complex entities.
    """

    name = "entity_extraction"
    order = 20

    def __init__(
        self,
        patterns: Optional[List[EntityPattern]] = None,
        llm_extract: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
    ) -> None:
        self._patterns = patterns or self._default_patterns()
        self._llm_extract = llm_extract

    def process(self, context: PipelineContext) -> None:
        question = context.question
        entities: List[ExtractedEntity] = []

        # Pattern-based extraction
        for ep in self._patterns:
            for match in ep.pattern.finditer(question):
                value = match.group() if ep.groups is None else self._extract_groups(match, ep.groups)
                if value:
                    entities.append(ExtractedEntity(
                        type=ep.entity_type,
                        value=value.strip(),
                        confidence=ep.confidence,
                        raw_match=match.group(),
                    ))

        # LLM extraction (if available)
        if self._llm_extract is not None:
            try:
                llm_entities = self._llm_extract(question)
                for le in llm_entities:
                    entities.append(ExtractedEntity(
                        type=le.get("type", "unknown"),
                        value=le.get("value", ""),
                        confidence=float(le.get("confidence", 0.7)),
                        metadata=le.get("metadata", {}),
                    ))
            except Exception as exc:
                logger.warning("LLM entity extraction failed: %s", exc)

        # Deduplicate by (type, value)
        seen = set()
        unique: List[ExtractedEntity] = []
        for e in entities:
            key = (e.type, e.value.lower())
            if key not in seen:
                seen.add(key)
                unique.append(e)

        context.extracted_entities = [e.to_dict() for e in unique]

        # Set primary entity (highest confidence)
        if unique:
            primary = max(unique, key=lambda e: e.confidence)
            context.primary_entity = primary.to_dict()

        # Carry entity hints from intent stage
        if context.intent_entities.get("entity_type"):
            context.extracted_entities.append({
                "type": "intent_hint",
                "value": context.intent_entities.get("entity_id", ""),
                "confidence": 0.6,
            })

        logger.debug("Extracted %d entities", len(context.extracted_entities))

    # -- defaults --

    @staticmethod
    def _default_patterns() -> List[EntityPattern]:
        return [
            EntityPattern("nomenclature_code", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\b"), confidence=0.95),
            EntityPattern("nomenclature_code", re.compile(r"\b\d{2}\.\d{2}\.\d{2}\b"), confidence=0.9),
            EntityPattern("year", re.compile(r"\b(20[2-3]\d)\b"), confidence=0.85),
            EntityPattern("date", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"), confidence=0.8),
            EntityPattern("amount", re.compile(r"\b(\d[\d\s]*[,.]?\d*)\s*(tonnes?|kg|litres?|m³|dh|eur|usd)\b", re.IGNORECASE), confidence=0.85),
            EntityPattern("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), confidence=0.95),
            EntityPattern("phone", re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b"), confidence=0.7),
            EntityPattern("reference_id", re.compile(r"\b(REF[-:\s]?\w+|DOS[-:\s]?\w+|BSD[-:\s]?\w+)\b", re.IGNORECASE), confidence=0.85),
            EntityPattern("number", re.compile(r"\b(\d+)\b"), confidence=0.5),
        ]

    @staticmethod
    def _extract_groups(match: re.Match, groups: List[str]) -> str:
        parts = []
        for g in groups:
            try:
                val = match.group(g)
                if val:
                    parts.append(val)
            except IndexError:
                pass
        return " ".join(parts) if parts else match.group()
