"""
Django's `createsuperuser` only sets the fields it knows about (username,
email, password, is_staff, is_superuser) — it has no idea about our custom
`role` field, which isn't in REQUIRED_FIELDS. So every account created via
`createsuperuser --noinput` (including the one the `migrate` service creates
on every fresh deploy) silently lands on the model's default: role=OBSERVATEUR,
with no permissions and no Django group — despite is_superuser=True.

Run with:
    docker compose exec backend python manage.py fix_superuser_role

Idempotent — safe to run on every deploy. Promotes every is_superuser=True
account whose role isn't already SUPERADMIN/ADMIN.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Ensure every is_superuser=True account has role=SUPERADMIN"

    def handle(self, *args, **options):
        fixed = 0
        for user in User.objects.filter(is_superuser=True).exclude(role__in=['SUPERADMIN', 'ADMIN']):
            user.role = 'SUPERADMIN'
            user.save(update_fields=['role'])
            fixed += 1
            self.stdout.write(f"   ⚡ {user.username}: role -> SUPERADMIN")

        if fixed:
            self.stdout.write(self.style.SUCCESS(f"✅ {fixed} compte(s) superadmin corrigé(s)"))
        else:
            self.stdout.write(self.style.SUCCESS("✅ Tous les comptes superadmin ont déjà le bon rôle"))
