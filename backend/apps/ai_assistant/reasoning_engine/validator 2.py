"""
Validation Stage — validates tool execution results.

Checks completeness, consistency, and quality of results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.reasoning_engine.pipeline import PipelineContext, PipelineStage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation Rule
# ---------------------------------------------------------------------------

@dataclass
class ValidationRule:
    """A single validation rule."""
    name: str
    check: Callable[[Dict[str, Any], PipelineContext], bool]
    message: str = ""
    severity: str = "error"  # error, warning, info


@dataclass
class ValidationResult:
    """Result of a single validation."""
    rule: str
    passed: bool
    message: str
    severity: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
        }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ResultValidator:
    """Validates tool execution results against rules."""

    def __init__(self, rules: Optional[List[ValidationRule]] = None) -> None:
        self._rules = rules or self._default_rules()

    def validate(
        self,
        results: List[Dict[str, Any]],
        context: PipelineContext,
    ) -> List[ValidationResult]:
        validations: List[ValidationResult] = []

        for rule in self._rules:
            try:
                passed = rule.check(results, context)
                validations.append(ValidationResult(
                    rule=rule.name,
                    passed=passed,
                    message=rule.message if not passed else "",
                    severity=rule.severity,
                ))
            except Exception as exc:
                validations.append(ValidationResult(
                    rule=rule.name,
                    passed=False,
                    message=f"Validation error: {exc}",
                    severity="error",
                ))

        return validations

    @staticmethod
    def _default_rules() -> List[ValidationRule]:
        return [
            ValidationRule(
                name="has_results",
                check=lambda r, c: bool(r),
                message="No tool results to validate",
                severity="warning",
            ),
            ValidationRule(
                name="results_are_dicts",
                check=lambda r, c: all(isinstance(x, dict) for x in r),
                message="Some results are not dictionaries",
                severity="error",
            ),
            ValidationRule(
                name="no_empty_results",
                check=lambda r, c: not any(not x for x in r),
                message="Some results are empty",
                severity="warning",
            ),
        ]


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class ValidationStage(PipelineStage):
    """
    Stage 6: Validate tool execution results.

    Checks completeness and quality. Does not modify results.
    """

    name = "validation"
    order = 60

    def __init__(
        self,
        validator: Optional[ResultValidator] = None,
        strict: bool = False,
    ) -> None:
        self._validator = validator or ResultValidator()
        self._strict = strict

    def should_run(self, context: PipelineContext) -> bool:
        return bool(context.executed_tools)

    def process(self, context: PipelineContext) -> None:
        validations = self._validator.validate(context.tool_results, context)

        context.validation_results = [v.to_dict() for v in validations]

        # Check if any critical validations failed
        errors = [v for v in validations if not v.passed and v.severity == "error"]
        warnings = [v for v in validations if not v.passed and v.severity == "warning"]

        if errors and self._strict:
            context.error_message = "; ".join(e.message for e in errors)
            logger.warning("Validation failed (strict): %s", context.error_message)
        elif warnings:
            logger.debug("Validation warnings: %s", [w.message for w in warnings])

        logger.debug(
            "Validation: %d passed, %d errors, %d warnings",
            sum(1 for v in validations if v.passed),
            len(errors),
            len(warnings),
        )
