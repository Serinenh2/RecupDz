"""
Génération du PDF BSD — Bordereau de Suivi des Déchets, reproduisant le
formulaire qualité interne de l'entreprise (réf. ENR_REA_02) : en-tête avec
identité de l'émetteur, puis trois rubriques — Générateur de déchet,
Collecteur-Transporteur, Destination/Centre de traitement — chacune avec
cases à cocher (type de déchet, mode de stockage), quantités par unité et
emplacement libre pour cachet et signature. Document noir et blanc, une
page A4.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER
import io

BLACK = colors.black
COL   = 17 * cm

REFERENCE        = 'ENR_REA_02'
DATE_CREATION    = '01/07/2024'
DATE_APPLICATION = '15/07/2024'


def generate_bsd_pdf(data: dict) -> bytes:
    buffer = io.BytesIO()

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    ENT   = ps('ENT',  fontName='Helvetica-Bold', fontSize=11, alignment=TA_CENTER, leading=14)
    TITRE = ps('TITRE',fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER, leading=15)
    META  = ps('META', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, leading=11)
    SEC   = ps('SEC',  fontName='Helvetica-Bold', fontSize=10.5, leading=14)
    LBL   = ps('LBL',  fontName='Helvetica', fontSize=9.5, leading=16)
    SM    = ps('SM',   fontName='Helvetica', fontSize=9, leading=13)
    CB    = ps('CB',   fontName='Helvetica-Bold', fontSize=9, leading=13, alignment=TA_CENTER)

    def v(key, default=''):
        val = data.get(key, default)
        return str(val) if val not in (None, '') else default

    def fmt_date(iso):
        if not iso:
            return ''
        parts = str(iso).split('-')
        if len(parts) != 3:
            return str(iso)
        y, m, d = parts
        return f"{d}/{m}/{y}"

    def champ(label, valeur, largeur_label=4.2*cm):
        t = Table([[Paragraph(label, LBL), Paragraph(f"<b>{valeur}</b>" if valeur else '', LBL)]],
                   colWidths=[largeur_label, COL - largeur_label])
        t.setStyle(TableStyle([
            ('LINEBELOW', (1,0),(1,0), 0.5, BLACK),
            ('TOPPADDING', (0,0),(-1,-1), 2), ('BOTTOMPADDING', (0,0),(-1,-1), 2),
            ('LEFTPADDING', (0,0),(-1,-1), 0), ('VALIGN', (0,0),(-1,-1), 'BOTTOM'),
        ]))
        return t

    def double_champ(l1, v1, l2, v2, lw1=3.2*cm, lw2=2*cm):
        moitie = COL/2
        t = Table([[
            Paragraph(l1, LBL), Paragraph(f"<b>{v1}</b>" if v1 else '', LBL),
            Paragraph(l2, LBL), Paragraph(f"<b>{v2}</b>" if v2 else '', LBL),
        ]], colWidths=[lw1, moitie-lw1, lw2, moitie-lw2])
        t.setStyle(TableStyle([
            ('LINEBELOW', (1,0),(1,0), 0.5, BLACK), ('LINEBELOW', (3,0),(3,0), 0.5, BLACK),
            ('TOPPADDING', (0,0),(-1,-1), 2), ('BOTTOMPADDING', (0,0),(-1,-1), 2),
            ('LEFTPADDING', (0,0),(-1,-1), 0), ('VALIGN', (0,0),(-1,-1), 'BOTTOM'),
        ]))
        return t

    def ligne_cases(items):
        cells, widths, box_cols = [], [], []
        for i, (label, coche) in enumerate(items):
            cells += [Paragraph(label, SM), Paragraph('X' if coche else '', CB)]
            widths += [2.6*cm, 0.8*cm]
            box_cols.append(len(widths) - 1)
        widths[-1] += COL - sum(widths)
        t = Table([cells], colWidths=widths)
        style = [
            ('TOPPADDING', (0,0),(-1,-1), 3), ('BOTTOMPADDING', (0,0),(-1,-1), 3),
            ('LEFTPADDING', (0,0),(-1,-1), 4), ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
        ]
        for c in box_cols:
            style.append(('BOX', (c,0),(c,0), 0.6, BLACK))
        t.setStyle(TableStyle(style))
        return t

    def boites_quantite(quantite, unite):
        u = (unite or 'KG').upper()
        kg = quantite if u == 'KG' else ''
        li = quantite if u == 'LITRE' else ''
        m3 = quantite if u == 'M3' else ''
        t = Table([[
            Paragraph('Quantités :', LBL),
            Paragraph('Kg', SM), Paragraph(str(kg), CB),
            Paragraph('L', SM), Paragraph(str(li), CB),
            Paragraph('M²', SM), Paragraph(str(m3), CB),
        ]], colWidths=[3.2*cm, 0.9*cm, 2.6*cm, 0.7*cm, 2.6*cm, 0.9*cm, COL-3.2*cm-0.9*cm-2.6*cm-0.7*cm-2.6*cm-0.9*cm])
        t.setStyle(TableStyle([
            ('BOX', (2,0),(2,0), 0.6, BLACK), ('BOX', (4,0),(4,0), 0.6, BLACK), ('BOX', (6,0),(6,0), 0.6, BLACK),
            ('TOPPADDING', (0,0),(-1,-1), 3), ('BOTTOMPADDING', (0,0),(-1,-1), 3),
            ('LEFTPADDING', (0,0),(-1,-1), 4), ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
        ]))
        return t

    def date_signature(label_date, valeur_date):
        t = Table([[
            Paragraph(label_date, LBL), Paragraph(f"<b>{valeur_date}</b>" if valeur_date else '', LBL),
            Paragraph('Cachet et signature :', LBL), Paragraph('', LBL),
        ]], colWidths=[3.5*cm, 4*cm, 4*cm, COL-11.5*cm])
        t.setStyle(TableStyle([
            ('BOX', (1,0),(1,0), 0.6, BLACK),
            ('LINEBELOW', (3,0),(3,0), 0.5, BLACK),
            ('TOPPADDING', (0,0),(-1,-1), 8), ('BOTTOMPADDING', (0,0),(-1,-1), 8),
            ('LEFTPADDING', (0,0),(-1,-1), 4),
        ]))
        return t

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        topMargin=1.2*cm, bottomMargin=1.2*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    story = []

    # ── En-tête — identité de l'émetteur + cartouche qualité ──────────────────
    entete = Table([[
        Paragraph(v('raison_sociale', v('recuperateur_nom', 'RÉCUPÉRATEUR')).upper(), ENT),
        Paragraph('BORDEREAU DE SUIVI DES DÉCHETS (BSD)', TITRE),
    ]], colWidths=[5*cm, COL-5*cm])
    entete.setStyle(TableStyle([
        ('BOX', (0,0),(-1,-1), 0.8, BLACK), ('INNERGRID', (0,0),(-1,-1), 0.8, BLACK),
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0),(-1,-1), 10),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
    ]))
    story.append(entete)

    cartouche = Table([[
        Paragraph(f"Référence : {REFERENCE}", META),
        Paragraph(f"DATE DE CRÉATION : {DATE_CREATION}", META),
        Paragraph(f"DATE D'APPLICATION : {DATE_APPLICATION}", META),
        Paragraph('PAGE : 1/1', META),
    ]], colWidths=[COL/4]*4)
    cartouche.setStyle(TableStyle([
        ('BOX', (0,0),(-1,-1), 0.8, BLACK), ('INNERGRID', (0,0),(-1,-1), 0.5, BLACK),
        ('TOPPADDING', (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
    ]))
    story.append(cartouche)
    story.append(HRFlowable(width='100%', thickness=1.5, color=BLACK))
    story.append(Spacer(1, 8))

    story.append(Paragraph('<u>BORDEREAU DE SUIVI DES DÉCHETS (BSD)</u>',
        ps('T2', fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER, leading=16)))
    story.append(Spacer(1, 6))

    annee = v('date_emission')[:4] if v('date_emission') else ''
    story.append(double_champ('N° Bordereau :', f"{v('numero')} /BSD/HSE/ /{annee}" if v('numero') else '',
        'Délivré le :', fmt_date(v('date_emission')), lw1=2.8*cm, lw2=2.3*cm))
    story.append(Spacer(1, 5))
    story.append(Paragraph("Objet de la Prestation :", LBL))
    story.append(Paragraph('Collecte et transport des déchets',
        ps('OBJ', fontName='Helvetica-Bold', fontSize=11, alignment=TA_CENTER, leading=13)))
    story.append(Spacer(1, 6))

    # ── 1. Générateur de déchet ────────────────────────────────────────────────
    story.append(Paragraph('1- GÉNÉRATEUR DE DÉCHET :', SEC))
    story.append(HRFlowable(width='100%', thickness=1, color=BLACK))
    story.append(Spacer(1, 3))
    story.append(champ('Dénomination :', v('generateur_nom')))
    story.append(champ('Bon de commande :', v('bon_commande')))
    story.append(champ('Siège social :', v('generateur_adresse')))
    story.append(champ('Site d\'enlèvement :', v('site_enlevement', v('generateur_adresse'))))
    story.append(double_champ('TEL :', v('generateur_tel'), 'FAX :', v('generateur_fax')))
    story.append(double_champ('Nomenclature de Déchet :', v('designation'), 'Code :', v('code_dechet'),
        lw1=4.2*cm, lw2=1.6*cm))
    etat = v('etat_physique').upper()
    story.append(ligne_cases([
        ('Solide', etat == 'SOLIDE'), ('Liquide', etat == 'LIQUIDE'),
        ('Pâteux', etat == 'PATEUX'), ('Gazeux', etat == 'GAZEUX'),
    ]))
    embal = v('emballage').upper()
    story.append(ligne_cases([
        ('Fût', 'FUT' in embal), ('Big Bag', 'BIG' in embal),
        ('Caisse Bois', 'CAISSE' in embal), ('Vrac/palette', 'VRAC' in embal or 'PALETTE' in embal),
    ]))
    story.append(champ('Autres Précision :', v('autres_precision')))
    story.append(boites_quantite(v('quantite'), v('unite')))
    story.append(date_signature("Date d'enlèvement :", fmt_date(v('date_emission'))))
    story.append(Spacer(1, 6))

    # ── 2. Collecteur — Transporteur ───────────────────────────────────────────
    story.append(Paragraph('2- COLLECTEUR -TRANSPORTEUR', SEC))
    story.append(HRFlowable(width='100%', thickness=1, color=BLACK))
    story.append(Spacer(1, 3))
    story.append(champ('Dénomination :', v('transporteur_nom', v('raison_sociale', v('recuperateur_nom')))))
    story.append(champ('Siège social :', v('recuperateur_adresse')))
    story.append(champ('Responsable :', v('responsable')))
    story.append(double_champ('Représentant :', v('representant'), 'Fonction :', v('fonction'),
        lw1=2.8*cm, lw2=2*cm))
    story.append(champ('Moyen de transport :', v('transporteur_vehicule')))
    story.append(champ('Matricule :', v('immatriculation')))
    story.append(boites_quantite(v('quantite'), v('unite')))
    story.append(date_signature("Date d'enlèvement :", fmt_date(v('date_emission'))))
    story.append(Spacer(1, 6))

    # ── 3. Destination — Centre de traitement ──────────────────────────────────
    story.append(Paragraph('3-DESTINATION -CENTRE DE TRAITEMENT', SEC))
    story.append(HRFlowable(width='100%', thickness=1, color=BLACK))
    story.append(Spacer(1, 3))
    story.append(champ('Installation :', v('recepteur_nom')))
    story.append(boites_quantite(v('quantite'), v('unite')))
    story.append(date_signature("Date D'arrivé :", fmt_date(v('date_reception'))))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
