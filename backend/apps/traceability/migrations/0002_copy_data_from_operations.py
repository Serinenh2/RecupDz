from django.db import migrations

COLUMNS = [
    'id', 'numero', 'bon_livraison', 'date_livraison', 'bon_commande',
    'commande_client', 'date_commande', 'code_dechet', 'designation_dechet',
    'classe_dechet', 'unite', 'quantite', 'chauffeur', 'immatriculation',
    'date_recuperation', 'destination_type', 'bsd_numero', 'statut',
    'observations', 'created_at', 'updated_at', 'created_by_id',
    'eliminateur_id', 'generateur_id', 'recuperateur_id', 'transporteur_id',
    'valorisateur_id',
]


def copy_forward(apps, schema_editor):
    """Copie les dossiers existants de l'app 'operations' (en cours de
    retrait) vers la nouvelle app 'traceability', en conservant les ids
    pour preserver l'historique et toute reference externe (ex: assistant IA).
    """
    connection = schema_editor.connection
    if connection.alias != 'default':
        return
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        if 'operations_operationrecuperation' not in tables:
            return
        cols = ', '.join(COLUMNS)
        cursor.execute(f"SELECT {cols} FROM operations_operationrecuperation")
        rows = cursor.fetchall()
        if not rows:
            return
        placeholders = ', '.join(['%s'] * len(COLUMNS))
        cursor.executemany(
            f"INSERT INTO traceability_traceability ({cols}) VALUES ({placeholders})",
            rows,
        )


def copy_backward(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM traceability_traceability")


class Migration(migrations.Migration):

    # Anciennement dependante de l'app 'operations' (depuis supprimee une
    # fois sa table copiee et son modele detruit). La dependance croisee a
    # ete retiree pour ne pas casser le graphe de migrations sur une
    # installation fraiche ; copy_forward() reste defensif (no-op si la
    # table source n'existe plus).
    dependencies = [
        ('traceability', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(copy_forward, copy_backward),
    ]
