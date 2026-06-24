from rest_framework import serializers
from .models import Nomenclature, DesignationDechet

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
