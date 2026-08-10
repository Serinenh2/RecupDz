from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from .serializers import UserSerializer
from .permissions import IsSuperAdmin
from .models import AuditLog

User = get_user_model()


# ── Helper: Sync User.role with Django Group membership ─────
ROLE_TO_GROUP = {
    'SUPERADMIN': 'super_administrateur',
    'ADMIN': 'administrateur',
    'RECUPERATEUR': 'recuperateur',
    'RESPONSABLE_COLLECTE': 'responsable_collecte',
    'AGENT_COLLECTE': 'agent_collecte',
    'RESPONSABLE_DECHARGE': 'responsable_decharge',
    'OBSERVATEUR': 'observateur',
}


def _assign_group_for_role(user):
    """Sync the Django Group membership to match the user's current role."""
    group_name = ROLE_TO_GROUP.get(user.role)
    user.groups.clear()
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)


class RoleSerializer(serializers.ModelSerializer):
    permissions_list = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions_list', 'user_count']

    def get_permissions_list(self, obj):
        return [
            f"{p.content_type.app_label}.{p.codename}"
            for p in obj.permissions.select_related('content_type').all()
        ]

    def get_user_count(self, obj):
        return obj.user_set.count()


PERMISSION_TRANSLATIONS = {
    'Can add': 'Peut ajouter',
    'Can change': 'Peut modifier',
    'Can delete': 'Peut supprimer',
    'Can view': 'Peut consulter',
}

class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source='content_type.app_label', read_only=True)
    model_name = serializers.CharField(source='content_type.model', read_only=True)
    name = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'app_label', 'model_name']

    def get_name(self, obj):
        """Traduit le nom de permission anglais → français."""
        _name = obj.name
        for en, fr in PERMISSION_TRANSLATIONS.items():
            if _name.startswith(en):
                return _name.replace(en, fr, 1)
        return _name


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def users_list(request):
    qs = User.objects.all().order_by('-date_joined')
    search = request.query_params.get('search')
    role = request.query_params.get('role')
    if search:
        qs = qs.filter(username__icontains=search) | qs.filter(email__icontains=search) | qs.filter(first_name__icontains=search) | qs.filter(last_name__icontains=search)
    if role:
        qs = qs.filter(role=role)
    page_size = int(request.query_params.get('page_size', 10))
    page = int(request.query_params.get('page', 1))
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    return Response({
        'count': paginator.count,
        'results': UserSerializer(page_obj, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def user_create(request):
    data = request.data.copy()
    password = data.pop('password', None)
    s = UserSerializer(data=data)
    if s.is_valid():
        user = s.save()
        if password:
            user.set_password(password)
            user.save()
        # Assign the Django group matching the user's role
        _assign_group_for_role(user)
        AuditLog.objects.create(
            user=request.user, action='CREATE', model_name='User',
            object_id=str(user.id), details={'username': user.username},
            ip_address=getattr(request, '_audit_ip', None),
        )
        return Response(UserSerializer(user).data, status=201)
    return Response(s.errors, status=400)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsSuperAdmin])
def user_detail(request, pk):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur introuvable'}, status=404)

    if request.method == 'GET':
        data = UserSerializer(user).data
        data['permissions'] = user.get_all_permissions_list()
        data['groups'] = list(user.groups.values_list('name', flat=True))
        return Response(data)

    if request.method == 'PATCH':
        old_role = user.role
        s = UserSerializer(user, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            # Sync group if role changed
            if user.role != old_role:
                _assign_group_for_role(user)
            AuditLog.objects.create(
                user=request.user, action='UPDATE', model_name='User',
                object_id=str(pk), details={'fields': list(request.data.keys())},
                ip_address=getattr(request, '_audit_ip', None),
            )
            return Response(UserSerializer(user).data)
        return Response(s.errors, status=400)

    if request.method == 'DELETE':
        if user.is_superuser:
            return Response({'error': 'Impossible de supprimer un superadmin'}, status=400)
        AuditLog.objects.create(
            user=request.user, action='DELETE', model_name='User',
            object_id=str(pk), details={'username': user.username},
            ip_address=getattr(request, '_audit_ip', None),
        )
        user.delete()
        return Response(status=204)


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def user_reset_password(request, pk):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur introuvable'}, status=404)
    new_password = request.data.get('new_password')
    if not new_password or len(new_password) < 8:
        return Response({'error': 'Le mot de passe doit contenir au moins 8 caractères'}, status=400)
    user.set_password(new_password)
    user.save()
    AuditLog.objects.create(
        user=request.user, action='UPDATE', model_name='User',
        object_id=str(pk), details={'action': 'reset_password'},
        ip_address=getattr(request, '_audit_ip', None),
    )
    return Response({'status': 'ok'})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == 'PATCH':
        s = UserSerializer(request.user, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=400)
    data = UserSerializer(request.user).data
    data['permissions'] = request.user.get_all_permissions_list()
    data['groups'] = list(request.user.groups.values_list('name', flat=True))
    return Response(data)


@api_view(['GET', 'POST'])
@permission_classes([IsSuperAdmin])
def roles_list(request):
    if request.method == 'POST':
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Le nom du rôle est requis'}, status=400)
        if Group.objects.filter(name=name).exists():
            return Response({'error': 'Un rôle avec ce nom existe déjà'}, status=400)
        group = Group.objects.create(name=name)
        AuditLog.objects.create(
            user=request.user, action='CREATE', model_name='Group',
            object_id=str(group.id), details={'name': name},
            ip_address=getattr(request, '_audit_ip', None),
        )
        return Response(RoleSerializer(group).data, status=201)
    groups = Group.objects.prefetch_related('permissions__content_type').all()
    return Response(RoleSerializer(groups, many=True).data)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsSuperAdmin])
