"""
Génération du PDF DSD — Déclaration des Déchets Spéciaux Dangereux
Conforme au Décret exécutif n°05-315 du 10 septembre 2005.
Document noir et blanc, pensé pour occuper pleinement ses deux pages A4.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, HRFlowable, PageBreak)
from reportlab.lib.enums import TA_CENTER
import io

BLACK = colors.black


def generate_dsd_pdf(data: dict) -> bytes:
    buffer = io.BytesIO()
    W, H = A4
    ML = 2*cm; MR = 2*cm; MT = 1.5*cm; MB = 1.5*cm
    COL = W - ML - MR

    def ps(n, **k):
        return ParagraphStyle(n, **k)

    T    = ps('T',   fontName='Helvetica-Bold', fontSize=14, alignment=TA_CENTER, leading=18)
    T2   = ps('T2',  fontName='Helvetica-Bold', fontSize=12.5, alignment=TA_CENTER, leading=16)
    REF  = ps('REF', fontName='Helvetica', fontSize=9, alignment=TA_CENTER, leading=12)
    SEC  = ps('SEC', fontName='Helvetica-Bold', fontSize=11.5, leading=15)
    SUB  = ps('SUB', fontName='Helvetica-Bold', fontSize=10.5, leading=14)
    LB   = ps('LB',  fontName='Helvetica-Bold', fontSize=10.5, leading=22)
    VL   = ps('VL',  fontName='Helvetica', fontSize=10.5, leading=22)
    HD   = ps('HD',  fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, leading=13)
    BN   = ps('BN',  fontName='Helvetica-Bold', fontSize=20, alignment=TA_CENTER, leading=24)
    SM   = ps('SM',  fontName='Helvetica', fontSize=9.5, leading=13)
    FT   = ps('FT',  fontName='Helvetica', fontSize=8, alignment=TA_CENTER, leading=11)

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

    def sec_hdr(txt):
        story = [Spacer(1, 12), Paragraph(txt.upper(), SEC),
                  HRFlowable(width='100%', thickness=1.2, color=BLACK), Spacer(1, 6)]
        return story

    def sub_hdr(txt):
        return [Spacer(1, 4), Paragraph(txt, SUB), Spacer(1, 5)]

    def champ(label, valeur, lw=6.5*cm):
        t = Table([[Paragraph(label, LB), Paragraph(f"<b>{valeur}</b>" if valeur else '', VL)]],
                   colWidths=[lw, COL - lw])
        t.setStyle(TableStyle([
            ('LINEBELOW', (1,0),(1,0), 0.5, BLACK),
            ('TOPPADDING', (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING', (0,0),(-1,-1), 0), ('VALIGN', (0,0),(-1,-1), 'BOTTOM'),
        ]))
        return t

    def double_champ(l1, v1, l2, v2, lw1=4*cm, lw2=3.5*cm):
        moitie = COL/2
        t = Table([[
            Paragraph(l1, LB), Paragraph(f"<b>{v1}</b>" if v1 else '', VL),
            Paragraph(l2, LB), Paragraph(f"<b>{v2}</b>" if v2 else '', VL),
        ]], colWidths=[lw1, moitie-lw1, lw2, moitie-lw2])
        t.setStyle(TableStyle([
            ('LINEBELOW', (1,0),(1,0), 0.5, BLACK), ('LINEBELOW', (3,0),(3,0), 0.5, BLACK),
            ('TOPPADDING', (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING', (0,0),(-1,-1), 0), ('VALIGN', (0,0),(-1,-1), 'BOTTOM'),
        ]))
        return t

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        topMargin=MT, bottomMargin=MB, leftMargin=ML, rightMargin=MR)
    s = []

    # ── PAGE 1 ─────────────────────────────────────────────────────────────────
    s.append(Paragraph('RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE', T))
    s.append(HRFlowable(width='100%', thickness=1.5, color=BLACK))
    s.append(Spacer(1, 10))
    s.append(Paragraph('DÉCLARATION DES DÉCHETS SPÉCIAUX DANGEREUX', T2))
    s.append(Paragraph("Décret exécutif n°05-315 du 10 septembre 2005 — Journal Officiel n°62", REF))
    s.append(Spacer(1, 10))
    s.append(double_champ('Année :', v('annee'), 'Date de transmission :', fmt_date(v('date_transmission')),
        lw1=2.2*cm, lw2=4.5*cm))

    s.extend(sec_hdr('Identification du générateur et/ou du détenteur'))
    s.append(double_champ('Statut :', v('statut_juridique'), 'Dénomination :', v('denomination'),
        lw1=2.2*cm, lw2=3.5*cm))
    s.append(champ('Siège social :', v('siege_social')))
    s.append(champ("Domaine d'activité :", v('domaine_activite')))
    s.append(champ('Certification :', v('certification')))
    s.append(champ('Responsable déchets :', v('responsable_dechets')))

    s.extend(sec_hdr('A — Nature, quantité et caractéristiques des déchets spéciaux dangereux générés'))
    s.extend(sub_hdr('1 — Nature des déchets spéciaux dangereux générés'))
    s.append(champ('Matière première :', v('matiere_premiere')))
    s.append(champ('Dénomination du déchet :', v('denomination_dechet')))
    s.append(double_champ('Code du déchet :', v('code_dechet'), 'Consistance :', v('consistance'),
        lw1=3.6*cm, lw2=2.8*cm))
    s.append(champ('Précisions / Mélanges :', v('autres_precisions')))
    s.append(Spacer(1, 8))

    s.extend(sub_hdr('2 — Quantité & 3 — Caractéristiques'))
    quantite_box = Table([
        [Paragraph('QUANTITÉ GÉNÉRÉE', HD)],
        [Paragraph(v('quantite_generee', '0'), BN)],
        [Paragraph('tonnes / an', SM)],
    ], colWidths=[5*cm])
    quantite_box.setStyle(TableStyle([
        ('BOX', (0,0),(-1,-1), 0.8, BLACK),
        ('TOPPADDING', (0,0),(-1,-1), 7), ('BOTTOMPADDING', (0,0),(-1,-1), 7),
        ('ALIGN', (0,0),(-1,-1), 'CENTER'),
    ]))
    details_carac = Table([
        [Paragraph('Composition chimique :', LB)],
        [Paragraph(v('composition_chimique'), VL)],
        [Spacer(1, 6)],
        [Paragraph('Critère de dangerosité :', LB)],
        [Paragraph(v('critere_dangerosite'), VL)],
    ], colWidths=[COL - 5*cm - 0.5*cm])
    details_carac.setStyle(TableStyle([
        ('TOPPADDING', (0,0),(-1,-1), 1), ('BOTTOMPADDING', (0,0),(-1,-1), 1),
        ('LEFTPADDING', (0,0),(-1,-1), 10), ('VALIGN', (0,0),(-1,-1), 'TOP'),
    ]))
    qc = Table([[quantite_box, details_carac]], colWidths=[5*cm, COL-5*cm])
    qc.setStyle(TableStyle([
        ('BOX', (0,0),(-1,-1), 0.5, BLACK), ('LINEAFTER', (0,0),(0,-1), 0.5, BLACK),
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
    ]))
    s.append(qc)
    s.append(Spacer(1, 8))

    s.extend(sub_hdr('4 — Stockage des déchets spéciaux dangereux'))
    stq = Table([[
        Paragraph('STOCKAGE TEMPORAIRE', HD),
        Paragraph(f"{v('stockage_temporaire_qte', '0')} t/an",
            ps('sq', fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER)),
        Paragraph('STOCKAGE PERMANENT', HD),
        Paragraph(f"{v('stockage_permanent_qte', '0')} t/an",
            ps('sq2', fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER)),
    ]], colWidths=[COL/4]*4)
    stq.setStyle(TableStyle([
        ('BOX', (0,0),(-1,-1), 0.5, BLACK), ('INNERGRID', (0,0),(-1,-1), 0.5, BLACK),
        ('TOPPADDING', (0,0),(-1,-1), 6), ('BOTTOMPADDING', (0,0),(-1,-1), 6),
    ]))
    s.append(stq)
    s.append(Spacer(1, 4))
    s.append(champ('Modalités de stockage :', v('modalites_stockage')))

    # ── PAGE 2 ─────────────────────────────────────────────────────────────────
    s.append(PageBreak())
    s.append(Paragraph('DÉCLARATION DES DÉCHETS SPÉCIAUX DANGEREUX — SUITE (Page 2/2)', T2))
    s.append(HRFlowable(width='100%', thickness=1.5, color=BLACK))
    s.append(Spacer(1, 10))

    s.extend(sec_hdr('B — Modes de traitement'))
    s.append(double_champ('Modalités de gestion :', v('modalites_gestion'),
                           'Modalités de contrôle :', v('modalites_controle'),
                           lw1=5*cm, lw2=5*cm))
    s.append(champ("Modalités d'élimination :", v('modalites_elimination')))
    s.append(champ("Types d'installation de traitement :", v('types_installation')))
    s.append(champ('Types de traitement :', v('types_traitement')))
    s.append(double_champ('Quantités traitées :', f"{v('quantites_traitees')} t/an" if v('quantites_traitees') else '',
                           'Rendement :', v('rendement_traitement'), lw1=4.2*cm, lw2=2.8*cm))
    s.append(Spacer(1, 8))

    s.extend(sec_hdr('C — Mesures prises et à prévoir pour éviter la production des déchets spéciaux dangereux'))
    tq = Table([[
        Paragraph('RÉUTILISATION', HD), Paragraph('RECYCLAGE', HD),
        Paragraph('VALORISATION', HD), Paragraph('ÉLIMINATION', HD),
    ], [
        Paragraph(f"{v('reutilisation_qte', '0')} t/an", ps('q1', fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER)),
        Paragraph(f"{v('recyclage_qte', '0')} t/an", ps('q2', fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER)),
        Paragraph(f"{v('valorisation_qte', '0')} t/an", ps('q3', fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER)),
        Paragraph(f"{v('elimination_qte', '0')} t/an", ps('q4', fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER)),
    ]], colWidths=[COL/4]*4)
    tq.setStyle(TableStyle([
        ('BOX', (0,0),(-1,-1), 0.5, BLACK), ('INNERGRID', (0,0),(-1,-1), 0.5, BLACK),
        ('TOPPADDING', (0,0),(-1,-1), 8), ('BOTTOMPADDING', (0,0),(-1,-1), 8),
    ]))
    s.append(tq)
    s.append(Spacer(1, 10))

    mesures = [
        ('1 — Techniques de minimisation', v('mesures_min_prises'), v('mesures_min_envisager')),
        ('2 — Bonnes pratiques environnementales', v('mesures_bpe_prises'), v('mesures_bpe_envisager')),
        ('3 — Techniques disponibles', v('mesures_tech_prises'), v('mesures_tech_envisager')),
        ('4 — Techniques de production plus propres', v('mesures_pp_prises'), v('mesures_pp_envisager')),
        ('5 — Gestion préventive et maîtrise des risques', v('mesures_risques_prises'), v('mesures_risques_envisager')),
    ]
    hrow = [Paragraph('', HD), Paragraph('MESURES PRISES', HD), Paragraph('MESURES À ENVISAGER', HD)]
    mrows = [hrow] + [[Paragraph(f'<b>{titre}</b>', SM), Paragraph(prise, SM), Paragraph(envisager, SM)]
                       for titre, prise, envisager in mesures]
    col_m = (COL - 5*cm) / 2
    mt = Table(mrows, colWidths=[5*cm, col_m, col_m],
               rowHeights=[0.7*cm] + [1.4*cm]*5)
    mt.setStyle(TableStyle([
        ('BOX', (0,0),(-1,-1), 0.5, BLACK), ('INNERGRID', (0,0),(-1,-1), 0.5, BLACK),
        ('TOPPADDING', (0,0),(-1,-1), 5), ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING', (0,0),(-1,-1), 8), ('VALIGN', (0,0),(-1,-1), 'TOP'),
    ]))
    s.append(mt)
    s.append(Spacer(1, 8))

    sig = Table([[
        Paragraph('Fait à :', LB), Paragraph('.' * 35, VL),
        Paragraph('Date :', LB), Paragraph(f"<b>{fmt_date(v('date_transmission'))}</b>" if v('date_transmission') else '', VL),
    ]], colWidths=[2*cm, COL/2-2*cm, 2*cm, COL/2-2*cm])
    sig.setStyle(TableStyle([
        ('TOPPADDING', (0,0),(-1,-1), 3), ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING', (0,0),(-1,-1), 0),
    ]))
    s.append(sig)
    s.append(Spacer(1, 4))
    s.append(champ('Nom et qualité du signataire :', v('responsable_dechets'), lw=5.5*cm))
    s.append(Spacer(1, 6))
    s.append(champ('Signature et cachet :', '', lw=4*cm))

    s.append(Spacer(1, 6))
    s.append(HRFlowable(width='100%', thickness=0.8, color=BLACK))
    s.append(Spacer(1, 4))
    s.append(Paragraph(
        "Conformément au Décret exécutif n°05-315 du 10 septembre 2005 — "
        "Loi n°01-19 du 12 décembre 2001 — "
        "À transmettre dans un délai n'excédant pas 3 mois après la clôture de l'année considérée.", FT))

    doc.build(s)
    buffer.seek(0)
    return buffer.read()
