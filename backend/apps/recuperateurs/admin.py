from django.contrib import admin
from .models import Recuperateur, AgrementRecuperateur, DocumentRecuperateur
from .models_specialisation import (
    CategorieSpecialisation, SousCategorieSpecialisation, DetailSpecialisation,
)

class AgrementInline(admin.TabularInline):
    model = AgrementRecuperateur
    extra = 0

class DocInline(admin.TabularInline):
    model = DocumentRecuperateur
    extra = 0

@admin.register(Recuperateur)
class RecuperateurAdmin(admin.ModelAdmin):
    list_display  = ['numero_id','nom_raison_sociale','type_recuperateur','statut','wilaya']
    list_filter   = ['type_recuperateur','statut','wilaya']
    search_fields = ['nom_raison_sociale','numero_id']
    inlines       = [AgrementInline, DocInline]
    filter_horizontal = ['specialisation_details']  # widget double-liste avec cases à cocher

@admin.register(AgrementRecuperateur)
class AgrementAdmin(admin.ModelAdmin):
    list_display  = ['numero_agrement','recuperateur','type_agrement','etendue_geo','statut','date_fin']
    list_filter   = ['type_agrement','statut','etendue_geo']
    search_fields = ['numero_agrement','codes_dechets']


# ════════════════════════════════════════════════════════════════════════════
# Hiérarchie de spécialisation — gestion complète par le Super Admin
#
# Chaque DetailSpecialisation a un champ "classe_nomenclature" (MA/I/S/SD).
# Quand un détail est coché pour un récupérateur (sur sa fiche, plus haut),
# TOUS les codes de nomenclature de cette classe s'affichent dans sa page
# Nomenclature côté frontend (filtre ?mes_specialisations=1).
# ════════════════════════════════════════════════════════════════════════════

class SousCategorieInline(admin.TabularInline):
    model = SousCategorieSpecialisation
    extra = 1

@admin.register(CategorieSpecialisation)
class CategorieSpecialisationAdmin(admin.ModelAdmin):
    list_display  = ['icone', 'nom', 'ordre']
    list_editable = ['ordre']
    inlines       = [SousCategorieInline]
    search_fields = ['nom']


class DetailInline(admin.TabularInline):
    model = DetailSpecialisation
    extra = 1
    fields = ['nom', 'classe_nomenclature', 'ordre']

@admin.register(SousCategorieSpecialisation)
class SousCategorieSpecialisationAdmin(admin.ModelAdmin):
    list_display  = ['nom', 'categorie', 'ordre']
    list_filter   = ['categorie']
    list_editable = ['ordre']
    inlines       = [DetailInline]
    search_fields = ['nom']


@admin.register(DetailSpecialisation)
class DetailSpecialisationAdmin(admin.ModelAdmin):
    list_display  = ['nom', 'sous_categorie', 'classe_nomenclature', 'ordre']
    list_filter   = ['sous_categorie__categorie', 'sous_categorie', 'classe_nomenclature']
    list_editable = ['ordre', 'classe_nomenclature']
    search_fields = ['nom']
