"""
Workflow Reasoner — reasons about workflow state and decides next actions.

Uses the current workflow state, step outputs, and context to make
intelligent decisions about execution flow, retries, and adaptations.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.workflows.models import (
    StepConfig, StepStatus, WorkflowDefinition, WorkflowState, WorkflowStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """Output of a reasoning step."""
    action: str
    target_step: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    reasoning: str = ""
    alternatives: List[str] = field(default_factory=list)


class WorkflowReasoner:
    """
    Reasons about workflow state and execution decisions.

    Responsibilities:
      1. Analyze step failures and suggest recovery actions
      2. Evaluate whether to continue, pause, or abort a workflow
      3. Adapt execution based on intermediate results
      4. Generate explanations for workflow decisions
    """

    def __init__(self) -> None:
        self._analyzers: List[Callable[[WorkflowState, WorkflowDefinition], Optional[ReasoningResult]]] = []

    def add_analyzer(
        self, analyzer: Callable[[WorkflowState, WorkflowDefinition], Optional[ReasoningResult]]
    ) -> None:
        self._analyzers.append(analyzer)

    def reason_about_failure(
        self,
        step: StepConfig,
        error: str,
        state: WorkflowState,
        workflow: WorkflowDefinition,
    ) -> ReasoningResult:
        """Analyze a step failure and determine the best course of action."""
        step_state = state.get_step_state(step.id)

        if step_state.attempt < step.max_retries:
            return ReasoningResult(
                action="retry",
                target_step=step.id,
                confidence=0.8,
                reasoning=f"Step failed but {step.max_retries - step_state.attempt} retries remaining",
                data={"error": error, "attempt": step_state.attempt},
            )

        if step.fallback_value is not None:
            return ReasoningResult(
                action="fallback",
                target_step=step.id,
                confidence=0.6,
                reasoning="Using fallback value after exhausting retries",
                data={"fallback": step.fallback_value},
            )

        compensable = self._has_compensation(step, workflow)
        if compensable:
            return ReasoningResult(
                action="compensate",
                target_step=step.compensation_step,
                confidence=0.7,
                reasoning="Triggering compensation for failed step",
                data={"error": error},
            )

        return ReasoningResult(
            action="abort",
            confidence=0.9,
            reasoning=f"Step '{step.id}' failed irrecoverably: {error}",
            data={"error": error},
        )

    def reason_about_workflow(
        self, state: WorkflowState, workflow: WorkflowDefinition
    ) -> ReasoningResult:
        """High-level reasoning about the overall workflow state."""
        if state.status == WorkflowStatus.COMPLETED:
            return ReasoningResult(
                action="complete",
                confidence=1.0,
                reasoning="All steps completed successfully",
                data={"completed_steps": state.completed_steps()},
            )

        if state.status == WorkflowStatus.FAILED:
            return ReasoningResult(
                action="handle_failure",
                confidence=0.9,
                reasoning=f"Workflow failed. Errors: {[s.error for s in state.step_states.values() if s.status == StepStatus.FAILED]}",
                data={"failed_steps": state.failed_steps()},
            )

        failed = state.failed_steps()
        if failed:
            for analyzer in self._analyzers:
                result = analyzer(state, workflow)
                if result:
                    return result

            return ReasoningResult(
                action="evaluate_failures",
                confidence=0.7,
                reasoning=f"{len(failed)} step(s) failed: {failed}",
                data={"failed_steps": failed},
            )

        if state.all_done():
            return ReasoningResult(
                action="complete",
                confidence=1.0,
                reasoning="All steps completed or skipped",
            )

        return ReasoningResult(
            action="continue",
            confidence=0.9,
            reasoning="Workflow is progressing normally",
        )

    def adapt_plan(
        self,
        state: WorkflowState,
        workflow: WorkflowDefinition,
        step_output: Dict[str, Any],
        completed_step_id: str,
    ) -> Optional[ReasoningResult]:
        """Decide if the plan needs adaptation based on step output."""
        if not step_output.get("_suggest_skip_next"):
            return None

        skip_targets = step_output["_suggest_skip_next"]
        if isinstance(skip_targets, str):
            skip_targets = [skip_targets]

        for target in skip_targets:
            target_state = state.get_step_state(target)
            if target_state.status == StepStatus.PENDING:
                target_state.status = StepStatus.SKIPPED
                logger.info(f"Skipping step {target} based on output from {completed_step_id}")

        return ReasoningResult(
            action="adapted",
            confidence=0.7,
            reasoning=f"Skipped steps based on output from {completed_step_id}: {skip_targets}",
            data={"skipped_steps": skip_targets},
        )

    def _has_compensation(self, step: StepConfig, workflow: WorkflowDefinition) -> bool:
        if step.compensation_step:
            comp_step = workflow.get_step(step.compensation_step)
            return comp_step is not None
        return False
