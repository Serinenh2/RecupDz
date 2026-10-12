from rest_framework import serializers
from .models import Nomenclature, DesignationDechet, CatalogueEntreprise

class NomenclatureSerializer(serializers.ModelSerializer):
    classe_display = serializers.CharField(source='get_classe_display', read_only=True)
    couleur_danger = serializers.ReadOnlyField()
    class Meta:
        model = Nomenclature
        fields = '__all__'

class DesignationDechetSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source='nomenclature.code', read_only=True)
    class Meta:
        model  = DesignationDechet
        fields = ['id', 'id_recup_dz', 'code', 'designation', 'matiere', 'ordre']

class CatalogueEntrepriseSerializer(serializers.ModelSerializer):
    code_dechet = serializers.SerializerMethodField()
    classe      = serializers.SerializerMethodField()

    class Meta:
        model  = CatalogueEntreprise
        fields = ['id', 'designation', 'reference', 'conditionnement', 'nomenclature',
                  'code_dechet', 'classe', 'created_at']
        read_only_fields = ['created_at']

    def get_code_dechet(self, obj):
        return obj.nomenclature.code if obj.nomenclature else ''

    def get_classe(self, obj):
        return obj.nomenclature.classe if obj.nomenclature else ''
