"""
Repository Layer — abstracts Django ORM access.

Every repository follows the same interface:
    - get(id) → Optional[Dict]
    - list(**filters) → List[Dict]
    - create(data) → Dict
    - update(id, data) → Optional[Dict]
    - delete(id) → bool
    - count(**filters) → int
    - exists(**filters) → bool

All methods return plain dicts (not model instances).
Tools NEVER import or use Django models directly.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base Repository
# ---------------------------------------------------------------------------

class BaseRepository(ABC):
    """Abstract base repository. All repos inherit from this."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Dotted model path, e.g. 'nomenclature.Nomenclature'."""
        ...

    def _get_model(self):
        """Lazy-import and return the Django model class."""
        from django.apps import apps
        return apps.get_model(self.model_name)

    def _to_dict(self, instance) -> Dict[str, Any]:
        """Convert a model instance to a plain dict."""
        if instance is None:
            return {}
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if hasattr(value, "isoformat"):
                data[field.name] = value.isoformat()
            elif hasattr(value, "pk"):
                data[field.name] = value.pk
            else:
                data[field.name] = value
        return data

    def _to_dict_list(self, queryset) -> List[Dict[str, Any]]:
        """Convert a queryset to a list of dicts."""
        return [self._to_dict(obj) for obj in queryset]

    # -- Standard CRUD --

    def get(self, pk: Any) -> Optional[Dict[str, Any]]:
        try:
            instance = self._get_model().objects.get(pk=pk)
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def list(self, limit: int = 20, offset: int = 0, **filters) -> List[Dict[str, Any]]:
        qs = self._get_model().objects.all()
        for key, value in filters.items():
            if value is not None and value != "":
                qs = qs.filter(**{key: value})
        return self._to_dict_list(qs[offset:offset + limit])

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        instance = self._get_model().objects.create(**data)
        return self._to_dict(instance)

    def update(self, pk: Any, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            instance = self._get_model().objects.get(pk=pk)
            for key, value in data.items():
                setattr(instance, key, value)
            instance.save()
            return self._to_dict(instance)
        except self._get_model().DoesNotExist:
            return None

    def delete(self, pk: Any) -> bool:
        try:
            self._get_model().objects.get(pk=pk).delete()
            return True
        except self._get_model().DoesNotExist:
            return False

    def count(self, **filters) -> int:
        qs = self._get_model().objects.all()
        for key, value in filters.items():
            if value is not None and value != "":
                qs = qs.filter(**{key: value})
        return qs.count()

    def exists(self, **filters) -> bool:
        return self.count(**filters) > 0

    def first(self, **filters) -> Optional[Dict[str, Any]]:
        qs = self._get_model().objects.all()
        for key, value in filters.items():
            if value is not None and value != "":
                qs = qs.filter(**{key: value})
        instance = qs.first()
        return self._to_dict(instance) if instance else None
