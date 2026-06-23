from rest_framework import serializers
from .models import Recuperateur, AgrementRecuperateur, DocumentRecuperateur
from .models_specialisation import (
    CategorieSpecialisation, SousCategorieSpecialisation, DetailSpecialisation,
)

class AgrementSerializer(serializers.ModelSerializer):
    type_display    = serializers.CharField(source='get_type_agrement_display', read_only=True)
    etendue_display = serializers.CharField(source='get_etendue_geo_display', read_only=True)
    statut_display  = serializers.CharField(source='get_statut_display', read_only=True)
    est_valide      = serializers.ReadOnlyField()
    jours_restants  = serializers.ReadOnlyField()
    expire_bientot  = serializers.ReadOnlyField()
    codes_list      = serializers.ReadOnlyField()
    wilayas_list    = serializers.ReadOnlyField()
    class Meta:
        model  = AgrementRecuperateur
        fields = '__all__'

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DocumentRecuperateur
        fields = '__all__'

class RecuperateurListSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    type_display   = serializers.CharField(source='get_type_recuperateur_display', read_only=True)
    agrement_actif = serializers.SerializerMethodField()
    class Meta:
        model  = Recuperateur
        fields = ['id','numero_id','nom_raison_sociale','nom_commercial',
                  'type_recuperateur','type_display','statut','statut_display',
                  'wilaya','commune','telephone','email','created_at','agrement_actif']
    def get_agrement_actif(self, obj):
        agr = obj.agrements.filter(statut='ACTIF').first()
        if agr: return AgrementSerializer(agr).data
        return None


# ── Spécialisation — lecture seule pour le récupérateur ────────────────────────

class DetailSpecialisationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DetailSpecialisation
        fields = ['id', 'nom', 'ordre']

class SousCategorieSpecialisationSerializer(serializers.ModelSerializer):
    details = DetailSpecialisationSerializer(many=True, read_only=True)
    class Meta:
        model  = SousCategorieSpecialisation
        fields = ['id', 'nom', 'ordre', 'details']

class CategorieSpecialisationSerializer(serializers.ModelSerializer):
    sous_categories = SousCategorieSpecialisationSerializer(many=True, read_only=True)
    class Meta:
        model  = CategorieSpecialisation
        fields = ['id', 'nom', 'icone', 'ordre', 'sous_categories']


class RecuperateurSerializer(serializers.ModelSerializer):
    statut_display          = serializers.CharField(source='get_statut_display', read_only=True)
    type_display            = serializers.CharField(source='get_type_recuperateur_display', read_only=True)
    agrements                = AgrementSerializer(many=True, read_only=True)
    documents                = DocumentSerializer(many=True, read_only=True)
    # Lecture seule — assignée uniquement par le Super Admin via Django Admin
    specialisation_details   = DetailSpecialisationSerializer(many=True, read_only=True)

    class Meta:
        model  = Recuperateur
        fields = '__all__'
        read_only_fields = ['specialisation_details']