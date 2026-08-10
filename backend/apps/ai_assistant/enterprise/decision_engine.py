"""
AI Decision Engine — structured decision pipeline with full audit trail.

Decision Flow:
    1. User              → receive and normalise the message
    2. Intent Detection  → AI Router regex rules (deterministic, zero LLM cost)
    3. Reference Classification → ReferenceClassifier disambiguates numeric refs
    4. Entity Extraction → regex-based extraction (waste codes, BSD numbers, dates…)
    5. Confidence Score  → weighted composite from steps 2-4
    6. Search Strategy   → AISearchStrategy for short queries / knowledge lookup
    7. Tool Selection    → AI Router ranks candidates, picks best tool
    8. Parameter Validation → ToolParameterValidator ensures all required params exist
    9. Tool Execution    → delegated to the orchestrator (NOT executed here)
   10. Response Generation → delegated to the orchestrator (NOT executed here)

Every step emits a DecisionLog with input, output, confidence, reasoning, and
wall-clock timing.  The final DecisionResult carries the full log trail so the
caller can inspect exactly *why* the engine made its choice.

Rules:
    - Never guess — if confidence < 80 % → clarification
    - Never execute the wrong tool — parameter validation blocks mismatches
    - Does NOT modify any existing module — pure additive
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apps.ai_assistant.enterprise.ai_search_strategy import is_short_query

logger = logging.getLogger(__name__)


# ── Data Contracts ────────────────────────────────────────────────────


@dataclass(frozen=True)
class DecisionLog:
    """Single decision step audit entry."""

    step: str
    input_summary: str
    output_summary: str
    confidence: float
    reasoning: str
    elapsed_ms: float
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "step": self.step,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class DecisionResult:
    """Complete decision output with full audit trail."""

    tool_name: str
    action: Optional[str]
    parameters: Dict[str, Any]
    confidence: float
    logs: List[DecisionLog] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "tool_name": self.tool_name,
            "action": self.action,
            "parameters": self.parameters,
            "confidence": round(self.confidence, 4),
            "needs_clarification": self.needs_clarification,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "logs": [log.to_dict() for log in self.logs],
        }
        if self.needs_clarification:
            d["clarification_question"] = self.clarification_question
            d["clarification_options"] = self.clarification_options
        return d


# ── Confidence Weights ────────────────────────────────────────────────

_STEP_WEIGHTS: Dict[str, float] = {
    "intent_detection": 0.30,
    "reference_classification": 0.15,
    "entity_extraction": 0.10,
    "search_strategy": 0.15,
    "tool_selection": 0.30,
}
# parameter_validation is binary (pass/fail gate), not a confidence contributor.

CONFIDENCE_THRESHOLD: float = 0.80
PARAMETER_GATE_FLOOR: float = 0.60


# ── Helpers ───────────────────────────────────────────────────────────


def _elapsed_ms(start: float) -> float:
    return (time.monotonic() - start) * 1000.0


def _truncate(text: str, length: int = 80) -> str:
    return text if len(text) <= length else text[: length - 3] + "..."


# ── Entity extraction patterns ────────────────────────────────────────

_WASTE_CODE_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{2})\b")
_BSD_NUMBER_RE = re.compile(r"\b(BSD[-\s]?\d{4}[-\s]?\d{3,})\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
_QUANTITY_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?\s*(?:kg|tonnes?|l|litres?))\b", re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b(\d+(?:[.,]\d+)?\s*%)")
_EMAIL_RE = re.compile(r"\b([\w.+-]+@[\w-]+\.[\w.-]+)\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\d{9,12}\b")
_AGREMENT_RE = re.compile(r"\b(AGR[-\s]?\d{4,})\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


# ── Decision Engine ───────────────────────────────────────────────────


class DecisionEngine:
    """
    Structured decision pipeline with full audit trail.

    Does **not** modify any existing module.  Reads from the AI Router,
    ReferenceClassifier, ParameterValidator, and AISearchStrategy; writes
    nothing.  Steps 9-10 (execution, response) are delegated to the caller.
    """

    def __init__(self, container: Any) -> None:
        self._c = container
        self._ai_router: Any = None
        self._reference_classifier: Any = None
        self._parameter_validator: Any = None
        self._search_strategy: Any = None

    # ------------------------------------------------------------------
    # Lazy singletons (import-free from existing modules)
    # ------------------------------------------------------------------

    def _get_router(self) -> Any:
        if self._ai_router is None:
            from apps.ai_assistant.enterprise.ai_router import AIRouter
            self._ai_router = AIRouter()
        return self._ai_router

    def _get_ref_classifier(self) -> Any:
        if self._reference_classifier is None:
            from apps.ai_assistant.enterprise.reference_classifier import ReferenceClassifier
            self._reference_classifier = ReferenceClassifier()
        return self._reference_classifier

    def _get_param_validator(self) -> Any:
        if self._parameter_validator is None:
            from apps.ai_assistant.enterprise.parameter_validator import ToolParameterValidator
            self._parameter_validator = ToolParameterValidator()
        return self._parameter_validator

    def _get_search(self) -> Any:
        if self._search_strategy is None:
            from apps.ai_assistant.enterprise.ai_search_strategy import AISearchStrategy
            self._search_strategy = AISearchStrategy(self._c)
        return self._search_strategy

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def decide(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """
        Run the full 10-step decision flow.

        Steps 1-8 are executed here.  Steps 9-10 are left to the orchestrator.
        """
        ctx = context or {}
        logs: List[DecisionLog] = []
        engine_start = time.monotonic()

        # ── Step 1: User ─────────────────────────────────────────────
        step1 = self._step_receive_user(message, ctx)
        logs.append(step1)
        if not self._passed(step1):
            return self._clarify("Je n'ai pas compris votre message.", logs, engine_start)

        # ── Step 2: Intent Detection ─────────────────────────────────
        step2 = self._step_intent_detection(message, ctx)
        logs.append(step2)
        if not self._passed(step2):
            return self._clarify("Pouvez-vous préciser votre demande ?", logs, engine_start)

        intent_info: Dict[str, Any] = step2.details.get("intent", {})
        intent_name = intent_info.get("intent", "unknown")
        intent_confidence = step2.confidence

        # Greeting → no tool needed
        if intent_name == "greeting":
            return self._success(
                tool_name="greeting",
                action=None,
                parameters={},
                confidence=1.0,
                logs=logs,
                engine_start=engine_start,
            )

        # ── Step 3: Reference Classification ─────────────────────────
        step3 = self._step_reference_classification(message, ctx)
        logs.append(step3)

        # ── Step 4: Entity Extraction ────────────────────────────────
        step4 = self._step_entity_extraction(message, ctx)
        logs.append(step4)

        # ── Step 5: Confidence Score ─────────────────────────────────
        step5 = self._step_confidence_score(logs)
        logs.append(step5)
        if step5.confidence < CONFIDENCE_THRESHOLD:
            return self._clarify(
                "Je ne suis pas assez sûr de votre demande. Pouvez-vous préciser ?",
                logs,
                engine_start,
            )

        # ── Step 6: Search Strategy ──────────────────────────────────
        step6 = self._step_search_strategy(message, ctx)
        logs.append(step6)

        # ── Step 7: Tool Selection ───────────────────────────────────
        step7 = self._step_tool_selection(message, ctx, intent_info)
        logs.append(step7)
        if not self._passed(step7):
            return self._clarify(
                "Je ne suis pas sûr de comprendre votre demande. Pouvez-vous reformuler ?",
                logs,
                engine_start,
            )

        tool_name = step7.details.get("tool_name", "none")
        action = step7.details.get("action")
        parameters = step7.details.get("parameters", {})

        # ── Step 8: Parameter Validation ─────────────────────────────
        step8 = self._step_parameter_validation(tool_name, parameters)
        logs.append(step8)
        if not self._passed(step8):
            missing = step8.details.get("missing", [])
            missing_names = [m.get("name", "?") for m in missing]
            return self._clarify(
                f"Pour effectuer cette action, j'ai besoin de : {', '.join(missing_names)}",
                logs,
                engine_start,
            )

        # ── Step 9 & 10: delegated to orchestrator ───────────────────
        final_confidence = step5.confidence
        return self._success(
            tool_name=tool_name,
            action=action,
            parameters=parameters,
            confidence=final_confidence,
            logs=logs,
            engine_start=engine_start,
        )

    # ------------------------------------------------------------------
    # Step Implementations
    # ------------------------------------------------------------------

    def _step_receive_user(
        self, message: str, context: Dict[str, Any],
    ) -> DecisionLog:
        """Step 1: Receive and validate user input."""
        s = time.monotonic()
        raw = message or ""

        if not raw.strip():
            return DecisionLog(
                step="1_user",
                input_summary=repr(raw),
                output_summary="REJECTED",
                confidence=0.0,
                reasoning="Message vide",
                elapsed_ms=_elapsed_ms(s),
            )
        if len(raw.strip()) < 2:
            return DecisionLog(
                step="1_user",
                input_summary=repr(raw),
                output_summary="REJECTED",
                confidence=0.3,
                reasoning="Message trop court",
                elapsed_ms=_elapsed_ms(s),
            )
        if re.match(r"^[^a-zA-Z0-9]+$", raw.strip()):
            return DecisionLog(
                step="1_user",
                input_summary=repr(raw),
                output_summary="REJECTED",
                confidence=0.2,
                reasoning="Uniquement des caractères spéciaux",
                elapsed_ms=_elapsed_ms(s),
            )

        return DecisionLog(
            step="1_user",
            input_summary=_truncate(raw),
            output_summary="ACCEPTED",
            confidence=1.0,
            reasoning="Message reçu",
            elapsed_ms=_elapsed_ms(s),
            details={"length": len(raw.strip()), "conversation_id": context.get("conversation_id", "")},
        )

    def _step_intent_detection(
        self, message: str, context: Dict[str, Any],
    ) -> DecisionLog:
        """Step 2: Deterministic intent detection via AI Router."""
        s = time.monotonic()
        try:
            result = self._get_router().classify(message)
            if result is None:
                return DecisionLog(
                    step="2_intent_detection",
                    input_summary=_truncate(message),
                    output_summary="NO_INTENT",
                    confidence=0.0,
                    reasoning="Aucune intention détectée par les règles regex",
                    elapsed_ms=_elapsed_ms(s),
                )
            intent_dict = result.to_dict()
            return DecisionLog(
                step="2_intent_detection",
                input_summary=_truncate(message),
                output_summary=f"intent={result.intent}, tool={result.tool}",
                confidence=result.confidence,
                reasoning=f"Intent détecté : {result.intent} → {result.tool}",
                elapsed_ms=_elapsed_ms(s),
                details={"intent": intent_dict},
            )
        except Exception as exc:
            logger.warning("Intent detection failed: %s", exc)
            return DecisionLog(
                step="2_intent_detection",
                input_summary=_truncate(message),
                output_summary="ERROR",
                confidence=0.0,
                reasoning=f"Erreur de détection : {exc}",
                elapsed_ms=_elapsed_ms(s),
            )

    def _step_reference_classification(
        self, message: str, context: Dict[str, Any],
    ) -> DecisionLog:
        """Step 3: Classify any numeric references in the message."""
        s = time.monotonic()
        try:
            tokens = _extract_reference_tokens(message)
            classified: List[Dict[str, Any]] = []
            for token in tokens:
                res = self._get_ref_classifier().classify(token)
                classified.append({
                    "token": token,
                    "reference_type": res.reference_type,
                    "confidence": round(res.confidence, 3),
                })

            if not classified:
                return DecisionLog(
                    step="3_reference_classification",
                    input_summary=_truncate(message),
                    output_summary="NONE",
                    confidence=0.9,
                    reasoning="Aucune référence numérique détectée",
                    elapsed_ms=_elapsed_ms(s),
                    details={"references": []},
                )

            avg_conf = sum(r["confidence"] for r in classified) / len(classified)
            types = [r["reference_type"] for r in classified]
            return DecisionLog(
                step="3_reference_classification",
                input_summary=_truncate(message),
                output_summary=f"{len(classified)} refs: {', '.join(types)}",
                confidence=avg_conf,
                reasoning=f"{len(classified)} référence(s) classifiée(s) : {', '.join(types)}",
                elapsed_ms=_elapsed_ms(s),
                details={"references": classified},
            )
        except Exception as exc:
            logger.warning("Reference classification failed: %s", exc)
            return DecisionLog(
                step="3_reference_classification",
                input_summary=_truncate(message),
                output_summary="ERROR",
                confidence=0.7,
                reasoning=f"Erreur : {exc}",
                elapsed_ms=_elapsed_ms(s),
            )

    def _step_entity_extraction(
        self, message: str, context: Dict[str, Any],
    ) -> DecisionLog:
        """Step 4: Regex-based entity extraction."""
        s = time.monotonic()
        entities: Dict[str, List[str]] = {
            "waste_codes": _WASTE_CODE_RE.findall(message),
            "bsd_numbers": _BSD_NUMBER_RE.findall(message),
            "dates": _DATE_RE.findall(message),
            "quantities": _QUANTITY_RE.findall(message),
            "percentages": _PERCENT_RE.findall(message),
            "emails": _EMAIL_RE.findall(message),
            "agrement_numbers": _AGREMENT_RE.findall(message),
            "years": _YEAR_RE.findall(message),
        }
        total = sum(len(v) for v in entities.values())
        confidence = min(1.0, 0.7 + total * 0.075)

        summary = ", ".join(f"{k}:{len(v)}" for k, v in entities.items() if v) or "aucune"
        return DecisionLog(
            step="4_entity_extraction",
            input_summary=_truncate(message),
            output_summary=f"{total} entité(s) — {summary}",
            confidence=confidence,
            reasoning=f"{total} entité(s) extraite(s)",
            elapsed_ms=_elapsed_ms(s),
            details={"entities": entities, "total": total},
        )

    def _step_confidence_score(self, logs: List[DecisionLog]) -> DecisionLog:
        """Step 5: Compute weighted overall confidence from steps 2-4."""
        s = time.monotonic()
        weighted_sum = 0.0
        total_weight = 0.0
        breakdown: Dict[str, float] = {}

        for log in logs:
            w = _STEP_WEIGHTS.get(log.step.split("_", 1)[1] if "_" in log.step else log.step, 0.0)
            if w > 0:
                weighted_sum += log.confidence * w
                total_weight += w
                breakdown[log.step] = round(log.confidence, 4)

        overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        status = "PASS" if overall >= CONFIDENCE_THRESHOLD else "FAIL"

        return DecisionLog(
            step="5_confidence_score",
            input_summary=f"{len(logs)} steps",
            output_summary=f"{status} ({overall:.4f})",
            confidence=overall,
            reasoning=f"Score global : {overall:.4f} (seuil : {CONFIDENCE_THRESHOLD})",
            elapsed_ms=_elapsed_ms(s),
            details={"breakdown": breakdown, "threshold": CONFIDENCE_THRESHOLD},
        )

    def _step_search_strategy(
        self, message: str, context: Dict[str, Any],
    ) -> DecisionLog:
        """Step 6: Search business knowledge (best-effort, non-blocking)."""
        s = time.monotonic()
        try:
            short = is_short_query(message)
            if not short:
                return DecisionLog(
                    step="6_search_strategy",
                    input_summary=_truncate(message),
                    output_summary="SKIPPED (long query)",
                    confidence=0.8,
                    reasoning="Requête longue — recherche non déclenchée",
                    elapsed_ms=_elapsed_ms(s),
                    details={"is_short": False},
                )

            search_result = self._get_search().search(message)
            if search_result is None or not search_result.has_result:
                return DecisionLog(
                    step="6_search_strategy",
                    input_summary=_truncate(message),
                    output_summary="NO_MATCH",
                    confidence=0.5,
                    reasoning="Requête courte — aucun match trouvé",
                    elapsed_ms=_elapsed_ms(s),
                    details={"is_short": True, "has_result": False},
                )

            best = search_result.best_match
            return DecisionLog(
                step="6_search_strategy",
                input_summary=_truncate(message),
                output_summary=f"MATCH: {best.tool}.{best.action} (score={best.score:.2f})",
                confidence=best.score,
                reasoning=f"Match trouvé via {best.source} : {best.tool}.{best.action}",
                elapsed_ms=_elapsed_ms(s),
                details={
                    "is_short": True,
                    "has_result": True,
                    "source": best.source,
                    "tool": best.tool,
                    "action": best.action,
                    "score": round(best.score, 3),
                },
            )
        except Exception as exc:
            logger.warning("Search strategy failed: %s", exc)
            return DecisionLog(
                step="6_search_strategy",
                input_summary=_truncate(message),
                output_summary="ERROR",
                confidence=0.5,
                reasoning=f"Erreur : {exc}",
                elapsed_ms=_elapsed_ms(s),
            )

    def _step_tool_selection(
        self,
        message: str,
        context: Dict[str, Any],
        intent_info: Dict[str, Any],
    ) -> DecisionLog:
        """Step 7: Select the best tool from the AI Router classification."""
        s = time.monotonic()
        try:
            result = self._get_router().classify(message)
            if result is None or result.tool == "none":
                return DecisionLog(
                    step="7_tool_selection",
                    input_summary=_truncate(message),
                    output_summary="NO_TOOL",
                    confidence=0.0,
                    reasoning="Aucun outil sélectionné",
                    elapsed_ms=_elapsed_ms(s),
                )

            best = result.candidates[0] if result.candidates else None
            tool_name = result.tool
            action = result.parameters.get("action", "")
            parameters = {k: v for k, v in result.parameters.items() if k != "action"}
            # If the router didn't provide an action, infer from intent
            if not action:
                action = _infer_action_from_intent(
                    result.intent, tool_name, message,
                )
                if action:
                    parameters["action"] = action
            # If the router provided no parameters at all, inject the
            # user message as `query` for tools that need it (the AI
            # Router never supplies parameters — Hermes does in the
            # orchestrator, but the DecisionEngine is a standalone
            # audit layer that runs before the orchestrator).
            _QUERY_TOOLS = {
                "waste_tool", "declaration_tool", "nomenclature_tool",
                "glossaire_tool", "bsd_tool", "bc_tool", "bl_tool",
                "producteur_tool", "transporteur_tool", "partner_tool",
                "entreprise_tool", "inspection_tool", "traceability_tool",
                "reglementation_tool", "rapport_tool", "statistiques_tool",
            }
            if not parameters.get("query") and tool_name in _QUERY_TOOLS:
                parameters["query"] = message
            candidate_list = [c.to_dict() for c in result.candidates] if result.candidates else []

            return DecisionLog(
                step="7_tool_selection",
                input_summary=_truncate(message),
                output_summary=f"{tool_name}.{action}",
                confidence=result.confidence,
                reasoning=f"Outil sélectionné : {tool_name}.{action} (confiance : {result.confidence:.3f})",
                elapsed_ms=_elapsed_ms(s),
                details={
                    "tool_name": tool_name,
                    "action": action,
                    "parameters": parameters,
                    "candidates": candidate_list,
                    "candidate_count": len(candidate_list),
                },
            )
        except Exception as exc:
            logger.warning("Tool selection failed: %s", exc)
            return DecisionLog(
                step="7_tool_selection",
                input_summary=_truncate(message),
                output_summary="ERROR",
                confidence=0.0,
                reasoning=f"Erreur : {exc}",
                elapsed_ms=_elapsed_ms(s),
            )

    def _step_parameter_validation(
        self, tool_name: str, parameters: Dict[str, Any],
    ) -> DecisionLog:
        """Step 8: Validate all required parameters before execution."""
        s = time.monotonic()
        if tool_name in ("greeting", "none"):
            return DecisionLog(
                step="8_parameter_validation",
                input_summary=f"{tool_name}",
                output_summary="SKIPPED (no tool)",
                confidence=1.0,
                reasoning="Pas d'outil à valider",
                elapsed_ms=_elapsed_ms(s),
            )
        try:
            result = self._get_param_validator().validate(tool_name, parameters)
            if result.valid:
                return DecisionLog(
                    step="8_parameter_validation",
                    input_summary=f"{tool_name} params={list(parameters.keys())}",
                    output_summary="VALID",
                    confidence=1.0,
                    reasoning="Tous les paramètres requis sont présents",
                    elapsed_ms=_elapsed_ms(s),
                    details={"valid": True, "missing": []},
                )
            missing = [mp.to_dict() for mp in result.missing_parameters]
            return DecisionLog(
                step="8_parameter_validation",
                input_summary=f"{tool_name} params={list(parameters.keys())}",
                output_summary=f"INVALID — {len(missing)} manquant(s)",
                confidence=0.0,
                reasoning=f"Paramètres manquants : {', '.join(mp.name for mp in result.missing_parameters)}",
                elapsed_ms=_elapsed_ms(s),
                details={"valid": False, "missing": missing},
            )
        except Exception as exc:
            logger.warning("Parameter validation failed: %s", exc)
            return DecisionLog(
                step="8_parameter_validation",
                input_summary=f"{tool_name}",
                output_summary="ERROR",
                confidence=0.0,
                reasoning=f"Erreur : {exc}",
                elapsed_ms=_elapsed_ms(s),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _passed(log: DecisionLog) -> bool:
        return log.confidence > 0.0

    def _clarify(
        self,
        question: str,
        logs: List[DecisionLog],
        engine_start: float,
    ) -> DecisionResult:
        return DecisionResult(
            tool_name="none",
            action=None,
            parameters={},
            confidence=0.0,
            logs=logs,
            needs_clarification=True,
            clarification_question=question,
            clarification_options=[],
            elapsed_ms=_elapsed_ms(engine_start),
        )

    def _success(
        self,
        tool_name: str,
        action: Optional[str],
        parameters: Dict[str, Any],
        confidence: float,
        logs: List[DecisionLog],
        engine_start: float,
    ) -> DecisionResult:
        return DecisionResult(
            tool_name=tool_name,
            action=action,
            parameters=parameters,
            confidence=confidence,
            logs=logs,
            needs_clarification=False,
            elapsed_ms=_elapsed_ms(engine_start),
        )


# ── Module Helpers ────────────────────────────────────────────────────


def _extract_reference_tokens(message: str) -> List[str]:
    """
    Extract potential reference tokens from a message.

    Looks for:
        - Dotted numeric codes (15.01.06, 1.3.1)
        - Prefixed document numbers (BSD-2024-001, BC-2023-0042)
        - Year references (2024, 2025)
    """
    tokens: List[str] = []
    # Dotted codes
    tokens.extend(re.findall(r"\b(\d+(?:\.\d+){1,5})\b", message))
    # Prefixed document numbers
    tokens.extend(re.findall(r"\b((?:BSD|BC|BL|TRK|TRA)[-\s]?\d[\w-]*)\b", message, re.IGNORECASE))
    # Deduplicate preserving order
    seen: set[str] = set()
    unique: List[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


# ── Intent → Action mapping ───────────────────────────────────────────

_INTENT_ACTION_MAP: Dict[str, str] = {
    "waste_search": "search",
    "nomenclature": "search",
    "glossary": "search",
    "bsd": "search",
    "bc": "search",
    "bl": "search",
    "company": "search",
    "producer": "search",
    "transporter": "search",
    "partner": "search",
    "report": "report",
    "statistics": "stats",
    "dashboard": "overview",
    "archive": "search",
    "traceability": "search",
    "declaration": "search",
    "inspection": "search",
    "regulation": "search",
    "notification": "list",
    "authentication": "profile",
}


def _infer_action_from_intent(intent: str, tool: str, message: str) -> str:
    """Infer a default action from the intent when the router omits it."""
    # Check explicit mapping
    action = _INTENT_ACTION_MAP.get(intent, "")
    if action:
        return action
    # Fallback: if the message contains "list" / "lister" → "list"
    msg_lower = message.lower()
    if any(w in msg_lower for w in ("lister", "liste", "list", "tous les", "show")):
        return "list"
    # Default to "search" for most tools
    if tool and tool != "none" and tool != "greeting":
        return "search"
    return ""
