"""
Complète la hiérarchie créée par `seed_specialisation` : lie les codes de
nomenclature réglementaires (Décret 06-104) aux détails de la sous-catégorie
"Déchets d'emballage", puis assigne ces détails à tous les récupérateurs.

Sans ça, la page Traçabilité affiche "Aucune catégorie ne vous a été
assignée" pour tout récupérateur — `seed_specialisation` crée la hiérarchie
mais ne lie aucun code et n'assigne rien (ces deux étapes étaient prévues
pour être faites à la main dans Django Admin, ce qui n'a jamais été fait).
Les codes d'emballage (15.01.01 à 15.01.08) couvrent exactement les
articles de "Mon catalogue" (Nomenclature > Mon catalogue).

Exécution : python manage.py seed_specialisation_default
(lance seed_specialisation automatiquement si la hiérarchie n'existe pas encore)

Idempotent — relancer ne crée pas de doublons.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand
from apps.nomenclature.models import Nomenclature
from apps.recuperateurs.models import Recuperateur
from apps.recuperateurs.models_specialisation import DetailSpecialisation

# Détail de "Déchets d'emballage" (nom tel que créé par seed_specialisation)
# -> code(s) Nomenclature correspondant (Décret 06-104, famille 15 - Emballages).
DETAIL_TO_CODES = {
    'PET':            ['15.01.02'],
    'PEHD':           ['15.01.02'],
    'PP':             ['15.01.02'],
    'Films':          ['15.01.02'],
    'Papier/carton':  ['15.01.01'],
    'Verre':          ['15.01.05'],
    'Alu':            ['15.01.04'],
    'Acier':          ['15.01.04'],
    'Bois':           ['15.01.03'],
    'Textile':        ['15.01.07'],
    'Composites':     ['15.01.06'],
    'Mélange':        ['15.01.08'],
}


class Command(BaseCommand):
    help = "Lie les codes d'emballage à la spécialisation et l'assigne à tous les récupérateurs"

    def handle(self, *args, **options):
        if not DetailSpecialisation.objects.filter(sous_categorie__nom="Déchets d'emballage").exists():
            self.stdout.write("Hiérarchie de spécialisation absente — lancement de seed_specialisation...")
            call_command('seed_specialisation')

        details = DetailSpecialisation.objects.filter(sous_categorie__nom="Déchets d'emballage")
        linked = 0
        for detail in details:
            codes = DETAIL_TO_CODES.get(detail.nom)
            if not codes:
                continue
            detail.codes_nomenclature.set(Nomenclature.objects.filter(code__in=codes))
            linked += 1

        assignable = details.filter(codes_nomenclature__isnull=False).distinct()
        recup_count = 0
        for recuperateur in Recuperateur.objects.all():
            recuperateur.specialisation_details.add(*assignable)
            recup_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"{linked} détail(s) d'emballage lié(s) à un code nomenclature, "
            f"assignés à {recup_count} récupérateur(s)."
        ))
