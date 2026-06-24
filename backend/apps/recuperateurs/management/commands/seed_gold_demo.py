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
from django.contrib.auth.models import Group
from apps.recuperateurs.models import Recuperateur, AgrementRecuperateur
from apps.recuperateurs.models_specialisation import DetailSpecialisation
from apps.nomenclature.models import Nomenclature

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

        # Assigne le groupe RBAC 'recuperateur' (créé par `setup_rbac`) — indispensable
        # pour que les permissions (et donc les pages visibles côté frontend) fonctionnent.
        # Fait directement ici plutôt que d'attendre un futur passage de `setup_rbac`,
        # qui ne migre que les utilisateurs déjà existants au moment où il est lancé.
        try:
            group = Group.objects.get(name='recuperateur')
            user.groups.add(group)
            self.stdout.write(self.style.SUCCESS("✅ Groupe RBAC 'recuperateur' assigné"))
        except Group.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                "⚠️  Groupe 'recuperateur' introuvable — lancez d'abord "
                "`python manage.py setup_rbac`, puis relancez cette commande."
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

        # ── 4. Spécialisation — coche les détails MA (emballage) pour tester
        #     le type "Déchets ménagers". La structure officielle "Déchets
        #     spéciaux et spéciaux dangereux" (38 sections du Décret 06-104)
        #     est assignée séparément par `seed_gold_agrement_excel`, qui
        #     remplace les anciens détails génériques SD/S (Chimique, Solvants...).
        noms_a_cocher = [
            'PET', 'PEHD', 'PP', 'Films',                     # → MA (emballage plastique)
            'Papier/carton', 'Verre', 'Alu', 'Acier',         # → MA (emballage autres matières)
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

        # ── 5. Cascade spécifique à Gold Environment — relie chacun des 8 détails
        #     de la sous-catégorie "Déchets d'emballage" (PET, PEHD, PP, Films,
        #     Papier/carton, Verre, Alu, Acier) à SON code précis 15.01.xx.
        #     C'est CETTE relation (M2M codes_nomenclature) qui permet d'avoir
        #     un mapping différent par récupérateur — un autre récupérateur
        #     pourrait avoir les mêmes détails cochés mais liés à d'autres codes.
        mapping_emballage = [
            ('PET',           '15.01.02'),  # plastique
            ('PEHD',          '15.01.02'),  # plastique
            ('PP',            '15.01.02'),  # plastique
            ('Films',         '15.01.02'),  # plastique
            ('Papier/carton', '15.01.01'),
            ('Verre',         '15.01.07'),
            ('Alu',           '15.01.04'),  # metallique
            ('Acier',         '15.01.04'),  # metallique
        ]
        cascade_ok = 0
        for nom_detail, code in mapping_emballage:
            detail = DetailSpecialisation.objects.filter(nom=nom_detail).first()
            code_obj = Nomenclature.objects.filter(code=code).first()
            if detail and code_obj:
                detail.codes_nomenclature.add(code_obj)
                cascade_ok += 1
        if cascade_ok:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Cascade configurée : {cascade_ok} détail(s) d'emballage liés "
                f"à leurs codes nomenclature (15.01.01 à 15.01.08)"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "⚠️  Aucune cascade configurée — vérifiez que `seed_specialisation` "
                "et la mise à jour de `setup.py` (codes 15.01.xx) ont bien été lancés."
            ))

        self.stdout.write(self.style.SUCCESS(
            "\n=== Compte de démonstration prêt ===\n"
            "Connexion : admin_gold / Gold2024!\n"
            "Rôle : RECUPERATEUR — toutes les pages métier sont accessibles.\n"
            "La page Nomenclature affichera, avec le filtre activé, les codes "
            "MA + S + SD correspondant à la spécialisation cochée ci-dessus."
        ))
