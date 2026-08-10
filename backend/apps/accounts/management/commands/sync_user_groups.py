"""
Management command to sync all existing users' Django Group membership
to match their current `role` field.

Run with:
    docker compose exec backend python manage.py sync_user_groups

Background:
    Previously, when users were created with the RECUPERATEUR role (or any role),
    they were not automatically added to the corresponding Django Group
    (e.g. 'recuperateur'). This command fixes all existing users.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

ROLE_TO_GROUP = {
    'SUPERADMIN': 'super_administrateur',
    'ADMIN': 'administrateur',
    'RECUPERATEUR': 'recuperateur',
    'RESPONSABLE_COLLECTE': 'responsable_collecte',
    'AGENT_COLLECTE': 'agent_collecte',
    'RESPONSABLE_DECHARGE': 'responsable_decharge',
    'OBSERVATEUR': 'observateur',
}


def sync_user_groups(user, dry_run=False):
    """Sync a single user's groups based on their role. Returns True if changed."""
    expected_group_name = ROLE_TO_GROUP.get(user.role)
    current_groups = set(user.groups.values_list('name', flat=True))

    if expected_group_name is None:
        # No expected group — user should have no groups
        if current_groups:
            if not dry_run:
                user.groups.clear()
            return True
        return False

    if expected_group_name in current_groups and len(current_groups) == 1:
        return False  # Already correct

    if not dry_run:
        user.groups.clear()
        group, _ = Group.objects.get_or_create(name=expected_group_name)
        user.groups.add(group)

    return True


class Command(BaseCommand):
    help = 'Sync Django group membership for all users based on their role field'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate without making any changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total = User.objects.count()
        fixed = 0
        already_ok = 0

        self.stdout.write(f"🔍 Vérification de {total} utilisateur(s)...")
        if dry_run:
            self.stdout.write(self.style.WARNING("   Mode DRY-RUN — aucune modification"))

        for user in User.objects.iterator():
            changed = sync_user_groups(user, dry_run=dry_run)
            if changed:
                fixed += 1
                self.stdout.write(
                    f"   {'⚡' if not dry_run else '○'} {user.username} "
                    f"(rôle: {user.role}) → groupe: {ROLE_TO_GROUP.get(user.role, '—')}"
                )
            else:
                already_ok += 1

        self.stdout.write("\n" + "=" * 50)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"  DRY-RUN terminé : {fixed} utilisateur(s) À corriger, "
                f"{already_ok} déjà correct(s)"
            ))
            self.stdout.write("  Relancez SANS --dry-run pour appliquer les changements.")
        else:
            if fixed > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ {fixed} utilisateur(s) corrigé(s) — groupes synchronisés"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    "  ✅ Tous les utilisateurs sont déjà corrects"
                ))
            self.stdout.write(self.style.SUCCESS(
                f"  📊 Total : {total} utilisateur(s) — {already_ok} déjà OK — {fixed} corrigé(s)"
            ))
