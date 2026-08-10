"""
Conversation History Repository — access to AI conversation messages.

All Django ORM access for AIMessage lives HERE, not in services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ConversationHistoryRepository(BaseRepository):
    """Repository for AIMessage model (ai_assistant.AIMessage)."""

    model_name = "ai_assistant.AIMessage"

    def get_messages(self, conversation_id: int) -> List[Dict[str, Any]]:
        """Get all messages for a conversation, ordered by creation time."""
        qs = self._get_model().objects.filter(
            conversation_id=conversation_id
        ).order_by("created_at")
        return self._to_dict_list(qs)

    def get_messages_for_prompt(self, conversation_id: int) -> List[Dict[str, str]]:
        """
        Get messages formatted for LLM prompt building.
        Returns list of {role, content} dicts.
        """
        qs = self._get_model().objects.filter(
            conversation_id=conversation_id
        ).order_by("created_at")

        result = []
        for msg in qs:
            role = "user" if msg.role == "USER" else "assistant"
            content = (msg.message or "").strip()
            if content:
                result.append({"role": role, "content": content})
        return result

    def get_last_user_message(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get the last user message for a conversation."""
        msg = self._get_model().objects.filter(
            conversation_id=conversation_id,
            role="USER",
        ).order_by("-created_at").first()
        return self._to_dict(msg) if msg else None

    def get_message_count(self, conversation_id: int) -> int:
        """Count messages in a conversation."""
        return self._get_model().objects.filter(
            conversation_id=conversation_id
        ).count()
