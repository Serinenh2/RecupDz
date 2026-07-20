"""
Execution Orchestrator — Reasoning → Planning → Execution pipeline.

Workflow:
    User Message
        ↓
    ReasoningOrchestrator.reason() → DecisionProposal
        ↓
    ToolPlanner.plan()              → ExecutionPlan
        ↓
    ToolExecutorV2.execute_plan()   → ToolExecutionResult

Responsibilities:
    1. Run ReasoningOrchestrator (AIReasoningPolicy + DecisionEngine → DecisionProposal)
    2. Run ToolPlanner (DecisionProposal → ExecutionPlan)
    3. Run ToolExecutorV2 (ExecutionPlan → ToolExecutionResult)
    4. Validate at each stage — never expose exceptions
    5. Provide full audit trace when requested

Constraints:
    - Zero Django imports
    - Zero repository access
    - All dependencies injected via constructor (DI)
    - Never re-raises exceptions — always returns safe fallback
    - French error messages throughout
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from apps.ai_assistant.enterprise.tool_planner import (
    DecisionProposal,
    ExecutionPlan,
    ToolPlanner,
)
from apps.ai_assistant.enterprise.tool_executor_v2 import (
    ToolExecutionResult,
    ToolExecutorV2,
)

logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """Chains ReasoningOrchestrator → ToolPlanner → ToolExecutorV2.

    The single entry point for the full reasoning-to-execution pipeline.
    Never exposes Python exceptions — all errors return safe fallback results.
    """

    def __init__(
        self,
        *,
        reasoning_orchestrator: Any = None,
        tool_planner: Optional[ToolPlanner] = None,
        tool_executor_v2: Optional[ToolExecutorV2] = None,
    ) -> None:
        self._reasoning_orchestrator = reasoning_orchestrator
        self._tool_planner = tool_planner
        self._tool_executor_v2 = tool_executor_v2

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        message: str,
        context: Optional[Any] = None,
    ) -> ToolExecutionResult:
        """Run the full pipeline: reason → plan → execute.

        Returns a ToolExecutionResult — never raises.
        """
        try:
            proposal = self._reason(message, context)
            if proposal is None:
                return self._empty_result("Raisonnement indisponible.")

            if not proposal.has_tool:
                return self._empty_result("Aucun outil nécessaire.")

            plan = self._plan(proposal)
            if plan is None:
                return self._empty_result("Planification indisponible.")

            if plan.is_empty:
                return self._empty_result("Aucun outil à exécuter.")

            return self._execute_plan(plan, context)
        except Exception as exc:
            logger.debug("ExecutionOrchestrator failed: %s", exc)
            return self._error_result("Erreur interne du pipeline.")

    def execute_with_trace(
        self,
        message: str,
        context: Optional[Any] = None,
    ) -> Tuple[
        ToolExecutionResult,
        Optional[DecisionProposal],
        Optional[ExecutionPlan],
    ]:
        """Same as execute() but also returns the DecisionProposal and ExecutionPlan.

        Useful for debugging, audit trails, and integration tests.
        """
        proposal: Optional[DecisionProposal] = None
        plan: Optional[ExecutionPlan] = None

        try:
            proposal = self._reason(message, context)
            if proposal is None:
                return (
                    self._empty_result("Raisonnement indisponible."),
                    proposal,
                    plan,
                )

            if not proposal.has_tool:
                return (
                    self._empty_result("Aucun outil nécessaire."),
                    proposal,
                    plan,
                )

            plan = self._plan(proposal)
            if plan is None:
                return (
                    self._empty_result("Planification indisponible."),
                    proposal,
                    plan,
                )

            if plan.is_empty:
                return (
                    self._empty_result("Aucun outil à exécuter."),
                    proposal,
                    plan,
                )

            result = self._execute_plan(plan, context)
            return result, proposal, plan
        except Exception as exc:
            logger.debug("ExecutionOrchestrator trace failed: %s", exc)
            return (
                self._error_result("Erreur interne du pipeline."),
                proposal,
                plan,
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def has_reasoning_orchestrator(self) -> bool:
        return self._reasoning_orchestrator is not None

    @property
    def has_tool_planner(self) -> bool:
        return self._tool_planner is not None

    @property
    def has_tool_executor_v2(self) -> bool:
        return self._tool_executor_v2 is not None

    @property
    def is_available(self) -> bool:
        return (
            self.has_reasoning_orchestrator
            and self.has_tool_planner
            and self.has_tool_executor_v2
        )

    # ------------------------------------------------------------------
    # Internal — Pipeline stages
    # ------------------------------------------------------------------

    def _reason(
        self,
        message: str,
        context: Optional[Any],
    ) -> Optional[DecisionProposal]:
        """Stage 1: ReasoningOrchestrator → DecisionProposal."""
        if self._reasoning_orchestrator is None:
            return None
        try:
            return self._reasoning_orchestrator.reason(message, context=context)
        except Exception as exc:
            logger.debug("ReasoningOrchestrator failed: %s", exc)
            return None

    def _plan(
        self,
        proposal: DecisionProposal,
    ) -> Optional[ExecutionPlan]:
        """Stage 2: ToolPlanner → ExecutionPlan."""
        if self._tool_planner is None:
            return None
        try:
            return self._tool_planner.plan(proposal)
        except Exception as exc:
            logger.debug("ToolPlanner failed: %s", exc)
            return None

    def _execute_plan(
        self,
        plan: ExecutionPlan,
        context: Optional[Any],
    ) -> ToolExecutionResult:
        """Stage 3: ToolExecutorV2 → ToolExecutionResult."""
        if self._tool_executor_v2 is None:
            return self._error_result("Exécuteur indisponible.")
        try:
            return self._tool_executor_v2.execute_plan(plan, context=context)
        except Exception as exc:
            logger.debug("ToolExecutorV2 failed: %s", exc)
            return self._error_result("Exécution échouée.")

    # ------------------------------------------------------------------
    # Internal — Result builders
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result(message: str) -> ToolExecutionResult:
        """Build a successful empty result (no tool executed)."""
        return ToolExecutionResult(
            success=True,
            step_results=[],
            total_elapsed_ms=0.0,
            steps_succeeded=0,
            steps_failed=0,
            messages=[message],
        )

    @staticmethod
    def _error_result(message: str) -> ToolExecutionResult:
        """Build a failed result with a safe French error message."""
        return ToolExecutionResult(
            success=False,
            step_results=[],
            total_elapsed_ms=0.0,
            steps_succeeded=0,
            steps_failed=0,
            messages=[message],
        )
