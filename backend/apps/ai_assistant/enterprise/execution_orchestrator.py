"""
Execution Orchestrator — Reasoning → Knowledge → Planning → Execution pipeline.

Workflow:
    User Message
        ↓
    ReasoningOrchestrator.reason()    → DecisionProposal
        ↓
    KnowledgeSearchEngine.search()    → SearchResults       (enterprise knowledge)
        ↓
    ToolPlanner.plan()               → ExecutionPlan
        ↓
    ToolExecutorV2.execute_plan()     → ToolExecutionResult

Responsibilities:
    1. Run ReasoningOrchestrator (AIReasoningPolicy + DecisionEngine → DecisionProposal)
    2. Run KnowledgeSearchEngine (query → ranked enterprise knowledge)
    3. Run ToolPlanner (DecisionProposal → ExecutionPlan)
    4. Run ToolExecutorV2 (ExecutionPlan → ToolExecutionResult)
    5. Validate at each stage — never expose exceptions
    6. Provide full audit trace when requested

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
    """Chains ReasoningOrchestrator → KnowledgeSearch → ToolPlanner → ToolExecutorV2.

    The single entry point for the full reasoning-to-execution pipeline.
    Never exposes Python exceptions — all errors return safe fallback results.
    """

    def __init__(
        self,
        *,
        reasoning_orchestrator: Any = None,
        knowledge_search: Any = None,
        tool_planner: Optional[ToolPlanner] = None,
        tool_executor_v2: Optional[ToolExecutorV2] = None,
        safety_layer: Any = None,
    ) -> None:
        self._reasoning_orchestrator = reasoning_orchestrator
        self._knowledge_search = knowledge_search
        self._tool_planner = tool_planner
        self._tool_executor_v2 = tool_executor_v2
        self._safety_layer = safety_layer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        message: str,
        context: Optional[Any] = None,
    ) -> ToolExecutionResult:
        """Run the full pipeline: safety → reason → knowledge → plan → execute → validate.

        Returns a ToolExecutionResult — never raises.
        """
        try:
            input_check = self._check_input(message, context)
            if input_check is not None:
                return input_check

            proposal = self._reason(message, context)
            if proposal is None:
                return self._empty_result("Raisonnement indisponible.")

            knowledge_results = self._search_knowledge(message)

            if not proposal.has_tool:
                return self._empty_result("Aucun outil nécessaire.")

            plan = self._plan(proposal)
            if plan is None:
                return self._empty_result("Planification indisponible.")

            if plan.is_empty:
                return self._empty_result("Aucun outil à exécuter.")

            result = self._execute_plan(plan, context)

            if knowledge_results is not None and knowledge_results.has_results:
                ctx_str = knowledge_results.to_context_string()
                if ctx_str:
                    result = self._inject_knowledge(result, ctx_str)

            return self._check_output(result)
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
        Optional[Any],
    ]:
        """Same as execute() but also returns DecisionProposal, ExecutionPlan, and SearchResults.

        The 4th element is the KnowledgeSearchEngine SearchResults (or None).
        Useful for debugging, audit trails, and integration tests.
        """
        proposal: Optional[DecisionProposal] = None
        plan: Optional[ExecutionPlan] = None
        knowledge_results: Optional[Any] = None

        try:
            input_check = self._check_input(message, context)
            if input_check is not None:
                return (input_check, proposal, plan, knowledge_results)

            proposal = self._reason(message, context)
            if proposal is None:
                return (
                    self._empty_result("Raisonnement indisponible."),
                    proposal,
                    plan,
                    knowledge_results,
                )

            knowledge_results = self._search_knowledge(message)

            if not proposal.has_tool:
                return (
                    self._empty_result("Aucun outil nécessaire."),
                    proposal,
                    plan,
                    knowledge_results,
                )

            plan = self._plan(proposal)
            if plan is None:
                return (
                    self._empty_result("Planification indisponible."),
                    proposal,
                    plan,
                    knowledge_results,
                )

            if plan.is_empty:
                return (
                    self._empty_result("Aucun outil à exécuter."),
                    proposal,
                    plan,
                    knowledge_results,
                )

            result = self._execute_plan(plan, context)

            if knowledge_results is not None and knowledge_results.has_results:
                ctx_str = knowledge_results.to_context_string()
                if ctx_str:
                    result = self._inject_knowledge(result, ctx_str)

            result = self._check_output(result)
            return result, proposal, plan, knowledge_results
        except Exception as exc:
            logger.debug("ExecutionOrchestrator trace failed: %s", exc)
            return (
                self._error_result("Erreur interne du pipeline."),
                proposal,
                plan,
                knowledge_results,
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def has_reasoning_orchestrator(self) -> bool:
        return self._reasoning_orchestrator is not None

    @property
    def has_knowledge_search(self) -> bool:
        return self._knowledge_search is not None

    @property
    def has_tool_planner(self) -> bool:
        return self._tool_planner is not None

    @property
    def has_safety_layer(self) -> bool:
        return self._safety_layer is not None

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

    def _check_input(
        self,
        message: str,
        context: Optional[Any],
    ) -> Optional[ToolExecutionResult]:
        """Stage 0: AISafetyLayer.check_input() → block if unsafe.

        Returns None if safe, or a failed ToolExecutionResult if blocked.
        """
        if self._safety_layer is None:
            return None
        try:
            user_id = getattr(context, "user_id", None) if context else None
            conversation_id = getattr(context, "conversation_id", None) if context else None
            result = self._safety_layer.check_input(
                text=message,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            if result.blocked:
                logger.info("Input blocked by safety: %s", result.violations)
                return self._error_result(result.block_response())
            return None
        except Exception as exc:
            logger.debug("Safety input check failed: %s", exc)
            return self._error_result("Erreur de vérification de sécurité.")

    def _check_output(
        self,
        result: ToolExecutionResult,
    ) -> ToolExecutionResult:
        """Stage 5: AISafetyLayer.check_output() → sanitize if needed.

        Validates tool output and sanitizes PII/confidential content.
        Returns the (possibly sanitized) result — never raises.
        """
        if self._safety_layer is None:
            return result
        try:
            output_text = "\n".join(result.messages) if result.messages else ""
            if not output_text:
                return result
            check = self._safety_layer.check_output(text=output_text)
            if check.blocked:
                sanitized = self._safety_layer.sanitize_output(text=output_text)
                logger.info("Output sanitized by safety: %s", check.violations)
                return ToolExecutionResult(
                    success=result.success,
                    step_results=list(result.step_results),
                    total_elapsed_ms=result.total_elapsed_ms,
                    steps_succeeded=result.steps_succeeded,
                    steps_failed=result.steps_failed,
                    messages=[sanitized] if sanitized else ["Contenu filtré par la couche de sécurité."],
                )
            return result
        except Exception as exc:
            logger.debug("Safety output check failed: %s", exc)
            return result

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

    def _search_knowledge(self, message: str) -> Optional[Any]:
        """Stage 2: KnowledgeSearchEngine → SearchResults."""
        if self._knowledge_search is None:
            return None
        try:
            from apps.ai_assistant.enterprise.knowledge_search import SearchMode
            return self._knowledge_search.search(
                message, mode=SearchMode.HYBRID, limit=5,
            )
        except Exception as exc:
            logger.debug("KnowledgeSearchEngine failed: %s", exc)
            return None

    def _plan(
        self,
        proposal: DecisionProposal,
    ) -> Optional[ExecutionPlan]:
        """Stage 3: ToolPlanner → ExecutionPlan."""
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
        """Stage 4: ToolExecutorV2 → ToolExecutionResult."""
        if self._tool_executor_v2 is None:
            return self._error_result("Exécuteur indisponible.")
        try:
            return self._tool_executor_v2.execute_plan(plan, context=context)
        except Exception as exc:
            logger.debug("ToolExecutorV2 failed: %s", exc)
            return self._error_result("Exécution échouée.")

    # ------------------------------------------------------------------
    # Internal — Knowledge injection
    # ------------------------------------------------------------------

    @staticmethod
    def _inject_knowledge(
        result: ToolExecutionResult,
        knowledge_context: str,
    ) -> ToolExecutionResult:
        """Prepend enterprise knowledge context to the result messages.

        This makes the knowledge available for downstream PromptBuilder
        without modifying the ToolExecutionResult type.
        """
        prefix = "[CONNAISSANCES_ENTREPRISE]"
        existing = list(result.messages)
        existing.insert(0, f"{prefix}\n{knowledge_context}")
        return ToolExecutionResult(
            success=result.success,
            step_results=list(result.step_results),
            total_elapsed_ms=result.total_elapsed_ms,
            steps_succeeded=result.steps_succeeded,
            steps_failed=result.steps_failed,
            messages=existing,
        )

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
