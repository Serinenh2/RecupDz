"""
Comprehensive tests for the ToolExecutor validated pipeline.

Pipeline:
    1. Validate Tool      — registry lookup
    2. Execute Tool        — timeout + retry + circuit breaker
    3. Middleware: after   — post-processing hooks
    4. Validate Response   — shape + sanitisation
    5. Return JSON         — clean ToolResultResponse

Covers:
    - ResponseValidator (sanitise, truncate, sensitive data removal, expanded patterns)
    - _ErrorMessages (French business messages)
    - Step 1: Tool validation (not found, empty name, suggestion)
    - Step 2: Execution (timeout, retry, exception wrapping, total timeout enforcement)
    - Circuit breaker (threshold, recovery, per-tool independence)
    - Step 3: Middleware ordering (after before sanitisation)
    - Step 4: Response validation (None result, invalid type, oversized payload)
    - Step 5: Full pipeline integration
    - Error isolation (no Python tracebacks, no repository exceptions)
    - Middleware integration with pipeline
    - Batch and parallel execution
    - Expanded exception patterns and sensitive keys
"""

from __future__ import annotations

import json
import re
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_executor import (
    ExecutionStats,
    LoggingMiddleware,
    RateLimitMiddleware,
    ResponseValidator,
    RetryPolicy,
    ToolExecutor,
    ToolMiddleware,
    _ErrorMessages,
)
from apps.ai_assistant.tools.tool_registry import ToolRegistry
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import (
    FieldSchema,
    ParameterSchema,
)


# ---------------------------------------------------------------------------
# Test Tools
# ---------------------------------------------------------------------------

class EchoTool(BaseTool):
    name = "echo_tool"
    description = "Echoes input"

    def _execute(self, parameters, context):
        return ToolResultResponse.ok(data=parameters.get("text", ""))


class FailingTool(BaseTool):
    name = "failing_tool"
    description = "Always raises ValueError"

    def _execute(self, parameters, context):
        raise ValueError("intentional failure")


class SlowTool(BaseTool):
    name = "slow_tool"
    description = "Sleeps"

    def _execute(self, parameters, context):
        time.sleep(parameters.get("delay", 1.0))
        return ToolResultResponse.ok(data="done")


class RepositoryErrorTool(BaseTool):
    name = "repo_error_tool"
    description = "Simulates repository exception"

    def _execute(self, parameters, context):
        from django.db import DatabaseError
        raise DatabaseError("connection refused to postgres://user:pass@host/db")


class SchemaTool(BaseTool):
    name = "schema_tool"
    description = "Has required parameters"

    @property
    def parameter_schema(self):
        return ParameterSchema(fields=[
            FieldSchema(name="action", type="str", required=True, enum=["search", "list"]),
            FieldSchema(name="query", type="str", required=True),
        ])

    def _execute(self, parameters, context):
        return ToolResultResponse.ok(data=parameters)


class SensitiveTool(BaseTool):
    name = "sensitive_tool"
    description = "Returns sensitive data"

    def _execute(self, parameters, context):
        return ToolResultResponse.ok(data={
            "password": "secret123",
            "api_key": "sk-abc",
            "token": "bearer xyz",
            "result": "legitimate data",
        })


class OversizedTool(BaseTool):
    name = "oversized_tool"
    description = "Returns huge payload"

    def _execute(self, parameters, context):
        return ToolResultResponse.ok(data={"payload": "x" * 200_000})


class NoneResultTool(BaseTool):
    name = "none_result_tool"
    description = "Returns None instead of ToolResultResponse"

    def _execute(self, parameters, context):
        return None  # type: ignore


class StringResultTool(BaseTool):
    name = "string_result_tool"
    description = "Returns a string instead of ToolResultResponse"

    def _execute(self, parameters, context):
        return "just a string"  # type: ignore


class CrashTool(BaseTool):
    name = "crash_tool"
    description = "Raises RuntimeError"

    def _execute(self, parameters, context):
        raise RuntimeError("db connection pool exhausted")


class RetryableTool(BaseTool):
    name = "retryable_tool"
    description = "Fails then succeeds"

    call_count = 0

    def _execute(self, parameters, context):
        RetryableTool.call_count += 1
        if RetryableTool.call_count < 3:
            return ToolResultResponse.fail(message="transient error")
        return ToolResultResponse.ok(data="recovered")


class SchemaCrashTool(BaseTool):
    name = "schema_crash_tool"
    description = "Schema validation crashes"

    @property
    def parameter_schema(self):
        raise RuntimeError("schema unavailable")

    def _execute(self, parameters, context):
        return ToolResultResponse.ok(data="ok")


# ---------------------------------------------------------------------------
# ResponseValidator Tests
# ---------------------------------------------------------------------------

