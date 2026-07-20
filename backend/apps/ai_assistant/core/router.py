"""
Intent Router — classifies user messages and selects target tools.

Two strategies:
  1. LLMRouter   — uses the LLM for classification (accurate, slower)
  2. RuleRouter  — regex + keyword heuristics (fast, deterministic)

Both implement the Router ABC and can be swapped via DI.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional, Pattern, Tuple

from apps.ai_assistant.core.interfaces import (
    Context,
    Intent,
    LLMProvider,
    RouteResult,
    Router,
)
from apps.ai_assistant.core.prompts import PromptRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule-Based Router (Fallback / Fast Path)
# ---------------------------------------------------------------------------

class RuleRouter(Router):
    """
    Deterministic intent classification via regex patterns and keywords.
    Zero LLM cost. Used as fallback or when LLM is unavailable.
    """

    def __init__(self) -> None:
        self._rules: List[Tuple[Intent, Pattern[str], Optional[str]]] = []
        self._build_rules()

    def classify(self, context: Context) -> RouteResult:
        user_message = self._last_user_message(context)
        if not user_message:
            return RouteResult(intent=Intent.UNKNOWN, confidence=0.0)

        normalised = user_message.strip().lower()

        for intent, pattern, tool_hint in self._rules:
            match = pattern.search(normalised)
            if match:
                logger.debug("RuleRouter: matched %s on '%s'", intent.value, match.group()[:40])
                return RouteResult(
                    intent=intent,
                    confidence=0.85,
                    entities={"matched_text": match.group()},
                    tool_hint=tool_hint,
                )

        if len(normalised) < 3:
            return RouteResult(intent=Intent.GREETING, confidence=0.7)

        if "?" in user_message:
            return RouteResult(intent=Intent.QUESTION, confidence=0.7, tool_hint="knowledge_search")

        return RouteResult(intent=Intent.QUESTION, confidence=0.5, tool_hint="direct_response")

    # -- rules --

    def _build_rules(self) -> None:
        greeting_words = r"(bonjour|salut|hello|hey|bonsoir|salam|مرحبا|أهلا|السلام عليكم)"
        self._rules.append((
            Intent.GREETING,
            re.compile(rf"^{greeting_words}[\s!.,?]*$", re.IGNORECASE),
            None,
        ))

        self._rules.append((
            Intent.CHITCHAT,
            re.compile(r"\b(comment (ça va|tu vas|vas.tu)|ça va|merci|de rien|au revoir|bye)\b", re.IGNORECASE),
            None,
        ))

        self._rules.append((
            Intent.COMMAND,
            re.compile(r"\b(génère?|generer|crée?|creer|imprime?|exporte?|télécharge?|telecharger)\b", re.IGNORECASE),
            None,
        ))

        self._rules.append((
            Intent.ANALYSIS,
            re.compile(r"\b(analyse?|analyser|vérifie?|verifier|contrôle?|controler|évalue?|evaluer)\b", re.IGNORECASE),
            "analysis_tool",
        ))

        self._rules.append((
            Intent.RECOMMENDATION,
            re.compile(r"\b(recommand|conseille?|suggère?|suggerer|quelle|quel|quoi)\b", re.IGNORECASE),
            "recommendation_tool",
        ))

    def _last_user_message(self, context: Context) -> str:
        for msg in reversed(context.messages):
            if msg.role.value == "user":
                return msg.content
        return ""


# ---------------------------------------------------------------------------
# LLM Router (High Accuracy)
# ---------------------------------------------------------------------------

class LLMRouter(Router):
    """
    Uses the LLM to classify intent with structured output.
    Provides higher accuracy for ambiguous inputs.
    """

    def __init__(
        self,
        llm: LLMProvider,
        registry: Optional[PromptRegistry] = None,
        fallback: Optional[Router] = None,
    ) -> None:
        self._llm = llm
        self._registry = registry or PromptRegistry()
        self._fallback = fallback or RuleRouter()

    def classify(self, context: Context) -> RouteResult:
        user_message = self._last_user_message(context)
        if not user_message:
            return RouteResult(intent=Intent.UNKNOWN, confidence=0.0)

        if not self._llm.is_available():
            logger.info("LLMRouter: LLM unavailable, using fallback RuleRouter")
            return self._fallback.classify(context)

        prompt = self._registry.render("intent_classification", user_message=user_message)

        try:
            raw = self._llm.generate_structured(
                prompt,
                system_prompt=(
                    "Tu es un classificateur d'intentions. "
                    "Tu retournes toujours un JSON valide avec les champs: "
                    "intent, confidence, entities, tool_hint."
                ),
                temperature=0.1,
                max_tokens=256,
            )
            return self._parse_classification(raw)
        except Exception as exc:
            logger.error("LLMRouter classification failed: %s — falling back to rules", exc)
            return self._fallback.classify(context)

    def _parse_classification(self, raw: Dict[str, Any]) -> RouteResult:
        intent_str = raw.get("intent", "unknown").lower()
        try:
            intent = Intent(intent_str)
        except ValueError:
            logger.warning("Unknown intent '%s', defaulting to QUESTION", intent_str)
            intent = Intent.QUESTION

        return RouteResult(
            intent=intent,
            confidence=min(max(float(raw.get("confidence", 0.5)), 0.0), 1.0),
            entities=raw.get("entities", {}),
            tool_hint=raw.get("tool_hint"),
        )

    def _last_user_message(self, context: Context) -> str:
        for msg in reversed(context.messages):
            if msg.role.value == "user":
                return msg.content
        return ""


# ---------------------------------------------------------------------------
# Router Factory
# ---------------------------------------------------------------------------

class RouterFactory:
    """Creates the appropriate router based on configuration."""

    @staticmethod
    def create(
        *,
        llm: Optional[LLMProvider] = None,
        use_llm: bool = True,
        registry: Optional[PromptRegistry] = None,
    ) -> Router:
        if use_llm and llm is not None:
            return LLMRouter(llm=llm, registry=registry)
        return RuleRouter()
