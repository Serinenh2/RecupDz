"""
Génération du PDF Bon de Commande (BC) — reproduit le formulaire papier :
en-tête récupérateur (logo, identité, agrément, RC/NIF/NA/NIS), client,
tableau des déchets avec prix unitaires, récapitulatif HT/TVA/TTC, signature.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
                                PageBreak, Frame, PageTemplate, NextPageTemplate)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
import functools

BLACK = colors.black
GREEN = colors.HexColor('#3B6D11')
COL   = 17 * cm

# ── Typographie SARL INDUREX : Montserrat, en-tête vert (#3C7A42) — identité
#    visuelle propre à cette société, distincte du style générique ci-dessus ──
_INDUREX_GREEN = colors.HexColor('#3C7A42')
_FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
if 'Montserrat-Bold' not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont('Montserrat',          os.path.join(_FONTS_DIR, 'Montserrat-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('Montserrat-SemiBold', os.path.join(_FONTS_DIR, 'Montserrat-SemiBold.ttf')))
    pdfmetrics.registerFont(TTFont('Montserrat-Bold',     os.path.join(_FONTS_DIR, 'Montserrat-Bold.ttf')))

# Bande réservée en bas des documents INDUREX pour les 3 badges de certification
# ISO (9001/14001/45001) — dessinés par _NumberedCanvas au-dessus du numéro de page.
_INDUREX_BOTTOM_MARGIN = 3.5 * cm


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
                'signature_path':  r.signature_electronique.path if r.signature_electronique else None,
                'cachet_path':     r.cachet_electronique.path if r.cachet_electronique else None,
                'iso_9001_path':   r.iso_9001.path if r.iso_9001 else None,
                'iso_14001_path':  r.iso_14001.path if r.iso_14001 else None,
                'iso_45001_path':  r.iso_45001.path if r.iso_45001 else None,
            }
        except Recuperateur.DoesNotExist:
            pass
    return {
        'nom': data.get('recuperateur_nom') or '', 'agrement_num': '', 'agrement_date': '',
        'adresse': '', 'commune': '', 'code_postal': '', 'rc': '', 'nif': '', 'na': '', 'nis': '',
        'telephone': '', 'fax': '', 'email': '', 'compte_bancaire': '',
        'responsable': '', 'logo_path': None, 'signature_path': None, 'cachet_path': None,
        'iso_9001_path': None, 'iso_14001_path': None, 'iso_45001_path': None,
    }


def _signature_flowable(rec, align='RIGHT', cachet_size=2.8*cm, sig_w=3*cm, sig_h=1.6*cm):
    """Table [cachet, signature] (les images présentes) prête à ajouter au story —
    None si le récupérateur n'a téléversé ni cachet ni signature électronique."""
    imgs = []
    widths = []
    if rec.get('cachet_path'):
        try:
            imgs.append(Image(rec['cachet_path'], width=cachet_size, height=cachet_size))
            widths.append(cachet_size + 0.3*cm)
        except Exception:
            pass
    if rec.get('signature_path'):
        try:
            imgs.append(Image(rec['signature_path'], width=sig_w, height=sig_h))
            widths.append(sig_w + 0.3*cm)
        except Exception:
            pass
    if not imgs:
        return None
    tbl = Table([imgs], colWidths=widths)
    tbl.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), align), ('VALIGN', (0, 0), (-1, -1), 'BOTTOM')]))
    return tbl


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


# ── Page CGV pleine page (verso de la Facture) : reproduit les marges du
#    document papier original (~1 cm de chaque côté), sans pied de page ISO
#    ni identité RC/NIF — ceux-ci restent sur la page 1 uniquement. ──
_CGV_MARGIN_LR     = 1.05 * cm   # marges gauche/droite du scan (~5%% de la largeur)
_CGV_MARGIN_TOP    = 1.15 * cm
_CGV_MARGIN_BOTTOM = 0.75 * cm   # cadre jusqu'à ~97%% de la page, comme le scan
_CGV_WIDTH         = A4[0] - 2 * _CGV_MARGIN_LR


