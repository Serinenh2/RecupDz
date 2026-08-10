"""
Workflow Agent — integrates all workflow components into a cohesive agent.

Coordinates the reasoner, decision tree, task queue, execution graph,
validation, and recovery engines to execute workflows end-to-end.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.workflows.models import (
    Edge, StepConfig, StepStatus, StepType,
    WorkflowDefinition, WorkflowResult, WorkflowState, WorkflowStatus,
)
from apps.ai_assistant.workflows.decision_tree.engine import DecisionTree
from apps.ai_assistant.workflows.task_queue.queue import TaskQueue
from apps.ai_assistant.workflows.execution_graph.graph import ExecutionGraph
from apps.ai_assistant.workflows.validation.engine import (
    InputValidator, OutputValidator, ValidationResult, WorkflowValidator,
)
from apps.ai_assistant.workflows.recovery.engine import RecoveryAction, RecoveryEngine, RecoveryRecord
from apps.ai_assistant.workflows.reasoner.reasoner import ReasoningResult, WorkflowReasoner

logger = logging.getLogger(__name__)


StepHandler = Callable[[StepConfig, Dict[str, Any], WorkflowState], Dict[str, Any]]


@dataclass
class AgentConfig:
    """Configuration for the workflow agent."""
    max_concurrent_steps: int = 1
    default_timeout_seconds: float = 60.0
    enable_validation: bool = True
    enable_recovery: bool = True
    enable_reasoning: bool = True
    abort_on_validation_failure: bool = True


class WorkflowAgent:
    """
    Workflow-aware agent that orchestrates execution.

    Integrates:
      - DecisionTree: branching logic
      - TaskQueue: step scheduling
      - ExecutionGraph: DAG resolution
      - ValidationEngine: input/output validation
      - RecoveryEngine: error handling
      - WorkflowReasoner: intelligent decisions
    """

    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self._config = config or AgentConfig()
        self._decision_tree = DecisionTree()
        self._task_queue = TaskQueue(max_concurrent=self._config.max_concurrent_steps)
        self._execution_graph = ExecutionGraph()
        self._input_validator = InputValidator()
        self._output_validator = OutputValidator()
        self._workflow_validator = WorkflowValidator()
        self._recovery_engine = RecoveryEngine()
        self._reasoner = WorkflowReasoner()
        self._handlers: Dict[str, StepHandler] = {}

    @property
    def decision_tree(self) -> DecisionTree:
        return self._decision_tree

    @property
    def task_queue(self) -> TaskQueue:
        return self._task_queue

    @property
    def execution_graph(self) -> ExecutionGraph:
        return self._execution_graph

    @property
    def recovery_engine(self) -> RecoveryEngine:
        return self._recovery_engine

    @property
    def reasoner(self) -> WorkflowReasoner:
        return self._reasoner

    def register_handler(self, tool_name: str, handler: StepHandler) -> None:
        self._handlers[tool_name] = handler

    def execute(
        self,
        workflow: WorkflowDefinition,
        initial_input: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Execute a complete workflow and return the result."""
        state = WorkflowState(workflow_id=workflow.id)
        state.global_context.update(initial_input or {})
        state.status = WorkflowStatus.RUNNING
        state.start_time = time.monotonic()

        plan = self._execution_graph.analyze(workflow)

        logger.info(
            f"Executing workflow '{workflow.name}': "
            f"{plan.layer_count} layers, {plan.total_steps} steps, "
            f"max_parallelism={plan.max_parallelism}"
        )

        if self._config.enable_validation:
            vresult = self._workflow_validator.validate_workflow(workflow, state)
            if not vresult.is_valid and self._config.abort_on_validation_failure:
                state.status = WorkflowStatus.FAILED
                state.end_time = time.monotonic()
                return self._build_result(
                    workflow, state,
                    errors=[{"code": i.code, "message": i.message} for i in vresult.errors],
                )

        self._task_queue.initialize(workflow, state)

        while not self._task_queue.is_empty:
            queued = self._task_queue.pop_next()
            if queued is None:
                if self._task_queue.running_count > 0:
                    time.sleep(0.01)
                    continue
                break

            self._execute_step(queued.step, workflow, state)

            if state.status == WorkflowStatus.FAILED:
                break

        if state.status == WorkflowStatus.RUNNING:
            if state.all_done():
                state.status = WorkflowStatus.COMPLETED
            elif state.failed_steps():
                state.status = WorkflowStatus.FAILED

        state.end_time = time.monotonic()
        return self._build_result(workflow, state)

    def _execute_step(
        self,
        step: StepConfig,
        workflow: WorkflowDefinition,
        state: WorkflowState,
    ) -> None:
        step_state = state.get_step_state(step.id)
        step_state.status = StepStatus.RUNNING
        step_state.attempt += 1
        step_state.start_time = time.monotonic()

        input_data = self._resolve_inputs(step, state)

        if self._config.enable_validation:
            vresult = self._input_validator.validate_inputs(step, input_data)
            if not vresult.is_valid:
                step_state.status = StepStatus.FAILED
                step_state.error = f"Input validation failed: {[i.message for i in vresult.errors]}"
                step_state.end_time = time.monotonic()
                self._handle_step_failure(step, step_state.error, workflow, state)
                return

        try:
            output_data = self._execute_handler(step, input_data, state)
            step_state.output_data = output_data
            step_state.end_time = time.monotonic()

            if self._config.enable_validation:
                vresult = self._output_validator.validate_outputs(step, output_data)
                if not vresult.is_valid and self._config.abort_on_validation_failure:
                    step_state.status = StepStatus.FAILED
                    step_state.error = f"Output validation failed: {[i.message for i in vresult.errors]}"
                    self._handle_step_failure(step, step_state.error, workflow, state)
                    return

            if self._config.enable_reasoning:
                adapt = self._reasoner.adapt_plan(state, workflow, output_data, step.id)
                if adapt:
                    logger.info(f"Plan adapted: {adapt.reasoning}")

            step_state.status = StepStatus.COMPLETED
            state.global_context[f"steps.{step.id}.output"] = output_data

            self._task_queue.mark_completed(step.id, output_data, state, workflow)

            self._resolve_branching(step, workflow, state)

        except Exception as e:
            step_state.end_time = time.monotonic()
            self._handle_step_failure(step, str(e), workflow, state)

    def _execute_handler(
        self, step: StepConfig, input_data: Dict[str, Any], state: WorkflowState
    ) -> Dict[str, Any]:
        if step.step_type == StepType.CONDITION:
            context = {**state.global_context, **input_data}
            next_steps = self._decision_tree.resolve_parallel_branches(step, None, state)
            return {"_next_steps": next_steps, "_condition_context": context}

        if step.step_type == StepType.WAIT:
            return {"_waited": True, "_timestamp": time.time()}

        if step.step_type == StepType.PARALLEL:
            return {"_parallel_branches": True}

        handler = self._handlers.get(step.tool_name or step.handler or "")
        if handler:
            return handler(step, input_data, state)

        return {"_skipped": True, "_reason": "no_handler"}

    def _handle_step_failure(
        self,
        step: StepConfig,
        error: str,
        workflow: WorkflowDefinition,
        state: WorkflowState,
    ) -> None:
        step_state = state.get_step_state(step.id)
        step_state.error = error
        should_retry = False

        if self._config.enable_reasoning:
            reasoning = self._reasoner.reason_about_failure(step, error, state, workflow)
            logger.info(f"Reasoning: {reasoning.action} — {reasoning.reasoning}")

            if reasoning.action == "retry":
                should_retry = True

            elif reasoning.action == "fallback":
                step_state.output_data = {"fallback": reasoning.data.get("fallback")}
                step_state.status = StepStatus.COMPLETED
                self._task_queue.mark_completed(step.id, step_state.output_data, state, workflow)
                return

            elif reasoning.action == "compensate":
                if self._config.enable_recovery:
                    self._recovery_engine.execute_compensation(
                        step.id, state, step_state.output_data
                    )

        if not should_retry and self._config.enable_recovery:
            recovery_action = self._recovery_engine.handle_failure(
                step.id, error, state, step
            )
            if recovery_action.strategy.value == "retry":
                should_retry = True
            elif recovery_action.strategy.value == "skip":
                step_state.status = StepStatus.SKIPPED
                self._task_queue.mark_skipped(step.id)
                return

        if should_retry:
            step_state.status = StepStatus.PENDING
            step_state.error = None
            self._task_queue.requeue(step)
            return

        step_state.status = StepStatus.FAILED
        state.status = WorkflowStatus.FAILED
        self._task_queue.mark_failed(step.id, error, state, workflow)

    def _resolve_inputs(
        self, step: StepConfig, state: WorkflowState
    ) -> Dict[str, Any]:
        inputs = dict(state.global_context)
        for inp in step.inputs:
            if inp.source_step and inp.source_key:
                src_state = state.get_step_state(inp.source_step)
                if inp.source_key in src_state.output_data:
                    inputs[inp.name] = src_state.output_data[inp.source_key]
            elif inp.name in state.global_context:
                pass
            elif inp.default is not None:
                inputs[inp.name] = inp.default
        return inputs

    def _resolve_branching(
        self, step: StepConfig, workflow: WorkflowDefinition, state: WorkflowState
    ) -> None:
        next_step_id = self._decision_tree.evaluate_step(step, workflow, state)
        if next_step_id:
            next_step = workflow.get_step(next_step_id)
            if next_step:
                next_state = state.get_step_state(next_step_id)
                if next_state.status == StepStatus.PENDING:
                    next_state.status = StepStatus.QUEUED

    def _build_result(
        self,
        workflow: WorkflowDefinition,
        state: WorkflowState,
        errors: Optional[List[Dict[str, Any]]] = None,
    ) -> WorkflowResult:
        output = {}
        for step in workflow.get_leaf_steps():
            step_state = state.get_step_state(step.id)
            if step_state.output_data:
                output.update(step_state.output_data)

        step_results = {}
        for sid, ss in state.step_states.items():
            step_results[sid] = {
                "status": ss.status.value,
                "attempt": ss.attempt,
                "duration_ms": ss.duration_ms,
                "output": ss.output_data,
                "error": ss.error,
            }

        duration = state.duration_ms or 0.0

        return WorkflowResult(
            workflow_id=workflow.id,
            run_id=state.run_id,
            status=state.status,
            output=output,
            errors=errors or [],
            step_results=step_results,
            duration_ms=duration,
            metadata=state.metadata,
        )
