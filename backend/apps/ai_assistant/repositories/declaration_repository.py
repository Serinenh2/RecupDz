"""
Declaration Repository — access to waste declarations (DSD).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class DeclarationRepository(BaseRepository):
    """Repository for Declaration model."""

    model_name = "declarations.Declaration"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(denomination__icontains=query) |
            Q(code_dechet__icontains=query) |
            Q(denomination_dechet__icontains=query)
        )
        return self._to_list(qs[:limit])

    def filter_by_recuperateur(self, recuperateur_id: Any, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(recuperateur_id=recuperateur_id)
        return self._to_list(qs[:limit])

    def filter_by_status(self, statut: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(statut=statut)
        return self._to_list(qs[:limit])

    def filter_by_year(self, annee: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(annee=annee)
        return self._to_list(qs[:limit])

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
