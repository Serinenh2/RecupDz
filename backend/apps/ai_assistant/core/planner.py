"""
Task Planner — decomposes user requests into ordered execution plans.

Uses the LLM to analyse intent + context and produce a step-by-step plan.
Falls back to a simple single-step plan when planning is disabled.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.config import AgentConfig
from apps.ai_assistant.core.interfaces import (
    Context,
    ExecutionPlan,
    Intent,
    LLMProvider,
    RouteResult,
    TaskStep,
)
from apps.ai_assistant.core.prompts import PromptRegistry

logger = logging.getLogger(__name__)


class LLMPlanner:
    """
    Strategy: use the LLM to create an execution plan.

    Falls back to a direct single-step plan for simple intents.
    """

    def __init__(
        self,
        llm: LLMProvider,
        config: AgentConfig,
        registry: Optional[PromptRegistry] = None,
    ) -> None:
        self._llm = llm
        self._config = config
        self._registry = registry or PromptRegistry()

    def create_plan(self, context: Context, route: RouteResult) -> ExecutionPlan:
        if not self._config.enable_planning:
            return self._simple_plan(context, route)

        if route.intent in (Intent.GREETING, Intent.CHITCHAT, Intent.CLARIFICATION):
            return self._simple_plan(context, route)

        return self._llm_plan(context, route)

    # -- internal --

    def _simple_plan(self, context: Context, route: RouteResult) -> ExecutionPlan:
        tool_name = route.tool_hint or "direct_response"
        user_message = self._last_user_message(context)
        step = TaskStep(
            id=f"step_{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            description=f"Handle {route.intent.value}: {user_message[:80]}",
            parameters={
                "user_message": user_message,
                "intent": route.intent.value,
                "entities": route.entities,
            },
        )
        return ExecutionPlan(
            steps=[step],
            reasoning="Simple plan: direct handling without LLM planning.",
            metadata={"plan_type": "simple", "intent": route.intent.value},
        )

    def _llm_plan(self, context: Context, route: RouteResult) -> ExecutionPlan:
        user_message = self._last_user_message(context)
        tools_desc = self._format_tools_description(route)

        prompt = self._registry.render(
            "planning",
            available_tools=tools_desc,
            context=self._summarise_context(context),
            user_message=user_message,
        )

        try:
            raw = self._llm.generate_structured(
                prompt,
                system_prompt="Tu es un planificateur de tâches expert. Tu retournes toujours du JSON valide.",
                temperature=0.3,
                max_tokens=1024,
            )
            return self._parse_plan(raw)
        except Exception as exc:
            logger.error("LLM planning failed, falling back to simple plan: %s", exc)
            return self._simple_plan(context, route)

    def _parse_plan(self, raw: Dict[str, Any]) -> ExecutionPlan:
        steps_raw: List[Dict[str, Any]] = raw.get("steps", [])
        if not steps_raw:
            logger.warning("LLM returned empty steps, using fallback")
            return self._fallback_plan()

        steps: List[TaskStep] = []
        for i, s in enumerate(steps_raw[: self._config.max_plan_steps]):
            step = TaskStep(
                id=s.get("id", f"step_{i + 1}"),
                tool_name=s.get("tool_name", "unknown"),
                description=s.get("description", ""),
                parameters=s.get("parameters", {}),
            )
            steps.append(step)

        return ExecutionPlan(
            steps=steps,
            reasoning=raw.get("reasoning", ""),
            metadata={"plan_type": "llm"},
        )

    def _fallback_plan(self) -> ExecutionPlan:
        step = TaskStep(
            id="step_fallback",
            tool_name="direct_response",
            description="Generate a fallback response",
            parameters={},
        )
        return ExecutionPlan(
            steps=[step],
            reasoning="Fallback plan after LLM planning failure.",
            metadata={"plan_type": "fallback"},
        )

    def _last_user_message(self, context: Context) -> str:
        for msg in reversed(context.messages):
            if msg.role.value == "user":
                return msg.content
        return ""

    def _format_tools_description(self, route: RouteResult) -> str:
        hint = route.tool_hint or "Aucun outil spécifique suggéré."
        return (
            f"Outil suggéré par le routeur: {hint}\n"
            f"Intent détecté: {route.intent.value} (confiance: {route.confidence:.0%})"
        )

    def _summarise_context(self, context: Context) -> str:
        parts: List[str] = []
        if context.user_id:
            parts.append(f"Utilisateur: {context.user_id}")
        if context.entity_type:
            parts.append(f"Entité: {context.entity_type}/{context.entity_id}")
        if context.domain_data:
            parts.append(f"Données: {json.dumps(context.domain_data, ensure_ascii=False)[:500]}")
        history = [m.content for m in context.messages[-5:] if m.role.value == "user"]
        if history:
            parts.append("Derniers messages: " + " | ".join(history))
        return "\n".join(parts) if parts else "Aucun contexte disponible."
