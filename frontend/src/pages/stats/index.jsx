import { useEffect, useState, useMemo } from 'react'
import { Calendar, CalendarRange, CalendarDays, CalendarClock, Package, Download, Loader2, AlertTriangle, Home, Layers, Boxes } from 'lucide-react'
import api from '../../api'
import DateInput from '../../components/common/DateInput'

const PERIODES = [
  { key: 'QUOTIDIENNE', label: 'Quotidienne',          icon: CalendarClock },
  { key: 'PRECISE',     label: 'Date précise',         icon: Calendar },
  { key: 'INTERVALLE',  label: 'Intervalle de dates',  icon: CalendarRange },
  { key: 'MENSUELLE',   label: 'Mensuelle',            icon: CalendarDays },
  { key: 'ANNUELLE',    label: 'Annuelle',             icon: CalendarDays },
]

const MOIS = [
  'Janvier','Février','Mars','Avril','Mai','Juin',
  'Juillet','Août','Septembre','Octobre','Novembre','Décembre',
]

const UNITE_LABELS = { KG: 'kg', TONNE: 't', M3: 'm³', LITRE: 'L', UNITE: 'unité' }

const today = () => new Date().toISOString().split('T')[0]
const thisYear = () => new Date().getFullYear()

const CLASSE_LABELS = { D: 'Déchets ordinaires', S: 'Déchets spéciaux', SD: 'Déchets spéciaux dangereux', MA: 'Ménagers et assimilés', I: 'Inertes' }

const VUES = [
  { key: 'TOUS',         label: 'Tous les dossiers' },
  { key: 'OPERATION',    label: "Par numéro d'opération" },
  { key: 'GENERATEUR',   label: 'Par générateur' },
  { key: 'TYPE',         label: 'Par type de déchets' },
  { key: 'DESIGNATION',  label: 'Par désignation précise des déchets' },
  { key: 'STOCKAGE',     label: 'Déchets en stock' },
  { key: 'VALORISATION', label: 'Déchets valorisés' },
  { key: 'ELIMINATION',  label: 'Déchets éliminés' },
  { key: 'STOCK_ACTUEL', label: 'Stock actuel par type de déchets' },
]

// Destinations physiques qui font sortir un déchet du stock disponible
const SORTIE_TYPES = ['VALORISATION', 'ELIMINATION', 'RECYCLAGE', 'CET']

// Stock disponible = quantité récupérée − quantité déjà envoyée en valorisation/élimination/CET,
// calculé dossier par dossier (via `repartitions`) puis cumulé par type de déchet.
function calculerStock(rows) {
  const parType = new Map()
  rows.filter(r => r.statut !== 'ANNULEE').forEach(r => {
    const sortie = (r.repartitions || [])
      .filter(rep => SORTIE_TYPES.includes(rep.type))
      .reduce((s, rep) => s + Number(rep.quantite || 0), 0)
    const stock = Number(r.quantite || 0) - sortie
    if (stock <= 0) return
    const key = r.designation_dechet || r.code_dechet || 'Non renseigné'
    if (!parType.has(key)) {
      parType.set(key, { designation: key, code: r.code_dechet, unite: r.unite_display || r.unite, operations: [], stock_total: 0 })
    }
    const t = parType.get(key)
    t.operations.push({
      numero: r.numero, recupere: Number(r.quantite || 0), sortie, stock,
      unite: r.unite_display || r.unite, date: r.date_recuperation,
    })
    t.stock_total += stock
  })
  return Array.from(parType.values()).sort((a, b) => b.stock_total - a.stock_total)
}

// Vues qui filtrent les dossiers par destination finale plutôt que de les regrouper
const DESTINATIONS_PAR_VUE = {
  STOCKAGE:     ['STOCKAGE'],
  VALORISATION: ['VALORISATION', 'RECYCLAGE'],
  ELIMINATION:  ['ELIMINATION', 'CET'],
}

// Vues qui regroupent les dossiers par dimension plutôt que de les lister un par un
const DIMENSIONS_PAR_VUE = {
  GENERATEUR:  r => r.generateur_nom || 'Non renseigné',
  TYPE:        r => CLASSE_LABELS[r.classe_dechet] || r.classe_dechet || 'Non classé',
  DESIGNATION: r => r.designation_dechet || 'Non renseigné',
}

