"""
Backup the database.

Supports both SQLite (file copy) and PostgreSQL (pg_dump).
Backups are saved to BACKUP_DIR (default: <BASE_DIR>/backups/).
"""
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée une sauvegarde de la base de données."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='',
            help='Répertoire de sortie (défaut: <BASE_DIR>/backups/)',
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            default=False,
            help='Compresser le fichier de sauvegarde avec gzip',
        )

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        engine = db['ENGINE']

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        output_dir = Path(options['output_dir']) if options['output_dir'] else settings.BASE_DIR / 'backups'
        output_dir.mkdir(parents=True, exist_ok=True)

        if 'sqlite' in engine:
            self._backup_sqlite(db, output_dir, timestamp, options['compress'])
        elif 'postgresql' in engine:
            self._backup_postgresql(db, output_dir, timestamp, options['compress'])
        else:
            raise CommandError(f"Moteur de base non supporté: {engine}")

    def _backup_sqlite(self, db, output_dir, timestamp, compress):
        db_path = Path(db['NAME'])
        if not db_path.exists():
            raise CommandError(f"Base SQLite introuvable: {db_path}")

        dest = output_dir / f'backup_{timestamp}.sqlite3'
        shutil.copy2(str(db_path), str(dest))

        if compress:
            import gzip
            gz_path = dest.with_suffix(dest.suffix + '.gz')
            with open(dest, 'rb') as f_in:
                with gzip.open(str(gz_path), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            dest.unlink()
            dest = gz_path

        self.stdout.write(self.style.SUCCESS(
            f"Sauvegarde SQLite créée: {dest} ({dest.stat().st_size / 1024:.1f} Ko)"
        ))

    def _backup_postgresql(self, db, output_dir, timestamp, compress):
        pg_dump = shutil.which('pg_dump')
        if not pg_dump:
            raise CommandError("pg_dump introuvable. Installez postgresql-client.")

        filename = f'backup_{timestamp}.sql'
        dest = output_dir / filename

        env = {
            'PGHOST': db.get('HOST', 'localhost'),
            'PGPORT': str(db.get('PORT', '5432')),
            'PGUSER': db.get('USER', ''),
            'PGPASSWORD': db.get('PASSWORD', ''),
        }

        cmd = [
            pg_dump,
            '--dbname', db['NAME'],
            '--format', 'plain',
            '--no-owner',
            '--no-privileges',
            '--file', str(dest),
        ]

        try:
            result = subprocess.run(
                cmd, env={**env, **dict(__import__('os').environ)},
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                raise CommandError(f"pg_dump a échoué:\n{result.stderr}")
        except FileNotFoundError:
            raise CommandError("pg_dump introuvable. Installez postgresql-client.")
        except subprocess.TimeoutExpired:
            raise CommandError("pg_dump a dépassé le délai de 5 minutes.")

        if compress:
            import gzip
            gz_path = dest.with_suffix('.sql.gz')
            with open(dest, 'rb') as f_in:
                with gzip.open(str(gz_path), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            dest.unlink()
            dest = gz_path

        self.stdout.write(self.style.SUCCESS(
            f"Sauvegarde PostgreSQL créée: {dest} ({dest.stat().st_size / 1024:.1f} Ko)"
        ))
