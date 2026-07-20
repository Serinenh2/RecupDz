"""
Workflow Engine — top-level orchestrator for workflow execution.

Public API for defining, executing, and monitoring workflows.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.workflows.models import (
    Edge, EdgeType, Priority, RecoveryStrategy, StepConfig, StepInput,
    StepOutput, StepType, WorkflowDefinition, WorkflowResult, WorkflowState,
    WorkflowStatus,
)
from apps.ai_assistant.workflows.agent.agent import AgentConfig, StepHandler, WorkflowAgent
from apps.ai_assistant.workflows.planner.planner import PlannerGoal, PlannerStep, WorkflowPlanner
from apps.ai_assistant.workflows.validation.engine import (
    InputValidator, OutputValidator, ValidationRule, WorkflowValidator,
)
from apps.ai_assistant.workflows.recovery.engine import RecoveryAction, RecoveryEngine, RetryPolicy

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Top-level workflow engine.

    Usage:
        engine = WorkflowEngine()
        engine.register_handler("search", my_search_handler)

        workflow = engine.define_workflow("my_workflow", "Do something", [
            Step(id="search", name="Search", tool_name="search"),
            Step(id="process", name="Process", tool_name="process", depends_on=["search"]),
        ])

        result = engine.execute("my_workflow", {"query": "test"})
    """

    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self._config = config or AgentConfig()
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._agents: Dict[str, WorkflowAgent] = {}
        self._handlers: Dict[str, StepHandler] = {}
        self._planner = WorkflowPlanner()
        self._results: Dict[str, WorkflowResult] = {}

    def register_workflow(self, workflow: WorkflowDefinition) -> None:
        self._workflows[workflow.id] = workflow

    def register_handler(self, tool_name: str, handler: StepHandler) -> None:
        self._handlers[tool_name] = handler
        for agent in self._agents.values():
            agent.register_handler(tool_name, handler)

    def define_workflow(
        self,
        workflow_id: str,
        name: str,
        steps: List[Dict[str, Any]],
        description: str = "",
        **kwargs: Any,
    ) -> WorkflowDefinition:
        """Define a workflow from a list of step dicts."""
        step_configs = []
        edges = []

        for s in steps:
            step = StepConfig(
                id=s["id"],
                name=s.get("name", s["id"]),
                step_type=StepType(s.get("type", "action")),
                tool_name=s.get("tool_name"),
                handler=s.get("handler"),
                timeout_seconds=s.get("timeout", 60.0),
                max_retries=s.get("max_retries", 0),
                recovery_strategy=RecoveryStrategy(s.get("recovery", "abort")),
                priority=Priority(s.get("priority", "normal")),
                metadata=s.get("metadata", {}),
            )
            step_configs.append(step)

            for dep in s.get("depends_on", []):
                edges.append(Edge(
                    id=f"{dep}_to_{step.id}",
                    from_step=dep,
                    to_step=step.id,
                    edge_type=EdgeType.ON_SUCCESS,
                ))

        if not edges and len(step_configs) > 1:
            for i in range(len(step_configs) - 1):
                edges.append(Edge(
                    id=f"{step_configs[i].id}_seq_{step_configs[i+1].id}",
                    from_step=step_configs[i].id,
                    to_step=step_configs[i + 1].id,
                    edge_type=EdgeType.ON_SUCCESS,
                ))

        workflow = WorkflowDefinition(
            id=workflow_id,
            name=name,
            description=description,
            steps=step_configs,
            edges=edges,
            timeout_seconds=kwargs.get("timeout", 300.0),
            tags=kwargs.get("tags", []),
        )

        self._workflows[workflow_id] = workflow
        return workflow

    def execute(
        self,
        workflow_id: str,
        initial_input: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Execute a registered workflow."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return WorkflowResult(
                workflow_id=workflow_id,
                run_id="",
                status=WorkflowStatus.FAILED,
                errors=[{"message": f"Workflow not found: {workflow_id}"}],
            )

        agent = WorkflowAgent(self._config)
        self._agents[workflow_id] = agent

        for tool_name, handler in self._handlers.items():
            agent.register_handler(tool_name, handler)

        result = agent.execute(workflow, initial_input)
        self._results[f"{workflow_id}:{result.run_id}"] = result

        logger.info(
            f"Workflow '{workflow_id}' finished: {result.status.value} "
            f"in {result.duration_ms:.1f}ms"
        )
        return result

    def plan_and_execute(
        self,
        goal: PlannerGoal,
        handlers: Optional[Dict[str, StepHandler]] = None,
    ) -> WorkflowResult:
        """Plan a workflow from a goal, then execute it."""
        workflow = self._planner.plan(goal)
        self.register_workflow(workflow)

        if handlers:
            for name, handler in handlers.items():
                self.register_handler(name, handler)

        return self.execute(workflow.id)

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> List[str]:
        return list(self._workflows.keys())

    def get_result(self, workflow_id: str, run_id: str) -> Optional[WorkflowResult]:
        return self._results.get(f"{workflow_id}:{run_id}")

    @property
    def planner(self) -> WorkflowPlanner:
        return self._planner
