"""
Task Queue — schedules and prioritizes workflow steps based on dependencies.

Manages ready-to-execute steps, respects priorities and dependency ordering.
Thread-safe, supports concurrent access patterns.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from apps.ai_assistant.workflows.models import (
    Edge, EdgeType, Priority, StepConfig, StepStatus,
    WorkflowDefinition, WorkflowState,
)

logger = logging.getLogger(__name__)

PRIORITY_WEIGHT = {
    Priority.CRITICAL: 4,
    Priority.HIGH: 3,
    Priority.NORMAL: 2,
    Priority.LOW: 1,
}


@dataclass
class QueuedStep:
    """A step ready for execution."""
    step: StepConfig
    priority: Priority
    ready_at: float = 0.0
    queued_at: float = field(default_factory=time.monotonic)
    dependencies_met: List[str] = field(default_factory=list)

    @property
    def priority_weight(self) -> int:
        return PRIORITY_WEIGHT.get(self.priority, 2)

    def __lt__(self, other: "QueuedStep") -> bool:
        if self.priority_weight != other.priority_weight:
            return self.priority_weight > other.priority_weight
        return self.queued_at < other.queued_at


class TaskQueue:
    """
    Manages the execution queue for workflow steps.

    Responsibilities:
      1. Track which steps are ready (all dependencies satisfied)
      2. Prioritize ready steps
      3. Provide the next step to execute
      4. Handle step completion and cascade readiness
    """

    def __init__(self, max_concurrent: int = 1) -> None:
        self._max_concurrent = max_concurrent
        self._queue: List[QueuedStep] = []
        self._running: Dict[str, QueuedStep] = {}
        self._completed: Set[str] = set()
        self._failed: Set[str] = set()
        self._skipped: Set[str] = set()
        self._cancelled: Set[str] = set()
        self._lock = threading.Lock()

    def initialize(
        self, workflow: WorkflowDefinition, state: WorkflowState
    ) -> None:
        """Build initial queue from workflow definition."""
        with self._lock:
            self._queue.clear()
            self._running.clear()
            self._completed.clear()
            self._failed.clear()
            self._skipped.clear()
            self._cancelled.clear()

            for step in workflow.steps:
                if not step.enabled:
                    continue
                step_state = state.get_step_state(step.id)
                if step_state.status in (
                    StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.CANCELLED
                ):
                    if step_state.status == StepStatus.COMPLETED:
                        self._completed.add(step.id)
                    elif step_state.status == StepStatus.SKIPPED:
                        self._skipped.add(step.id)
                    else:
                        self._cancelled.add(step.id)
                    continue

                deps = self._get_satisfied_dependencies(step.id, workflow, state)
                total_deps = self._count_dependencies(step.id, workflow)

                if len(deps) >= total_deps:
                    self._queue.append(QueuedStep(
                        step=step,
                        priority=step.priority,
                        dependencies_met=deps,
                    ))
                else:
                    step_state.status = StepStatus.QUEUED

            self._queue.sort()

    def get_next(self) -> Optional[QueuedStep]:
        """Get the highest-priority ready step."""
        with self._lock:
            if not self._queue:
                return None
            if len(self._running) >= self._max_concurrent:
                return None
            return self._queue[0]

    def pop_next(self) -> Optional[QueuedStep]:
        """Remove and return the next ready step."""
        with self._lock:
            if not self._queue:
                return None
            if len(self._running) >= self._max_concurrent:
                return None
            step = self._queue.pop(0)
            step.step.status = StepStatus.RUNNING
            self._running[step.step.id] = step
            return step

    def mark_completed(
        self, step_id: str, output: Dict[str, Any], state: WorkflowState,
        workflow: WorkflowDefinition,
    ) -> List[QueuedStep]:
        """Mark step done and return newly ready steps."""
        with self._lock:
            self._running.pop(step_id, None)
            self._completed.add(step_id)

            step_state = state.get_step_state(step_id)
            step_state.status = StepStatus.COMPLETED
            step_state.output_data = output

            return self._update_readiness(workflow, state)

    def mark_failed(
        self, step_id: str, error: str, state: WorkflowState,
        workflow: WorkflowDefinition,
    ) -> List[QueuedStep]:
        """Mark step failed and return newly ready steps."""
        with self._lock:
            self._running.pop(step_id, None)
            self._failed.add(step_id)

            step_state = state.get_step_state(step_id)
            step_state.status = StepStatus.FAILED
            step_state.error = error

            return self._update_readiness(workflow, state)

    def mark_skipped(self, step_id: str) -> None:
        with self._lock:
            self._skipped.add(step_id)

    def requeue(self, step: StepConfig) -> None:
        """Re-enqueue a step for retry after failure."""
        with self._lock:
            self._failed.discard(step.id)
            self._running.pop(step.id, None)
            already = {qs.step.id for qs in self._queue}
            if step.id not in already:
                self._queue.append(QueuedStep(step=step, priority=step.priority))
                self._queue.sort()

    def cancel_all(self) -> None:
        with self._lock:
            for step_id in list(self._running):
                self._cancelled.add(step_id)
            self._running.clear()
            self._queue.clear()

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0 and len(self._running) == 0

    @property
    def running_count(self) -> int:
        with self._lock:
            return len(self._running)

    @property
    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "queued": [qs.step.id for qs in self._queue],
                "running": list(self._running.keys()),
                "completed": list(self._completed),
                "failed": list(self._failed),
                "skipped": list(self._skipped),
            }

    def _update_readiness(
        self, workflow: WorkflowDefinition, state: WorkflowState
    ) -> List[QueuedStep]:
        queued_ids = {qs.step.id for qs in self._queue}

        for step in workflow.steps:
            if not step.enabled:
                continue
            if step.id in queued_ids or step.id in self._completed or step.id in self._running or step.id in self._failed or step.id in self._skipped or step.id in self._cancelled:
                continue

            step_state = state.get_step_state(step.id)
            if step_state.status not in (StepStatus.PENDING, StepStatus.QUEUED):
                continue

            deps = self._get_satisfied_dependencies(step.id, workflow, state)
            total_deps = self._count_dependencies(step.id, workflow)

            if len(deps) >= total_deps:
                self._queue.append(QueuedStep(
                    step=step,
                    priority=step.priority,
                    dependencies_met=deps,
                ))
                queued_ids.add(step.id)

        self._queue.sort()
        return []

    def _get_satisfied_dependencies(
        self, step_id: str, workflow: WorkflowDefinition, state: WorkflowState
    ) -> List[str]:
        satisfied = []
        for edge in workflow.edges:
            if edge.to_step == step_id and edge.edge_type in (
                EdgeType.NORMAL, EdgeType.ON_SUCCESS
            ):
                src_state = state.get_step_state(edge.from_step)
                if src_state.status in (
                    StepStatus.COMPLETED, StepStatus.SKIPPED
                ):
                    satisfied.append(edge.from_step)
        return satisfied

    def _count_dependencies(self, step_id: str, workflow: WorkflowDefinition) -> int:
        return sum(
            1 for e in workflow.edges
            if e.to_step == step_id and e.edge_type in (
                EdgeType.NORMAL, EdgeType.ON_SUCCESS
            )
        )
