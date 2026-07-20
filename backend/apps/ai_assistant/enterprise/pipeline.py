"""
Enterprise Pipeline — delegates to AgentOrchestrator for the mandatory workflow.

    User → AgentOrchestrator → AI Router / Hermes → Tool → Repo → DB → Hermes → Response + Follow-ups

This is the public API. All workflow enforcement happens in AgentOrchestrator.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from apps.ai_assistant.core.interfaces import (
    Context,
    ExecutionPlan,
    FormattedResponse,
    Intent,
    Message,
    OutputFormat,
    ReasoningResult,
    Role,
    RouteResult,
    TaskStep,
    ToolResult,
)
from apps.ai_assistant.infrastructure.audit.audit import AuditAction
from apps.ai_assistant.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


class EnterprisePipeline:
    """
    Public API for the enterprise AI pipeline.

    Delegates to AgentOrchestrator for the mandatory 7-step workflow:
        1. Receive message
        2. Understand intent
        3. Select tool
        4. Execute tool → structured JSON
        5. Generate professional response
        6. Generate follow-up questions
        7. Return response + follow-ups
    """

    def __init__(self, container: Any) -> None:
        self._c = container
        self._orchestrator = None

    @property
    def _orch(self):
        if self._orchestrator is None:
            from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
            self._orchestrator = AgentOrchestrator(container=self._c)
        return self._orchestrator

    # ==================================================================
    # Main entry point
    # ==================================================================

    def handle(
        self,
        message: str,
        conversation: Any = None,
        user_id: str = "",
        conversation_id: str = "",
        contexte_supp: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the agent workflow.

        Returns: {"success", "message", "data", "meta", "followups"}
        """
        return self._orch.orchestrate(
            message=message,
            user_id=user_id,
            conversation_id=conversation_id,
            contexte_supp=contexte_supp,
        )
