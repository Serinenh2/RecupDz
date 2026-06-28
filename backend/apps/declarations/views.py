from rest_framework import viewsets, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from apps.accounts.permissions import ModulePermission
from .models import Declaration
from .serializers import DeclarationSerializer
from .generate_dsd import generate_dsd_pdf
from .generate_dsd_word import generate_dsd_docx

WORD_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

class DeclarationViewSet(viewsets.ModelViewSet):
    module_label     = 'declarations'
    permission_classes = [ModulePermission]
    queryset         = Declaration.objects.select_related('recuperateur').all()
    serializer_class = DeclarationSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['recuperateur', 'annee', 'statut']
    search_fields    = ['denomination', 'code_dechet', 'annee']

    def get_queryset(self):
        qs = Declaration.objects.select_related('recuperateur').all()
        user = self.request.user
        if user.is_superuser or user.has_role('SUPERADMIN', 'ADMIN'):
            return qs
        recuperateur = getattr(user, 'recuperateur', None)
        return qs.filter(recuperateur=recuperateur) if recuperateur else qs

    def perform_create(self, serializer):
        recuperateur = getattr(self.request.user, 'recuperateur', None)
        if recuperateur:
            serializer.save(created_by=self.request.user, recuperateur=recuperateur)
        else:
            serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def generer_pdf(self, request, pk=None):
        """Genere le PDF DSD pour une declaration existante"""
        decl = self.get_object()
        data = DeclarationSerializer(decl).data
        try:
            pdf = generate_dsd_pdf(data)
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="DSD_{decl.denomination}_{decl.annee}.pdf"'
            return resp
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['post'])
    def generer_word(self, request, pk=None):
        """Genere le document Word DSD pour une declaration existante"""
        decl = self.get_object()
        data = DeclarationSerializer(decl).data
        try:
            docx_bytes = generate_dsd_docx(data)
            resp = HttpResponse(docx_bytes, content_type=WORD_CT)
            resp['Content-Disposition'] = f'attachment; filename="DSD_{decl.denomination}_{decl.annee}.docx"'
            return resp
        except Exception as e:
            return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_dsd(request):
    """Generate DSD PDF from form data (without saving)"""
    try:
        pdf = generate_dsd_pdf(request.data)
        nom    = request.data.get('denomination', 'DSD')[:20].replace(' ','_')
        annee  = request.data.get('annee', '2024')
        resp   = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="DSD_{nom}_{annee}.pdf"'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_dsd_word(request):
    """Generate DSD Word document from form data (without saving)"""
    try:
        docx_bytes = generate_dsd_docx(request.data)
        nom    = request.data.get('denomination', 'DSD')[:20].replace(' ','_')
        annee  = request.data.get('annee', '2024')
        resp   = HttpResponse(docx_bytes, content_type=WORD_CT)
        resp['Content-Disposition'] = f'attachment; filename="DSD_{nom}_{annee}.docx"'
        return resp
    except Exception as e:
        return Response({'error': str(e)}, status=500)