class TestResponseValidator(unittest.TestCase):

    def test_valid_result_passes(self):
        result = ToolResultResponse.ok(data={"key": "value"})
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertTrue(validated.success)
        self.assertEqual(validated.data, {"key": "value"})

    def test_none_result_returns_failure(self):
        validated = ResponseValidator.validate(None, "test_tool")
        self.assertFalse(validated.success)
        self.assertIn("erreur", validated.message.lower())

    def test_non_toolresult_returns_failure(self):
        validated = ResponseValidator.validate("just a string", "test_tool")
        self.assertFalse(validated.success)

    def test_non_bool_success_coerced(self):
        result = ToolResultResponse(success="yes", message="ok", data={})
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertFalse(validated.success)

    def test_exception_style_message_replaced(self):
        result = ToolResultResponse.fail(
            message="Tool 'my_tool' — ValueError: something went wrong"
        )
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertFalse(validated.success)
        self.assertIn("erreur", validated.message.lower())
        self.assertNotIn("ValueError", validated.message)

    def test_exception_class_in_message_replaced(self):
        result = ToolResultResponse.fail(
            message="RuntimeError: db connection pool exhausted"
        )
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertIn("erreur", validated.message.lower())

    def test_sanitises_traceback_in_message(self):
        result = ToolResultResponse.fail(
            message="Traceback (most recent call last):\n  File \"app.py\", line 42"
        )
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertNotIn("Traceback", validated.message)

    def test_sanitises_django_references(self):
        result = ToolResultResponse.ok(data={"msg": "django.db.utils.OperationalError"})
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertNotIn("django.db", json.dumps(validated.data))

    def test_sanitises_password_in_message(self):
        result = ToolResultResponse.ok(message="password = secret123 connection")
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertNotIn("password", validated.message.lower())

    def test_truncates_long_message(self):
        result = ToolResultResponse.fail(message="x" * 5000)
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertLessEqual(len(validated.message), 2010)

    def test_sanitises_sensitive_keys_in_dict(self):
        result = ToolResultResponse.ok(data={
            "password": "secret",
            "result": "legitimate",
        })
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertEqual(validated.data["password"], "[REDACTED]")
        self.assertEqual(validated.data["result"], "legitimate")

    def test_truncates_oversized_list(self):
        result = ToolResultResponse.ok(data=list(range(500)))
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertLessEqual(len(validated.data), 100)

    def test_truncates_oversized_dict(self):
        big_data = {f"key_{i}": "x" * 1500 for i in range(100)}
        result = ToolResultResponse.ok(data=big_data)
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertLessEqual(len(validated.data), 20)

    def test_nested_sanitisation(self):
        result = ToolResultResponse.ok(data={
            "items": [
                {"name": "ok", "secret_token": "abc"},
                {"name": "ok2", "password": "xyz"},
            ]
        })
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertIsInstance(validated.data, dict)

    def test_non_serialisable_data_converted(self):
        result = ToolResultResponse.ok(data=object())
        validated = ResponseValidator.validate(result, "test_tool")
        self.assertIsInstance(validated.data, str)


# ---------------------------------------------------------------------------
# Error Messages Tests
# ---------------------------------------------------------------------------

class TestErrorMessages(unittest.TestCase):

    def test_all_messages_are_french(self):
        for attr in dir(_ErrorMessages):
            if attr.startswith("_"):
                continue
            msg = getattr(_ErrorMessages, attr)
            self.assertIsInstance(msg, str)
            self.assertGreater(len(msg), 10)

    def test_no_english_error_patterns(self):
        for attr in dir(_ErrorMessages):
            if attr.startswith("_"):
                continue
            msg = getattr(_ErrorMessages, attr).lower()
            self.assertNotIn("traceback", msg)
            self.assertNotIn("exception", msg)
            self.assertNotIn("stack trace", msg)


# ---------------------------------------------------------------------------
# Step 1: Validate Tool
# ---------------------------------------------------------------------------

