"""
Clarification Manager — ambiguity detection and clarification question generation.

When the Router cannot determine the correct tool, does NOT guess.
Generates clarification questions so the user can confirm the intent.

Flow:
    Orchestrator → ClarificationManager.analyze() → ClarificationResult
                                                     → user confirms
                                                     → Orchestrator routes correctly

Example:
    User: "1.3.1"
    Assistant: "J'ai trouvé plusieurs interprétations possibles.
               Est-ce un code déchet ? une référence réglementaire ? un terme du glossaire ?"
    User: "code déchet"
    → waste_tool.get_by_code(code="1.3.1")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClarificationOption:
    """One possible interpretation for an ambiguous input."""

    label: str
    tool: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "label": self.label,
            "tool": self.tool,
            "action": self.action,
        }
        if self.parameters:
            result["parameters"] = self.parameters
        if self.confidence:
            result["confidence"] = round(self.confidence, 2)
        return result


@dataclass(frozen=True)
class ClarificationResult:
    """Result when clarification is needed before routing."""

    question: str
    options: List[ClarificationOption]
    original_message: str
    reason: str  # "ambiguous_reference", "low_confidence", "close_candidates"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "options": [opt.to_dict() for opt in self.options],
            "original_message": self.original_message,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Reference → Tool mapping
# ---------------------------------------------------------------------------

_REFERENCE_OPTION_MAP: Dict[str, List[ClarificationOption]] = {
    "waste_code": [
        ClarificationOption(
            label="un code déchet (nomenclature)",
            tool="waste_tool",
            action="get_by_code",
        ),
        ClarificationOption(
            label="une référence réglementaire",
            tool="reglementation_tool",
            action="by_reference",
        ),
        ClarificationOption(
            label="un terme du glossaire",
            tool="glossaire_tool",
            action="search",
        ),
    ],
    "regulation_reference": [
        ClarificationOption(
            label="une référence réglementaire",
            tool="reglementation_tool",
            action="by_reference",
        ),
        ClarificationOption(
            label="un code déchet (nomenclature)",
            tool="waste_tool",
            action="get_by_code",
        ),
        ClarificationOption(
            label="un terme du glossaire",
            tool="glossaire_tool",
            action="search",
        ),
    ],
    "procedure_chapter": [
        ClarificationOption(
            label="un chapitre de procédure",
            tool="glossaire_tool",
            action="search",
        ),
        ClarificationOption(
            label="une référence réglementaire",
            tool="reglementation_tool",
            action="by_reference",
        ),
        ClarificationOption(
            label="un code déchet (nomenclature)",
            tool="waste_tool",
            action="get_by_code",
        ),
    ],
    "article": [
        ClarificationOption(
            label="un article réglementaire",
            tool="reglementation_tool",
            action="by_reference",
        ),
        ClarificationOption(
            label="un code déchet (nomenclature)",
            tool="waste_tool",
            action="get_by_code",
        ),
        ClarificationOption(
            label="un terme du glossaire",
            tool="glossaire_tool",
            action="search",
        ),
    ],
    "unknown_reference": [
        ClarificationOption(
            label="un code déchet (nomenclature)",
            tool="waste_tool",
            action="get_by_code",
        ),
        ClarificationOption(
            label="une référence réglementaire",
            tool="reglementation_tool",
            action="by_reference",
        ),
        ClarificationOption(
            label="un terme du glossaire",
            tool="glossaire_tool",
            action="search",
        ),
    ],
}


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class ClarificationManager:
    """Detects ambiguous routing and generates clarification questions.

    Triggers:
        1. **Ambiguous reference** — dotted numeric classified with
           confidence below threshold (e.g. "1.3.1" → waste_code @ 0.80
           could also be regulation reference).
        2. **Low confidence** — best routing candidate below threshold.
        3. **Close candidates** — top two candidates within a narrow
           confidence gap, neither clearly dominant.

    The manager never executes a tool. It only generates a question
    so the user can confirm which tool to invoke.
    """

    CONFIDENCE_THRESHOLD: float = 0.50
    CANDIDATE_GAP_THRESHOLD: float = 0.15
    REFERENCE_AMBIGUITY_THRESHOLD: float = 0.85

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        message: str,
        candidates: Optional[List[Any]] = None,
        classified_references: Optional[List[Any]] = None,
    ) -> Optional[ClarificationResult]:
        """Analyze whether clarification is needed before routing.

        Args:
            message: Original user message.
            candidates: ToolCandidate list from the AI Router classify().
            classified_references: ClassifiedReference list from entity extraction.

        Returns:
            ``ClarificationResult`` if ambiguous, ``None`` if routing is clear.
        """
        try:
            return self._analyze_internal(message, candidates, classified_references)
        except Exception as exc:
            logger.error("Clarification analysis crashed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _analyze_internal(
        self,
        message: str,
        candidates: Optional[List[Any]],
        classified_references: Optional[List[Any]],
    ) -> Optional[ClarificationResult]:
        # 1. Ambiguous references (highest priority)
        ref_result = self._check_reference_ambiguity(message, classified_references)
        if ref_result is not None:
            return ref_result

        # 2. Routing ambiguity (low confidence or close candidates)
        route_result = self._check_routing_ambiguity(message, candidates)
        if route_result is not None:
            return route_result

        return None

    # -- Reference ambiguity ----------------------------------------------

    def _check_reference_ambiguity(
        self,
        message: str,
        classified_references: Optional[List[Any]],
    ) -> Optional[ClarificationResult]:
        """Check if any reference in the message has ambiguous classification."""
        if not classified_references:
            return None

        for ref in classified_references:
            ref_type = getattr(ref, "reference_type", "")
            ref_text = getattr(ref, "reference", "")
            ref_conf = getattr(ref, "confidence", 1.0)

            if ref_type in ("bsd_number", "bc_number", "bl_number", "tracking_number", "version_number"):
                continue

            if ref_conf < self.REFERENCE_AMBIGUITY_THRESHOLD:
                options = _REFERENCE_OPTION_MAP.get(ref_type, _REFERENCE_OPTION_MAP["unknown_reference"])
                options = self._fill_parameters(options, ref_text)
                question = self._format_reference_question(ref_text, options)
                return ClarificationResult(
                    question=question,
                    options=options,
                    original_message=message,
                    reason="ambiguous_reference",
                )

        return None

    # -- Routing ambiguity -----------------------------------------------

    def _check_routing_ambiguity(
        self,
        message: str,
        candidates: Optional[List[Any]],
    ) -> Optional[ClarificationResult]:
        """Check if the routing candidates are ambiguous."""
        if not candidates or len(candidates) < 2:
            return None

        best = candidates[0]
        best_conf = getattr(best, "confidence", 0.0)
        second = candidates[1]
        second_conf = getattr(second, "confidence", 0.0)

        # Low confidence
        if best_conf < self.CONFIDENCE_THRESHOLD:
            options = self._candidates_to_options(candidates[:3])
            question = self._format_routing_question(options)
            return ClarificationResult(
                question=question,
                options=options,
                original_message=message,
                reason="low_confidence",
            )

        # Close candidates — neither clearly dominant
        gap = best_conf - second_conf
        if gap < self.CANDIDATE_GAP_THRESHOLD:
            options = self._candidates_to_options(candidates[:3])
            question = self._format_routing_question(options)
            return ClarificationResult(
                question=question,
                options=options,
                original_message=message,
                reason="close_candidates",
            )

        return None

    # -- Option generation -----------------------------------------------

    @staticmethod
    def _fill_parameters(
        options: List[ClarificationOption],
        ref_text: str,
    ) -> List[ClarificationOption]:
        """Fill parameters dict on each option with the reference text."""
        filled: List[ClarificationOption] = []
        for opt in options:
            params: Dict[str, Any] = {}
            if opt.action == "get_by_code":
                params = {"code": ref_text}
            elif opt.action == "by_reference":
                params = {"reference": ref_text}
            elif opt.action == "search":
                params = {"query": ref_text}
            filled.append(ClarificationOption(
                label=opt.label,
                tool=opt.tool,
                action=opt.action,
                parameters=params,
                confidence=opt.confidence,
            ))
        return filled

    @staticmethod
    def _candidates_to_options(candidates: List[Any]) -> List[ClarificationOption]:
        """Convert ToolCandidate objects to ClarificationOptions."""
        _INTENT_LABELS: Dict[str, str] = {
            "waste_search": "consulter les déchets",
            "waste_get": "obtenir un code déchet",
            "nomenclature_search": "rechercher dans la nomenclature",
            "bsd_search": "rechercher un bordereau",
            "declaration_search": "rechercher une déclaration",
            "regulation_search": "consulter la réglementation",
            "inspection_search": "rechercher une inspection",
            "partner_search": "rechercher un partenaire",
            "traceability_search": "rechercher dans la traçabilité",
            "statistiques": "consulter les statistiques",
            "dashboard": "voir le tableau de bord",
            "notification_list": "consulter les notifications",
        }
        options: List[ClarificationOption] = []
        for c in candidates:
            tool = getattr(c, "tool", "unknown")
            intent = getattr(c, "intent", "")
            conf = getattr(c, "confidence", 0.0)
            params = getattr(c, "parameters", {})
            label = _INTENT_LABELS.get(intent, intent or tool)
            options.append(ClarificationOption(
                label=label,
                tool=tool,
                action=intent,
                parameters=params,
                confidence=conf,
            ))
        return options

    # -- Question formatting ---------------------------------------------

    @staticmethod
    def _format_reference_question(
        ref_text: str,
        options: List[ClarificationOption],
    ) -> str:
        """Format a clarification question for ambiguous references."""
        numbered = "\n".join(
            f"  {i}. {opt.label}" for i, opt in enumerate(options, 1)
        )
        return (
            f"J'ai trouvé plusieurs interprétations possibles pour « {ref_text} ».\n"
            f"Est-ce :\n{numbered}\n\n"
            f"Répondez avec le numéro de votre choix ou décrivez ce que vous recherchez."
        )

    @staticmethod
    def _format_routing_question(options: List[ClarificationOption]) -> str:
        """Format a clarification question for ambiguous routing."""
        numbered = "\n".join(
            f"  {i}. {opt.label}" for i, opt in enumerate(options, 1)
        )
        return (
            f"Je ne suis pas sûr de comprendre votre demande.\n"
            f"Vouliez-vous :\n{numbered}\n\n"
            f"Répondez avec le numéro de votre choix ou décrivez ce que vous recherchez."
        )
