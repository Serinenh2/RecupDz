"""
Validation Engine — validates step inputs, outputs, and workflow state.

Provides composable validators for data integrity, business rules,
and post-execution verification.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from apps.ai_assistant.workflows.models import (
    StepConfig, StepStatus, ValidationSeverity,
    WorkflowDefinition, WorkflowState, WorkflowStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation Results
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """Single validation finding."""
    severity: ValidationSeverity
    message: str
    step_id: Optional[str] = None
    field_name: Optional[str] = None
    code: str = "UNKNOWN"
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Aggregated validation result."""
    issues: List[ValidationIssue] = field(default_factory=list)
    is_valid: bool = True
    duration_ms: float = 0.0

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL):
            self.is_valid = False

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [
                {
                    "severity": i.severity.value,
                    "message": i.message,
                    "step_id": i.step_id,
                    "code": i.code,
                }
                for i in self.issues
            ],
        }


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

@dataclass
class ValidationRule:
    """Composable validation rule."""
    name: str
    check: Callable[[Dict[str, Any]], Optional[ValidationIssue]]
    enabled: bool = True


class InputValidator:
    """Validates step input data before execution."""

    def __init__(self) -> None:
        self._rules: List[ValidationRule] = []

    def add_rule(self, rule: ValidationRule) -> None:
        self._rules.append(rule)

    def validate_inputs(
        self, step: StepConfig, input_data: Dict[str, Any]
    ) -> ValidationResult:
        result = ValidationResult()
        start = time.monotonic()

        for inp in step.inputs:
            if inp.required and inp.name not in input_data:
                if inp.default is None:
                    result.add(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=f"Required input '{inp.name}' is missing",
                        step_id=step.id,
                        field_name=inp.name,
                        code="MISSING_REQUIRED",
                    ))
                else:
                    input_data[inp.name] = inp.default

        for rule in self._rules:
            if not rule.enabled:
                continue
            issue = rule.check({"step": step, "inputs": input_data})
            if issue:
                issue.step_id = step.id
                result.add(issue)

        result.duration_ms = (time.monotonic() - start) * 1000
        return result


class OutputValidator:
    """Validates step output data after execution."""

    def __init__(self) -> None:
        self._rules: List[ValidationRule] = []

    def add_rule(self, rule: ValidationRule) -> None:
        self._rules.append(rule)

    def validate_outputs(
        self, step: StepConfig, output_data: Dict[str, Any]
    ) -> ValidationResult:
        result = ValidationResult()
        start = time.monotonic()

        for out in step.outputs:
            if out.name not in output_data:
                result.add(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"Expected output '{out.name}' not present",
                    step_id=step.id,
                    field_name=out.name,
                    code="MISSING_OUTPUT",
                ))

        for key, value in output_data.items():
            if isinstance(value, str) and not value.strip():
                result.add(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"Output '{key}' is empty string",
                    step_id=step.id,
                    field_name=key,
                    code="EMPTY_OUTPUT",
                ))

        for rule in self._rules:
            if not rule.enabled:
                continue
            issue = rule.check({"step": step, "outputs": output_data})
            if issue:
                issue.step_id = step.id
                result.add(issue)

        result.duration_ms = (time.monotonic() - start) * 1000
        return result


class WorkflowValidator:
    """Validates overall workflow state and transitions."""

    def __init__(self) -> None:
        self._state_rules: List[Callable[[WorkflowState], Optional[ValidationIssue]]] = []

    def add_state_rule(
        self, rule: Callable[[WorkflowState], Optional[ValidationIssue]]
    ) -> None:
        self._state_rules.append(rule)

    def validate_workflow(
        self, workflow: WorkflowDefinition, state: WorkflowState
    ) -> ValidationResult:
        result = ValidationResult()
        start = time.monotonic()

        if not workflow.steps:
            result.add(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Workflow has no steps",
                code="EMPTY_WORKFLOW",
            ))

        enabled_steps = [s for s in workflow.steps if s.enabled]
        if not enabled_steps:
            result.add(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="All steps are disabled",
                code="ALL_DISABLED",
            ))

        step_ids = {s.id for s in workflow.steps}
        for edge in workflow.edges:
            if edge.from_step not in step_ids:
                result.add(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Edge references unknown source step: {edge.from_step}",
                    code="INVALID_EDGE",
                ))
            if edge.to_step not in step_ids:
                result.add(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Edge references unknown target step: {edge.to_step}",
                    code="INVALID_EDGE",
                ))

        tool_steps = [s for s in enabled_steps if s.tool_name]
        for s in tool_steps:
            if not s.tool_name:
                result.add(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"Action step '{s.id}' has no tool_name",
                    step_id=s.id,
                    code="NO_TOOL",
                ))

        for rule in self._state_rules:
            issue = rule(state)
            if issue:
                result.add(issue)

        result.duration_ms = (time.monotonic() - start) * 1000
        return result

    def validate_step_transition(
        self,
        step_id: str,
        from_status: StepStatus,
        to_status: StepStatus,
        state: WorkflowState,
    ) -> ValidationResult:
        result = ValidationResult()

        valid_transitions = {
            StepStatus.PENDING: {StepStatus.QUEUED, StepStatus.RUNNING, StepStatus.SKIPPED},
            StepStatus.QUEUED: {StepStatus.RUNNING, StepStatus.CANCELLED},
            StepStatus.RUNNING: {StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.RETRYING, StepStatus.WAITING},
            StepStatus.RETRYING: {StepStatus.RUNNING, StepStatus.FAILED},
            StepStatus.WAITING: {StepStatus.RUNNING, StepStatus.CANCELLED},
            StepStatus.FAILED: {StepStatus.RETRYING, StepStatus.CANCELLED},
        }

        allowed = valid_transitions.get(from_status, set())
        if to_status not in allowed:
            result.add(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=f"Invalid transition: {from_status.value} -> {to_status.value}",
                step_id=step_id,
                code="INVALID_TRANSITION",
                details={"allowed": [s.value for s in allowed]},
            ))

        return result
