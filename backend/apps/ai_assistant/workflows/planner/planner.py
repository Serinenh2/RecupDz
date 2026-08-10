"""
Workflow Planner — decomposes goals into executable workflow definitions.

Takes a high-level goal and context, and produces a WorkflowDefinition
with steps, edges, and configuration.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.workflows.models import (
    Edge, EdgeType, Priority, RecoveryStrategy, StepConfig, StepInput,
    StepOutput, StepType, WorkflowDefinition,
)

logger = logging.getLogger(__name__)


@dataclass
class PlannerGoal:
    """High-level goal to decompose into a workflow."""
    description: str
    goal_type: str = "generic"
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    priority: Priority = Priority.NORMAL
    timeout_seconds: float = 300.0


@dataclass
class PlannerStep:
    """Intermediate step representation during planning."""
    id: str
    name: str
    description: str = ""
    tool_name: Optional[str] = None
    step_type: StepType = StepType.ACTION
    depends_on: List[str] = field(default_factory=list)
    inputs: List[StepInput] = field(default_factory=list)
    outputs: List[StepOutput] = field(default_factory=list)
    timeout_seconds: float = 60.0
    max_retries: int = 2
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.RETRY
    priority: Priority = Priority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowPlanner:
    """
    Decomposes goals into workflow definitions.

    Responsibilities:
      1. Analyze goal and determine required steps
      2. Establish dependency ordering
      3. Configure recovery and validation for each step
      4. Generate the complete WorkflowDefinition
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, Callable[[PlannerGoal], List[PlannerStep]]] = {}
        self._post_processors: List[Callable[[WorkflowDefinition], WorkflowDefinition]] = []

    def register_strategy(
        self, goal_type: str, strategy: Callable[[PlannerGoal], List[PlannerStep]]
    ) -> None:
        self._strategies[goal_type] = strategy

    def add_post_processor(
        self, processor: Callable[[WorkflowDefinition], WorkflowDefinition]
    ) -> None:
        self._post_processors.append(processor)

    def plan(self, goal: PlannerGoal) -> WorkflowDefinition:
        """Decompose a goal into a workflow definition."""
        start = time.monotonic()

        strategy = self._strategies.get(goal.goal_type)
        if strategy is None:
            strategy = self._default_strategy

        planner_steps = strategy(goal)
        workflow = self._build_workflow(goal, planner_steps, start)

        for pp in self._post_processors:
            workflow = pp(workflow)

        logger.info(
            f"Planned workflow '{workflow.name}': {len(workflow.steps)} steps, "
            f"{len(workflow.edges)} edges"
        )
        return workflow

    def plan_from_steps(
        self, goal: PlannerGoal, steps: List[PlannerStep]
    ) -> WorkflowDefinition:
        """Build workflow from explicit step list."""
        start = time.monotonic()
        return self._build_workflow(goal, steps, start)

    def _build_workflow(
        self,
        goal: PlannerGoal,
        planner_steps: List[PlannerStep],
        start_time: float,
    ) -> WorkflowDefinition:
        steps = []
        edges = []

        for ps in planner_steps:
            step = StepConfig(
                id=ps.id,
                name=ps.name,
                step_type=ps.step_type,
                tool_name=ps.tool_name,
                inputs=ps.inputs,
                outputs=ps.outputs,
                timeout_seconds=ps.timeout_seconds,
                max_retries=ps.max_retries,
                recovery_strategy=ps.recovery_strategy,
                priority=ps.priority,
                metadata=ps.metadata,
            )
            steps.append(step)

        for ps in planner_steps:
            for dep_id in ps.depends_on:
                edge = Edge(
                    id=f"{dep_id}_to_{ps.id}",
                    from_step=dep_id,
                    to_step=ps.id,
                    edge_type=EdgeType.ON_SUCCESS,
                )
                edges.append(edge)

        if len(edges) == 0 and len(steps) > 1:
            for i in range(len(steps) - 1):
                edges.append(Edge(
                    id=f"{steps[i].id}_seq_{steps[i+1].id}",
                    from_step=steps[i].id,
                    to_step=steps[i + 1].id,
                    edge_type=EdgeType.ON_SUCCESS,
                ))

        elapsed = (time.monotonic() - start_time) * 1000
        logger.info(f"Workflow planned in {elapsed:.1f}ms")

        return WorkflowDefinition(
            id=f"plan_{goal.goal_type}_{int(time.time())}",
            name=f"Plan: {goal.description[:50]}",
            description=goal.description,
            steps=steps,
            edges=edges,
            timeout_seconds=goal.timeout_seconds,
            metadata={
                "goal_type": goal.goal_type,
                "parameters": goal.parameters,
                "constraints": goal.constraints,
                "planning_time_ms": round(elapsed, 1),
            },
            tags=[goal.goal_type],
        )

    def _default_strategy(self, goal: PlannerGoal) -> List[PlannerStep]:
        return [
            PlannerStep(
                id="parse_goal",
                name="Parse Goal",
                description="Understand and validate the goal",
                step_type=StepType.ACTION,
                timeout_seconds=10.0,
            ),
            PlannerStep(
                id="gather_data",
                name="Gather Data",
                description="Collect required data for the goal",
                step_type=StepType.ACTION,
                depends_on=["parse_goal"],
                timeout_seconds=30.0,
                max_retries=2,
            ),
            PlannerStep(
                id="execute",
                name="Execute",
                description="Execute the main action",
                step_type=StepType.ACTION,
                depends_on=["gather_data"],
                timeout_seconds=60.0,
                max_retries=1,
            ),
            PlannerStep(
                id="validate_result",
                name="Validate Result",
                description="Verify the result is correct",
                step_type=StepType.ACTION,
                depends_on=["execute"],
                timeout_seconds=10.0,
            ),
        ]
