import json
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count
from apps.accounts.permissions import ModulePermission
from apps.accounts.models import AuditLog
from .models import Traceability
from .serializers import TraceabilitySerializer

class TraceabilityViewSet(viewsets.ModelViewSet):
    module_label     = 'traceability'
    permission_classes = [ModulePermission]
    queryset         = Traceability.objects.select_related(
        'recuperateur','generateur','transporteur','valorisateur','eliminateur'
    ).all()
    serializer_class = TraceabilitySerializer
    filter_backends  = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields    = ['numero','code_dechet','designation_dechet',
                        'bon_livraison','bon_commande','chauffeur','immatriculation']
    filterset_fields = ['recuperateur','statut','classe_dechet','destination_type']
    ordering_fields  = ['date_recuperation','created_at','quantite']

    def _audit(self, action_name, instance, details=None):
        AuditLog.objects.create(
            user=self.request.user if self.request.user.is_authenticated else None,
            action=action_name,
            model_name='Traceability',
            object_id=str(instance.id),
            details=details or {},
            ip_address=getattr(self.request, '_audit_ip', None),
        )

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        self._audit('CREATE', instance, {'numero': instance.numero})

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit('UPDATE', instance, {'numero': instance.numero})

    def perform_destroy(self, instance):
        # Conserve un instantané du dossier dans le journal d'audit avant
        # la suppression definitive (regle de tracabilite/historique du projet).
        snapshot = json.loads(JSONRenderer().render(TraceabilitySerializer(instance).data))
        self._audit('DELETE', instance, {'snapshot': snapshot})
        instance.delete()

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        return Response({
            'total':             qs.count(),
            'quantite_totale':   qs.aggregate(t=Sum('quantite'))['t'] or 0,
            'par_statut':        list(qs.values('statut').annotate(count=Count('id'))),
            'par_destination':   list(qs.values('destination_type').annotate(count=Count('id'))),
            'par_classe':        list(qs.values('classe_dechet').annotate(count=Count('id'))),
        })
