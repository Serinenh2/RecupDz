"""
Inspection Repository — access to inspection records.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class InspectionRepository(BaseRepository):
    """Repository for Inspection model."""

    model_name = "inspections.Inspection"

    def filter_by_recuperateur(self, recuperateur_id: Any, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(recuperateur_id=recuperateur_id)
        return self._to_list(qs[:limit])

    def filter_by_resultat(self, resultat: str, limit: int = 50) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(resultat=resultat)
        return self._to_list(qs[:limit])

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
