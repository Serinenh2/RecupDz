"""
Router Agent — classifies intent, selects tools, routes conversations.

Responsibilities:
  1. Intent Classification   — determine what the user wants
  2. Tool Selection           — pick the right tool(s) for the intent
  3. Fallback                 — degrade gracefully when confidence is low
  4. Clarification            — ask the user to clarify ambiguous requests
  5. Conversation Routing     — route to the correct conversation context
  6. Confidence Score         — quantify classification certainty

No business logic. Only routing decisions.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Intent(str, Enum):
    UNKNOWN = "unknown"
    GREETING = "greeting"
    QUESTION = "question"
    COMMAND = "command"
    CLARIFICATION = "clarification"
    CHITCHAT = "chitchat"
    ENTITY_LOOKUP = "entity_lookup"
    ANALYSIS = "analysis"
    RECOMMENDATION = "recommendation"
    STATISTICS = "statistics"
    REPORT = "report"
    REGULATION = "regulation"


class ConversationContext(str, Enum):
    GENERAL = "general"
    NOMENCLATURE = "nomenclature"
    AGREMENTS = "agrements"
    BSD = "bsd"
    DECLARATIONS = "declarations"
    STOCKS = "stocks"
    REGLEMENTAIRE = "reglementaire"
    DASHBOARD = "dashboard"
    PARTNERS = "partners"
    REPORTS = "reports"


class RoutingAction(str, Enum):
    EXECUTE_TOOL = "execute_tool"
    ASK_CLARIFICATION = "ask_clarification"
    FALLBACK = "fallback"
    DIRECT_RESPONSE = "direct_response"
    SKIP = "skip"


# ---------------------------------------------------------------------------
# Route Result
# ---------------------------------------------------------------------------

@dataclass
class RouteDecision:
    """Complete routing decision for a user message."""
    intent: Intent
    confidence: float
    action: RoutingAction
    tool_name: Optional[str] = None
    tool_parameters: Dict[str, Any] = field(default_factory=dict)
    conversation_context: ConversationContext = ConversationContext.GENERAL
    entities: Dict[str, Any] = field(default_factory=dict)
    clarification_question: Optional[str] = None
    fallback_message: Optional[str] = None
    reasoning: str = ""
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": round(self.confidence, 3),
            "action": self.action.value,
            "tool_name": self.tool_name,
            "tool_parameters": self.tool_parameters,
            "conversation_context": self.conversation_context.value,
            "entities": self.entities,
            "clarification_question": self.clarification_question,
            "fallback_message": self.fallback_message,
            "reasoning": self.reasoning,
            "alternatives": self.alternatives,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


# ---------------------------------------------------------------------------
# Classification Rule
# ---------------------------------------------------------------------------

@dataclass
class ClassificationRule:
    """A single rule for intent classification."""
    intent: Intent
    pattern: Pattern[str]
    tool_name: str = ""
    tool_parameters: Dict[str, Any] = field(default_factory=dict)
    context: ConversationContext = ConversationContext.GENERAL
    confidence: float = 0.85
    priority: int = 0


# ---------------------------------------------------------------------------
# Tool Mapping
# ---------------------------------------------------------------------------

@dataclass
class ToolMapping:
    """Maps an intent to its associated tool and default parameters."""
    tool_name: str
    intent: Intent
    default_action: str = ""
    context: ConversationContext = ConversationContext.GENERAL
    confidence_boost: float = 0.0
    keywords: List[str] = field(default_factory=list)
    parameter_extractors: Dict[str, Callable[[str, Dict[str, Any]], Any]] = field(
        default_factory=dict, repr=False
    )


# ---------------------------------------------------------------------------
# Router Agent
# ---------------------------------------------------------------------------

class RouterAgent:
    """
    Production-ready router agent.

    Classifies user intent, selects tools, handles fallback,
    generates clarification questions, and routes conversations.
    """

    CONFIDENCE_THRESHOLD = 0.6
    CLARIFICATION_THRESHOLD = 0.4
    MAX_ALTERNATIVES = 3

    def __init__(
        self,
        llm_classify: Optional[Callable[[str, str], Dict[str, Any]]] = None,
        rules: Optional[List[ClassificationRule]] = None,
        tool_mappings: Optional[List[ToolMapping]] = None,
    ) -> None:
        self._llm_classify = llm_classify
        self._rules = rules or self._default_rules()
        self._tool_mappings = tool_mappings or self._default_tool_mappings()
        self._context_rules = self._default_context_rules()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(
        self,
        message: str,
        *,
        conversation_id: str = "",
        user_id: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RouteDecision:
        """
        Route a user message to the appropriate tool or response.

        Returns a RouteDecision with intent, tool, parameters, and action.
        """
        start = time.monotonic()
        meta = metadata or {}

        # 1. Classify intent
        intent_result = self._classify_intent(message, conversation_history)

        # 2. Extract entities
        entities = self._extract_entities(message, intent_result)

        # 3. Select tool
        tool_decision = self._select_tool(
            intent_result["intent"],
            entities,
            message,
            meta,
        )

        # 4. Determine conversation context
        conv_context = self._determine_context(
            intent_result["intent"],
            entities,
            message,
        )

        # 5. Apply fallback / clarification logic
        action, clarification, fallback = self._resolve_action(
            intent_result["confidence"],
            tool_decision["tool_name"],
            intent_result["intent"],
        )

        # 6. Build alternatives
        alternatives = self._build_alternatives(
            intent_result["intent"],
            entities,
            tool_decision["tool_name"],
        )

        elapsed = (time.monotonic() - start) * 1000

        decision = RouteDecision(
            intent=intent_result["intent"],
            confidence=intent_result["confidence"],
            action=action,
            tool_name=tool_decision["tool_name"],
            tool_parameters=tool_decision["parameters"],
            conversation_context=conv_context,
            entities=entities,
            clarification_question=clarification,
            fallback_message=fallback,
            reasoning=intent_result.get("reasoning", ""),
            alternatives=alternatives,
            elapsed_ms=elapsed,
        )

        logger.info(
            "Route: intent=%s conf=%.2f action=%s tool=%s ctx=%s (%.1fms)",
            decision.intent.value,
            decision.confidence,
            decision.action.value,
            decision.tool_name or "none",
            decision.conversation_context.value,
            elapsed,
        )

        return decision

    # ------------------------------------------------------------------
    # 1. Intent Classification
    # ------------------------------------------------------------------

    def _classify_intent(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Classify user intent using LLM (if available) then rules."""

        # Try LLM classification first
        if self._llm_classify is not None:
            try:
                result = self._llm_classify(message, self._build_system_prompt())
                if result and "intent" in result:
                    intent = self._parse_intent(result.get("intent", "unknown"))
                    confidence = min(max(float(result.get("confidence", 0.5)), 0.0), 1.0)
                    return {
                        "intent": intent,
                        "confidence": confidence,
                        "entities": result.get("entities", {}),
                        "tool_hint": result.get("tool_hint"),
                        "reasoning": result.get("reasoning", "LLM classification"),
                        "source": "llm",
                    }
            except Exception as exc:
                logger.warning("LLM classification failed: %s — using rules", exc)

        # Rule-based classification
        return self._classify_by_rules(message)

    def _classify_by_rules(self, message: str) -> Dict[str, Any]:
        """Classify intent using pattern matching rules."""
        normalised = message.strip().lower()

        # Sort rules by priority (higher = checked first)
        sorted_rules = sorted(self._rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if rule.pattern.search(normalised):
                return {
                    "intent": rule.intent,
                    "confidence": rule.confidence,
                    "entities": {},
                    "tool_hint": rule.tool_name or None,
                    "reasoning": f"Rule match: {rule.pattern.pattern[:40]}",
                    "source": "rule",
                }

        # Fallback heuristics
        if len(normalised) < 3:
            return {
                "intent": Intent.GREETING,
                "confidence": 0.7,
                "entities": {},
                "tool_hint": None,
                "reasoning": "Short message = greeting",
                "source": "heuristic",
            }

        if "?" in message:
            return {
                "intent": Intent.QUESTION,
                "confidence": 0.6,
                "entities": {},
                "tool_hint": None,
                "reasoning": "Contains question mark",
                "source": "heuristic",
            }

        return {
            "intent": Intent.QUESTION,
            "confidence": 0.4,
            "entities": {},
            "tool_hint": None,
            "reasoning": "Default fallback",
            "source": "heuristic",
        }

    def _build_system_prompt(self) -> str:
        return (
            "Tu es un classificateur d'intentions pour un systeme de gestion "
            "des dechets speciaux en Algerie. Tu retournes toujours un JSON "
            "avec les champs: intent, confidence (0-1), entities, tool_hint, reasoning. "
            "Intents possibles: unknown, greeting, question, command, clarification, "
            "chitchat, entity_lookup, analysis, recommendation, statistics, report, regulation."
        )

    # ------------------------------------------------------------------
    # 2. Entity Extraction
    # ------------------------------------------------------------------

    def _extract_entities(
        self,
        message: str,
        intent_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract structured entities from the message."""
        entities: Dict[str, Any] = {}

        # Merge entities from LLM classification
        if intent_result.get("entities"):
            entities.update(intent_result["entities"])

        # Regex-based entity extraction
        normalised = message.lower()

        # Nomenclature codes (e.g., 15.01.06, 20.01.01)
        code_match = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3})\b", message)
        if code_match:
            entities["nomenclature_code"] = code_match.group(1)

        # Year references
        year_match = re.search(r"\b(20[2-3]\d)\b", message)
        if year_match:
            entities["year"] = year_match.group(1)

        # Wilaya codes (Algerian administrative divisions)
        wilaya_match = re.search(r"\b(?:wilaya|wila ya|province)\s*(\d{1,3})\b", normalised)
        if wilaya_match:
            entities["wilaya"] = wilaya_match.group(1)

        # Amounts with units
        amount_match = re.search(
            r"\b(\d[\d\s]*[,.]?\d*)\s*(tonnes?|kg|litres?|m[³3]|dh|eur)\b",
            normalised,
        )
        if amount_match:
            entities["amount"] = amount_match.group(1).replace(" ", "")
            entities["unit"] = amount_match.group(2)

        # Dates (DD/MM/YYYY or DD-MM-YYYY)
        date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", message)
        if date_match:
            entities["date"] = date_match.group(1)

        # Reference IDs
        ref_match = re.search(r"\b(REF[-:\s]?\w+|DOS[-:\s]?\w+|BSD[-:\s]?\w+|OP[-:\s]?\w+)\b", message, re.IGNORECASE)
        if ref_match:
            entities["reference_id"] = ref_match.group(1)

        # Email
        email_match = re.search(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", message)
        if email_match:
            entities["email"] = email_match.group()

        # Phone numbers
        phone_match = re.search(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b", message)
        if phone_match:
            entities["phone"] = phone_match.group()

        return entities

    # ------------------------------------------------------------------
    # 3. Tool Selection
    # ------------------------------------------------------------------

    def _select_tool(
        self,
        intent: Intent,
        entities: Dict[str, Any],
        message: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Select the best tool for the given intent and entities."""

        # Find matching tool mappings
        candidates: List[Tuple[ToolMapping, float]] = []

        for mapping in self._tool_mappings:
            if mapping.intent != intent:
                continue

            score = 0.5  # base score

            # Boost if keywords match
            normalised = message.lower()
            keyword_matches = sum(1 for kw in mapping.keywords if kw in normalised)
            score += keyword_matches * 0.1

            # Boost if entities match tool parameters
            if entities.get("nomenclature_code") and "waste" in mapping.tool_name:
                score += 0.2
            if entities.get("wilaya") and mapping.context in (
                ConversationContext.PARTNERS,
                ConversationContext.GENERAL,
            ):
                score += 0.1
            if entities.get("year") and "declaration" in mapping.tool_name:
                score += 0.15

            # Apply confidence boost from mapping
            score += mapping.confidence_boost

            candidates.append((mapping, min(score, 1.0)))

        if not candidates:
            return {"tool_name": None, "parameters": {}, "score": 0.0}

        # Sort by score, return best
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_mapping, best_score = candidates[0]

        # Build parameters
        parameters = self._build_tool_parameters(
            best_mapping,
            entities,
            message,
            metadata,
        )

        return {
            "tool_name": best_mapping.tool_name,
            "parameters": parameters,
            "score": best_score,
        }

    def _build_tool_parameters(
        self,
        mapping: ToolMapping,
        entities: Dict[str, Any],
        message: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build tool parameters from entities and message context."""
        params: Dict[str, Any] = {}

        # Set default action
        if mapping.default_action:
            params["action"] = mapping.default_action

        # Apply parameter extractors
        for param_name, extractor in mapping.parameter_extractors.items():
            try:
                value = extractor(message, entities)
                if value is not None:
                    params[param_name] = value
            except Exception as exc:
                logger.debug("Extractor failed for %s: %s", param_name, exc)

        # Map entities to parameters
        if entities.get("nomenclature_code"):
            params.setdefault("code", entities["nomenclature_code"])
        if entities.get("year"):
            params.setdefault("annee", entities["year"])
        if entities.get("wilaya"):
            params.setdefault("wilaya", entities["wilaya"])
        if entities.get("reference_id"):
            params.setdefault("query", entities["reference_id"])

        # Add search query if not yet set
        if "query" not in params and mapping.default_action in ("search", "list"):
            # Use first significant words as query
            words = message.split()
            stop_words = {"le", "la", "les", "un", "une", "des", "du", "de", "en", "et",
                         "ou", "est", "sont", "avec", "pour", "par", "sur", "qui", "que",
                         "quel", "quelle", "quels", "quelles", "comment", "pourquoi",
                         "bonjour", "salut", "merci", "oui", "non"}
            query_words = [w for w in words if w.lower() not in stop_words and len(w) > 1]
            if query_words:
                params.setdefault("query", " ".join(query_words[:5]))

        # Add user context
        if metadata.get("user_id"):
            params.setdefault("recuperateur_id", metadata["user_id"])

        return params

    # ------------------------------------------------------------------
    # 4. Conversation Context
    # ------------------------------------------------------------------

    def _determine_context(
        self,
        intent: Intent,
        entities: Dict[str, Any],
        message: str,
    ) -> ConversationContext:
        """Determine the conversation context from intent and entities."""
        normalised = message.lower()

        # Check context rules
        for pattern, context in self._context_rules:
            if pattern.search(normalised):
                return context

        # Map intent to default context
        intent_context_map = {
            Intent.ENTITY_LOOKUP: ConversationContext.GENERAL,
            Intent.ANALYSIS: ConversationContext.DASHBOARD,
            Intent.RECOMMENDATION: ConversationContext.DASHBOARD,
            Intent.STATISTICS: ConversationContext.DASHBOARD,
            Intent.REPORT: ConversationContext.REPORTS,
            Intent.REGULATION: ConversationContext.REGLEMENTAIRE,
        }

        if intent in intent_context_map:
            return intent_context_map[intent]

        # Check entities for context clues
        if entities.get("nomenclature_code"):
            return ConversationContext.NOMENCLATURE
        if entities.get("reference_id"):
            ref = entities["reference_id"].upper()
            if "BSD" in ref:
                return ConversationContext.BSD
            if "OP" in ref:
                return ConversationContext.STOCKS

        return ConversationContext.GENERAL

    # ------------------------------------------------------------------
    # 5. Action Resolution (Fallback / Clarification)
    # ------------------------------------------------------------------

    def _resolve_action(
        self,
        confidence: float,
        tool_name: Optional[str],
        intent: Intent,
    ) -> Tuple[RoutingAction, Optional[str], Optional[str]]:
        """Determine the routing action based on confidence and tool availability."""

        # High confidence — execute
        if confidence >= self.CONFIDENCE_THRESHOLD and tool_name:
            return RoutingAction.EXECUTE_TOOL, None, None

        # High confidence but no tool — direct response
        if confidence >= self.CONFIDENCE_THRESHOLD and not tool_name:
            return RoutingAction.DIRECT_RESPONSE, None, None

        # Low confidence with tool — still execute but note low confidence
        if confidence >= self.CLARIFICATION_THRESHOLD and tool_name:
            return RoutingAction.EXECUTE_TOOL, None, None

        # Very low confidence — ask clarification
        if confidence < self.CLARIFICATION_THRESHOLD:
            clarification = self._generate_clarification(intent, confidence)
            return RoutingAction.ASK_CLARIFICATION, clarification, None

        # Medium confidence, no tool — fallback
        if not tool_name:
            fallback = self._generate_fallback(intent)
            return RoutingAction.FALLBACK, None, fallback

        return RoutingAction.EXECUTE_TOOL, None, None

    def _generate_clarification(
        self,
        intent: Intent,
        confidence: float,
    ) -> str:
        """Generate a clarification question based on intent and confidence."""
        clarifications = {
            Intent.UNKNOWN: (
                "Je ne suis pas sur de comprendre votre demande. "
                "Pouvez-vous reformuler ou me donner plus de details?"
            ),
            Intent.QUESTION: (
                "Votre question semble generale. "
                "Sur quel sujet precis souhaitez-vous des informations? "
                "(nomenclature, declarations, partenaires, etc.)"
            ),
            Intent.ENTITY_LOOKUP: (
                "Quel element precis recherchez-vous? "
                "Un code nomenclature, un recuperateur, un BSD?"
            ),
            Intent.ANALYSIS: (
                "Que souhaitez-vous analyser exactement? "
                "Les donnees d'un recuperateur, une periode specifique?"
            ),
            Intent.COMMAND: (
                "Que souhaitez-vous que je fasse? "
                "Generer un rapport, exporter des donnees?"
            ),
        }

        return clarifications.get(intent, clarifications[Intent.UNKNOWN])

    def _generate_fallback(self, intent: Intent) -> str:
        """Generate a fallback message."""
        return (
            "Je peux vous aider avec la gestion des dechets speciaux. "
            "Voici ce que je peux faire:\n"
            "- Consulter la nomenclature des dechets\n"
            "- Rechercher des recuperateurs et partenaires\n"
            "- Gerer les declarations (DSD)\n"
            "- Consulter les BSD et bons de livraison\n"
            "- Afficher des statistiques et rapports\n"
            "- Rechercher des informations reglementaires\n"
            "Comment puis-je vous aider?"
        )

    # ------------------------------------------------------------------
    # 6. Alternatives
    # ------------------------------------------------------------------

    def _build_alternatives(
        self,
        intent: Intent,
        entities: Dict[str, Any],
        selected_tool: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Build alternative tool suggestions."""
        alternatives: List[Dict[str, Any]] = []

        for mapping in self._tool_mappings:
            if mapping.tool_name == selected_tool:
                continue
            if mapping.intent == intent:
                alternatives.append({
                    "tool_name": mapping.tool_name,
                    "context": mapping.context.value,
                })

        return alternatives[: self.MAX_ALTERNATIVES]

    # ------------------------------------------------------------------
    # Default Rules
    # ------------------------------------------------------------------

    @staticmethod
    def _default_rules() -> List[ClassificationRule]:
        """Build default classification rules."""
        rules: List[ClassificationRule] = []

        # Greetings
        rules.append(ClassificationRule(
            intent=Intent.GREETING,
            pattern=re.compile(
                r"^(bonjour|salut|hello|hey|bonsoir|salam|مرحبا|أهلا|السلام عليكم)[\s!.,?]*$",
                re.IGNORECASE,
            ),
            confidence=0.9,
            priority=10,
        ))

        # Chitchat
        rules.append(ClassificationRule(
            intent=Intent.CHITCHAT,
            pattern=re.compile(
                r"\b(comment (ça va|tu vas|vas.tu)|ça va|merci|de rien|au revoir|bye)\b",
                re.IGNORECASE,
            ),
            confidence=0.85,
            priority=9,
        ))

        # Statistics
        rules.append(ClassificationRule(
            intent=Intent.STATISTICS,
            pattern=re.compile(
                r"\b(statistiques?|stat|chiffres?|nombre|quantite|total|resume|vue d.ensemble)\b",
                re.IGNORECASE,
            ),
            tool_name="statistiques_tool",
            context=ConversationContext.DASHBOARD,
            confidence=0.8,
            priority=8,
        ))

        # Reports
        rules.append(ClassificationRule(
            intent=Intent.REPORT,
            pattern=re.compile(
                r"\b(rapport|generer|exporter|telecharger|imprimer|pdf|document)\b",
                re.IGNORECASE,
            ),
            tool_name="rapport_tool",
            context=ConversationContext.REPORTS,
            confidence=0.8,
            priority=8,
        ))

        # Regulation
        rules.append(ClassificationRule(
            intent=Intent.REGULATION,
            pattern=re.compile(
                r"\b(reglement|regulation|loi|decret|arrete|reference|glossaire|faq|guide)\b",
                re.IGNORECASE,
            ),
            tool_name="reglementation_tool",
            context=ConversationContext.REGLEMENTAIRE,
            confidence=0.8,
            priority=7,
        ))

        # Analysis
        rules.append(ClassificationRule(
            intent=Intent.ANALYSIS,
            pattern=re.compile(
                r"\b(analyse?|analyser|verifie?|verifier|controle?|controler|evalue?|evaluer)\b",
                re.IGNORECASE,
            ),
            tool_name="statistiques_tool",
            context=ConversationContext.DASHBOARD,
            confidence=0.8,
            priority=7,
        ))

        # Recommendation
        rules.append(ClassificationRule(
            intent=Intent.RECOMMENDATION,
            pattern=re.compile(
                r"\b(recommand|conseille?|sugere?|suggerer|quelle|quel|quoi|conseil)\b",
                re.IGNORECASE,
            ),
            confidence=0.75,
            priority=6,
        ))

        # Entity lookup — declarations
        rules.append(ClassificationRule(
            intent=Intent.ENTITY_LOOKUP,
            pattern=re.compile(
                r"\b(declaration|dsd|declarations)\b",
                re.IGNORECASE,
            ),
            tool_name="declaration_tool",
            context=ConversationContext.DECLARATIONS,
            confidence=0.85,
            priority=8,
        ))

        # Entity lookup — nomenclature
        rules.append(ClassificationRule(
            intent=Intent.ENTITY_LOOKUP,
            pattern=re.compile(
                r"\b(nomenclature|code.*dechet|classe.*dechet|famille|dangerosite|code\s+\d+\.\d+)\b",
                re.IGNORECASE,
            ),
            tool_name="waste_tool",
            context=ConversationContext.NOMENCLATURE,
            confidence=0.85,
            priority=8,
        ))

        # Entity lookup — recuperateur
        rules.append(ClassificationRule(
            intent=Intent.ENTITY_LOOKUP,
            pattern=re.compile(
                r"\b(recuperateur|entreprise|societe|company|agrement|rc|nif|nis)\b",
                re.IGNORECASE,
            ),
            tool_name="entreprise_tool",
            context=ConversationContext.GENERAL,
            confidence=0.8,
            priority=7,
        ))

        # Entity lookup — partner
        rules.append(ClassificationRule(
            intent=Intent.ENTITY_LOOKUP,
            pattern=re.compile(
                r"\b(partenaire|eliminateurs?|valoriseurs?|cet|transporteurs?|producteurs?|generateurs?)\b",
                re.IGNORECASE,
            ),
            tool_name="partner_tool",
            context=ConversationContext.PARTNERS,
            confidence=0.8,
            priority=7,
        ))

        # Entity lookup — BSD
        rules.append(ClassificationRule(
            intent=Intent.ENTITY_LOOKUP,
            pattern=re.compile(
                r"\b(bsd|bordereau|suivi.*dechet|tracking)\b",
                re.IGNORECASE,
            ),
            tool_name="entreprise_tool",
            context=ConversationContext.BSD,
            confidence=0.8,
            priority=7,
        ))

        # Command — generate
        rules.append(ClassificationRule(
            intent=Intent.COMMAND,
            pattern=re.compile(
                r"\b(generer?|creer?|creer|imprimer|exporter|telecharger|telecharger)\b",
                re.IGNORECASE,
            ),
            confidence=0.8,
            priority=6,
        ))

        return rules

    @staticmethod
    def _default_tool_mappings() -> List[ToolMapping]:
        """Build default tool mappings."""
        mappings: List[ToolMapping] = []

        # Declaration Tool
        mappings.append(ToolMapping(
            tool_name="declaration_tool",
            intent=Intent.ENTITY_LOOKUP,
            default_action="search",
            context=ConversationContext.DECLARATIONS,
            keywords=["declaration", "dsd", "dechets", "speciaux", "dangereux"],
        ))

        # Waste Tool
        mappings.append(ToolMapping(
            tool_name="waste_tool",
            intent=Intent.ENTITY_LOOKUP,
            default_action="search",
            context=ConversationContext.NOMENCLATURE,
            keywords=["nomenclature", "code", "dechet", "classe", "dangerosite", "famille"],
        ))

        # Partner Tool
        mappings.append(ToolMapping(
            tool_name="partner_tool",
            intent=Intent.ENTITY_LOOKUP,
            default_action="list",
            context=ConversationContext.PARTNERS,
            keywords=["partenaire", "eliminateur", "valoriseur", "cet"],
        ))

        # Producer Tool
        mappings.append(ToolMapping(
            tool_name="producteur_tool",
            intent=Intent.ENTITY_LOOKUP,
            default_action="list",
            context=ConversationContext.PARTNERS,
            keywords=["producteur", "generateur", "source"],
        ))

        # Transporter Tool
        mappings.append(ToolMapping(
            tool_name="transporteur_tool",
            intent=Intent.ENTITY_LOOKUP,
            default_action="list",
            context=ConversationContext.PARTNERS,
            keywords=["transporteur", "transport", "camion"],
        ))

        # Company Tool
        mappings.append(ToolMapping(
            tool_name="entreprise_tool",
            intent=Intent.ENTITY_LOOKUP,
            default_action="search",
            context=ConversationContext.GENERAL,
            keywords=["recuperateur", "entreprise", "societe", "agrement"],
        ))

        # Statistics Tool
        mappings.append(ToolMapping(
            tool_name="statistiques_tool",
            intent=Intent.STATISTICS,
            default_action="recuperateur_overview",
            context=ConversationContext.DASHBOARD,
            keywords=["statistiques", "chiffres", "total", "quantite", "resume"],
        ))
        mappings.append(ToolMapping(
            tool_name="statistiques_tool",
            intent=Intent.ANALYSIS,
            default_action="quantities_by_period",
            context=ConversationContext.DASHBOARD,
            keywords=["analyse", "verifier", "evaluer"],
        ))

        # Report Tool
        mappings.append(ToolMapping(
            tool_name="rapport_tool",
            intent=Intent.REPORT,
            default_action="traceability_report",
            context=ConversationContext.REPORTS,
            keywords=["rapport", "generer", "exporter", "telecharger"],
        ))

        # Regulation Tool
        mappings.append(ToolMapping(
            tool_name="reglementation_tool",
            intent=Intent.REGULATION,
            default_action="search",
            context=ConversationContext.REGLEMENTAIRE,
            keywords=["reglement", "loi", "decret", "reference", "glossaire"],
        ))

        # Authentication Tool
        mappings.append(ToolMapping(
            tool_name="authentification_tool",
            intent=Intent.ENTITY_LOOKUP,
            default_action="profile",
            context=ConversationContext.GENERAL,
            keywords=["profil", "utilisateur", "compte", "connexion"],
        ))

        return mappings

    @staticmethod
    def _default_context_rules() -> List[Tuple[Pattern[str], ConversationContext]]:
        """Build default context classification rules."""
        return [
            (re.compile(r"\b(nomenclature|code\s+\d+\.\d+|code.*dechet)\b", re.IGNORECASE), ConversationContext.NOMENCLATURE),
            (re.compile(r"\b(agrement|agrement)\b", re.IGNORECASE), ConversationContext.AGREMENTS),
            (re.compile(r"\b(bsd|bordereau)\b", re.IGNORECASE), ConversationContext.BSD),
            (re.compile(r"\b(declaration|dsd)\b", re.IGNORECASE), ConversationContext.DECLARATIONS),
            (re.compile(r"\b(stock|quantite|tonnage)\b", re.IGNORECASE), ConversationContext.STOCKS),
            (re.compile(r"\b(reglement|loi|decret)\b", re.IGNORECASE), ConversationContext.REGLEMENTAIRE),
            (re.compile(r"\b(statistiques|dashboard|tableau)\b", re.IGNORECASE), ConversationContext.DASHBOARD),
            (re.compile(r"\b(partenaire|eliminateur|valoriseur)\b", re.IGNORECASE), ConversationContext.PARTNERS),
            (re.compile(r"\b(rapport|export|pdf)\b", re.IGNORECASE), ConversationContext.REPORTS),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_intent(raw: str) -> Intent:
        """Parse an intent string into Intent enum."""
        try:
            return Intent(raw.lower().strip())
        except ValueError:
            return Intent.QUESTION