function aggregerParDimension(rows, dim) {
  const keyFn = DIMENSIONS_PAR_VUE[dim]
  const m = new Map()
  rows.forEach(r => {
    const key = keyFn(r)
    if (!m.has(key)) m.set(key, [])
    m.get(key).push(r)
  })
  return Array.from(m.entries())
    .map(([label, items]) => ({ label, count: items.length, totaux: totauxParUnite(items) }))
    .sort((a, b) => b.count - a.count)
}

function totauxParUnite(rows) {
  const m = new Map()
  rows.forEach(r => {
    const key = r.unite || 'KG'
    const label = UNITE_LABELS[key] || r.unite_display || key
    const prev = m.get(key)?.value || 0
    m.set(key, { label, value: prev + Number(r.quantite || 0) })
  })
  return Array.from(m.values())
}

function exportCsv(rows, nomFichier) {
  const header = ["N° opération",'Désignation déchet','Quantité récupérée','Unité','Générateur des déchets','Date de récupération']
  const lines = rows.map(r => [
    r.numero, r.designation_dechet, r.quantite, r.unite_display || r.unite, r.generateur_nom || '', r.date_recuperation,
  ].map(v => `"${String(v ?? '').replace(/"/g,'""')}"`).join(';'))
  const csv = [header.join(';'), ...lines].join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nomFichier
  a.click()
  URL.revokeObjectURL(url)
}

