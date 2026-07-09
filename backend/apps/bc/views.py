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
from .models import BonCommande, next_numero
from .serializers import BCSerializer
from .generate_bc import generate_bc_pdf, _calc_totaux
from .generate_bc_word import generate_bc_docx

WORD_CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

DOC_LABELS = {'PROFORMA': 'Proforma', 'BC': 'BC', 'FACTURE': 'Facture'}


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
            pdf = generate_bc_pdf(BCSerializer(instance).data)
            archive_document(
                source_app_label='bc', source_id=instance.id, numero=instance.numero,
                categorie=instance.type_document, label=DOC_LABELS.get(instance.type_document, 'BC'),
                pdf_bytes=pdf, dossier_id=instance.dossier_id, user=self.request.user,
            )
        except Exception:
            pass

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

    @action(detail=True, methods=['post'])
    def generer_bc(self, request, pk=None):
        """Depuis un Proforma : renvoie un brouillon de BC pré-rempli (non enregistré)."""
        proforma = self.get_object()
        if proforma.type_document != 'PROFORMA':
            return Response({'error': "Seul un document de type Proforma peut générer un BC."}, status=400)
        draft = {
            'type_document':         'BC',
            'numero':                next_numero('CM'),
            'recuperateur':          proforma.recuperateur_id,
            'ref_client':            proforma.ref_client,
            'client_nom':            proforma.client_nom,
            'client_adresse':        proforma.client_adresse,
            'client_rc':             proforma.client_rc,
            'client_nif':            proforma.client_nif,
            'client_numero_article': proforma.client_numero_article,
            'client_nis':            proforma.client_nis,
            'client_telephone':      proforma.client_telephone,
            'client_fax':            proforma.client_fax,
            'client_email':          proforma.client_email,
            'date_commande':         date.today().isoformat(),
            'pieces_liees':          proforma.numero,
            'lignes':                proforma.lignes,
            'tva_pct':               proforma.tva_pct,
            'observations':          proforma.observations,
            'statut':                'BROUILLON',
            'proforma_origine':      proforma.id,
            'dossier_id':            str(proforma.dossier_id),
        }
        return Response(draft)

    @action(detail=True, methods=['post'])
    def generer_bl(self, request, pk=None):
        """Depuis un BC : renvoie un brouillon de BL pré-rempli (non enregistré)."""
        bc = self.get_object()
        if bc.type_document != 'BC':
            return Response({'error': "Seul un Bon de Commande peut générer un BL."}, status=400)
        lignes_bl = [
            {
                'ref_article': l.get('ref_article', ''),
                'description': l.get('description', ''),
                'quantite':    l.get('quantite', ''),
                'unite':       l.get('unite', 'KG'),
                'stockage':    '',
            }
            for l in (bc.lignes or [])
        ]

        # Le client du BC (choisi depuis la fiche Opérateur) est directement le
        # destinataire du BL quand son type correspond à un type de destinataire
        # valide (Éliminateur/Valorisateur/CET) — évite de le resaisir. Si le BC
        # n'a pas de fiche liée (client saisi à la main) on tente un rapprochement
        # par nom parmi les opérateurs de type destinataire valide.
        destinataire_type = 'ELIMINATEUR'
        destinataire = ''
        client_op = bc.client_operateur
        if client_op and client_op.type_operateur in ('ELIMINATEUR', 'VALORISATEUR', 'CET'):
            destinataire_type = client_op.type_operateur
            destinataire = client_op.id
        elif bc.client_nom:
            from apps.operateurs.models import Operateur
            match = Operateur.objects.filter(
                type_operateur__in=['ELIMINATEUR', 'VALORISATEUR', 'CET'],
                raison_sociale__iexact=bc.client_nom.strip(),
            ).first()
            if match:
                destinataire_type = match.type_operateur
                destinataire = match.id

        _, _, total_ttc = _calc_totaux(bc.lignes or [], float(bc.tva_pct))

        draft = {
            'numero':                next_numero('BL'),
            'recuperateur':          bc.recuperateur_id,
            'destinataire_type':     destinataire_type,
            'destinataire':          destinataire,
            'client_nom_bc':         bc.client_nom,
            'ref_client':            bc.ref_client,
            'client_rc':             bc.client_rc,
            'client_nif':            bc.client_nif,
            'client_numero_article': bc.client_numero_article,
            'client_nis':            bc.client_nis,
            'client_telephone':      bc.client_telephone,
            'client_fax':            bc.client_fax,
            'client_email':          bc.client_email,
            'date_livraison':        date.today().isoformat(),
            'pieces_liees':          bc.numero,
            'lignes':                lignes_bl,
            'montant_reference':     round(total_ttc, 2),
            'statut':                'BROUILLON',
            'bon_commande_origine':  bc.id,
            'dossier_id':            str(bc.dossier_id),
        }
        return Response(draft)


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
