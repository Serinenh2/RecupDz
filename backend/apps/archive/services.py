from django.core.files.base import ContentFile
from .models import Document


def archive_document(source_app_label, source_id, numero, categorie, label, pdf_bytes, dossier_id, user):
    """Crée ou met à jour (idempotent) la copie archivée d'un document validé.

    Le rapprochement se fait via un tag 'source:<app_label>:<id>' plutôt
    qu'une FK : cela évite de coupler le modèle Document générique (utilisé
    aussi pour les imports manuels) au schéma de bc/bl, et permet de mettre à
    jour la même copie si le document est re-validé après une modification.
    """
    source_tag = f"source:{source_app_label}:{source_id}"
    tags = f"dossier:{dossier_id},{source_tag}"
    fichier = ContentFile(pdf_bytes, name=f"{numero}.pdf")

    doc = Document.objects.filter(tags__contains=source_tag).first()
    if doc:
        doc.titre = f"{label} {numero}"
        doc.categorie = categorie
        doc.tags = tags
        doc.fichier = fichier
        doc.nom_original = fichier.name
        doc.taille = len(pdf_bytes)
        doc.type_mime = 'application/pdf'
        doc.save()
        return doc

    return Document.objects.create(
        titre=f"{label} {numero}",
        categorie=categorie,
        fichier=fichier,
        nom_original=fichier.name,
        taille=len(pdf_bytes),
        type_mime='application/pdf',
        tags=tags,
        uploaded_by=user,
    )