def roles_detail(request, pk):
    try:
        group = Group.objects.prefetch_related('permissions__content_type').get(pk=pk)
    except Group.DoesNotExist:
        return Response({'error': 'Rôle introuvable'}, status=404)

    if request.method == 'GET':
        return Response(RoleSerializer(group).data)

    if request.method == 'PATCH':
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Le nom du rôle est requis'}, status=400)
        old_name = group.name
        group.name = name
        group.save()
        AuditLog.objects.create(
            user=request.user, action='UPDATE', model_name='Group',
            object_id=str(pk), details={'old_name': old_name, 'new_name': name},
            ip_address=getattr(request, '_audit_ip', None),
        )
        return Response(RoleSerializer(group).data)

    if request.method == 'DELETE':
        if group.user_set.exists():
            return Response({'error': 'Impossible de supprimer un rôle qui a des utilisateurs assignés'}, status=400)
        AuditLog.objects.create(
            user=request.user, action='DELETE', model_name='Group',
            object_id=str(pk), details={'name': group.name},
            ip_address=getattr(request, '_audit_ip', None),
        )
        group.delete()
        return Response(status=204)





@api_view(['PUT'])
@permission_classes([IsSuperAdmin])
def roles_update_permissions(request, pk):
    try:
        group = Group.objects.get(pk=pk)
    except Group.DoesNotExist:
        return Response({'error': 'Rôle introuvable'}, status=404)

    perm_ids = request.data.get('permissions', [])
    perms = Permission.objects.filter(id__in=perm_ids)
    group.permissions.set(perms)

    AuditLog.objects.create(
        user=request.user,
        action='UPDATE',
        model_name='Group',
        object_id=str(pk),
        details={'permissions_count': len(perm_ids)},
        ip_address=getattr(request, '_audit_ip', None),
    )

    return Response({'status': 'ok', 'permissions_count': len(perm_ids)})


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def permissions_list(request):
    perms = Permission.objects.select_related('content_type').all()
    app = request.query_params.get('app')
    if app:
        perms = perms.filter(content_type__app_label=app)
    return Response(PermissionSerializer(perms, many=True).data)


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def assign_role(request, user_id):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur introuvable'}, status=404)

    role_name = request.data.get('role')
    valid_roles = [c[0] for c in User.ROLE_CHOICES]
    if role_name not in valid_roles:
        return Response({'error': f'Rôle invalide. Valeurs acceptées : {valid_roles}'}, status=400)

    old_role = user.role
    user.role = role_name
    user.save()
    _assign_group_for_role(user)

    AuditLog.objects.create(
        user=request.user,
        action='ASSIGN_ROLE',
        model_name='User',
        object_id=str(user_id),
        details={'old_role': old_role, 'new_role': role_name},
        ip_address=getattr(request, '_audit_ip', None),
    )

    return Response({'status': 'ok', 'user': UserSerializer(user).data})


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def audit_log(request):
    qs = AuditLog.objects.select_related('user').all()
    limit = int(request.query_params.get('limit', 50))
    return Response([
        {
            'id': log.id,
            'user': log.user.username if log.user else None,
            'action': log.get_action_display(),
            'action_code': log.action,
            'model_name': log.model_name,
            'object_id': log.object_id,
            'details': log.details,
            'ip_address': log.ip_address,
            'timestamp': log.timestamp.isoformat(),
        }
        for log in qs[:limit]
    ])


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def mon_recuperateur(request):
    try:
        rec = request.user.recuperateur
    except Exception:
        return Response({'error': 'Aucune fiche recuperateur liee'}, status=404)
    if request.method == 'PATCH':
        from apps.recuperateurs.serializers import RecuperateurSerializer
        s = RecuperateurSerializer(rec, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=400)
    from apps.recuperateurs.serializers import RecuperateurSerializer
    return Response(RecuperateurSerializer(rec).data)



