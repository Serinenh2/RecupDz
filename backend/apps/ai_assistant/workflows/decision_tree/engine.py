"""
Decision Tree — evaluates conditions and determines workflow branching.

Evaluates expressions against workflow context to select the next step.
Supports: comparisons, boolean logic, regex, existence checks, custom evaluators.
"""

from __future__ import annotations

import logging
import operator
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.workflows.models import (
    Edge, EdgeType, StepConfig, StepStatus, WorkflowDefinition, WorkflowState,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Condition Evaluation
# ---------------------------------------------------------------------------

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a if isinstance(a, (str, list)) else False,
    "starts_with": lambda a, b: str(a).startswith(str(b)),
    "ends_with": lambda a, b: str(a).endswith(str(b)),
    "matches": lambda a, b: bool(re.search(str(b), str(a))),
    "is_empty": lambda a, _: not a,
    "is_not_empty": lambda a, _: bool(a),
    "is_none": lambda a, _: a is None,
    "is_not_none": lambda a, _: a is not None,
    "type_is": lambda a, b: type(a).__name__ == str(b),
}


@dataclass
class ConditionNode:
    """A single condition in the decision tree."""
    field_path: str
    operator: str
    value: Any = None
    negate: bool = False

    def evaluate(self, context: Dict[str, Any]) -> bool:
        actual = _resolve_path(context, self.field_path)
        op_func = OPERATORS.get(self.operator)
        if op_func is None:
            logger.warning(f"Unknown operator: {self.operator}")
            return False

        try:
            result = op_func(actual, self.value)
        except Exception as e:
            logger.debug(f"Condition evaluation error: {e}")
            return False

        return not result if self.negate else result


@dataclass
class ConditionGroup:
    """Group of conditions with AND/OR logic."""
    logic: str = "and"
    conditions: List[ConditionNode] = field(default_factory=list)
    children: List["ConditionGroup"] = field(default_factory=list)

    def evaluate(self, context: Dict[str, Any]) -> bool:
        results = [c.evaluate(context) for c in self.conditions]
        child_results = [ch.evaluate(context) for ch in self.children]
        all_results = results + child_results

        if not all_results:
            return True

        if self.logic == "and":
            return all(all_results)
        elif self.logic == "or":
            return any(all_results)
        return False


@dataclass
class BranchRule:
    """Maps a condition to a target step."""
    target_step_id: str
    condition: Optional[ConditionGroup] = None
    priority: int = 0

    def matches(self, context: Dict[str, Any]) -> bool:
        if self.condition is None:
            return True
        return self.condition.evaluate(context)


# ---------------------------------------------------------------------------
# Decision Tree Engine
# ---------------------------------------------------------------------------

class DecisionTree:
    """
    Evaluates branching conditions for workflow steps.

    Given a current step and context, determines which outgoing edge
    (next step) should be taken.
    """

    def __init__(self) -> None:
        self._custom_evaluators: Dict[str, Callable[[Any, Any, Dict], bool]] = {}

    def register_evaluator(
        self, name: str, fn: Callable[[Any, Any, Dict], bool]
    ) -> None:
        self._custom_evaluators[name] = fn

    def evaluate_step(
        self,
        step: StepConfig,
        workflow: WorkflowDefinition,
        state: WorkflowState,
    ) -> Optional[str]:
        """Determine the next step ID after completing the given step."""
        edges = workflow.get_edges_from(step.id)
        if not edges:
            return None

        context = self._build_context(state)
        conditional = [e for e in edges if e.edge_type == EdgeType.CONDITIONAL]
        normal = [e for e in edges if e.edge_type == EdgeType.NORMAL]

        for edge in conditional:
            if self._evaluate_condition(edge.condition, context):
                logger.debug(f"Branch: {step.id} -> {edge.to_step} (condition met)")
                return edge.to_step

        on_success = [e for e in edges if e.edge_type == EdgeType.ON_SUCCESS]
        step_state = state.get_step_state(step.id)
        if step_state.status == StepStatus.COMPLETED and on_success:
            return on_success[0].to_step

        on_failure = [e for e in edges if e.edge_type == EdgeType.ON_FAILURE]
        if step_state.status == StepStatus.FAILED and on_failure:
            return on_failure[0].to_step

        if normal:
            return normal[0].to_step

        defaults = [e for e in edges if e.edge_type == EdgeType.DEFAULT]
        if defaults:
            return defaults[0].to_step

        return None

    def resolve_parallel_branches(
        self,
        step: StepConfig,
        workflow: WorkflowDefinition,
        state: WorkflowState,
    ) -> List[str]:
        """For PARALLEL steps, return all branches to execute concurrently."""
        edges = workflow.get_edges_from(step.id)
        context = self._build_context(state)
        branches = []

        for edge in edges:
            if edge.edge_type in (EdgeType.NORMAL, EdgeType.CONDITIONAL):
                if edge.condition is None or self._evaluate_condition(edge.condition, context):
                    branches.append(edge.to_step)

        return branches

    def _build_context(self, state: WorkflowState) -> Dict[str, Any]:
        ctx = dict(state.global_context)
        for step_id, step_state in state.step_states.items():
            ctx[f"steps.{step_id}.status"] = step_state.status.value
            ctx[f"steps.{step_id}.output"] = step_state.output_data
            ctx[f"steps.{step_id}.error"] = step_state.error
        return ctx

    def _evaluate_condition(
        self, condition_str: Optional[str], context: Dict[str, Any]
    ) -> bool:
        if not condition_str:
            return True

        try:
            tree = self._parse_condition(condition_str)
            return tree.evaluate(context)
        except Exception as e:
            logger.warning(f"Condition parse error: {condition_str} -> {e}")
            return False

    def _parse_condition(self, expr: str) -> ConditionGroup:
        expr = expr.strip()

        if "|" in expr and not expr.startswith("("):
            parts = [p.strip() for p in expr.split("|", 1)]
            return ConditionGroup(
                logic="or",
                conditions=[self._parse_single(p) for p in parts],
            )

        if "&" in expr and not expr.startswith("("):
            parts = [p.strip() for p in expr.split("&", 1)]
            return ConditionGroup(
                logic="and",
                conditions=[self._parse_single(p) for p in parts],
            )

        return ConditionGroup(conditions=[self._parse_single(expr)])

    def _parse_single(self, expr: str) -> ConditionNode:
        expr = expr.strip()
        negate = False
        if expr.startswith("not "):
            negate = True
            expr = expr[4:].strip()

        for op in sorted(OPERATORS.keys(), key=len, reverse=True):
            if f" {op} " in expr or op in ("is_empty", "is_not_empty", "is_none", "is_not_none"):
                if op in ("is_empty", "is_not_empty", "is_none", "is_not_none"):
                    field_path = expr.replace(op, "").strip()
                    return ConditionNode(field_path=field_path, operator=op, negate=negate)
                parts = expr.split(f" {op} ", 1)
                if len(parts) == 2:
                    field_path = parts[0].strip()
                    raw_value = parts[1].strip()
                    value = self._coerce_value(raw_value)
                    return ConditionNode(
                        field_path=field_path, operator=op, value=value, negate=negate
                    )

        return ConditionNode(field_path=expr, operator="is_not_empty", negate=negate)

    def _coerce_value(self, raw: str) -> Any:
        if raw.lower() in ("true", "yes"):
            return True
        if raw.lower() in ("false", "no"):
            return False
        if raw.lower() == "null" or raw.lower() == "none":
            return None
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            return raw[1:-1]
        return raw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_path(data: Dict[str, Any], path: str) -> Any:
    """Resolve dotted path like 'steps.parse.status'."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current
