from django.contrib import admin
from .models import Nomenclature, DesignationDechet

@admin.register(Nomenclature)
class NomenclatureAdmin(admin.ModelAdmin):
    list_display  = ['code','designation_fr','classe','bsd_obligatoire','agrement_requis']
    list_filter   = ['classe','bsd_obligatoire','agrement_requis']
    search_fields = ['code','designation_fr','designation_ar']


@admin.register(DesignationDechet)
class DesignationDechetAdmin(admin.ModelAdmin):
    list_display  = ['id_recup_dz', 'designation', 'nomenclature', 'matiere', 'ordre']
    list_filter   = ['nomenclature__code', 'matiere']
    search_fields = ['id_recup_dz', 'designation', 'matiere']
    list_editable = ['ordre']
    autocomplete_fields = ['nomenclature']