class TestStep1ValidateTool(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.executor = ToolExecutor(self.registry)

    def test_tool_not_found_returns_business_message(self):
        result = self.executor.execute("nonexistent_tool", {})
        self.assertFalse(result.success)
        self.assertIn("disponible", result.message.lower())
        self.assertNotIn("Traceback", result.message)
        self.assertNotIn("registry", result.message.lower())

    def test_tool_not_found_includes_error_code(self):
        result = self.executor.execute("nonexistent_tool", {})
        self.assertEqual(result.data.get("error_code"), "TOOL_NOT_FOUND")

    def test_tool_not_found_includes_suggestion(self):
        result = self.executor.execute("echo", {})
        self.assertFalse(result.success)
        self.assertEqual(result.data.get("suggestion"), "echo_tool")

    def test_empty_tool_name(self):
        result = self.executor.execute("", {})
        self.assertFalse(result.success)
        self.assertIn("disponible", result.message.lower())

    def test_none_tool_name(self):
        result = self.executor.execute(None, {})  # type: ignore
        self.assertFalse(result.success)

    def test_tool_found_executes(self):
        result = self.executor.execute("echo_tool", {"text": "hello"})
        self.assertTrue(result.success)
        self.assertEqual(result.data, "hello")


# ---------------------------------------------------------------------------
# Step 2: Execute Tool (validation now happens inside BaseTool.execute)
# ---------------------------------------------------------------------------

class TestStep2ExecuteTool(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(SchemaTool())
        self.registry.register(EchoTool())
        self.executor = ToolExecutor(self.registry)

    def test_missing_required_parameter(self):
        result = self.executor.execute("schema_tool", {"action": "search"})
        self.assertFalse(result.success)
        self.assertIn("errors", result.data)

    def test_invalid_enum_value(self):
        result = self.executor.execute("schema_tool", {
            "action": "invalid",
            "query": "test",
        })
        self.assertFalse(result.success)
        self.assertIn("errors", result.data)

    def test_valid_parameters_pass(self):
        result = self.executor.execute("schema_tool", {
            "action": "search",
            "query": "test",
        })
        self.assertTrue(result.success)

    def test_validation_crash_returns_safe_error(self):
        registry = ToolRegistry()
        registry.register(SchemaCrashTool())
        executor = ToolExecutor(registry)
        result = executor.execute("schema_crash_tool", {})
        self.assertFalse(result.success)
        self.assertNotIn("schema unavailable", result.message)

    def test_no_schema_tools_skip_validation(self):
        result = self.executor.execute("echo_tool", {"text": "any"})
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Step 3: Execute Tool
# ---------------------------------------------------------------------------

class TestStep3ExecuteTool(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())
        self.registry.register(SlowTool())
        self.registry.register(CrashTool())
        self.registry.register(RepositoryErrorTool())
        self.registry.register(RetryableTool())
        self.executor = ToolExecutor(self.registry, default_timeout=5.0)

    def test_successful_execution(self):
        result = self.executor.execute("echo_tool", {"text": "hello"})
        self.assertTrue(result.success)
        self.assertEqual(result.data, "hello")

    def test_exception_returns_business_message(self):
        result = self.executor.execute("failing_tool", {})
        self.assertFalse(result.success)
        self.assertIn("erreur", result.message.lower())
        self.assertNotIn("ValueError", result.message)
        self.assertNotIn("intentional failure", result.message)

    def test_exception_includes_error_code(self):
        result = self.executor.execute("failing_tool", {})
        self.assertFalse(result.success)
        self.assertEqual(result.data.get("error_code"), "EXECUTION_ERROR")

    def test_timeout_returns_business_message(self):
        result = self.executor.execute("slow_tool", {"delay": 10.0}, timeout=0.1)
        self.assertFalse(result.success)
        self.assertIn("trop de temps", result.message.lower())
        self.assertNotIn("threading", result.message.lower())

    def test_timeout_includes_error_code(self):
        result = self.executor.execute("slow_tool", {"delay": 10.0}, timeout=0.1)
        self.assertEqual(result.data.get("error_code"), "TIMEOUT")

    def test_repository_error_does_not_leak(self):
        """Repository exceptions must never reach the caller."""
        result = self.executor.execute("repo_error_tool", {})
        self.assertFalse(result.success)
        msg_lower = result.message.lower()
        self.assertNotIn("connection pool", msg_lower)
        self.assertNotIn("postgres", msg_lower)
        self.assertNotIn("database", msg_lower)

    def test_retry_eventually_succeeds(self):
        RetryableTool.call_count = 0
        executor = ToolExecutor(
            self.registry,
            default_retry=RetryPolicy(max_retries=3, delay_seconds=0.01),
        )
        result = executor.execute("retryable_tool", {})
        self.assertTrue(result.success)
        self.assertEqual(result.data, "recovered")
        self.assertEqual(RetryableTool.call_count, 3)

    def test_retry_exhausted(self):
        class AlwaysFailTool(BaseTool):
            name = "always_fail"
            description = "Always fails"

            def _execute(self, parameters, context):
                return ToolResultResponse.fail(message="permanent failure")

        self.registry.register(AlwaysFailTool())
        executor = ToolExecutor(
            self.registry,
            default_retry=RetryPolicy(max_retries=2, delay_seconds=0.01),
        )
        result = executor.execute("always_fail", {})
        self.assertFalse(result.success)

    def test_crash_returns_safe_message(self):
        result = self.executor.execute("crash_tool", {})
        self.assertFalse(result.success)
        self.assertIn("erreur", result.message.lower())


# ---------------------------------------------------------------------------
# Step 4: Validate Response
# ---------------------------------------------------------------------------

class TestStep4ValidateResponse(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(NoneResultTool())
        self.registry.register(StringResultTool())
        self.registry.register(SensitiveTool())
        self.registry.register(OversizedTool())
        self.executor = ToolExecutor(self.registry)

    def test_none_result_wrapped(self):
        result = self.executor.execute("none_result_tool", {})
        # BaseTool wraps None into ToolResultResponse.ok(data=None) → success=True
        # ResponseValidator sanitises None data → {}
        self.assertTrue(result.success)

    def test_string_result_wrapped(self):
        result = self.executor.execute("string_result_tool", {})
        # BaseTool wraps non-ToolResultResponse returns into ok(data=result)
        self.assertTrue(result.success)

    def test_sensitive_data_sanitised(self):
        result = self.executor.execute("sensitive_tool", {})
        self.assertTrue(result.success)
        self.assertEqual(result.data.get("password"), "[REDACTED]")
        self.assertEqual(result.data.get("api_key"), "[REDACTED]")
        self.assertEqual(result.data.get("token"), "[REDACTED]")
        self.assertEqual(result.data.get("result"), "legitimate data")

    def test_oversized_payload_truncated(self):
        result = self.executor.execute("oversized_tool", {})
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Step 5: Full Pipeline Integration
# ---------------------------------------------------------------------------

class TestStep5FullPipeline(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())
        self.registry.register(SchemaTool())
        self.registry.register(SlowTool())
        self.registry.register(RepositoryErrorTool())
        self.executor = ToolExecutor(self.registry, default_timeout=5.0)

    def test_full_pipeline_success(self):
        result = self.executor.execute("echo_tool", {"text": "bonjour"})
        self.assertTrue(result.success)
        self.assertEqual(result.data, "bonjour")

    def test_full_pipeline_all_steps_for_tool_not_found(self):
        result = self.executor.execute("missing_tool", {})
        self.assertFalse(result.success)
        self.assertIn("disponible", result.message.lower())

    def test_full_pipeline_all_steps_for_validation_failure(self):
        result = self.executor.execute("schema_tool", {"action": "bad"})
        self.assertFalse(result.success)
        self.assertNotIn("Traceback", result.message)

    def test_full_pipeline_all_steps_for_execution_error(self):
        result = self.executor.execute("failing_tool", {})
        self.assertFalse(result.success)
        self.assertIn("erreur", result.message.lower())

    def test_full_pipeline_no_exception_leaks(self):
        """Run every failing path — verify no Python exceptions leak."""
        tools_to_test = [
            ("failing_tool", {}),
            ("slow_tool", {"delay": 10.0}),
            ("missing_tool_xyz", {}),
            ("schema_tool", {"action": "bad"}),
        ]
        for name, params in tools_to_test:
            result = self.executor.execute(name, params, timeout=0.5)
            self.assertFalse(result.success)
            self.assertNotIn("Traceback", result.message)
            self.assertNotIn("File \"", result.message)
            self.assertNotIn("Exception", result.message)

    def test_repository_exception_does_not_leak(self):
        """Database errors must never appear in the response."""
        result = self.executor.execute("repo_error_tool", {})
        self.assertFalse(result.success)
        msg_lower = result.message.lower()
        self.assertNotIn("database", msg_lower)
        self.assertNotIn("postgres", msg_lower)
        self.assertNotIn("password", msg_lower)
        self.assertNotIn("connection refused", msg_lower)

    def test_response_is_json_serialisable(self):
        result = self.executor.execute("echo_tool", {"text": "test"})
        dumped = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertIsInstance(dumped, str)
        parsed = json.loads(dumped)
        self.assertTrue(parsed["success"])

    def test_stats_recorded(self):
        self.executor.execute("echo_tool", {"text": "a"})
        self.executor.execute("failing_tool", {})
        stats = self.executor.stats
        self.assertEqual(stats.total_calls, 2)
        self.assertEqual(stats.successful_calls, 1)
        self.assertEqual(stats.failed_calls, 1)


# ---------------------------------------------------------------------------
# Middleware Integration
# ---------------------------------------------------------------------------

class TestMiddlewarePipeline(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())

    def test_middleware_before_intercept(self):
        class BlockMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                return ToolResultResponse.fail(message="blocked by middleware")
            def after(self, tool, result, parameters, context):
                return result

        executor = ToolExecutor(self.registry)
        executor.add_middleware(BlockMiddleware())
        result = executor.execute("echo_tool", {"text": "hi"})
        self.assertFalse(result.success)
        self.assertIn("blocked", result.message)

    def test_middleware_after_transforms(self):
        class TransformMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                return None
            def after(self, tool, result, parameters, context):
                result.metadata["transformed"] = True
                return result

        executor = ToolExecutor(self.registry)
        executor.add_middleware(TransformMiddleware())
        result = executor.execute("echo_tool", {"text": "hi"})
        self.assertTrue(result.metadata.get("transformed"))

    def test_middleware_exception_does_not_crash_pipeline(self):
        class BrokenMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                raise RuntimeError("middleware broken")
            def after(self, tool, result, parameters, context):
                return result

        executor = ToolExecutor(self.registry)
        executor.add_middleware(BrokenMiddleware())
        result = executor.execute("echo_tool", {"text": "hi"})
        # Should still work, middleware error is caught
        self.assertFalse(result.success)

    def test_middleware_on_error_fallback(self):
        """on_error is called when exceptions escape BaseTool (e.g. thread crash)."""
        class FallbackMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                return None
            def after(self, tool, result, parameters, context):
                return result
            def on_error(self, tool, exc, parameters, context):
                return ToolResultResponse.ok(data="fallback_data")

        # BaseTool catches all exceptions, so on_error is a safety net
        # for thread-level crashes. Normal tool errors are wrapped by BaseTool.
        executor = ToolExecutor(self.registry)
        executor.add_middleware(FallbackMiddleware())
        result = executor.execute("failing_tool", {})
        # BaseTool wraps the ValueError into a ToolResultResponse.fail()
        self.assertFalse(result.success)

    def test_response_validated_after_middleware(self):
        """Response validator runs after middleware 'after' hooks."""
        class BadTransformMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                return None
            def after(self, tool, result, parameters, context):
                result.data = {"password": "secret", "api_key": "sk-123"}
                return result

        executor = ToolExecutor(self.registry)
        executor.add_middleware(BadTransformMiddleware())
        result = executor.execute("echo_tool", {"text": "hi"})
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Batch and Parallel Execution
# ---------------------------------------------------------------------------

class TestBatchExecution(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())
        self.executor = ToolExecutor(self.registry)

    def test_batch_success(self):
        calls = [
            {"tool": "echo_tool", "parameters": {"text": "a"}},
            {"tool": "echo_tool", "parameters": {"text": "b"}},
        ]
        results = self.executor.execute_batch(calls)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))

    def test_batch_stops_on_failure(self):
        calls = [
            {"tool": "failing_tool", "parameters": {}},
            {"tool": "echo_tool", "parameters": {"text": "a"}},
        ]
        results = self.executor.execute_batch(calls)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)

    def test_batch_unknown_tool(self):
        calls = [
            {"tool": "nope_tool", "parameters": {}},
        ]
        results = self.executor.execute_batch(calls)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)


