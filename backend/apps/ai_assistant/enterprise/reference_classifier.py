"""
Reference Classifier — disambiguates numeric references without executing tools.

Recognizes:
    - Waste Code (nomenclature): XX.XX.XX format (e.g., 15.01.06)
    - Nomenclature Code: alias for Waste Code
    - Regulation Reference: article/alinea numbers in legal context
    - Procedure Chapter: chapter/section numbers in procedural context
    - Article: legal article with explicit keyword
    - BSD Number: BSD-YYYY-NNNN or BSDNNNN
    - BC Number: BC-YYYY-NNNN or BCNNNN
    - BL Number: BL-YYYY-NNNN or BLNNNN
    - Tracking Number: TRK-NNNN or TRA-NNNN
    - Version Number: vN.N or N.N.N.N format
    - Unknown Reference: unrecognized pattern

Returns:
    {"reference_type": "", "confidence": 0.0}

No business tool is ever executed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional


# ── Result ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClassificationResult:
    """Immutable classification result."""
    reference_type: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference_type": self.reference_type,
            "confidence": round(self.confidence, 3),
        }


# ── Reference Types ───────────────────────────────────────────────────


class ReferenceType:
    WASTE_CODE = "waste_code"
    NOMENCLATURE_CODE = "nomenclature_code"
    REGULATION_REFERENCE = "regulation_reference"
    PROCEDURE_CHAPTER = "procedure_chapter"
    ARTICLE = "article"
    BSD_NUMBER = "bsd_number"
    BC_NUMBER = "bc_number"
    BL_NUMBER = "bl_number"
    TRACKING_NUMBER = "tracking_number"
    VERSION_NUMBER = "version_number"
    UNKNOWN = "unknown_reference"


# ── Context Keywords ──────────────────────────────────────────────────

_REGULATION_KEYWORDS = re.compile(
    r"\b(?:loi|loi\s+01|décret|decret|arret[ée]|règlement|reglement|"
    r"juridique|l[ée]gal|compliance|réglementaire|reglementaire|"
    r"titres?)\b",
    re.IGNORECASE,
)

_PROCEDURE_KEYWORDS = re.compile(
    r"\b(?:proc[ée]dure|procedure|chapitre|chapter|section|"
    r"guide|manuel|consigne|protocole|"
    r"étape|etape|phase|niveau)\b",
    re.IGNORECASE,
)

_ARTICLE_KEYWORDS = re.compile(
    r"\b(?:article|alinéa|alinea|point|paragraphe|§)\b",
    re.IGNORECASE,
)


# ── Classifier ────────────────────────────────────────────────────────


class ReferenceClassifier:
    """
    Classifies numeric references by type and confidence.

    Usage:
        classifier = ReferenceClassifier()
        result = classifier.classify("1.3.1")
        print(result.to_dict())
        # {"reference_type": "regulation_reference", "confidence": 0.72}
    """

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a reference string.

        Args:
            text: The reference string to classify (e.g., "1.3.1", "BSD-2024-001").

        Returns:
            ClassificationResult with reference_type and confidence.
        """
        if not text or not text.strip():
            return ClassificationResult(
                reference_type=ReferenceType.UNKNOWN,
                confidence=0.0,
            )

        normalized = text.strip().strip("\"'()[]{}")

        normalized_lower = normalized.lower()

        # ── Pass 1: Exact prefix patterns (high confidence) ──────────

        result = self._check_prefixed_references(normalized, normalized_lower)
        if result is not None:
            return result

        # ── Pass 2: Version number patterns ──────────────────────────

        result = self._check_version_number(normalized, normalized_lower)
        if result is not None:
            return result

        # ── Pass 3: Waste code / Nomenclature code (XX.XX.XX) ───────

        result = self._check_waste_code(normalized)
        if result is not None:
            return result

        # ── Pass 4: Context-dependent numeric patterns ───────────────

        result = self._check_contextual_numeric(normalized, normalized_lower)
        if result is not None:
            return result

        # ── Pass 5: Fallback — bare numeric with no context ──────────

        result = self._check_bare_numeric(normalized)
        if result is not None:
            return result

        # ── No match ─────────────────────────────────────────────────

        return ClassificationResult(
            reference_type=ReferenceType.UNKNOWN,
            confidence=0.0,
        )

    # ------------------------------------------------------------------
    # Pass 1: Prefixed references (BSD, BC, BL, TRK, TRA)
    # ------------------------------------------------------------------

    def _check_prefixed_references(
        self, text: str, text_lower: str,
    ) -> Optional[ClassificationResult]:
        """Check for document-numbered references with explicit prefixes."""

        # BSD Number: BSD-2024-001, BSD12345, BSD 2024 001
        if re.match(r"^bsd[-\s]?\d", text_lower):
            return ClassificationResult(
                reference_type=ReferenceType.BSD_NUMBER,
                confidence=0.97,
            )

        # BC Number: BC-2024-001, BC12345
        if re.match(r"^bc[-\s]?\d", text_lower):
            return ClassificationResult(
                reference_type=ReferenceType.BC_NUMBER,
                confidence=0.97,
            )

        # BL Number: BL-2024-001, BL12345
        if re.match(r"^bl[-\s]?\d", text_lower):
            return ClassificationResult(
                reference_type=ReferenceType.BL_NUMBER,
                confidence=0.97,
            )

        # Tracking Number: TRK-12345, TRA-12345, TRACK-12345
        if re.match(r"^(?:trk|tra|track)[-\s]?\d", text_lower):
            return ClassificationResult(
                reference_type=ReferenceType.TRACKING_NUMBER,
                confidence=0.95,
            )

        return None

    # ------------------------------------------------------------------
    # Pass 2: Version numbers
    # ------------------------------------------------------------------

    def _check_version_number(
        self, text: str, text_lower: str,
    ) -> Optional[ClassificationResult]:
        """Check for version number patterns."""

        # v1.3, v2.0.1, V1.3
        if re.match(r"^v\d+\.\d+", text_lower):
            return ClassificationResult(
                reference_type=ReferenceType.VERSION_NUMBER,
                confidence=0.93,
            )

        # 1.0.0.1 — four-part dotted version (not a waste code)
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", text):
            return ClassificationResult(
                reference_type=ReferenceType.VERSION_NUMBER,
                confidence=0.90,
            )

        return None

    # ------------------------------------------------------------------
    # Pass 3: Waste code / Nomenclature code (XX.XX.XX)
    # ------------------------------------------------------------------

    def _check_waste_code(self, text: str) -> Optional[ClassificationResult]:
        """
        Check for waste nomenclature code format: XX.XX.XX

        Waste codes follow the pattern:
            - Family (1-2 digits) . Subfamily (2 digits) . Code (2 digits)
            - Examples: 15.01.06, 20.01.08, 16.01.03
            - Valid families: 01-20 (standard waste classification)
        """
        match = re.match(r"^(\d{1,2})\.(\d{2})\.(\d{2})$", text)
        if match:
            family = int(match.group(1))
            subfamily = int(match.group(2))
            code = int(match.group(3))

            # Valid waste families: 01-20
            if 1 <= family <= 20 and 1 <= subfamily <= 99 and 1 <= code <= 99:
                return ClassificationResult(
                    reference_type=ReferenceType.WASTE_CODE,
                    confidence=0.92,
                )

            # Out-of-range but still XX.XX.XX format — lower confidence
            return ClassificationResult(
                reference_type=ReferenceType.WASTE_CODE,
                confidence=0.70,
            )

        # Two-level code: XX.XX (could be waste subfamily or regulation)
        match_two = re.match(r"^(\d{1,2})\.(\d{2})$", text)
        if match_two:
            family = int(match_two.group(1))
            subfamily = int(match_two.group(2))

            # Valid waste families with plausible subfamily
            if 1 <= family <= 20 and 1 <= subfamily <= 99:
                return ClassificationResult(
                    reference_type=ReferenceType.WASTE_CODE,
                    confidence=0.75,
                )

        return None

    # ------------------------------------------------------------------
    # Pass 4: Context-dependent numeric patterns
    # ------------------------------------------------------------------

    def _check_contextual_numeric(
        self, text: str, text_lower: str,
    ) -> Optional[ClassificationResult]:
        """Check numeric patterns that depend on surrounding context keywords."""

        # Must contain at least one digit
        if not re.search(r"\d", text):
            return None

        has_regulation_context = bool(_REGULATION_KEYWORDS.search(text_lower))
        has_procedure_context = bool(_PROCEDURE_KEYWORDS.search(text_lower))
        has_article_context = bool(_ARTICLE_KEYWORDS.search(text_lower))

        # Article with explicit keyword: "article 1.3.1", "alinéa 2.4"
        if has_article_context and re.search(r"\d+\.\d+", text):
            return ClassificationResult(
                reference_type=ReferenceType.ARTICLE,
                confidence=0.90,
            )

        # Regulation reference with context: "loi 1.3.1", "décret 2.4"
        if has_regulation_context and re.search(r"\d+\.\d+", text):
            return ClassificationResult(
                reference_type=ReferenceType.REGULATION_REFERENCE,
                confidence=0.88,
            )

        # Procedure chapter with context: "chapitre 1.3", "étape 2.4"
        if has_procedure_context and re.search(r"\d+\.\d+", text):
            return ClassificationResult(
                reference_type=ReferenceType.PROCEDURE_CHAPTER,
                confidence=0.85,
            )

        return None

    # ------------------------------------------------------------------
    # Pass 5: Bare numeric with no context
    # ------------------------------------------------------------------

    def _check_bare_numeric(self, text: str) -> Optional[ClassificationResult]:
        """
        Handle bare numeric references with no context keywords.

        Heuristics:
            - XX.XX.XX (3 parts, each 1-2 digits) → waste_code (most common in domain)
            - XX.XX (2 parts) → regulation_reference (article-like)
            - Single number → unknown (too ambiguous)
        """
        # Three-part dotted: 1.3.1, 15.01.06, 20.01.08
        if re.match(r"^\d{1,2}\.\d{1,2}\.\d{1,2}$", text):
            parts = text.split(".")
            first = int(parts[0])
            # Waste code families are 01-20 — strong signal
            if 1 <= first <= 20:
                return ClassificationResult(
                    reference_type=ReferenceType.WASTE_CODE,
                    confidence=0.80,
                )
            # Higher first number — more likely regulation/article
            return ClassificationResult(
                reference_type=ReferenceType.REGULATION_REFERENCE,
                confidence=0.65,
            )

        # Two-part dotted: 1.3, 15.01
        if re.match(r"^\d{1,2}\.\d{1,2}$", text):
            parts = text.split(".")
            first = int(parts[0])
            if 1 <= first <= 20:
                return ClassificationResult(
                    reference_type=ReferenceType.WASTE_CODE,
                    confidence=0.70,
                )
            return ClassificationResult(
                reference_type=ReferenceType.REGULATION_REFERENCE,
                confidence=0.60,
            )

        # Single number: too ambiguous
        if re.match(r"^\d+$", text):
            return ClassificationResult(
                reference_type=ReferenceType.UNKNOWN,
                confidence=0.10,
            )

        return None


# ── Module-level singleton ────────────────────────────────────────────

_classifier: Optional[ReferenceClassifier] = None


def classify_reference(text: str) -> Dict[str, Any]:
    """
    Classify a reference string. Module-level convenience function.

    Args:
        text: The reference string to classify.

    Returns:
        {"reference_type": "...", "confidence": 0.0}
    """
    global _classifier
    if _classifier is None:
        _classifier = ReferenceClassifier()
    return _classifier.classify(text).to_dict()
