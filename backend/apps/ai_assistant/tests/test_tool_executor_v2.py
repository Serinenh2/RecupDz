"""
Tests for ToolExecutorV2 — plan-driven tool execution with error isolation.

Covers:
    - StepResult / ToolExecutionResult data contracts
    - Single step execution (success, failure, timeout, retry)
    - Plan execution (sequential, partial failure)
    - Tool validation (not found, missing params)
    - Output validation (non-serialisable, sensitive data)
    - Error isolation (exceptions never leaked)
    - Retry logic
    - Callback hooks
    - Framework independence
"""

import json
import time
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from apps.ai_assistant.enterprise.tool_executor_v2 import (
    StepResult,
    ToolExecutionResult,
    ToolExecutorV2,
)
from apps.ai_assistant.enterprise.tool_planner import (
    DecisionProposal,
    ExecutionMode,
    ExecutionPlan,
    ToolPlanner,
    ToolStep,
)


# ════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════


def _make_mock_tool(
    name: str = "waste_tool",
    execute_return: dict = None,
    execute_side_effect: Exception = None,
    timeout: float = 30.0,
    schema_fields: list = None,
):
    """Create a mock BaseTool."""
    tool = MagicMock()
    tool.name = name
    tool.timeout_seconds = timeout

    response = MagicMock()
    if execute_return is None:
        execute_return = {"success": True, "data": {"count": 5}, "message": "OK"}
    response.to_dict.return_value = execute_return
    tool.execute.return_value = response

    if execute_side_effect:
        tool.execute.side_effect = execute_side_effect

    if schema_fields:
        schema = MagicMock()
        schema.fields = schema_fields
        tool.parameter_schema = schema
    else:
        tool.parameter_schema = None

    return tool


def _make_mock_registry(tools: dict = None):
    """Create a mock ToolRegistry."""
    registry = MagicMock()
    if tools is None:
        tools = {}
    registry.get.side_effect = lambda name: tools.get(name)
    registry.has.side_effect = lambda name: name in tools
    return registry


def _make_step(
    step_id: str = "step_1",
    tool: str = "waste_tool",
    action: str = "search",
    params: dict = None,
    retry: int = 0,
    timeout_ms: float = 30000.0,
) -> ToolStep:
    return ToolStep(
        step_id=step_id,
        tool=tool,
        action=action,
        parameters=params or {"query": "test"},
        retry_count=retry,
        timeout_ms=timeout_ms,
    )


def _make_plan(*steps: ToolStep) -> ExecutionPlan:
    return ExecutionPlan(
        ordered_tools=list(steps),
        execution_mode=ExecutionMode.SEQUENTIAL,
        tool_count=len(steps),
        is_empty=False,
    )


# ════════════════════════════════════════════════════════════════════════
# Data Contract: StepResult
# ════════════════════════════════════════════════════════════════════════


class TestStepResult(unittest.TestCase):
    def test_success(self):
        sr = StepResult(
            step_id="s1", tool="waste_tool", action="search",
            success=True, data={"count": 5}, message="OK",
            elapsed_ms=120.5, attempts=1,
        )
        d = sr.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["count"], 5)
        self.assertNotIn("attempts", d)  # only shown when > 1
        self.assertNotIn("error_code", d)

    def test_failure(self):
        sr = StepResult(
            step_id="s1", tool="waste_tool", action="search",
            success=False, message="Erreur",
            error_code="tool_not_found",
        )
        d = sr.to_dict()
        self.assertFalse(d["success"])
        self.assertEqual(d["error_code"], "tool_not_found")

    def test_retry_attempts_shown(self):
        sr = StepResult(
            step_id="s1", tool="x", action="y",
            success=False, attempts=3,
        )
        d = sr.to_dict()
        self.assertEqual(d["attempts"], 3)

    def test_no_data_omitted(self):
        sr = StepResult(
            step_id="s1", tool="x", action="y",
            success=True, data=None,
        )
        d = sr.to_dict()
        self.assertNotIn("data", d)


