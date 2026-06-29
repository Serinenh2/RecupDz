"""
Génération du document Word (.docx) du Bon de Livraison (BL).
Contenu équivalent au PDF, présenté de façon simple et imprimable sous Word.
"""
import io
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _section(doc, texte):
    p = doc.add_paragraph()
    run = p.add_run(texte)
    run.bold = True
    run.font.size = Pt(12)


def _champ(doc, label, valeur):
    p = doc.add_paragraph()
    r1 = p.add_run(f"{label} : ")
    r1.bold = True
    p.add_run(str(valeur) if valeur else '—')


def generate_bl_docx(data: dict) -> bytes:
    doc = Document()
    doc.add_heading('BON DE LIVRAISON', level=1).alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    _champ(doc, 'N° Bon de livraison', data.get('numero'))
    _champ(doc, 'Date de livraison', data.get('date_livraison'))
    _champ(doc, 'Bon de commande N°', data.get('bon_commande_numero'))
    _champ(doc, 'Date de commande', data.get('date_commande'))
    _champ(doc, 'Statut', data.get('statut_display') or data.get('statut'))

    doc.add_paragraph()
    _section(doc, 'Émetteur')
    _champ(doc, 'Récupérateur', data.get('recuperateur_nom'))

    doc.add_paragraph()
    _section(doc, f"Destinataire ({data.get('destinataire_type_display') or data.get('destinataire_type','')})")
    _champ(doc, 'Raison sociale', data.get('destinataire_nom'))

    doc.add_paragraph()
    _section(doc, 'Désignation des marchandises')
    table = doc.add_table(rows=1, cols=5)
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    for i, h in enumerate(['Désignation', 'Référence', 'Conditionnement', 'Qté Box', 'Qté Préforme']):
        hdr[i].text = h
    for ligne in (data.get('lignes') or []):
        row = table.add_row().cells
        row[0].text = str(ligne.get('designation', ''))
        row[1].text = str(ligne.get('reference', ''))
        row[2].text = str(ligne.get('conditionnement', ''))
        row[3].text = str(ligne.get('qte_box', ''))
        row[4].text = str(ligne.get('qte_preforme', ''))

    doc.add_paragraph()
    _section(doc, 'Établi par')
    _champ(doc, 'Magasinier', data.get('etabli_par'))

    doc.add_paragraph()
    _section(doc, 'Qualité')
    qualite = data.get('qualite') or {}
    for cle, lbl in [('chauffeur','Chauffeur'), ('sgt','SGT'), ('maraicher','Maraîcher'),
                      ('bacher','Bacher'), ('proprete','Propreté')]:
        _champ(doc, lbl, qualite.get(cle))
    _champ(doc, 'Garantie aptitude au contact alimentaire', 'Oui' if data.get('garantie_alimentaire') else 'Non')

    doc.add_paragraph()
    _section(doc, 'Visa de Chauffeur')
    _champ(doc, 'Chauffeur', data.get('chauffeur_nom'))
    _champ(doc, 'Camion', data.get('camion_numero'))
    _champ(doc, 'Immatriculation', data.get('camion_immatriculation'))

    if data.get('observations'):
        doc.add_paragraph()
        _section(doc, 'Observations')
        doc.add_paragraph(data.get('observations'))

    for section in doc.sections:
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()
