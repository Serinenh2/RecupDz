"""
BSD Repository — access to waste tracking documents.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class BSDRepository(BaseRepository):
    """Repository for BordereauSuiviDechet model."""

    model_name = "bsd.BordereauSuiviDechet"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(numero__icontains=query) |
            Q(code_dechet__icontains=query) |
            Q(designation__icontains=query) |
            Q(generateur_nom__icontains=query)
        )
        return self._to_list(qs[:limit])

    def get_by_numero(self, numero: str) -> Optional[Dict[str, Any]]:
        try:
            instance = self._get_model().objects.get(numero=numero)
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def filter_by_recuperateur(self, recuperateur_id: Any, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(recuperateur_id=recuperateur_id)
        return self._to_list(qs[:limit])

    def filter_by_status(self, statut: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(statut=statut)
        return self._to_list(qs[:limit])

    def count_by_status(self, recuperateur_id: Any = None) -> Dict[str, int]:
        from django.db.models import Count
        qs = self._get_model().objects.all()
        if recuperateur_id:
            qs = qs.filter(recuperateur_id=recuperateur_id)
        return dict(qs.values_list("statut").annotate(count=Count("id")).values_list("statut", "count"))

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
