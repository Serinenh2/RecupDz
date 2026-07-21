"""
Reasoning Engine — chain-of-thought validation and plan refinement.

Applies LLM-backed reasoning to verify plan coherence, detect gaps,
and suggest adjustments before execution.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.config import AgentConfig
from apps.ai_assistant.core.interfaces import (
    Context,
    ExecutionPlan,
    LLMProvider,
    ReasoningResult,
    TaskStep,
)
from apps.ai_assistant.core.prompts import PromptRegistry

logger = logging.getLogger(__name__)


class LLMReasoner:
    """
    Strategy: use the LLM to reason about an execution plan.

    Analyses the plan step by step and suggests adjustments.
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

    def reason(self, context: Context, plan: ExecutionPlan) -> ReasoningResult:
        if not self._config.enable_reasoning:
            return ReasoningResult(
                chain_of_thought=["Reasoning disabled."],
                conclusion="Plan accepted without reasoning.",
                confidence=1.0,
            )

        plan_text = self._plan_to_text(plan)
        context_text = self._context_to_text(context)

        prompt = self._registry.render("reasoning", plan=plan_text, context=context_text)

        try:
            raw = self._llm.generate_structured(
                prompt,
                system_prompt=(
                    "Tu es un expert en raisonnement logique. "
                    "Tu analyses des plans d'exécution et tu验证 leur cohérence."
                ),
                temperature=0.2,
                max_tokens=1024,
            )
            return self._parse_reasoning(raw)
        except Exception as exc:
            logger.error("LLM reasoning failed: %s — accepting plan as-is", exc)
            return ReasoningResult(
                chain_of_thought=[f"Reasoning error: {exc}"],
                conclusion="Plan accepted due to reasoning failure.",
                confidence=0.5,
            )

    def refine_plan(self, plan: ExecutionPlan, result: ReasoningResult) -> ExecutionPlan:
        """Apply reasoning adjustments to the plan."""
        if result.confidence >= 0.8 and not result.adjustments:
            logger.debug("Plan accepted with confidence %.0f%%", result.confidence * 100)
            return plan

        adjustments = result.adjustments
        if not adjustments:
            return plan

        steps_to_remove = set(adjustments.get("steps_to_remove", []))
        steps_to_modify = adjustments.get("steps_to_modify", {})
        steps_to_add_raw = adjustments.get("steps_to_add", [])

        new_steps: List[TaskStep] = []
        for step in plan.steps:
            if step.id in steps_to_remove:
                logger.debug("Reasoning: removing step %s", step.id)
                continue
            if step.id in steps_to_modify:
                overrides = steps_to_modify[step.id]
                step = TaskStep(
                    id=step.id,
                    tool_name=overrides.get("tool_name", step.tool_name),
                    description=overrides.get("description", step.description),
                    parameters=overrides.get("parameters", step.parameters),
                )
                logger.debug("Reasoning: modified step %s", step.id)
            new_steps.append(step)

        for add_spec in steps_to_add_raw:
            new_step = TaskStep(
                id=add_spec.get("id", f"reasoned_{len(new_steps) + 1}"),
                tool_name=add_spec.get("tool_name", "unknown"),
                description=add_spec.get("description", ""),
                parameters=add_spec.get("parameters", {}),
            )
            new_steps.append(new_step)
            logger.debug("Reasoning: added step %s", new_step.id)

        refined = ExecutionPlan(
            steps=new_steps,
            reasoning=plan.reasoning + "\n[Refined by reasoning engine]",
            metadata={**plan.metadata, "refined": True, "original_step_count": len(plan.steps)},
        )
        logger.info(
            "Plan refined: %d → %d steps (confidence=%.0f%%)",
            len(plan.steps), len(new_steps), result.confidence * 100,
        )
        return refined

    # -- helpers --

    def _parse_reasoning(self, raw: Dict[str, Any]) -> ReasoningResult:
        chain = raw.get("chain_of_thought", [])
        if isinstance(chain, str):
            chain = [chain]

        adjustments = raw.get("adjustments", {})
        if isinstance(adjustments, str):
            try:
                adjustments = json.loads(adjustments)
            except (json.JSONDecodeError, TypeError):
                adjustments = {}

        return ReasoningResult(
            chain_of_thought=chain,
            conclusion=raw.get("conclusion", ""),
            confidence=float(raw.get("confidence", 0.5)),
            adjustments=adjustments,
        )

    def _plan_to_text(self, plan: ExecutionPlan) -> str:
        lines = [f"Nombre d'étapes: {len(plan.steps)}"]
        for step in plan.steps:
            lines.append(
                f"  [{step.id}] {step.tool_name} — {step.description} "
                f"(params: {json.dumps(step.parameters, ensure_ascii=False)})"
            )
        if plan.reasoning:
            lines.append(f"Raisonnement initial: {plan.reasoning}")
        return "\n".join(lines)

    def _context_to_text(self, context: Context) -> str:
        parts: List[str] = []
        if context.user_id:
            parts.append(f"Utilisateur: {context.user_id}")
        if context.entity_type:
            parts.append(f"Entité: {context.entity_type}/{context.entity_id}")
        user_msgs = [m.content for m in context.messages if m.role.value == "user"]
        if user_msgs:
            parts.append("Dernière demande: " + user_msgs[-1][:300])
        return "\n".join(parts) if parts else "Pas de contexte."
