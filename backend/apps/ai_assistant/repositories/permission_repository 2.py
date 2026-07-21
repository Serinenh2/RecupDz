"""
Permission Repository — RBAC roles, groups, and user permission queries.

All Django ORM access for auth models lives HERE, not in tools.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from apps.ai_assistant.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PermissionRepository(BaseRepository):
    """Repository for Django auth models (Group, User permissions)."""

    model_name = "auth.Group"

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def list_groups(self) -> List[Dict[str, Any]]:
        """Return all groups with permission count and user count."""
        from django.contrib.auth.models import Group

        results = []
        for group in Group.objects.prefetch_related("permissions").order_by("name"):
            results.append({
                "pk": group.pk,
                "name": group.name,
                "permission_count": group.permissions.count(),
                "user_count": group.user_set.count(),
            })
        return results

    def get_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """Return a single group by pk with full permissions list."""
        from django.contrib.auth.models import Group

        try:
            group = Group.objects.prefetch_related("permissions__content_type").get(pk=group_id)
        except Group.DoesNotExist:
            return None

        permissions = []
        for perm in group.permissions.select_related("content_type").order_by(
            "content_type__app_label", "codename"
        ):
            permissions.append({
                "codename": perm.codename,
                "app_label": perm.content_type.app_label,
                "model": perm.content_type.model,
                "display": f"{perm.content_type.app_label}.{perm.codename}",
            })

        return {
            "pk": group.pk,
            "name": group.name,
            "permissions": permissions,
            "permission_count": len(permissions),
            "user_count": group.user_set.count(),
        }

    def get_group_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a group by name (tries lowercase then original)."""
        from django.contrib.auth.models import Group

        group = None
        for try_name in [name.lower(), name]:
            try:
                group = Group.objects.prefetch_related("permissions__content_type").get(name=try_name)
                break
            except Group.DoesNotExist:
                continue

        if group is None:
            return None

        permissions = []
        for perm in group.permissions.select_related("content_type").order_by(
            "content_type__app_label", "codename"
        ):
            permissions.append({
                "codename": perm.codename,
                "app_label": perm.content_type.app_label,
                "model": perm.content_type.model,
                "display": f"{perm.content_type.app_label}.{perm.codename}",
            })

        return {
            "pk": group.pk,
            "name": group.name,
            "permissions": permissions,
            "permission_count": len(permissions),
            "user_count": group.user_set.count(),
        }

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Return a user by pk with group memberships."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.prefetch_related("groups").get(pk=user_id)
        except User.DoesNotExist:
            return None

        return {
            "pk": user.pk,
            "username": user.username,
            "role": getattr(user, "role", ""),
            "groups": [g.name for g in user.groups.all()],
        }

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Return a user by username with group memberships."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.prefetch_related("groups").get(username=username)
        except User.DoesNotExist:
            return None

        return {
            "pk": user.pk,
            "username": user.username,
            "role": getattr(user, "role", ""),
            "groups": [g.name for g in user.groups.all()],
        }

    def list_users(self) -> List[Dict[str, Any]]:
        """Return all users with group memberships."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        results = []
        for user in User.objects.prefetch_related("groups").order_by("username"):
            results.append({
                "pk": user.pk,
                "username": user.username,
                "role": getattr(user, "role", ""),
                "groups": [g.name for g in user.groups.all()],
            })
        return results

    # ------------------------------------------------------------------
    # Permission Resolution
    # ------------------------------------------------------------------

    def get_user_permissions(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Return all permissions for a user (group + direct).
        Returns None if user not found.
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.prefetch_related(
                "groups__permissions__content_type",
                "user_permissions__content_type",
            ).get(pk=user_id)
        except User.DoesNotExist:
            return None

        group_perms = set()
        for group in user.groups.all():
            for perm in group.permissions.all():
                group_perms.add(f"{perm.content_type.app_label}.{perm.codename}")

        direct_perms = set()
        for perm in user.user_permissions.all():
            direct_perms.add(f"{perm.content_type.app_label}.{perm.codename}")

        all_perms = sorted(group_perms | direct_perms)

        return {
            "pk": user.pk,
            "username": user.username,
            "role": getattr(user, "role", ""),
            "groups": [g.name for g in user.groups.all()],
            "permissions": all_perms,
            "permissions_direct": sorted(direct_perms),
            "permissions_via_group": sorted(group_perms),
            "permission_count": len(all_perms),
        }

    def check_user_permission(self, user_id: int, permission: str) -> Optional[Dict[str, Any]]:
        """
        Check if a user has a specific permission.
        Returns None if user not found, or dict with 'autorise' bool.
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

        return {
            "username": user.username,
            "permission": permission,
            "autorise": user.has_perm(permission),
        }