def _add_cgv_page_template(doc):
    """Ajoute au document le gabarit pleine page 'CGV' utilisé par le verso de la
    Facture (activé par NextPageTemplate dans _conditions_generales_story).
    Doit être appelé AVANT doc.build() ; SimpleDocTemplate ajoutera ensuite ses
    gabarits 'First'/'Later', d'où le _firstPageTemplateIndex pointé sur 'First'."""
    frame = Frame(_CGV_MARGIN_LR, _CGV_MARGIN_BOTTOM, _CGV_WIDTH,
                  A4[1] - _CGV_MARGIN_TOP - _CGV_MARGIN_BOTTOM, id='cgv',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='CGV', frames=[frame], pagesize=A4)])
    doc._firstPageTemplateIndex = 1


# Rouge du document original (texte, intitulés, titre et cadre).
_CGV_ROUGE = colors.HexColor('#E03A3A')

# ── Sections 1 à 7 : texte courant ────────────────────────────────────────────
_CGV_SECTIONS = [
    ("1 - Application des conditions générales de vente",
     "La remise de toute commande implique, de la part de l'acheteur, l'acceptation sans réserve des présentes "
     "conditions générales de vente, auxquelles il ne peut être dérogé que par accord exprès dans notre "
     "confirmation. Ces conditions priment les conditions d'achat pouvant figurer sur les documents de "
     "l'acheteur, sauf accord contraire et écrit de notre Société."),
    ("2 - Commandes",
     "Les marchés et commandes ne deviennent valables et définitifs qu'après acceptation expresse de notre part "
     "et confirmation par écrit. Nos agents n'ont pas qualité pour traiter définitivement. Toutes les commandes "
     "enregistrées par eux sont prises sous réserve d'acceptation de notre Société."),
    ("3 - Délais",
     "Les délais portés sur nos documents commerciaux sont toujours indicatifs. Notre Société se réserve le droit "
     "de modifier, suspendre ou annuler ses engagements, en cas de non-respect réitéré des conditions de "
     "paiement, de non fourniture de renseignements nécessaires à l'exécution des commandes, de guerre civile ou "
     "autre, grève, lock-out, accident d'outillage, interruption ou retard dans les approvisionnements, sinistre "
     "de toute nature, fait du prince et, de façon générale, en cas de force majeure, sans que la modification, "
     "suspension ou annulation puisse donner lieu à indemnité de quelque nature que ce soit. En cas de "
     "difficultés d'approvisionnement, notre Société informera le client des cas ou événements ci-dessus, non "
     "limitativement énumérés, et lui fera connaître éventuellement les nouveaux délais de livraison."),
    ("4 - Livraisons",
     "Quelles que soient la destination des produits et matériels, et les conditions de vente, la livraison est "
     "réputée effectuée dans nos entrepôts, et implique transfert de responsabilité à la charge de l'acheteur. "
     "Dans tous les cas ceux-ci voyagent aux risques et périls de l'acheteur, et ce principe ne saurait subir de "
     "dérogation par le fait d'indications telles que remise franco, contre remboursement, ou avance des frais de "
     "transport... Il appartient donc à l'acheteur de faire, à l'arrivée des produits et matériels, toutes "
     "vérifications utiles et s'il y a lieu, d'effectuer toutes réserves et démarches en cas de perte partielle "
     "ou totale, d'avarie, de retard, ainsi que d'exercer tout recourt contre le transporteur. La responsabilité "
     "civile de notre Société ne pourra être mise en cause, en cas de détérioration, avarie ou perte totale ou "
     "partielle des produits et matériels, quelle qu'en soit la cause lorsque ceux-ci, mis à disposition du "
     "client, auront à sa demande été entreposés par nos soins dans nos ateliers ou dans les locaux appartenant "
     "à des tiers."),
    ("5 - Prix",
     "Nos prix s'entendent pour des produits pris et emballés en nos ateliers. Les produits sont facturés au prix "
     "convenu lors de la commande ou de la confirmation. Nos factures, outre les indications légales, "
     "mentionnent le cas échéant :<br/>"
     " - les remises acquises dans leur principe et leur montant,<br/>"
     " - la ou les dates de règlement, - l'escompte applicable en cas de paiement anticipé par rapport aux "
     "présentes conditions générales de vente.<br/>"
     " - les pénalités de retard en cas de non-paiement aux échéances fixées."),
    ("6 - Paiement",
     "En cas de remise d'un chèque ou de création d'un effet de commerce, le paiement ne sera réputé réaliser "
     "qu'au moment de l'encaissement ou du règlement à échéances convenues. Tous nos produits et matériels sont "
     "payables selon les conditions préalablement entendues entre les deux parties, sauf convention contraire, "
     "spéciale pour chaque affaire traitée et pour laquelle notre accord préalable et écrit sera nécessaire. La "
     "date de mise à disposition ou à défaut la date d'expédition, constitue le point de départ du ou des délais "
     "de paiement convenus. Toute détérioration du crédit de l'acheteur pourra justifier l'exigence de garanties, "
     "ou d'un règlement comptant ou par traite payable à vue, avant l'exécution des commandes reçues."),
    ("7 - Réclamations et garantie",
     "Notre Société assure la garantie des vices cachés dans les conditions légales : toutefois, l'acheteur "
     "dispose d'un délai de 30 jours à compter de la découverte du vice caché pour nous notifier ses réserves. "
     "En ce qui concerne les vices apparents, l'acheteur doit émettre les réserves nécessaires dans les 3 jours "
     "suivant la réception des produits, par lettre recommandée avec A.R. Pour être recevables, les réclamations "
     "devront être détaillées et précises, en particulier s'il s'agit de malfaçons ou d'erreurs de spécification. "
     "En aucun cas une quelconque réclamation n'autorise l'acheteur à suspendre ou refuser le paiement du prix."),
]

