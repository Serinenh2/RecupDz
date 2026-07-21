"""
Integration Tests — ReasoningOrchestrator.

Tests the real chain: AIReasoningPolicy → DecisionEngine → DecisionProposal.
Real components (no mocks) with a minimal mock container for DecisionEngine.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from apps.ai_assistant.enterprise.reasoning_orchestrator import ReasoningOrchestrator
from apps.ai_assistant.enterprise.reasoning_policy import AIReasoningPolicy
from apps.ai_assistant.enterprise.decision_engine import DecisionEngine
from apps.ai_assistant.enterprise.tool_planner import DecisionProposal, ToolPlanner


# ── Minimal container for DecisionEngine ───────────────────────────────


class _MockContainer:
    """Minimal container for DecisionEngine (provides search strategy)."""

    def __init__(self):
        self._search = MagicMock()

    @property
    def search_engine(self):
        return self._search


# ── Integration: AIReasoningPolicy Only ───────────────────────────────


class TestIntegrationReasoningPolicyOnly(unittest.TestCase):
    """Real AIReasoningPolicy → ReasoningOrchestrator (no DecisionEngine)."""

    def setUp(self):
        self.roc = ReasoningOrchestrator(
            reasoning_policy=AIReasoningPolicy(),
            decision_engine=None,
        )

    def test_greeting(self):
        proposal = self.roc.reason("bonjour")
        self.assertIsInstance(proposal, DecisionProposal)
        self.assertIn(proposal.tool, ("greeting", "none"))

    def test_waste_code(self):
        proposal = self.roc.reason("code 01.01.01")
        self.assertIsInstance(proposal, DecisionProposal)
        self.assertTrue(proposal.has_tool or proposal.tool == "none")

    def test_bsd_number(self):
        proposal = self.roc.reason("BSD-20241234")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_nomenclature(self):
        proposal = self.roc.reason("nomenclature des dechets")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_trace_has_reasoning_policy(self):
        proposal = self.roc.reason("test")
        self.assertIn("ReasoningPolicy", proposal.reasoning)

    def test_confidence_populated(self):
        proposal = self.roc.reason("code 01.01.01")
        self.assertGreaterEqual(proposal.confidence, 0.0)

    def test_with_context(self):
        proposal = self.roc.reason("test", context={"user_id": "u1"})
        self.assertIsInstance(proposal, DecisionProposal)


# ── Integration: DecisionEngine Only ──────────────────────────────────


class TestIntegrationDecisionEngineOnly(unittest.TestCase):
    """Real DecisionEngine → ReasoningOrchestrator (no AIReasoningPolicy)."""

    def setUp(self):
        self.roc = ReasoningOrchestrator(
            reasoning_policy=None,
            decision_engine=DecisionEngine(container=_MockContainer()),
        )

    def test_greeting(self):
        proposal = self.roc.reason("bonjour")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_waste_code(self):
        proposal = self.roc.reason("code 01.01.01")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_bsd_number(self):
        proposal = self.roc.reason("BSD-20241234")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_trace_has_decision_engine(self):
        proposal = self.roc.reason("test")
        self.assertIn("DecisionEngine", proposal.reasoning)

    def test_confidence_populated(self):
        proposal = self.roc.reason("code 01.01.01")
        self.assertGreaterEqual(proposal.confidence, 0.0)


# ── Integration: Both Components ──────────────────────────────────────


class TestIntegrationBothComponents(unittest.TestCase):
    """Real AIReasoningPolicy + DecisionEngine → DecisionProposal."""

    def setUp(self):
        self.roc = ReasoningOrchestrator(
            reasoning_policy=AIReasoningPolicy(),
            decision_engine=DecisionEngine(container=_MockContainer()),
        )

    def test_greeting(self):
        proposal = self.roc.reason("bonjour")
        self.assertIsInstance(proposal, DecisionProposal)
        self.assertIn(proposal.tool, ("greeting", "none"))

    def test_waste_code(self):
        proposal = self.roc.reason("code 01.01.01")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_bsd_number(self):
        proposal = self.roc.reason("BSD-20241234")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_trace_has_both(self):
        proposal = self.roc.reason("code 01.01.01")
        self.assertIn("ReasoningPolicy", proposal.reasoning)
        self.assertIn("DecisionEngine", proposal.reasoning)

    def test_reasoning_trace_not_empty(self):
        proposal = self.roc.reason("test")
        self.assertTrue(len(proposal.reasoning) > 0)

    def test_with_context(self):
        proposal = self.roc.reason("test", context={"user_id": "u1"})
        self.assertIsInstance(proposal, DecisionProposal)

    def test_empty_message(self):
        proposal = self.roc.reason("")
        self.assertIsInstance(proposal, DecisionProposal)


# ── Integration: DecisionProposal → ToolPlanner ───────────────────────


class TestIntegrationProposalFeedsToolPlanner(unittest.TestCase):
    """DecisionProposal from ReasoningOrchestrator feeds into ToolPlanner."""

    def setUp(self):
        self.roc = ReasoningOrchestrator(
            reasoning_policy=AIReasoningPolicy(),
            decision_engine=DecisionEngine(container=_MockContainer()),
        )
        self.planner = ToolPlanner()

    def test_proposal_feeds_planner(self):
        proposal = self.roc.reason("code 01.01.01")
        plan = self.planner.plan(proposal)
        self.assertIsNotNone(plan)
        self.assertIsInstance(plan.tool_count, int)

    def test_greeting_proposal_feeds_planner(self):
        proposal = self.roc.reason("bonjour")
        plan = self.planner.plan(proposal)
        self.assertIsNotNone(plan)

    def test_no_tool_proposal_feeds_planner(self):
        proposal = self.roc.reason("xyzzy random")
        plan = self.planner.plan(proposal)
        self.assertIsNotNone(plan)


# ── Integration: reason_with_trace ────────────────────────────────────


class TestIntegrationReasonWithTrace(unittest.TestCase):
    """reason_with_trace returns all three objects with real components."""

    def setUp(self):
        self.roc = ReasoningOrchestrator(
            reasoning_policy=AIReasoningPolicy(),
            decision_engine=DecisionEngine(container=_MockContainer()),
        )

    def test_returns_three_tuple(self):
        result = self.roc.reason_with_trace("code 01.01.01")
        self.assertEqual(len(result), 3)

    def test_proposal_is_decision_proposal(self):
        proposal, _, _ = self.roc.reason_with_trace("test")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_reasoning_is_reasoning_result(self):
        _, reasoning, _ = self.roc.reason_with_trace("test")
        from apps.ai_assistant.enterprise.reasoning_policy import ReasoningResult
        self.assertIsInstance(reasoning, ReasoningResult)

    def test_decision_is_decision_result(self):
        _, _, decision = self.roc.reason_with_trace("test")
        from apps.ai_assistant.enterprise.decision_engine import DecisionResult
        self.assertIsInstance(decision, DecisionResult)


# ── Integration: Container DI ─────────────────────────────────────────


class TestIntegrationContainerDI(unittest.TestCase):
    """Container wires ReasoningOrchestrator correctly."""

    def test_container_creates_reasoning_orchestrator(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        roc = c.reasoning_orchestrator
        self.assertIsInstance(roc, ReasoningOrchestrator)
        self.assertTrue(roc.has_reasoning_policy)
        self.assertTrue(roc.has_decision_engine)

    def test_container_returns_same_instance(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        r1 = c.reasoning_orchestrator
        r2 = c.reasoning_orchestrator
        self.assertIs(r1, r2)

    def test_container_reasoning_orchestrator_works(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        roc = c.reasoning_orchestrator
        proposal = roc.reason("bonjour")
        self.assertIsInstance(proposal, DecisionProposal)


if __name__ == "__main__":
    unittest.main()
