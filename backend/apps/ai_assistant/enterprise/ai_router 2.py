"""
AI Router — deterministic message classification and tool routing.

Zero LLM cost. Covers all 18 intents with 100+ regex rules.
Falls back to None when no rule matches (pipeline uses Hermes LLM).

Workflow (classify):
    1. Receive user message
    2. Detect Intent      → regex rules (100+ patterns)
    3. Detect Entities    → regex extraction (waste codes, BSD numbers, etc.)
    4. Detect References  → ReferenceClassifier (waste_code, article, bsd_number, etc.)
    5. Choose Tool        → rank all candidates by confidence
    6. Return result      → NEVER executes a tool before classification

Supported Intents:
    greeting, question, waste_search, nomenclature, glossary,
    bsd, bc, bl, company, producer, transporter, partner,
    report, statistics, dashboard, archive, traceability,
    declaration, inspection, regulation, notification, authentication

Returns:
    classify() → RoutingResult with intent, entities, references, ranked candidates
    route()    → RouteResult (backward-compatible, single best match)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Data Contracts ────────────────────────────────────────────────────


@dataclass(frozen=True)
class RouteResult:
    """Immutable routing decision."""
    intent: str
    confidence: float
    tool: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "tool": self.tool,
        }


@dataclass
class RouteRule:
    """A single routing rule with pattern, tool, and param extractors."""
    pattern: re.Pattern[str]
    intent: str
    tool: str
    confidence: float = 0.95
    priority: int = 0
    param_extractors: Dict[str, Callable[[re.Match, str], Any]] = field(
        default_factory=dict, repr=False,
    )


@dataclass(frozen=True)
class ClassifiedEntity:
    """An extracted entity from the user message."""
    entity_type: str
    value: str
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "value": self.value,
            "confidence": round(self.confidence, 3),
        }


@dataclass(frozen=True)
class ClassifiedReference:
    """A classified numeric reference from ReferenceClassifier."""
    reference: str
    reference_type: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference": self.reference,
            "reference_type": self.reference_type,
            "confidence": round(self.confidence, 3),
        }


@dataclass(frozen=True)
class ToolCandidate:
    """A ranked tool candidate with intent, confidence, and parameters."""
    tool: str
    intent: str
    confidence: float
    priority: int
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: str = "rule"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "priority": self.priority,
            "parameters": self.parameters,
            "source": self.source,
        }


@dataclass(frozen=True)
class RoutingResult:
    """
    Complete classification result from the AI Router pipeline.

    Workflow:
        1. Intent detected (regex rules)
        2. Entities extracted (regex patterns)
        3. References classified (ReferenceClassifier)
        4. Tool candidates ranked by confidence
        5. Best tool selected (never executed before classification)
    """
    intent: str
    confidence: float
    tool: str
    entities: List[ClassifiedEntity] = field(default_factory=list)
    references: List[ClassifiedReference] = field(default_factory=list)
    candidates: List[ToolCandidate] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "tool": self.tool,
            "entities": [e.to_dict() for e in self.entities],
            "references": [r.to_dict() for r in self.references],
            "candidates": [c.to_dict() for c in self.candidates],
            "parameters": self.parameters,
        }


# ── Parameter Extractors ─────────────────────────────────────────────


def _extract_query(match: re.Match, message: str) -> str:
    """Extract a search query, stripping filler words (FR/EN)."""
    if "query" in match.groupdict() and match.group("query"):
        raw = match.group("query").strip()
    else:
        raw = message

    cleaned = raw

    # Pass 1: Strip question words
    cleaned = re.sub(
        r"^(?:qu[' ]?els?\s+sont\s+|"
        r"quel(?:le|s|es)?\s+(?:est|sont)\s+(?:ce\s+)?(?:que\s+)?|"
        r"quelle\s+(?:est\s+(?:la|le|les)\s+)?|"
        r"qu[' ]?est[- ]?ce\s+que\s+|"
        r"qu[' ]?est[- ]?(?:ce\s+)?(?:que\s+)?|"
        r"c[' ]?est\s+quoi\s+|"
        r"comment\s+(?:fonctionne|marche|appelle[- ]?t[- ]?on)\s+|"
        r"ça\s+veut\s+dire\s+|"
        r"donnez[- ]?(?:moi\s+)?|donner[- ]?(?:moi\s+)?|"
        r"montrez[- ]?(?:moi\s+)?|"
        r"qu[' ]?est[- ]?ce\s+qui\s+|"
        r"what\s+is\s+(?:the\s+)?|what\s+are\s+(?:the\s+)?|"
        r"how\s+does\s+(?:the\s+)?|"
        r"show\s+me\s+(?:the\s+)?|"
        r"tell\s+me\s+(?:about\s+)?|"
        r")",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()

    # Pass 2: Strip action verbs
    cleaned = re.sub(
        r"^(?:recherch(?:e|er|ez|ons)?\s+|"
        r"cherche(?:z|r|ons)?\s+|"
        r"trou(?:ver|vez|vons)?\s+|"
        r"affich(?:e|er|ez|ons)?\s+|"
        r"montrez?\s+|"
        r"list(?:er|ez|e|ons)?\s+|"
        r"voir\s+|"
        r"cherchez?\s+|"
        r"search(?:ing)?\s+|"
        r"find\s+|"
        r"look\s+up\s+|"
        r"list\s+|"
        r"display\s+|"
        r"get\s+|"
        r"show\s+|"
        r"fetch\s+|"
        r")",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()

    # Pass 3: Strip articles and determiners
    cleaned = re.sub(
        r"^(?:l[' ]\s*|"
        r"les?\s+|des?\s+|du\s+|un(?:e)?\s+|"
        r"mon\s+|ma\s+|mes\s+|"
        r"ce(?:t|s)?\s+|"
        r"the\s+|a\s+|an\s+|"
        r"my\s+|his\s+|her\s+|its\s+|our\s+|their\s+|"
        r"this\s+|that\s+|these\s+|those\s+|"
        r")",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()

    # Pass 4: Strip possession phrases
    cleaned = re.sub(
        r"^(?:j[' ]?ai\s+|"
        r"i\s+have\s+|we\s+have\s+|"
        r"il\s+y\s+a\s+|"
        r"got\s+|there\s+is\s+|there\s+are\s+|"
        r")",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()

    # Pass 5: Strip connector phrases
    cleaned = re.sub(
        r"^(?:codes?\s+(?:pour|li[ée]s?\s+|relatifs?\s+|d[' ]|du\s+|de\s+|des\s+)\s*|"
        r"codes?\s+(?:for|related\s+to|of|about)\s*|"
        r"nomenclature\s+(?:pour|li[ée]e?\s+|relatif\s+|d[' ]|du\s+|de\s+|des\s+)\s*|"
        r"nomenclature\s+(?:for|related\s+to|of|about)\s*|"
        r"d[ée]chets?\s+(?:pour|li[ée]s?\s+|relatifs?\s+|d[' ]|du\s+|de\s+|des\s+)\s*|"
        r"d[ée]chets?\s+(?:for|related\s+to|of|about)\s*|"
        r"waste\s+codes?\s+(?:for|related\s+to|of|about)\s*|"
        r"waste\s+(?:for|related\s+to|of|about)\s*|"
        r"li[ée]s?\s+(?:au|aux|à|to)\s+|"
        r"relatifs?\s+(?:au|aux|à|to)\s+|"
        r"pour\s+|for\s+|about\s+|of\s+|"
        r"du\s+|de\s+|des\s+|d[' ]\s*|"
        r")",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()

    # Pass 6: Strip remaining prepositions
    cleaned = re.sub(
        r"^(?:l[' ]\s*|d[' ]\s*|"
        r"au\s+|aux\s+|à\s+|to\s+|in\s+|on\s+|at\s+|"
        r"du\s+|de\s+|des\s+|"
        r"les?\s+|des?\s+|un(?:e)?\s+|"
        r"the\s+|a\s+|an\s+|"
        r")",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()

    # Pass 6b: Second pass for articles
    cleaned = re.sub(
        r"^(?:l[' ]\s*|d[' ]\s*|"
        r"les?\s+|des?\s+|du\s+|un(?:e)?\s+|"
        r"the\s+|a\s+|an\s+|"
        r")",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()

    # Final cleanup
    cleaned = cleaned.strip("? !.,;:\"'")

    return cleaned if cleaned else raw.strip("? !.,;:\"'")


def _extract_code(match: re.Match, message: str) -> str:
    """Extract a nomenclature code."""
    if "code" in match.groupdict() and match.group("code"):
        return match.group("code")
    code_match = re.search(r"\b(\d{1,2}\.\d{2}(?:\.\d{2})?)\b", message)
    return code_match.group(1) if code_match else ""


def _extract_term(match: re.Match, message: str) -> Optional[str]:
    """Extract a glossary term, returning None if no glossary match found."""
    if "term" in match.groupdict() and match.group("term"):
        return match.group("term").strip()

    candidate = _extract_query(match, message)
    if not candidate:
        return None

    from apps.ai_assistant.glossaire_data import GLOSSAIRE
    candidate_lower = candidate.lower().strip()
    candidate_words = set(candidate_lower.split())

    for entry in GLOSSAIRE:
        terme = entry.get("terme_fr", "").lower()
        if candidate_lower in terme or terme in candidate_lower:
            return candidate
        terme_words = set(terme.split())
        overlap = candidate_words & terme_words
        significant_overlap = {w for w in overlap if len(w) >= 3}
        if significant_overlap:
            return candidate

    glossary_keywords = {
        "bsd", "bordereau", "agrément", "agrement", "recyclage",
        "valorisation", "élimination", "traçabilité", "dechet",
        "déchet", "nomenclature", "décharge", "compostage",
        "collecte", "tri", "réutilisation", "registre",
        "plan de gestion", "déclaration", "producteur",
        "transporteur", "récupérateur", "éliminateur", "valorisateur",
        "cet", "centre d'enfouissement", "dangereux", "spécial",
        "inerte", "ménager", "emballage",
    }
    if candidate_lower in glossary_keywords:
        return candidate

    return None


def _extract_numero(match: re.Match, message: str) -> str:
    """Extract a BSD/BC/BL numero."""
    if "numero" in match.groupdict() and match.group("numero"):
        return match.group("numero")
    numero_match = re.search(
        r"\b(BSD|BC|BL|BR)[-\s]?(\d{4,})\b", message, re.IGNORECASE,
    )
    if numero_match:
        return f"{numero_match.group(1)}-{numero_match.group(2)}"
    return ""


def _extract_class(match: re.Match, message: str) -> str:
    """Extract a waste class."""
    class_match = re.search(
        r"\b(class[es]?\s+)?(MA|SD|I|S)\b", message, re.IGNORECASE,
    )
    return class_match.group(2).upper() if class_match else ""


# ── AI Router ─────────────────────────────────────────────────────────


class AIRouter:
    """
    Fast, deterministic router mapping user messages to tool calls.

    Zero LLM cost. Covers all 18 intents with 100+ regex rules.
    Returns None when no rule matches (pipeline falls back to Hermes).

    Usage:
        router = AIRouter()
        result = router.route("Quels sont les déchets dangereux ?")
        if result:
            print(result.to_dict())
            # {"intent": "waste_search", "confidence": 0.95, "tool": "waste_tool"}
    """

    def __init__(self) -> None:
        self._rules: List[RouteRule] = self._build_rules()

    def route(self, message: str) -> Optional[RouteResult]:
        """
        Route a user message to an intent + tool.

        Returns RouteResult if a rule matches, None otherwise.
        """
        if not message or not message.strip():
            return None

        msg = message.strip()
        msg_lower = msg.lower()

        candidates: List[Tuple[RouteResult, int]] = []

        for rule in self._rules:
            match = rule.pattern.search(msg_lower)
            if match:
                params = {}
                skip = False
                for param_name, extractor in rule.param_extractors.items():
                    try:
                        value = extractor(match, msg)
                        if value is None:
                            skip = True
                            break
                        params[param_name] = value
                    except Exception:
                        skip = True
                        break

                if skip:
                    continue

                result = RouteResult(
                    intent=rule.intent,
                    confidence=rule.confidence,
                    tool=rule.tool,
                )
                candidates.append((result, rule.priority))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[1], -x[0].confidence))
        best = candidates[0][0]

        logger.debug(
            "AIRouter: '%s' → intent=%s, tool=%s (%.2f)",
            msg[:40], best.intent, best.tool, best.confidence,
        )
        return best

    def classify(self, message: str) -> Optional[RoutingResult]:
        """
        Full classification pipeline: intent → entities → references → rank → select.

        NEVER executes a tool. Returns a RoutingResult with all intermediate steps.

        Workflow:
            1. Detect Intent      → regex rules (100+ patterns)
            2. Detect Entities    → regex extraction (waste codes, BSD numbers, etc.)
            3. Detect References  → ReferenceClassifier (waste_code, article, etc.)
            4. Choose Tool        → rank all candidates by confidence
            5. Return result      → tool selected but NOT executed

        Returns:
            RoutingResult with intent, entities, references, ranked candidates
            or None if no intent matches
        """
        if not message or not message.strip():
            return None

        msg = message.strip()

        # ── Step 1: Detect Intent ────────────────────────────────────
        intent_result = self._detect_intent(msg)
        if intent_result is None:
            return None

        # ── Step 2: Detect Entities ──────────────────────────────────
        entities = self._detect_entities(msg)

        # ── Step 3: Detect References ────────────────────────────────
        references = self._detect_references(msg)

        # ── Step 4: Rank Candidates ──────────────────────────────────
        candidates = self._rank_candidates(msg, intent_result)

        # ── Step 5: Select Best Tool ─────────────────────────────────
        best_tool = intent_result.tool
        best_confidence = intent_result.confidence
        best_params = getattr(intent_result, '_params', {})

        # Merge reference signals into parameters
        ref_params = self._merge_reference_signals(references, best_params)

        logger.info(
            "AIRouter.classify: '%s' → intent=%s, tool=%s (%.2f), "
            "entities=%d, references=%d, candidates=%d",
            msg[:40], intent_result.intent, best_tool, best_confidence,
            len(entities), len(references), len(candidates),
        )

        return RoutingResult(
            intent=intent_result.intent,
            confidence=best_confidence,
            tool=best_tool,
            entities=entities,
            references=references,
            candidates=candidates,
            parameters=ref_params,
        )

    # ------------------------------------------------------------------
    # Step 1: Intent Detection
    # ------------------------------------------------------------------

    def _detect_intent(self, msg: str) -> Optional[RouteResult]:
        """Detect intent using regex rules. Returns best match or None."""
        msg_lower = msg.lower()

        candidates: List[Tuple[RouteResult, int, Dict[str, Any]]] = []

        for rule in self._rules:
            match = rule.pattern.search(msg_lower)
            if match:
                params = {}
                skip = False
                for param_name, extractor in rule.param_extractors.items():
                    try:
                        value = extractor(match, msg)
                        if value is None:
                            skip = True
                            break
                        params[param_name] = value
                    except Exception:
                        skip = True
                        break

                if skip:
                    continue

                result = RouteResult(
                    intent=rule.intent,
                    confidence=rule.confidence,
                    tool=rule.tool,
                )
                candidates.append((result, rule.priority, params))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[1], -x[0].confidence))
        best_result, _, best_params = candidates[0]

        # Attach params to result for downstream use
        object.__setattr__(best_result, '_params', best_params)

        return best_result

    # ------------------------------------------------------------------
    # Step 2: Entity Detection
    # ------------------------------------------------------------------

    def _detect_entities(self, msg: str) -> List[ClassifiedEntity]:
        """Extract entities from the user message using regex patterns."""
        entities: List[ClassifiedEntity] = []

        # Waste codes: XX.XX.XX
        waste_codes = set(re.findall(r"\b(\d{1,2}\.\d{2}\.\d{2})\b", msg))
        for code in waste_codes:
            entities.append(ClassifiedEntity(
                entity_type="waste_code", value=code, confidence=1.0,
            ))

        # BSD numbers: BSD-2024-001
        bsd_numbers = set(re.findall(
            r"\b(BSD[- ]?\d{4,})\b", msg, re.IGNORECASE,
        ))
        for bsd in bsd_numbers:
            entities.append(ClassifiedEntity(
                entity_type="bsd_number", value=bsd, confidence=1.0,
            ))

        # BC numbers: BC-2024-001
        bc_numbers = set(re.findall(
            r"\b(BC[- ]?\d{4,})\b", msg, re.IGNORECASE,
        ))
        for bc in bc_numbers:
            entities.append(ClassifiedEntity(
                entity_type="bc_number", value=bc, confidence=1.0,
            ))

        # BL numbers: BL-2024-001
        bl_numbers = set(re.findall(
            r"\b(BL[- ]?\d{4,})\b", msg, re.IGNORECASE,
        ))
        for bl in bl_numbers:
            entities.append(ClassifiedEntity(
                entity_type="bl_number", value=bl, confidence=1.0,
            ))

        # Agrement numbers
        agrement_numbers = set(re.findall(
            r"\b(agré?ment[- ]?\d{3,})\b", msg, re.IGNORECASE,
        ))
        for agr in agrement_numbers:
            entities.append(ClassifiedEntity(
                entity_type="agrement_number", value=agr, confidence=1.0,
            ))

        # Years: 2024, 2025
        years = set(re.findall(r"\b(20[0-9]{2})\b", msg))
        for year in years:
            entities.append(ClassifiedEntity(
                entity_type="year", value=year, confidence=0.9,
            ))

        # Quantities: 10.5 tonnes, 100 kg
        quantities = set(re.findall(
            r"\b(\d+(?:[.,]\d+)?\s*(?:tonnes?|kg|tons?|kilos?))\b",
            msg, re.IGNORECASE,
        ))
        for qty in quantities:
            entities.append(ClassifiedEntity(
                entity_type="quantity", value=qty, confidence=0.95,
            ))

        # Emails
        emails = set(re.findall(
            r"\b([\w.+-]+@[\w-]+\.[\w.-]+)\b", msg,
        ))
        for email in emails:
            entities.append(ClassifiedEntity(
                entity_type="email", value=email, confidence=1.0,
            ))

        # Percentages
        percentages = set(re.findall(
            r"\b(\d+(?:[.,]\d+)?\s*%)", msg,
        ))
        for pct in percentages:
            entities.append(ClassifiedEntity(
                entity_type="percentage", value=pct, confidence=0.95,
            ))

        return entities

    # ------------------------------------------------------------------
    # Step 3: Reference Detection
    # ------------------------------------------------------------------

    def _detect_references(self, msg: str) -> List[ClassifiedReference]:
        """Classify numeric references using ReferenceClassifier."""
        try:
            from apps.ai_assistant.enterprise.reference_classifier import (
                classify_reference,
            )
        except ImportError:
            return []

        references: List[ClassifiedReference] = []
        dotted_numerics = set(re.findall(r"\b\d+(?:\.\d+){1,3}\b", msg))

        for ref in dotted_numerics:
            result = classify_reference(ref)
            references.append(ClassifiedReference(
                reference=ref,
                reference_type=result["reference_type"],
                confidence=result["confidence"],
            ))

        return references

    # ------------------------------------------------------------------
    # Step 4: Candidate Ranking
    # ------------------------------------------------------------------

    def _rank_candidates(
        self, msg: str, intent_result: RouteResult,
    ) -> List[ToolCandidate]:
        """Rank all matching tool candidates by confidence."""
        msg_lower = msg.lower()
        candidates: List[ToolCandidate] = []
        seen_tools: set = set()

        for rule in self._rules:
            match = rule.pattern.search(msg_lower)
            if match:
                params = {}
                skip = False
                for param_name, extractor in rule.param_extractors.items():
                    try:
                        value = extractor(match, msg)
                        if value is None:
                            skip = True
                            break
                        params[param_name] = value
                    except Exception:
                        skip = True
                        break

                if skip:
                    continue

                tool_key = f"{rule.tool}:{rule.intent}"
                if tool_key not in seen_tools:
                    seen_tools.add(tool_key)
                    candidates.append(ToolCandidate(
                        tool=rule.tool,
                        intent=rule.intent,
                        confidence=rule.confidence,
                        priority=rule.priority,
                        parameters=params,
                        source="rule",
                    ))

        # Sort by priority (desc) then confidence (desc)
        candidates.sort(key=lambda c: (-c.priority, -c.confidence))

        return candidates

    # ------------------------------------------------------------------
    # Step 5: Reference Signal Merging
    # ------------------------------------------------------------------

    def _merge_reference_signals(
        self,
        references: List[ClassifiedReference],
        base_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge reference classification signals into tool parameters."""
        params = dict(base_params)

        if not references:
            return params

        # Group references by type
        ref_by_type: Dict[str, List[str]] = {}
        for ref in references:
            ref_by_type.setdefault(ref.reference_type, []).append(ref.reference)

        # Add reference info to parameters
        if "waste_code" in ref_by_type:
            params["waste_codes"] = ref_by_type["waste_code"]
        if "bsd_number" in ref_by_type:
            params["bsd_numbers"] = ref_by_type["bsd_number"]
        if "article" in ref_by_type:
            params["article_references"] = ref_by_type["article"]
        if "regulation_reference" in ref_by_type:
            params["regulation_references"] = ref_by_type["regulation_reference"]

        return params

    # ------------------------------------------------------------------
    # Rule definitions — organized by intent
    # ------------------------------------------------------------------

    def _build_rules(self) -> List[RouteRule]:
        rules: List[RouteRule] = []

        # ══════════════════════════════════════════════════════════════
        # INTENT: greeting
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"^(?:bonjour|salut|hello|hey|coucou|bonsoir|bsr|yo|salam|"
                r"hi|greetings|good\s+morning|good\s+evening|"
                r"مرحبا|سلام|السلام|أهلا|هاي)\s*[!!.]?\s*$",
                re.IGNORECASE,
            ),
            intent="greeting", tool="greeting", confidence=0.98, priority=100,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: question (generic — no specific tool)
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:qu[' ]?est[- ]?ce\s+que|"
                r"quel(?:le|s|es)?\s+(?:est|sont)\s+(?:ce\s+)?(?:que\s+)?|"
                r"comment\s+(?:fonctionne|marche|peut[- ]?on)|"
                r"pourquoi|o[ùu]\s+(?:est|sont|se\s+trouve)|"
                r"quand|combien|est[- ]?ce\s+que|"
                r"what\s+(?:is|are|does|do|can|should)|"
                r"how\s+(?:does|do|can|should|much|many)|"
                r"why|where|when)\b",
                re.IGNORECASE,
            ),
            intent="question", tool="", confidence=0.70, priority=10,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: glossary (definition lookup)
        # ══════════════════════════════════════════════════════════════
        glossary_patterns = [
            r"\b(?:c[' ]?est\s+quoi)\b",
            r"\b(?:qu[' ]?est[- ]ce\s+que)\b",
            r"\b(?:what\s+is|what\s+are)\b",
            r"\b(?:d[ée]finition\s+de|definition\s+de)\b",
            r"\b(?:signification\s+de)\b",
            r"\b(?:comment\s+(?:fonctionne|marche))\b",
            r"\b(?:ç[aà]\s+veut\s+dire)\b",
            r"\b(?:define)\b",
        ]
        for pat in glossary_patterns:
            rules.append(RouteRule(
                pattern=re.compile(pat, re.IGNORECASE),
                intent="glossary", tool="glossaire_tool",
                confidence=0.90, priority=80,
                param_extractors={"term": _extract_term},
            ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: nomenclature (code lookup + search)
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:code|nomenclature)\s+(\d{1,2}\.\d{2}(?:\.\d{2})?)\b",
            ),
            intent="nomenclature", tool="nomenclature_tool",
            confidence=0.97, priority=95,
            param_extractors={"code": _extract_code},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:sous[- ]?codes?|children|subcodes?|de|of|sous)\s+"
                r"(?:de\s+)?(\d{1,2}\.\d{2}(?:\.\d{2})?)\b",
                re.IGNORECASE,
            ),
            intent="nomenclature", tool="nomenclature_tool",
            confidence=0.95, priority=93,
            param_extractors={"parent": _extract_code},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:recherch(?:e|er|ez|ons)?|cherch(?:e|er|ez|ons)?|search(?:ing)?|find|lookup)\b.*"
                r"\b(?:nomenclature|code[s]?\s+d[' ]?dechet|code[s]?\s+li)",
                re.IGNORECASE,
            ),
            intent="nomenclature", tool="nomenclature_tool",
            confidence=0.92, priority=90,
            param_extractors={"term": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:code[s]?|nomenclature)\b.*\b(?:pour|for|lié|lie|relatif|"
                r"du|de|des|plastique|huile|papier|verre|métal|bois)\b",
                re.IGNORECASE,
            ),
            intent="nomenclature", tool="nomenclature_tool",
            confidence=0.88, priority=87,
            param_extractors={"term": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:simil(?:aire|ar)s?|related|proche|même\s+famille|meme famille|"
                r"autres?\s+codes?)\b.*\b(?:code|nomenclature)\b"
                r"|\b(?:code[s]?|nomenclature)\b.*\b(?:simil(?:aire|ar)s?|related|proche)\b",
                re.IGNORECASE,
            ),
            intent="nomenclature", tool="nomenclature_tool",
            confidence=0.90, priority=88,
            param_extractors={"term": _extract_query},
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: waste_search (waste-specific queries)
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:d[ée]chet[s]?\s+dangereux|dangerous\s+waste|"
                r"dechets?\s+sp[ée]ciaux?\s+dangereux)\b",
                re.IGNORECASE,
            ),
            intent="waste_search", tool="waste_tool",
            confidence=0.95, priority=92,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:classe|class)\s+(MA|SD|I|S)\b", re.IGNORECASE,
            ),
            intent="waste_search", tool="waste_tool",
            confidence=0.93, priority=91,
            param_extractors={"classe": _extract_class},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:recherch(?:e|er|ez|ons)?|cherch(?:e|er|ez|ons)?|search(?:ing)?|find|trouver|lookup)\b.*"
                r"\b(?:d[ée]chet[s]?|waste|nomenclature)\b",
                re.IGNORECASE,
            ),
            intent="waste_search", tool="waste_tool",
            confidence=0.88, priority=85,
            param_extractors={"query": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:d[ée]chet[s]?|waste)\s+(?:code\s+)?(\d{1,2}\.\d{2}(?:\.\d{2})?)\b",
                re.IGNORECASE,
            ),
            intent="waste_search", tool="waste_tool",
            confidence=0.94, priority=90,
            param_extractors={"code": _extract_code},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:j[' ]?ai|I\s+have|we\s+have|got|there\s+is|il\s+y\s+a)\b"
                r".*\b(?:huile|oil|plastique|plastic|papier|paper|verre|glass|"
                r"m[ée]tal|metal|bois|wood|chimique|chemical|dangereux|dangerous|"
                r"inflammable|toxique|toxic|corrosif|corrosive)\b",
                re.IGNORECASE,
            ),
            intent="waste_search", tool="waste_tool",
            confidence=0.85, priority=82,
            param_extractors={"query": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:d[ée]signations?|désignations?)\b.*"
                r"(\d{1,2}\.\d{2}(?:\.\d{2})?)",
                re.IGNORECASE,
            ),
            intent="waste_search", tool="waste_tool",
            confidence=0.91, priority=89,
            param_extractors={"code": _extract_code},
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: bsd (Bordereau de Suivi des Déchets)
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(r"\b(BSD[-\s]?\d{4,})\b", re.IGNORECASE),
            intent="bsd", tool="bsd_tool",
            confidence=0.96, priority=94,
            param_extractors={"numero": _extract_numero},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:lister?|liste|show|afficher?|voir|display|tous\s+les)\s+"
                r"(?:les?\s+)?BSD\b",
                re.IGNORECASE,
            ),
            intent="bsd", tool="bsd_tool",
            confidence=0.90, priority=87,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:recherch(?:e|er|ez|ons)?|cherch(?:e|er|ez|ons)?|search(?:ing)?|find)\b.*\bBSD\b",
                re.IGNORECASE,
            ),
            intent="bsd", tool="bsd_tool",
            confidence=0.88, priority=86,
            param_extractors={"query": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\bBSD\b.*\b(?:en\s+attente|pending|attente|validé|rejeté|"
                r"valid|reject|en cours)\b",
                re.IGNORECASE,
            ),
            intent="bsd", tool="bsd_tool",
            confidence=0.87, priority=85,
            param_extractors={"statut": lambda m, msg: (
                "EN_ATTENTE" if re.search(r"en\s+attente|pending|attente", msg, re.I)
                else "SIGNE" if re.search(r"valid", msg, re.I)
                else "RECEPTIONNE" if re.search(r"reject|rejet", msg, re.I)
                else "EN_TRANSIT"
            )},
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: bc (Bon de Commande)
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(r"\b(BC[-\s]?\d{4,})\b", re.IGNORECASE),
            intent="bc", tool="bc_tool",
            confidence=0.96, priority=94,
            param_extractors={"numero": _extract_numero},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:lister?|liste|show|afficher?|voir|tous\s+les)\s+"
                r"(?:les?\s+)?(?:BC|bons?\s+de\s+commande)\b",
                re.IGNORECASE,
            ),
            intent="bc", tool="bc_tool",
            confidence=0.90, priority=87,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: bl (Bon de Livraison)
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(r"\b(BL[-\s]?\d{4,})\b", re.IGNORECASE),
            intent="bl", tool="bl_tool",
            confidence=0.96, priority=94,
            param_extractors={"numero": _extract_numero},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:lister?|liste|show|afficher?|voir|tous\s+les)\s+"
                r"(?:les?\s+)?(?:BL|bons?\s+de\s+livraison)\b",
                re.IGNORECASE,
            ),
            intent="bl", tool="bl_tool",
            confidence=0.90, priority=87,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: company
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:entreprise[s]?|soci[ée]t[ée]s?|compan(?:y|ies)|"
                r"[ée]tablissement[s]?)\b",
                re.IGNORECASE,
            ),
            intent="company", tool="entreprise_tool",
            confidence=0.87, priority=83,
            param_extractors={"query": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:agr[ée]ment[s]?|agrement[s]?)\b.*"
                r"\b(?:expir|prouve|prochaine|bient[ôo]t)\b",
                re.IGNORECASE,
            ),
            intent="company", tool="entreprise_tool",
            confidence=0.89, priority=85,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: producer
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:producteur[s]?|g[ée]n[ée]rateur[s]?|sources?)\b",
                re.IGNORECASE,
            ),
            intent="producer", tool="producteur_tool",
            confidence=0.87, priority=83,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:recherch(?:e|er|ez|ons)?|cherch(?:e|er|ez|ons)?|search(?:ing)?|find)\b.*"
                r"\b(?:producteur|g[ée]n[ée]rateur)\b",
                re.IGNORECASE,
            ),
            intent="producer", tool="producteur_tool",
            confidence=0.88, priority=84,
            param_extractors={"query": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:show|list|display|see|get)\b.*"
                r"\b(?:producer[s]?|generator[s]?)\b",
                re.IGNORECASE,
            ),
            intent="producer", tool="producteur_tool",
            confidence=0.88, priority=84,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: transporter
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:transporteur[s]?|transport(?:eur)?s?)\b",
                re.IGNORECASE,
            ),
            intent="transporter", tool="transporteur_tool",
            confidence=0.87, priority=83,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:recherch(?:e|er|ez|ons)?|cherch(?:e|er|ez|ons)?|search(?:ing)?|find)\b.*\btransporteur\b",
                re.IGNORECASE,
            ),
            intent="transporter", tool="transporteur_tool",
            confidence=0.88, priority=84,
            param_extractors={"query": _extract_query},
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: partner
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:partenaire[s]?|[ée]liminateur[s]?|"
                r"[vV]aloriseur[s]?|CET)\b",
                re.IGNORECASE,
            ),
            intent="partner", tool="partner_tool",
            confidence=0.87, priority=83,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:recherch(?:e|er|ez|ons)?|cherch(?:e|er|ez|ons)?|search(?:ing)?|find)\b.*"
                r"\b(?:partenaire|[ée]liminateur|valoriseur)\b",
                re.IGNORECASE,
            ),
            intent="partner", tool="partner_tool",
            confidence=0.88, priority=84,
            param_extractors={"query": _extract_query},
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: statistics
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:statistiques?|stats?|chiffres?|"
                r"donn[ée]es|[ée]tats?\s+des?\s+lieux|"
                r"vue\s+d[' ]?ensemble|metrics?|"
                r"figures?|numbers?)\b",
                re.IGNORECASE,
            ),
            intent="statistics", tool="statistiques_tool",
            confidence=0.88, priority=82,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:quantit[ée]s?|tonnage|tonnes?|volume)\b.*"
                r"\b(?:par|per|during|pour)\b",
                re.IGNORECASE,
            ),
            intent="statistics", tool="statistiques_tool",
            confidence=0.85, priority=81,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: report
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:rapport[s]?|report[s]?|bilan|synth[èe]se|"
                r"compte[- ]rendu|export(?:er)?|pdf|"
                r"g[ée]n[ée]rer?\s+rapport)\b",
                re.IGNORECASE,
            ),
            intent="report", tool="rapport_tool",
            confidence=0.88, priority=82,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:g[ée]n[ée]rer?|generer?|cr[ée]er?|create)\b.*"
                r"\b(?:rapport|report|bilan)\b",
                re.IGNORECASE,
            ),
            intent="report", tool="rapport_tool",
            confidence=0.89, priority=83,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: dashboard
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:tableau\s+de\s+bord|dashboard|"
                r"vue\s+d['']ensemble|overview|"
                r"kpi[s]?|indicateur[s]?)\b",
                re.IGNORECASE,
            ),
            intent="dashboard", tool="dashboard_tool",
            confidence=0.88, priority=84,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:statistiques?\s+(?:globales?|g[ée]n[ée]rales?)|"
                r"r[ée]sum[ée]\s+(?:global|g[ée]n[ée]ral)|"
                r"vue\s+globale|global\s+stats?)\b",
                re.IGNORECASE,
            ),
            intent="dashboard", tool="dashboard_tool",
            confidence=0.85, priority=83,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:activit[ée]|activit[ée]s?\s+r[ée]cente|"
                r"fil\s+d['']activit[ée]|activity\s+feed|derni[èe]res?\s+actions?)\b",
                re.IGNORECASE,
            ),
            intent="dashboard", tool="dashboard_tool",
            confidence=0.85, priority=83,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: archive
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:archive[s]?|archivage|document[s]\s+archiv[ée]s?)\b",
                re.IGNORECASE,
            ),
            intent="archive", tool="archive_tool",
            confidence=0.85, priority=81,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:recherch(?:e|er|ez|ons)?|cherch(?:e|er|ez|ons)?|search(?:ing)?|find)\b.*"
                r"\b(?:archive|archivage)\b",
                re.IGNORECASE,
            ),
            intent="archive", tool="archive_tool",
            confidence=0.86, priority=82,
            param_extractors={"query": _extract_query},
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: traceability
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:tra[çc]abilit[ée]|tracking|suivi)\b",
                re.IGNORECASE,
            ),
            intent="traceability", tool="traceability_tool",
            confidence=0.86, priority=82,
            param_extractors={"query": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:somme|total|sommme)\s+(?:des?\s+)?"
                r"(?:quantit[ée]s?|tonnage|volume)\b",
                re.IGNORECASE,
            ),
            intent="traceability", tool="traceability_tool",
            confidence=0.87, priority=83,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: declaration (DSD)
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:d[ée]claration[s]?|declaration[s]?|DSD)\b",
                re.IGNORECASE,
            ),
            intent="declaration", tool="declaration_tool",
            confidence=0.88, priority=84,
            param_extractors={"query": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:lister?|liste|show|afficher?|voir|tous\s+les)\s+"
                r"(?:les?\s+)?(?:d[ée]claration[s]?|DSD)\b",
                re.IGNORECASE,
            ),
            intent="declaration", tool="declaration_tool",
            confidence=0.90, priority=86,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: inspection
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:inspection[s]?|contr[ôo]le[s]?|visite[s]?\s+technique)\b",
                re.IGNORECASE,
            ),
            intent="inspection", tool="inspection_tool",
            confidence=0.85, priority=81,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: regulation (maps to regulation tool, no specific intent)
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:r[ée]glementation|reglementation|loi[s]?|"
                r"d[ée]cret[s]?|arret[ée]?|norme[s]?|"
                r"juridique|l[ée]gal|compliance|r[ée]glementaire)\b",
                re.IGNORECASE,
            ),
            intent="regulation", tool="reglementation_tool",
            confidence=0.88, priority=82,
            param_extractors={"query": _extract_query},
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:loi\s+01[- ]19|d[ée]cret\s+06[- ]104|"
                r"d[ée]cret\s+11[- ]194|d[ée]cret\s+05[- ]315)\b",
                re.IGNORECASE,
            ),
            intent="regulation", tool="reglementation_tool",
            confidence=0.95, priority=90,
            param_extractors={"reference": lambda m, msg: m.group(0)},
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: notification
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:notif(?:ication)?s?|alerte[s]?|alarme[s]?|"
                r"avertissement[s]?)\b",
                re.IGNORECASE,
            ),
            intent="notification", tool="notification_tool",
            confidence=0.86, priority=82,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:nombre|combien|count)\s+(?:de\s+)?"
                r"(?:notif(?:ication)?s?|alerte[s]?)\b",
                re.IGNORECASE,
            ),
            intent="notification", tool="notification_tool",
            confidence=0.87, priority=83,
        ))

        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:notif(?:ication)?s?)\b.*"
                r"\b(?:haute|haute\s+priorit[ée]|urgent|critique|high)\b",
                re.IGNORECASE,
            ),
            intent="notification", tool="notification_tool",
            confidence=0.88, priority=84,
        ))

        # ══════════════════════════════════════════════════════════════
        # INTENT: authentication
        # ══════════════════════════════════════════════════════════════
        rules.append(RouteRule(
            pattern=re.compile(
                r"\b(?:profil|utilisateur|compte|connexion|login|"
                r"mon\s+compte|my\s+account)\b",
                re.IGNORECASE,
            ),
            intent="authentication", tool="authentification_tool",
            confidence=0.85, priority=80,
        ))

        return rules


# ── Module-level singleton ────────────────────────────────────────────

_router: Optional[AIRouter] = None


def route_message(message: str) -> Optional[Dict[str, Any]]:
    """
    Quick routing function (backward-compatible).

    Returns:
        {"intent": "...", "confidence": 0.0, "tool": "..."}
        or None if no rule matches.
    """
    global _router
    if _router is None:
        _router = AIRouter()
    result = _router.route(message)
    return result.to_dict() if result else None


_classifier: Optional[AIRouter] = None


def classify_message(message: str) -> Optional[Dict[str, Any]]:
    """
    Full classification pipeline (new API).

    Returns:
        {
            "intent": "...",
            "confidence": 0.0,
            "tool": "...",
            "entities": [...],
            "references": [...],
            "candidates": [...],
            "parameters": {...}
        }
        or None if no intent matches.
    """
    global _classifier
    if _classifier is None:
        _classifier = AIRouter()
    result = _classifier.classify(message)
    return result.to_dict() if result else None
