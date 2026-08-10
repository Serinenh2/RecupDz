"""
Recuperateur Repository — access to waste recovery operators.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class RecuperateurRepository(BaseRepository):
    """Repository for Recuperateur model."""

    model_name = "recuperateurs.Recuperateur"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(nom_raison_sociale__icontains=query) |
            Q(nom_commercial__icontains=query) |
            Q(numero_id__icontains=query) |
            Q(nif__icontains=query) |
            Q(registre_commerce__icontains=query)
        )
        return self._to_list(qs[:limit])

    def get_by_numero(self, numero_id: str) -> Optional[Dict[str, Any]]:
        try:
            instance = self._get_model().objects.get(numero_id=numero_id)
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def filter_by_status(self, statut: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(statut=statut)
        return self._to_list(qs[:limit])

    def filter_by_wilaya(self, wilaya: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(wilaya=wilaya)
        return self._to_list(qs[:limit])

    def get_with_agrements(self, pk: Any) -> Optional[Dict[str, Any]]:
        data = self.get(pk)
        if data:
            instance = self._get_model().objects.get(pk=pk)
            data["agrements"] = self._to_list(instance.agrements.all())
        return data

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]


class AgrementRepository(BaseRepository):
    """Repository for AgrementRecuperateur model."""

    model_name = "recuperateurs.AgrementRecuperateur"

    def filter_by_recuperateur(self, recuperateur_id: Any) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(recuperateur_id=recuperateur_id)
        return self._to_list(qs)

    def filter_active(self, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(statut="ACTIF")
        return self._to_list(qs[:limit])

    def filter_expiring_soon(self, days: int = 60, limit: int = 50) -> List[Dict[str, Any]]:
        from datetime import date, timedelta
        cutoff = date.today() + timedelta(days=days)
        qs = self._get_model().objects.filter(
            statut="ACTIF",
            date_fin__lte=cutoff,
            date_fin__gte=date.today()
        )
        return self._to_list(qs[:limit])

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
