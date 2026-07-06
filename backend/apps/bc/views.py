from rest_framework import viewsets, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from apps.accounts.permissions import ModulePermission
from .models import BonCommande
from .serializers import BCSerializer
from .generate_bc import generate_bc_pdf
from .generate_bc_word import generate_bc_docx

WORD_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


class BCFilter(django_filters.FilterSet):
    date_min = django_filters.DateFilter(field_name='date_commande', lookup_expr='gte')
    date_max = django_filters.DateFilter(field_name='date_commande', lookup_expr='lte')

    class Meta:
        model  = BonCommande
        fields = ['recuperateur', 'statut', 'date_commande', 'type_document']


class BCViewSet(viewsets.ModelViewSet):
    module_label       = 'bc'
    permission_classes = [ModulePermission]
    queryset           = BonCommande.objects.select_related('recuperateur').all()
    serializer_class   = BCSerializer
    filter_backends    = [filters.SearchFilter, DjangoFilterBackend]
    search_fields      = ['numero', 'client_nom']
    filterset_class    = BCFilter

    def get_queryset(self):
        qs   = BonCommande.objects.select_related('recuperateur').all()
        user = self.request.user
        if user.is_superuser or user.has_role('SUPERADMIN', 'ADMIN'):
            return qs
        recuperateur = getattr(user, 'recuperateur', None)
        return qs.filter(recuperateur=recuperateur) if recuperateur else qs

    def perform_create(self, s):
        recuperateur = getattr(self.request.user, 'recuperateur', None)
        if recuperateur:
            s.save(created_by=self.request.user, recuperateur=recuperateur)
        else:
            s.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def generer_pdf(self, request, pk=None):
        bc   = self.get_object()
        data = BCSerializer(bc).data
        try:
            pdf  = generate_bc_pdf(data)
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="BC_{bc.numero}.pdf"'
            return resp
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'])
    def generer_word(self, request, pk=None):
        bc   = self.get_object()
        data = BCSerializer(bc).data
        try:
            docx_bytes = generate_bc_docx(data)
            resp = HttpResponse(docx_bytes, content_type=WORD_CT)
            resp['Content-Disposition'] = f'attachment; filename="BC_{bc.numero}.docx"'
            return resp
        except Exception as e:
            return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_bc(request):
    try:
        pdf  = generate_bc_pdf(request.data)
        num  = request.data.get('numero', 'BC')[:30].replace(' ', '_')
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="BC_{num}.pdf"'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_bc_word(request):
    try:
        docx_bytes = generate_bc_docx(request.data)
        num  = request.data.get('numero', 'BC')[:30].replace(' ', '_')
        resp = HttpResponse(docx_bytes, content_type=WORD_CT)
        resp['Content-Disposition'] = f'attachment; filename="BC_{num}.docx"'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=500)
