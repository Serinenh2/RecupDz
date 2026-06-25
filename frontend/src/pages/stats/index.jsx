import { useEffect, useState, useMemo } from 'react'
import { Calendar, CalendarRange, CalendarDays, CalendarClock, Package, Download, Loader2 } from 'lucide-react'
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

export default function StatsPage() {
  const [periode,    setPeriode]    = useState('QUOTIDIENNE')
  const [datePrecise, setDatePrecise] = useState(today())
  const [dateMin,     setDateMin]     = useState(today())
  const [dateMax,     setDateMax]     = useState(today())
  const [mois,        setMois]        = useState(new Date().getMonth() + 1)
  const [annee,       setAnnee]       = useState(thisYear())

  const [rows,    setRows]    = useState([])
  const [loading, setLoading] = useState(false)

  const totauxParUnite = useMemo(() => {
    const m = new Map()
    rows.forEach(r => {
      const key = r.unite || 'KG'
      const label = UNITE_LABELS[key] || r.unite_display || key
      const prev = m.get(key)?.value || 0
      m.set(key, { label, value: prev + Number(r.quantite || 0) })
    })
    return Array.from(m.values())
  }, [rows])

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

  const exportCsv = () => {
    const header = ['Désignation déchet','Quantité récupérée','Unité','Générateur des déchets','Date de récupération']
    const lines = rows.map(r => [
      r.designation_dechet, r.quantite, r.unite_display || r.unite, r.generateur_nom || '', r.date_recuperation,
    ].map(v => `"${String(v ?? '').replace(/"/g,'""')}"`).join(';'))
    const csv = [header.join(';'), ...lines].join('\n')
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `statistiques_dechets_${periode.toLowerCase()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Package size={24} className="text-primary-600"/> Statistiques des déchets récupérés
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Quantités récupérées par période</p>
        </div>
        <button onClick={exportCsv} disabled={rows.length===0} className="btn-secondary">
          <Download size={15}/> Exporter CSV
        </button>
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
      </div>

      {/* Résumé */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <div className="card p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-500 flex items-center justify-center flex-shrink-0">
            <Package size={18} className="text-white"/>
          </div>
          <div><p className="text-2xl font-black text-slate-900 dark:text-white">{rows.length}</p><p className="text-xs text-slate-500">Dossier(s)</p></div>
        </div>
        {totauxParUnite.map(t => (
          <div key={t.label} className="card p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500 flex items-center justify-center flex-shrink-0">
              <Package size={18} className="text-white"/>
            </div>
            <div>
              <p className="text-2xl font-black text-slate-900 dark:text-white">
                {t.value.toLocaleString('fr-FR')}
              </p>
              <p className="text-xs text-slate-500">Quantité totale ({t.label})</p>
            </div>
          </div>
        ))}
      </div>

      {/* Tableau */}
      <div className="card overflow-x-auto">
        {loading ? (
          <div className="flex justify-center py-16"><Loader2 className="w-8 h-8 text-primary-500 animate-spin"/></div>
        ) : rows.length === 0 ? (
          <div className="p-16 text-center">
            <Package size={40} className="mx-auto mb-3 text-slate-200"/>
            <p className="font-semibold text-slate-400">Aucun déchet récupéré pour cette période</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E2E8F0] dark:border-[#334155] text-left">
                <th className="px-4 py-3 font-semibold text-slate-500 text-xs uppercase">Désignation déchet récupéré</th>
                <th className="px-4 py-3 font-semibold text-slate-500 text-xs uppercase">Quantité récupérée</th>
                <th className="px-4 py-3 font-semibold text-slate-500 text-xs uppercase">Générateur des déchets</th>
                <th className="px-4 py-3 font-semibold text-slate-500 text-xs uppercase">Date de récupération</th>
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
