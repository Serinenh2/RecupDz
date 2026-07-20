"""
Conversation Manager — orchestration layer for conversations.

Responsibilities:
    - Coordinate ConversationService (business logic) and OllamaService (LLM)
    - Handle Ollama availability, errors, and fallbacks
    - Manage summarization flow (calls Ollama for summarization)

Does NOT contain business logic or Django ORM access.
Uses ConversationService for prompt/history building.
Uses OllamaService for LLM communication.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from apps.ai_assistant.services.ollama_service import (
    OllamaConnectionError,
    OllamaError,
    OllamaService,
    OllamaTimeoutError,
)
from apps.ai_assistant.services.conversation_service import (
    ConversationService,
    SUMMARIZE_SYSTEM,
)

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Orchestrates conversation flow between service and LLM.

    Flow per request:
        1. Build system prompt via ConversationService
        2. Build history via ConversationService (sliding window)
        3. If history needs summarization → call Ollama to summarize
        4. Assemble final prompt via ConversationService
        5. Call Ollama to generate response
        6. Return response, or None on failure (fallback to rule-based)

    Usage:
        manager = ConversationManager()
        response = manager.generate(message, conversation)
        if response is None:
            response = rule_based_fallback(message, conversation)
    """

    def __init__(
        self,
        ollama: Optional[OllamaService] = None,
        service: Optional[ConversationService] = None,
    ) -> None:
        self._ollama = ollama or OllamaService()
        self._service = service or ConversationService()

    @property
    def service(self) -> ConversationService:
        return self._service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        message: str,
        conversation: Any,
        contexte_supp: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate a response using Ollama.

        Returns the assistant reply as a string, or None if Ollama is
        unavailable (caller should fall back to rule-based).
        """
        if not self._ollama.is_available():
            logger.warning("Ollama unavailable — falling back to rule-based")
            return None

        try:
            # Step 1: Build system prompt (business logic)
            system_prompt = self._service.build_system_prompt(conversation)

            # Step 2: Build history with sliding window (business logic)
            history_result = self._service.build_history(conversation)

            # Step 3: Handle summarization if needed (orchestration)
            if isinstance(history_result, tuple):
                older, recent = history_result
                summary = self._summarize(older)
                history = self._service.format_history_with_summary(
                    older, recent, summary
                )
            else:
                history = history_result

            # Step 4: Log request
            total_msgs = len(history) + 1
            logger.info(
                "Ollama request: ctx=%s, history=%d msgs (incl. summary)",
                getattr(conversation, "contexte", None) or "default",
                total_msgs,
            )

            # Step 5: Call Ollama (orchestration)
            reply = self._ollama.chat(
                message=message,
                history=history,
                system_prompt=system_prompt,
            )

            if not reply or not reply.strip():
                logger.warning("Ollama returned empty response")
                return None

            logger.info("Ollama response: %d chars", len(reply))
            return reply.strip()

        except OllamaConnectionError:
            logger.warning("Ollama connection failed — falling back")
            return None
        except OllamaTimeoutError:
            logger.warning("Ollama timed out — falling back")
            return None
        except OllamaError as exc:
            logger.error("Ollama error: %s — falling back", exc)
            return None
        except Exception as exc:
            logger.exception("Unexpected error in ConversationManager: %s", exc)
            return None

    def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        return self._ollama.is_available()

    def health(self) -> Dict[str, Any]:
        """Detailed health check."""
        return self._ollama.health()

    # ------------------------------------------------------------------
    # Summarization (orchestration — calls Ollama)
    # ------------------------------------------------------------------

    def _summarize(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Summarize older conversation messages via Ollama."""
        if not messages:
            return None

        conversation_text = self._service.build_summarization_text(messages)

        try:
            reply = self._ollama.chat(
                message=conversation_text,
                history=[],
                system_prompt=SUMMARIZE_SYSTEM,
            )
            return reply.strip() if reply else None

        except Exception as exc:
            logger.warning("Summarization failed: %s", exc)
            return None
