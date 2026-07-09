from datetime import date
from rest_framework import viewsets, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from apps.accounts.permissions import ModulePermission
from apps.archive.services import archive_document
from apps.bc.models import next_numero
from .models import BonLivraison
from .serializers import BLSerializer
from .generate_bl import generate_bl_pdf
from .generate_bl_word import generate_bl_docx

WORD_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


class BLFilter(django_filters.FilterSet):
    date_min = django_filters.DateFilter(field_name='date_livraison', lookup_expr='gte')
    date_max = django_filters.DateFilter(field_name='date_livraison', lookup_expr='lte')

    class Meta:
        model  = BonLivraison
        fields = ['recuperateur', 'statut', 'destinataire_type', 'date_livraison']


class BLViewSet(viewsets.ModelViewSet):
    module_label     = 'bl'
    permission_classes = [ModulePermission]
    queryset = BonLivraison.objects.select_related('recuperateur', 'destinataire').all()
    serializer_class = BLSerializer
    filter_backends  = [filters.SearchFilter, DjangoFilterBackend]
    search_fields    = ['numero', 'destinataire__raison_sociale']
    filterset_class  = BLFilter

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
            instance = s.save(created_by=self.request.user, recuperateur=recuperateur)
        else:
            instance = s.save(created_by=self.request.user)
        if instance.statut == 'VALIDE':
            self._archive_if_valide(instance)

    def perform_update(self, serializer):
        old_statut = serializer.instance.statut
        instance = serializer.save()
        if instance.statut == 'VALIDE' and old_statut != 'VALIDE':
            self._archive_if_valide(instance)

    def _archive_if_valide(self, instance):
        try:
            pdf = generate_bl_pdf(BLSerializer(instance).data)
            archive_document(
                source_app_label='bl', source_id=instance.id, numero=instance.numero,
                categorie='BL', label='BL',
                pdf_bytes=pdf, dossier_id=instance.dossier_id, user=self.request.user,
            )
        except Exception:
            pass

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

    @action(detail=True, methods=['post'])
    def generer_facture(self, request, pk=None):
        """Depuis un BL : renvoie un brouillon de Facture pré-rempli (non enregistré).
        Si le BL a lui-même été généré depuis un BC, les prix et le nom du client
        sont récupérés depuis ce BC d'origine (le BL ne stocke ni prix ni nom client)."""
        bl = self.get_object()
        origin_bc = bl.bon_commande_origine

        lignes_facture = []
        for l in (bl.lignes or []):
            desc  = l.get('description', '')
            match = None
            if origin_bc:
                match = next((bl_l for bl_l in (origin_bc.lignes or [])
                              if bl_l.get('description') == desc), None)
            lignes_facture.append({
                'ref_article':   match.get('ref_article', '')   if match else '',
                'description':   desc,
                'quantite':      l.get('quantite', ''),
                'unite':         l.get('unite', ''),
                'prix_unitaire': match.get('prix_unitaire', '') if match else '',
                'remise_pct':    match.get('remise_pct', 0)     if match else 0,
                'tva_pct':       match.get('tva_pct', '')       if match else '',
            })

        draft = {
            'type_document':         'FACTURE',
            'numero':                next_numero('FA'),
            'recuperateur':          bl.recuperateur_id,
            'ref_client':            bl.ref_client,
            'client_nom':            origin_bc.client_nom     if origin_bc else '',
            'client_adresse':        origin_bc.client_adresse if origin_bc else '',
            'client_rc':             bl.client_rc,
            'client_nif':            bl.client_nif,
            'client_numero_article': bl.client_numero_article,
            'client_nis':            bl.client_nis,
            'client_telephone':      bl.client_telephone,
            'client_fax':            bl.client_fax,
            'client_email':          bl.client_email,
            'date_commande':         date.today().isoformat(),
            'pieces_liees':          bl.numero,
            'lignes':                lignes_facture,
            'tva_pct':               origin_bc.tva_pct if origin_bc else 19,
            'statut':                'BROUILLON',
            'bon_livraison_origine': bl.id,
            'dossier_id':            str(bl.dossier_id),
        }
        return Response(draft)


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
