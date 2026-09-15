from rest_framework import serializers
from django.contrib.auth import get_user_model
User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    role_display      = serializers.CharField(source='get_role_display', read_only=True)
    recuperateur_id   = serializers.SerializerMethodField()
    recuperateur_nom  = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id','username','email','first_name','last_name',
                  'role','role_display','phone','wilaya','is_superuser','is_active',
                  'recuperateur_id','recuperateur_nom']
        extra_kwargs = {'password': {'write_only': True}}

    def get_recuperateur_id(self, obj):
        try:
            return obj.recuperateur.id
        except Exception:
            return None

    def get_recuperateur_nom(self, obj):
        try:
            return obj.recuperateur.nom_raison_sociale
        except Exception:
            return None