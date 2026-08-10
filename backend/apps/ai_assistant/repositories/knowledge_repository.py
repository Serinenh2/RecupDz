"""
Knowledge Base Repository — access to regulations, FAQs, guides.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class KnowledgeBaseRepository(BaseRepository):
    """Repository for KnowledgeBase model."""

    model_name = "ai_assistant.KnowledgeBase"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(titre__icontains=query) |
            Q(contenu__icontains=query) |
            Q(reference_reglementaire__icontains=query)
        ).filter(est_active=True)
        return self._to_list(qs[:limit])

    def filter_by_category(self, categorie: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(categorie=categorie, est_active=True)
        return self._to_list(qs[:limit])

    def get_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        try:
            instance = self._get_model().objects.get(reference_reglementaire=reference, est_active=True)
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
