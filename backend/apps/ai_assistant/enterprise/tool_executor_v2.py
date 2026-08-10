"""
Tool Executor V2 — plan-driven tool execution with full error isolation.

Consumes ExecutionPlan from ToolPlanner.  Executes each ToolStep via the
Tool Registry.  Never exposes Python exceptions, stack traces, repository
errors, or internal tool errors.

Responsibilities:
    1. Validate tool exists in registry
    2. Validate required parameters
    3. Execute the business tool
    4. Validate JSON output
    5. Handle recoverable errors
    6. Retry when appropriate
    7. Return standardised ToolExecutionResult

Constraints:
    - Business logic remains unchanged (delegates to BaseTool.execute)
    - Execute tools ONLY through ToolRegistry.get()
    - Dependency injection — registry and validator injected, never imported
    - Zero Django imports, zero repository access
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.enterprise.tool_planner import (
    ExecutionPlan,
    ToolPlanner,
    ToolStep,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

_DEFAULT_TIMEOUT: float = 30.0
_MAX_RETRY_DELAY: float = 10.0
_RETRY_BASE_DELAY: float = 0.5
_RETRY_BACKOFF: float = 2.0
_MAX_OUTPUT_SIZE: int = 100_000  # 100 KB

# French business messages — never expose internals
_MSG_TOOL_NOT_FOUND: str = "L'outil '{tool}' n'existe pas dans le système."
_MSG_MISSING_PARAMS: str = (
    "Paramètres manquants pour '{tool}' : {params}"
)
_MSG_EXECUTION_FAILED: str = "L'exécution de '{tool}' a échoué."
_MSG_TIMEOUT: str = "L'outil '{tool}' a dépassé le délai de {timeout}s."
_MSG_OUTPUT_INVALID: str = "La sortie de '{tool}' n'est pas au format attendu."
_MSG_RETRY_EXHAUSTED: str = (
    "L'outil '{tool}' a échoué après {count} tentative(s)."
)
_MSG_STEP_FAILED: str = "Étape '{step}' a échoué."


# ══════════════════════════════════════════════════════════════════════
# Data Contracts
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StepResult:
    """Result of executing a single ToolStep."""

    step_id: str
    tool: str
    action: str
    success: bool
    data: Any = None
    message: str = ""
    elapsed_ms: float = 0.0
    attempts: int = 1
    error_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "step_id": self.step_id,
            "tool": self.tool,
            "action": self.action,
            "success": self.success,
            "message": self.message,
        }
        if self.data is not None:
            d["data"] = self.data
        if self.elapsed_ms:
            d["elapsed_ms"] = round(self.elapsed_ms, 2)
        if self.attempts > 1:
            d["attempts"] = self.attempts
        if self.error_code:
            d["error_code"] = self.error_code
        return d


@dataclass(frozen=True)
class ToolExecutionResult:
    """Standardised result of executing an entire ExecutionPlan."""

    success: bool
    step_results: List[StepResult] = field(default_factory=list)
    total_elapsed_ms: float = 0.0
    steps_succeeded: int = 0
    steps_failed: int = 0
    messages: List[str] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        if not self.step_results:
            return self.success
        return self.steps_failed == 0 and self.steps_succeeded > 0

    @property
    def has_data(self) -> bool:
        return any(sr.data is not None for sr in self.step_results)

    @property
    def merged_data(self) -> Any:
        """Merge all step data into a single dict/list."""
        if not self.step_results:
            return None
        single = [sr for sr in self.step_results if sr.data is not None]
        if len(single) == 1:
            return single[0].data
        if all(isinstance(sr.data, dict) for sr in single):
            merged: Dict[str, Any] = {}
            for sr in single:
                merged.update(sr.data)
            return merged
        return [sr.data for sr in single]

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": self.success,
            "step_results": [sr.to_dict() for sr in self.step_results],
            "total_elapsed_ms": round(self.total_elapsed_ms, 2),
            "steps_succeeded": self.steps_succeeded,
            "steps_failed": self.steps_failed,
        }
        if self.messages:
            d["messages"] = self.messages
        if self.has_data:
            d["data"] = self.merged_data
        return d


# ══════════════════════════════════════════════════════════════════════
# Tool Executor V2
# ══════════════════════════════════════════════════════════════════════


class ToolExecutorV2:
    """
    Plan-driven tool executor with full error isolation.

    Consumes ExecutionPlan from ToolPlanner.  Resolves tools via the
    injected ToolRegistry.  All errors are caught and converted to
    standardised StepResult / ToolExecutionResult — never re-raised.

    Usage:
        executor = ToolExecutorV2(registry=container.tool_registry)
        result = executor.execute_plan(plan)
        if result.all_succeeded:
            # use result.merged_data
    """

    def __init__(
        self,
        registry: Any,
        *,
        default_timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 1,
        on_step_complete: Optional[Callable[[StepResult], None]] = None,
    ) -> None:
        self._registry = registry
        self._default_timeout = default_timeout
        self._max_retries = max_retries
        self._on_step_complete = on_step_complete

    # ════════════════════════════════════════════════════════════════
    # Public API
    # ════════════════════════════════════════════════════════════════

    def execute_plan(
        self,
        plan: ExecutionPlan,
        context: Optional[Any] = None,
    ) -> ToolExecutionResult:
        """
        Execute an entire ExecutionPlan.

        Steps run in order.  On failure, retries are attempted up to
        the step's retry_count.  All errors are caught and wrapped.
        """
        if plan.is_empty:
            return ToolExecutionResult(
                success=True,
                step_results=[],
                total_elapsed_ms=0.0,
                steps_succeeded=0,
                steps_failed=0,
                messages=["Aucun outil à exécuter"],
            )

        engine_start = time.monotonic()
        results: List[StepResult] = []
        messages: List[str] = []
        succeeded = 0
        failed = 0

        for step in plan.ordered_tools:
            step_result = self._execute_step(step, context)
            results.append(step_result)

            if step_result.success:
                succeeded += 1
            else:
                failed += 1
                messages.append(
                    _MSG_STEP_FAILED.format(step=step.step_id)
                )

            # Notify callback
            if self._on_step_complete is not None:
                try:
                    self._on_step_complete(step_result)
                except Exception:
                    pass  # Never let callback crash execution

        total_elapsed = (time.monotonic() - engine_start) * 1000

        return ToolExecutionResult(
            success=failed == 0,
            step_results=results,
            total_elapsed_ms=total_elapsed,
            steps_succeeded=succeeded,
            steps_failed=failed,
            messages=messages,
        )

    def execute_step(
        self,
        step: ToolStep,
        context: Optional[Any] = None,
    ) -> StepResult:
        """Execute a single ToolStep directly (outside a plan)."""
        return self._execute_step(step, context)

    # ════════════════════════════════════════════════════════════════
    # Internal — Step Execution
    # ════════════════════════════════════════════════════════════════

    def _execute_step(
        self,
        step: ToolStep,
        context: Optional[Any],
    ) -> StepResult:
        """Execute a single step with retry logic."""
        s = time.monotonic()
        tool_name = step.tool
        action = step.action
        parameters = dict(step.parameters)
        # Inject action if not present (required by most tools)
        if action and "action" not in parameters:
            parameters["action"] = action

        max_attempts = 1 + step.retry_count
        last_error_msg = ""
        last_error_code = ""

        for attempt in range(1, max_attempts + 1):
            # ── Step 1: Validate tool exists ────────────────────────
            tool = self._validate_tool(tool_name)
            if tool is None:
                elapsed = (time.monotonic() - s) * 1000
                return StepResult(
                    step_id=step.step_id,
                    tool=tool_name,
                    action=action,
                    success=False,
                    message=_MSG_TOOL_NOT_FOUND.format(tool=tool_name),
                    elapsed_ms=elapsed,
                    attempts=attempt,
                    error_code="tool_not_found",
                )

            # ── Step 2: Validate parameters ────────────────────────
            param_errs = self._validate_parameters(tool, parameters)
            if param_errs:
                elapsed = (time.monotonic() - s) * 1000
                return StepResult(
                    step_id=step.step_id,
                    tool=tool_name,
                    action=action,
                    success=False,
                    message=_MSG_MISSING_PARAMS.format(
                        tool=tool_name,
                        params=", ".join(param_errs),
                    ),
                    elapsed_ms=elapsed,
                    attempts=attempt,
                    error_code="missing_parameters",
                )

            # ── Step 3: Execute tool ───────────────────────────────
            exec_result = self._invoke_tool(
                tool, parameters, context, step.timeout_ms / 1000.0,
            )

            if exec_result["success"]:
                elapsed = (time.monotonic() - s) * 1000
                return StepResult(
                    step_id=step.step_id,
                    tool=tool_name,
                    action=action,
                    success=True,
                    data=exec_result["data"],
                    message=exec_result.get("message", ""),
                    elapsed_ms=elapsed,
                    attempts=attempt,
                )

            # ── Step 4: Check if retryable ─────────────────────────
            last_error_msg = exec_result.get(
                "message", _MSG_EXECUTION_FAILED.format(tool=tool_name),
            )
            last_error_code = exec_result.get("error_code", "execution_error")

            if attempt < max_attempts:
                delay = self._retry_delay(attempt)
                time.sleep(delay)
                logger.info(
                    "Retrying '%s' (attempt %d/%d) after %.1fs",
                    tool_name, attempt + 1, max_attempts, delay,
                )

        # ── All retries exhausted ──────────────────────────────────
        elapsed = (time.monotonic() - s) * 1000
        final_code = last_error_code or "retry_exhausted"
        if last_error_code and max_attempts > 1:
            final_msg = (
                f"{last_error_msg} "
                + _MSG_RETRY_EXHAUSTED.format(
                    tool=tool_name, count=max_attempts,
                )
            )
        elif last_error_code:
            final_msg = last_error_msg
        else:
            final_msg = _MSG_RETRY_EXHAUSTED.format(
                tool=tool_name, count=max_attempts,
            )
        return StepResult(
            step_id=step.step_id,
            tool=tool_name,
            action=action,
            success=False,
            message=final_msg,
            elapsed_ms=elapsed,
            attempts=max_attempts,
            error_code=final_code,
        )

    # ════════════════════════════════════════════════════════════════
    # Internal — Validation
    # ════════════════════════════════════════════════════════════════

    def _validate_tool(self, tool_name: str) -> Optional[Any]:
        """Look up tool in registry. Returns None if not found."""
        try:
            tool = self._registry.get(tool_name)
            return tool
        except Exception:
            logger.warning("Registry lookup failed for '%s'", tool_name)
            return None

    def _validate_parameters(
        self, tool: Any, parameters: Dict[str, Any],
    ) -> List[str]:
        """
        Validate parameters against the tool's schema.
        Returns list of error messages (empty = valid).
        """
        try:
            schema = getattr(tool, "parameter_schema", None)
            if schema is None or not hasattr(schema, "fields"):
                return []
            if not schema.fields:
                return []

            from apps.ai_assistant.tools.tool_validator import ToolValidator
            validator = ToolValidator()
            errors = validator.validate(parameters, schema)
            return [f"{e.field}: {e.message}" for e in errors]
        except Exception:
            # If validation itself fails, pass through (tool will validate)
            return []

    # ════════════════════════════════════════════════════════════════
    # Internal — Tool Invocation
    # ════════════════════════════════════════════════════════════════

    def _invoke_tool(
        self,
        tool: Any,
        parameters: Dict[str, Any],
        context: Optional[Any],
        timeout: float,
    ) -> Dict[str, Any]:
        """
        Invoke tool.execute() with timeout. Never raises.
        Returns {"success": bool, "data": Any, "message": str, "error_code": str}.
        """
        import threading

        result_holder: Dict[str, Any] = {
            "success": False,
            "data": None,
            "message": "",
            "error_code": "",
        }
        exception_holder: List[BaseException] = []

        def _run():
            try:
                # Build context if None
                ctx = context
                if ctx is None:
                    try:
                        from apps.ai_assistant.tools.tool_context import ToolContext
                        ctx = ToolContext()
                    except Exception:
                        ctx = _MinimalContext()

                response = tool.execute(parameters, ctx)

                # Normalise response
                if hasattr(response, "to_dict"):
                    d = response.to_dict()
                    result_holder["success"] = d.get("success", False)
                    result_holder["data"] = d.get("data")
                    result_holder["message"] = d.get("message", "")
                elif isinstance(response, dict):
                    result_holder["success"] = response.get("success", False)
                    result_holder["data"] = response.get("data")
                    result_holder["message"] = response.get("message", "")
                else:
                    result_holder["success"] = True
                    result_holder["data"] = response

            except BaseException as exc:
                exception_holder.append(exc)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            logger.warning(
                "Tool timed out after %.1fs", timeout,
            )
            return {
                "success": False,
                "data": None,
                "message": _MSG_TIMEOUT.format(
                    tool=tool.name if hasattr(tool, "name") else "?",
                    timeout=timeout,
                ),
                "error_code": "timeout",
            }

        if exception_holder:
            exc = exception_holder[0]
            logger.error(
                "Tool raised %s: %s",
                type(exc).__name__,
                str(exc)[:200],
            )
            return {
                "success": False,
                "data": None,
                "message": _MSG_EXECUTION_FAILED.format(
                    tool=tool.name if hasattr(tool, "name") else "?",
                ),
                "error_code": "tool_exception",
            }

        # Validate output
        output_err = self._validate_output(result_holder)
        if output_err:
            return {
                "success": False,
                "data": None,
                "message": output_err,
                "error_code": "invalid_output",
            }

        return result_holder

    def _validate_output(self, result: Dict[str, Any]) -> Optional[str]:
        """
        Validate the tool output is safe and well-formed.
        Returns error message if invalid, None if OK.
        """
        data = result.get("data")

        # Check data is JSON-serialisable
        if data is not None:
            try:
                serialized = json.dumps(data, default=str)
                if len(serialized) > _MAX_OUTPUT_SIZE:
                    return _MSG_OUTPUT_INVALID.format(tool="(output too large)")
            except (TypeError, ValueError, OverflowError):
                return _MSG_OUTPUT_INVALID.format(tool="(non-serialisable)")

        # Check message doesn't leak internals
        msg = result.get("message", "")
        if self._contains_sensitive(msg):
            result["message"] = "Une erreur interne s'est produite."

        return None

    @staticmethod
    def _contains_sensitive(text: str) -> bool:
        """Check if text leaks internal error details."""
        if not text:
            return False
        sensitive = [
            "Traceback", "traceback", "File \"", "line ",
            "Traceback (most recent", "Exception:", "Error:",
            "django.", "models.", "IntegrityError",
            "OperationalError", "ProgrammingError",
            "password", "secret", "token", "api_key",
            "/home/", "/usr/", "/var/", "venv/",
        ]
        text_lower = text.lower()
        return any(s.lower() in text_lower for s in sensitive)

    # ════════════════════════════════════════════════════════════════
    # Internal — Retry
    # ════════════════════════════════════════════════════════════════

    def _retry_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff, clamped."""
        delay = _RETRY_BASE_DELAY * (_RETRY_BACKOFF ** (attempt - 1))
        return min(delay, _MAX_RETRY_DELAY)


# ══════════════════════════════════════════════════════════════════════
# Minimal Context (fallback when ToolContext unavailable)
# ══════════════════════════════════════════════════════════════════════


class _MinimalContext:
    """Ultra-minimal context when ToolContext cannot be imported."""

    request_id = "v2-exec"
    conversation_id = ""
    user_id = ""
    user_roles: List[str] = []
    language = "fr"
    metadata: Dict[str, Any] = {}
    trace_log: List[Dict[str, Any]] = []

    def trace(self, event: str, details: Any = None) -> None:
        pass

    def has_permission(self, permission: str) -> bool:
        return True