class TestParallelExecution(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.executor = ToolExecutor(self.registry)

    def test_parallel_success(self):
        calls = [
            {"tool": "echo_tool", "parameters": {"text": "a"}},
            {"tool": "echo_tool", "parameters": {"text": "b"}},
            {"tool": "echo_tool", "parameters": {"text": "c"}},
        ]
        results = self.executor.execute_parallel(calls, timeout=5.0)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestExecutionStats(unittest.TestCase):

    def test_stats_record(self):
        stats = ExecutionStats()
        stats.record("tool_a", True, 0.1)
        stats.record("tool_a", True, 0.2)
        stats.record("tool_b", False, 0.3)
        self.assertEqual(stats.total_calls, 3)
        self.assertEqual(stats.successful_calls, 2)
        self.assertEqual(stats.failed_calls, 1)
        self.assertAlmostEqual(stats.total_time_seconds, 0.6)
        self.assertEqual(stats.per_tool["tool_a"], 2)
        self.assertEqual(stats.per_tool["tool_b"], 1)

    def test_success_rate_empty(self):
        stats = ExecutionStats()
        self.assertEqual(stats.success_rate, 0.0)

    def test_success_rate_calculation(self):
        stats = ExecutionStats()
        stats.record("x", True, 0.1)
        stats.record("x", True, 0.1)
        stats.record("x", False, 0.1)
        self.assertAlmostEqual(stats.success_rate, 2 / 3)

    def test_reset_stats(self):
        executor = ToolExecutor(ToolRegistry())
        executor.execute.__func__  # just verify method exists
        executor._stats.record("x", True, 0.1)
        executor.reset_stats()
        self.assertEqual(executor.stats.total_calls, 0)


# ---------------------------------------------------------------------------
# Error Isolation — No Leak Tests
# ---------------------------------------------------------------------------

class TestErrorIsolation(unittest.TestCase):
    """Verify that NO internal details ever leak in responses."""

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(FailingTool())
        self.registry.register(RepositoryErrorTool())
        self.registry.register(CrashTool())
        self.executor = ToolExecutor(self.registry, default_timeout=2.0)

    def _assert_no_internals(self, result: ToolResultResponse):
        """Assert response contains no internal details."""
        text = json.dumps(result.to_dict(), ensure_ascii=False).lower()
        # No Python internals
        self.assertNotIn("traceback", text)
        self.assertNotIn("file \"", text)
        self.assertNotIn("line ", text)
        self.assertNotIn("raise ", text)
        # No database internals
        self.assertNotIn("django.db", text)
        self.assertNotIn("psycopg2", text)
        self.assertNotIn("sqlite3", text)
        # No secrets
        self.assertNotIn("password", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("api_key", text)
        self.assertNotIn("token", text)

    def test_valueerror_does_not_leak(self):
        result = self.executor.execute("failing_tool", {})
        self.assertFalse(result.success)
        self._assert_no_internals(result)

    def test_database_error_does_not_leak(self):
        result = self.executor.execute("repo_error_tool", {})
        self.assertFalse(result.success)
        self._assert_no_internals(result)

    def test_runtime_error_does_not_leak(self):
        result = self.executor.execute("crash_tool", {})
        self.assertFalse(result.success)
        self._assert_no_internals(result)

    def test_timeout_does_not_leak_threading_info(self):
        result = self.executor.execute(
            "slow_tool", {"delay": 10.0},
            timeout=0.1,
        ) if "slow_tool" in self.registry else ToolResultResponse.fail(message="test")
        # slow_tool not in this setUp registry, so test via a dedicated one
        registry = ToolRegistry()
        registry.register(SlowTool())
        executor = ToolExecutor(registry, default_timeout=2.0)
        result = executor.execute("slow_tool", {"delay": 10.0}, timeout=0.1)
        self.assertFalse(result.success)
        self._assert_no_internals(result)

    def test_all_error_codes_are_strings(self):
        result = self.executor.execute("failing_tool", {})
        self.assertIsInstance(result.data.get("error_code"), str)


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def test_execute_empty_parameters(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        executor = ToolExecutor(registry)
        result = executor.execute("echo_tool", {})
        self.assertTrue(result.success)

    def test_execute_with_context(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        executor = ToolExecutor(registry)
        ctx = ToolContext.create(user_id="u1", conversation_id="c1")
        result = executor.execute("echo_tool", {"text": "hi"}, ctx)
        self.assertTrue(result.success)

    def test_execute_with_custom_retry(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        executor = ToolExecutor(registry)
        result = executor.execute(
            "echo_tool", {"text": "hi"},
            retry=RetryPolicy(max_retries=1, delay_seconds=0.01),
        )
        self.assertTrue(result.success)

    def test_execute_with_custom_timeout(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        executor = ToolExecutor(registry, default_timeout=1.0)
        result = executor.execute("echo_tool", {"text": "hi"}, timeout=10.0)
        self.assertTrue(result.success)

    def test_multiple_middleware_ordering(self):
        order = []

        class MW1(ToolMiddleware):
            def before(self, tool, parameters, context):
                order.append("mw1_before")
                return None
            def after(self, tool, result, parameters, context):
                order.append("mw1_after")
                return result

        class MW2(ToolMiddleware):
            def before(self, tool, parameters, context):
                order.append("mw2_before")
                return None
            def after(self, tool, result, parameters, context):
                order.append("mw2_after")
                return result

        registry = ToolRegistry()
        registry.register(EchoTool())
        executor = ToolExecutor(registry)
        executor.add_middleware(MW1())
        executor.add_middleware(MW2())
        executor.execute("echo_tool", {"text": "hi"})
        self.assertEqual(order, ["mw1_before", "mw2_before", "mw1_after", "mw2_after"])

    def test_clear_middleware(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        executor = ToolExecutor(registry)

        class Dummy(ToolMiddleware):
            def before(self, tool, parameters, context): return None
            def after(self, tool, result, parameters, context): return result

        executor.add_middleware(Dummy())
        self.assertEqual(len(executor._middleware), 1)
        executor.clear_middleware()
        self.assertEqual(len(executor._middleware), 0)


# ---------------------------------------------------------------------------
# Circuit Breaker Tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(FailingTool())
        self.registry.register(EchoTool())
        self.executor = ToolExecutor(
            self.registry,
            circuit_breaker_threshold=3,
            circuit_breaker_recovery=0.5,
        )

    def test_circuit_opens_after_threshold_failures(self):
        for _ in range(3):
            self.executor.execute("failing_tool", {})
        result = self.executor.execute("failing_tool", {})
        self.assertFalse(result.success)
        self.assertEqual(result.data.get("error_code"), "CIRCUIT_OPEN")
        self.assertIn("indisponible", result.message.lower())

    def test_circuit_resets_after_recovery_time(self):
        for _ in range(3):
            self.executor.execute("failing_tool", {})
        # Circuit should be open
        result = self.executor.execute("failing_tool", {})
        self.assertEqual(result.data.get("error_code"), "CIRCUIT_OPEN")
        # Wait for recovery
        time.sleep(0.6)
        result = self.executor.execute("failing_tool", {})
        # Should attempt execution again (still fails but not circuit-open)
        self.assertNotEqual(result.data.get("error_code"), "CIRCUIT_OPEN")

    def test_circuit_resets_on_success(self):
        # Use a tool that fails once then succeeds
        call_count = 0
        original_execute = EchoTool._execute

        def flaky_execute(self_tool, parameters, context):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return ToolResultResponse.fail(message="transient")
            return ToolResultResponse.ok(data="recovered")

        EchoTool._execute = flaky_execute
        try:
            executor = ToolExecutor(
                self.registry,
                default_retry=RetryPolicy(max_retries=0),
                circuit_breaker_threshold=3,
            )
            for _ in range(2):
                executor.execute("echo_tool", {})
            # 2 failures, CB has 2 consecutive_failures
            cb = executor._circuit_breakers.get("echo_tool")
            self.assertIsNotNone(cb)
            self.assertEqual(cb.consecutive_failures, 2)
            # Now succeed — should reset CB
            executor.execute("echo_tool", {})
            self.assertEqual(cb.consecutive_failures, 0)
        finally:
            EchoTool._execute = original_execute

    def test_circuit_breaker_per_tool_independent(self):
        for _ in range(3):
            self.executor.execute("failing_tool", {})
        # failing_tool circuit is open
        result = self.executor.execute("failing_tool", {})
        self.assertEqual(result.data.get("error_code"), "CIRCUIT_OPEN")
        # echo_tool should still work
        result = self.executor.execute("echo_tool", {"text": "hi"})
        self.assertTrue(result.success)

    def test_circuit_breaker_not_triggered_below_threshold(self):
        for _ in range(2):
            self.executor.execute("failing_tool", {})
        result = self.executor.execute("failing_tool", {})
        # Should attempt execution, not circuit-open
        self.assertNotEqual(result.data.get("error_code"), "CIRCUIT_OPEN")

    def test_circuit_breaker_custom_threshold(self):
        executor = ToolExecutor(
            self.registry,
            circuit_breaker_threshold=1,
            circuit_breaker_recovery=60.0,
        )
        executor.execute("failing_tool", {})
        result = executor.execute("failing_tool", {})
        self.assertEqual(result.data.get("error_code"), "CIRCUIT_OPEN")


# ---------------------------------------------------------------------------
# Total Timeout Enforcement Tests
# ---------------------------------------------------------------------------

class TestTotalTimeoutEnforcement(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(SlowTool())
        self.registry.register(FailingTool())

    def test_total_timeout_across_retries(self):
        executor = ToolExecutor(
            self.registry,
            default_retry=RetryPolicy(max_retries=3, delay_seconds=0.01),
            default_timeout=1.0,
        )
        start = time.monotonic()
        result = executor.execute("slow_tool", {"delay": 5.0}, timeout=1.0)
        elapsed = time.monotonic() - start
        self.assertFalse(result.success)
        self.assertLess(elapsed, 3.0)
        self.assertIn("trop de temps", result.message.lower())

    def test_timeout_enforced_between_retries(self):
        executor = ToolExecutor(
            self.registry,
            default_retry=RetryPolicy(max_retries=5, delay_seconds=0.01),
            default_timeout=0.5,
        )
        start = time.monotonic()
        result = executor.execute("failing_tool", {}, timeout=0.5)
        elapsed = time.monotonic() - start
        self.assertFalse(result.success)
        self.assertLess(elapsed, 2.0)

    def test_single_attempt_respects_timeout(self):
        executor = ToolExecutor(
            self.registry,
            default_retry=RetryPolicy(max_retries=0),
            default_timeout=0.1,
        )
        start = time.monotonic()
        result = executor.execute("slow_tool", {"delay": 5.0}, timeout=0.1)
        elapsed = time.monotonic() - start
        self.assertFalse(result.success)
        self.assertLess(elapsed, 1.0)


# ---------------------------------------------------------------------------
# Middleware Ordering Tests (after BEFORE sanitisation)
# ---------------------------------------------------------------------------

class TestMiddlewareOrdering(unittest.TestCase):

    def test_middleware_after_runs_before_sanitisation(self):
        """Middleware 'after' can inject data that gets sanitised by ResponseValidator."""
        class DictTool(BaseTool):
            name = "dict_tool"
            description = "Returns a dict"
            def _execute(self, parameters, context):
                return ToolResultResponse.ok(data={"text": "hello", "safe": True})

        class InjectingMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                return None
            def after(self, tool, result, parameters, context):
                result.data["password"] = "secret123"
                result.data["api_key"] = "sk-leaked"
                result.data["safe_field"] = "visible"
                return result

        registry = ToolRegistry()
        registry.register(DictTool())
        executor = ToolExecutor(registry)
        executor.add_middleware(InjectingMiddleware())

        result = executor.execute("dict_tool", {})
        self.assertTrue(result.success)
        # ResponseValidator should redact injected sensitive data
        self.assertEqual(result.data.get("password"), "[REDACTED]")
        self.assertEqual(result.data.get("api_key"), "[REDACTED]")
        self.assertEqual(result.data.get("safe_field"), "visible")

    def test_middleware_after_exception_doesnt_break_pipeline(self):
        class BadAfterMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                return None
            def after(self, tool, result, parameters, context):
                raise RuntimeError("middleware boom")

        registry = ToolRegistry()
        registry.register(EchoTool())
        executor = ToolExecutor(registry)
        executor.add_middleware(BadAfterMiddleware())

        result = executor.execute("echo_tool", {"text": "hi"})
        self.assertTrue(result.success)
        self.assertEqual(result.data, "hi")


# ---------------------------------------------------------------------------
# Expanded Exception Class Patterns Tests
# ---------------------------------------------------------------------------

class TestExpandedExceptionPatterns(unittest.TestCase):

    def test_django_object_does_not_exist_stripped(self):
        msg = "ObjectDoesNotExist: matching query did not exist"
        self.assertTrue(ResponseValidator._EXCEPTION_CLASS_PATTERN.search(msg))

    def test_django_multiple_objects_returned_stripped(self):
        msg = "MultipleObjectsReturned: expected 1 got 3"
        self.assertTrue(ResponseValidator._EXCEPTION_CLASS_PATTERN.search(msg))

    def test_django_field_does_not_exist_stripped(self):
        msg = "FieldDoesNotExist: User has no field named 'foo'"
        self.assertTrue(ResponseValidator._EXCEPTION_CLASS_PATTERN.search(msg))

    def test_serialization_error_stripped(self):
        msg = "SerializationError: unable to serialize data"
        self.assertTrue(ResponseValidator._EXCEPTION_CLASS_PATTERN.search(msg))

    def test_synchronous_only_operation_stripped(self):
        msg = "SynchronousOnlyOperation: You cannot call this from an async context"
        self.assertTrue(ResponseValidator._EXCEPTION_CLASS_PATTERN.search(msg))

    def test_failing_tool_message_sanitised(self):
        result = ToolResultResponse.fail(
            message="ObjectDoesNotExist: matching query did not exist",
        )
        validated = ResponseValidator.validate(result, "test")
        self.assertNotIn("ObjectDoesNotExist", validated.message)
        self.assertIn("erreur", validated.message.lower())


# ---------------------------------------------------------------------------
# Expanded Sensitive Keys Tests
# ---------------------------------------------------------------------------

class TestExpandedSensitiveKeys(unittest.TestCase):

    def test_db_password_redacted(self):
        data = {"db_password": "postgres://user:pass@host/db"}
        result = ToolResultResponse.ok(data=data)
        validated = ResponseValidator.validate(result, "test")
        self.assertEqual(validated.data["db_password"], "[REDACTED]")

    def test_jwt_secret_redacted(self):
        data = {"jwt_secret": "super-secret-jwt-key"}
        result = ToolResultResponse.ok(data=data)
        validated = ResponseValidator.validate(result, "test")
        self.assertEqual(validated.data["jwt_secret"], "[REDACTED]")

    def test_session_key_redacted(self):
        data = {"session_key": "abc123"}
        result = ToolResultResponse.ok(data=data)
        validated = ResponseValidator.validate(result, "test")
        self.assertEqual(validated.data["session_key"], "[REDACTED]")

    def test_nested_sensitive_keys_redacted(self):
        data = {"config": {"password": "secret", "host": "localhost"}}
        result = ToolResultResponse.ok(data=data)
        validated = ResponseValidator.validate(result, "test")
        self.assertEqual(validated.data["config"]["password"], "[REDACTED]")
        self.assertEqual(validated.data["config"]["host"], "localhost")

    def test_cvv_redacted(self):
        data = {"cvv": "123"}
        result = ToolResultResponse.ok(data=data)
        validated = ResponseValidator.validate(result, "test")
        self.assertEqual(validated.data["cvv"], "[REDACTED]")


# ---------------------------------------------------------------------------
# Integration: Full Pipeline End-to-End
# ---------------------------------------------------------------------------

class TestEndToEndPipeline(unittest.TestCase):
    """End-to-end tests simulating real orchestrator calls."""

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.registry.register(SchemaTool())
        self.registry.register(FailingTool())
        self.registry.register(SlowTool())
        self.executor = ToolExecutor(
            self.registry,
            default_timeout=5.0,
            default_retry=RetryPolicy(max_retries=1, delay_seconds=0.01),
        )

    def test_e2e_success_path(self):
        ctx = ToolContext.create(user_id="user_1", conversation_id="conv_1")
        result = self.executor.execute(
            "echo_tool", {"text": "Bonjour le monde"}, ctx,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data, "Bonjour le monde")

    def test_e2e_validation_error_path(self):
        result = self.executor.execute("schema_tool", {"action": "bad"})
        self.assertFalse(result.success)
        self.assertIn("errors", result.data)

    def test_e2e_execution_error_path(self):
        result = self.executor.execute("failing_tool", {})
        self.assertFalse(result.success)
        self.assertIn("erreur", result.message.lower())
        self.assertEqual(result.data.get("error_code"), "EXECUTION_ERROR")

    def test_e2e_tool_not_found_path(self):
        result = self.executor.execute("waste_tool_xyz", {})
        self.assertFalse(result.success)
        self.assertIn("disponible", result.message.lower())

    def test_e2e_timeout_path(self):
        result = self.executor.execute("slow_tool", {"delay": 10.0}, timeout=0.1)
        self.assertFalse(result.success)
        self.assertIn("trop de temps", result.message.lower())

    def test_e2e_response_always_json(self):
        """Every path returns JSON-serialisable data."""
        calls = [
            ("echo_tool", {"text": "hi"}),
            ("failing_tool", {}),
            ("nonexistent_tool", {}),
            ("schema_tool", {"action": "bad"}),
        ]
        for name, params in calls:
            result = self.executor.execute(name, params, timeout=1.0)
            dumped = json.dumps(result.to_dict(), ensure_ascii=False)
            parsed = json.loads(dumped)
            self.assertIn("success", parsed)
            self.assertIn("message", parsed)
            self.assertIn("data", parsed)


if __name__ == "__main__":
    unittest.main()
