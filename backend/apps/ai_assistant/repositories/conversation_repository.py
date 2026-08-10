"""
Conversation Repository — persistence for AIConversation model.

All Django ORM access for AIConversation lives HERE, not in services or managers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ConversationRepository(BaseRepository):
    """Repository for AIConversation model (ai_assistant.AIConversation)."""

    model_name = "ai_assistant.AIConversation"

    def get_by_user(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversations for a user, ordered by most recent."""
        qs = self._get_model().objects.filter(user_id=user_id).order_by(
            "-updated_at", "-created_at"
        )
        return self._to_dict_list(qs[:limit])

    def get_by_contexte(self, user_id: int, contexte: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get conversations filtered by contexte."""
        qs = self._get_model().objects.filter(
            user_id=user_id, contexte=contexte
        ).order_by("-updated_at")
        return self._to_dict_list(qs[:limit])

    def get_active(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently active conversations."""
        qs = self._get_model().objects.filter(user_id=user_id).order_by(
            "-last_message_at"
        )
        return self._to_dict_list(qs[:limit])

    def create_conversation(
        self,
        user_id: int,
        titre: str,
        contexte: str = "GENERAL",
        entite_id: str = "",
    ) -> Dict[str, Any]:
        """Create a new conversation."""
        instance = self._get_model().objects.create(
            user_id=user_id,
            titre=titre,
            contexte=contexte,
            entite_id=entite_id,
        )
        return self._to_dict(instance)

    def update_last_message(self, pk: Any) -> Optional[Dict[str, Any]]:
        """Update last_message_at to now."""
        from django.utils import timezone

        try:
            instance = self._get_model().objects.get(pk=pk)
            instance.last_message_at = timezone.now()
            instance.save(update_fields=["last_message_at", "updated_at"])
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def _to_dict_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
