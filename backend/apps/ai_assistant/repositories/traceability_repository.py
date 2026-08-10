"""
Traceability Repository — access to waste recovery operations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class TraceabilityRepository(BaseRepository):
    """Repository for Traceability model."""

    model_name = "traceability.Traceability"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(numero__icontains=query) |
            Q(code_dechet__icontains=query) |
            Q(designation_dechet__icontains=query) |
            Q(bon_livraison__icontains=query)
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

    def filter_by_waste_code(self, code_dechet: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(code_dechet=code_dechet)
        return self._to_list(qs[:limit])

    def filter_by_date_range(self, date_from: str, date_to: str, limit: int = 100) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(
            date_recuperation__gte=date_from,
            date_recuperation__lte=date_to
        )
        return self._to_list(qs[:limit])

    def sum_quantities(self, recuperateur_id: Any = None, date_from: str = None, date_to: str = None) -> float:
        from django.db.models import Sum
        qs = self._get_model().objects.all()
        if recuperateur_id:
            qs = qs.filter(recuperateur_id=recuperateur_id)
        if date_from:
            qs = qs.filter(date_recuperation__gte=date_from)
        if date_to:
            qs = qs.filter(date_recuperation__lte=date_to)
        result = qs.aggregate(total=Sum("quantite"))
        return float(result["total"] or 0)

    def count_by_status(self, recuperateur_id: Any = None) -> Dict[str, int]:
        from django.db.models import Count
        qs = self._get_model().objects.all()
        if recuperateur_id:
            qs = qs.filter(recuperateur_id=recuperateur_id)
        return dict(qs.values_list("statut").annotate(count=Count("id")).values_list("statut", "count"))

    def count_by_waste_class(self, recuperateur_id: Any = None) -> Dict[str, int]:
        from django.db.models import Count
        qs = self._get_model().objects.all()
        if recuperateur_id:
            qs = qs.filter(recuperateur_id=recuperateur_id)
        return dict(qs.values_list("classe_dechet").annotate(count=Count("id")).values_list("classe_dechet", "count"))

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