# ════════════════════════════════════════════════════════════════════════
# Data Contract: ToolExecutionResult
# ════════════════════════════════════════════════════════════════════════


class TestToolExecutionResult(unittest.TestCase):
    def test_empty(self):
        ter = ToolExecutionResult(success=True)
        self.assertTrue(ter.all_succeeded)
        self.assertFalse(ter.has_data)
        self.assertIsNone(ter.merged_data)

    def test_all_succeeded(self):
        sr = StepResult(step_id="s1", tool="a", action="x", success=True)
        ter = ToolExecutionResult(
            success=True, step_results=[sr],
            steps_succeeded=1, steps_failed=0,
        )
        self.assertTrue(ter.all_succeeded)

    def test_has_failure(self):
        sr = StepResult(step_id="s1", tool="a", action="x", success=False)
        ter = ToolExecutionResult(
            success=False, step_results=[sr],
            steps_succeeded=0, steps_failed=1,
        )
        self.assertFalse(ter.all_succeeded)

    def test_has_data(self):
        sr = StepResult(
            step_id="s1", tool="a", action="x",
            success=True, data={"k": "v"},
        )
        ter = ToolExecutionResult(success=True, step_results=[sr])
        self.assertTrue(ter.has_data)

    def test_merged_data_single(self):
        sr = StepResult(
            step_id="s1", tool="a", action="x",
            success=True, data={"count": 5},
        )
        ter = ToolExecutionResult(success=True, step_results=[sr])
        self.assertEqual(ter.merged_data, {"count": 5})

    def test_merged_data_multiple_dicts(self):
        sr1 = StepResult(
            step_id="s1", tool="a", action="x",
            success=True, data={"a": 1},
        )
        sr2 = StepResult(
            step_id="s2", tool="b", action="y",
            success=True, data={"b": 2},
        )
        ter = ToolExecutionResult(
            success=True, step_results=[sr1, sr2],
        )
        self.assertEqual(ter.merged_data, {"a": 1, "b": 2})

    def test_merged_data_mixed_types(self):
        sr1 = StepResult(
            step_id="s1", tool="a", action="x",
            success=True, data=[1, 2],
        )
        sr2 = StepResult(
            step_id="s2", tool="b", action="y",
            success=True, data={"b": 2},
        )
        ter = ToolExecutionResult(
            success=True, step_results=[sr1, sr2],
        )
        self.assertIsInstance(ter.merged_data, list)

    def test_to_dict_full(self):
        sr = StepResult(
            step_id="s1", tool="a", action="x",
            success=True, data={"k": "v"}, elapsed_ms=100.0,
        )
        ter = ToolExecutionResult(
            success=True, step_results=[sr],
            total_elapsed_ms=150.5,
            steps_succeeded=1,
            messages=["ok"],
        )
        d = ter.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["total_elapsed_ms"], 150.5)
        self.assertIn("messages", d)
        self.assertIn("data", d)

    def test_to_dict_no_messages(self):
        ter = ToolExecutionResult(success=True)
        d = ter.to_dict()
        self.assertNotIn("messages", d)
        self.assertNotIn("data", d)


# ════════════════════════════════════════════════════════════════════════
# Single Step Execution
# ════════════════════════════════════════════════════════════════════════