# ── Sections 8 et 9 : présentées dans un cadre rouge (comme sur l'original) ──
_CGV_SECTIONS_ENCADREES = [
    ("8 - Clause de réserve de propriété",
     "Toutes nos ventes sont conclues avec réserve de propriété. En conséquence, le transfert à l'acheteur de la "
     "propriété des produits vendus est suspendu jusqu'au paiement intégral du prix, intérêts et accessoires. "
     "Les risques sont mis à la charge de l'acheteur dès la mise à disposition des produits vendus sous réserve "
     "de propriété. L'acheteur doit donc veiller jusqu'au transfert de propriété à son profit, à la bonne "
     "conservation des produits et de leurs spécifications conformes aux documents de vente, ainsi qu'à la "
     "sauvegarde de leur identification. En outre et nonobstant l'application du paragraphe 6 qui précède, en "
     "cas de non-paiement aux échéances prévues, comme en cas d'inexécution de l'un quelconque des engagements "
     "de l'acheteur, le contrat de vente sera résolu de plein droit, si bon semble à notre Société, sans "
     "formalité judiciaire ou extra-judiciaire. 8 jours après une simple mise en demeure, par lettre "
     "recommandée, restée sans effet. La reprise par nos soins de produits revendiqués impose à l'acheteur "
     "l'obligation de réparer le préjudice résultant de l'indisponibilité des marchandises concernées. En "
     "conséquence, l'acheteur devra à titre de clause pénale, une indemnité fixée à 5% du prix convenu, par mois "
     "de détention des produits restitués. Si la résolution du contrat nous rend débiteurs d'acomptes "
     "préalablement reçus de l'acheteur, notre Société sera en droit de procéder à la compensation de cette "
     "dette avec la créance née de l'application de la clause pénale ci-dessus stipulée. En cas de revente ou de "
     "transformation des produits sous réserve de propriété par l'acheteur dans le cadre de son activité "
     "normale, et dans le cas où le prix n'en aurait pas été intégralement acquitté, l'acheteur cèdera à notre "
     "profit les créances nées de la revente, ou si notre produit est inclus dans un ensemble, le prorata de ses "
     "créances correspondant au montant de sa réserve de propriété."),
    ("9 - Différents",
     "Nonobstant toute stipulation contraire, en cas de contestation relative à une fourniture ou à son "
     "règlement, le tribunal de Rouiba sont seuls compétents, quelles que soient les conditions de vente et le "
     "mode de paiement accepté, même en cas d'appel en garantie ou de pluralité de défendeurs"),
]


