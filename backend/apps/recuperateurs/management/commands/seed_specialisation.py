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

DATA = [
    {
        "nom": "Déchets ménagers et assimilés", "icone": "🏠",
        "sous_categories": [
            {"nom": "Déchets organiques", "details": ["Alimentaire", "Végétal"]},
            {"nom": "Déchets d'emballage", "details": [
                "PET", "PEHD", "PP", "Films", "Papier/carton", "Verre", "Alu", "Acier",
            ]},
            {"nom": "Textiles et cuirs", "details": []},
            {"nom": "Encombrants ménagers", "details": []},
        ],
    },
    {
        "nom": "Déchets inertes", "icone": "🧱",
        "sous_categories": [
            {"nom": "Construction et démolition", "details": [
                "Béton", "Briques", "Gravats", "Sable/argile", "Démolition mélangée",
            ]},
            {"nom": "Miniers et de forage", "details": []},
        ],
    },
    {
        "nom": "Déchets spéciaux et spéciaux dangereux", "icone": "⚠️",
        "sous_categories": [
            {"nom": "Industriels spéciaux", "details": [
                "Chimique", "Solvants", "Peintures", "Traitement de surface",
            ]},
            {"nom": "Hydrocarbures", "details": [
                "Huiles", "Boues pétrolières", "Hydrocarbures répandus",
            ]},
            {"nom": "Médicaux et infectieux", "details": []},
            {"nom": "Électroniques et batteries", "details": ["DEEE", "Piles"]},
            {"nom": "Pneumatiques", "details": []},
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

                for det_ordre, det_nom in enumerate(sc_data["details"]):
                    detail, created = DetailSpecialisation.objects.get_or_create(
                        sous_categorie=sous_categorie, nom=det_nom,
                        defaults={"ordre": det_ordre},
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