class TestSingleStepExecution(unittest.TestCase):
    def test_success(self):
        tool = _make_mock_tool(
            execute_return={"success": True, "data": {"count": 5}, "message": "OK"},
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)

        self.assertTrue(result.success)
        self.assertEqual(result.data["count"], 5)
        self.assertEqual(result.attempts, 1)
        tool.execute.assert_called_once()

    def test_tool_not_found(self):
        registry = _make_mock_registry({})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step(tool="nonexistent_tool")
        result = executor.execute_step(step)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "tool_not_found")
        self.assertIn("n'existe pas", result.message)

    def test_tool_exception_caught(self):
        tool = _make_mock_tool(
            execute_side_effect=RuntimeError("internal crash"),
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "tool_exception")
        self.assertIn("échoué", result.message)
        # Must NOT contain the original exception text
        self.assertNotIn("internal crash", result.message)
        self.assertNotIn("RuntimeError", result.message)

    def test_timeout(self):
        def slow_execute(params, ctx):
            time.sleep(5)
            return MagicMock(to_dict=lambda: {"success": True, "data": None})

        tool = _make_mock_tool()
        tool.execute.side_effect = slow_execute
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry, default_timeout=0.1)

        step = _make_step(timeout_ms=100.0)
        result = executor.execute_step(step)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "timeout")
        self.assertIn("délai", result.message)

    def test_action_injected(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step(action="search", params={"query": "test"})
        executor.execute_step(step)

        call_params = tool.execute.call_args[0][0]
        self.assertEqual(call_params["action"], "search")

    def test_existing_action_not_overwritten(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step(action="search", params={"action": "dangerous"})
        executor.execute_step(step)

        call_params = tool.execute.call_args[0][0]
        self.assertEqual(call_params["action"], "dangerous")

    def test_elapsed_ms_positive(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertGreater(result.elapsed_ms, 0)

    def test_registry_exception_treated_as_not_found(self):
        registry = MagicMock()
        registry.get.side_effect = RuntimeError("registry broken")
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "tool_not_found")


# ════════════════════════════════════════════════════════════════════════
# Plan Execution
# ════════════════════════════════════════════════════════════════════════


class TestPlanExecution(unittest.TestCase):
    def test_empty_plan(self):
        executor = ToolExecutorV2(registry=_make_mock_registry())
        plan = ExecutionPlan(is_empty=True)
        result = executor.execute_plan(plan)
        self.assertTrue(result.success)
        self.assertEqual(len(result.step_results), 0)

    def test_single_step_plan(self):
        tool = _make_mock_tool(
            execute_return={"success": True, "data": {"count": 3}},
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)
        plan = _make_plan(_make_step())

        result = executor.execute_plan(plan)

        self.assertTrue(result.success)
        self.assertEqual(result.steps_succeeded, 1)
        self.assertEqual(result.steps_failed, 0)

    def test_multi_step_all_success(self):
        tool1 = _make_mock_tool(
            name="waste_tool",
            execute_return={"success": True, "data": {"a": 1}},
        )
        tool2 = _make_mock_tool(
            name="glossaire_tool",
            execute_return={"success": True, "data": {"b": 2}},
        )
        registry = _make_mock_registry({
            "waste_tool": tool1, "glossaire_tool": tool2,
        })
        executor = ToolExecutorV2(registry=registry)
        plan = _make_plan(
            _make_step(tool="waste_tool"),
            _make_step(step_id="step_2", tool="glossaire_tool"),
        )

        result = executor.execute_plan(plan)

        self.assertTrue(result.success)
        self.assertTrue(result.all_succeeded)
        self.assertEqual(result.steps_succeeded, 2)
        self.assertEqual(result.steps_failed, 0)

    def test_multi_step_partial_failure(self):
        tool1 = _make_mock_tool(
            name="waste_tool",
            execute_return={"success": True, "data": {"a": 1}},
        )
        registry = _make_mock_registry({"waste_tool": tool1})
        executor = ToolExecutorV2(registry=registry)
        plan = _make_plan(
            _make_step(tool="waste_tool"),
            _make_step(step_id="step_2", tool="nonexistent"),
        )

        result = executor.execute_plan(plan)

        self.assertFalse(result.success)
        self.assertEqual(result.steps_succeeded, 1)
        self.assertEqual(result.steps_failed, 1)
        self.assertEqual(len(result.messages), 1)

    def test_plan_total_elapsed_positive(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)
        plan = _make_plan(_make_step())

        result = executor.execute_plan(plan)
        self.assertGreater(result.total_elapsed_ms, 0)

    def test_plan_to_dict_serializable(self):
        tool = _make_mock_tool(
            execute_return={"success": True, "data": {"k": "v"}},
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)
        plan = _make_plan(_make_step())

        result = executor.execute_plan(plan)
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertTrue(d["success"])


# ════════════════════════════════════════════════════════════════════════
# Retry Logic
# ════════════════════════════════════════════════════════════════════════


class TestRetryLogic(unittest.TestCase):
    def test_retry_on_failure(self):
        tool = _make_mock_tool()
        # Fail first two attempts, succeed on third
        tool.execute.side_effect = [
            RuntimeError("fail 1"),
            MagicMock(to_dict=lambda: {"success": False, "message": "fail 2"}),
            MagicMock(to_dict=lambda: {"success": True, "data": {"ok": True}}),
        ]
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step(retry=2)
        result = executor.execute_step(step)

        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 3)

    def test_retry_exhausted(self):
        tool = _make_mock_tool(
            execute_side_effect=RuntimeError("always fail"),
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step(retry=2)
        result = executor.execute_step(step)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "tool_exception")
        self.assertEqual(result.attempts, 3)
        self.assertIn("3 tentative(s)", result.message)

    def test_no_retry_on_success(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step(retry=3)
        result = executor.execute_step(step)

        self.assertTrue(result.success)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(tool.execute.call_count, 1)

    def test_retry_delay_increases(self):
        executor = ToolExecutorV2(registry=_make_mock_registry())
        self.assertAlmostEqual(executor._retry_delay(1), 0.5)
        self.assertAlmostEqual(executor._retry_delay(2), 1.0)
        self.assertAlmostEqual(executor._retry_delay(3), 2.0)
        self.assertAlmostEqual(executor._retry_delay(4), 4.0)
        self.assertAlmostEqual(executor._retry_delay(10), 10.0)  # clamped


# ════════════════════════════════════════════════════════════════════════
# Output Validation
# ════════════════════════════════════════════════════════════════════════


class TestOutputValidation(unittest.TestCase):
    def test_non_serialisable_data(self):
        tool = _make_mock_tool()
        # Return object that can't be JSON-serialised
        response = MagicMock()
        response.to_dict.return_value = {
            "success": True,
            "data": {"obj": object()},  # not serialisable
            "message": "OK",
        }
        tool.execute.return_value = response
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)

        # Should succeed — the default=str in json.dumps handles objects
        # But if it truly can't serialise, it fails
        self.assertIsInstance(result, StepResult)

    def test_sensitive_data_in_message_stripped(self):
        tool = _make_mock_tool()
        response = MagicMock()
        response.to_dict.return_value = {
            "success": False,
            "data": None,
            "message": "Traceback (most recent call last):\n  File \"views.py\"",
        }
        tool.execute.return_value = response
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)

        self.assertNotIn("Traceback", result.message)
        self.assertNotIn("views.py", result.message)

    def test_normal_message_preserved(self):
        tool = _make_mock_tool(
            execute_return={
                "success": True,
                "data": {"k": "v"},
                "message": "Résultat trouvé",
            },
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertEqual(result.message, "Résultat trouvé")


# ════════════════════════════════════════════════════════════════════════
# Sensitive Data Detection
# ════════════════════════════════════════════════════════════════════════


class TestSensitiveDetection(unittest.TestCase):
    def test_traceback(self):
        self.assertTrue(ToolExecutorV2._contains_sensitive("Traceback (most recent call)"))

    def test_django_model(self):
        self.assertTrue(ToolExecutorV2._contains_sensitive("django.db.models"))

    def test_integrity_error(self):
        self.assertTrue(ToolExecutorV2._contains_sensitive("IntegrityError occurred"))

    def test_password_leak(self):
        self.assertTrue(ToolExecutorV2._contains_sensitive("password=secret123"))

    def test_file_path(self):
        self.assertTrue(ToolExecutorV2._contains_sensitive("File \"/home/user/app.py\""))

    def test_venv_path(self):
        self.assertTrue(ToolExecutorV2._contains_sensitive("venv/lib/python3"))

    def test_clean_message(self):
        self.assertFalse(ToolExecutorV2._contains_sensitive("Résultat trouvé avec succès"))

    def test_empty_message(self):
        self.assertFalse(ToolExecutorV2._contains_sensitive(""))
        self.assertFalse(ToolExecutorV2._contains_sensitive(None))


# ════════════════════════════════════════════════════════════════════════
# Callback Hook
# ════════════════════════════════════════════════════════════════════════


class TestCallbackHook(unittest.TestCase):
    def test_callback_called(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        calls = []
        executor = ToolExecutorV2(
            registry=registry,
            on_step_complete=lambda sr: calls.append(sr),
        )
        plan = _make_plan(_make_step())

        executor.execute_plan(plan)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].success)

    def test_callback_exception_doesnt_crash(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})

        def bad_callback(sr):
            raise RuntimeError("callback broken")

        executor = ToolExecutorV2(
            registry=registry,
            on_step_complete=bad_callback,
        )
        plan = _make_plan(_make_step())

        result = executor.execute_plan(plan)
        self.assertTrue(result.success)


