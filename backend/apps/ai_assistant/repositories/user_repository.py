"""
User Repository — access to user accounts and authentication.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    """Repository for User model (accounts.User)."""

    model_name = "accounts.User"

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        try:
            instance = self._get_model().objects.get(username=username)
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            instance = self._get_model().objects.get(email=email)
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def filter_by_role(self, role: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(role=role)
        return self._to_list(qs[:limit])

    def filter_by_wilaya(self, wilaya: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(wilaya=wilaya)
        return self._to_list(qs[:limit])

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )
        return self._to_list(qs[:limit])

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
