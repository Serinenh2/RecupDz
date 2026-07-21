"""
Reasoning Orchestrator — chains AIReasoningPolicy + DecisionEngine → DecisionProposal.

Workflow:
    User Message
        ↓
    AIReasoningPolicy.analyze() → ReasoningResult
        ↓
    DecisionEngine.decide()     → DecisionResult
        ↓
    Merge → DecisionProposal

Responsibilities:
    1. Run AIReasoningPolicy (deterministic reasoning, 11 steps)
    2. Run DecisionEngine (structured decision, 10 steps)
    3. Merge both results into a single DecisionProposal
    4. Provide full audit trail in proposal.reasoning

Constraints:
    - Zero tool execution
    - Zero repository access
    - Zero Django coupling
    - DecisionEngine stays independent (not coupled to this class)
    - All dependencies injected via constructor (DI)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from apps.ai_assistant.enterprise.reasoning_policy import (
    AIReasoningPolicy,
    ReasoningResult,
)
from apps.ai_assistant.enterprise.decision_engine import (
    DecisionEngine,
    DecisionResult,
)
from apps.ai_assistant.enterprise.tool_planner import DecisionProposal

logger = logging.getLogger(__name__)


class ReasoningOrchestrator:
    """Chains AIReasoningPolicy + DecisionEngine into a single DecisionProposal.

    Pure reasoning pipeline — no tool execution, no repos, no Django.
    Both components are injected via constructor and remain independent.
    """

    def __init__(
        self,
        *,
        reasoning_policy: Optional[AIReasoningPolicy] = None,
        decision_engine: Optional[DecisionEngine] = None,
    ) -> None:
        self._reasoning_policy = reasoning_policy
        self._decision_engine = decision_engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reason(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DecisionProposal:
        """Run the full reasoning chain and return a DecisionProposal.

        Steps:
            1. AIReasoningPolicy.analyze(message) → ReasoningResult
            2. DecisionEngine.decide(message)     → DecisionResult
            3. Merge → DecisionProposal

        Returns a DecisionProposal ready for ToolPlanner.
        Never executes tools.
        """
        reasoning = self._run_reasoning(message, context)
        decision = self._run_decision(message, context)
        return self._build_proposal(reasoning, decision, message)

    def reason_with_trace(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[DecisionProposal, Optional[ReasoningResult], Optional[DecisionResult]]:
        """Same as reason() but also returns raw ReasoningResult + DecisionResult.

        Useful for debugging, audit trails, and integration tests.
        """
        reasoning = self._run_reasoning(message, context)
        decision = self._run_decision(message, context)
        proposal = self._build_proposal(reasoning, decision, message)
        return proposal, reasoning, decision

    @property
    def has_reasoning_policy(self) -> bool:
        return self._reasoning_policy is not None

    @property
    def has_decision_engine(self) -> bool:
        return self._decision_engine is not None

    @property
    def is_available(self) -> bool:
        return self._reasoning_policy is not None or self._decision_engine is not None

    # ------------------------------------------------------------------
    # Internal — component runners (with graceful fallback)
    # ------------------------------------------------------------------

    def _run_reasoning(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ReasoningResult]:
        """Run AIReasoningPolicy.analyze(). Returns None if unavailable."""
        if self._reasoning_policy is None:
            return None
        try:
            return self._reasoning_policy.analyze(message, context=context)
        except Exception as exc:
            logger.debug("AIReasoningPolicy.analyze() failed: %s", exc)
            return None

    def _run_decision(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[DecisionResult]:
        """Run DecisionEngine.decide(). Returns None if unavailable."""
        if self._decision_engine is None:
            return None
        try:
            return self._decision_engine.decide(message, context=context)
        except Exception as exc:
            logger.debug("DecisionEngine.decide() failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal — proposal construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_proposal(
        reasoning: Optional[ReasoningResult],
        decision: Optional[DecisionResult],
        message: str,
    ) -> DecisionProposal:
        """Merge ReasoningResult + DecisionResult into a DecisionProposal.

        Priority rules:
            - tool/action/parameters → DecisionEngine (authoritative)
            - confidence → DecisionEngine (weighted, higher granularity)
            - missing params → AIReasoningPolicy (parameter_report)
            - reasoning trace → combined from both components
        """
        if reasoning is None and decision is None:
            return DecisionProposal(
                message=message,
                tool="none",
                confidence=0.0,
                reasoning="No reasoning components available",
            )

        tool = "none"
        action = ""
        parameters: Dict[str, Any] = {}
        confidence = 0.0
        missing: List[Dict[str, str]] = []

        if decision is not None:
            tool = decision.tool_name or "none"
            action = decision.action or ""
            parameters = dict(decision.parameters) if decision.parameters else {}
            confidence = decision.confidence

        if reasoning is not None:
            missing = list(reasoning.parameter_report.missing) if reasoning.parameter_report.missing else []
            if tool == "none" and reasoning.tool_decision.tool != "none":
                tool = reasoning.tool_decision.tool
                action = action or reasoning.tool_decision.action
                if not parameters:
                    parameters = dict(reasoning.tool_decision.parameters)
            if confidence == 0.0 and reasoning.confidence.overall > 0.0:
                confidence = reasoning.confidence.overall

        trace = ReasoningOrchestrator._build_trace(reasoning, decision)

        return DecisionProposal(
            message=message,
            tool=tool,
            action=action,
            parameters=parameters,
            confidence=confidence,
            reasoning=trace,
            missing=missing,
        )

    @staticmethod
    def _build_trace(
        reasoning: Optional[ReasoningResult],
        decision: Optional[DecisionResult],
    ) -> str:
        """Build a combined reasoning trace from both components."""
        parts: List[str] = []

        if reasoning is not None:
            lang = reasoning.language.language if reasoning.language else "unknown"
            intent = reasoning.intent.intent if reasoning.intent else "unknown"
            parts.append(
                f"ReasoningPolicy: lang={lang}, intent={intent}, "
                f"confidence={reasoning.confidence.overall:.2f}, "
                f"tool={reasoning.tool_decision.tool}"
            )
            if reasoning.clarification.needed:
                parts.append(f"Clarification: {reasoning.clarification.reason}")

        if decision is not None:
            parts.append(
                f"DecisionEngine: tool={decision.tool_name}, "
                f"confidence={decision.confidence:.2f}, "
                f"elapsed={decision.elapsed_ms:.0f}ms"
            )
            if decision.needs_clarification:
                q = decision.clarification_question or ""
                parts.append(f"Clarification: {q}")

        return " | ".join(parts) if parts else "No reasoning available"
