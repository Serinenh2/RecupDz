"""
Génération du PDF Bon de Commande (BC) — reproduit le formulaire papier :
en-tête récupérateur (logo, identité, agrément, RC/NIF/NA/NIS), client,
tableau des déchets avec prix unitaires, récapitulatif HT/TVA/TTC, signature.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io

BLACK = colors.black
GREEN = colors.HexColor('#3B6D11')
COL   = 17 * cm


def _fmt_date(iso):
    """Convertit une date ISO (YYYY-MM-DD) en JJ/MM/AAAA — inchangé si le format est différent."""
    if not iso:
        return ''
    parts = str(iso).split('-')
    if len(parts) != 3:
        return str(iso)
    y, m, d = parts
    return f"{d}/{m}/{y}"


def _recuperateur_info(data):
    from apps.recuperateurs.models import Recuperateur
    rec_id = data.get('recuperateur') or data.get('recuperateur_id')
    if rec_id:
        try:
            r   = Recuperateur.objects.get(pk=rec_id)
            agr = r.agrement_actif
            return {
                'nom':             r.nom_commercial or r.nom_raison_sociale,
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
            }
        except Recuperateur.DoesNotExist:
            pass
    return {
        'nom': data.get('recuperateur_nom') or '', 'agrement_num': '', 'agrement_date': '',
        'adresse': '', 'commune': '', 'code_postal': '', 'rc': '', 'nif': '', 'na': '', 'nis': '',
        'telephone': '', 'fax': '', 'email': '', 'compte_bancaire': '',
        'responsable': '', 'logo_path': None,
    }


def _calc_ligne(l, default_tva_pct):
    """Calcule le montant HT (après remise) et la TVA d'une ligne."""
    try:
        qte    = float(l.get('quantite') or 0)
        pu     = float(l.get('prix_unitaire') or 0)
        remise = float(l.get('remise_pct') or 0)
    except (TypeError, ValueError):
        qte = pu = remise = 0.0
    tva_val = l.get('tva_pct')
    tva_pct = float(tva_val) if tva_val not in (None, '') else float(default_tva_pct)
    ht = qte * pu * (1 - remise / 100)
    return {'ht': ht, 'remise_pct': remise, 'tva_pct': tva_pct, 'tva': ht * tva_pct / 100}


def _calc_totaux(lignes, tva_pct=19):
    total_ht  = 0.0
    total_tva = 0.0
    for l in lignes:
        c = _calc_ligne(l, tva_pct)
        total_ht  += c['ht']
        total_tva += c['tva']
    total_ttc = total_ht + total_tva
    return total_ht, total_tva, total_ttc


