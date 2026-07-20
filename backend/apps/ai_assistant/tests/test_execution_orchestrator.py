"""
Unit Tests — ExecutionOrchestrator.

Tests the full pipeline: ReasoningOrchestrator → ToolPlanner → ToolExecutorV2.
All dependencies are mocked — no real components.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from apps.ai_assistant.enterprise.execution_orchestrator import ExecutionOrchestrator
from apps.ai_assistant.enterprise.tool_planner import DecisionProposal, ExecutionPlan
from apps.ai_assistant.enterprise.tool_executor_v2 import (
    ToolExecutionResult,
    StepResult,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _proposal(tool="nomenclature_tool", action="search", confidence=0.85):
    return DecisionProposal(
        message="code 01.01.01",
        tool=tool,
        action=action,
        parameters={"code": "01.01.01"},
        confidence=confidence,
    )


def _empty_proposal():
    return DecisionProposal(tool="none")


def _plan(tool="nomenclature_tool"):
    step = MagicMock()
    step.step_id = "step_1"
    step.tool = tool
    step.action = "search"
    step.parameters = {"code": "01.01.01"}
    return ExecutionPlan(
        ordered_tools=[step],
        execution_mode="sequential",
        tool_count=1,
        is_empty=False,
    )


def _empty_plan():
    return ExecutionPlan(is_empty=True, tool_count=0)


def _success_result():
    return ToolExecutionResult(
        success=True,
        step_results=[
            StepResult(
                step_id="step_1",
                tool="nomenclature_tool",
                action="search",
                success=True,
                data={"code": "01.01.01", "name": "Papier"},
                message="OK",
                elapsed_ms=42.5,
            )
        ],
        total_elapsed_ms=42.5,
        steps_succeeded=1,
        steps_failed=0,
    )


def _failed_result():
    return ToolExecutionResult(
        success=False,
        step_results=[
            StepResult(
                step_id="step_1",
                tool="nomenclature_tool",
                action="search",
                success=False,
                message="L'outil 'nomenclature_tool' n'existe pas.",
                elapsed_ms=10.0,
                error_code="tool_not_found",
            )
        ],
        total_elapsed_ms=10.0,
        steps_succeeded=0,
        steps_failed=1,
        messages=["Étape 'step_1' a échoué."],
    )


def _make_mocks(
    reason_proposal=None,
    plan_result=None,
    execute_result=None,
):
    """Build mock reasoning_orchestrator, tool_planner, tool_executor_v2."""
    ro = MagicMock()
    if reason_proposal is not None:
        ro.reason.return_value = reason_proposal
    else:
        ro.reason.return_value = _proposal()

    tp = MagicMock()
    if plan_result is not None:
        tp.plan.return_value = plan_result
    else:
        tp.plan.return_value = _plan()

    te = MagicMock()
    if execute_result is not None:
        te.execute_plan.return_value = execute_result
    else:
        te.execute_plan.return_value = _success_result()

    return ro, tp, te


# ══════════════════════════════════════════════════════════════════════
# Tests — Constructor & Properties
# ══════════════════════════════════════════════════════════════════════


class TestExecutionOrchestratorInit(unittest.TestCase):

    def test_all_components(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        self.assertTrue(eo.has_reasoning_orchestrator)
        self.assertTrue(eo.has_tool_planner)
        self.assertTrue(eo.has_tool_executor_v2)
        self.assertTrue(eo.is_available)

    def test_no_components(self):
        eo = ExecutionOrchestrator()
        self.assertFalse(eo.has_reasoning_orchestrator)
        self.assertFalse(eo.has_tool_planner)
        self.assertFalse(eo.has_tool_executor_v2)
        self.assertFalse(eo.is_available)

    def test_partial_components(self):
        ro, _, _ = _make_mocks()
        eo = ExecutionOrchestrator(reasoning_orchestrator=ro)
        self.assertTrue(eo.has_reasoning_orchestrator)
        self.assertFalse(eo.has_tool_planner)
        self.assertFalse(eo.has_tool_executor_v2)
        self.assertFalse(eo.is_available)


# ══════════════════════════════════════════════════════════════════════
# Tests — execute()
# ══════════════════════════════════════════════════════════════════════


class TestExecutionOrchestratorExecute(unittest.TestCase):

    def test_full_pipeline(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("code 01.01.01")
        self.assertIsInstance(result, ToolExecutionResult)
        self.assertTrue(result.success)
        self.assertTrue(result.has_data)

    def test_calls_reasoning_orchestrator(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        eo.execute("bonjour")
        ro.reason.assert_called_once_with("bonjour", context=None)

    def test_calls_tool_planner_with_proposal(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        eo.execute("code 01.01.01")
        tp.plan.assert_called_once()
        call_args = tp.plan.call_args
        self.assertIsInstance(call_args[0][0], DecisionProposal)

    def test_calls_tool_executor_with_plan(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        eo.execute("code 01.01.01")
        te.execute_plan.assert_called_once()
        call_args = te.execute_plan.call_args
        self.assertIsInstance(call_args[0][0], ExecutionPlan)

    def test_passes_context(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        ctx = MagicMock()
        eo.execute("test", context=ctx)
        te.execute_plan.assert_called_once()
        call_kwargs = te.execute_plan.call_args
        self.assertIs(call_kwargs[1].get("context", call_kwargs[0][1] if len(call_args := call_kwargs[0]) > 1 else None), ctx)

    def test_no_reasoning_orchestrator(self):
        _, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=None,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("test")
        self.assertTrue(result.success)
        self.assertEqual(result.messages, ["Raisonnement indisponible."])

    def test_no_tool_planner(self):
        ro, _, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=None,
            tool_executor_v2=te,
        )
        result = eo.execute("test")
        self.assertTrue(result.success)
        self.assertEqual(result.messages, ["Planification indisponible."])

    def test_no_tool_executor(self):
        ro, tp, _ = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=None,
        )
        result = eo.execute("test")
        self.assertFalse(result.success)
        self.assertEqual(result.messages, ["Exécuteur indisponible."])

    def test_none_available(self):
        eo = ExecutionOrchestrator()
        result = eo.execute("test")
        self.assertTrue(result.success)
        self.assertEqual(result.messages, ["Raisonnement indisponible."])

    def test_empty_proposal(self):
        ro, tp, te = _make_mocks(reason_proposal=_empty_proposal())
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("xyzzy")
        self.assertTrue(result.success)
        self.assertEqual(result.messages, ["Aucun outil nécessaire."])
        tp.plan.assert_not_called()

    def test_empty_plan(self):
        ro, tp, te = _make_mocks(plan_result=_empty_plan())
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("xyzzy")
        self.assertTrue(result.success)
        self.assertEqual(result.messages, ["Aucun outil à exécuter."])
        te.execute_plan.assert_not_called()

    def test_reasoning_exception(self):
        ro = MagicMock()
        ro.reason.side_effect = RuntimeError("boom")
        tp = MagicMock()
        te = MagicMock()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("test")
        self.assertTrue(result.success)
        self.assertEqual(result.messages, ["Raisonnement indisponible."])
        tp.plan.assert_not_called()

    def test_planner_exception(self):
        ro = MagicMock()
        ro.reason.return_value = _proposal()
        tp = MagicMock()
        tp.plan.side_effect = RuntimeError("boom")
        te = MagicMock()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("test")
        self.assertTrue(result.success)
        self.assertEqual(result.messages, ["Planification indisponible."])
        te.execute_plan.assert_not_called()

    def test_executor_exception(self):
        ro, tp, te = _make_mocks()
        te.execute_plan.side_effect = RuntimeError("boom")
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("test")
        self.assertFalse(result.success)
        self.assertEqual(result.messages, ["Exécution échouée."])

    def test_executor_failure(self):
        ro, tp, te = _make_mocks(execute_result=_failed_result())
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("test")
        self.assertFalse(result.success)
        self.assertEqual(result.steps_failed, 1)


# ══════════════════════════════════════════════════════════════════════
# Tests — execute_with_trace()
# ══════════════════════════════════════════════════════════════════════


class TestExecutionOrchestratorExecuteWithTrace(unittest.TestCase):

    def test_returns_three_tuple(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute_with_trace("code 01.01.01")
        self.assertEqual(len(result), 3)

    def test_result_is_tool_execution_result(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        execution_result, proposal, plan = eo.execute_with_trace("test")
        self.assertIsInstance(execution_result, ToolExecutionResult)

    def test_proposal_is_decision_proposal(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        _, proposal, plan = eo.execute_with_trace("test")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_plan_is_execution_plan(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        _, proposal, plan = eo.execute_with_trace("test")
        self.assertIsInstance(plan, ExecutionPlan)

    def test_trace_no_reasoning(self):
        _, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=None,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result, proposal, plan = eo.execute_with_trace("test")
        self.assertTrue(result.success)
        self.assertIsNone(proposal)
        self.assertIsNone(plan)

    def test_trace_empty_proposal(self):
        ro, tp, te = _make_mocks(reason_proposal=_empty_proposal())
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result, proposal, plan = eo.execute_with_trace("test")
        self.assertTrue(result.success)
        self.assertIsNotNone(proposal)
        self.assertIsNone(plan)

    def test_trace_no_planner(self):
        ro, _, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=None,
            tool_executor_v2=te,
        )
        result, proposal, plan = eo.execute_with_trace("test")
        self.assertTrue(result.success)
        self.assertIsNotNone(proposal)
        self.assertIsNone(plan)

    def test_trace_empty_plan(self):
        ro, tp, te = _make_mocks(plan_result=_empty_plan())
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result, proposal, plan = eo.execute_with_trace("test")
        self.assertTrue(result.success)
        self.assertIsNotNone(proposal)
        self.assertIsNotNone(plan)

    def test_trace_exception(self):
        ro = MagicMock()
        ro.reason.side_effect = RuntimeError("boom")
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=MagicMock(),
            tool_executor_v2=MagicMock(),
        )
        result, proposal, plan = eo.execute_with_trace("test")
        self.assertTrue(result.success)
        self.assertIsNone(proposal)
        self.assertIsNone(plan)


# ══════════════════════════════════════════════════════════════════════
# Tests — Edge Cases
# ══════════════════════════════════════════════════════════════════════


class TestExecutionOrchestratorEdgeCases(unittest.TestCase):

    def test_empty_message(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("")
        self.assertIsInstance(result, ToolExecutionResult)

    def test_none_message(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute(None)
        self.assertIsInstance(result, ToolExecutionResult)

    def test_long_message(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("x" * 10000)
        self.assertIsInstance(result, ToolExecutionResult)

    def test_proposal_with_context(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("test", context={"user_id": "u1"})
        self.assertIsInstance(result, ToolExecutionResult)

    def test_multiple_calls_same_instance(self):
        ro, tp, te = _make_mocks()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        r1 = eo.execute("test1")
        r2 = eo.execute("test2")
        self.assertIsInstance(r1, ToolExecutionResult)
        self.assertIsInstance(r2, ToolExecutionResult)
        self.assertEqual(ro.reason.call_count, 2)


if __name__ == "__main__":
    unittest.main()
