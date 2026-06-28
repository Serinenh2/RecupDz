from rest_framework import serializers
from .models import Operateur

class OperateurSerializer(serializers.ModelSerializer):
    type_display   = serializers.CharField(source='get_type_operateur_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    agrement_valide= serializers.ReadOnlyField()
    codes_list     = serializers.ReadOnlyField()
    recuperateur_nom = serializers.SerializerMethodField()

    class Meta:
        model  = Operateur
        fields = '__all__'
        read_only_fields = ['recuperateur']

    def get_recuperateur_nom(self, obj):
        return obj.recuperateur.nom_raison_sociale if obj.recuperateur else ''

class OperateurListSerializer(serializers.ModelSerializer):
    type_display   = serializers.CharField(source='get_type_operateur_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    agrement_valide= serializers.ReadOnlyField()
    recuperateur_nom = serializers.SerializerMethodField()

    class Meta:
        model  = Operateur
        fields = ['id','type_operateur','type_display','raison_sociale','nif','nis',
                  'registre_commerce','adresse','wilaya','commune','telephone','email',
                  'num_agrement','date_fin_agrement','statut','statut_display',
                  'agrement_valide','created_at','recuperateur','recuperateur_nom']

    def get_recuperateur_nom(self, obj):
        return obj.recuperateur.nom_raison_sociale if obj.recuperateur else ''
