from rest_framework import serializers
from .models import BonLivraison


class BLSerializer(serializers.ModelSerializer):
    statut_display            = serializers.CharField(source='get_statut_display', read_only=True)
    destinataire_type_display = serializers.CharField(source='get_destinataire_type_display', read_only=True)
    destinataire_nom          = serializers.CharField(source='destinataire.raison_sociale', read_only=True)
    recuperateur_nom          = serializers.CharField(source='recuperateur.nom_raison_sociale', read_only=True)

    class Meta:
        model = BonLivraison
        fields = '__all__'
