"""
Archive Repository — access to archived documents.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class ArchiveRepository(BaseRepository):
    """Repository for Document (archive) model."""

    model_name = "archive.Document"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(titre__icontains=query) |
            Q(description__icontains=query) |
            Q(nom_original__icontains=query)
        )
        return self._to_list(qs[:limit])

    def filter_by_categorie(self, categorie: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(categorie=categorie)
        return self._to_list(qs[:limit])

    def filter_by_uploader(self, user_id: Any, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(uploaded_by_id=user_id)
        return self._to_list(qs[:limit])

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.order_by("-created_at")[:limit]
        return self._to_list(qs)

    def get_procedures(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get documents categorized as procedures, guides, or SOPs."""
        qs = self._get_model().objects.filter(
            categorie__in=["PROCEDURE", "GUIDE", "SOP", "MANUAL", "PROCÉDURE"]
        )[:limit]
        return self._to_list(qs)

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