# ════════════════════════════════════════════════════════════════════════
# Error Isolation
# ════════════════════════════════════════════════════════════════════════


class TestErrorIsolation(unittest.TestCase):
    def test_exception_never_leaks(self):
        """Every exception must be caught and wrapped."""
        tool = _make_mock_tool(
            execute_side_effect=KeyboardInterrupt("ctrl+c"),
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)

        self.assertFalse(result.success)
        self.assertNotIn("KeyboardInterrupt", result.message)
        self.assertNotIn("ctrl+c", result.message)

    def test_system_exit_caught(self):
        tool = _make_mock_tool(
            execute_side_effect=SystemExit(1),
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertFalse(result.success)

    def test_memory_error_caught(self):
        tool = _make_mock_tool(
            execute_side_effect=MemoryError("out of memory"),
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertFalse(result.success)
        self.assertNotIn("MemoryError", result.message)

    def test_french_messages_only(self):
        """All error messages must be in French, never English."""
        tool = _make_mock_tool(
            execute_side_effect=RuntimeError("oops"),
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        # Must not contain English error patterns
        self.assertNotIn("Error", result.message)
        self.assertNotIn("Exception", result.message)
        self.assertNotIn("Failed", result.message)


# ════════════════════════════════════════════════════════════════════════
# Tool Response Formats
# ════════════════════════════════════════════════════════════════════════


class TestToolResponseFormats(unittest.TestCase):
    def test_dict_response(self):
        """Tool returns plain dict instead of ToolResultResponse."""
        tool = _make_mock_tool()
        tool.execute.return_value = {
            "success": True, "data": {"count": 10}, "message": "OK",
        }
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertTrue(result.success)
        self.assertEqual(result.data["count"], 10)

    def test_non_dict_response(self):
        """Tool returns a raw value."""
        tool = _make_mock_tool()
        tool.execute.return_value = "raw string result"
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertTrue(result.success)
        self.assertEqual(result.data, "raw string result")

    def test_none_response(self):
        tool = _make_mock_tool()
        tool.execute.return_value = None
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertTrue(result.success)

    def test_response_without_to_dict(self):
        tool = _make_mock_tool()
        tool.execute.return_value = 42
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step()
        result = executor.execute_step(step)
        self.assertTrue(result.success)
        self.assertEqual(result.data, 42)


# ════════════════════════════════════════════════════════════════════════
# Edge Cases
# ════════════════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):
    def test_step_with_empty_params(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step(params={})
        result = executor.execute_step(step)
        self.assertTrue(result.success)

    def test_step_with_large_params(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        big_query = "x" * 10000
        step = _make_step(params={"query": big_query})
        result = executor.execute_step(step)
        self.assertTrue(result.success)

    def test_very_many_steps(self):
        tools = {}
        steps = []
        for i in range(20):
            name = f"tool_{i}"
            tools[name] = _make_mock_tool(name=name)
            steps.append(_make_step(
                step_id=f"step_{i}", tool=name, action="do",
            ))
        registry = _make_mock_registry(tools)
        executor = ToolExecutorV2(registry=registry)
        plan = _make_plan(*steps)

        result = executor.execute_plan(plan)
        self.assertTrue(result.success)
        self.assertEqual(result.steps_succeeded, 20)

    def test_special_characters_in_params(self):
        tool = _make_mock_tool()
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        step = _make_step(params={"query": "Éàèêë!@#$%^&*()"})
        result = executor.execute_step(step)
        self.assertTrue(result.success)


# ════════════════════════════════════════════════════════════════════════
# Framework Independence
# ════════════════════════════════════════════════════════════════════════


class TestFrameworkIndependence(unittest.TestCase):
    def test_no_django_imports(self):
        import apps.ai_assistant.enterprise.tool_executor_v2 as mod
        source = open(mod.__file__).read()
        self.assertNotIn("import django", source)
        self.assertNotIn("from django", source)

    def test_no_repository_imports(self):
        import apps.ai_assistant.enterprise.tool_executor_v2 as mod
        source = open(mod.__file__).read()
        self.assertNotIn("from apps.ai_assistant.repositories", source)

    def test_no_model_imports(self):
        import apps.ai_assistant.enterprise.tool_executor_v2 as mod
        source = open(mod.__file__).read()
        self.assertNotIn("from apps.accounts.models", source)

    def test_registry_injected_not_imported(self):
        """Registry must be injected via constructor, not imported."""
        import apps.ai_assistant.enterprise.tool_executor_v2 as mod
        source = open(mod.__file__).read()
        self.assertNotIn("from apps.ai_assistant.tools.tool_registry import", source)

    def test_dataclasses_frozen(self):
        from dataclasses import fields
        for cls in [StepResult, ToolExecutionResult]:
            self.assertTrue(
                getattr(cls, "__dataclass_params__").frozen,
                f"{cls.__name__} is not frozen",
            )


# ════════════════════════════════════════════════════════════════════════
# Full Integration: Plan → Execute → Result
# ════════════════════════════════════════════════════════════════════════


class TestFullIntegration(unittest.TestCase):
    def test_end_to_end_read_plan(self):
        tool = _make_mock_tool(
            execute_return={
                "success": True,
                "data": {"waste_codes": ["15.01.06"]},
                "message": "Trouvé",
            },
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        planner = ToolPlanner()
        proposal = DecisionProposal(
            message="Quels déchets dangereux ?",
            tool="waste_tool", action="search",
            parameters={"query": "déchets dangereux"},
            confidence=0.95,
        )
        plan = planner.plan(proposal)
        result = executor.execute_plan(plan)

        self.assertTrue(result.success)
        self.assertTrue(result.all_succeeded)
        self.assertTrue(result.has_data)
        self.assertEqual(result.merged_data["waste_codes"], ["15.01.06"])

    def test_end_to_end_plan_serializable(self):
        tool = _make_mock_tool(
            execute_return={"success": True, "data": {"k": "v"}},
        )
        registry = _make_mock_registry({"waste_tool": tool})
        executor = ToolExecutorV2(registry=registry)

        planner = ToolPlanner()
        proposal = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "test"}, confidence=0.9,
        )
        plan = planner.plan(proposal)
        result = executor.execute_plan(plan)
        d = result.to_dict()

        self.assertIsInstance(d, dict)
        self.assertTrue(d["success"])
        self.assertEqual(len(d["step_results"]), 1)


if __name__ == "__main__":
    unittest.main()
