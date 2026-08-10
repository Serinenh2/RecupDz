"""
Intent Detection Stage — classifies what the user wants.

Uses pattern matching and keyword detection. LLM-backed version
can be injected for higher accuracy.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple

from apps.ai_assistant.reasoning_engine.pipeline import Intent, PipelineContext, PipelineStage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------

@dataclass
class IntentRule:
    """A single classification rule."""
    intent: Intent
    pattern: Pattern[str]
    tool_hint: str = ""
    confidence: float = 0.85


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class IntentDetectionStage(PipelineStage):
    """
    Stage 1: Detect the user's intent from the question.

    Uses regex rules by default. Accepts an optional LLM classifier
    for higher accuracy on ambiguous inputs.
    """

    name = "intent_detection"
    order = 10

    def __init__(
        self,
        llm_classify: Optional[Callable[[str], Dict[str, Any]]] = None,
        rules: Optional[List[IntentRule]] = None,
    ) -> None:
        self._llm_classify = llm_classify
        self._rules = rules or self._default_rules()

    def should_run(self, context: PipelineContext) -> bool:
        return bool(context.question.strip())

    def process(self, context: PipelineContext) -> None:
        question = context.question.strip()

        # Try LLM first if available
        if self._llm_classify is not None:
            try:
                result = self._llm_classify(question)
                context.intent = self._parse_intent(result.get("intent", "unknown"))
                context.intent_confidence = float(result.get("confidence", 0.5))
                context.intent_entities = result.get("entities", {})
                logger.debug("LLM intent: %s (%.0f%%)", context.intent.value, context.intent_confidence * 100)
                return
            except Exception as exc:
                logger.warning("LLM intent classification failed: %s — using rules", exc)

        # Rule-based fallback
        normalised = question.lower()
        for rule in self._rules:
            if rule.pattern.search(normalised):
                context.intent = rule.intent
                context.intent_confidence = rule.confidence
                if rule.tool_hint:
                    context.intent_entities["tool_hint"] = rule.tool_hint
                logger.debug("Rule intent: %s (matched '%s')", context.intent.value, rule.pattern.pattern[:30])
                return

        # Default
        if "?" in question:
            context.intent = Intent.QUESTION
            context.intent_confidence = 0.6
        elif len(normalised) < 3:
            context.intent = Intent.GREETING
            context.intent_confidence = 0.7
        else:
            context.intent = Intent.QUESTION
            context.intent_confidence = 0.4

    # -- defaults --

    @staticmethod
    def _default_rules() -> List[IntentRule]:
        return [
            IntentRule(
                Intent.GREETING,
                re.compile(r"^(bonjour|salut|hello|hey|bonsoir|salam)[\s!.,?]*$", re.IGNORECASE),
            ),
            IntentRule(
                Intent.CHITCHAT,
                re.compile(r"\b(comment (ça va|tu vas)|merci|de rien|au revoir|bye)\b", re.IGNORECASE),
            ),
            IntentRule(
                Intent.COMMAND,
                re.compile(r"\b(génère?|generer|crée?|creer|imprime?|exporte?|télécharge?)\b", re.IGNORECASE),
                tool_hint="document_generator",
            ),
            IntentRule(
                Intent.ANALYSIS,
                re.compile(r"\b(analyse?|analyser|vérifie?|verifier|contrôle?|controler|évalue?|evaluer)\b", re.IGNORECASE),
                tool_hint="analysis_tool",
            ),
            IntentRule(
                Intent.RECOMMENDATION,
                re.compile(r"\b(recommand|conseille?|suggère?|suggerer|quelle|quel|quoi)\b", re.IGNORECASE),
                tool_hint="recommendation_tool",
            ),
            IntentRule(
                Intent.ENTITY_LOOKUP,
                re.compile(r"\b(code|nomenclature|agrément|agrement|recupérateur|recuperateur|bsd|déclaration)\b", re.IGNORECASE),
                tool_hint="entity_search",
            ),
        ]

    @staticmethod
    def _parse_intent(raw: str) -> Intent:
        try:
            return Intent(raw.lower())
        except ValueError:
            return Intent.QUESTION
