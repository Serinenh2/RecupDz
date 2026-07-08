import re
from rest_framework import serializers
from .models import BonCommande

NUMERO_PREFIXES = {
    'BC':       'CM',
    'PROFORMA': 'PR',
    'FACTURE':  'FA',
}


class BCSerializer(serializers.ModelSerializer):
    statut_display   = serializers.CharField(source='get_statut_display', read_only=True)
    recuperateur_nom = serializers.CharField(source='recuperateur.nom_raison_sociale', read_only=True)

    class Meta:
        model  = BonCommande
        fields = '__all__'
        read_only_fields = ['recuperateur']

    def validate(self, data):
        type_document = data.get('type_document') or getattr(self.instance, 'type_document', 'BC')
        numero = data.get('numero')
        if numero is not None:
            numero = numero.strip().upper()
            prefix = NUMERO_PREFIXES.get(type_document, 'CM')
            if not re.match(rf'^{prefix}\d{{4}}\d+$', numero):
                raise serializers.ValidationError({
                    'numero': f"Le numéro doit être au format {prefix}AAAANNNN "
                              f"(ex: {prefix}20260003 — AAAA = année, NNNN = n° de bon)."
                })
            data['numero'] = numero
        return data
