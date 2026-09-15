from rest_framework import viewsets, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from apps.accounts.permissions import ModulePermission
from apps.accounts.upload_security import validate_uploaded_file
from .models import Document
from .serializers import DocumentSerializer


ALLOWED_DOC_MIMES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'text/csv',
    'image/jpeg',
    'image/png',
    'application/zip',
    'application/x-zip-compressed',
    'application/x-rar-compressed',
    'application/vnd.rar',
}

# Aligné sur la limite affichée dans l'UI d'import de documents (50 Mo)
MAX_DOC_UPLOAD_SIZE = 50 * 1024 * 1024


class DocumentViewSet(viewsets.ModelViewSet):
    module_label     = 'archive'
    permission_classes = [ModulePermission]
    queryset         = Document.objects.select_related('uploaded_by').all()
    serializer_class = DocumentSerializer
    parser_classes   = [MultiPartParser, FormParser, JSONParser]
    filter_backends  = [filters.SearchFilter, DjangoFilterBackend]
    search_fields    = ['titre', 'description', 'tags', 'nom_original']
    filterset_fields = ['categorie']

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        fichier = self.request.FILES.get('fichier')
        extra = {}
        if fichier:
            fichier = validate_uploaded_file(fichier, allowed_mimes=ALLOWED_DOC_MIMES, max_size=MAX_DOC_UPLOAD_SIZE)
            extra['nom_original'] = fichier.name
            extra['taille']       = fichier.size
            extra['type_mime']    = fichier.content_type or ''
        serializer.save(uploaded_by=self.request.user, **extra)

    def perform_update(self, serializer):
        fichier = self.request.FILES.get('fichier')
        extra = {}
        if fichier:
            fichier = validate_uploaded_file(fichier, allowed_mimes=ALLOWED_DOC_MIMES, max_size=MAX_DOC_UPLOAD_SIZE)
            extra['nom_original'] = fichier.name
            extra['taille']       = fichier.size
            extra['type_mime']    = fichier.content_type or ''
        serializer.save(**extra)