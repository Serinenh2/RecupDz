"""
Enterprise Pipeline — public API delegating to ConversationOrchestrator.

    User → ConversationOrchestrator → AgentOrchestrator → Hermes / Tools → Response

This is the public API. ConversationOrchestrator handles conversation
lifecycle, memory, and context. AgentOrchestrator handles the AI workflow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EnterprisePipeline:
    """Public API for the enterprise AI pipeline.

    Delegates to ConversationOrchestrator for conversation lifecycle,
    which in turn delegates to AgentOrchestrator for the AI workflow.
    """

    def __init__(self, container: Any) -> None:
        self._c = container
        self._conversation_orchestrator = None

    @property
    def _conv_orch(self):
        if self._conversation_orchestrator is None:
            self._conversation_orchestrator = self._c.conversation_orchestrator
        return self._conversation_orchestrator

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
        """Process a user message through the agent workflow.

        Returns: {"success", "message", "data", "meta", "followups"}
        """
        return self._conv_orch.handle(
            message=message,
            user_id=user_id,
            conversation_id=conversation_id,
            contexte_supp=contexte_supp,
        )