# ── Nombre en lettres (français, sans traits d'union) ─────────────────────────
_UNITES        = ['', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf']
_DIX_DIX_NEUF  = ['dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize',
                  'dix sept', 'dix huit', 'dix neuf']
_DIZAINES      = {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante',
                  6: 'soixante', 7: 'soixante', 8: 'quatre vingt', 9: 'quatre vingt'}


def _deux_chiffres_en_lettres(n):
    if n < 10:
        return _UNITES[n]
    if n < 20:
        return _DIX_DIX_NEUF[n - 10]
    d, u = divmod(n, 10)
    if d in (7, 9):
        base = _DIZAINES[d]
        return f"{base} {_DIX_DIX_NEUF[u]}" if u else f"{base} dix"
    mot = _DIZAINES[d]
    if u == 0:
        return mot
    if u == 1 and d != 8:
        return f"{mot} et un"
    return f"{mot} {_UNITES[u]}"


def _trois_chiffres_en_lettres(n):
    c, r = divmod(n, 100)
    parts = []
    if c > 0:
        parts.append('cent' if c == 1 else f"{_UNITES[c]} cent")
    if r > 0:
        parts.append(_deux_chiffres_en_lettres(r))
    return ' '.join(parts)


def nombre_en_lettres(n):
    n = int(n)
    if n == 0:
        return 'zéro'
    parts = []
    millions, reste = divmod(n, 1_000_000)
    milliers, reste = divmod(reste, 1000)
    if millions:
        parts.append('un million' if millions == 1 else f"{_trois_chiffres_en_lettres(millions)} million")
    if milliers:
        parts.append('mille' if milliers == 1 else f"{_trois_chiffres_en_lettres(milliers)} mille")
    if reste or not parts:
        parts.append(_trois_chiffres_en_lettres(reste))
    return ' '.join(p for p in parts if p)


def montant_en_lettres(montant):
    """Ex: 2162287.50 -> 'deux million cent soixante deux mille deux cent quatre vingt sept DA et 50 Cts'"""
    # Arrondi préalable à 2 décimales pour éviter qu'un résidu flottant (ex: 2162451.0000000002)
    # ne produise des centimes invalides comme "100 Cts".
    montant  = round(float(montant), 2)
    entier   = int(montant)
    centimes = int(round((montant - entier) * 100))
    if centimes >= 100:
        entier   += 1
        centimes -= 100
    texte = f"{nombre_en_lettres(entier)} DA"
    if centimes:
        texte += f" et {centimes:02d} Cts"
    return texte


def _is_indurex(rec):
    return 'INDUREX' in (rec.get('nom') or '').upper()


def generate_bc_pdf(data: dict) -> bytes:
    buffer = io.BytesIO()

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    NOM   = ps('NOM',   fontName='Helvetica-BoldOblique', fontSize=20, alignment=TA_LEFT,    leading=24, textColor=GREEN)
    META  = ps('META',  fontName='Helvetica',             fontSize=9,  alignment=TA_LEFT,    leading=13)
    LBL   = ps('LBL',   fontName='Helvetica',             fontSize=9.5,                      leading=15)
    TITRE = ps('TITRE', fontName='Helvetica-BoldOblique', fontSize=13, alignment=TA_CENTER,  leading=16)
    HEAD  = ps('HEAD',  fontName='Helvetica-Bold',        fontSize=9,  alignment=TA_CENTER,  leading=12, textColor=colors.white)
    HEADR = ps('HEADR', fontName='Helvetica-Bold',        fontSize=9,  alignment=TA_RIGHT,   leading=12, textColor=colors.white)
    CELL  = ps('CELL',  fontName='Helvetica',             fontSize=9,  alignment=TA_CENTER,  leading=12)
    CELLR = ps('CELLR', fontName='Helvetica',             fontSize=9,  alignment=TA_RIGHT,   leading=12)
    SIGN  = ps('SIGN',  fontName='Helvetica',             fontSize=10, alignment=TA_RIGHT,   leading=14)
    FOOT  = ps('FOOT',  fontName='Helvetica-Oblique',     fontSize=9,  alignment=TA_LEFT,    leading=13)

    def v(key, default=''):
        val = data.get(key, default)
        return str(val) if val not in (None, '') else default

    rec = _recuperateur_info(data)

    if _is_indurex(rec):
        return _generate_bc_pdf_indurex(data, rec)

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        topMargin=1.2*cm, bottomMargin=1.2*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    story = []

    # ── En-tête : logo + raison sociale ────────────────────────────────────────
    logo_cell = ''
    if rec['logo_path']:
        try:
            logo_cell = Image(rec['logo_path'], width=2.2*cm, height=2.2*cm)
        except Exception:
            logo_cell = ''
    entete = Table([[logo_cell, Paragraph(rec['nom'].upper(), NOM)]], colWidths=[2.5*cm, COL - 2.5*cm])
    entete.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    story.append(entete)
    story.append(Spacer(1, 6))

    if rec['agrement_num']:
        story.append(Paragraph(f"Agrément N° {rec['agrement_num']} du {rec['agrement_date']}", META))
    adresse_ligne = ' '.join(filter(None, [rec['adresse'], rec['code_postal']]))
    if adresse_ligne:
        story.append(Paragraph(adresse_ligne, META))

    id_table = Table([[
        Paragraph(f"RC {rec['rc']}", META), Paragraph(f"NIF {rec['nif']}", META),
    ], [
        Paragraph(f"NA {rec['na']}", META), Paragraph(f"NIS {rec['nis']}", META),
    ]], colWidths=[COL / 2, COL / 2])
    id_table.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
    story.append(id_table)
    story.append(Spacer(1, 10))

    # ── Date / lieu ─────────────────────────────────────────────────────────────
    lieu_date = Table([['', Paragraph(f"{rec['commune']} le : {_fmt_date(v('date_commande'))}", LBL)]],
        colWidths=[COL - 7*cm, 7*cm])
    story.append(lieu_date)
    story.append(Spacer(1, 8))

    # ── Client ──────────────────────────────────────────────────────────────────
    story.append(Paragraph(f"Nome de Client : <b>{v('client_nom')}</b>", LBL))
    story.append(Paragraph(f"Adresse : <b>{v('client_adresse')}</b>", LBL))
    story.append(Spacer(1, 10))

    # ── Titre ───────────────────────────────────────────────────────────────────
    titre_txt = {'PROFORMA': 'Proforma', 'FACTURE': 'Facture'}.get(data.get('type_document'), 'Bon de commande')
    titre_tbl = Table([[Paragraph(titre_txt, TITRE)]], colWidths=[8*cm])
    titre_tbl.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    wrapper = Table([[titre_tbl]], colWidths=[COL])
    wrapper.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
    story.append(wrapper)
    story.append(Spacer(1, 14))

    # ── Tableau des déchets ──────────────────────────────────────────────────────
    lignes  = data.get('lignes') or []
    tva_pct = float(data.get('tva_pct') or 19)

    col_w = [1.2*cm, 6*cm, 2.3*cm, 2*cm, 2.5*cm, 3*cm]
    headers = ['N°', 'Description (Nature des déchets)', 'Quantités', 'Unités', 'Prix unitaires', 'Total HT']
    # En-têtes alignés sur le même sens que les cellules de données de leur colonne
    # (Prix unitaires / Total HT sont à droite, comme les montants qu'ils surplombent).
    header_styles = [HEAD, HEAD, HEAD, HEAD, HEADR, HEADR]
    rows = [[Paragraph(h, s) for h, s in zip(headers, header_styles)]]

    if not lignes:
        rows.append([Paragraph(str(x), CELL) for x in ['1', '', '', 'KG', 'DZ', 'DZ']])
    else:
        for i, l in enumerate(lignes, start=1):
            try:
                qte = float(l.get('quantite') or 0)
                pu  = float(l.get('prix_unitaire') or 0)
                ht  = qte * pu
            except (TypeError, ValueError):
                ht = 0.0
            rows.append([
                Paragraph(str(i), CELL),
                Paragraph(str(l.get('description', '')), CELL),
                Paragraph(str(l.get('quantite', '')), CELL),
                Paragraph(str(l.get('unite', 'KG')), CELL),
                Paragraph(f"{pu:,.2f} DZ".replace(',', ' '), CELLR),
                Paragraph(f"{ht:,.2f} DZ".replace(',', ' '), CELLR),
            ])

    tbl = Table(rows, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ('GRID',       (0, 0), (-1, -1), 0.6, BLACK),
        ('BACKGROUND', (0, 0), (-1, 0),  GREEN),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6))

    # ── Récapitulatif HT / TVA / TTC (aligné à droite) ─────────────────────────
    total_ht, tva, total_ttc = _calc_totaux(lignes, tva_pct)

    recap_rows = [
        [Paragraph('Total HT',              META), Paragraph(f"{total_ht:,.2f} DZ".replace(',', ' '), CELLR)],
        [Paragraph(f'TVA ({tva_pct:.0f}%)', META), Paragraph(f"{tva:,.2f} DZ".replace(',', ' '), CELLR)],
        [Paragraph('<b>Total TTC</b>',       LBL),  Paragraph(f"<b>{total_ttc:,.2f} DZ</b>".replace(',', ' '), CELLR)],
    ]
    recap_tbl = Table(recap_rows, colWidths=[4*cm, 3*cm])
    recap_tbl.setStyle(TableStyle([
        ('GRID',          (0, 0), (-1, -1), 0.5, BLACK),
        ('BACKGROUND',    (0, 2), (-1, 2),  colors.HexColor('#EAF3DE')),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]))
    recap_wrapper = Table([[recap_tbl]], colWidths=[COL])
    recap_wrapper.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'RIGHT')]))
    story.append(recap_wrapper)
    story.append(Spacer(1, 14))

    # ── Arrêté de la facture ─────────────────────────────────────────────────────
    arrete_nom = {'PROFORMA': 'présente proforma', 'BC': 'présente commande'}.get(
        data.get('type_document'), 'présente facture')
    story.append(Paragraph(
        f"<u>Arrêter la {arrete_nom} en toutes taxes comprises a la somme de :</u> "
        f"<b>{total_ttc:,.2f} DZ</b>".replace(',', ' '),
        FOOT,
    ))
    story.append(Spacer(1, 30))

    # ── Signature ───────────────────────────────────────────────────────────────
    story.append(Paragraph('Le Gérant', SIGN))
    if rec['responsable']:
        story.append(Paragraph(rec['responsable'], SIGN))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ── Slogan fixe de l'en-tête SARL INDUREX (non stocké en base — identité visuelle propre à cette société) ──
