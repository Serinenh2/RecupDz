"""
Génération du PDF Bon de Livraison (BL) — reproduit le formulaire papier du
récupérateur : en-tête avec logo et identité de l'entreprise (agrément,
RC/NIF/NA/NIS), client destinataire, tableau des déchets livrés, puis
chauffeur et signature du gérant.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from apps.bc.generate_bc import (
    _NumberedCanvas, _fmt_montant, _fmt_qte, _fmt_date, _signature_flowable,
    _INDUREX_GREEN, _INDUREX_BOTTOM_MARGIN,
)
import io
import functools

BLACK = colors.black
GREEN = colors.HexColor('#3B6D11')
COL   = 17 * cm


def _recuperateur_info(data):
    from apps.recuperateurs.models import Recuperateur
    rec_id = data.get('recuperateur') or data.get('recuperateur_id')
    if rec_id:
        try:
            r = Recuperateur.objects.get(pk=rec_id)
            agr = r.agrement_actif
            return {
                'nom':             r.nom_commercial or r.nom_raison_sociale,
                'slogan':          r.slogan or '',
                'capital_social':  r.capital_social or '',
                'agrement_num':    agr.numero_agrement if agr else '',
                'agrement_date':   agr.date_delivrance.strftime('%d/%m/%Y') if agr and agr.date_delivrance else '',
                'adresse':         r.adresse or '',
                'commune':         r.commune or '',
                'code_postal':     r.code_postal or '',
                'rc':              r.registre_commerce or '',
                'nif':             r.nif or '',
                'na':              r.numero_article or '',
                'nis':             r.nis or '',
                'telephone':       r.telephone or '',
                'fax':             r.fax or '',
                'email':           r.email or '',
                'compte_bancaire': r.compte_bancaire or '',
                'responsable':     r.responsable or '',
                'logo_path':       r.logo.path if r.logo else None,
                'signature_path':  r.signature_electronique.path if r.signature_electronique else None,
                'cachet_path':     r.cachet_electronique.path if r.cachet_electronique else None,
                'iso_9001_path':   r.iso_9001.path if r.iso_9001 else None,
                'iso_14001_path':  r.iso_14001.path if r.iso_14001 else None,
                'iso_45001_path':  r.iso_45001.path if r.iso_45001 else None,
            }
        except Recuperateur.DoesNotExist:
            pass
    return {'nom': data.get('recuperateur_nom') or '', 'slogan': '', 'capital_social': '',
            'agrement_num': '', 'agrement_date': '',
            'adresse': '', 'commune': '', 'code_postal': '', 'rc': '', 'nif': '', 'na': '', 'nis': '',
            'telephone': '', 'fax': '', 'email': '', 'compte_bancaire': '',
            'responsable': '', 'logo_path': None, 'signature_path': None, 'cachet_path': None,
            'iso_9001_path': None, 'iso_14001_path': None, 'iso_45001_path': None}


def _destinataire_info(data):
    from apps.operateurs.models import Operateur
    dest_id = data.get('destinataire') or data.get('destinataire_id')
    if dest_id:
        try:
            o = Operateur.objects.get(pk=dest_id)
            return {'nom': o.raison_sociale, 'adresse': o.adresse or ''}
        except Operateur.DoesNotExist:
            pass
    return {'nom': data.get('destinataire_nom') or '', 'adresse': data.get('destinataire_adresse') or ''}


def generate_bl_pdf(data: dict) -> bytes:
    rec  = _recuperateur_info(data)
    dest = _destinataire_info(data)
    return _generate_bl_pdf_indurex(data, rec, dest)


_INDUREX_CAPITAL_VERT = colors.HexColor('#0F452B')
_MODE_LIV_ABBR   = {'ENLEVEMENT': 'ENLEV', 'LIVRAISON': 'LIVR'}


def _generate_bl_pdf_indurex(data: dict, rec: dict, dest: dict) -> bytes:
    buffer = io.BytesIO()

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    NOM     = ps('NOM',     fontName='Montserrat-Bold',     fontSize=20, alignment=TA_LEFT,   leading=23, textColor=_INDUREX_GREEN)
    SLOGAN  = ps('SLOGAN',  fontName='Montserrat-Bold', fontSize=9.5,alignment=TA_LEFT,   leading=13, textColor=_INDUREX_GREEN)
    CAPITAL = ps('CAPITAL', fontName='Montserrat-Bold', fontSize=7.5,alignment=TA_LEFT,   leading=10, textColor=_INDUREX_CAPITAL_VERT)
    META    = ps('META',    fontName='Helvetica',      fontSize=9.5,alignment=TA_LEFT,   leading=13)
    LBL    = ps('LBL',    fontName='Helvetica',      fontSize=10.5,alignment=TA_LEFT,  leading=15)
    LBLB   = ps('LBLB',   fontName='Helvetica-Bold', fontSize=10.5,alignment=TA_LEFT,  leading=15)
    TITRE  = ps('TITRE',  fontName='Helvetica-Bold', fontSize=16, alignment=TA_CENTER, leading=19, textColor=colors.white)
    HEAD   = ps('HEAD',   fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, leading=13, textColor=colors.white)
    CELL   = ps('CELL',   fontName='Helvetica',      fontSize=10, alignment=TA_CENTER, leading=13)

    def v(key, default=''):
        val = data.get(key, default)
        return str(val) if val not in (None, '') else default

    lignes = data.get('lignes') or []

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        topMargin=1*cm, bottomMargin=_INDUREX_BOTTOM_MARGIN, leftMargin=1.5*cm, rightMargin=1.5*cm)
    story = []

    # ── En-tête : logo + raison sociale + slogan | bloc référence ──────────────
    logo_cell = ''
    if rec['logo_path']:
        try:
            logo_cell = Image(rec['logo_path'], width=2*cm, height=2*cm)
        except Exception:
            logo_cell = ''

    ref_box_rows = [
        [Paragraph('Référence', LBLB), Paragraph(v('numero'), META)],
        [Paragraph('Date',      LBLB), Paragraph(_fmt_date(v('date_livraison')), META)],
        [Paragraph('Montant',   LBLB), Paragraph(_fmt_montant(data.get('montant_reference') or 0), META)],
        [Paragraph('Mode Liv',  LBLB), Paragraph(_MODE_LIV_ABBR.get(v('mode_livraison'), v('mode_livraison')), META)],
    ]
    ref_box = Table(ref_box_rows, colWidths=[2.6*cm, 4.1*cm])
    ref_box.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))

    nom_block = [Paragraph((rec.get('nom') or '').upper(), NOM)]
    if rec.get('slogan'):
        nom_block.append(Paragraph(rec['slogan'], SLOGAN))
    if rec.get('capital_social'):
        nom_block.append(Paragraph(rec['capital_social'], CAPITAL))
    entete = Table([[logo_cell, nom_block, ref_box]], colWidths=[2.3*cm, COL - 2.3*cm - 6.7*cm, 6.7*cm])
    entete.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX',    (2, 0), (2, 0), 0.6, BLACK),
    ]))
    story.append(entete)
    story.append(Spacer(1, 10))

    # Identité RC/NIF/NIS/adresse — déplacée en bas de page (voir _NumberedCanvas._draw_footer),
    # à gauche des badges ISO, séparée par un filet vert. Toujours 3 lignes maximum,
    # libellés en gras pour un rendu propre malgré la largeur réduite de cette colonne.
    FOOTER_META = ps('FOOTER_META', fontName='Helvetica', fontSize=6.5, alignment=TA_LEFT, leading=8)
    footer_lines = [
        f"<b>RC:</b> {rec['rc']}  <b>NIF:</b> {rec['nif']}  <b>Al:</b> {rec['na']}  <b>NIS:</b> {rec['nis']}"
    ]
    if rec['adresse']:
        footer_lines.append(rec['adresse'])
    footer_line_extra = '  '.join(filter(None, [
        rec['commune'],
        f"<b>Email:</b> {rec['email']}" if rec['email'] else '',
        f"<b>Tél:</b> {rec['telephone']}" if rec['telephone'] else '',
        f"<b>Fax:</b> {rec['fax']}" if rec['fax'] else '',
    ]))
    if footer_line_extra:
        footer_lines.append(footer_line_extra)
    footer_paragraphs = [Paragraph(line, FOOTER_META) for line in footer_lines[:3]]

    # ── Titre ───────────────────────────────────────────────────────────────────
    titre_tbl = Table([[Paragraph(f"Bon Livraison N°: {v('numero')}", TITRE)]], colWidths=[COL])
    titre_tbl.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, BLACK),
        ('BACKGROUND', (0, 0), (-1, -1), _INDUREX_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(titre_tbl)
    story.append(Spacer(1, 10))

    # ── Bloc client (réf/RC/NIF/... à gauche, raison sociale/adresse à droite) ─
    client_lignes = [
        ('Réf Client:',   v('ref_client')),
        ('N° RC:',        v('client_rc')),
        ('NIF:',          v('client_nif')),
        ('N° Article:',   v('client_numero_article')),
        ('N° I.S:',       v('client_nis')),
        ('Tél:',          v('client_telephone')),
        ('Pièces Liées:', v('pieces_liees')),
    ]
    gauche_rows = [[Paragraph(lbl, LBL), Paragraph(val, LBL)] for lbl, val in client_lignes]
    gauche_tbl = Table(gauche_rows, colWidths=[2.4*cm, 6.1*cm])
    gauche_tbl.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 2),
        ('LEFTPADDING', (1, 0), (1, -1), 3),
    ]))

    droite_content = [Paragraph(dest['nom'], LBLB)]
    for ligne_adresse in (dest['adresse'] or '').split('\n'):
        if ligne_adresse.strip():
            droite_content.append(Paragraph(ligne_adresse.strip(), LBL))
    droite_tbl = Table([[droite_content]], colWidths=[8.5*cm])
    droite_tbl.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    bloc_client = Table([[gauche_tbl, droite_tbl]], colWidths=[8.5*cm, 8.5*cm])
    bloc_client.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(bloc_client)
    story.append(Spacer(1, 12))

    # ── Tableau des articles (pas de prix — un bon de livraison suit des quantités) ─
    col_w   = [2.8*cm, 9.2*cm, 2.3*cm, 2.7*cm]
    headers = ['Réf Article', 'Désignation', 'Unité', 'Quantité']
    rows    = [[Paragraph(h, HEAD) for h in headers]]

    for l in lignes:
        rows.append([
            Paragraph(str(l.get('ref_article', '')), CELL),
            Paragraph(str(l.get('description', '')), CELL),
            Paragraph(str(l.get('unite', 'KG')), CELL),
            Paragraph(_fmt_qte(l.get('quantite')), CELL),
        ])

    tbl_style = TableStyle([
        ('GRID',          (0, 0), (-1, -1), 0.6, BLACK),
        ('BACKGROUND',    (0, 0), (-1, 0),  _INDUREX_GREEN),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ])

    # ── Le tableau est étiré pour occuper l'espace restant de la page (comme le
    # formulaire papier pré-imprimé, indépendamment du nombre de lignes saisies).
    avail_w  = A4[0] - 3 * cm
    usable_h = A4[1] - 1 * cm - _INDUREX_BOTTOM_MARGIN
    top_h    = sum(fl.wrap(avail_w, 20000)[1] for fl in story)
    tbl_no_filler = Table(rows, colWidths=col_w)
    tbl_no_filler.setStyle(tbl_style)
    tbl_h    = tbl_no_filler.wrap(avail_w, 20000)[1]
    # Marge de sécurité : le Frame interne de reportlab applique un padding (~6pt de
    # chaque côté) non compté dans topMargin/bottomMargin.
    filler_h = max(0.6 * cm, usable_h - top_h - tbl_h - 1.2 * cm)

    # Cachet/signature électroniques insérés dans la case vide de la zone
    # articles (comme le cachet humide apposé à la main sur le formulaire papier).
    filler_row = ['' for _ in headers]
    sign_flowable = _signature_flowable(rec, align='CENTER', cachet_size=4*cm, sig_w=4.5*cm, sig_h=2.4*cm)
    if sign_flowable:
        filler_row[0] = sign_flowable

    filler_idx = len(rows)
    rows_with_filler = rows + [filler_row]
    tbl = Table(rows_with_filler, colWidths=col_w, rowHeights=[None] * len(rows) + [filler_h])
    tbl_style_filler = TableStyle(tbl_style.getCommands() + [
        ('SPAN',  (0, filler_idx), (-1, filler_idx)),
        ('ALIGN', (0, filler_idx), (-1, filler_idx), 'CENTER'),
    ])
    tbl.setStyle(tbl_style_filler)
    story.append(tbl)

    iso_paths = [rec.get('iso_9001_path'), rec.get('iso_14001_path'), rec.get('iso_45001_path')]
    doc.build(story, canvasmaker=functools.partial(
        _NumberedCanvas, iso_paths=iso_paths, footer_paragraphs=footer_paragraphs))
    buffer.seek(0)
    return buffer.read()
