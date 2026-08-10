"""
Operateur Repository — access to external operators (generateurs, transporteurs, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class OperateurRepository(BaseRepository):
    """Repository for Operateur model."""

    model_name = "operateurs.Operateur"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(raison_sociale__icontains=query) |
            Q(nif__icontains=query) |
            Q(nis__icontains=query) |
            Q(registre_commerce__icontains=query)
        )
        return self._to_list(qs[:limit])

    def filter_by_type(self, type_operateur: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(type_operateur=type_operateur)
        return self._to_list(qs[:limit])

    def filter_by_recuperateur(self, recuperateur_id: Any, type_operateur: str = None) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(recuperateur_id=recuperateur_id)
        if type_operateur:
            qs = qs.filter(type_operateur=type_operateur)
        return self._to_list(qs)

    def filter_generateurs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.filter_by_type("GENERATEUR", limit)

    def filter_transporteurs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.filter_by_type("TRANSPORTEUR", limit)

    def filter_by_wilaya(self, wilaya: str, type_operateur: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(wilaya=wilaya)
        if type_operateur:
            qs = qs.filter(type_operateur=type_operateur)
        return self._to_list(qs[:limit])

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
