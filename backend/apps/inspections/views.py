from rest_framework import viewsets, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from apps.accounts.permissions import ModulePermission
from .models import Inspection
from .serializers import InspectionSerializer
from .generate_pv import generate_pv_pdf
from .generate_pv_word import generate_pv_docx

WORD_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

class InspectionViewSet(viewsets.ModelViewSet):
    module_label     = 'inspections'
    permission_classes = [ModulePermission]
    queryset = Inspection.objects.select_related('recuperateur','inspecteur').all()
    serializer_class = InspectionSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['recuperateur','type_inspection','resultat']
    search_fields    = ['pv_numero','observations']

    def perform_create(self, s):
        s.save(inspecteur=self.request.user)

    @action(detail=True, methods=['get'])
    def generer_pdf(self, request, pk=None):
        insp = self.get_object()
        data = InspectionSerializer(insp).data
        data['recuperateur_nom'] = insp.recuperateur.nom_raison_sociale if insp.recuperateur else ''
        try:
            pdf  = generate_pv_pdf(data)
            nom  = insp.pv_numero or f'PV_{insp.pk}'
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="{nom}.pdf"'
            return resp
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'])
    def generer_word(self, request, pk=None):
        insp = self.get_object()
        data = InspectionSerializer(insp).data
        data['recuperateur_nom'] = insp.recuperateur.nom_raison_sociale if insp.recuperateur else ''
        try:
            docx_bytes = generate_pv_docx(data)
            nom  = insp.pv_numero or f'PV_{insp.pk}'
            resp = HttpResponse(docx_bytes, content_type=WORD_CT)
            resp['Content-Disposition'] = f'attachment; filename="{nom}.docx"'
            return resp
        except Exception as e:
            return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_pv(request):
    try:
        pdf  = generate_pv_pdf(request.data)
        nom  = request.data.get('pv_numero', 'PV')[:30].replace(' ','_')
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="PV_{nom}.pdf"'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_pv_word(request):
    try:
        docx_bytes = generate_pv_docx(request.data)
        nom  = request.data.get('pv_numero', 'PV')[:30].replace(' ','_')
        resp = HttpResponse(docx_bytes, content_type=WORD_CT)
        resp['Content-Disposition'] = f'attachment; filename="PV_{nom}.docx"'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=500)
