from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_superuser or request.user.has_role('SUPERADMIN')
        )


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.has_role('SUPERADMIN', 'ADMIN')
        )


class IsResponsableCollecte(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.has_role_or_above('RESPONSABLE_COLLECTE')
        )


class IsAgentCollecte(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.has_role_or_above('AGENT_COLLECTE')
        )


class IsResponsableDecharge(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.has_role('SUPERADMIN', 'ADMIN', 'RESPONSABLE_DECHARGE')
        )


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in ('GET', 'HEAD', 'OPTIONS')


class ModulePermission(BasePermission):
    """Checks user has the required permission for the ViewSet's model.

    ViewSet must define `module_label` attribute, e.g. `module_label = 'recuperateurs'`.
    Permission action is derived from the HTTP method:
        GET/HEAD/OPTIONS → view
        POST → add
        PUT/PATCH → change
        DELETE → delete
    """
    METHOD_ACTION_MAP = {
        'GET':     'view',
        'HEAD':    'view',
        'OPTIONS': 'view',
        'POST':    'add',
        'PUT':     'change',
        'PATCH':   'change',
        'DELETE':  'delete',
    }

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or user.has_role('SUPERADMIN'):
            return True

        module = getattr(view, 'module_label', None)
        if not module:
            return True

        model = getattr(view, 'queryset', None)
        model_name = model.model.__name__.lower() if model is not None else None
        if not model_name:
            return True

        action = self.METHOD_ACTION_MAP.get(request.method, 'view')
        perm = f"{module}.{action}_{model_name}"

        return user.has_perm(perm)
