"""
AI Gateway — connects Django views to the core AI agent.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.config import AIConfig
from apps.ai_assistant.core.router_agent import RouterAgent, RouteDecision, Intent, RoutingAction
from apps.ai_assistant.services.ollama_service import OllamaService
from apps.ai_assistant.services.chat_service import ChatService

logger = logging.getLogger(__name__)


class AIGateway:
    """Main gateway for AI assistant interactions."""

    def __init__(self) -> None:
        self._router: Optional[RouterAgent] = None
        self._ollama: Optional[OllamaService] = None
        self._initialized = False

    def _initialize(self) -> None:
        if self._initialized:
            return

        config = AIConfig.from_env()
        self._ollama = OllamaService(config.ollama)
        self._chat = ChatService(self._ollama)

        def llm_classify(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
            result = self._ollama.chat_simple(
                user_prompt,
                system_prompt=system_prompt,
                json_mode=True,
            )
            return {"text": result.content}

        self._router = RouterAgent(llm_classify=llm_classify)
        self._initialized = True

    def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a chat message and return response."""
        self._initialize()

        conversation_id = (context or {}).get("conversation_id", "")
        user_id = (context or {}).get("user_id", "")

        start = time.monotonic()

        decision = self._router.route(
            message,
            conversation_id=conversation_id or uuid.uuid4().hex,
            user_id=user_id or "",
        )

        elapsed = (time.monotonic() - start) * 1000

        response_text = decision.fallback_message or decision.clarification_question or ""
        if not response_text:
            response_text = decision.reasoning or "I received your message."

        return {
            "success": decision.action.value != RoutingAction.FALLBACK.value or bool(response_text),
            "response": response_text,
            "action": decision.action.value,
            "intent": decision.intent.value if decision.intent else None,
            "confidence": decision.confidence,
            "tool": decision.tool_name,
            "execution_time_ms": round(elapsed, 1),
            "context": {
                "conversation_id": conversation_id or "",
                "entities": decision.entities,
            },
        }


class GatewayManager:
    """Manages gateway instances."""

    _instance: Optional[AIGateway] = None

    @classmethod
    def get_gateway(cls) -> AIGateway:
        if cls._instance is None:
            cls._instance = AIGateway()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
