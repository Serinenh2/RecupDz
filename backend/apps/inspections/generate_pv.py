from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
import io

MOIS_FR = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

DOTS = '.' * 28


def _texte_date(date_str):
    """Convertit une date ISO (YYYY-MM-DD) en 'le JJ du mois de MOIS AAAA'."""
    if not date_str:
        return DOTS, DOTS
    try:
        annee, mois, jour = str(date_str).split('-')[:3]
        mois_nom = MOIS_FR[int(mois)]
        return f"{int(jour)}", f"{mois_nom} {annee}"
    except Exception:
        return DOTS, DOTS


def _fmt_date(iso):
    """Convertit une date ISO (YYYY-MM-DD) en JJ/MM/AAAA — inchangé si le format est différent."""
    if not iso:
        return ''
    parts = str(iso).split('-')
    if len(parts) != 3:
        return str(iso)
    y, m, d = parts
    return f"{d}/{m}/{y}"


def generate_pv_pdf(data: dict) -> bytes:
    """
    Procès-verbal d'incinération des Déchets Spéciaux (DS) / Déchets Spéciaux
    Dangereux (DSD) — document officiel délivré par l'installation d'incinération
    (éliminateur) certifiant la destruction des déchets remis par un récupérateur.
    Mise en page noir et blanc, pensée pour occuper toute la page A4.
    """
    buffer = io.BytesIO()
    BLACK = colors.black

    def st(name, **kw):
        return ParagraphStyle(name, **kw)

    TITLE  = st('TITLE',  fontName='Helvetica-Bold', fontSize=15, alignment=TA_CENTER, leading=19)
    OBJET  = st('OBJET',  fontName='Helvetica-Bold', fontSize=12.5, leading=16)
    LABEL  = st('LABEL',  fontName='Helvetica', fontSize=12, leading=18)
    BODY   = st('BODY',   fontName='Helvetica', fontSize=12, leading=19, alignment=TA_JUSTIFY)
    TH     = st('TH',     fontName='Helvetica-Bold', fontSize=11.5, leading=16)
    TD     = st('TD',     fontName='Helvetica', fontSize=11.5, leading=16)

    def remplir(valeur):
        v = str(valeur).strip() if valeur else ''
        return DOTS if not v else f"<b>{v}</b>"

    def champ(label, valeur, suite=''):
        return Paragraph(f"{label} {remplir(valeur)}{suite}", LABEL)

    def filet(epaisseur=0.8, espace_avant=10, espace_apres=10):
        return [Spacer(1, espace_avant),
                HRFlowable(width='100%', thickness=epaisseur, color=BLACK),
                Spacer(1, espace_apres)]

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        topMargin=1.1*cm, bottomMargin=1.1*cm, leftMargin=2.6*cm, rightMargin=2.6*cm)
    story = []

    # ── En-tête — identité de l'installation d'incinération ──────────────────
    story.append(champ('Raison Sociale', data.get('raison_sociale')))
    story.append(Spacer(1, 7))
    story.append(champ("Agrément d'exploitation N° :", data.get('agrement_exploitation')))
    story.append(Spacer(1, 7))
    story.append(champ('Adresse :', data.get('adresse')))
    story.append(Spacer(1, 7))
    story.append(champ('RC :', data.get('rc')))
    story.append(Spacer(1, 7))
    story.append(champ('NIF :', data.get('nif')))
    story.append(Spacer(1, 7))
    story.append(champ('NIS :', data.get('nis')))
    story.append(Spacer(1, 7))
    story.append(champ('ART :', data.get('art')))
    story.append(Spacer(1, 7))
    story.append(champ('Téléphone :', data.get('telephone')))

    story.extend(filet(espace_avant=14, espace_apres=12))

    story.append(Paragraph(
        'Objet : Incinération des Déchets Spéciaux (DS) / Déchets Spéciaux Dangereux (DSD)', OBJET))
    story.append(Spacer(1, 16))

    pv_numero = data.get('pv_numero') or DOTS
    story.append(Paragraph(
        f"Procès-verbal d'incinération n° <b>{pv_numero}</b> du <b>{_fmt_date(data.get('date_inspection')) or DOTS}</b>",
        TITLE))

    story.extend(filet(espace_avant=14, espace_apres=16))

    jour, mois_annee = _texte_date(data.get('date_inspection'))
    societe = data.get('raison_sociale') or DOTS
    site    = data.get('site_incineration') or data.get('adresse') or DOTS
    story.append(Paragraph(
        f"L'an deux mille, le {jour} du mois de {mois_annee}, il a été procédé par "
        f"la société : {societe} sur son site d'incinération situé à : {site}",
        BODY))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        'à la destruction par procédé d\'incinération des déchets suivants :', BODY))
    story.append(Spacer(1, 9))

    dechets = data.get('dechets') or [{
        'designation': data.get('designation_dechet') or data.get('designation') or '',
        'quantite':    data.get('quantite') or '',
    }]
    rows = [[Paragraph('Désignation', TH), Paragraph('Quantité', TH)]]
    for d in dechets:
        rows.append([Paragraph(str(d.get('designation') or ''), TD), Paragraph(str(d.get('quantite') or ''), TD)])
    table = Table(rows, colWidths=[11.5*cm, 4*cm], rowHeights=[30] + [28] * (len(rows) - 1))
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.8, BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))

    qte_totale = data.get('quantite_totale')
    if not qte_totale and data.get('quantite'):
        qte_totale = f"{data.get('quantite')} {data.get('unite_display') or data.get('unite') or ''}".strip()
    story.append(champ('Une quantité totale de', qte_totale, suite=f" récupérée par {remplir(data.get('recuperateur_nom'))}"))
    story.append(Spacer(1, 7))
    story.append(champ('Sise :', data.get('recuperateur_adresse')))
    story.append(Spacer(1, 7))
    story.append(champ('Agrément n°', data.get('recuperateur_agrement'), suite=f" du {remplir(_fmt_date(data.get('recuperateur_agrement_date')))}"))
    story.append(Spacer(1, 16))

    story.append(champ('Les déchets proviennent de :', data.get('generateur_nom')))
    story.append(Spacer(1, 7))
    story.append(champ('sise', data.get('generateur_adresse')))

    story.extend(filet(espace_avant=12, espace_apres=10))

    story.append(Paragraph(
        'Nous certifions que les déchets susmentionnés ont été intégralement détruits '
        'par incinération conformément à la réglementation en vigueur et aux '
        'prescriptions techniques de notre installation.', BODY))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        'Le présent procès-verbal est établi pour servir et valoir ce que de droit.', BODY))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
