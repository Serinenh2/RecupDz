import re
from rest_framework import serializers
from .models import BonLivraison

NUMERO_PREFIX = 'BL'


class BLSerializer(serializers.ModelSerializer):
    statut_display            = serializers.CharField(source='get_statut_display', read_only=True)
    destinataire_type_display = serializers.CharField(source='get_destinataire_type_display', read_only=True)
    destinataire_nom          = serializers.CharField(source='destinataire.raison_sociale', read_only=True)
    destinataire_commune      = serializers.CharField(source='destinataire.commune', read_only=True)
    recuperateur_nom          = serializers.CharField(source='recuperateur.nom_raison_sociale', read_only=True)

    class Meta:
        model = BonLivraison
        fields = '__all__'
        read_only_fields = ['recuperateur']

    def validate(self, data):
        dest_type    = data.get('destinataire_type') or getattr(self.instance, 'destinataire_type', None)
        destinataire = data.get('destinataire')      or getattr(self.instance, 'destinataire', None)

        # CET cannot receive special or hazardous waste (S/SD)
        if dest_type == 'CET' and destinataire:
            if hasattr(destinataire, 'type_operateur') and destinataire.type_operateur != 'CET':
                raise serializers.ValidationError(
                    "L'opérateur sélectionné n'est pas un Centre d'Enfouissement Technique (CET)."
                )

        numero = data.get('numero')
        if numero is not None:
            numero = numero.strip().upper()
            if not re.match(rf'^{NUMERO_PREFIX}\d{{4}}\d+$', numero):
                raise serializers.ValidationError({
                    'numero': f"Le numéro doit être au format {NUMERO_PREFIX}AAAANNNN "
                              f"(ex: {NUMERO_PREFIX}20260003 — AAAA = année, NNNN = n° de bon)."
                })
            data['numero'] = numero

        return data
