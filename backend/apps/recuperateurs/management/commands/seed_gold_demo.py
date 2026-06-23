"""
Crée un compte récupérateur de démonstration complet — SARL Gold Environment.
Permet de tester toutes les fonctionnalités : profil, agrément, spécialisation
(donc le filtrage de la nomenclature), et servir de point de départ pour créer
des opérations, BSD, déclarations, etc. depuis l'interface.

Exécution : python manage.py seed_gold_demo

Idempotent — relancer met juste à jour le compte existant au lieu de planter.
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.recuperateurs.models import Recuperateur, AgrementRecuperateur
from apps.recuperateurs.models_specialisation import DetailSpecialisation

User = get_user_model()


class Command(BaseCommand):
    help = "Crée le compte de démonstration SARL Gold Environment (admin_gold / Gold2024!)"

    def handle(self, *args, **options):
        # ── 1. Compte utilisateur ────────────────────────────────────────────
        user, created = User.objects.get_or_create(
            username='admin_gold',
            defaults={
                'email': 'contact@goldenvironment.dz',
                'first_name': 'Karim',
                'last_name': 'Boudiaf',
                'role': 'RECUPERATEUR',
                'phone': '0555123456',
                'wilaya': '16',
            }
        )
        user.set_password('Gold2024!')
        user.role = 'RECUPERATEUR'
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'✅ Compte créé' if created else 'ℹ️  Compte mis à jour'} : admin_gold / Gold2024!"
        ))

        # ── 2. Fiche récupérateur ────────────────────────────────────────────
        recuperateur, created = Recuperateur.objects.get_or_create(
            user=user,
            defaults={
                'type_recuperateur': 'AVEC_AGREMENT',
                'statut_juridique': 'SARL',
                'nom_raison_sociale': 'SARL Gold Environment',
                'nom_commercial': 'Gold Environment',
                'responsable': 'Karim Boudiaf',
                'registre_commerce': '16/00-1234567B25',
                'nif': '000216123456789',
                'nis': '216123456789012',
                'adresse': "Zone Industrielle Oued Smar, Lot N°45",
                'wilaya': '16',
                'commune': 'Oued Smar',
                'code_postal': '16270',
                'telephone': '0555123456',
                'email': 'contact@goldenvironment.dz',
                'site_web': 'https://goldenvironment.dz',
                'statut': 'ACTIF',
                'date_creation': date(2022, 3, 15),
                'notes': 'Compte de démonstration créé automatiquement pour tests fonctionnels.',
            }
        )
        if not created:
            # Met à jour les champs clés si la fiche existait déjà
            recuperateur.nom_raison_sociale = 'SARL Gold Environment'
            recuperateur.statut = 'ACTIF'
            recuperateur.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'✅ Fiche créée' if created else 'ℹ️  Fiche mise à jour'} : {recuperateur.nom_raison_sociale} "
            f"({recuperateur.numero_id})"
        ))

        # ── 3. Agrément valide (5 ans, encore actif) ────────────────────────
        agrement, created = AgrementRecuperateur.objects.get_or_create(
            recuperateur=recuperateur,
            numero_agrement='AGR-16-2023-0456',
            defaults={
                'type_agrement': 'AVEC_AGREMENT',
                'date_delivrance': date(2023, 6, 1),
                'duree_validite_ans': 5,
                'date_debut': date(2023, 6, 1),
                'date_fin': date(2028, 6, 1),
                'etendue_geo': 'WILAYAS',
                'wilayas_couvertes': '16,09,35,42',
                'codes_dechets': '',  # legacy — le filtrage se fait maintenant par spécialisation
                'statut': 'ACTIF',
                'autorite_delivrance': "Direction de l'Environnement de la Wilaya d'Alger",
                'observations': "Agrément de démonstration — valide jusqu'en 2028.",
            }
        )
        self.stdout.write(self.style.SUCCESS(
            f"{'✅ Agrément créé' if created else 'ℹ️  Agrément déjà présent'} : {agrement.numero_agrement} "
            f"(valide jusqu'au {agrement.date_fin})"
        ))

        # ── 4. Spécialisation — coche plusieurs détails pour tester le filtrage
        #     de la nomenclature sur plusieurs classes à la fois (S, SD, MA) ──
        noms_a_cocher = [
            'Chimique', 'Solvants', 'Traitement de surface',  # → SD
            'Huiles', 'DEEE', 'Pneumatiques',                 # → S
            'PET', 'PEHD', 'Papier/carton',                   # → MA
        ]
        details = DetailSpecialisation.objects.filter(nom__in=noms_a_cocher)
        if details.exists():
            recuperateur.specialisation_details.set(details)
            classes = sorted(set(details.values_list('classe_nomenclature', flat=True)))
            self.stdout.write(self.style.SUCCESS(
                f"✅ Spécialisation assignée : {details.count()} détail(s) coché(s) "
                f"couvrant les classes {classes}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "⚠️  Aucun détail de spécialisation trouvé — lancez d'abord "
                "`python manage.py seed_specialisation`."
            ))

        self.stdout.write(self.style.SUCCESS(
            "\n=== Compte de démonstration prêt ===\n"
            "Connexion : admin_gold / Gold2024!\n"
            "Rôle : RECUPERATEUR — toutes les pages métier sont accessibles.\n"
            "La page Nomenclature affichera, avec le filtre activé, les codes "
            "MA + S + SD correspondant à la spécialisation cochée ci-dessus."
        ))
