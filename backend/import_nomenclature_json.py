"""
Import nomenclature codes and annexes from nomenclature_dechets.json
Usage: python import_nomenclature_json.py /path/to/nomenclature_dechets.json
"""
import os, sys, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.nomenclature.models import Nomenclature

json_path = sys.argv[1] if len(sys.argv) > 1 else '/Users/imanebenmoussa/Downloads/nomenclature_dechets.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

CODE_KEY = "قائمة النفايات - Liste des Déchets / Décret exécutif n° 06-104 du 28 février 2006"

created = 0
updated = 0
skipped = 0

for item in data:
    raw_code = item.get(CODE_KEY, '').strip()
    annexe = item.get('', '').strip()

    # Skip header row
    if not raw_code or raw_code.startswith("قائمة") or raw_code.startswith("Code"):
        continue

    # Normalize code: zero-pad
    parts = raw_code.split('.')
    if len(parts) != 3:
        skipped += 1
        continue
    try:
        code = f"{int(parts[0]):02d}.{int(parts[1]):02d}.{int(parts[2]):02d}"
    except ValueError:
        skipped += 1
        continue

    # Update existing or create new
    obj, was_created = Nomenclature.objects.update_or_create(
        code=code,
        defaults={
            'annexe': annexe,
        }
    )
    if was_created:
        created += 1
    else:
        updated += 1

total = Nomenclature.objects.count()
print(f'✅ Import JSON: {created} créés, {updated} mis à jour, {skipped} ignorés')
print(f'   Total en base : {total} codes')
print(f'   Codes avec annexe II: {Nomenclature.objects.filter(annexe="II").count()}')
print(f'   Codes avec annexe III: {Nomenclature.objects.filter(annexe="III").count()}')
