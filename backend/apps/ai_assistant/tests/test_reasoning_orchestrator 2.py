"""
Unit Tests — ReasoningOrchestrator.

Tests the chain: AIReasoningPolicy → DecisionEngine → DecisionProposal.
Both components are mocked. Zero LLM calls. Zero Django imports.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from apps.ai_assistant.enterprise.reasoning_orchestrator import ReasoningOrchestrator
from apps.ai_assistant.enterprise.tool_planner import DecisionProposal


# ── Helpers ────────────────────────────────────────────────────────────


def _make_reasoning_result(
    *,
    tool: str = "none",
    action: str = "",
    parameters: dict | None = None,
    confidence: float = 0.5,
    lang: str = "fr",
    intent: str = "unknown",
    needs_clarification: bool = False,
    clarification_reason: str = "",
    missing: list | None = None,
) -> MagicMock:
    """Build a mock ReasoningResult."""
    r = MagicMock()
    r.message = "test message"
    r.confidence.overall = confidence
    r.confidence.passes_threshold = confidence >= 0.8
    r.language.language = lang
    r.intent.intent = intent
    r.tool_decision.tool = tool
    r.tool_decision.action = action
    r.tool_decision.parameters = parameters or {}
    r.clarification.needed = needs_clarification
    r.clarification.reason = clarification_reason
    r.parameter_report.missing = missing or []
    r.parameter_report.valid = not missing
    r.business_knowledge.must_search_business_first = True
    return r


def _make_decision_result(
    *,
    tool_name: str = "none",
    action: str = "",
    parameters: dict | None = None,
    confidence: float = 0.5,
    needs_clarification: bool = False,
    clarification_question: str = "",
    elapsed_ms: float = 10.0,
) -> MagicMock:
    """Build a mock DecisionResult."""
    d = MagicMock()
    d.tool_name = tool_name
    d.action = action
    d.parameters = parameters or {}
    d.confidence = confidence
    d.needs_clarification = needs_clarification
    d.clarification_question = clarification_question
    d.elapsed_ms = elapsed_ms
    return d


# ── Tests: Basic Chain ────────────────────────────────────────────────


class TestReasonBasicChain(unittest.TestCase):
    """reason() calls both components and merges into DecisionProposal."""

    def setUp(self):
        self.rp = MagicMock()
        self.de = MagicMock()
        self.roc = ReasoningOrchestrator(
            reasoning_policy=self.rp,
            decision_engine=self.de,
        )

    def test_calls_reasoning_policy(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result()
        self.roc.reason("bonjour")
        self.rp.analyze.assert_called_once_with("bonjour", context=None)

    def test_calls_decision_engine(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result()
        self.roc.reason("code 01.01.01")
        self.de.decide.assert_called_once_with("code 01.01.01", context=None)

    def test_returns_decision_proposal(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result()
        result = self.roc.reason("test")
        self.assertIsInstance(result, DecisionProposal)

    def test_context_passed_to_both(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result()
        ctx = {"user_id": "u1"}
        self.roc.reason("test", context=ctx)
        self.rp.analyze.assert_called_once_with("test", context=ctx)
        self.de.decide.assert_called_once_with("test", context=ctx)


# ── Tests: Field Merging ──────────────────────────────────────────────


class TestReasonFieldMerging(unittest.TestCase):
    """DecisionProposal fields are correctly merged from both components."""

    def setUp(self):
        self.rp = MagicMock()
        self.de = MagicMock()
        self.roc = ReasoningOrchestrator(
            reasoning_policy=self.rp,
            decision_engine=self.de,
        )

    def test_tool_from_decision_engine(self):
        self.rp.analyze.return_value = _make_reasoning_result(tool="waste_tool")
        self.de.decide.return_value = _make_decision_result(tool_name="nomenclature_tool")
        result = self.roc.reason("test")
        self.assertEqual(result.tool, "nomenclature_tool")

    def test_action_from_decision_engine(self):
        self.rp.analyze.return_value = _make_reasoning_result(action="search")
        self.de.decide.return_value = _make_decision_result(action="list")
        result = self.roc.reason("test")
        self.assertEqual(result.action, "list")

    def test_parameters_from_decision_engine(self):
        self.rp.analyze.return_value = _make_reasoning_result(
            parameters={"code": "15.01.01"}
        )
        self.de.decide.return_value = _make_decision_result(
            parameters={"code": "01.01.01", "year": 2024}
        )
        result = self.roc.reason("test")
        self.assertEqual(result.parameters, {"code": "01.01.01", "year": 2024})

    def test_confidence_from_decision_engine(self):
        self.rp.analyze.return_value = _make_reasoning_result(confidence=0.9)
        self.de.decide.return_value = _make_decision_result(confidence=0.95)
        result = self.roc.reason("test")
        self.assertAlmostEqual(result.confidence, 0.95)

    def test_missing_params_from_reasoning_policy(self):
        self.rp.analyze.return_value = _make_reasoning_result(
            missing=[{"name": "code", "type": "str"}]
        )
        self.de.decide.return_value = _make_decision_result()
        result = self.roc.reason("test")
        self.assertEqual(len(result.missing), 1)
        self.assertEqual(result.missing[0]["name"], "code")

    def test_message_preserved(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result()
        result = self.roc.reason("code 01.01.01")
        self.assertEqual(result.message, "code 01.01.01")

    def test_reasoning_trace_built(self):
        self.rp.analyze.return_value = _make_reasoning_result(
            tool="waste_tool", lang="fr", intent="waste_search"
        )
        self.de.decide.return_value = _make_decision_result(
            tool_name="waste_tool", confidence=0.92
        )
        result = self.roc.reason("dechets dangereux")
        self.assertIn("ReasoningPolicy", result.reasoning)
        self.assertIn("DecisionEngine", result.reasoning)
        self.assertIn("waste_tool", result.reasoning)


# ── Tests: Fallback — ReasoningPolicy Only ────────────────────────────


class TestReasonWithReasoningPolicyOnly(unittest.TestCase):
    """When only AIReasoningPolicy is available."""

    def setUp(self):
        self.rp = MagicMock()
        self.roc = ReasoningOrchestrator(
            reasoning_policy=self.rp,
            decision_engine=None,
        )

    def test_uses_reasoning_tool_decision(self):
        self.rp.analyze.return_value = _make_reasoning_result(
            tool="nomenclature_tool", action="search"
        )
        result = self.roc.reason("code 01.01.01")
        self.assertEqual(result.tool, "nomenclature_tool")
        self.assertEqual(result.action, "search")

    def test_uses_reasoning_confidence(self):
        self.rp.analyze.return_value = _make_reasoning_result(confidence=0.85)
        result = self.roc.reason("test")
        self.assertAlmostEqual(result.confidence, 0.85)

    def test_has_decision_engine_false(self):
        self.assertFalse(self.roc.has_decision_engine)

    def test_has_reasoning_policy_true(self):
        self.assertTrue(self.roc.has_reasoning_policy)

    def test_is_available_true(self):
        self.assertTrue(self.roc.is_available)


# ── Tests: Fallback — DecisionEngine Only ─────────────────────────────


class TestReasonWithDecisionEngineOnly(unittest.TestCase):
    """When only DecisionEngine is available."""

    def setUp(self):
        self.de = MagicMock()
        self.roc = ReasoningOrchestrator(
            reasoning_policy=None,
            decision_engine=self.de,
        )

    def test_uses_decision_result(self):
        self.de.decide.return_value = _make_decision_result(
            tool_name="bsd_tool", action="search"
        )
        result = self.roc.reason("BSD-20241234")
        self.assertEqual(result.tool, "bsd_tool")

    def test_has_reasoning_policy_false(self):
        self.assertFalse(self.roc.has_reasoning_policy)

    def test_has_decision_engine_true(self):
        self.assertTrue(self.roc.has_decision_engine)

    def test_missing_params_empty(self):
        self.de.decide.return_value = _make_decision_result()
        result = self.roc.reason("test")
        self.assertEqual(result.missing, [])


# ── Tests: Fallback — Neither Available ───────────────────────────────


class TestReasonWithNoComponents(unittest.TestCase):
    """When neither component is available."""

    def setUp(self):
        self.roc = ReasoningOrchestrator(
            reasoning_policy=None,
            decision_engine=None,
        )

    def test_returns_none_proposal(self):
        result = self.roc.reason("test")
        self.assertIsInstance(result, DecisionProposal)

    def test_tool_is_none(self):
        result = self.roc.reason("test")
        self.assertEqual(result.tool, "none")

    def test_confidence_is_zero(self):
        result = self.roc.reason("test")
        self.assertEqual(result.confidence, 0.0)

    def test_reasoning_trace_unavailable(self):
        result = self.roc.reason("test")
        self.assertIn("No reasoning components", result.reasoning)

    def test_is_available_false(self):
        self.assertFalse(self.roc.is_available)


# ── Tests: Exception Handling ─────────────────────────────────────────


class TestReasonExceptionHandling(unittest.TestCase):
    """Graceful fallback when components raise exceptions."""

    def setUp(self):
        self.rp = MagicMock()
        self.de = MagicMock()
        self.roc = ReasoningOrchestrator(
            reasoning_policy=self.rp,
            decision_engine=self.de,
        )

    def test_reasoning_exception_returns_none(self):
        self.rp.analyze.side_effect = RuntimeError("reasoning failed")
        self.de.decide.return_value = _make_decision_result(tool_name="bsd_tool")
        result = self.roc.reason("test")
        self.assertEqual(result.tool, "bsd_tool")

    def test_decision_exception_returns_none(self):
        self.rp.analyze.return_value = _make_reasoning_result(tool="waste_tool")
        self.de.decide.side_effect = RuntimeError("decision failed")
        result = self.roc.reason("test")
        self.assertEqual(result.tool, "waste_tool")

    def test_both_exceptions_returns_default(self):
        self.rp.analyze.side_effect = RuntimeError("rp failed")
        self.de.decide.side_effect = RuntimeError("de failed")
        result = self.roc.reason("test")
        self.assertEqual(result.tool, "none")
        self.assertEqual(result.confidence, 0.0)


# ── Tests: reason_with_trace ──────────────────────────────────────────


class TestReasonWithTrace(unittest.TestCase):
    """reason_with_trace() returns all three objects."""

    def setUp(self):
        self.rp = MagicMock()
        self.de = MagicMock()
        self.roc = ReasoningOrchestrator(
            reasoning_policy=self.rp,
            decision_engine=self.de,
        )

    def test_returns_three_tuple(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result()
        result = self.roc.reason_with_trace("test")
        self.assertEqual(len(result), 3)

    def test_first_is_proposal(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result()
        proposal, _, _ = self.roc.reason_with_trace("test")
        self.assertIsInstance(proposal, DecisionProposal)

    def test_second_is_reasoning_result(self):
        mock_rr = _make_reasoning_result()
        self.rp.analyze.return_value = mock_rr
        self.de.decide.return_value = _make_decision_result()
        _, reasoning, _ = self.roc.reason_with_trace("test")
        self.assertEqual(reasoning, mock_rr)

    def test_third_is_decision_result(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        mock_dr = _make_decision_result()
        self.de.decide.return_value = mock_dr
        _, _, decision = self.roc.reason_with_trace("test")
        self.assertEqual(decision, mock_dr)

    def test_trace_none_when_component_missing(self):
        roc = ReasoningOrchestrator(reasoning_policy=None, decision_engine=None)
        proposal, reasoning, decision = roc.reason_with_trace("test")
        self.assertIsNone(reasoning)
        self.assertIsNone(decision)
        self.assertEqual(proposal.tool, "none")


# ── Tests: Edge Cases ─────────────────────────────────────────────────


class TestReasonEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def setUp(self):
        self.rp = MagicMock()
        self.de = MagicMock()
        self.roc = ReasoningOrchestrator(
            reasoning_policy=self.rp,
            decision_engine=self.de,
        )

    def test_empty_message(self):
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result()
        result = self.roc.reason("")
        self.assertIsInstance(result, DecisionProposal)
        self.assertEqual(result.message, "")

    def test_de_tool_none_rp_tool_waste(self):
        """When DE says 'none' but RP found a tool, prefer RP."""
        self.rp.analyze.return_value = _make_reasoning_result(
            tool="waste_tool", action="search"
        )
        self.de.decide.return_value = _make_decision_result(tool_name="none")
        result = self.roc.reason("dechets")
        self.assertEqual(result.tool, "waste_tool")

    def test_de_confidence_zero_rp_confidence_high(self):
        """When DE confidence is 0, use RP confidence."""
        self.rp.analyze.return_value = _make_reasoning_result(confidence=0.88)
        self.de.decide.return_value = _make_decision_result(confidence=0.0)
        result = self.roc.reason("test")
        self.assertAlmostEqual(result.confidence, 0.88)

    def test_both_have_tools_prefer_de(self):
        """When both have tools, DecisionEngine wins."""
        self.rp.analyze.return_value = _make_reasoning_result(tool="bsd_tool")
        self.de.decide.return_value = _make_decision_result(
            tool_name="nomenclature_tool"
        )
        result = self.roc.reason("test")
        self.assertEqual(result.tool, "nomenclature_tool")

    def test_clarification_from_reasoning_policy(self):
        """Clarification needed from RP is reflected in trace."""
        self.rp.analyze.return_value = _make_reasoning_result(
            needs_clarification=True,
            clarification_reason="ambiguous_reference",
        )
        self.de.decide.return_value = _make_decision_result()
        result = self.roc.reason("01.01.01")
        self.assertIn("Clarification", result.reasoning)
        self.assertIn("ambiguous_reference", result.reasoning)

    def test_clarification_from_decision_engine(self):
        """Clarification needed from DE is reflected in trace."""
        self.rp.analyze.return_value = _make_reasoning_result()
        self.de.decide.return_value = _make_decision_result(
            needs_clarification=True,
            clarification_question="Voulez-vous dire X ou Y?",
        )
        result = self.roc.reason("test")
        self.assertIn("Voulez-vous dire X ou Y?", result.reasoning)


# ── Tests: Default Constructor ────────────────────────────────────────


class TestReasoningOrchestratorDefaults(unittest.TestCase):
    """Default constructor creates a usable instance."""

    def test_default_constructor(self):
        roc = ReasoningOrchestrator()
        self.assertFalse(roc.has_reasoning_policy)
        self.assertFalse(roc.has_decision_engine)
        self.assertFalse(roc.is_available)

    def test_default_reason_returns_proposal(self):
        roc = ReasoningOrchestrator()
        result = roc.reason("test")
        self.assertIsInstance(result, DecisionProposal)
        self.assertEqual(result.tool, "none")


if __name__ == "__main__":
    unittest.main()