// ── Rubrique CET — quantités envoyées en Centre d'Enfouissement Technique ─────
function RubriqueCET({ bls, loading }) {
  const lignes = useMemo(() =>
    bls.flatMap(bl =>
      (bl.lignes || []).map(l => ({
        ...l,
        cet_nom:  bl.destinataire_nom || `CET${bl.destinataire_commune ? ' ' + bl.destinataire_commune : ''}`,
        bl_num:   bl.numero,
        date:     bl.date_livraison,
      }))
    )
  , [bls])

  const parCet = useMemo(() => {
    const m = new Map()
    lignes.forEach(l => {
      const k = l.cet_nom
      if (!m.has(k)) m.set(k, { total_kg: 0, total_t: 0, count: 0, lignes: [] })
      const e = m.get(k)
      e.lignes.push(l)
      e.count++
      if (l.unite === 'KG')    e.total_kg += Number(l.quantite || 0)
      if (l.unite === 'TONNE') e.total_t  += Number(l.quantite || 0)
    })
    return Array.from(m.entries()).map(([nom, v]) => ({ nom, ...v }))
  }, [lignes])

  const totalLignes = lignes.length

  const exportCetCsv = () => {
    const hdr = ['CET','Désignation','Quantité','Unité','N° BL','Date livraison']
    const rows = lignes.map(l => [l.cet_nom, l.description, l.quantite, l.unite, l.bl_num, l.date]
      .map(v => `"${String(v ?? '').replace(/"/g,'""')}"`).join(';'))
    const csv = [hdr.join(';'), ...rows].join('\n')
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'statistiques_cet.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card p-5 space-y-4 border-l-4 border-slate-400">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Layers size={18} className="text-slate-500"/> Déchets envoyés au CET (Centre d'Enfouissement Technique)
        </h2>
        <button onClick={exportCetCsv} disabled={lignes.length===0} className="btn-secondary btn-sm">
          <Download size={13}/> Exporter CSV
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <div className="card p-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-500 flex items-center justify-center flex-shrink-0">
            <Package size={16} className="text-white"/>
          </div>
          <div>
            <p className="text-xl font-black text-slate-900 dark:text-white">{bls.length}</p>
            <p className="text-xs text-slate-500">BL émis vers CET</p>
          </div>
        </div>
        <div className="card p-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-500 flex items-center justify-center flex-shrink-0">
            <Layers size={16} className="text-white"/>
          </div>
          <div>
            <p className="text-xl font-black text-slate-900 dark:text-white">{totalLignes}</p>
            <p className="text-xs text-slate-500">Ligne(s) de déchet</p>
          </div>
        </div>
        {parCet.map(c => (
          <div key={c.nom} className="card p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-slate-400 flex items-center justify-center flex-shrink-0">
              <Layers size={16} className="text-white"/>
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{c.nom}</p>
              <p className="text-xs text-slate-500">
                {c.total_kg > 0 && `${c.total_kg.toLocaleString('fr-FR')} kg`}
                {c.total_kg > 0 && c.total_t > 0 && ' / '}
                {c.total_t > 0 && `${c.total_t.toLocaleString('fr-FR')} t`}
                {c.total_kg === 0 && c.total_t === 0 && `${c.count} ligne(s)`}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl overflow-x-auto border border-[#E2E8F0] dark:border-[#2B3D1E]">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-7 h-7 text-slate-400 animate-spin"/></div>
        ) : lignes.length === 0 ? (
          <div className="p-10 text-center">
            <Layers size={32} className="mx-auto mb-2 text-slate-200"/>
            <p className="font-semibold text-slate-400 text-sm">Aucun BL CET pour cette période</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E2E8F0] dark:border-[#2B3D1E] text-left bg-slate-50 dark:bg-[#16240D]/50">
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">CET</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Désignation des déchets</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Quantité</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">N° BL</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Date livraison</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((l, idx) => (
                <tr key={idx} className="border-b border-slate-50 dark:border-[#16240D] last:border-0 hover:bg-slate-50 dark:hover:bg-[#16240D]/50">
                  <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-200">{l.cet_nom}</td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-300">{l.description || '—'}</td>
                  <td className="px-4 py-2.5 font-semibold text-slate-700 dark:text-slate-200">
                    {l.quantite ? `${Number(l.quantite).toLocaleString('fr-FR')} ${l.unite || 'KG'}` : '—'}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{l.bl_num}</td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-300">{l.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Rubrique Stock — stock disponible actuel par type de déchets ─────────────
// Indépendant de la période sélectionnée : reflète l'état actuel, tous dossiers confondus.
function RubriqueStock({ rows, loading }) {
  const stockParType = useMemo(() => calculerStock(rows), [rows])

  const exportStockCsv = () => {
    const hdr = ['Type de déchet', 'Code', "N° opération", 'Quantité récupérée', 'Quantité sortie', 'Stock disponible', 'Unité']
    const lignes = []
    stockParType.forEach(t => t.operations.forEach(o =>
      lignes.push([t.designation, t.code, o.numero, o.recupere, o.sortie, o.stock, o.unite])
    ))
    const rowsCsv = lignes.map(v => v.map(x => `"${String(x ?? '').replace(/"/g, '""')}"`).join(';'))
    const csv = [hdr.join(';'), ...rowsCsv].join('\n')
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'stock_actuel.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card p-5 space-y-4 border-l-4 border-teal-400">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Boxes size={18} className="text-teal-600"/> Stock actuel par type de déchets
        </h2>
        <button onClick={exportStockCsv} disabled={stockParType.length===0} className="btn-secondary btn-sm">
          <Download size={13}/> Exporter CSV
        </button>
      </div>
      <p className="text-xs text-slate-500">
        Quantité récupérée non encore valorisée, éliminée ou envoyée au CET — tous dossiers confondus, indépendamment de la période sélectionnée ci-dessous.
      </p>

      <div className="rounded-xl overflow-x-auto border border-[#E2E8F0] dark:border-[#2B3D1E]">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-7 h-7 text-teal-500 animate-spin"/></div>
        ) : stockParType.length === 0 ? (
          <div className="p-10 text-center">
            <Boxes size={32} className="mx-auto mb-2 text-slate-200"/>
            <p className="font-semibold text-slate-400 text-sm">Aucun stock disponible actuellement</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E2E8F0] dark:border-[#2B3D1E] text-left bg-slate-50 dark:bg-[#16240D]/50">
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Type de déchet / N° opération</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Détail</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Stock disponible</th>
              </tr>
            </thead>
            <tbody>
              {stockParType.flatMap(t => [
                <tr key={`t-${t.designation}`} className="border-b border-slate-50 dark:border-[#16240D] bg-slate-50/60 dark:bg-[#16240D]/40">
                  <td className="px-4 py-2.5 font-bold text-slate-800 dark:text-white">
                    <span className="font-mono text-xs text-slate-400 mr-2">{t.code}</span>{t.designation}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 text-xs">{t.operations.length} opération(s)</td>
                  <td className="px-4 py-2.5 font-black text-teal-700 dark:text-teal-400">
                    {t.stock_total.toLocaleString('fr-FR', { maximumFractionDigits: 3 })} {t.unite}
                  </td>
                </tr>,
                ...t.operations.map(o => (
                  <tr key={`${t.designation}-${o.numero}`} className="border-b border-slate-50 dark:border-[#16240D] last:border-0 hover:bg-slate-50 dark:hover:bg-[#16240D]/50">
                    <td className="px-4 py-2 pl-8 font-mono text-xs text-slate-500">{o.numero}</td>
                    <td className="px-4 py-2 text-xs text-slate-500">
                      {o.recupere.toLocaleString('fr-FR')} récupéré − {o.sortie.toLocaleString('fr-FR')} sorti ({o.date})
                    </td>
                    <td className="px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
                      {o.stock.toLocaleString('fr-FR', { maximumFractionDigits: 3 })} {o.unite}
                    </td>
                  </tr>
                )),
              ])}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Rubrique (Spéciaux/SD ou Ménagers et assimilés) ───────────────────────────
function Rubrique({ titre, icon: Icon, accent, rows, loading, fichierCsv, vue }) {
  const totaux = useMemo(() => totauxParUnite(rows), [rows])
  const isGroupee = !!DIMENSIONS_PAR_VUE[vue]
  const groupes = useMemo(() => isGroupee ? aggregerParDimension(rows, vue) : [], [rows, vue, isGroupee])
  const COLONNE_LABELS = { GENERATEUR: 'Générateur', TYPE: 'Type de déchet', DESIGNATION: 'Désignation précise' }

  return (
    <div className={`card p-5 space-y-4 border-l-4 ${accent.border}`}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Icon size={18} className={accent.text}/> {titre}
        </h2>
        <button onClick={() => exportCsv(rows, fichierCsv)} disabled={rows.length===0} className="btn-secondary btn-sm">
          <Download size={13}/> Exporter CSV
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <div className="card p-3 flex items-center gap-3">
          <div className={`w-9 h-9 rounded-xl ${accent.bg} flex items-center justify-center flex-shrink-0`}>
            <Package size={16} className="text-white"/>
          </div>
          <div><p className="text-xl font-black text-slate-900 dark:text-white">{rows.length}</p><p className="text-xs text-slate-500">Dossier(s)</p></div>
        </div>
        {totaux.map(t => (
          <div key={t.label} className="card p-3 flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl ${accent.bg} flex items-center justify-center flex-shrink-0`}>
              <Package size={16} className="text-white"/>
            </div>
            <div>
              <p className="text-xl font-black text-slate-900 dark:text-white">{t.value.toLocaleString('fr-FR')}</p>
              <p className="text-xs text-slate-500">Quantité totale ({t.label})</p>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl overflow-x-auto border border-[#E2E8F0] dark:border-[#2B3D1E]">
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-7 h-7 text-primary-500 animate-spin"/></div>
        ) : rows.length === 0 ? (
          <div className="p-10 text-center">
            <Icon size={32} className="mx-auto mb-2 text-slate-200"/>
            <p className="font-semibold text-slate-400 text-sm">Aucun déchet récupéré pour cette période</p>
          </div>
        ) : isGroupee ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E2E8F0] dark:border-[#2B3D1E] text-left bg-slate-50 dark:bg-[#16240D]/50">
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">{COLONNE_LABELS[vue]}</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Dossier(s)</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Quantité totale</th>
              </tr>
            </thead>
            <tbody>
              {groupes.map(g => (
                <tr key={g.label} className="border-b border-slate-50 dark:border-[#16240D] last:border-0 hover:bg-slate-50 dark:hover:bg-[#16240D]/50">
                  <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-200">{g.label}</td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-300">{g.count}</td>
                  <td className="px-4 py-2.5 font-semibold text-slate-700 dark:text-slate-200">
                    {g.totaux.map(t => `${t.value.toLocaleString('fr-FR')} ${t.label}`).join(', ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E2E8F0] dark:border-[#2B3D1E] text-left bg-slate-50 dark:bg-[#16240D]/50">
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">N° opération</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Désignation déchet récupéré</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Quantité récupérée</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Générateur des déchets</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Date de récupération</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b border-slate-50 dark:border-[#16240D] last:border-0 hover:bg-slate-50 dark:hover:bg-[#16240D]/50">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{r.numero}</td>
                  <td className="px-4 py-2.5">
                    <span className="font-mono text-xs text-slate-400 mr-2">{r.code_dechet}</span>
                    {r.designation_dechet}
                  </td>
                  <td className="px-4 py-2.5 font-semibold text-slate-700 dark:text-slate-200">
                    {r.quantite} {r.unite_display || r.unite}
                  </td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-300">{r.generateur_nom || '—'}</td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-300">{r.date_recuperation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default function StatsPage() {
  const [periode,    setPeriode]    = useState('QUOTIDIENNE')
  const [datePrecise, setDatePrecise] = useState(today())
  const [dateMin,     setDateMin]     = useState(today())
  const [dateMax,     setDateMax]     = useState(today())
  const [mois,        setMois]        = useState(new Date().getMonth() + 1)
  const [annee,       setAnnee]       = useState(thisYear())

  const [rows,       setRows]       = useState([])
  const [loading,    setLoading]    = useState(false)
  const [vue,        setVue]        = useState('TOUS')
  const [blsCet,     setBlsCet]     = useState([])
  const [loadingCet, setLoadingCet] = useState(false)
  const [rowsStock,    setRowsStock]    = useState([])
  const [loadingStock, setLoadingStock] = useState(false)

  const rowsFiltrees = useMemo(() => {
    const destinations = DESTINATIONS_PAR_VUE[vue]
    return destinations ? rows.filter(r => destinations.includes(r.destination_type)) : rows
  }, [rows, vue])

  const rowsSpeciaux = useMemo(() => rowsFiltrees.filter(r => ['S','SD'].includes(r.classe_dechet)), [rowsFiltrees])
  const rowsMenagers = useMemo(() => rowsFiltrees.filter(r => !['S','SD'].includes(r.classe_dechet)), [rowsFiltrees])

  const buildParams = () => {
    const p = { page_size: 500, ordering: '-date_recuperation' }
    if (periode === 'QUOTIDIENNE')      p.date_recuperation = today()
    else if (periode === 'PRECISE')     p.date_recuperation = datePrecise
    else if (periode === 'INTERVALLE') { p.date_min = dateMin; p.date_max = dateMax }
    else if (periode === 'MENSUELLE')  { p.mois = mois; p.annee = annee }
    else if (periode === 'ANNUELLE')    p.annee = annee
    return p
  }

  const buildBlCetParams = () => {
    const p = { destinataire_type: 'CET', page_size: 500 }
    if (periode === 'QUOTIDIENNE')      { p.date_livraison = today() }
    else if (periode === 'PRECISE')     { p.date_livraison = datePrecise }
    else if (periode === 'INTERVALLE')  { p.date_min = dateMin; p.date_max = dateMax }
    else if (periode === 'MENSUELLE') {
      const d = new Date(annee, mois - 1, 1)
      p.date_min = d.toISOString().split('T')[0]
      const last = new Date(annee, mois, 0)
      p.date_max = last.toISOString().split('T')[0]
    }
    else if (periode === 'ANNUELLE') { p.date_min = `${annee}-01-01`; p.date_max = `${annee}-12-31` }
    return p
  }

  const load = async () => {
    setLoading(true)
    try {
      const params = buildParams()
      const res = await api.get('/traceability/', { params })
      const data = res.data.results || res.data
      setRows(data)
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  const loadCet = async () => {
    setLoadingCet(true)
    try {
      const res = await api.get('/bl/', { params: buildBlCetParams() })
      setBlsCet(res.data.results || res.data)
    } catch {
      setBlsCet([])
    } finally {
      setLoadingCet(false)
    }
  }

  const loadStock = async () => {
    setLoadingStock(true)
    try {
      const res = await api.get('/traceability/', { params: { page_size: 2000, ordering: '-date_recuperation' } })
      setRowsStock(res.data.results || res.data)
    } catch {
      setRowsStock([])
    } finally {
      setLoadingStock(false)
    }
  }

  useEffect(() => { load(); loadCet() }, [periode, datePrecise, dateMin, dateMax, mois, annee])
  useEffect(() => { loadStock() }, [])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Package size={24} className="text-primary-600"/> Statistiques des déchets récupérés
        </h1>
        <p className="text-slate-500 text-sm mt-0.5">Quantités récupérées par période</p>
      </div>

      {/* Sélecteur de période */}
      <div className="card p-4 space-y-4">
        <div className="flex gap-1 bg-slate-100 dark:bg-[#16240D] rounded-xl p-1 flex-wrap">
          {PERIODES.map(p => (
            <button key={p.key} onClick={() => setPeriode(p.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
                ${periode===p.key?'bg-white dark:bg-[#2B3D1E] text-primary-700 shadow-sm':'text-slate-500'}`}>
              <p.icon size={13}/> {p.label}
            </button>
          ))}
        </div>

        {periode === 'QUOTIDIENNE' && (
          <p className="text-xs text-slate-500">Affiche les dossiers récupérés aujourd'hui ({today()}).</p>
        )}

        {periode === 'PRECISE' && (
          <div className="max-w-xs">
            <label className="label">Date précise</label>
            <DateInput value={datePrecise} onChange={setDatePrecise}/>
          </div>
        )}

        {periode === 'INTERVALLE' && (
          <div className="grid grid-cols-2 gap-3 max-w-md">
            <div>
              <label className="label">Du</label>
              <DateInput value={dateMin} onChange={setDateMin}/>
            </div>
            <div>
              <label className="label">Au</label>
              <DateInput value={dateMax} onChange={setDateMax}/>
            </div>
          </div>
        )}

        {periode === 'MENSUELLE' && (
          <div className="grid grid-cols-2 gap-3 max-w-md">
            <div>
              <label className="label">Mois</label>
              <select value={mois} onChange={e=>setMois(Number(e.target.value))} className="input">
                {MOIS.map((m,i) => <option key={m} value={i+1}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Année</label>
              <input type="number" value={annee} onChange={e=>setAnnee(Number(e.target.value))} className="input"/>
            </div>
          </div>
        )}

        {periode === 'ANNUELLE' && (
          <div className="max-w-xs">
            <label className="label">Année</label>
            <input type="number" value={annee} onChange={e=>setAnnee(Number(e.target.value))} className="input"/>
          </div>
        )}

        <div className="max-w-sm pt-2 border-t border-[#E2E8F0] dark:border-[#2B3D1E]">
          <label className="label">Vue</label>
          <select value={vue} onChange={e=>setVue(e.target.value)} className="input">
            {VUES.map(v => <option key={v.key} value={v.key}>{v.label}</option>)}
          </select>
        </div>
      </div>

      {vue === 'STOCK_ACTUEL' ? (
        <RubriqueStock rows={rowsStock} loading={loadingStock} />
      ) : (
        <>
          {/* Rubrique 1 — Déchets spéciaux et spéciaux dangereux */}
          <Rubrique
            titre="Déchets spéciaux et spéciaux dangereux (S / SD)"
            icon={AlertTriangle}
            accent={{ border: 'border-red-400', text: 'text-red-600', bg: 'bg-red-500' }}
            rows={rowsSpeciaux}
            loading={loading}
            vue={vue}
            fichierCsv={`statistiques_dechets_speciaux_${periode.toLowerCase()}.csv`}
          />

          {/* Rubrique 2 — Déchets ménagers et assimilés */}
          <Rubrique
            titre="Déchets ménagers et assimilés"
            icon={Home}
            accent={{ border: 'border-emerald-400', text: 'text-emerald-600', bg: 'bg-emerald-500' }}
            rows={rowsMenagers}
            loading={loading}
            vue={vue}
            fichierCsv={`statistiques_dechets_menagers_${periode.toLowerCase()}.csv`}
          />

          {/* Rubrique 3 — Déchets envoyés au CET */}
          <RubriqueCET bls={blsCet} loading={loadingCet} />
        </>
      )}
    </div>
  )
}
