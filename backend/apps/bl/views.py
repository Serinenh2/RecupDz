from rest_framework import viewsets, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from apps.accounts.permissions import ModulePermission
from .models import BonLivraison
from .serializers import BLSerializer
from .generate_bl import generate_bl_pdf
from .generate_bl_word import generate_bl_docx

WORD_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


class BLViewSet(viewsets.ModelViewSet):
    module_label     = 'bl'
    permission_classes = [ModulePermission]
    queryset = BonLivraison.objects.select_related('recuperateur', 'destinataire').all()
    serializer_class = BLSerializer
    filter_backends  = [filters.SearchFilter, DjangoFilterBackend]
    search_fields    = ['numero', 'destinataire__raison_sociale', 'bon_commande_numero']
    filterset_fields = ['recuperateur', 'statut', 'destinataire_type']

    def get_queryset(self):
        qs = BonLivraison.objects.select_related('recuperateur', 'destinataire').all()
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
        bl = self.get_object()
        data = BLSerializer(bl).data
        try:
            pdf  = generate_bl_pdf(data)
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="BL_{bl.numero}.pdf"'
            return resp
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'])
    def generer_word(self, request, pk=None):
        bl = self.get_object()
        data = BLSerializer(bl).data
        try:
            docx_bytes = generate_bl_docx(data)
            resp = HttpResponse(docx_bytes, content_type=WORD_CT)
            resp['Content-Disposition'] = f'attachment; filename="BL_{bl.numero}.docx"'
            return resp
        except Exception as e:
            return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_bl(request):
    try:
        pdf  = generate_bl_pdf(request.data)
        num  = request.data.get('numero', 'BL')[:30].replace(' ', '_')
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="BL_{num}.pdf"'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_bl_word(request):
    try:
        docx_bytes = generate_bl_docx(request.data)
        num  = request.data.get('numero', 'BL')[:30].replace(' ', '_')
        resp = HttpResponse(docx_bytes, content_type=WORD_CT)
        resp['Content-Disposition'] = f'attachment; filename="BL_{num}.docx"'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=500)
