from django.contrib import admin
from .models import Traceability

@admin.register(Traceability)
class TraceabilityAdmin(admin.ModelAdmin):
    list_display  = ['numero','recuperateur','generateur','code_dechet',
                     'quantite','unite','date_recuperation','statut']
    list_filter   = ['statut','classe_dechet','destination_type']
    search_fields = ['numero','code_dechet','bon_livraison','bon_commande']