def _conditions_generales_story():
    """Page 2 (verso) de la Facture : reproduction fidèle du document original —
    pleine page (gabarit 'CGV'), tout le texte en rouge, intitulés soulignés,
    sections 8 et 9 encadrées, aux dimensions du document papier."""
    TITRE   = ParagraphStyle('CGV_TITRE',   fontName='Helvetica-Bold', fontSize=15.5, alignment=TA_CENTER,
                              leading=18, spaceAfter=8, textColor=_CGV_ROUGE)
    SECTION = ParagraphStyle('CGV_SECTION', fontName='Helvetica-Bold', fontSize=9.0, alignment=TA_LEFT,
                              leading=11.0, spaceBefore=7.5, spaceAfter=1.5, textColor=_CGV_ROUGE)
    BODY    = ParagraphStyle('CGV_BODY',    fontName='Helvetica',      fontSize=8.5, alignment=TA_JUSTIFY,
                              leading=10.9, textColor=_CGV_ROUGE)

    story = [NextPageTemplate('CGV'), PageBreak(),
             Paragraph('CONDITIONS GENERALES DE VENTE', TITRE)]
    for titre, texte in _CGV_SECTIONS:
        story.append(Paragraph(f"<u>{titre}</u>", SECTION))
        story.append(Paragraph(texte, BODY))

    # Sections 8 et 9 dans un cadre rouge pleine largeur, comme sur le document original.
    encadre_flowables = []
    for titre, texte in _CGV_SECTIONS_ENCADREES:
        encadre_flowables.append(Paragraph(f"<u>{titre}</u>", SECTION))
        encadre_flowables.append(Paragraph(texte, BODY))
    encadre = Table([[encadre_flowables]], colWidths=[_CGV_WIDTH])
    encadre.setStyle(TableStyle([
        ('BOX',           (0, 0), (-1, -1), 1.2, _CGV_ROUGE),
        ('LEFTPADDING',   (0, 0), (-1, -1), 7),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 7),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 5))
    story.append(encadre)
    return story


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
    _add_cgv_page_template(doc)
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
    arrete_txt = (
        f"<u>Arrêter la {arrete_nom} en toutes taxes comprises a la somme de :</u> "
        f"<b>{total_ttc:,.2f} DZ</b>".replace(',', ' ')
    )
    validite_jours = data.get('validite_offre_jours')
    if data.get('type_document') == 'PROFORMA' and validite_jours not in (None, ''):
        arrete_txt += f"<br/><b>Validité de l'offre :</b> {int(validite_jours)} jours"
    story.append(Paragraph(arrete_txt, FOOT))
    story.append(Spacer(1, 30))

    # ── Signature ───────────────────────────────────────────────────────────────
    sign_flowable = _signature_flowable(rec)
    if sign_flowable:
        story.append(sign_flowable)
        story.append(Spacer(1, 4))
    story.append(Paragraph('Le Gérant', SIGN))
    if rec['responsable']:
        story.append(Paragraph(rec['responsable'], SIGN))

    if data.get('type_document') == 'FACTURE':
        story.extend(_conditions_generales_story())

        def _first_page_footer(canvas_obj, _doc):
            canvas_obj.saveState()
            canvas_obj.setFont('Helvetica-Bold', 9)
            canvas_obj.setFillColor(_CGV_ROUGE)
            canvas_obj.drawCentredString(A4[0] / 2, 1.0 * cm, 'Voir conditions générales de vente au verso')
            canvas_obj.restoreState()

        doc.build(story, onFirstPage=_first_page_footer)
    else:
        doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ── Nom et slogan fixes de l'en-tête SARL INDUREX (non stockés en base — identité
#    visuelle propre à cette société, indépendante de nom_commercial/nom_raison_sociale) ──
_INDUREX_NOM     = 'SARL INDUREX'
_INDUREX_SLOGAN  = 'INDUSTRIAL WASTE RECOVERY AND VALORIZATION'
_INDUREX_CAPITAL      = 'AU CAPITAL DE 1 000 000,00 DA'
_INDUREX_CAPITAL_VERT = colors.HexColor('#0F452B')


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


_FOOTER_LEFT, _FOOTER_RIGHT = 2 * cm, A4[0] - 2 * cm  # bord de contenu (aligné avec tous les tableaux)


