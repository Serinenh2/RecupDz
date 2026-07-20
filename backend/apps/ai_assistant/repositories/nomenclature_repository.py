"""
Nomenclature Repository — access to waste classification codes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository


class NomenclatureRepository(BaseRepository):
    """Repository for Nomenclature model."""

    model_name = "nomenclature.Nomenclature"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search by code or designation."""
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(code__icontains=query) |
            Q(designation_fr__icontains=query) |
            Q(designation_ar__icontains=query)
        )
        return self._to_list(qs[:limit])

    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get exact match by code."""
        try:
            instance = self._get_model().objects.get(code=code)
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def list_children(self, parent_code: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List all nomenclature codes under a parent prefix.

        Hierarchy: "01" → "01.01" → "01.01.01"
        list_children("01")    → all codes starting with "01."
        list_children("01.01") → all codes starting with "01.01."
        """
        prefix = parent_code.rstrip(".")
        qs = self._get_model().objects.filter(
            code__startswith=f"{prefix}."
        ).order_by("code")
        return self._to_list(qs[:limit])

    def search_similar(self, term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find nomenclatures in the same family/subfamily as the matched code.

        1. Try exact code match → return siblings (same sous_famille).
        2. Fallback to keyword search → group by famille.
        """
        from django.db.models import Q

        # 1. If term looks like a code, find siblings
        if any(c.isdigit() for c in term):
            code = term.replace(" ", ".")
            try:
                match = self._get_model().objects.get(code=code)
                siblings = self._get_model().objects.filter(
                    sous_famille=match.sous_famille
                ).exclude(pk=match.pk).order_by("code")[:limit]
                return self._to_list(siblings)
            except self._get_model().DoesNotExist:
                pass

        # 2. Keyword search — find matches and return same-famille siblings
        qs = self._get_model().objects.filter(
            Q(designation_fr__icontains=term) |
            Q(code__icontains=term)
        )
        first = qs.first()
        if first:
            famille_hits = self._get_model().objects.filter(
                famille=first.famille
            ).order_by("code")[:limit]
            return self._to_list(famille_hits)

        # 3. Nothing found
        return []

    def filter_by_class(self, classe: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Filter by waste class (MA, I, S, SD)."""
        qs = self._get_model().objects.filter(classe=classe)
        return self._to_list(qs[:limit])

    def filter_dangerous(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all dangerous waste (SD or S class)."""
        qs = self._get_model().objects.filter(classe__in=["S", "SD"])
        return self._to_list(qs[:limit])

    def get_with_designations(self, pk: Any) -> Optional[Dict[str, Any]]:
        """Get nomenclature with its designations."""
        data = self.get(pk)
        if data:
            data["designations"] = self._to_list(
                self._get_model().objects.get(pk=pk).designations.all()
            )
        return data

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]


class DesignationDechetRepository(BaseRepository):
    """Repository for DesignationDechet model."""

    model_name = "nomenclature.DesignationDechet"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from django.db.models import Q
        qs = self._get_model().objects.filter(
            Q(designation__icontains=query) |
            Q(id_recup_dz__icontains=query) |
            Q(matiere__icontains=query)
        )
        return self._to_list(qs[:limit])

    def filter_by_nomenclature(self, nomenclature_id: Any) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.filter(nomenclature_id=nomenclature_id)
        return self._to_list(qs)

    def _to_list(self, queryset) -> List[Dict[str, Any]]:
        return [self._to_dict(obj) for obj in queryset]
