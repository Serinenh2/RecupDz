from django.db import migrations


def assigner_operateurs_existants(apps, schema_editor):
    """
    Avant cette migration, Operateur n'avait pas de propriétaire — tous les
    opérateurs créés (par n'importe quel récupérateur) étaient visibles par
    tout le monde. On rattache les opérateurs déjà créés au récupérateur qui
    les a effectivement saisis (déduit via les dossiers de traçabilité qui les
    référencent), pour qu'ils ne soient plus visibles que par lui désormais.
    Les opérateurs qu'on n'arrive pas à rattacher restent partagés (NULL).
    """
    Operateur = apps.get_model('operateurs', 'Operateur')
    Traceability = apps.get_model('traceability', 'Traceability')

    for operateur in Operateur.objects.filter(recuperateur__isnull=True):
        dossier = (
            Traceability.objects.filter(generateur=operateur)
            .exclude(recuperateur__isnull=True).first()
            or Traceability.objects.filter(transporteur=operateur)
            .exclude(recuperateur__isnull=True).first()
            or Traceability.objects.filter(valorisateur=operateur)
            .exclude(recuperateur__isnull=True).first()
            or Traceability.objects.filter(eliminateur=operateur)
            .exclude(recuperateur__isnull=True).first()
            or Traceability.objects.filter(cet=operateur)
            .exclude(recuperateur__isnull=True).first()
        )
        if dossier:
            operateur.recuperateur_id = dossier.recuperateur_id
            operateur.save(update_fields=['recuperateur'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('operateurs', '0003_operateur_recuperateur'),
        ('traceability', '0004_traceability_cet_traceability_quantite_enfouie_and_more'),
    ]

    operations = [
        migrations.RunPython(assigner_operateurs_existants, noop),
    ]
