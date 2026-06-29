"""
Génération du PDF Bon de Livraison (BL) — émis par le récupérateur à
destination d'un éliminateur ou d'un valorisateur. Reproduit la structure du
formulaire papier : en-tête identité émetteur/destinataire, tableau des
lignes de marchandise, puis cartouches Établi par / Qualité / Visa chauffeur.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io

BLACK = colors.black
COL   = 17 * cm


def generate_bl_pdf(data: dict) -> bytes:
    buffer = io.BytesIO()

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    ENT   = ps('ENT',  fontName='Helvetica-Bold', fontSize=13, alignment=TA_LEFT,  leading=16)
    TITRE = ps('TITRE',fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER, leading=16)
    META  = ps('META', fontName='Helvetica', fontSize=8, alignment=TA_LEFT, leading=11)
    SEC   = ps('SEC',  fontName='Helvetica-Bold', fontSize=10, leading=13)
    LBL   = ps('LBL',  fontName='Helvetica', fontSize=9, leading=14)
    SM    = ps('SM',   fontName='Helvetica', fontSize=8.5, leading=12)
    CELL  = ps('CELL', fontName='Helvetica', fontSize=8.5, leading=11, alignment=TA_CENTER)
    HEAD  = ps('HEAD', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER)

    def v(key, default=''):
        val = data.get(key, default)
        return str(val) if val not in (None, '') else default

    def champ(label, valeur, largeur_label=3.4*cm):
        t = Table([[Paragraph(label, LBL), Paragraph(f"<b>{valeur}</b>" if valeur else '', LBL)]],
                   colWidths=[largeur_label, COL - largeur_label])
        t.setStyle(TableStyle([
            ('LINEBELOW', (1,0),(1,0), 0.5, BLACK),
            ('TOPPADDING', (0,0),(-1,-1), 2), ('BOTTOMPADDING', (0,0),(-1,-1), 2),
            ('LEFTPADDING', (0,0),(-1,-1), 0), ('VALIGN', (0,0),(-1,-1), 'BOTTOM'),
        ]))
        return t

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        topMargin=1.2*cm, bottomMargin=1.2*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    story = []

    # ── En-tête : identité émetteur (récupérateur) + n° de bon ────────────────
    entete = Table([[
        Paragraph(v('recuperateur_nom', 'RÉCUPÉRATEUR').upper(), ENT),
        Paragraph(f"Bon de Livraison N° {v('numero')}", TITRE),
    ]], colWidths=[8*cm, COL-8*cm])
    entete.setStyle(TableStyle([
        ('BOX', (0,0),(-1,-1), 0.8, BLACK), ('INNERGRID', (0,0),(-1,-1), 0.8, BLACK),
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0),(-1,-1), 10),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
    ]))
    story.append(entete)
    story.append(Spacer(1, 8))

    story.append(champ('Date de livraison :', v('date_livraison')))
    story.append(champ('Bon de commande N° :', v('bon_commande_numero')))
    story.append(champ('Date de commande :', v('date_commande')))
    story.append(Spacer(1, 8))

    # ── Destinataire ────────────────────────────────────────────────────────
    story.append(Paragraph(f"Destinataire ({v('destinataire_type_display', v('destinataire_type'))}) :", SEC))
    story.append(HRFlowable(width='100%', thickness=1, color=BLACK))
    story.append(Spacer(1, 3))
    story.append(champ('Raison sociale :', v('destinataire_nom')))
    story.append(Spacer(1, 10))

    # ── Tableau des lignes ──────────────────────────────────────────────────
    lignes = data.get('lignes') or []
    rows = [[Paragraph(h, HEAD) for h in ['Désignation', 'Référence', 'Conditionnement', 'Qté Box', 'Qté Préforme']]]
    for l in lignes:
        rows.append([
            Paragraph(str(l.get('designation','')), CELL),
            Paragraph(str(l.get('reference','')), CELL),
            Paragraph(str(l.get('conditionnement','')), CELL),
            Paragraph(str(l.get('qte_box','')), CELL),
            Paragraph(str(l.get('qte_preforme','')), CELL),
        ])
    if len(rows) == 1:
        rows.append([Paragraph('', CELL)]*5)
    tbl = Table(rows, colWidths=[5*cm, 4*cm, 3.5*cm, 2.25*cm, 2.25*cm])
    tbl.setStyle(TableStyle([
        ('GRID', (0,0),(-1,-1), 0.6, BLACK),
        ('BACKGROUND', (0,0),(-1,0), colors.whitesmoke),
        ('TOPPADDING', (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 14))

    # ── Établi par / Qualité / Visa chauffeur ──────────────────────────────
    qualite = data.get('qualite') or {}
    criteres = ['chauffeur', 'sgt', 'maraicher', 'bacher', 'proprete']
    labels   = ['Chauffeur', 'SGT', 'Maraîcher', 'Bacher', 'Propreté']
    header_row = [Paragraph('', HEAD)] + [Paragraph(lbl, HEAD) for lbl in labels]
    ok_row  = [Paragraph('OK', HEAD)]  + [Paragraph('X' if qualite.get(c) == 'OK'  else '', CELL) for c in criteres]
    non_row = [Paragraph('Non', HEAD)] + [Paragraph('X' if qualite.get(c) == 'NON' else '', CELL) for c in criteres]
    qualite_tbl = Table([header_row, ok_row, non_row], colWidths=[1.5*cm]+[2*cm]*5)
    qualite_tbl.setStyle(TableStyle([
        ('GRID', (0,0),(-1,-1), 0.5, BLACK),
        ('TOPPADDING', (0,0),(-1,-1), 4), ('BOTTOMPADDING', (0,0),(-1,-1), 4),
    ]))
    qualite_block = Table([
        [Paragraph('Qualité', SEC)],
        [qualite_tbl],
    ], colWidths=[11.5*cm])
    qualite_block.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))

    etabli_visa = Table([
        [Paragraph('Établi par', SEC), Paragraph('Visa de Chauffeur', SEC)],
        [Paragraph(v('etabli_par'), LBL), Paragraph(f"Chauffeur : {v('chauffeur_nom')}", LBL)],
        [Paragraph('', LBL), Paragraph(f"Camion : {v('camion_numero')}", LBL)],
        [Paragraph('', LBL), Paragraph(f"Immatriculation : {v('camion_immatriculation')}", LBL)],
    ], colWidths=[8.5*cm, 8.5*cm])
    etabli_visa.setStyle(TableStyle([
        ('TOPPADDING', (0,0),(-1,-1), 4), ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('VALIGN', (0,0),(-1,-1), 'TOP'),
    ]))

    story.append(etabli_visa)
    story.append(Spacer(1, 8))
    story.append(qualite_block)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'Garantie pour une aptitude au contact alimentaire : ' + ('Oui' if data.get('garantie_alimentaire') else 'Non'),
        SM))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
