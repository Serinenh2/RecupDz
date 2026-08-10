"""
Restore the database from a backup.

Supports both SQLite (file copy) and PostgreSQL (psql).
"""
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Restaure la base de données à partir d'une sauvegarde."

    def add_arguments(self, parser):
        parser.add_argument('backup_file', type=str, help='Chemin du fichier de sauvegarde')
        parser.add_argument(
            '--no-confirm',
            action='store_true',
            default=False,
            help='Restaurer sans demander de confirmation',
        )

    def handle(self, *args, **options):
        backup_path = Path(options['backup_file'])
        if not backup_path.exists():
            raise CommandError(f"Fichier introuvable: {backup_path}")

        db = settings.DATABASES['default']
        engine = db['ENGINE']

        if not options['no_confirm']:
            self.stdout.write(self.style.WARNING(
                f"⚠ Ceci va ÉCRASER la base de données actuelle.\n"
                f"  Base: {db.get('NAME', 'N/A')}\n"
                f"  Backup: {backup_path}\n"
            ))
            confirm = input("Tapez 'oui' pour confirmer: ")
            if confirm.lower() != 'oui':
                self.stdout.write("Annulé.")
                return

        if 'sqlite' in engine:
            self._restore_sqlite(db, backup_path)
        elif 'postgresql' in engine:
            self._restore_postgresql(db, backup_path)
        else:
            raise CommandError(f"Moteur de base non supporté: {engine}")

    def _restore_sqlite(self, db, backup_path):
        db_path = Path(db['NAME'])

        if backup_path.suffix == '.gz':
            import gzip
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(str(backup_path), 'rb') as f_in:
                with open(str(db_path), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(str(backup_path), str(db_path))

        self.stdout.write(self.style.SUCCESS(
            f"Base SQLite restaurée: {db_path}"
        ))

    def _restore_postgresql(self, db, backup_path):
        psql = shutil.which('psql')
        if not psql:
            raise CommandError("psql introuvable. Installez postgresql-client.")

        is_gz = str(backup_path).endswith('.gz')

        env = {
            'PGHOST': db.get('HOST', 'localhost'),
            'PGPORT': str(db.get('PORT', '5432')),
            'PGUSER': db.get('USER', ''),
            'PGPASSWORD': db.get('PASSWORD', ''),
        }

        if is_gz:
            import gzip
            import subprocess as sp
            with gzip.open(str(backup_path), 'rb') as f:
                proc = sp.run(
                    [psql, '--dbname', db['NAME'], '--no-owner'],
                    stdin=f, capture_output=True, text=True, env={**env, **dict(__import__('os').environ)},
                    timeout=600,
                )
        else:
            cmd = [
                psql,
                '--dbname', db['NAME'],
                '--no-owner',
                '--file', str(backup_path),
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                env={**env, **dict(__import__('os').environ)},
                timeout=600,
            )

        if proc.returncode != 0:
            raise CommandError(f"psql a échoué:\n{proc.stderr}")

        self.stdout.write(self.style.SUCCESS(
            f"Base PostgreSQL restaurée depuis: {backup_path}"
        ))
