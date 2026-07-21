"""
AI Reasoning Policy — framework-independent, deterministic reasoning layer.

Zero tool execution.  Zero repository access.  Zero Django coupling.

Responsibilities:
    1. User Understanding      — normalise and characterise user input
    2. Language Detection      — detect FR / EN / AR and dialect hints
    3. Intent Detection        — deterministic regex classification
    4. Entity Extraction       — regex-based structured data extraction
    5. Reference Classification — disambiguate numeric / coded references
    6. Confidence Evaluation   — weighted composite scoring
    7. Business Knowledge Priority — enforce "company data before model data"
    8. Tool Decision           — select the best tool from candidates
    9. Parameter Validation    — ensure all required parameters exist
   10. Response Validation     — verify output contract integrity
   11. Clarification Rules     — decide when to ask the user

Architecture:
    AIReasoningPolicy.analyze(message) → ReasoningResult
        → steps: List[ReasoningStep]      # per-step audit trail
        → language: LanguageInfo           # detected language
        → intent: IntentAnalysis          # intent + tool mapping
        → entities: EntityAnalysis        # extracted entities + refs
        → confidence: ConfidenceReport    # weighted scoring
        → tool_decision: ToolDecision     # final tool selection
        → parameter_report: ParameterReport
        → response_validation: ResponseValidation
        → clarification: ClarificationDecision

Design Rules:
    - Never guess — if confidence < 80 % → clarification
    - Never execute the wrong tool — parameter validation blocks mismatches
    - Business knowledge BEFORE model knowledge (priority layer)
    - Does NOT modify any existing module — pure additive
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD: float = 0.80

# Weights for confidence scoring (sum = 1.0)
WEIGHT_INTENT: float = 0.30
WEIGHT_REFERENCES: float = 0.15
WEIGHT_ENTITIES: float = 0.10
WEIGHT_SEARCH: float = 0.15
WEIGHT_TOOL_SELECTION: float = 0.30

# Supported languages
_LANG_FR = "fr"
_LANG_EN = "en"
_LANG_AR = "ar"
_LANG_UNKNOWN = "unknown"

# Language detection keywords
_FR_KEYWORDS: Tuple[str, ...] = (
    "quels", "quelles", "quel", "quelle", "comment", "pourquoi",
    "est-ce", "c'est", "cette", "cet", "ces", "dans", "avec",
    "pour", "sur", "sous", "mais", "donc", "car", "oui", "non",
    "merci", "bonjour", "salut", "aide", "besoin", "recherche",
    "déchet", "déchets", "nomenclature", "glossaire", "réglementation",
    "déclaration", "transporteur", "producteur", "entreprise",
    "bordereau", "livraison", "commande", "inspection", "traçabilité",
    "rapport", "statistiques", "tableau", "tableau de bord",
    "danger", "dangereux", "non-dangereux", "tri", "recyclage",
    "élimination", " valorisation", "stockage", "elimination",
    "agrément", "agrément", "capacité", "spécialisation",
    "qu'est-ce", "qu'avez", "pouvez", "pouvoir", "savoir",
)

_EN_KEYWORDS: Tuple[str, ...] = (
    "what", "which", "how", "why", "when", "where", "who",
    "is", "are", "does", "do", "can", "could", "would",
    "the", "this", "that", "these", "those",
    "waste", "nomenclature", "glossary", "regulation",
    "declaration", "transporter", "producer", "company",
    "bordereau", "delivery", "order", "inspection", "traceability",
    "report", "statistics", "dashboard", "dangerous", "hazardous",
    "recycling", "disposal", "storage", "treatment",
)

_AR_KEYWORDS: Tuple[str, ...] = (
    "ما", "كيف", "لماذا", "أين", "متى", "من", "أي",
    "هل", "هذا", "هذه", "ذلك", "تلك",
    "نفايات", "مخلفات", "cadeau",
)

# Response validation regex patterns
_WASTE_CODE_RE = re.compile(r"\b(\d{1,2}\.\d{2}\.\d{2})\b")
_BSD_NUMBER_RE = re.compile(r"\b(BSD[- ]?\d{4,})\b", re.IGNORECASE)
_BC_NUMBER_RE = re.compile(r"\b(BC[- ]?\d{4,})\b", re.IGNORECASE)
_BL_NUMBER_RE = re.compile(r"\b(BL[- ]?\d{4,})\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
    r"|\b(\d{4}-\d{2}-\d{2})\b",
)
_QUANTITY_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(tonnes?|kg|kilos?|litres?|l|m³|m3)\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b(\d+(?:[.,]\d+)?\s*%)")
_EMAIL_RE = re.compile(r"\b([\w.+-]+@[\w-]+\.[\w.-]+)\b")
_AGREMENT_RE = re.compile(r"\b(AGR[- ]?\d{4,})\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


# ══════════════════════════════════════════════════════════════════════
# Data Contracts
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ReasoningStep:
    """Single step in the reasoning audit trail."""

    step: str
    input_summary: str
    output_summary: str
    confidence: float
    reasoning: str
    elapsed_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "step": self.step,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
        }
        if self.elapsed_ms:
            d["elapsed_ms"] = round(self.elapsed_ms, 2)
        if self.details:
            d["details"] = self.details
        return d


@dataclass(frozen=True)
class LanguageInfo:
    """Detected language and confidence."""

    language: str = _LANG_UNKNOWN
    confidence: float = 0.0
    is_bilingual: bool = False
    detected_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "language": self.language,
            "confidence": round(self.confidence, 3),
        }
        if self.is_bilingual:
            d["is_bilingual"] = True
        if self.detected_keywords:
            d["detected_keywords"] = self.detected_keywords
        return d


@dataclass(frozen=True)
class IntentAnalysis:
    """Detected intent with tool mapping and confidence."""

    intent: str = "unknown"
    tool: str = "none"
    confidence: float = 0.0
    is_greeting: bool = False
    is_question: bool = False
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "intent": self.intent,
            "tool": self.tool,
            "confidence": round(self.confidence, 3),
        }
        if self.is_greeting:
            d["is_greeting"] = True
        if self.is_question:
            d["is_question"] = True
        if self.candidates:
            d["candidates"] = self.candidates
        return d


@dataclass(frozen=True)
class EntityAnalysis:
    """Extracted entities and classified references."""

    waste_codes: List[str] = field(default_factory=list)
    bsd_numbers: List[str] = field(default_factory=list)
    bc_numbers: List[str] = field(default_factory=list)
    bl_numbers: List[str] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    quantities: List[str] = field(default_factory=list)
    percentages: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    agrement_numbers: List[str] = field(default_factory=list)
    years: List[str] = field(default_factory=list)
    classified_references: List[Dict[str, Any]] = field(default_factory=list)
    total_entities: int = 0

    @property
    def has_entities(self) -> bool:
        return self.total_entities > 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"total_entities": self.total_entities}
        entity_lists = {
            "waste_codes": self.waste_codes,
            "bsd_numbers": self.bsd_numbers,
            "bc_numbers": self.bc_numbers,
            "bl_numbers": self.bl_numbers,
            "dates": self.dates,
            "quantities": self.quantities,
            "percentages": self.percentages,
            "emails": self.emails,
            "agrement_numbers": self.agrement_numbers,
            "years": self.years,
        }
        for key, lst in entity_lists.items():
            if lst:
                d[key] = lst
        if self.classified_references:
            d["classified_references"] = self.classified_references
        return d


@dataclass(frozen=True)
class ConfidenceReport:
    """Weighted confidence scoring breakdown."""

    overall: float = 0.0
    passes_threshold: bool = False
    breakdown: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "overall": round(self.overall, 4),
            "passes_threshold": self.passes_threshold,
            "threshold": CONFIDENCE_THRESHOLD,
        }
        if self.breakdown:
            d["breakdown"] = {
                k: round(v, 4) for k, v in self.breakdown.items()
            }
        if self.weights:
            d["weights"] = self.weights
        return d


@dataclass(frozen=True)
class BusinessKnowledgeDirective:
    """Directive for business knowledge priority enforcement."""

    must_search_business_first: bool = True
    company_data_before_model: bool = True
    rag_always_run: bool = True
    search_before_llm: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "must_search_business_first": self.must_search_business_first,
            "company_data_before_model": self.company_data_before_model,
            "rag_always_run": self.rag_always_run,
            "search_before_llm": self.search_before_llm,
        }


@dataclass(frozen=True)
class ToolDecision:
    """Final tool selection decision."""

    tool: str = "none"
    action: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    source: str = ""
    needs_search_fallback: bool = False
    candidate_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "tool": self.tool,
            "action": self.action,
            "parameters": dict(self.parameters),
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }
        if self.needs_search_fallback:
            d["needs_search_fallback"] = True
        if self.candidate_count:
            d["candidate_count"] = self.candidate_count
        return d


@dataclass(frozen=True)
class ParameterReport:
    """Parameter validation result."""

    valid: bool = False
    missing: List[Dict[str, str]] = field(default_factory=list)
    tool_name: str = ""
    action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "valid": self.valid,
            "tool_name": self.tool_name,
        }
        if self.action:
            d["action"] = self.action
        if self.missing:
            d["missing"] = self.missing
        return d


@dataclass(frozen=True)
class ResponseValidation:
    """Validation of the reasoning output contract."""

    valid: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"valid": self.valid}
        if self.errors:
            d["errors"] = self.errors
        return d


@dataclass(frozen=True)
class ClarificationDecision:
    """Decision on whether clarification is needed."""

    needed: bool = False
    reason: str = ""
    question: str = ""
    options: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"needed": self.needed}
        if self.reason:
            d["reason"] = self.reason
        if self.question:
            d["question"] = self.question
        if self.options:
            d["options"] = self.options
        return d


@dataclass(frozen=True)
class ReasoningResult:
    """Complete reasoning analysis result with full audit trail."""

    message: str
    steps: List[ReasoningStep]
    language: LanguageInfo
    intent: IntentAnalysis
    entities: EntityAnalysis
    confidence: ConfidenceReport
    business_knowledge: BusinessKnowledgeDirective
    tool_decision: ToolDecision
    parameter_report: ParameterReport
    response_validation: ResponseValidation
    clarification: ClarificationDecision
    total_elapsed_ms: float = 0.0

    @property
    def should_proceed(self) -> bool:
        """True if the reasoning chain is complete and no clarification needed."""
        return (
            self.confidence.passes_threshold
            and not self.clarification.needed
            and self.tool_decision.tool != "none"
            and self.parameter_report.valid
        )

    @property
    def needs_clarification(self) -> bool:
        return self.clarification.needed

    @property
    def tool_name(self) -> str:
        return self.tool_decision.tool

    @property
    def action(self) -> str:
        return self.tool_decision.action

    @property
    def parameters(self) -> Dict[str, Any]:
        return dict(self.tool_decision.parameters)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "steps": [s.to_dict() for s in self.steps],
            "language": self.language.to_dict(),
            "intent": self.intent.to_dict(),
            "entities": self.entities.to_dict(),
            "confidence": self.confidence.to_dict(),
            "business_knowledge": self.business_knowledge.to_dict(),
            "tool_decision": self.tool_decision.to_dict(),
            "parameter_report": self.parameter_report.to_dict(),
            "response_validation": self.response_validation.to_dict(),
            "clarification": self.clarification.to_dict(),
            "should_proceed": self.should_proceed,
            "total_elapsed_ms": round(self.total_elapsed_ms, 2),
        }


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════


def _elapsed_ms(start: float) -> float:
    return (time.monotonic() - start) * 1000


def _truncate(text: str, max_len: int = 80) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _normalize(text: str) -> str:
    """Lower-case, collapse whitespace, strip accents for matching."""
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


# ── Intent → Action mapping (deterministic) ───────────────────────────

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

# Tools that need a `query` parameter when the router provides none
_QUERY_TOOLS: frozenset[str] = frozenset({
    "waste_tool", "declaration_tool", "nomenclature_tool",
    "glossaire_tool", "bsd_tool", "bc_tool", "bl_tool",
    "producteur_tool", "transporteur_tool", "partner_tool",
    "entreprise_tool", "inspection_tool", "traceability_tool",
    "reglementation_tool", "rapport_tool", "statistiques_tool",
})

# Greeting patterns (FR / EN)
_GREETING_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(bonjour|salut|bonsoir|hello|hi|hey|coucou|bonne ?journée"
        r"|bonne ?soirée|good ?morning|good ?afternoon|good ?evening)\b",
        re.IGNORECASE,
    ),
)

# Question indicators
_QUESTION_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\?", re.IGNORECASE),
    re.compile(
        r"\b(qu['o]|comment|pourquoi|est-ce|how|why|what|which|where"
        r"|when|who|can |could |would |does |do |is |are )\b",
        re.IGNORECASE,
    ),
)


# ══════════════════════════════════════════════════════════════════════
# AI Reasoning Policy
# ══════════════════════════════════════════════════════════════════════


class AIReasoningPolicy:
    """
    Framework-independent deterministic reasoning policy.

    Wraps existing enterprise components (AI Router, ReferenceClassifier,
    ToolParameterValidator) without executing tools or accessing data.

    Usage:
        policy = AIReasoningPolicy()
        result = policy.analyze("Quels sont les déchets dangereux ?")
        if result.should_proceed:
            # pass result.tool_decision to the orchestrator
        elif result.needs_clarification:
            # send result.clarification.question to the user
    """

    def __init__(self) -> None:
        self._router: Any = None
        self._ref_classifier: Any = None
        self._param_validator: Any = None

    # ── Lazy singletons ────────────────────────────────────────────────

    def _get_router(self) -> Any:
        if self._router is None:
            from apps.ai_assistant.enterprise.ai_router import AIRouter
            self._router = AIRouter()
        return self._router

    def _get_ref_classifier(self) -> Any:
        if self._ref_classifier is None:
            from apps.ai_assistant.enterprise.reference_classifier import (
                ReferenceClassifier,
            )
            self._ref_classifier = ReferenceClassifier()
        return self._ref_classifier

    def _get_param_validator(self) -> Any:
        if self._param_validator is None:
            from apps.ai_assistant.enterprise.parameter_validator import (
                ToolParameterValidator,
            )
            self._param_validator = ToolParameterValidator()
        return self._param_validator

    # ══════════════════════════════════════════════════════════════════
    # Main Entry Point
    # ══════════════════════════════════════════════════════════════════

    def analyze(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReasoningResult:
        """
        Run the full 11-step reasoning analysis.

        Returns a complete ReasoningResult with audit trail.
        Never executes tools, never accesses repositories.
        """
        engine_start = time.monotonic()
        ctx = context or {}
        steps: List[ReasoningStep] = []

        # ── Step 1: User Understanding ──────────────────────────────
        step1, normalised = self._step_user_understanding(message, ctx)
        steps.append(step1)

        # Early exit: empty / None message → immediate clarification
        if step1.details.get("is_empty", False):
            lang_info = LanguageInfo()
            intent_info = IntentAnalysis()
            entity_info = EntityAnalysis()
            ref_info = EntityAnalysis()
            conf_report = ConfidenceReport(overall=0.0, passes_threshold=False)
            biz_directive = BusinessKnowledgeDirective()
            tool_decision = ToolDecision(tool="none")
            param_report = ParameterReport(valid=True)
            resp_valid = ResponseValidation(valid=True)
            clarif = ClarificationDecision(
                needed=True,
                reason="empty_message",
                question="Je n'ai pas reçu de message. Pouvez-vous reformuler ?",
            )
            steps.append(
                self._make_passthrough_step("2_language_detection", lang_info)
            )
            steps.append(
                self._make_passthrough_step("3_intent_detection", intent_info)
            )
            steps.append(
                self._make_passthrough_step("4_entity_extraction", entity_info)
            )
            steps.append(
                self._make_passthrough_step(
                    "5_reference_classification", ref_info,
                )
            )
            steps.append(
                self._make_passthrough_step("6_confidence_evaluation", conf_report)
            )
            steps.append(
                self._make_passthrough_step(
                    "7_business_knowledge_priority", biz_directive,
                )
            )
            steps.append(
                self._make_passthrough_step("8_tool_decision", tool_decision)
            )
            steps.append(
                self._make_passthrough_step("9_parameter_validation", param_report)
            )
            steps.append(
                self._make_passthrough_step("10_response_validation", resp_valid)
            )
            steps.append(
                self._make_passthrough_step("11_clarification_rules", clarif)
            )
            return ReasoningResult(
                message=message or "",
                steps=steps,
                language=lang_info,
                intent=intent_info,
                entities=entity_info,
                confidence=conf_report,
                business_knowledge=biz_directive,
                tool_decision=tool_decision,
                parameter_report=param_report,
                response_validation=resp_valid,
                clarification=clarif,
                total_elapsed_ms=_elapsed_ms(engine_start),
            )

        # ── Step 2: Language Detection ──────────────────────────────
        step2, lang_info = self._step_language_detection(message, normalised)
        steps.append(step2)

        # ── Step 3: Intent Detection ────────────────────────────────
        step3, intent_info = self._step_intent_detection(message, normalised)
        steps.append(step3)

        # ── Step 4: Entity Extraction ───────────────────────────────
        step4, entity_info = self._step_entity_extraction(message, ctx)
        steps.append(step4)

        # ── Step 5: Reference Classification ────────────────────────
        step5, ref_info = self._step_reference_classification(
            message, entity_info,
        )
        steps.append(step5)

        # ── Step 6: Confidence Evaluation ───────────────────────────
        step6, conf_report = self._step_confidence_evaluation(
            intent_info, entity_info, ref_info,
        )
        steps.append(step6)

        # ── Step 7: Business Knowledge Priority ─────────────────────
        step7, biz_directive = self._step_business_knowledge_priority(
            intent_info, conf_report,
        )
        steps.append(step7)

        # ── Step 8: Tool Decision ───────────────────────────────────
        step8, tool_decision = self._step_tool_decision(
            message, intent_info, conf_report,
        )
        steps.append(step8)

        # ── Step 9: Parameter Validation ────────────────────────────
        step9, param_report = self._step_parameter_validation(
            tool_decision,
        )
        steps.append(step9)

        # ── Step 10: Response Validation ────────────────────────────
        step10, resp_valid = self._step_response_validation(
            message, intent_info, entity_info, tool_decision, param_report,
        )
        steps.append(step10)

        # ── Step 11: Clarification Rules ────────────────────────────
        step11, clarif = self._step_clarification_rules(
            conf_report, tool_decision, param_report, intent_info,
        )
        steps.append(step11)

        total_elapsed = _elapsed_ms(engine_start)

        return ReasoningResult(
            message=message,
            steps=steps,
            language=lang_info,
            intent=intent_info,
            entities=ref_info,
            confidence=conf_report,
            business_knowledge=biz_directive,
            tool_decision=tool_decision,
            parameter_report=param_report,
            response_validation=resp_valid,
            clarification=clarif,
            total_elapsed_ms=total_elapsed,
        )

    def _make_passthrough_step(
        self, step_name: str, data: Any,
    ) -> ReasoningStep:
        """Create a passthrough step for early-exit paths."""
        summary = "SKIPPED (early exit)"
        details: Dict[str, Any] = {}
        if hasattr(data, "to_dict"):
            details = data.to_dict()
        elif isinstance(data, dict):
            details = data
        return ReasoningStep(
            step=step_name,
            input_summary="",
            output_summary=summary,
            confidence=0.0,
            reasoning="Pas d'analyse — message vide",
            elapsed_ms=0.0,
            details=details,
        )

    # ══════════════════════════════════════════════════════════════════
    # Step Implementations
    # ══════════════════════════════════════════════════════════════════

    # ── Step 1: User Understanding ──────────────────────────────────

    def _step_user_understanding(
        self, message: str, context: Dict[str, Any],
    ) -> Tuple[ReasoningStep, str]:
        """Normalise and characterise user input."""
        s = time.monotonic()
        raw = message or ""
        normalised = _normalize(raw)
        char_count = len(raw)
        word_count = len(raw.split())
        is_empty = char_count == 0

        summary = (
            f"{word_count} mots, {char_count} caractères"
            if not is_empty
            else "EMPTY"
        )
        reasoning = (
            "Message valide avec contenu" if not is_empty
            else "Message vide — clarification requise"
        )
        confidence = 1.0 if not is_empty else 0.0

        return ReasoningStep(
            step="1_user_understanding",
            input_summary=_truncate(raw),
            output_summary=summary,
            confidence=confidence,
            reasoning=reasoning,
            elapsed_ms=_elapsed_ms(s),
            details={
                "char_count": char_count,
                "word_count": word_count,
                "is_empty": is_empty,
            },
        ), normalised

    # ── Step 2: Language Detection ──────────────────────────────────

    def _step_language_detection(
        self, message: str, normalised: str,
    ) -> Tuple[ReasoningStep, LanguageInfo]:
        """Detect the language of the user message (FR / EN / AR)."""
        s = time.monotonic()

        fr_hits = sum(1 for kw in _FR_KEYWORDS if kw in normalised)
        en_hits = sum(1 for kw in _EN_KEYWORDS if kw in normalised)
        ar_hits = sum(1 for kw in _AR_KEYWORDS if kw in normalised)

        total = fr_hits + en_hits + ar_hits
        detected_kws: List[str] = []

        if fr_hits:
            detected_kws.extend(
                [kw for kw in _FR_KEYWORDS if kw in normalised][:3]
            )
        if en_hits:
            detected_kws.extend(
                [kw for kw in _EN_KEYWORDS if kw in normalised][:3]
            )

        if fr_hits > en_hits and fr_hits > ar_hits:
            lang = _LANG_FR
            conf = min(1.0, 0.6 + fr_hits * 0.1)
        elif en_hits > fr_hits and en_hits > ar_hits:
            lang = _LANG_EN
            conf = min(1.0, 0.6 + en_hits * 0.1)
        elif ar_hits > 0:
            lang = _LANG_AR
            conf = min(1.0, 0.6 + ar_hits * 0.1)
        elif fr_hits > 0:
            lang = _LANG_FR
            conf = 0.5
        elif en_hits > 0:
            lang = _LANG_EN
            conf = 0.5
        else:
            lang = _LANG_UNKNOWN
            conf = 0.0

        is_bilingual = (
            (fr_hits > 0 and en_hits > 0 and abs(fr_hits - en_hits) <= 2)
            or (fr_hits > 0 and ar_hits > 0 and abs(fr_hits - ar_hits) <= 2)
            or (en_hits > 0 and ar_hits > 0 and abs(en_hits - ar_hits) <= 2)
        )

        lang_info = LanguageInfo(
            language=lang,
            confidence=conf,
            is_bilingual=is_bilingual,
            detected_keywords=detected_kws[:5],
        )

        summary = f"lang={lang} (conf={conf:.2f})"
        if is_bilingual:
            summary += " [bilingue]"

        return ReasoningStep(
            step="2_language_detection",
            input_summary=_truncate(message),
            output_summary=summary,
            confidence=conf,
            reasoning=f"Détection basée sur {total} mot(s)-clé(s)",
            elapsed_ms=_elapsed_ms(s),
            details={
                "language": lang,
                "fr_hits": fr_hits,
                "en_hits": en_hits,
                "ar_hits": ar_hits,
                "is_bilingual": is_bilingual,
            },
        ), lang_info

    # ── Step 3: Intent Detection ────────────────────────────────────

    def _step_intent_detection(
        self, message: str, normalised: str,
    ) -> Tuple[ReasoningStep, IntentAnalysis]:
        """Detect user intent via the deterministic AI Router."""
        s = time.monotonic()

        # Check greeting first (no LLM needed)
        is_greeting = any(p.search(normalised) for p in _GREETING_PATTERNS)
        if is_greeting:
            intent_info = IntentAnalysis(
                intent="greeting",
                tool="greeting",
                confidence=1.0,
                is_greeting=True,
            )
            return ReasoningStep(
                step="3_intent_detection",
                input_summary=_truncate(message),
                output_summary="intent=greeting",
                confidence=1.0,
                reasoning="Salutation détectée",
                elapsed_ms=_elapsed_ms(s),
                details=intent_info.to_dict(),
            ), intent_info

        # Check question
        is_question = any(p.search(message) for p in _QUESTION_PATTERNS)

        # Route via AI Router
        try:
            routing = self._get_router().classify(message)
            if routing is not None:
                candidates = [
                    c.to_dict() for c in routing.candidates
                ] if routing.candidates else []
                intent_info = IntentAnalysis(
                    intent=routing.intent,
                    tool=routing.tool,
                    confidence=routing.confidence,
                    is_greeting=False,
                    is_question=is_question,
                    candidates=candidates,
                )
                summary = (
                    f"intent={routing.intent}, tool={routing.tool}"
                    f" (conf={routing.confidence:.2f})"
                )
                return ReasoningStep(
                    step="3_intent_detection",
                    input_summary=_truncate(message),
                    output_summary=summary,
                    confidence=routing.confidence,
                    reasoning=f"Intent '{routing.intent}' détecté par AI Router",
                    elapsed_ms=_elapsed_ms(s),
                    details=intent_info.to_dict(),
                ), intent_info
        except Exception as exc:
            logger.warning("AI Router failed: %s", exc)

        # Fallback: question or unknown
        intent = "question" if is_question else "unknown"
        intent_info = IntentAnalysis(
            intent=intent,
            tool="none",
            confidence=0.3 if is_question else 0.1,
            is_greeting=False,
            is_question=is_question,
        )
        return ReasoningStep(
            step="3_intent_detection",
            input_summary=_truncate(message),
            output_summary=f"intent={intent} (fallback)",
            confidence=intent_info.confidence,
            reasoning="AI Router indisponible — fallback",
            elapsed_ms=_elapsed_ms(s),
            details=intent_info.to_dict(),
        ), intent_info

    # ── Step 4: Entity Extraction ───────────────────────────────────

    def _step_entity_extraction(
        self, message: str, context: Dict[str, Any],
    ) -> Tuple[ReasoningStep, EntityAnalysis]:
        """Extract structured entities via regex patterns."""
        s = time.monotonic()

        waste_codes = list(set(_WASTE_CODE_RE.findall(message)))
        bsd_numbers = list(set(
            m.group(1) for m in _BSD_NUMBER_RE.finditer(message)
        ))
        bc_numbers = list(set(
            m.group(1) for m in _BC_NUMBER_RE.finditer(message)
        ))
        bl_numbers = list(set(
            m.group(1) for m in _BL_NUMBER_RE.finditer(message)
        ))
        dates_raw = _DATE_RE.findall(message)
        dates = list(set(d for t in dates_raw for d in t if d))
        quantities = list(set(
            m.group(0) for m in _QUANTITY_RE.finditer(message)
        ))
        percentages = list(set(
            m.group(0) for m in _PERCENT_RE.finditer(message)
        ))
        emails = list(set(_EMAIL_RE.findall(message)))
        agrement_numbers = list(set(
            m.group(1) for m in _AGREMENT_RE.finditer(message)
        ))
        years = list(set(
            y for y in _YEAR_RE.findall(message) if 2000 <= int(y) <= 2100
        ))

        total = (
            len(waste_codes) + len(bsd_numbers) + len(bc_numbers)
            + len(bl_numbers) + len(dates) + len(quantities)
            + len(percentages) + len(emails) + len(agrement_numbers)
            + len(years)
        )

        entity_info = EntityAnalysis(
            waste_codes=waste_codes,
            bsd_numbers=bsd_numbers,
            bc_numbers=bc_numbers,
            bl_numbers=bl_numbers,
            dates=dates,
            quantities=quantities,
            percentages=percentages,
            emails=emails,
            agrement_numbers=agrement_numbers,
            years=years,
            total_entities=total,
        )

        summary_parts: List[str] = []
        entity_map = {
            "waste_codes": waste_codes,
            "bsd_numbers": bsd_numbers,
            "bc_numbers": bc_numbers,
            "bl_numbers": bl_numbers,
            "dates": dates,
            "quantities": quantities,
            "percentages": percentages,
            "emails": emails,
            "agrement_numbers": agrement_numbers,
            "years": years,
        }
        for key, lst in entity_map.items():
            if lst:
                summary_parts.append(f"{key}:{len(lst)}")

        summary = (
            f"{total} entité(s) — {', '.join(summary_parts)}"
            if total > 0
            else "aucune"
        )
        conf = min(1.0, 0.7 + total * 0.075)

        return ReasoningStep(
            step="4_entity_extraction",
            input_summary=_truncate(message),
            output_summary=summary,
            confidence=conf,
            reasoning=f"{total} entité(s) extraite(s) par regex",
            elapsed_ms=_elapsed_ms(s),
            details=entity_info.to_dict(),
        ), entity_info

    # ── Step 5: Reference Classification ────────────────────────────

    def _step_reference_classification(
        self, message: str, entities: EntityAnalysis,
    ) -> Tuple[ReasoningStep, EntityAnalysis]:
        """Disambiguate numeric references via ReferenceClassifier."""
        s = time.monotonic()

        refs: List[Dict[str, Any]] = []
        rc = self._get_ref_classifier()

        # Classify waste codes
        for code in entities.waste_codes:
            try:
                result = rc.classify(code)
                if result and result.reference_type:
                    refs.append({
                        "reference": code,
                        "reference_type": result.reference_type,
                        "confidence": round(result.confidence, 3),
                    })
            except Exception:
                refs.append({
                    "reference": code,
                    "reference_type": "waste_code",
                    "confidence": 0.8,
                })

        # Classify BSD numbers
        for num in entities.bsd_numbers:
            refs.append({
                "reference": num,
                "reference_type": "bsd_number",
                "confidence": 0.95,
            })

        # Classify BC numbers
        for num in entities.bc_numbers:
            refs.append({
                "reference": num,
                "reference_type": "bc_number",
                "confidence": 0.95,
            })

        # Classify BL numbers
        for num in entities.bl_numbers:
            refs.append({
                "reference": num,
                "reference_type": "bl_number",
                "confidence": 0.95,
            })

        # Classify agrément numbers
        for num in entities.agrement_numbers:
            refs.append({
                "reference": num,
                "reference_type": "agrement_number",
                "confidence": 0.90,
            })

        # Update entities with classified references
        updated_entities = EntityAnalysis(
            waste_codes=entities.waste_codes,
            bsd_numbers=entities.bsd_numbers,
            bc_numbers=entities.bc_numbers,
            bl_numbers=entities.bl_numbers,
            dates=entities.dates,
            quantities=entities.quantities,
            percentages=entities.percentages,
            emails=entities.emails,
            agrement_numbers=entities.agrement_numbers,
            years=entities.years,
            classified_references=refs,
            total_entities=entities.total_entities,
        )

        ref_count = len(refs)
        avg_conf = (
            sum(r["confidence"] for r in refs) / ref_count
            if ref_count > 0
            else 0.7
        )
        summary = (
            f"{ref_count} référence(s) classifiée(s)"
            if ref_count > 0
            else "NONE"
        )

        return ReasoningStep(
            step="5_reference_classification",
            input_summary=_truncate(message),
            output_summary=summary,
            confidence=avg_conf,
            reasoning=f"{ref_count} référence(s) disambiguée(s)",
            elapsed_ms=_elapsed_ms(s),
            details={"references": refs, "count": ref_count},
        ), updated_entities

    # ── Step 6: Confidence Evaluation ───────────────────────────────

    def _step_confidence_evaluation(
        self,
        intent: IntentAnalysis,
        entities: EntityAnalysis,
        refs: EntityAnalysis,
    ) -> Tuple[ReasoningStep, ConfidenceReport]:
        """Compute weighted overall confidence from analysis steps."""
        s = time.monotonic()

        breakdown: Dict[str, float] = {}
        weights: Dict[str, float] = {}

        # Intent confidence (weight 0.30)
        breakdown["intent"] = intent.confidence
        weights["intent"] = WEIGHT_INTENT

        # Reference confidence (weight 0.15)
        ref_list = refs.classified_references
        ref_conf = (
            sum(r.get("confidence", 0.7) for r in ref_list) / len(ref_list)
            if ref_list
            else 0.7
        )
        breakdown["references"] = ref_conf
        weights["references"] = WEIGHT_REFERENCES

        # Entity confidence (weight 0.10)
        entity_conf = min(1.0, 0.7 + entities.total_entities * 0.075)
        breakdown["entities"] = entity_conf
        weights["entities"] = WEIGHT_ENTITIES

        # Search strategy confidence (weight 0.15)
        # Default: 0.75 (neutral — search will refine later)
        search_conf = 0.75
        breakdown["search"] = search_conf
        weights["search"] = WEIGHT_SEARCH

        # Tool selection confidence (weight 0.30)
        tool_conf = intent.confidence
        breakdown["tool_selection"] = tool_conf
        weights["tool_selection"] = WEIGHT_TOOL_SELECTION

        # Weighted sum
        weighted = (
            breakdown["intent"] * WEIGHT_INTENT
            + breakdown["references"] * WEIGHT_REFERENCES
            + breakdown["entities"] * WEIGHT_ENTITIES
            + breakdown["search"] * WEIGHT_SEARCH
            + breakdown["tool_selection"] * WEIGHT_TOOL_SELECTION
        )

        passes = weighted >= CONFIDENCE_THRESHOLD

        conf_report = ConfidenceReport(
            overall=weighted,
            passes_threshold=passes,
            breakdown=breakdown,
            weights=weights,
        )

        status = "PASS" if passes else "FAIL"
        summary = f"{status} ({weighted:.4f})"

        return ReasoningStep(
            step="6_confidence_evaluation",
            input_summary=f"intent={intent.intent}",
            output_summary=summary,
            confidence=weighted,
            reasoning=(
                f"Seuil: {CONFIDENCE_THRESHOLD:.0%}, "
                f"score: {weighted:.4f}"
            ),
            elapsed_ms=_elapsed_ms(s),
            details=conf_report.to_dict(),
        ), conf_report

    # ── Step 7: Business Knowledge Priority ─────────────────────────

    def _step_business_knowledge_priority(
        self,
        intent: IntentAnalysis,
        confidence: ConfidenceReport,
    ) -> Tuple[ReasoningStep, BusinessKnowledgeDirective]:
        """
        Enforce business knowledge priority:
        company data MUST be searched BEFORE model knowledge.
        """
        s = time.monotonic()

        directive = BusinessKnowledgeDirective(
            must_search_business_first=True,
            company_data_before_model=True,
            rag_always_run=True,
            search_before_llm=True,
        )

        reasoning = (
            "Priorité données entreprise — RAG et recherche activés"
        )

        return ReasoningStep(
            step="7_business_knowledge_priority",
            input_summary=f"intent={intent.intent}",
            output_summary="BUSINESS_FIRST",
            confidence=1.0,
            reasoning=reasoning,
            elapsed_ms=_elapsed_ms(s),
            details=directive.to_dict(),
        ), directive

    # ── Step 8: Tool Decision ───────────────────────────────────────

    def _step_tool_decision(
        self,
        message: str,
        intent: IntentAnalysis,
        confidence: ConfidenceReport,
    ) -> Tuple[ReasoningStep, ToolDecision]:
        """Select the best tool from AI Router candidates."""
        s = time.monotonic()

        if intent.is_greeting or intent.tool == "greeting":
            td = ToolDecision(
                tool="greeting",
                action="",
                parameters={},
                confidence=1.0,
                source="reasoning:greeting",
            )
            return ReasoningStep(
                step="8_tool_decision",
                input_summary=_truncate(message),
                output_summary="greeting (no tool needed)",
                confidence=1.0,
                reasoning="Salutation — aucun outil requis",
                elapsed_ms=_elapsed_ms(s),
                details=td.to_dict(),
            ), td

        if intent.tool == "none" or intent.confidence < 0.3:
            td = ToolDecision(
                tool="none",
                action="",
                parameters={},
                confidence=intent.confidence,
                source="reasoning:no_match",
                needs_search_fallback=True,
            )
            return ReasoningStep(
                step="8_tool_decision",
                input_summary=_truncate(message),
                output_summary="NO_TOOL (search fallback available)",
                confidence=intent.confidence,
                reasoning="Aucun outil détecté — fallback recherche",
                elapsed_ms=_elapsed_ms(s),
                details=td.to_dict(),
            ), td

        # Build parameters
        tool_name = intent.tool
        action = _INTENT_ACTION_MAP.get(intent.intent, "search")
        parameters: Dict[str, Any] = {"action": action}

        # Inject query for search tools when router provides none
        if tool_name in _QUERY_TOOLS and "query" not in parameters:
            parameters["query"] = message

        td = ToolDecision(
            tool=tool_name,
            action=action,
            parameters=parameters,
            confidence=intent.confidence,
            source="reasoning:ai_router",
            candidate_count=len(intent.candidates),
        )

        summary = f"{tool_name}.{action}"
        return ReasoningStep(
            step="8_tool_decision",
            input_summary=_truncate(message),
            output_summary=summary,
            confidence=intent.confidence,
            reasoning=f"Outil sélectionné : {tool_name}.{action}",
            elapsed_ms=_elapsed_ms(s),
            details=td.to_dict(),
        ), td

    # ── Step 9: Parameter Validation ────────────────────────────────

    def _step_parameter_validation(
        self, tool_decision: ToolDecision,
    ) -> Tuple[ReasoningStep, ParameterReport]:
        """Validate all required parameters before execution."""
        s = time.monotonic()

        tool = tool_decision.tool

        if tool in ("greeting", "none"):
            pr = ParameterReport(
                valid=True,
                missing=[],
                tool_name=tool,
                action=tool_decision.action,
            )
            return ReasoningStep(
                step="9_parameter_validation",
                input_summary=tool,
                output_summary="SKIPPED (no tool)",
                confidence=1.0,
                reasoning="Pas d'outil à valider",
                elapsed_ms=_elapsed_ms(s),
                details=pr.to_dict(),
            ), pr

        try:
            result = self._get_param_validator().validate(
                tool, tool_decision.parameters,
            )
            if result.valid:
                pr = ParameterReport(
                    valid=True,
                    missing=[],
                    tool_name=tool,
                    action=tool_decision.action,
                )
                return ReasoningStep(
                    step="9_parameter_validation",
                    input_summary=f"{tool} params={list(tool_decision.parameters.keys())}",
                    output_summary="VALID",
                    confidence=1.0,
                    reasoning="Tous les paramètres requis sont présents",
                    elapsed_ms=_elapsed_ms(s),
                    details=pr.to_dict(),
                ), pr

            missing = [mp.to_dict() for mp in result.missing_parameters]
            pr = ParameterReport(
                valid=False,
                missing=missing,
                tool_name=tool,
                action=tool_decision.action,
            )
            missing_names = ", ".join(mp.name for mp in result.missing_parameters)
            return ReasoningStep(
                step="9_parameter_validation",
                input_summary=f"{tool} params={list(tool_decision.parameters.keys())}",
                output_summary=f"INVALID — {len(missing)} manquant(s)",
                confidence=0.0,
                reasoning=f"Paramètres manquants : {missing_names}",
                elapsed_ms=_elapsed_ms(s),
                details=pr.to_dict(),
            ), pr
        except Exception as exc:
            logger.warning("Parameter validation crashed: %s", exc)
            pr = ParameterReport(
                valid=False,
                missing=[{"name": "validation_error", "description": str(exc)}],
                tool_name=tool,
                action=tool_decision.action,
            )
            return ReasoningStep(
                step="9_parameter_validation",
                input_summary=tool,
                output_summary="ERROR",
                confidence=0.0,
                reasoning=f"Erreur de validation : {exc}",
                elapsed_ms=_elapsed_ms(s),
                details=pr.to_dict(),
            ), pr

    # ── Step 10: Response Validation ────────────────────────────────

    def _step_response_validation(
        self,
        message: str,
        intent: IntentAnalysis,
        entities: EntityAnalysis,
        tool_decision: ToolDecision,
        param_report: ParameterReport,
    ) -> Tuple[ReasoningStep, ResponseValidation]:
        """Verify output contract integrity."""
        s = time.monotonic()
        errors: List[str] = []

        # Rule: greeting never has tool
        if intent.is_greeting and tool_decision.tool not in ("greeting", "none"):
            errors.append("Greeting ne devrait pas avoir d'outil")

        # Rule: non-greeting must have a tool
        if not intent.is_greeting and tool_decision.tool == "none":
            # This is valid (search fallback), not an error
            pass

        # Rule: if tool selected, parameters must be non-empty
        if tool_decision.tool not in ("greeting", "none"):
            if not tool_decision.parameters:
                errors.append(
                    f"Outil '{tool_decision.tool}' sélectionné "
                    f"sans paramètres"
                )

        # Rule: if parameter validation failed, note it
        if not param_report.valid and param_report.tool_name not in (
            "greeting", "none",
        ):
            errors.append(
                f"Validation paramètres échouée pour "
                f"'{param_report.tool_name}'"
            )

        # Rule: entity count must be consistent
        if entities.total_entities < 0:
            errors.append("Nombre d'entités négatif")

        valid = len(errors) == 0
        rv = ResponseValidation(valid=valid, errors=errors)

        summary = "VALID" if valid else f"INVALID — {len(errors)} erreur(s)"
        conf = 1.0 if valid else 0.0

        return ReasoningStep(
            step="10_response_validation",
            input_summary=_truncate(message),
            output_summary=summary,
            confidence=conf,
            reasoning=(
                "Contrat de sortie valide"
                if valid
                else "; ".join(errors)
            ),
            elapsed_ms=_elapsed_ms(s),
            details=rv.to_dict(),
        ), rv

    # ── Step 11: Clarification Rules ────────────────────────────────

    def _step_clarification_rules(
        self,
        confidence: ConfidenceReport,
        tool_decision: ToolDecision,
        param_report: ParameterReport,
        intent: IntentAnalysis,
    ) -> Tuple[ReasoningStep, ClarificationDecision]:
        """
        Decide whether clarification is needed from the user.

        Triggers (checked in order):
            0. Greeting — never clarify
            1. No tool matched but search fallback available — no clarify
            2. Parameter validation failed — clarify
            3. Confidence below threshold (80 %) — clarify
            4. All checks passed — no clarify
        """
        s = time.monotonic()

        # Rule 0: Greeting → never clarify
        if intent.is_greeting:
            cd = ClarificationDecision(
                needed=False,
                reason="greeting",
            )
            return ReasoningStep(
                step="11_clarification_rules",
                input_summary="greeting",
                output_summary="NOT_NEEDED",
                confidence=1.0,
                reasoning="Pas de clarification pour une salutation",
                elapsed_ms=_elapsed_ms(s),
                details=cd.to_dict(),
            ), cd

        # Rule 1: No tool matched but search fallback is available
        # → the search strategy will handle it, no clarification needed
        if tool_decision.tool == "none" and tool_decision.needs_search_fallback:
            cd = ClarificationDecision(
                needed=False,
                reason="search_fallback",
            )
            return ReasoningStep(
                step="11_clarification_rules",
                input_summary="no tool → search fallback",
                output_summary="NOT_NEEDED (search_fallback)",
                confidence=0.7,
                reasoning=(
                    "Aucun outil — fallback recherche activé"
                ),
                elapsed_ms=_elapsed_ms(s),
                details=cd.to_dict(),
            ), cd

        # Rule 2: Parameter validation failed
        if not param_report.valid and param_report.tool_name not in (
            "greeting", "none",
        ):
            missing_names = [
                m.get("name", "?") for m in param_report.missing
            ]
            cd = ClarificationDecision(
                needed=True,
                reason="missing_parameters",
                question=(
                    f"Pour effectuer cette action, j'ai besoin de : "
                    f"{', '.join(missing_names)}"
                ),
            )
            return ReasoningStep(
                step="11_clarification_rules",
                input_summary=f"missing={missing_names}",
                output_summary="NEEDED (missing_parameters)",
                confidence=0.0,
                reasoning=f"Paramètres manquants : {', '.join(missing_names)}",
                elapsed_ms=_elapsed_ms(s),
                details=cd.to_dict(),
            ), cd

        # Rule 3: Confidence below threshold
        if not confidence.passes_threshold:
            cd = ClarificationDecision(
                needed=True,
                reason="low_confidence",
                question=(
                    "Je ne suis pas assez sûr de votre demande. "
                    "Pouvez-vous préciser ?"
                ),
            )
            return ReasoningStep(
                step="11_clarification_rules",
                input_summary=f"conf={confidence.overall:.4f}",
                output_summary="NEEDED (low_confidence)",
                confidence=confidence.overall,
                reasoning=(
                    f"Confiance {confidence.overall:.4f} < "
                    f"seuil {CONFIDENCE_THRESHOLD:.0%}"
                ),
                elapsed_ms=_elapsed_ms(s),
                details=cd.to_dict(),
            ), cd

        # No clarification needed
        cd = ClarificationDecision(
            needed=False,
            reason="all_checks_passed",
        )
        return ReasoningStep(
            step="11_clarification_rules",
            input_summary="ok",
            output_summary="NOT_NEEDED",
            confidence=1.0,
            reasoning="Tous les contrôles passés",
            elapsed_ms=_elapsed_ms(s),
            details=cd.to_dict(),
        ), cd