class _NumberedCanvas(_pdfcanvas.Canvas):
    """Pied de page 'Page: n/total' — bufferise les pages pour connaître le total avant d'écrire.
    iso_paths / footer_paragraphs (optionnels, documents SARL INDUREX uniquement) : badges de
    certification ISO (gauche) et identité RC/NIF/NIS (droite), séparés par un filet vert,
    affichés sur chaque page au-dessus du numéro de page."""

    def __init__(self, *args, iso_paths=None, footer_paragraphs=None, verso_note=None, **kwargs):
        _pdfcanvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self._iso_paths = [p for p in (iso_paths or []) if p]
        self._footer_paragraphs = footer_paragraphs or []
        # Note "Voir conditions générales de vente au verso" (Facture uniquement) —
        # affichée en rouge, centrée, sous les badges ISO/l'identité RC/NIF, en bas
        # de la 1re page seulement (la 2e page est le verso lui-même).
        self._verso_note = verso_note

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for i, state in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            self.saveState()
            page_num_y = 0.8 * cm if i == 0 else 0.3 * cm  # verso CGV pleine page : numéro sous le cadre
            if i == 0 and self._verso_note:
                self.setFont('Helvetica-Bold', 9)
                self.setFillColor(_CGV_ROUGE)
                self.drawCentredString(A4[0] / 2, 0.8 * cm, self._verso_note)
                page_num_y = 0.35 * cm
            self.setFont('Helvetica', 8)
            self.setFillColor(colors.black)
            self.drawCentredString(A4[0] / 2, page_num_y, f"Page: {self._pageNumber}/{total_pages}")
            if i == 0:
                # Badges ISO et identité RC/NIF sur la 1re page uniquement — le verso
                # CGV reproduit le document papier original, sans pied de page.
                self._draw_footer()
            self.restoreState()
            _pdfcanvas.Canvas.showPage(self)
        _pdfcanvas.Canvas.save(self)

    def _draw_footer(self):
        if self._iso_paths or self._footer_paragraphs:
            # Filet vert séparant le pied de page (identité RC/NIF + badges ISO) du
            # contenu principal au-dessus (ex. la ligne "Arrêtée ... à la Somme de").
            self.setStrokeColor(_INDUREX_GREEN)
            self.setLineWidth(0.8)
            self.line(_FOOTER_LEFT, 3.45 * cm, _FOOTER_RIGHT, 3.45 * cm)

        # Badges ISO alignés à droite du pied de page.
        badge_left = _FOOTER_RIGHT
        if self._iso_paths:
            size, gap = 2 * cm, 0.5 * cm
            total_w = len(self._iso_paths) * size + (len(self._iso_paths) - 1) * gap
            badge_left = _FOOTER_RIGHT - total_w
            x = badge_left
            for path in self._iso_paths:
                try:
                    self.drawImage(path, x, 1.15 * cm, width=size, height=size,
                                    mask='auto', preserveAspectRatio=True, anchor='c')
                except Exception:
                    pass
                x += size + gap

        if not self._footer_paragraphs:
            return
        # Identité RC/NIF/NIS/adresse alignée à gauche, à côté des badges (sans filet séparateur).
        divider_x = badge_left - 0.6 * cm
        text_x = _FOOTER_LEFT
        text_w = (divider_x - 0.5 * cm if self._iso_paths else _FOOTER_RIGHT) - text_x
        y = 3.25 * cm
        for p in self._footer_paragraphs:
            _, h = p.wrap(text_w, 3 * cm)
            y -= h
            p.drawOn(self, text_x, y)


