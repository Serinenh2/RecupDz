import re
from rest_framework import serializers
from .models import BonCommande

NUMERO_PREFIXES = {
    'BC':       'CM',
    'PROFORMA': 'PR',
    'FACTURE':  'FA',
}


class BCSerializer(serializers.ModelSerializer):
    statut_display              = serializers.CharField(source='get_statut_display', read_only=True)
    recuperateur_nom             = serializers.CharField(source='recuperateur.nom_raison_sociale', read_only=True)
    proforma_origine_numero      = serializers.CharField(source='proforma_origine.numero', read_only=True, default=None)
    bon_livraison_origine_numero = serializers.CharField(source='bon_livraison_origine.numero', read_only=True, default=None)
    bc_generes_numeros           = serializers.SerializerMethodField()
    bl_generes_numeros           = serializers.SerializerMethodField()

    class Meta:
        model  = BonCommande
        fields = '__all__'
        read_only_fields = ['recuperateur']

    def get_bc_generes_numeros(self, obj):
        return [{'id': bc.id, 'numero': bc.numero} for bc in obj.bc_generes.all()]

    def get_bl_generes_numeros(self, obj):
        return [{'id': bl.id, 'numero': bl.numero} for bl in obj.bl_generes.all()]

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
