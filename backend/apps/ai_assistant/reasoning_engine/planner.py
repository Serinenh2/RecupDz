"""
Planning Stage — decomposes the request into an ordered execution plan.

Uses intent + entities to create a step-by-step plan.
Each step names a tool and its parameters.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.reasoning_engine.pipeline import Intent, PipelineContext, PipelineStage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plan Step
# ---------------------------------------------------------------------------

@dataclass
class PlanStep:
    """A single step in the execution plan."""
    id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    tool_name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    depends_on: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "description": self.description,
            "parameters": self.parameters,
            "priority": self.priority,
        }


# ---------------------------------------------------------------------------
# Plan Builder
# ---------------------------------------------------------------------------

class PlanBuilder:
    """Fluent builder for constructing a plan."""

    def __init__(self) -> None:
        self._steps: List[PlanStep] = []

    def step(
        self,
        tool_name: str,
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        depends_on: Optional[str] = None,
    ) -> PlanBuilder:
        self._steps.append(PlanStep(
            tool_name=tool_name,
            description=description,
            parameters=parameters or {},
            priority=priority,
            depends_on=depends_on,
        ))
        return self

    def build(self) -> List[PlanStep]:
        return sorted(self._steps, key=lambda s: s.priority)


# ---------------------------------------------------------------------------
# Strategy Interface
# ---------------------------------------------------------------------------

class PlanningStrategy:
    """Strategy for creating a plan from context."""

    def create_plan(self, context: PipelineContext) -> List[PlanStep]:
        raise NotImplementedError


class RuleBasedPlanning(PlanningStrategy):
    """Deterministic plan creation from rules."""

    def __init__(self, rules: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> None:
        self._rules = rules or {}

    def create_plan(self, context: PipelineContext) -> List[PlanStep]:
        builder = PlanBuilder()

        # Default: direct response
        if context.intent in (Intent.GREETING, Intent.CHITCHAT):
            builder.step("direct_response", "Generate a direct response", {
                "user_message": context.question,
                "intent": context.intent.value,
            })
            return builder.build()

        # Question / entity lookup
        if context.intent in (Intent.QUESTION, Intent.ENTITY_LOOKUP):
            if context.extracted_entities:
                entity_types = {e["type"] for e in context.extracted_entities}
                builder.step("search_knowledge", "Search knowledge base", {
                    "query": context.question,
                    "entity_types": list(entity_types),
                }, priority=1)
            else:
                builder.step("search_knowledge", "Search knowledge base", {
                    "query": context.question,
                }, priority=1)
            builder.step("generate_answer", "Generate answer from results", {
                "query": context.question,
            }, priority=2, depends_on="search_knowledge")

        # Analysis
        elif context.intent == Intent.ANALYSIS:
            if context.primary_entity:
                builder.step("fetch_entity", "Fetch entity details", {
                    "entity_type": context.primary_entity["type"],
                    "entity_id": context.primary_entity["value"],
                }, priority=1)
                builder.step("analyze_entity", "Analyze entity data", {
                    "entity_type": context.primary_entity["type"],
                }, priority=2, depends_on="fetch_entity")
            builder.step("generate_analysis", "Generate analysis report", {
                "query": context.question,
            }, priority=3)

        # Command
        elif context.intent == Intent.COMMAND:
            builder.step("execute_command", "Execute the requested command", {
                "command": context.question,
                "tool_hint": context.intent_entities.get("tool_hint", ""),
            }, priority=1)

        # Recommendation
        elif context.intent == Intent.RECOMMENDATION:
            builder.step("gather_context", "Gather relevant context", {
                "query": context.question,
                "user_id": context.user_id,
            }, priority=1)
            builder.step("generate_recommendation", "Generate recommendation", {
                "query": context.question,
            }, priority=2, depends_on="gather_context")

        # Fallback
        else:
            builder.step("direct_response", "Generate a direct response", {
                "user_message": context.question,
            }, priority=1)

        return builder.build()


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class PlanningStage(PipelineStage):
    """
    Stage 3: Create an execution plan from intent + entities.

    Uses a PlanningStrategy. Default: rule-based.
    """

    name = "planning"
    order = 30

    def __init__(
        self,
        strategy: Optional[PlanningStrategy] = None,
        max_steps: int = 10,
    ) -> None:
        self._strategy = strategy or RuleBasedPlanning()
        self._max_steps = max_steps

    def should_run(self, context: PipelineContext) -> bool:
        return context.intent != Intent.UNKNOWN

    def process(self, context: PipelineContext) -> None:
        steps = self._strategy.create_plan(context)

        # Cap at max_steps
        if len(steps) > self._max_steps:
            logger.warning("Plan has %d steps, capping to %d", len(steps), self._max_steps)
            steps = steps[: self._max_steps]

        context.plan_steps = [s.to_dict() for s in steps]
        context.plan_reasoning = f"Plan with {len(steps)} steps for intent={context.intent.value}"

        logger.debug("Plan: %d steps — %s", len(steps), [s.tool_name for s in steps])
