from django.db import migrations


def backfill_dossier_id(apps, schema_editor):
    BonCommande  = apps.get_model('bc', 'BonCommande')
    BonLivraison = apps.get_model('bl', 'BonLivraison')

    # Propagate in chain order so each generation inherits its origin's
    # dossier_id (each row got an independent random UUID when the field
    # was added — this unifies rows that already belong to the same chain).
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
        ('bc', '0009_boncommande_dossier_id'),
        ('bl', '0008_bonlivraison_dossier_id'),
    ]

    operations = [
        migrations.RunPython(backfill_dossier_id, migrations.RunPython.noop),
    ]
