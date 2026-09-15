"""
Génération du document Word (.docx) du Bon de Livraison (BL) — réplique la mise
en page du PDF (voir generate_bl.py) : gabarit générique ou gabarit SARL INDUREX
(en-tête vert, bloc référence, footer RC/NIF + badges ISO) selon le récupérateur.
"""
import io
from docx import Document
from docx.shared import Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from apps.bc.generate_bc_word import (
    _shade_cell, _cell_borders, _set_col_widths, _set_run, _cell_lines, _kv_rows,
    _add_picture_safe, _zero_spacing, _doc_p, _INDUREX_GREEN,
    _INDUREX_GREEN_HEX, _WHITE, COL, _INDUREX_CAPITAL_VERT,
)
from .generate_bl import _recuperateur_info, _destinataire_info, _fmt_date, _fmt_montant, _fmt_qte

_MODE_LIV_ABBR   = {'ENLEVEMENT': 'ENLEV', 'LIVRAISON': 'LIVR'}


def generate_bl_docx(data: dict) -> bytes:
    rec  = _recuperateur_info(data)
    dest = _destinataire_info(data)
    return _generate_bl_docx_indurex(data, rec, dest)


# ── Gabarit SARL INDUREX ────────────────────────────────────────────────────────

def _generate_bl_docx_indurex(data: dict, rec: dict, dest: dict) -> bytes:
    def v(key, default=''):
        val = data.get(key, default)
        return str(val) if val not in (None, '') else default

    lignes = data.get('lignes') or []

    doc = Document()
    for section in doc.sections:
        section.left_margin   = Cm(1.5)
        section.right_margin  = Cm(1.5)
        section.top_margin    = Cm(1)
        section.bottom_margin = Cm(1.5)

    entete = doc.add_table(rows=1, cols=3)
    _set_col_widths(entete, [2.3, COL - 2.3 - 6.7, 6.7])
    if rec['logo_path']:
        _add_picture_safe(entete.rows[0].cells[0], rec['logo_path'], 2, 2)

    _nom_lines = [{'text': (rec.get('nom') or '').upper(), 'size': 20, 'bold': True, 'color': _INDUREX_GREEN}]
    if rec.get('slogan'):
        _nom_lines.append({'text': rec['slogan'], 'size': 9.5, 'bold': True, 'color': _INDUREX_GREEN})
    if rec.get('capital_social'):
        _nom_lines.append({'text': rec['capital_social'], 'size': 7.5, 'bold': True, 'color': _INDUREX_CAPITAL_VERT})
    _cell_lines(entete.rows[0].cells[1], _nom_lines)

    ref_cell = entete.rows[0].cells[2]
    _cell_borders(ref_cell)
    ref_tbl = ref_cell.add_table(rows=4, cols=2)
    _set_col_widths(ref_tbl, [2.6, 4.1])
    _kv_rows(ref_tbl, [
        ('Référence', v('numero')),
        ('Date',      _fmt_date(v('date_livraison'))),
        ('Montant',   _fmt_montant(data.get('montant_reference') or 0)),
        ('Mode Liv',  _MODE_LIV_ABBR.get(v('mode_livraison'), v('mode_livraison'))),
    ], label_size=9.5, value_size=9.5)

    _doc_p(doc)

    titre_tbl = doc.add_table(rows=1, cols=1)
    _set_col_widths(titre_tbl, [COL])
    titre_cell = titre_tbl.rows[0].cells[0]
    _shade_cell(titre_cell, _INDUREX_GREEN_HEX)
    _cell_lines(titre_cell, [{
        'text': f"Bon Livraison N°: {v('numero')}", 'size': 16, 'bold': True, 'color': _WHITE,
        'align': WD_ALIGN_PARAGRAPH.CENTER,
    }])

    _doc_p(doc)

    client_lignes = [
        ('Réf Client:',   v('ref_client')),
        ('N° RC:',        v('client_rc')),
        ('NIF:',          v('client_nif')),
        ('N° Article:',   v('client_numero_article')),
        ('N° I.S:',       v('client_nis')),
        ('Tél:',          v('client_telephone')),
        ('Pièces Liées:', v('pieces_liees')),
    ]
    bloc_client = doc.add_table(rows=1, cols=2)
    _set_col_widths(bloc_client, [8.5, 8.5])
    gauche_cell = bloc_client.rows[0].cells[0]
    gauche_tbl  = gauche_cell.add_table(rows=len(client_lignes), cols=2)
    _set_col_widths(gauche_tbl, [2.4, 6.1])
    _kv_rows(gauche_tbl, client_lignes, label_size=10.5, value_size=10.5)

    # Nichée dans sa propre table (cf. generate_bc_word.py) pour que le cadre
    # n'épouse que son propre contenu, sans s'étirer sur les 9 lignes de gauche.
    droite_outer = bloc_client.rows[0].cells[1]
    droite_tbl = droite_outer.add_table(rows=1, cols=1)
    _set_col_widths(droite_tbl, [8.5])
    droite_cell = droite_tbl.rows[0].cells[0]
    _cell_borders(droite_cell)
    droite_lines = [{'text': dest['nom'], 'size': 10.5, 'bold': True}]
    for ligne_adresse in (dest['adresse'] or '').split('\n'):
        if ligne_adresse.strip():
            droite_lines.append({'text': ligne_adresse.strip(), 'size': 10.5})
    _cell_lines(droite_cell, droite_lines)

    _doc_p(doc)

    col_w   = [2.8, 9.2, 2.3, 2.7]
    headers = ['Réf Article', 'Désignation', 'Unité', 'Quantité']
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.style = 'Table Grid'
    _set_col_widths(tbl, col_w)
    for i, h in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        _shade_cell(cell, _INDUREX_GREEN_HEX)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_run(cell.paragraphs[0].add_run(h), size=10, bold=True, color=_WHITE)
    for l in lignes:
        row = tbl.add_row().cells
        vals = [str(l.get('ref_article', '')), str(l.get('description', '')),
                str(l.get('unite', 'KG')), _fmt_qte(l.get('quantite'))]
        for j, val in enumerate(vals):
            row[j].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _set_run(row[j].paragraphs[0].add_run(val), size=10)

    if rec['cachet_path'] or rec['signature_path']:
        _doc_p(doc)
        sign_p = _doc_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
        if rec['cachet_path']:
            _add_picture_safe(sign_p, rec['cachet_path'], 4)
        if rec['signature_path']:
            sign_p.add_run('   ')
            _add_picture_safe(sign_p, rec['signature_path'], 4.5, 2.4)

    footer = doc.sections[0].footer
    footer_p = footer.paragraphs[0]
    footer_p.text = ''
    _zero_spacing(footer_p)
    _set_run(footer_p.add_run(
        f"RC: {rec['rc']}  NIF: {rec['nif']}  Al: {rec['na']}  NIS: {rec['nis']}"
    ), size=7)
    if rec['adresse']:
        p_adr = _zero_spacing(footer.add_paragraph())
        _set_run(p_adr.add_run(rec['adresse']), size=7)
    footer_extra = '  '.join(filter(None, [
        rec['commune'],
        f"Email: {rec['email']}" if rec['email'] else '',
        f"Tél: {rec['telephone']}" if rec['telephone'] else '',
        f"Fax: {rec['fax']}" if rec['fax'] else '',
    ]))
    if footer_extra:
        p_extra = _zero_spacing(footer.add_paragraph())
        _set_run(p_extra.add_run(footer_extra), size=7)

    iso_paths = [p for p in (rec.get('iso_9001_path'), rec.get('iso_14001_path'), rec.get('iso_45001_path')) if p]
    if iso_paths:
        p_iso = _zero_spacing(footer.add_paragraph())
        p_iso.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for path in iso_paths:
            _add_picture_safe(p_iso, path, 1.5)
            p_iso.add_run('  ')

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()
