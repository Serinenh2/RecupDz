from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from apps.accounts.permissions import ModulePermission
from .models import Operateur
from .serializers import OperateurSerializer, OperateurListSerializer

class OperateurViewSet(viewsets.ModelViewSet):
    module_label     = 'operateurs'
    permission_classes = [ModulePermission]
    queryset        = Operateur.objects.all()
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields   = ['raison_sociale','nif','nis','nin','registre_commerce','num_agrement']
    filterset_fields= ['type_operateur','statut','wilaya']

    def get_serializer_class(self):
        return OperateurListSerializer if self.action == 'list' else OperateurSerializer

    def get_queryset(self):
        qs = Operateur.objects.all()
        user = self.request.user
        if user.is_superuser or user.has_role('SUPERADMIN', 'ADMIN'):
            return qs
        recuperateur = getattr(user, 'recuperateur', None)
        if recuperateur:
            # Ses propres opérateurs + les opérateurs partagés/institutionnels (sans propriétaire)
            return qs.filter(Q(recuperateur=recuperateur) | Q(recuperateur__isnull=True))
        return qs.filter(recuperateur__isnull=True)

    def perform_create(self, serializer):
        recuperateur = getattr(self.request.user, 'recuperateur', None)
        serializer.save(recuperateur=recuperateur)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        return Response({
            'total':    qs.count(),
            'par_type': list(qs.values('type_operateur').annotate(count=Count('id'))),
            'actifs':   qs.filter(statut='ACTIF').count(),
        })

    @action(detail=False, methods=['post'])
    def verifier_compatibilite(self, request):
        """
        Vérifie la compatibilité entre un récupérateur et un opérateur
        pour un code déchet donné.
        POST { recuperateur_id, operateur_id, code_dechet, classe_dechet }
        """
        from apps.recuperateurs.models import Recuperateur, AgrementRecuperateur

        recuperateur_id = request.data.get('recuperateur_id')
        operateur_id    = request.data.get('operateur_id')
        code_dechet     = request.data.get('code_dechet', '')
        classe_dechet   = request.data.get('classe_dechet', '')

        CLASSES_AGREMENT = {'S', 'SD'}
        alertes = []

        try:
            rec = Recuperateur.objects.get(id=recuperateur_id)
            op  = Operateur.objects.get(id=operateur_id)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        # Déchet ne nécessite pas d'agrément
        if classe_dechet not in CLASSES_AGREMENT:
            return Response({'compatible': True, 'alertes': [], 'message': 'Opération autorisée'})

        # Récupérateur sans agrément actif
        agr = rec.agrements.filter(type_agrement='AVEC_AGREMENT', statut='ACTIF').first()

        if not agr:
            alertes.append({
                'severity': 'critical',
                'code': 'RECUPERATEUR_SANS_AGREMENT',
                'message': (
                    f"Le récupérateur {rec.nom_raison_sociale} n'est pas autorisé à travailler avec "
                    f"{op.raison_sociale} pour le déchet {code_dechet} (classe {classe_dechet}). "
                    f"Un agrément est requis pour manipuler des déchets spéciaux ou dangereux."
                )
            })
        else:
            # Agrement expiré
            from datetime import date
            if agr.date_fin and agr.date_fin < date.today():
                alertes.append({
                    'severity': 'critical',
                    'code': 'AGREMENT_EXPIRE',
                    'message': (
                        f"L'agrément du récupérateur {rec.nom_raison_sociale} a expiré "
                        f"le {agr.date_fin}. Opération non autorisée avec {op.raison_sociale}."
                    )
                })
            # Code déchet non couvert
            elif agr.codes_dechets:
                codes = [c.strip() for c in agr.codes_dechets.split(',') if c.strip()]
                if codes and code_dechet not in codes:
                    alertes.append({
                        'severity': 'critical',
                        'code': 'CODE_NON_AUTORISE',
                        'message': (
                            f"Le code déchet {code_dechet} ne figure pas dans l'agrément "
                            f"du récupérateur {rec.nom_raison_sociale}. "
                            f"Codes autorisés: {', '.join(codes[:5])}..."
                        )
                    })

        # Transporteur sans agrément pour SD
        if op.type_operateur == 'TRANSPORTEUR' and classe_dechet in CLASSES_AGREMENT:
            if not op.num_agrement or not op.agrement_valide:
                alertes.append({
                    'severity': 'critical',
                    'code': 'TRANSPORTEUR_SANS_AGREMENT',
                    'message': (
                        f"Le transporteur {op.raison_sociale} ne dispose pas d'un agrément valide "
                        f"pour transporter des déchets de classe {classe_dechet} ({code_dechet})."
                    )
                })
            elif op.codes_list and code_dechet not in op.codes_list:
                alertes.append({
                    'severity': 'warning',
                    'code': 'TRANSPORTEUR_CODE_NON_AUTORISE',
                    'message': (
                        f"Le code déchet {code_dechet} ne figure pas dans l'agrément "
                        f"du transporteur {op.raison_sociale}."
                    )
                })

        compatible = len(alertes) == 0
        return Response({
            'compatible': compatible,
            'alertes':    alertes,
            'message':    'Opération autorisée' if compatible else 'Opération non autorisée — voir alertes',
        })
