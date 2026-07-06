from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from .serializers import UserSerializer
from .permissions import IsSuperAdmin
from .models import AuditLog

User = get_user_model()


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


class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source='content_type.app_label', read_only=True)
    model_name = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'app_label', 'model_name']


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


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def roles_list(request):
    groups = Group.objects.prefetch_related('permissions__content_type').all()
    return Response(RoleSerializer(groups, many=True).data)


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def roles_detail(request, pk):
    try:
        group = Group.objects.prefetch_related('permissions__content_type').get(pk=pk)
    except Group.DoesNotExist:
        return Response({'error': 'Rôle introuvable'}, status=404)
    return Response(RoleSerializer(group).data)


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

    group_name = {
        'SUPERADMIN': 'super_administrateur',
        'ADMIN': 'administrateur',
        'RESPONSABLE_COLLECTE': 'responsable_collecte',
        'AGENT_COLLECTE': 'agent_collecte',
        'RESPONSABLE_DECHARGE': 'responsable_decharge',
        'OBSERVATEUR': 'observateur',
    }.get(role_name)

    user.groups.clear()
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)

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



