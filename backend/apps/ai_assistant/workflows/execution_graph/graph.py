"""
Execution Graph — resolves DAG ordering and manages parallel execution.

Validates that the workflow is a valid DAG (no cycles), computes execution
layers for parallel execution, and tracks execution progress.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from apps.ai_assistant.workflows.models import (
    Edge, EdgeType, StepConfig, StepStatus, StepType,
    WorkflowDefinition, WorkflowState, WorkflowStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionLayer:
    """A set of steps that can execute in parallel."""
    index: int
    step_ids: List[str]
    is_parallel: bool = False

    @property
    def size(self) -> int:
        return len(self.step_ids)


@dataclass
class ExecutionPlan:
    """Resolved execution plan for a workflow."""
    layers: List[ExecutionLayer]
    total_steps: int
    critical_path: List[str]
    max_parallelism: int

    @property
    def layer_count(self) -> int:
        return len(self.layers)


class CycleError(Exception):
    """Raised when a cycle is detected in the workflow graph."""
    pass


class ExecutionGraph:
    """
    Manages the DAG structure of a workflow.

    Responsibilities:
      1. Validate DAG properties (no cycles, all nodes reachable)
      2. Compute topological layers for parallel execution
      3. Track execution progress through the graph
      4. Compute critical path for time estimation
    """

    def analyze(self, workflow: WorkflowDefinition) -> ExecutionPlan:
        """Build complete execution plan from workflow definition."""
        self._validate_dag(workflow)
        layers = self._compute_layers(workflow)
        critical = self._compute_critical_path(workflow)
        max_par = max(l.size for l in layers) if layers else 1

        return ExecutionPlan(
            layers=layers,
            total_steps=len(workflow.steps),
            critical_path=critical,
            max_parallelism=max_par,
        )

    def get_ready_steps(
        self, workflow: WorkflowDefinition, state: WorkflowState
    ) -> List[StepConfig]:
        """Return all steps whose dependencies are satisfied."""
        ready = []
        for step in workflow.steps:
            if not step.enabled:
                continue
            step_state = state.get_step_state(step.id)
            if step_state.status not in (StepStatus.PENDING, StepStatus.QUEUED):
                continue
            if self._all_predecessors_done(step.id, workflow, state):
                ready.append(step)
        return ready

    def get_dependents(self, step_id: str, workflow: WorkflowDefinition) -> List[str]:
        """Return all steps that depend on the given step."""
        result = []
        visited: Set[str] = set()
        queue = deque([step_id])
        while queue:
            current = queue.popleft()
            for edge in workflow.get_edges_from(current):
                if edge.to_step not in visited:
                    visited.add(edge.to_step)
                    result.append(edge.to_step)
                    queue.append(edge.to_step)
        return result

    def get_predecessors(self, step_id: str, workflow: WorkflowDefinition) -> List[str]:
        """Return all steps that must complete before this step."""
        result = []
        visited: Set[str] = set()
        queue = deque([step_id])
        while queue:
            current = queue.popleft()
            for edge in workflow.get_edges_to(current):
                if edge.from_step not in visited:
                    visited.add(edge.from_step)
                    result.append(edge.from_step)
                    queue.append(edge.from_step)
        return result

    def _validate_dag(self, workflow: WorkflowDefinition) -> None:
        """Check for cycles using Kahn's algorithm."""
        in_degree: Dict[str, int] = defaultdict(int)
        adjacency: Dict[str, List[str]] = defaultdict(list)

        for step in workflow.steps:
            if step.id not in in_degree:
                in_degree[step.id] = 0

        for edge in workflow.edges:
            adjacency[edge.from_step].append(edge.to_step)
            in_degree[edge.to_step] = in_degree.get(edge.to_step, 0) + 1

        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(workflow.steps):
            cycle_nodes = [sid for sid, deg in in_degree.items() if deg > 0]
            raise CycleError(
                f"Workflow '{workflow.name}' contains a cycle involving: {cycle_nodes}"
            )

    def _compute_layers(self, workflow: WorkflowDefinition) -> List[ExecutionLayer]:
        """Topological sort into parallel layers."""
        in_degree: Dict[str, int] = defaultdict(int)
        adjacency: Dict[str, List[str]] = defaultdict(list)

        for step in workflow.steps:
            in_degree.setdefault(step.id, 0)
        for edge in workflow.edges:
            adjacency[edge.from_step].append(edge.to_step)
            in_degree[edge.to_step] += 1

        layers = []
        ready = sorted(
            [sid for sid, deg in in_degree.items() if deg == 0]
        )
        layer_idx = 0

        while ready:
            layer_steps = list(ready)
            is_parallel = len(layer_steps) > 1
            layers.append(ExecutionLayer(
                index=layer_idx,
                step_ids=layer_steps,
                is_parallel=is_parallel,
            ))

            next_ready = []
            for sid in layer_steps:
                for neighbor in adjacency.get(sid, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_ready.append(neighbor)

            ready = sorted(next_ready)
            layer_idx += 1

        return layers

    def _compute_critical_path(self, workflow: WorkflowDefinition) -> List[str]:
        """Find the longest path through the graph (by timeout estimates)."""
        step_times: Dict[str, float] = {}
        for step in workflow.steps:
            step_times[step.id] = step.timeout_seconds

        dist: Dict[str, float] = {s.id: 0.0 for s in workflow.steps}
        prev: Dict[str, Optional[str]] = {s.id: None for s in workflow.steps}

        layers = self._compute_layers(workflow)
        for layer in layers:
            for sid in layer.step_ids:
                for edge in workflow.get_edges_from(sid):
                    new_dist = dist[sid] + step_times.get(sid, 1.0)
                    if new_dist > dist.get(edge.to_step, 0):
                        dist[edge.to_step] = new_dist
                        prev[edge.to_step] = sid

        if not workflow.steps:
            return []

        end_node = max(dist, key=lambda k: dist[k])
        path = []
        current: Optional[str] = end_node
        while current is not None:
            path.append(current)
            current = prev.get(current)
        path.reverse()
        return path

    def _all_predecessors_done(
        self,
        step_id: str,
        workflow: WorkflowDefinition,
        state: WorkflowState,
    ) -> bool:
        for edge in workflow.get_edges_to(step_id):
            if edge.edge_type in (EdgeType.NORMAL, EdgeType.ON_SUCCESS):
                pred_state = state.get_step_state(edge.from_step)
                if pred_state.status not in (
                    StepStatus.COMPLETED, StepStatus.SKIPPED
                ):
                    return False
        return True
