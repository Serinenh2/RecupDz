"""
Administration Repository — access to environmental administration offices.

Bridges to: administration.AdministrationEnvironnement
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class AdministrationRepository(BaseRepository):
    """Repository for AdministrationEnvironnement model."""

    model_name = "administration.AdministrationEnvironnement"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(denomination__icontains=query) |
            Q(wilaya__icontains=query) |
            Q(commune__icontains=query) |
            Q(nom_directeur__icontains=query) |
            Q(email__icontains=query)
        )
        return self._to_list(qs[:limit])

    def filter_by_type(self, type_admin: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(type_administration=type_admin)
        return self._to_list(qs[:limit])

    def filter_by_wilaya(self, wilaya: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(wilaya=wilaya)
        return self._to_list(qs[:limit])

    def filter_by_status(self, statut: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(statut=statut)
        return self._to_list(qs[:limit])

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
