"""
Migre les 8 articles de "Mon catalogue" (jusqu'ici codés en dur dans le
frontend, frontend/src/pages/nomenclature/nomenclatureEntreprise.js) vers la
base de données, rattachés au récupérateur SARL Indurex (admin_indurex).

Nécessaire suite au passage de "Mon catalogue" d'une liste statique à un
catalogue géré par chaque récupérateur (CatalogueEntreprise, CRUD via l'app).

Idempotent — relancer ne crée pas de doublons (get_or_create sur
recuperateur + reference).
"""
from django.core.management.base import BaseCommand
from apps.nomenclature.models import Nomenclature, CatalogueEntreprise
from apps.recuperateurs.models import Recuperateur

DATA = [
    ('Palette de PEHD',       'COMPALPEHD',     'Kilogramme', '15.01.02'),
    ('Palette Bois Rebut',    'PALETTE_REB',    'Unité',      '15.01.03'),
    ('Cartons déchets',       'REBUTS_CARTONS', 'Kilogramme', '15.01.01'),
    ('Les Saches Usagées',    'SACHE-USE',      'Kilogramme', '15.01.02'),
    ('Rebuts Matière PET',    'REB_MAT_PET',    'Kilogramme', '15.01.02'),
    ('Ceinture carton Rebut', 'CEINCAR_REB',    'Kilogramme', '15.01.01'),
    ('BigBag',                'COMBIGBAG',      'Unité',      '15.01.02'),
    ('Mandrins Rebut',        'MANDRINS_REB',   'Unité',      '15.01.01'),
]


class Command(BaseCommand):
    help = "Crée les 8 articles de Mon catalogue pour SARL Indurex (admin_indurex)"

    def handle(self, *args, **options):
        try:
            recuperateur = Recuperateur.objects.get(user__username='admin_indurex')
        except Recuperateur.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                "Récupérateur admin_indurex introuvable — rien à faire."
            ))
            return

        created = 0
        for designation, reference, conditionnement, code in DATA:
            nomenclature = Nomenclature.objects.filter(code=code).first()
            obj, was_created = CatalogueEntreprise.objects.get_or_create(
                recuperateur=recuperateur,
                reference=reference,
                defaults={
                    'designation': designation,
                    'conditionnement': conditionnement,
                    'nomenclature': nomenclature,
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"{created} article(s) créé(s) dans le catalogue de {recuperateur.nom_raison_sociale}."
        ))
