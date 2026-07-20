"""
Integration Tests — ExecutionOrchestrator.

Tests with real AIReasoningPolicy + ToolPlanner, mocked ToolExecutorV2.
Verifies the full chain: message → DecisionProposal → ExecutionPlan → ToolExecutionResult.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from apps.ai_assistant.enterprise.execution_orchestrator import ExecutionOrchestrator
from apps.ai_assistant.enterprise.reasoning_orchestrator import ReasoningOrchestrator
from apps.ai_assistant.enterprise.reasoning_policy import AIReasoningPolicy
from apps.ai_assistant.enterprise.decision_engine import DecisionEngine
from apps.ai_assistant.enterprise.tool_planner import (
    DecisionProposal,
    ExecutionPlan,
    ToolPlanner,
)
from apps.ai_assistant.enterprise.tool_executor_v2 import (
    ToolExecutionResult,
    StepResult,
)


# ── Helpers ────────────────────────────────────────────────────────────


class _MockContainer:
    def __init__(self):
        self._search = MagicMock()

    @property
    def search_engine(self):
        return self._search


def _mock_executor(success=True, data=None):
    te = MagicMock()
    te.execute_plan.return_value = ToolExecutionResult(
        success=success,
        step_results=[
            StepResult(
                step_id="step_1",
                tool="nomenclature_tool",
                action="search",
                success=success,
                data=data or {"code": "01.01.01", "name": "Papier"},
                message="OK" if success else "Erreur",
                elapsed_ms=42.0,
            )
        ],
        total_elapsed_ms=42.0,
        steps_succeeded=1 if success else 0,
        steps_failed=0 if success else 1,
    )
    return te


def _build_eo(
    use_reasoning_policy=True,
    use_decision_engine=False,
    executor=None,
):
    rp = AIReasoningPolicy() if use_reasoning_policy else None
    de = DecisionEngine(container=_MockContainer()) if use_decision_engine else None
    ro = ReasoningOrchestrator(reasoning_policy=rp, decision_engine=de)
    tp = ToolPlanner()
    te = executor or _mock_executor()
    return ExecutionOrchestrator(
        reasoning_orchestrator=ro,
        tool_planner=tp,
        tool_executor_v2=te,
    )


# ── Integration: AIReasoningPolicy Only ───────────────────────────────


class TestIntegrationReasoningPolicyOnly(unittest.TestCase):

    def test_greeting(self):
        eo = _build_eo(use_decision_engine=False)
        result, proposal, plan = eo.execute_with_trace("bonjour")
        self.assertIsInstance(result, ToolExecutionResult)
        self.assertIsInstance(proposal, DecisionProposal)
        # greeting → no tool execution
        self.assertTrue(result.success)

    def test_waste_code(self):
        eo = _build_eo(use_decision_engine=False)
        result, proposal, plan = eo.execute_with_trace("code 01.01.01")
        self.assertIsInstance(result, ToolExecutionResult)
        self.assertIsInstance(proposal, DecisionProposal)
        self.assertIsInstance(plan, ExecutionPlan)

    def test_bsd_number(self):
        eo = _build_eo(use_decision_engine=False)
        result, proposal, plan = eo.execute_with_trace("BSD-20241234")
        self.assertIsInstance(result, ToolExecutionResult)
        self.assertIsInstance(proposal, DecisionProposal)

    def test_nomenclature(self):
        eo = _build_eo(use_decision_engine=False)
        result, proposal, plan = eo.execute_with_trace("nomenclature des dechets")
        self.assertIsInstance(result, ToolExecutionResult)
        self.assertIsInstance(proposal, DecisionProposal)


# ── Integration: AIReasoningPolicy + DecisionEngine ───────────────────


class TestIntegrationBothReasoners(unittest.TestCase):

    def test_greeting(self):
        eo = _build_eo(use_decision_engine=True)
        result, proposal, plan = eo.execute_with_trace("bonjour")
        self.assertIsInstance(result, ToolExecutionResult)
        self.assertTrue(result.success)

    def test_waste_code(self):
        eo = _build_eo(use_decision_engine=True)
        result, proposal, plan = eo.execute_with_trace("code 01.01.01")
        self.assertIsInstance(result, ToolExecutionResult)
        self.assertIsInstance(proposal, DecisionProposal)
        self.assertIsInstance(plan, ExecutionPlan)

    def test_bsd_number(self):
        eo = _build_eo(use_decision_engine=True)
        result, proposal, plan = eo.execute_with_trace("BSD-20241234")
        self.assertIsInstance(result, ToolExecutionResult)

    def test_trace_has_both(self):
        eo = _build_eo(use_decision_engine=True)
        _, proposal, plan = eo.execute_with_trace("code 01.01.01")
        self.assertIsNotNone(proposal)
        self.assertIsNotNone(plan)


# ── Integration: Proposal → Plan → Result ──────────────────────────────


class TestIntegrationProposalToResult(unittest.TestCase):

    def test_proposal_feeds_planner(self):
        eo = _build_eo()
        _, proposal, plan = eo.execute_with_trace("code 01.01.01")
        self.assertIsNotNone(plan)
        if proposal.has_tool:
            self.assertFalse(plan.is_empty)
            self.assertEqual(plan.tool_count, 1)

    def test_plan_feeds_executor(self):
        eo = _build_eo()
        result, _, plan = eo.execute_with_trace("code 01.01.01")
        if plan is not None and not plan.is_empty:
            self.assertIsInstance(result, ToolExecutionResult)

    def test_executor_receives_correct_plan(self):
        te = _mock_executor()
        eo = _build_eo(executor=te)
        _, proposal, plan = eo.execute_with_trace("code 01.01.01")
        if plan is not None and not plan.is_empty:
            te.execute_plan.assert_called_once()
            call_args = te.execute_plan.call_args
            self.assertIsInstance(call_args[0][0], ExecutionPlan)


# ── Integration: Fallback Scenarios ───────────────────────────────────


class TestIntegrationFallbacks(unittest.TestCase):

    def test_no_reasoning_policy(self):
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=None,
            tool_planner=ToolPlanner(),
            tool_executor_v2=_mock_executor(),
        )
        result = eo.execute("code 01.01.01")
        self.assertTrue(result.success)
        self.assertEqual(result.messages, ["Raisonnement indisponible."])

    def test_no_executor(self):
        rp = AIReasoningPolicy()
        ro = ReasoningOrchestrator(reasoning_policy=rp)
        tp = ToolPlanner()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            tool_planner=tp,
            tool_executor_v2=None,
        )
        result = eo.execute("code 01.01.01")
        self.assertFalse(result.success)
        self.assertEqual(result.messages, ["Exécuteur indisponible."])

    def test_executor_exception(self):
        te = MagicMock()
        te.execute_plan.side_effect = RuntimeError("boom")
        eo = _build_eo(executor=te)
        result = eo.execute("code 01.01.01")
        self.assertFalse(result.success)
        self.assertEqual(result.messages, ["Exécution échouée."])

    def test_executor_failure(self):
        te = MagicMock()
        te.execute_plan.return_value = ToolExecutionResult(
            success=False,
            step_results=[
                StepResult(
                    step_id="step_1",
                    tool="nomenclature_tool",
                    action="search",
                    success=False,
                    message="L'outil n'existe pas.",
                    elapsed_ms=10.0,
                    error_code="tool_not_found",
                )
            ],
            total_elapsed_ms=10.0,
            steps_succeeded=0,
            steps_failed=1,
        )
        eo = _build_eo(executor=te)
        result = eo.execute("code 01.01.01")
        self.assertFalse(result.success)
        self.assertEqual(result.steps_failed, 1)


# ── Integration: Container DI ─────────────────────────────────────────


class TestIntegrationContainerDI(unittest.TestCase):

    def test_container_creates_execution_orchestrator(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        eo = c.execution_orchestrator
        self.assertIsInstance(eo, ExecutionOrchestrator)
        self.assertTrue(eo.has_reasoning_orchestrator)
        self.assertTrue(eo.has_tool_planner)
        self.assertTrue(eo.has_tool_executor_v2)
        self.assertTrue(eo.is_available)

    def test_container_returns_same_instance(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        e1 = c.execution_orchestrator
        e2 = c.execution_orchestrator
        self.assertIs(e1, e2)

    def test_container_execution_orchestrator_works(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        eo = c.execution_orchestrator
        result = eo.execute("test")
        self.assertIsInstance(result, ToolExecutionResult)


# ── Integration: execute_with_trace types ──────────────────────────────


class TestIntegrationTraceTypes(unittest.TestCase):

    def test_result_type(self):
        eo = _build_eo()
        result, _, _ = eo.execute_with_trace("test")
        self.assertIsInstance(result, ToolExecutionResult)

    def test_proposal_type(self):
        eo = _build_eo()
        _, proposal, _ = eo.execute_with_trace("test")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_plan_type(self):
        eo = _build_eo()
        _, _, plan = eo.execute_with_trace("code 01.01.01")
        self.assertIsInstance(plan, ExecutionPlan)


if __name__ == "__main__":
    unittest.main()
