"""
Pré-remplit la hiérarchie de spécialisation (3 niveaux) avec la structure standard.
Exécution : python manage.py seed_specialisation

Idempotent — relancer ne crée pas de doublons (get_or_create partout).
Après le seed, allez dans Django Admin > Récupérateurs > Catégories de
spécialisation pour ajuster, ou directement sur la fiche d'un récupérateur
pour cocher les détails qui le concernent (champ "Spécialisation").
"""
from django.core.management.base import BaseCommand
from apps.recuperateurs.models_specialisation import (
    CategorieSpecialisation, SousCategorieSpecialisation, DetailSpecialisation,
)

# Chaque détail a une `classe` — c'est elle qui détermine quels codes de
# Nomenclature (classe MA / I / S / SD) s'affichent quand ce détail est coché
# pour un récupérateur.
DATA = [
    {
        "nom": "Déchets ménagers et assimilés", "icone": "🏠",
        "sous_categories": [
            {"nom": "Déchets organiques", "details": [
                ("Alimentaire", "MA"), ("Végétal", "MA"),
            ]},
            {"nom": "Déchets d'emballage", "details": [
                ("PET", "MA"), ("PEHD", "MA"), ("PP", "MA"), ("Films", "MA"),
                ("Papier/carton", "MA"), ("Verre", "MA"), ("Alu", "MA"), ("Acier", "MA"),
                ("Bois", "MA"), ("Textile", "MA"),
                ("Composites", "MA"), ("Mélange", "MA"),
            ]},
            {"nom": "Textiles et cuirs", "details": [], "classe": "MA"},
            {"nom": "Encombrants ménagers", "details": [], "classe": "MA"},
        ],
    },
    {
        "nom": "Déchets inertes", "icone": "🧱",
        "sous_categories": [
            {"nom": "Construction et démolition", "details": [
                ("Béton", "I"), ("Briques", "I"), ("Gravats", "I"),
                ("Sable/argile", "I"), ("Démolition mélangée", "I"),
            ]},
            {"nom": "Miniers et de forage", "details": [], "classe": "I"},
        ],
    },
    {
        "nom": "Déchets spéciaux et spéciaux dangereux", "icone": "⚠️",
        "sous_categories": [
            {"nom": "Industriels spéciaux", "details": [
                ("Chimique", "SD"), ("Solvants", "SD"),
                ("Peintures", "S"), ("Traitement de surface", "SD"),
            ]},
            {"nom": "Hydrocarbures", "details": [
                ("Huiles", "S"), ("Boues pétrolières", "SD"), ("Hydrocarbures répandus", "SD"),
            ]},
            {"nom": "Médicaux et infectieux", "details": [], "classe": "SD"},
            {"nom": "Électroniques et batteries", "details": [
                ("DEEE", "S"), ("Piles", "SD"),
            ]},
            {"nom": "Pneumatiques", "details": [], "classe": "S"},
        ],
    },
]


class Command(BaseCommand):
    help = "Pré-remplit la hiérarchie de spécialisation des récupérateurs"

    def handle(self, *args, **options):
        cat_count = sc_count = det_count = 0

        for cat_ordre, cat_data in enumerate(DATA):
            categorie, created = CategorieSpecialisation.objects.get_or_create(
                nom=cat_data["nom"],
                defaults={"icone": cat_data["icone"], "ordre": cat_ordre},
            )
            if created:
                cat_count += 1
                self.stdout.write(f"  + Catégorie créée : {categorie}")

            for sc_ordre, sc_data in enumerate(cat_data["sous_categories"]):
                sous_categorie, created = SousCategorieSpecialisation.objects.get_or_create(
                    categorie=categorie, nom=sc_data["nom"],
                    defaults={"ordre": sc_ordre},
                )
                if created:
                    sc_count += 1
                    self.stdout.write(f"    + Sous-catégorie créée : {sous_categorie}")

                details = sc_data["details"]
                if not details:
                    # Pas de sous-détail listé → créer un détail unique reprenant le
                    # nom de la sous-catégorie, avec la classe indiquée (clé "classe").
                    classe = sc_data.get("classe", "")
                    detail, created = DetailSpecialisation.objects.get_or_create(
                        sous_categorie=sous_categorie, nom=sc_data["nom"],
                        defaults={"ordre": 0, "classe_nomenclature": classe},
                    )
                    if created:
                        det_count += 1
                else:
                    for det_ordre, (det_nom, det_classe) in enumerate(details):
                        detail, created = DetailSpecialisation.objects.get_or_create(
                            sous_categorie=sous_categorie, nom=det_nom,
                            defaults={"ordre": det_ordre, "classe_nomenclature": det_classe},
                        )
                        if created:
                            det_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nSpécialisation initialisée : "
            f"{cat_count} catégories, {sc_count} sous-catégories, {det_count} détails créés."
        ))
        self.stdout.write(
            "Allez dans Django Admin > Récupérateurs > [choisir un récupérateur] "
            "> champ 'Spécialisation' pour cocher les types de déchets qui le concernent."
        )