_INDUREX_SLOGAN = 'INDUSTRIAL WAST RECOVERY AND VALORIZATION'


def _fmt_montant(n):
    try:
        return f"{float(n):,.2f}".replace(',', ' ')
    except (TypeError, ValueError):
        return f"{0:,.2f}".replace(',', ' ')


def _fmt_qte(n):
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    if n == int(n):
        return f"{int(n):,}".replace(',', ' ')
    return f"{n:,.3f}".replace(',', ' ')


from reportlab.pdfgen import canvas as _pdfcanvas


class _NumberedCanvas(_pdfcanvas.Canvas):
    """Pied de page 'Page: n/total' — bufferise les pages pour connaître le total avant d'écrire."""

    def __init__(self, *args, **kwargs):
        _pdfcanvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.saveState()
            self.setFont('Helvetica', 8)
            self.drawCentredString(A4[0] / 2, 0.8 * cm, f"Page: {self._pageNumber}/{total_pages}")
            self.restoreState()
            _pdfcanvas.Canvas.showPage(self)
        _pdfcanvas.Canvas.save(self)


def _generate_bc_pdf_indurex(data: dict, rec: dict) -> bytes:
    buffer = io.BytesIO()

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    NOM     = ps('NOM',     fontName='Helvetica-Bold',   fontSize=20, alignment=TA_LEFT,   leading=23)
    SLOGAN  = ps('SLOGAN',  fontName='Helvetica',        fontSize=9.5,alignment=TA_LEFT,   leading=13)
    META    = ps('META',    fontName='Helvetica',        fontSize=9.5,alignment=TA_LEFT,   leading=13)
    LBL     = ps('LBL',     fontName='Helvetica',        fontSize=10.5,alignment=TA_LEFT,  leading=15)
    LBLB    = ps('LBLB',    fontName='Helvetica-Bold',   fontSize=10.5,alignment=TA_LEFT,  leading=15)
    TITRE   = ps('TITRE',   fontName='Helvetica-Bold',   fontSize=16, alignment=TA_CENTER, leading=19)
    HEAD    = ps('HEAD',    fontName='Helvetica-Bold',   fontSize=10, alignment=TA_CENTER, leading=13, textColor=colors.white)
    HEADR   = ps('HEADR',   fontName='Helvetica-Bold',   fontSize=10, alignment=TA_RIGHT,  leading=13, textColor=colors.white)
    CELL    = ps('CELL',    fontName='Helvetica',        fontSize=10, alignment=TA_CENTER, leading=13)
    CELLR   = ps('CELLR',   fontName='Helvetica',        fontSize=10, alignment=TA_RIGHT,  leading=13)
    RECAPL  = ps('RECAPL',  fontName='Helvetica-Bold',   fontSize=10.5,alignment=TA_LEFT,  leading=14)
    RECAPR  = ps('RECAPR',  fontName='Helvetica-Bold',   fontSize=10.5,alignment=TA_RIGHT, leading=14)
    FOOT    = ps('FOOT',    fontName='Helvetica',        fontSize=10.5,alignment=TA_LEFT,  leading=15)

    def v(key, default=''):
        val = data.get(key, default)
        return str(val) if val not in (None, '') else default

    lignes  = data.get('lignes') or []
    tva_pct = float(data.get('tva_pct') or 19)
    total_ht, total_tva, total_ttc = _calc_totaux(lignes, tva_pct)

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        topMargin=1*cm, bottomMargin=1.3*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
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
        [Paragraph('Date',      LBLB), Paragraph(_fmt_date(v('date_commande')), META)],
        [Paragraph('Montant',   LBLB), Paragraph(_fmt_montant(total_ttc), META)],
        [Paragraph('Client',    LBLB), Paragraph(v('ref_client') or v('client_nom'), META)],
        [Paragraph('Echéance',  LBLB), Paragraph(_fmt_date(v('date_echeance')), META)],
    ]
    ref_box = Table(ref_box_rows, colWidths=[2.6*cm, 4.1*cm])
    ref_box.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))

    nom_block = [Paragraph(rec['nom'].upper(), NOM), Paragraph(_INDUREX_SLOGAN, SLOGAN)]
    entete = Table([[logo_cell, nom_block, ref_box]], colWidths=[2.3*cm, COL - 2.3*cm - 6.7*cm, 6.7*cm])
    entete.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX',    (2, 0), (2, 0), 0.6, BLACK),
    ]))
    story.append(entete)
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        f"RC: {rec['rc']}   NIF: {rec['nif']}   Al: {rec['na']}   NIS: {rec['nis']}", META
    ))
    if rec['adresse']:
        story.append(Paragraph(rec['adresse'], META))
    line2 = '   '.join(filter(None, [
        rec['commune'], rec['compte_bancaire'],
        f"Email: {rec['email']}" if rec['email'] else '',
        f"Tél: {rec['telephone']}" if rec['telephone'] else '',
        f"Fax: {rec['fax']}" if rec['fax'] else '',
    ]))
    if line2:
        story.append(Paragraph(line2, META))
    story.append(Spacer(1, 10))

    # ── Titre ───────────────────────────────────────────────────────────────────
    type_doc    = data.get('type_document')
    is_proforma = type_doc == 'PROFORMA'
    is_facture  = type_doc == 'FACTURE'
    titre_nom   = {'PROFORMA': 'Proforma', 'FACTURE': 'Facture'}.get(type_doc, 'Bon de Commande')
    titre_txt   = f"{titre_nom} N°: {v('numero')}"
    titre_tbl = Table([[Paragraph(titre_txt, TITRE)]], colWidths=[COL])
    titre_tbl.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, BLACK),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E5E5E5')),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(titre_tbl)
    story.append(Spacer(1, 10))

    # ── Bloc client (réf/RC/NIF/... à gauche, raison sociale/adresse à droite) ─
    client_lignes = [
        ('Réf Client',   v('ref_client')),
        ('N° RC',        v('client_rc')),
        ('NIF',          v('client_nif')),
        ('N° Article',   v('client_numero_article')),
        ('N° I.S',       v('client_nis')),
        ('Tél',          v('client_telephone')),
        ('Fax',          v('client_fax')),
        ('Email',        v('client_email')),
        ('Pièces Liées', v('pieces_liees')),
    ]
    if is_facture:
        client_lignes += [
            ('Mode Paiement', v('mode_paiement')),
            ('Référence',     v('reference_paiement')),
        ]
    gauche_rows = [[Paragraph(lbl, LBL), Paragraph(val, LBL)] for lbl, val in client_lignes]
    gauche_tbl = Table(gauche_rows, colWidths=[3.5*cm, 5*cm])
    gauche_tbl.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))

    droite_content = [Paragraph(v('client_nom'), LBLB)]
    for ligne_adresse in (v('client_adresse') or '').split('\n'):
        if ligne_adresse.strip():
            droite_content.append(Paragraph(ligne_adresse.strip(), LBL))
    droite_tbl = Table([[droite_content]], colWidths=[7.8*cm])
    droite_tbl.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    bloc_client = Table([[gauche_tbl, droite_tbl]], colWidths=[8.5*cm, 8.5*cm])
    bloc_client.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(bloc_client)
    story.append(Spacer(1, 12))

    # ── Tableau des articles ─────────────────────────────────────────────────────
    col_w   = [2.6*cm, 3.3*cm, 1.6*cm, 1.9*cm, 2.1*cm, 2.6*cm, 1.3*cm, 1.6*cm]
    headers = ['Réf Article', 'Désignation', 'Unité', 'Quantité', 'Prix U HT', 'Montant HT', 'R.%', 'Tva%']
    # En-têtes alignés sur le même sens que les cellules de données de leur colonne
    # (Prix U HT / Montant HT sont à droite, comme les montants qu'ils surplombent).
    header_styles = [HEAD, HEAD, HEAD, HEAD, HEADR, HEADR, HEAD, HEAD]
    rows    = [[Paragraph(h, s) for h, s in zip(headers, header_styles)]]

    for l in lignes:
        c = _calc_ligne(l, tva_pct)
        rows.append([
            Paragraph(str(l.get('ref_article', '')), CELL),
            Paragraph(str(l.get('description', '')), CELL),
            Paragraph(str(l.get('unite', 'KG')), CELL),
            Paragraph(_fmt_qte(l.get('quantite')), CELL),
            Paragraph(_fmt_montant(l.get('prix_unitaire')), CELLR),
            Paragraph(_fmt_montant(c['ht']), CELLR),
            Paragraph(f"{c['remise_pct']:.2f}", CELL),
            Paragraph(f"{c['tva_pct']:.2f}", CELL),
        ])

    tbl_style = TableStyle([
        ('GRID',          (0, 0), (-1, -1), 0.6, BLACK),
        ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#BFBFBF')),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ])

    # ── Récapitulatifs (gauche : Montant HT/TVA/Montant TVA — droite : totaux) ─
    recap_d = Table([
        [Paragraph('TOTAL H.T',    RECAPL), Paragraph(_fmt_montant(total_ht),  RECAPR)],
        [Paragraph('TOTAL T.V.A',  RECAPL), Paragraph(_fmt_montant(total_tva), RECAPR)],
        [Paragraph('TOTAL T.T.C',  RECAPL), Paragraph(_fmt_montant(total_ttc), RECAPR)],
        [Paragraph('',             RECAPL), Paragraph('',                      RECAPR)],
        [Paragraph('NET A PAYER',  RECAPL), Paragraph(_fmt_montant(total_ttc), RECAPR)],
    ], colWidths=[3.5*cm, 3.5*cm])
    recap_d.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    # Hauteurs de lignes réelles une fois calculées, pour caler le bloc de gauche dessus.
    recap_d.wrap(7 * cm, 2000)
    d_row_heights = recap_d._rowHeights

    # Bloc de gauche : uniquement les 3 colonnes Montant HT/TVA/Montant TVA — élargies
    # pour occuper toute la largeur disponible jusqu'à la marge gauche, et la ligne de
    # données étirée en hauteur pour occuper tout l'espace du bloc de droite (pas de
    # colonnes/lignes vides ajoutées).
    g_col_w = [COL - 7*cm - 6.1*cm, 2.6*cm, 3.5*cm]  # Montant HT / TVA / Montant TVA
    g_row_h = [d_row_heights[0], sum(d_row_heights[1:])]
    recap_g = Table([
        [Paragraph('Montant HT', HEAD), Paragraph('TVA', HEAD), Paragraph('Montant TVA', HEAD)],
        [Paragraph(_fmt_montant(total_ht), CELL), Paragraph(f"{tva_pct:.2f}", CELL), Paragraph(_fmt_montant(total_tva), CELL)],
    ], colWidths=g_col_w, rowHeights=g_row_h)
    recap_g.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 1), (-1, 1), 'TOP'),
    ]))

    recap_wrapper = Table([[recap_g, recap_d]], colWidths=[COL - 7*cm, 7*cm])
    recap_wrapper.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    # ── Arrêté du bon de commande / proforma (montant en lettres) ─────────────
    arrete_doc_nom = {'PROFORMA': 'la Présente Proforma', 'FACTURE': 'la Présente Facture'}.get(
        type_doc, 'le Présent Bon de Commande')
    arrete_tbl = Table([[Paragraph(
        f"Arrêtée {arrete_doc_nom} à la Somme de : <b>{montant_en_lettres(total_ttc)}</b>", FOOT
    )]], colWidths=[COL])
    arrete_tbl.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))

    # ── Le tableau d'articles est étiré pour occuper l'espace restant de la page
    # (comme le formulaire papier pré-imprimé où la zone articles est une grande
    # case vide, quel que soit le nombre de lignes réellement saisies).
    avail_w   = A4[0] - 3 * cm
    usable_h  = A4[1] - 1 * cm - 1.3 * cm
    top_h     = sum(fl.wrap(avail_w, 20000)[1] for fl in story)
    tbl_no_filler = Table(rows, colWidths=col_w)
    tbl_no_filler.setStyle(tbl_style)
    tbl_h     = tbl_no_filler.wrap(avail_w, 20000)[1]
    bottom_h  = (
        8 +  # Spacer après le tableau
        recap_wrapper.wrap(avail_w, 20000)[1] +
        12 +  # Spacer avant l'arrêté
        arrete_tbl.wrap(avail_w, 20000)[1]
    )
    # Marge de sécurité : le Frame interne de reportlab applique par défaut un
    # padding (~6pt de chaque côté) non compté dans topMargin/bottomMargin.
    filler_h = max(0.6 * cm, usable_h - top_h - tbl_h - bottom_h - 1.2 * cm)

    rows_with_filler = rows + [['' for _ in headers]]
    tbl = Table(rows_with_filler, colWidths=col_w, rowHeights=[None] * len(rows) + [filler_h])
    tbl.setStyle(tbl_style)

    story.append(tbl)
    story.append(Spacer(1, 8))
    story.append(recap_wrapper)
    story.append(Spacer(1, 12))
    story.append(arrete_tbl)

    doc.build(story, canvasmaker=_NumberedCanvas)
    buffer.seek(0)
    return buffer.read()
