"""
Base Tool — abstract base class every tool must inherit from.

Provides: lifecycle hooks, auto-validation, logging, error wrapping,
and the standardised {success, message, data} return envelope.
"""

from __future__ import annotations

import abc
import logging
import time
from typing import Any, ClassVar, Dict, List, Optional, Type

from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import (
    ParameterSchema,
    ToolValidator,
    ValidationError,
)

logger = logging.getLogger(__name__)


class BaseTool(abc.ABC):
    """
    Every tool MUST inherit from this class.

    Subclasses implement:
        - name (property)
        - description (property)
        - _execute(params, ctx) → ToolResultResponse

    BaseTool handles:
        - Auto-validation against parameter_schema
        - Pre/post lifecycle hooks
        - Timing + logging
        - Exception wrapping into ToolResultResponse
        - Permission checking
    """

    # -- subclasses set these as class variables --
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__
        if not cls.description:
            cls.description = f"Tool: {cls.__name__}"

    # ------------------------------------------------------------------
    # Abstract — subclasses implement this
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _execute(
        self,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResultResponse:
        """
        Core tool logic. Subclasses MUST implement this.

        Args:
            parameters: Validated input parameters.
            context: Enriched execution context.

        Returns:
            ToolResultResponse with success/message/data.
        """
        ...

    # ------------------------------------------------------------------
    # Public API — called by executor
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def description(self) -> str:  # type: ignore[override]
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = value

    @property
    def parameter_schema(self) -> ParameterSchema:
        """Override to declare the tool's parameter schema."""
        return ParameterSchema()

    @property
    def required_permissions(self) -> List[str]:
        """Override to require specific permissions. Empty = no restrictions."""
        return []

    @property
    def timeout_seconds(self) -> float:
        """Override to set a per-tool timeout. Default: 30s."""
        return 30.0

    @property
    def version(self) -> str:
        return "1.0.0"

    def execute(
        self,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResultResponse:
        """
        Full execution pipeline: validate → pre-hook → execute → post-hook.

        DO NOT override. Override _execute() instead.
        """
        start = time.monotonic()
        context.trace("tool_start", {"tool": self.name, "params_keys": list(parameters.keys())})

        # 1. Validate
        validation_errors = self._validate(parameters)
        if validation_errors:
            messages = "; ".join(e.message for e in validation_errors)
            result = ToolResultResponse.fail(
                message=f"Validation failed: {messages}",
                data={"errors": [e.to_dict() for e in validation_errors]},
            )
            context.trace("tool_validation_failed", {"errors": len(validation_errors)})
            return result

        # 2. Permission check
        perm_error = self._check_permissions(context)
        if perm_error:
            context.trace("tool_permission_denied", {"required": self.required_permissions})
            return perm_error

        # 3. Pre-hook
        hook_error = self.on_before_execute(parameters, context)
        if hook_error:
            context.trace("tool_pre_hook_failed", {"error": hook_error.message})
            return hook_error

        # 4. Execute with error wrapping
        try:
            result = self._execute(parameters, context)
            if not isinstance(result, ToolResultResponse):
                result = ToolResultResponse.ok(data=result)
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "Tool '%s' raised %s after %.3fs: %s",
                self.name, type(exc).__name__, elapsed, exc,
                exc_info=True,
            )
            custom = self.on_error(exc, parameters, context)
            result = custom if custom is not None else ToolResultResponse.from_exception(
                exc, context=f"Tool '{self.name}'",
            )
            context.trace("tool_exception", {"type": type(exc).__name__, "message": str(exc)})
        else:
            elapsed = time.monotonic() - start
            logger.info(
                "Tool '%s' completed in %.3fs — success=%s",
                self.name, elapsed, result.success,
            )
            context.trace("tool_complete", {"success": result.success, "elapsed": round(elapsed, 3)})

        # 5. Post-hook
        self.on_after_execute(result, parameters, context)

        return result

    # ------------------------------------------------------------------
    # Lifecycle hooks (override in subclasses)
    # ------------------------------------------------------------------

    def on_before_execute(
        self,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> Optional[ToolResultResponse]:
        """
        Called before _execute. Return a ToolResultResponse to abort.
        Return None to continue.
        """
        return None

    def on_after_execute(
        self,
        result: ToolResultResponse,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> None:
        """Called after _execute. Cannot abort — just observe."""
        pass

    def on_error(
        self,
        exc: Exception,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> Optional[ToolResultResponse]:
        """Called when _execute raises. Return a custom error response or None."""
        return None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def to_schema(self) -> Dict[str, Any]:
        """Export tool metadata as a JSON-compatible dict (for LLM tool-calling)."""
        schema = self.parameter_schema
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for f in schema.fields:
            props: Dict[str, Any] = {"type": f.type}
            if f.description:
                props["description"] = f.description
            if f.enum:
                props["enum"] = f.enum
            if f.default is not None:
                props["default"] = f.default
            properties[f.name] = props
            if f.required:
                required.append(f.name)
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
            "required_permissions": self.required_permissions,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate(self, parameters: Dict[str, Any]) -> List[ValidationError]:
        schema = self.parameter_schema
        if not schema.fields:
            return []
        validator = ToolValidator()
        return validator.validate(parameters, schema)

    def _check_permissions(self, context: ToolContext) -> Optional[ToolResultResponse]:
        required = self.required_permissions
        if not required:
            return None
        for perm in required:
            if not context.has_permission(perm):
                return ToolResultResponse.fail(
                    message=f"Permission denied: '{perm}' required",
                    data={"required_permissions": required},
                )
        return None

    def __init__(self) -> None:
        self._name = self.__class__.name or self.__class__.__name__
        self._description = self.__class__.description or ""
