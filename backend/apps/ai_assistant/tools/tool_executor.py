"""
Tool Executor — validated execution pipeline with zero error leakage.

Pipeline:
    1. Validate Tool      → tool exists in registry
    2. Execute Tool        → timeout guard + retry + circuit breaker
    3. Middleware: after   → post-processing hooks
    4. Validate Response   → shape + sanitisation (catches injected data)
    5. Return JSON         → clean ToolResultResponse

Features:
    - Circuit breaker: opens after N consecutive failures, auto-resolves
    - Total timeout: cumulative wall-clock cap across all retries
    - ResponseValidator: sanitises ALL output (tool + middleware injected)
    - Middleware chain: before/after/on_error hooks

Errors NEVER leak:
    - No Python tracebacks
    - No repository exceptions
    - No tool internals
    - All failures → French business messages
"""

from __future__ import annotations

import logging
import re
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_registry import ToolRegistry
from apps.ai_assistant.tools.tool_result import ToolResultResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Middleware (Chain of Responsibility)
# ---------------------------------------------------------------------------

class ToolMiddleware(ABC):
    """Intercepts tool execution for cross-cutting concerns."""

    @abstractmethod
    def before(
        self,
        tool: BaseTool,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> Optional[ToolResultResponse]:
        """Return None to continue, or a ToolResultResponse to short-circuit."""
        ...

    @abstractmethod
    def after(
        self,
        tool: BaseTool,
        result: ToolResultResponse,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResultResponse:
        """Called after execution. Can transform the result."""
        ...

    def on_error(
        self,
        tool: BaseTool,
        exc: Exception,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> Optional[ToolResultResponse]:
        """Called when execution raises. Return a fallback or None to propagate."""
        return None


class LoggingMiddleware(ToolMiddleware):
    """Logs every tool invocation."""

    def before(self, tool, parameters, context):
        logger.info(
            "[EXEC] %s | user=%s | params=%s",
            tool.name, context.user_id, list(parameters.keys()),
        )
        return None

    def after(self, tool, result, parameters, context):
        logger.info(
            "[EXEC] %s | success=%s | %.3fs",
            tool.name, result.success, context.elapsed_seconds,
        )
        return result

    def on_error(self, tool, exc, parameters, context):
        logger.error("[EXEC] %s | ERROR: %s", tool.name, exc)
        return None


class AuditMiddleware(ToolMiddleware):
    """Records execution traces for auditing."""

    def before(self, tool, parameters, context):
        context.trace("middleware_audit_before", {"tool": tool.name})
        return None

    def after(self, tool, result, parameters, context):
        context.trace("middleware_audit_after", {
            "tool": tool.name,
            "success": result.success,
        })
        return result


class RateLimitMiddleware(ToolMiddleware):
    """Simple per-tool rate limiter (token bucket)."""

    def __init__(self, max_calls: int = 60, window_seconds: float = 60.0) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._calls: Dict[str, List[float]] = {}

    def before(self, tool, parameters, context):
        now = time.monotonic()
        calls = self._calls.setdefault(tool.name, [])
        calls[:] = [t for t in calls if now - t < self._window]
        if len(calls) >= self._max:
            return ToolResultResponse.fail(
                message="Trop de requêtes. Veuillez patienter puis réessayer.",
                data={"limit": self._max, "window": self._window},
            )
        calls.append(now)
        return None

    def after(self, tool, result, parameters, context):
        return result


# ---------------------------------------------------------------------------
# Retry Policy
# ---------------------------------------------------------------------------

@dataclass
class RetryPolicy:
    """Configurable retry behaviour."""
    max_retries: int = 0
    delay_seconds: float = 0.5
    backoff_factor: float = 2.0
    retry_on: tuple = ()  # exception types to retry on


# ---------------------------------------------------------------------------
# Execution Stats
# ---------------------------------------------------------------------------

@dataclass
class ExecutionStats:
    """Aggregated execution statistics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_time_seconds: float = 0.0
    per_tool: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    def record(self, tool_name: str, success: bool, elapsed: float) -> None:
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_time_seconds += elapsed
        self.per_tool[tool_name] = self.per_tool.get(tool_name, 0) + 1


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

@dataclass
class CircuitBreakerState:
    """Tracks consecutive failures for a single tool."""
    consecutive_failures: int = 0
    last_failure_time: float = 0.0


# ---------------------------------------------------------------------------
# Response Validator
# ---------------------------------------------------------------------------

class ResponseValidator:
    """Validates and sanitises tool responses.

    Ensures every result is a clean, JSON-safe ToolResultResponse.
    Never exposes internal data structures, stack traces, or error details.
    """

    _SENSITIVE_PATTERNS: List[re.Pattern] = [
        re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
        re.compile(r"File \".*\.py\", line \d+", re.IGNORECASE),
        re.compile(r"django\.db\.", re.IGNORECASE),
        re.compile(r"psycopg2\.", re.IGNORECASE),
        re.compile(r"sqlite3\.", re.IGNORECASE),
        re.compile(r"password\s*=\s*", re.IGNORECASE),
        re.compile(r"secret\s*=\s*", re.IGNORECASE),
        re.compile(r"token\s*=\s*", re.IGNORECASE),
        re.compile(r"api[_-]?key\s*=\s*", re.IGNORECASE),
    ]

    # Matches BaseTool's from_exception() output: "Tool 'name' — ExcType: message"
    # Also matches plain "ExcType: message" patterns
    _EXCEPTION_MESSAGE_PATTERN = re.compile(
        r"^Tool\s+'[^']+'\s*[—–-]\s*"
        r"(?:\w+(?:\.\w+)*)\s*:\s*.+$",
        re.IGNORECASE,
    )

    _EXCEPTION_CLASS_PATTERN = re.compile(
        r"(?:^|\s)"
        r"(?:ValueError|RuntimeError|TypeError|KeyError|AttributeError|"
        r"IOError|OSError|ConnectionError|TimeoutError|DatabaseError|"
        r"IntegrityError|OperationalError|ProgrammingError|"
        r"NotImplementedError|IndexError|StopIteration|"
        r"ImportError|ModuleNotFoundError|PermissionError|"
        r"FileNotFoundError|JSONDecodeError|UnicodeDecodeError|"
        r"ObjectDoesNotExist|MultipleObjectsReturned|FieldDoesNotExist|"
        r"DataError|InternalError|InterfaceError|NotSupportedError|"
        r"SerializationError|DeserializationError|ObjectNotFrozen|"
        r"CacheKeyWarning|SynchronousOnlyOperation)"
        r"\s*:\s*.+",
    )

    _MAX_DATA_SIZE: int = 100_000  # 100KB max payload

    @classmethod
    def validate(cls, result: ToolResultResponse, tool_name: str) -> ToolResultResponse:
        """Validate and sanitise a tool result.

        Checks:
            1. Result is ToolResultResponse
            2. success is bool
            3. message is str
            4. data is JSON-serialisable
            5. No sensitive patterns in message
            6. No exception details in message
            7. Payload size within limits

        Returns sanitised ToolResultResponse or a business-error fallback.
        """
        if result is None:
            return ToolResultResponse.fail(
                message=_ErrorMessages.TOOL_CRASHED,
            )

        if not isinstance(result, ToolResultResponse):
            return ToolResultResponse.fail(
                message=_ErrorMessages.TOOL_INVALID_RESPONSE,
            )

        if not isinstance(result.success, bool):
            result.success = False

        original_message = str(result.message) if result.message else ""
        result.message = cls._sanitise_message(result.message, result.success)
        result.data = cls._sanitise_data(result.data)

        if not result.success and not result.data.get("error_code"):
            if cls._EXCEPTION_MESSAGE_PATTERN.match(original_message) or \
               cls._EXCEPTION_CLASS_PATTERN.search(original_message):
                result.data["error_code"] = "EXECUTION_ERROR"

        size = cls._estimate_size(result.data)
        if size > cls._MAX_DATA_SIZE:
            logger.warning(
                "Tool '%s' returned oversized payload (%d bytes), truncating",
                tool_name, size,
            )
            result.data = cls._truncate_data(result.data)

        return result

    @classmethod
    def _sanitise_text(cls, text: str) -> str:
        """Strip sensitive patterns from raw text."""
        if not isinstance(text, str):
            return str(text) if text else ""
        for pattern in cls._SENSITIVE_PATTERNS:
            text = pattern.sub("", text)
        text = text.strip()
        if len(text) > 2000:
            text = text[:2000] + "..."
        return text

    @classmethod
    def _sanitise_message(cls, message: str, success: bool) -> str:
        """Sanitise a message: strip exception details, sensitive patterns.

        For failed results, replaces exception-style messages with business messages.
        For successful results, strips sensitive patterns only.
        """
        if not isinstance(message, str):
            message = str(message) if message else ""

        message = message.strip()

        if not success:
            if cls._EXCEPTION_MESSAGE_PATTERN.match(message):
                return _ErrorMessages.TOOL_CRASHED
            if cls._EXCEPTION_CLASS_PATTERN.search(message):
                return _ErrorMessages.TOOL_CRASHED

        return cls._sanitise_text(message)

    _SENSITIVE_KEYS: Set[str] = {
        "password", "secret", "token", "api_key", "apikey",
        "api-key", "secret_key", "secretkey", "access_token",
        "private_key", "privatekey", "auth_token",
        "db_password", "database_password", "encryption_key",
        "signing_key", "jwt_secret", "session_key",
        "credit_card", "card_number", "cvv", "ssn",
        " bearer", "authorization",
    }

    @classmethod
    def _sanitise_data(cls, data: Any) -> Any:
        """Ensure data is JSON-serialisable and safe."""
        if data is None:
            return {}
        if isinstance(data, str):
            return cls._sanitise_text(data)
        if isinstance(data, (int, float, bool)):
            return data
        if isinstance(data, dict):
            return {
                k: "[REDACTED]" if k.lower() in cls._SENSITIVE_KEYS
                else cls._sanitise_data(v)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [cls._sanitise_data(item) for item in data[:100]]
        return str(data)[:500]

    @classmethod
    def _truncate_data(cls, data: Any) -> Any:
        """Truncate oversized data to safe limits."""
        if isinstance(data, dict):
            keys = list(data.keys())[:20]
            return {k: data[k] for k in keys}
        if isinstance(data, list):
            return data[:20]
        return str(data)[:1000]

    @classmethod
    def _estimate_size(cls, data: Any) -> int:
        """Rough estimate of serialised size."""
        try:
            import json
            return len(json.dumps(data, ensure_ascii=False, default=str))
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# Error Messages (French business messages — never expose internals)
# ---------------------------------------------------------------------------

class _ErrorMessages:
    """Centralised French business error messages."""

    TOOL_NOT_FOUND = "L'outil demandé n'est pas disponible. Veuillez reformuler votre question."
    TOOL_TIMEOUT = "L'outil a pris trop de temps à répondre. Veuillez réessayer."
    TOOL_CRASHED = "Une erreur est survenue lors du traitement. Veuillez réessayer."
    TOOL_INVALID_RESPONSE = "L'outil a retourné une réponse invalide. Veuillez réessayer."
    VALIDATION_FAILED = "Les paramètres sont invalides."
    NO_RESULT = "L'outil n'a produit aucun résultat."
    MAX_RETRIES = "L'outil a échoué après plusieurs tentatives. Veuillez réessayer plus tard."
    CIRCUIT_OPEN = "L'outil temporairement indisponible. Veuillez réessayer dans quelques instants."


# ---------------------------------------------------------------------------
# Tool Executor — 5-step validated pipeline
# ---------------------------------------------------------------------------

class ToolExecutor:
    """Executes tools through a validated pipeline with zero error leakage.

    Pipeline:
        1. Validate Tool      — registry lookup, fail with business message
        2. Execute Tool        — timeout + retry + circuit breaker
        3. Middleware: after   — post-processing hooks
        4. Validate Response   — shape + sanitisation, no error leakage
        5. Return JSON         — clean ToolResultResponse

    Features:
        - Circuit breaker: opens after N consecutive failures, auto-resolves
        - Total timeout: cumulative wall-clock cap across all retries
        - Middleware chain: before/after/on_error hooks
        - ResponseValidator: sanitises ALL output (tool + middleware injected)

    Error policy:
        - NO Python tracebacks in responses
        - NO repository exception details
        - NO tool internal state
        - ALL failures → French business messages
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        default_retry: Optional[RetryPolicy] = None,
        default_timeout: float = 30.0,
        thread_pool_size: int = 4,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_recovery: float = 30.0,
    ) -> None:
        self._registry = registry
        self._middleware: List[ToolMiddleware] = []
        self._default_retry = default_retry or RetryPolicy()
        self._default_timeout = default_timeout
        self._stats = ExecutionStats()
        self._thread_pool_size = thread_pool_size
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._cb_threshold = circuit_breaker_threshold
        self._cb_recovery = circuit_breaker_recovery

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

    def add_middleware(self, middleware: ToolMiddleware) -> ToolExecutor:
        self._middleware.append(middleware)
        return self

    def clear_middleware(self) -> None:
        self._middleware.clear()

    # ------------------------------------------------------------------
    # Circuit Breaker
    # ------------------------------------------------------------------

    def _check_circuit_breaker(self, tool_name: str) -> Optional[ToolResultResponse]:
        """Check if circuit is open. Returns failure response if blocked."""
        cb = self._circuit_breakers.get(tool_name)
        if cb is None or cb.consecutive_failures < self._cb_threshold:
            return None
        elapsed = time.monotonic() - cb.last_failure_time
        if elapsed >= self._cb_recovery:
            cb.consecutive_failures = 0
            logger.info("Circuit breaker reset for '%s' after %.1fs", tool_name, elapsed)
            return None
        logger.warning(
            "Circuit breaker OPEN for '%s' (%d failures, %.1fs since last)",
            tool_name, cb.consecutive_failures, elapsed,
        )
        return ToolResultResponse.fail(
            message=_ErrorMessages.CIRCUIT_OPEN,
            data={"error_code": "CIRCUIT_OPEN", "tool": tool_name},
        )

    def _record_circuit_breaker(self, tool_name: str, success: bool) -> None:
        """Record outcome for circuit breaker tracking."""
        cb = self._circuit_breakers.setdefault(tool_name, CircuitBreakerState())
        if success:
            cb.consecutive_failures = 0
        else:
            cb.consecutive_failures += 1
            cb.last_failure_time = time.monotonic()

    # ------------------------------------------------------------------
    # Step 1: Validate Tool
    # ------------------------------------------------------------------

    def _validate_tool(self, tool_name: str) -> Optional[ToolResultResponse]:
        """Step 1 — verify tool exists in registry.

        Returns None if valid, or a failure ToolResultResponse.
        """
        if not tool_name or not isinstance(tool_name, str):
            return ToolResultResponse.fail(
                message=_ErrorMessages.TOOL_NOT_FOUND,
                data={"error_code": "INVALID_TOOL_NAME"},
            )

        tool = self._registry.get(tool_name)
        if tool is None:
            available = self._registry.list_names()
            similar = [t for t in available if tool_name.lower() in t.lower()]
            suggestion = similar[0] if similar else None
            return ToolResultResponse.fail(
                message=_ErrorMessages.TOOL_NOT_FOUND,
                data={
                    "error_code": "TOOL_NOT_FOUND",
                    "requested": tool_name,
                    "suggestion": suggestion,
                },
            )
        return None

    # ------------------------------------------------------------------
    # Step 2: Execute Tool
    # ------------------------------------------------------------------

    def _execute_tool(
        self,
        tool: BaseTool,
        parameters: Dict[str, Any],
        context: ToolContext,
        timeout: float,
        retry_policy: RetryPolicy,
    ) -> ToolResultResponse:
        """Step 2 — execute with timeout guard, retry, and circuit breaker.

        Enforces TOTAL wall-clock timeout across all retries.
        Returns ToolResultResponse (never raises).
        """
        # Circuit breaker check
        cb_fail = self._check_circuit_breaker(tool.name)
        if cb_fail is not None:
            return cb_fail

        last_result: Optional[ToolResultResponse] = None
        pipeline_start = time.monotonic()

        for attempt in range(retry_policy.max_retries + 1):
            # Total timeout enforcement
            elapsed_total = time.monotonic() - pipeline_start
            if elapsed_total >= timeout:
                logger.warning(
                    "Tool '%s': total timeout exceeded after %.1fs (%d attempts)",
                    tool.name, elapsed_total, attempt,
                )
                self._record_circuit_breaker(tool.name, False)
                return ToolResultResponse.fail(
                    message=_ErrorMessages.TOOL_TIMEOUT,
                    data={"error_code": "TIMEOUT", "timeout_seconds": timeout},
                )

            remaining_timeout = timeout - elapsed_total
            start = time.monotonic()
            try:
                result = self._execute_with_timeout(tool, parameters, context, remaining_timeout)
                elapsed = time.monotonic() - start

                if result.success:
                    self._stats.record(tool.name, True, elapsed)
                    self._record_circuit_breaker(tool.name, True)
                    last_result = result
                    break

                last_result = result
                self._stats.record(tool.name, False, elapsed)

                if attempt >= retry_policy.max_retries:
                    self._record_circuit_breaker(tool.name, False)
                    break

                delay = retry_policy.delay_seconds * (retry_policy.backoff_factor ** attempt)
                # Don't sleep past total timeout
                remaining = timeout - (time.monotonic() - pipeline_start)
                delay = min(delay, max(remaining, 0.0))
                if delay > 0:
                    logger.warning(
                        "Tool '%s' failed (attempt %d/%d), retrying in %.1fs",
                        tool.name, attempt + 1, retry_policy.max_retries + 1, delay,
                    )
                    time.sleep(delay)

            except Exception as exc:
                elapsed = time.monotonic() - start
                self._stats.record(tool.name, False, elapsed)

                result = self._handle_execution_error(tool, exc, parameters, context)
                last_result = result

                if attempt >= retry_policy.max_retries:
                    self._record_circuit_breaker(tool.name, False)
                    break

                if retry_policy.retry_on and not isinstance(exc, retry_policy.retry_on):
                    self._record_circuit_breaker(tool.name, False)
                    break

                delay = retry_policy.delay_seconds * (retry_policy.backoff_factor ** attempt)
                remaining = timeout - (time.monotonic() - pipeline_start)
                delay = min(delay, max(remaining, 0.0))
                if delay > 0:
                    time.sleep(delay)

        if last_result is None:
            self._record_circuit_breaker(tool.name, False)
            return ToolResultResponse.fail(message=_ErrorMessages.NO_RESULT)

        return last_result

    def _handle_execution_error(
        self,
        tool: BaseTool,
        exc: Exception,
        parameters: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResultResponse:
        """Handle execution errors — check middleware, then produce safe fallback."""
        for mw in self._middleware:
            try:
                fallback = mw.on_error(tool, exc, parameters, context)
                if fallback is not None:
                    return fallback
            except Exception:
                pass

        if isinstance(exc, TimeoutError):
            return ToolResultResponse.fail(
                message=_ErrorMessages.TOOL_TIMEOUT,
                data={"error_code": "TIMEOUT"},
            )

        logger.error(
            "Tool '%s' raised %s: %s",
            tool.name, type(exc).__name__, exc,
        )
        return ToolResultResponse.fail(
            message=_ErrorMessages.TOOL_CRASHED,
            data={"error_code": "EXECUTION_ERROR"},
        )

    def _execute_with_timeout(
        self,
        tool: BaseTool,
        parameters: Dict[str, Any],
        context: ToolContext,
        timeout: float,
    ) -> ToolResultResponse:
        """Run tool.execute() with a wall-clock timeout via threads."""
        result_box: List[Optional[ToolResultResponse]] = [None]
        error_box: List[Optional[Exception]] = [None]

        def _target() -> None:
            try:
                result_box[0] = tool.execute(parameters, context)
            except Exception as exc:
                error_box[0] = exc

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            logger.error("Tool '%s' timed out after %.1fs", tool.name, timeout)
            return ToolResultResponse.fail(
                message=_ErrorMessages.TOOL_TIMEOUT,
                data={"error_code": "TIMEOUT", "timeout_seconds": timeout},
            )

        if error_box[0] is not None:
            raise error_box[0]

        return result_box[0] or ToolResultResponse.fail(
            message=_ErrorMessages.NO_RESULT,
            data={"error_code": "NO_RESULT"},
        )

    # ------------------------------------------------------------------
    # Step 4: Validate Response
    # ------------------------------------------------------------------

    def _validate_response(
        self,
        result: ToolResultResponse,
        tool_name: str,
    ) -> ToolResultResponse:
        """Step 4 — validate and sanitise the tool response.

        Ensures:
            - Result is ToolResultResponse
            - No sensitive data leaks
            - Payload within size limits
            - All fields properly typed
        """
        return ResponseValidator.validate(result, tool_name)

    # ------------------------------------------------------------------
    # Public API — Full 5-Step Pipeline
    # ------------------------------------------------------------------

    def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[ToolContext] = None,
        *,
        retry: Optional[RetryPolicy] = None,
        timeout: Optional[float] = None,
    ) -> ToolResultResponse:
        """Execute a tool through the full validated pipeline.

        Pipeline:
            1. Validate Tool      — tool exists in registry
            2. Execute Tool        — timeout + retry + circuit breaker
            3. Middleware: after   — post-processing hooks
            4. Validate Response   — shape + sanitisation (catches injected data)
            5. Return JSON         — clean result

        Never raises. All errors → French business messages.
        """
        ctx = context or ToolContext()
        retry_policy = retry or self._default_retry
        tool_timeout = timeout or self._default_timeout

        # Step 1: Validate Tool
        tool_check = self._validate_tool(tool_name)
        if tool_check is not None:
            return tool_check

        tool = self._registry.get(tool_name)

        # Middleware: before
        for mw in self._middleware:
            try:
                intercept = mw.before(tool, parameters, ctx)
                if intercept is not None:
                    logger.debug("Middleware intercepted before '%s'", tool_name)
                    return self._validate_response(intercept, tool_name)
            except Exception as exc:
                logger.error("Middleware before failed for '%s': %s", tool_name, exc)
                return ToolResultResponse.fail(
                    message=_ErrorMessages.TOOL_CRASHED,
                    data={"error_code": "MIDDLEWARE_ERROR"},
                )

        # Step 2: Execute Tool (with timeout + retry + circuit breaker)
        result = self._execute_tool(tool, parameters, ctx, tool_timeout, retry_policy)

        # Middleware: after (BEFORE sanitisation to catch any injected data)
        for mw in self._middleware:
            try:
                result = mw.after(tool, result, parameters, ctx)
            except Exception as exc:
                logger.error("Middleware after failed for '%s': %s", tool_name, exc)

        # Step 3: Validate Response (sanitises data from tool AND middleware)
        result = self._validate_response(result, tool_name)

        # Step 4: Return JSON (clean result)
        return result

    # ------------------------------------------------------------------
    # Batch execution
    # ------------------------------------------------------------------

    def execute_batch(
        self,
        calls: List[Dict[str, Any]],
        context: Optional[ToolContext] = None,
    ) -> List[ToolResultResponse]:
        """Execute multiple tool calls sequentially. Stops on first failure."""
        results: List[ToolResultResponse] = []
        for call in calls:
            tool_name = call.get("tool", "")
            parameters = call.get("parameters", {})
            result = self.execute(tool_name, parameters, context)
            results.append(result)
            if not result.success:
                logger.warning("Batch stopped at '%s': %s", tool_name, result.message)
                break
        return results

    def execute_parallel(
        self,
        calls: List[Dict[str, Any]],
        context: Optional[ToolContext] = None,
        timeout: Optional[float] = None,
    ) -> List[ToolResultResponse]:
        """Execute multiple tool calls in parallel using threads."""
        tool_timeout = timeout or self._default_timeout
        ctx = context or ToolContext()
        results: List[Optional[ToolResultResponse]] = [None] * len(calls)

        def _run(idx: int, call: Dict[str, Any]) -> None:
            results[idx] = self.execute(
                call.get("tool", ""),
                call.get("parameters", {}),
                ctx,
                timeout=tool_timeout,
            )

        with ThreadPoolExecutor(max_workers=min(len(calls), self._thread_pool_size)) as pool:
            futures = [pool.submit(_run, i, c) for i, c in enumerate(calls)]
            for future in futures:
                try:
                    future.result(timeout=tool_timeout + 5)
                except Exception as exc:
                    logger.error("Parallel execution error: %s", exc)

        return [r for r in results if r is not None]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> ExecutionStats:
        return self._stats

    def reset_stats(self) -> None:
        self._stats = ExecutionStats()
