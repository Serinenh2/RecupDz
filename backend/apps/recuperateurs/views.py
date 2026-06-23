from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from datetime import date, timedelta
from apps.accounts.permissions import ModulePermission
from .models import Recuperateur, AgrementRecuperateur
from .models_specialisation import CategorieSpecialisation
from .serializers import (
    RecuperateurSerializer, RecuperateurListSerializer, AgrementSerializer,
    CategorieSpecialisationSerializer,
)
from .alerts import get_all_alerts, check_droit_recuperation


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def specialisation_hierarchie(request):
    """
    Retourne la hiérarchie complète (Catégorie > SousCatégorie > Détail).
    Utile pour afficher toute la structure, en surlignant ce qui est
    coché pour le récupérateur connecté (voir mon-recuperateur pour ses IDs cochés).
    """
    categories = CategorieSpecialisation.objects.prefetch_related(
        'sous_categories__details'
    ).all()
    return Response(CategorieSpecialisationSerializer(categories, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verifier_droit(request):
    recuperateur_id = request.data.get('recuperateur_id')
    code_dechet     = request.data.get('code_dechet', '')
    classe_dechet   = request.data.get('classe_dechet', '')
    if not recuperateur_id or not code_dechet:
        return Response({'error': 'recuperateur_id et code_dechet requis'}, status=400)
    result = check_droit_recuperation(recuperateur_id, code_dechet, classe_dechet)
    return Response(result)


class AgrementViewSet(viewsets.ModelViewSet):
    module_label    = 'recuperateurs'
    queryset         = AgrementRecuperateur.objects.select_related('recuperateur').all()
    serializer_class = AgrementSerializer
    permission_classes = [ModulePermission]
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['recuperateur','type_agrement','statut','etendue_geo']
    search_fields    = ['numero_agrement','codes_dechets']

    @action(detail=False, methods=['get'])
    def alerts(self, request):
        today = date.today()
        soon  = today + timedelta(days=60)
        result = []
        for agr in AgrementRecuperateur.objects.filter(statut='ACTIF', date_fin__lt=today).select_related('recuperateur'):
            result.append({'type':'EXPIRE','severity':'critical',
                'message': f"Agrément {agr.numero_agrement} expiré — {agr.recuperateur.nom_raison_sociale}",
                'recuperateur_id': agr.recuperateur.id, 'agrement_id': agr.id})
        for agr in AgrementRecuperateur.objects.filter(statut='ACTIF', date_fin__gte=today, date_fin__lte=soon).select_related('recuperateur'):
            result.append({'type':'EXPIRING','severity':'warning',
                'message': f"Agrément expire dans {(agr.date_fin - today).days}j — {agr.recuperateur.nom_raison_sociale}",
                'recuperateur_id': agr.recuperateur.id, 'agrement_id': agr.id})
        return Response({'total': len(result), 'critical': sum(1 for r in result if r['severity']=='critical'), 'alerts': result})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs    = AgrementRecuperateur.objects.all()
        today = date.today()
        return Response({
            'total':       qs.count(),
            'actifs':      qs.filter(statut='ACTIF').count(),
            'expires':     qs.filter(statut='ACTIF', date_fin__lt=today).count(),
            'suspendus':   qs.filter(statut='SUSPENDU').count(),
            'par_type':    list(qs.values('type_agrement').annotate(count=Count('id'))),
            'par_etendue': list(qs.values('etendue_geo').annotate(count=Count('id'))),
        })


class RecuperateurViewSet(viewsets.ModelViewSet):
    module_label    = 'recuperateurs'
    queryset        = Recuperateur.objects.prefetch_related('agrements').all()
    permission_classes = [ModulePermission]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields   = ['nom_raison_sociale','nom_commercial','numero_id','nif','nis','registre_commerce']
    filterset_fields= ['type_recuperateur','statut','wilaya']

    def get_serializer_class(self):
        return RecuperateurListSerializer if self.action == 'list' else RecuperateurSerializer

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs    = Recuperateur.objects.all()
        today = date.today()
        soon  = today + timedelta(days=60)
        return Response({
            'total':      qs.count(),
            'actifs':     qs.filter(statut='ACTIF').count(),
            'suspendus':  qs.filter(statut='SUSPENDU').count(),
            'en_attente': qs.filter(statut='EN_ATTENTE').count(),
            'par_type':   list(qs.values('type_recuperateur').annotate(count=Count('id'))),
            'par_wilaya': list(qs.values('wilaya').annotate(count=Count('id')).order_by('-count')[:15]),
            'par_statut': list(qs.values('statut').annotate(count=Count('id'))),
        })

    @action(detail=False, methods=['get'])
    def alerts(self, request):
        today = date.today()
        soon  = today + timedelta(days=60)
        alerts = []
        for agr in AgrementRecuperateur.objects.filter(statut='ACTIF', date_fin__lt=today).select_related('recuperateur'):
            alerts.append({'type':'EXPIRE','severity':'critical',
                'message': f"Agrément expiré — {agr.recuperateur.nom_raison_sociale} (W.{agr.recuperateur.wilaya})",
                'id': agr.recuperateur.id})
        for agr in AgrementRecuperateur.objects.filter(statut='ACTIF', date_fin__gte=today, date_fin__lte=soon).select_related('recuperateur'):
            alerts.append({'type':'EXPIRING','severity':'warning',
                'message': f"Agrément expire dans {(agr.date_fin-today).days}j — {agr.recuperateur.nom_raison_sociale}",
                'id': agr.recuperateur.id})
        return Response({'total': len(alerts), 'alerts': alerts})
