"""
Bon Livraison Repository — access to delivery notes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class BonLivraisonRepository(BaseRepository):
    """Repository for BonLivraison model."""

    model_name = "bl.BonLivraison"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(numero__icontains=query) |
            Q(ref_client__icontains=query) |
            Q(client_nom__icontains=query)
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

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
