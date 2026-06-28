"""
Crée un compte récupérateur SANS AGRÉMENT — SARL Indurex.
Sert à tester le parcours d'un récupérateur de déchets ordinaires
(Ménagers et Assimilés / Inertes) qui n'a pas besoin d'agrément
ni de spécialisation sur des codes Spéciaux/Spéciaux Dangereux.

Exécution : python manage.py seed_indurex_demo

Idempotent — relancer met juste à jour le compte existant au lieu de planter.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from apps.recuperateurs.models import Recuperateur

User = get_user_model()


class Command(BaseCommand):
    help = "Crée le compte récupérateur sans agrément SARL Indurex (admin_indurex / Indurex2026!)"

    def handle(self, *args, **options):
        # ── 1. Compte utilisateur ────────────────────────────────────────────
        user, created = User.objects.get_or_create(
            username='admin_indurex',
            defaults={
                'email': 'contact@indurex.dz',
                'first_name': 'Sami',
                'last_name': 'Belkacem',
                'role': 'RECUPERATEUR',
                'phone': '0550987654',
                'wilaya': '09',
            }
        )
        user.set_password('Indurex2026!')
        user.role = 'RECUPERATEUR'
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'✅ Compte créé' if created else 'ℹ️  Compte mis à jour'} : admin_indurex / Indurex2026!"
        ))

        # Assigne le groupe RBAC 'recuperateur' (créé par `setup_rbac`) —
        # indispensable pour que les permissions (et donc les pages visibles
        # côté frontend) fonctionnent.
        try:
            group = Group.objects.get(name='recuperateur')
            user.groups.add(group)
            self.stdout.write(self.style.SUCCESS("✅ Groupe RBAC 'recuperateur' assigné"))
        except Group.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                "⚠️  Groupe 'recuperateur' introuvable — lancez d'abord "
                "`python manage.py setup_rbac`, puis relancez cette commande."
            ))

        # ── 2. Fiche récupérateur — SANS AGRÉMENT ────────────────────────────
        recuperateur, created = Recuperateur.objects.get_or_create(
            user=user,
            defaults={
                'type_recuperateur': 'SANS_AGREMENT',
                'statut_juridique': 'SARL',
                'nom_raison_sociale': 'SARL Indurex',
                'nom_commercial': 'Indurex',
                'responsable': 'Sami Belkacem',
                'registre_commerce': '09/00-3344556C24',
                'nif': '000209334455667',
                'adresse': "Zone d'Activité Boufarik, Lot 8, Blida",
                'wilaya': '09',
                'commune': 'Boufarik',
                'code_postal': '09230',
                'telephone': '0550987654',
                'email': 'contact@indurex.dz',
                'statut': 'ACTIF',
                'notes': "Récupérateur sans agrément — déchets ordinaires (Ménagers et Assimilés / Inertes) uniquement.",
            }
        )
        if not created:
            recuperateur.type_recuperateur = 'SANS_AGREMENT'
            recuperateur.nom_raison_sociale = 'SARL Indurex'
            recuperateur.statut = 'ACTIF'
            recuperateur.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'✅ Fiche créée' if created else 'ℹ️  Fiche mise à jour'} : {recuperateur.nom_raison_sociale} "
            f"({recuperateur.numero_id}) — SANS AGRÉMENT"
        ))

        self.stdout.write(self.style.SUCCESS(
            "\n=== Compte SARL Indurex prêt ===\n"
            "Connexion : admin_indurex / Indurex2026!\n"
            "Type : Récupérateur SANS agrément — déchets ordinaires uniquement.\n"
            "Aucune spécialisation S/SD n'est assignée — la page Nomenclature filtrée\n"
            "ne montrera que les codes MA/I si une spécialisation MA est cochée\n"
            "manuellement depuis Django Admin (Récupérateurs > Indurex > Spécialisation)."
        ))