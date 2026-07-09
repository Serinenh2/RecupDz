import uuid
from django.db import migrations


def fix_shared_dossier_id_default(apps, schema_editor):
    """Migration 0009/0008 added `dossier_id` with a callable default
    (uuid.uuid4), but Django's AddField backfill evaluates that default
    ONCE for the whole bulk update on existing rows — so every pre-existing
    root document ended up sharing the same UUID instead of getting its own.
    Give each true root document (no origin at all) a fresh unique id, then
    re-run the chain propagation so generated documents inherit correctly.
    """
    BonCommande  = apps.get_model('bc', 'BonCommande')
    BonLivraison = apps.get_model('bl', 'BonLivraison')

    for bc in BonCommande.objects.filter(proforma_origine__isnull=True, bon_livraison_origine__isnull=True):
        bc.dossier_id = uuid.uuid4()
        bc.save(update_fields=['dossier_id'])

    for bl in BonLivraison.objects.filter(bon_commande_origine__isnull=True):
        bl.dossier_id = uuid.uuid4()
        bl.save(update_fields=['dossier_id'])

    for bc in BonCommande.objects.filter(proforma_origine__isnull=False):
        bc.dossier_id = bc.proforma_origine.dossier_id
        bc.save(update_fields=['dossier_id'])

    for bl in BonLivraison.objects.filter(bon_commande_origine__isnull=False):
        bl.dossier_id = bl.bon_commande_origine.dossier_id
        bl.save(update_fields=['dossier_id'])

    for fa in BonCommande.objects.filter(bon_livraison_origine__isnull=False):
        fa.dossier_id = fa.bon_livraison_origine.dossier_id
        fa.save(update_fields=['dossier_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('bc', '0010_backfill_dossier_id'),
    ]

    operations = [
        migrations.RunPython(fix_shared_dossier_id_default, migrations.RunPython.noop),
    ]
