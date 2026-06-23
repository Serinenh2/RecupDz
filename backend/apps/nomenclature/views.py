from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Nomenclature
from .serializers import NomenclatureSerializer

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
