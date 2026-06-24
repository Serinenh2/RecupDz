from rest_framework import viewsets, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Nomenclature, DesignationDechet
from .serializers import NomenclatureSerializer, DesignationDechetSerializer

class NomenclatureViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Nomenclature.objects.all()
    serializer_class = NomenclatureSerializer
    filter_backends  = [filters.SearchFilter, DjangoFilterBackend]
    search_fields    = ['code','designation_fr','designation_ar']
    filterset_fields = ['classe','famille','bsd_obligatoire','agrement_requis']
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()

        # ?mes_specialisations=1 → ne renvoie que les codes dont la classe (MA/I/S/SD)
        # correspond à au moins un détail de spécialisation coché (par l'administrateur)
        # pour le récupérateur connecté.
        only_mine = self.request.query_params.get('mes_specialisations')
        if only_mine in ('1', 'true', 'True'):
            user = self.request.user
            recuperateur = getattr(user, 'recuperateur', None)
            if recuperateur is not None:
                classes = (
                    recuperateur.specialisation_details
                    .exclude(classe_nomenclature='')
                    .values_list('classe_nomenclature', flat=True)
                    .distinct()
                )
                if classes:
                    qs = qs.filter(classe__in=list(classes))
                else:
                    # Spécialisation pas encore assignée → aucun code (évite de tout montrer par erreur)
                    qs = qs.none()
        return qs


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designations_par_code(request):
    """
    4ème niveau de la cascade Traçabilité : pour un Code nomenclature donné
    (ex: 15.01.02), retourne la liste des désignations précises disponibles
    (ex: Bouteille d'eau PET, Flacon PEHD, Big Bag PP...).
    GET /api/nomenclature/designations/?code=15.01.02
    """
    code = request.query_params.get('code', '').strip()
    if not code:
        return Response({'error': 'Paramètre "code" requis.'}, status=400)
    designations = DesignationDechet.objects.filter(nomenclature__code=code)
    return Response(DesignationDechetSerializer(designations, many=True).data)