def _generate_bc_pdf_indurex(data: dict, rec: dict) -> bytes:
    buffer = io.BytesIO()

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    NOM     = ps('NOM',     fontName='Montserrat-Bold',     fontSize=20, alignment=TA_LEFT,   leading=23, textColor=_INDUREX_GREEN)
    SLOGAN  = ps('SLOGAN',  fontName='Montserrat-Bold', fontSize=9.5,alignment=TA_LEFT,   leading=13, textColor=_INDUREX_GREEN)
    CAPITAL = ps('CAPITAL', fontName='Montserrat-Bold', fontSize=7.5,alignment=TA_LEFT,   leading=10, textColor=_INDUREX_CAPITAL_VERT)
    META    = ps('META',    fontName='Helvetica',        fontSize=9.5,alignment=TA_LEFT,   leading=13)
    LBL     = ps('LBL',     fontName='Helvetica',        fontSize=10.5,alignment=TA_LEFT,  leading=15)
    LBLB    = ps('LBLB',    fontName='Helvetica-Bold',   fontSize=10.5,alignment=TA_LEFT,  leading=15)
    TITRE   = ps('TITRE',   fontName='Helvetica-Bold',   fontSize=16, alignment=TA_CENTER, leading=19, textColor=colors.white)
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
        topMargin=1*cm, bottomMargin=_INDUREX_BOTTOM_MARGIN, leftMargin=1.5*cm, rightMargin=1.5*cm)
    _add_cgv_page_template(doc)
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

    nom_block = [Paragraph(_INDUREX_NOM, NOM), Paragraph(_INDUREX_SLOGAN, SLOGAN), Paragraph(_INDUREX_CAPITAL, CAPITAL)]
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
    type_doc    = data.get('type_document')
    is_proforma = type_doc == 'PROFORMA'
    is_facture  = type_doc == 'FACTURE'
    titre_nom   = {'PROFORMA': 'Proforma', 'FACTURE': 'Facture'}.get(type_doc, 'Bon de Commande')
    titre_txt   = f"{titre_nom} N°: {v('numero')}"
    titre_tbl = Table([[Paragraph(titre_txt, TITRE)]], colWidths=[COL])
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
    if is_facture:
        client_lignes += [
            ('Mode Paiement:', v('mode_paiement')),
            ('Référence:',     v('reference_paiement')),
        ]
    gauche_rows = [[Paragraph(lbl, LBL), Paragraph(val, LBL)] for lbl, val in client_lignes]
    gauche_tbl = Table(gauche_rows, colWidths=[2.9*cm, 5.6*cm])
    gauche_tbl.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 2),
        ('LEFTPADDING', (1, 0), (1, -1), 3),
    ]))

    droite_content = [Paragraph(v('client_nom'), LBLB)]
    for ligne_adresse in (v('client_adresse') or '').split('\n'):
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
        ('BACKGROUND',    (0, 0), (-1, 0),  _INDUREX_GREEN),
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
        ('BACKGROUND', (0, 0), (-1, 0), _INDUREX_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 1), (-1, 1), 'TOP'),
    ]))

    recap_wrapper = Table([[recap_g, recap_d]], colWidths=[COL - 7*cm, 7*cm])
    recap_wrapper.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # ── Arrêté du bon de commande / proforma (montant en lettres) ─────────────
    arrete_doc_nom = {'PROFORMA': 'la Présente Proforma', 'FACTURE': 'la Présente Facture'}.get(
        type_doc, 'le Présent Bon de Commande')
    arrete_txt = f"Arrêtée {arrete_doc_nom} à la Somme de : <b>{montant_en_lettres(total_ttc)}</b>"
    validite_jours = data.get('validite_offre_jours')
    if is_proforma and validite_jours not in (None, ''):
        arrete_txt += f"<br/><b>Validité de l'offre :</b> {int(validite_jours)} jours"
    arrete_tbl = Table([[Paragraph(arrete_txt, FOOT)]], colWidths=[COL])
    arrete_tbl.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))

    # ── Le tableau d'articles est étiré pour occuper l'espace restant de la page
    # (comme le formulaire papier pré-imprimé où la zone articles est une grande
    # case vide, quel que soit le nombre de lignes réellement saisies).
    avail_w   = A4[0] - 3 * cm
    usable_h  = A4[1] - 1 * cm - _INDUREX_BOTTOM_MARGIN
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

    # Cachet/signature électroniques insérés dans la case vide de la zone
    # articles (comme le cachet humide apposé à la main sur le formulaire papier)
    # plutôt qu'ajoutés après l'arrêté, qui déborderait sur une 2e page puisque
    # la hauteur du tableau est calculée pour occuper exactement la page.
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
    story.append(Spacer(1, 8))
    story.append(recap_wrapper)
    story.append(Spacer(1, 12))
    story.append(arrete_tbl)

    if is_facture:
        story.extend(_conditions_generales_story())

    iso_paths  = [rec.get('iso_9001_path'), rec.get('iso_14001_path'), rec.get('iso_45001_path')]
    verso_note = 'Voir conditions générales de vente au verso' if is_facture else None
    doc.build(story, canvasmaker=functools.partial(
        _NumberedCanvas, iso_paths=iso_paths, footer_paragraphs=footer_paragraphs, verso_note=verso_note))
    buffer.seek(0)
    return buffer.read()