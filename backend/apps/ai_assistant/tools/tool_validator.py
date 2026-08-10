"""
Tool Validator — schema-based parameter validation.

Validates tool parameters against declared schemas before execution.
Supports type checking, required fields, enums, ranges, and custom rules.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation Error
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationError:
    """A single validation failure."""
    field: str
    message: str
    code: str = "invalid"

    def to_dict(self) -> Dict[str, str]:
        return {"field": self.field, "message": self.message, "code": self.code}


# ---------------------------------------------------------------------------
# Schema Definition
# ---------------------------------------------------------------------------

@dataclass
class FieldSchema:
    """Schema for a single parameter field."""
    name: str
    type: str  # "str", "int", "float", "bool", "list", "dict", "any"
    required: bool = True
    default: Any = None
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    enum: Optional[List[Any]] = None
    allow_none: bool = False
    nested_schema: Optional["ParameterSchema"] = None


@dataclass
class ParameterSchema:
    """Full parameter schema for a tool."""
    fields: List[FieldSchema] = field(default_factory=list)
    extra_fields_allowed: bool = False
    custom_rules: List[Callable[[Dict[str, Any]], List[ValidationError]]] = field(
        default_factory=list, repr=False
    )

    def add_field(self, **kwargs: Any) -> ParameterSchema:
        self.fields.append(FieldSchema(**kwargs))
        return self

    def add_custom_rule(self, rule: Callable[[Dict[str, Any]], List[ValidationError]]) -> ParameterSchema:
        self.custom_rules.append(rule)
        return self


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ToolValidator:
    """
    Validates parameters against a ParameterSchema.

    Returns a list of ValidationError objects. Empty list = valid.
    """

    _TYPE_MAP = {
        "str": str,
        "int": int,
        "float": (int, float),
        "bool": bool,
        "list": list,
        "dict": dict,
        "any": None,
    }

    def validate(self, parameters: Dict[str, Any], schema: ParameterSchema) -> List[ValidationError]:
        errors: List[ValidationError] = []

        if not schema.extra_fields_allowed:
            known = {f.name for f in schema.fields}
            for key in parameters:
                if key not in known:
                    errors.append(ValidationError(
                        field=key,
                        message=f"Unknown parameter '{key}'",
                        code="unknown_field",
                    ))

        for field_schema in schema.fields:
            field_errors = self._validate_field(parameters, field_schema)
            errors.extend(field_errors)

        for rule in schema.custom_rules:
            try:
                rule_errors = rule(parameters)
                errors.extend(rule_errors)
            except Exception as exc:
                logger.error("Custom rule failed: %s", exc)
                errors.append(ValidationError(
                    field="<custom_rule>",
                    message=f"Custom rule error: {exc}",
                    code="rule_error",
                ))

        if errors:
            logger.warning("Validation failed: %d errors", len(errors))
        return errors

    # -- field-level --

    def _validate_field(self, parameters: Dict[str, Any], fs: FieldSchema) -> List[ValidationError]:
        errors: List[ValidationError] = []
        value = parameters.get(fs.name, _MISSING)

        if value is _MISSING:
            if fs.required:
                errors.append(ValidationError(
                    field=fs.name,
                    message=f"Required parameter '{fs.name}' is missing",
                    code="required",
                ))
            return errors

        if value is None:
            if fs.allow_none:
                return errors
            errors.append(ValidationError(
                field=fs.name,
                message=f"Parameter '{fs.name}' cannot be null",
                code="null_not_allowed",
            ))
            return errors

        if fs.enum is not None and value not in fs.enum:
            errors.append(ValidationError(
                field=fs.name,
                message=f"Parameter '{fs.name}' must be one of {fs.enum}, got '{value}'",
                code="invalid_enum",
            ))
            return errors

        expected = self._TYPE_MAP.get(fs.type)
        if expected is not None and not isinstance(value, expected):
            errors.append(ValidationError(
                field=fs.name,
                message=f"Parameter '{fs.name}' must be {fs.type}, got {type(value).__name__}",
                code="invalid_type",
            ))
            return errors

        if isinstance(value, (str, list)):
            if fs.min_length is not None and len(value) < fs.min_length:
                errors.append(ValidationError(
                    field=fs.name,
                    message=f"Parameter '{fs.name}' length must be >= {fs.min_length}",
                    code="too_short",
                ))
            if fs.max_length is not None and len(value) > fs.max_length:
                errors.append(ValidationError(
                    field=fs.name,
                    message=f"Parameter '{fs.name}' length must be <= {fs.max_length}",
                    code="too_long",
                ))

        if isinstance(value, (int, float)):
            if fs.min_value is not None and value < fs.min_value:
                errors.append(ValidationError(
                    field=fs.name,
                    message=f"Parameter '{fs.name}' must be >= {fs.min_value}",
                    code="too_small",
                ))
            if fs.max_value is not None and value > fs.max_value:
                errors.append(ValidationError(
                    field=fs.name,
                    message=f"Parameter '{fs.name}' must be <= {fs.max_value}",
                    code="too_large",
                ))

        if isinstance(value, str) and fs.pattern is not None:
            if not re.search(fs.pattern, value):
                errors.append(ValidationError(
                    field=fs.name,
                    message=f"Parameter '{fs.name}' does not match pattern '{fs.pattern}'",
                    code="pattern_mismatch",
                ))

        return errors


# ---------------------------------------------------------------------------
# Schema Builder (Fluent API)
# ---------------------------------------------------------------------------

class SchemaBuilder:
    """Fluent builder for ParameterSchema."""

    def __init__(self) -> None:
        self._schema = ParameterSchema()

    def field(self, name: str, type_: str = "str", **kwargs: Any) -> SchemaBuilder:
        self._schema.add_field(name=name, type=type_, **kwargs)
        return self

    def allow_extras(self) -> SchemaBuilder:
        self._schema.extra_fields_allowed = True
        return self

    def custom_rule(self, rule: Callable[[Dict[str, Any]], List[ValidationError]]) -> SchemaBuilder:
        self._schema.add_custom_rule(rule)
        return self

    def build(self) -> ParameterSchema:
        return self._schema


# placeholder sentinel
_MISSING = object()
