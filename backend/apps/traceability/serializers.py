from rest_framework import serializers
from .models import Traceability

class TraceabilitySerializer(serializers.ModelSerializer):
    statut_display      = serializers.CharField(source='get_statut_display', read_only=True)
    unite_display       = serializers.CharField(source='get_unite_display', read_only=True)
    destination_display = serializers.CharField(source='get_destination_type_display', read_only=True)
    couleur_display      = serializers.CharField(source='get_couleur_display', read_only=True)
    niveau_proprete_display = serializers.CharField(source='get_niveau_proprete_display', read_only=True)
    necessite_bsd       = serializers.ReadOnlyField()
    # Nested names
    generateur_nom      = serializers.SerializerMethodField()
    transporteur_nom    = serializers.SerializerMethodField()
    valorisateur_nom    = serializers.SerializerMethodField()
    eliminateur_nom     = serializers.SerializerMethodField()
    cet_nom             = serializers.SerializerMethodField()
    recuperateur_nom    = serializers.SerializerMethodField()

    class Meta:
        model  = Traceability
        fields = '__all__'

    def get_generateur_nom(self, obj):
        return obj.generateur.raison_sociale if obj.generateur else ''
    def get_transporteur_nom(self, obj):
        return obj.transporteur.raison_sociale if obj.transporteur else ''
    def get_valorisateur_nom(self, obj):
        return obj.valorisateur.raison_sociale if obj.valorisateur else ''
    def get_eliminateur_nom(self, obj):
        return obj.eliminateur.raison_sociale if obj.eliminateur else ''
    def get_cet_nom(self, obj):
        return obj.cet.raison_sociale if obj.cet else ''
    def get_recuperateur_nom(self, obj):
        return obj.recuperateur.nom_raison_sociale if obj.recuperateur else ''
