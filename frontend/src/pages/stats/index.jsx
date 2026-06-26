import { useEffect, useState, useMemo } from 'react'
import { Calendar, CalendarRange, CalendarDays, CalendarClock, Package, Download, Loader2, AlertTriangle, Home } from 'lucide-react'
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
  { key: 'GENERATEUR',   label: 'Par générateur' },
  { key: 'TYPE',         label: 'Par type de déchets' },
  { key: 'DESIGNATION',  label: 'Par désignation précise des déchets' },
  { key: 'STOCKAGE',     label: 'Déchets en stock' },
  { key: 'VALORISATION', label: 'Déchets valorisés' },
  { key: 'ELIMINATION',  label: 'Déchets éliminés' },
]

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
  const header = ['Désignation déchet','Quantité récupérée','Unité','Générateur des déchets','Date de récupération']
  const lines = rows.map(r => [
    r.designation_dechet, r.quantite, r.unite_display || r.unite, r.generateur_nom || '', r.date_recuperation,
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

      <div className="rounded-xl overflow-x-auto border border-[#E2E8F0] dark:border-[#334155]">
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
              <tr className="border-b border-[#E2E8F0] dark:border-[#334155] text-left bg-slate-50 dark:bg-slate-800/50">
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">{COLONNE_LABELS[vue]}</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Dossier(s)</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Quantité totale</th>
              </tr>
            </thead>
            <tbody>
              {groupes.map(g => (
                <tr key={g.label} className="border-b border-slate-50 dark:border-slate-800 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/50">
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
              <tr className="border-b border-[#E2E8F0] dark:border-[#334155] text-left bg-slate-50 dark:bg-slate-800/50">
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Désignation déchet récupéré</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Quantité récupérée</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Générateur des déchets</th>
                <th className="px-4 py-2.5 font-semibold text-slate-500 text-xs uppercase">Date de récupération</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} className="border-b border-slate-50 dark:border-slate-800 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/50">
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

  const [rows,    setRows]    = useState([])
  const [loading, setLoading] = useState(false)
  const [vue,     setVue]     = useState('TOUS')

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

  useEffect(() => { load() }, [periode, datePrecise, dateMin, dateMax, mois, annee])

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
        <div className="flex gap-1 bg-slate-100 dark:bg-slate-800 rounded-xl p-1 flex-wrap">
          {PERIODES.map(p => (
            <button key={p.key} onClick={() => setPeriode(p.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
                ${periode===p.key?'bg-white dark:bg-slate-700 text-primary-700 shadow-sm':'text-slate-500'}`}>
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

        <div className="max-w-sm pt-2 border-t border-[#E2E8F0] dark:border-[#334155]">
          <label className="label">Vue</label>
          <select value={vue} onChange={e=>setVue(e.target.value)} className="input">
            {VUES.map(v => <option key={v.key} value={v.key}>{v.label}</option>)}
          </select>
        </div>
      </div>

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
    </div>
  )
}
