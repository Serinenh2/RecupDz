import { useState, useMemo } from 'react'
import { Search, X, AlertTriangle, Leaf, Info, ChevronDown, ChevronRight } from 'lucide-react'
import { NOMENCLATURE, FAMILLES } from './nomenclatureData'

// ── Class config ──────────────────────────────────────────────────────────────
const CLASSE_CFG = {
  MA: { label:'Ménagers et Assimilés', color:'bg-primary-500',   text:'text-primary-700',   bg:'bg-primary-50',   badge:'badge-blue'   },
  I:  { label:'Inertes',              color:'bg-emerald-500', text:'text-emerald-700',bg:'bg-emerald-50', badge:'badge-green'  },
  S:  { label:'Spéciaux',             color:'bg-amber-500',   text:'text-amber-700',  bg:'bg-amber-50',  badge:'badge-yellow' },
  SD: { label:'Spéciaux Dangereux',   color:'bg-red-500',     text:'text-red-700',    bg:'bg-red-50',    badge:'badge-red'    },
}

// ── Danger badges ─────────────────────────────────────────────────────────────
const DANGER_COLORS = {
  'Explosible':                         'bg-red-100 text-red-800',
  'Inflammable':                        'bg-orange-100 text-orange-800',
  'Facilement inflammable':             'bg-orange-100 text-orange-800',
  'Toxique':                            'bg-purple-100 text-purple-800',
  'Cancérogène':                        'bg-pink-100 text-pink-800',
  'Mutagène':                           'bg-pink-100 text-pink-800',
  'Corrosive':                          'bg-yellow-100 text-yellow-800',
  'Irritante':                          'bg-yellow-100 text-yellow-800',
  'Nocive':                             'bg-amber-100 text-amber-800',
  'Infectieuse':                        'bg-red-100 text-red-800',
  'Comburante':                         'bg-primary-100 text-primary-800',
  "Dangereuse pour l'environnement":    'bg-green-100 text-green-800',
  'Toxique vis-à-vis de la reproduction':'bg-purple-100 text-purple-800',
}

function DangerBadge({ label }) {
  const cls = DANGER_COLORS[label] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold mr-1 mb-1 ${cls}`}>
      {label}
    </span>
  )
}

function parseDanger(str) {
  if (!str || str === 'nan') return []
  return str.split(/[,;\n]/).map(s => s.trim()).filter(Boolean)
}

// ── Detail modal ──────────────────────────────────────────────────────────────
function DetailModal({ item, onClose }) {
  if (!item) return null
  const dangers = parseDanger(item.danger_fr)
  const cfg     = CLASSE_CFG[item.classe] || CLASSE_CFG.I
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden">
        <div className={`px-6 py-4 flex items-start justify-between ${cfg.bg} border-b border-gray-100`}>
          <div>
            <span className="font-mono text-lg font-black text-gray-900">{item.code}</span>
            <div className="flex items-center gap-2 mt-1">
              <span className={`badge ${cfg.badge}`}>{item.classe} — {cfg.label}</span>
              {item.annexe && <span className="text-xs text-gray-400">Annexe {item.annexe}</span>}
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 p-1">
            <X size={18} />
          </button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1">Désignation</p>
            <p className="text-sm text-gray-900 leading-relaxed">{item.nom_fr}</p>
          </div>
          <div>
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-1">Famille</p>
            <p className="text-sm text-gray-700">
              <span className="font-semibold">{item.famille} — </span>
              {FAMILLES[item.famille] || '—'}
            </p>
          </div>
          {dangers.length > 0 && (
            <div>
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                <AlertTriangle size={12} className="text-red-500" /> Critères de dangerosité
              </p>
              <div className="flex flex-wrap">
                {dangers.map((d, i) => <DangerBadge key={i} label={d} />)}
              </div>
            </div>
          )}
          {!dangers.length && (
            <div className="flex items-center gap-2 text-sm text-emerald-600 bg-emerald-50 rounded-xl px-3 py-2">
              <Leaf size={14} /> Déchet non dangereux
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Rubrique section ──────────────────────────────────────────────────────────
function Rubrique({ title, subtitle, icon: Icon, iconBg, items, showDanger, onSelect, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="card overflow-hidden">
      <button type="button" onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-gray-50 transition-colors text-left">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${iconBg}`}>
          <Icon size={20} className="text-white" />
        </div>
        <div className="flex-1">
          <p className="font-bold text-slate-900">{title}</p>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="bg-gray-100 text-gray-600 text-xs font-bold px-3 py-1 rounded-full">
            {items.length}
          </span>
          {open ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
        </div>
      </button>

      {open && (
        <div className="overflow-x-auto border-t border-gray-100">
          {items.length === 0 ? (
            <p className="text-center py-8 text-slate-400 text-sm">Aucun résultat</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide w-24">Code</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Désignation (Français)</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide w-16">Classe</th>
                  {showDanger && (
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      <span className="flex items-center gap-1"><AlertTriangle size={11} className="text-red-400" /> Dangerosité</span>
                    </th>
                  )}
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide w-20">Annexe</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => {
                  const cfg     = CLASSE_CFG[item.classe] || CLASSE_CFG.I
                  const dangers = parseDanger(item.danger_fr)
                  return (
                    <tr key={item.code}
                      onClick={() => onSelect(item)}
                      className="border-b border-gray-50 last:border-0 hover:bg-primary-50/40 cursor-pointer transition-colors">
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs font-bold text-primary-700 bg-primary-50 px-2 py-1 rounded">
                          {item.code}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-800 max-w-md">
                        <p className="leading-snug">{item.nom_fr}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`badge ${cfg.badge}`}>{item.classe}</span>
                      </td>
                      {showDanger && (
                        <td className="px-4 py-3 max-w-xs">
                          {dangers.length > 0
                            ? <div className="flex flex-wrap">{dangers.map((d,i) => <DangerBadge key={i} label={d} />)}</div>
                            : <span className="text-xs text-gray-300">—</span>
                          }
                        </td>
                      )}
                      <td className="px-4 py-3 text-xs text-gray-400">{item.annexe || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function NomenclaturePage() {
  const [search,       setSearch]       = useState('')
  const [classeFilter, setClasseFilter] = useState('')
  const [familleFilter,setFamilleFilter]= useState('')
  const [selected,     setSelected]     = useState(null)

  const filtered = useMemo(() => {
    return NOMENCLATURE.filter(item => {
      const matchSearch = !search ||
        item.code.toLowerCase().includes(search.toLowerCase()) ||
        item.nom_fr.toLowerCase().includes(search.toLowerCase()) ||
        (item.danger_fr || '').toLowerCase().includes(search.toLowerCase())
      const matchClasse  = !classeFilter  || item.classe  === classeFilter
      const matchFamille = !familleFilter || item.famille === familleFilter
      return matchSearch && matchClasse && matchFamille
    })
  }, [search, classeFilter, familleFilter])

  const rubrique1 = filtered.filter(i => i.classe === 'MA' || i.classe === 'I')
  const rubrique2 = filtered.filter(i => i.classe === 'S'  || i.classe === 'SD')

  // Unique familles
  const uniqueFamilles = [...new Set(NOMENCLATURE.map(n => n.famille))].sort((a,b) => Number(a)-Number(b))

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Nomenclature des Déchets</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Décret exécutif n° 06-104 du 28 février 2006 — {NOMENCLATURE.length} codes répertoriés
        </p>
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-56">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher par code, désignation ou dangerosité..."
            className="input pl-9 text-sm" />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <X size={14} />
            </button>
          )}
        </div>
        <select value={classeFilter} onChange={e => setClasseFilter(e.target.value)} className="input w-44 text-sm">
          <option value="">Toutes les classes</option>
          {Object.entries(CLASSE_CFG).map(([k,v]) => <option key={k} value={k}>{k} — {v.label}</option>)}
        </select>
        <select value={familleFilter} onChange={e => setFamilleFilter(e.target.value)} className="input w-64 text-sm">
          <option value="">Toutes les familles</option>
          {uniqueFamilles.map(f => <option key={f} value={f}>{f} — {FAMILLES[f] || `Famille ${f}`}</option>)}
        </select>
        {/* Stats chips */}
        <div className="flex gap-2 ml-auto flex-wrap">
          {Object.entries(CLASSE_CFG).map(([k,v]) => {
            const count = NOMENCLATURE.filter(n => n.classe === k).length
            return (
              <button key={k} onClick={() => setClasseFilter(classeFilter === k ? '' : k)}
                className={`px-3 py-1 rounded-full text-xs font-bold transition-all border
                  ${classeFilter === k
                    ? `${v.color} text-white border-transparent`
                    : `${v.bg} ${v.text} border-gray-200 hover:border-gray-300`}`}>
                {k} : {count}
              </button>
            )
          })}
        </div>
      </div>

      {/* Rubrique 1 */}
      <Rubrique
        title="Rubrique 1 — Déchets Ménagers & Assimilés / Inertes"
        subtitle="Classes MA (Ménagers et Assimilés) et I (Inertes) — déchets non dangereux"
        icon={Leaf}
        iconBg="bg-primary-500"
        items={rubrique1}
        showDanger={false}
        onSelect={setSelected}
        defaultOpen={true}
      />

      {/* Rubrique 2 */}
      <Rubrique
        title="Rubrique 2 — Déchets Spéciaux & Spéciaux Dangereux"
        subtitle="Classes S (Spéciaux) et SD (Spéciaux Dangereux) — gestion spécifique requise"
        icon={AlertTriangle}
        iconBg="bg-red-500"
        items={rubrique2}
        showDanger={true}
        onSelect={setSelected}
        defaultOpen={true}
      />

      {/* Legend */}
      <div className="card p-5">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1">
          <Info size={13} /> Légende des classes
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(CLASSE_CFG).map(([code, cfg]) => (
            <div key={code} className={`rounded-xl p-4 ${cfg.bg} border border-gray-100`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-7 h-7 ${cfg.color} rounded-lg flex items-center justify-center text-white text-xs font-black flex-shrink-0`}>
                  {code}
                </span>
                <p className={`text-xs font-semibold ${cfg.text} leading-tight`}>{cfg.label}</p>
              </div>
              <p className="text-[10px] text-gray-500">
                {code === 'MA' && 'Ordures ménagères et déchets assimilés'}
                {code === 'I'  && 'Déchets sans transformation physique ou chimique'}
                {code === 'S'  && 'Déchets des activités industrielles et commerciales'}
                {code === 'SD' && 'Déchets présentant des propriétés de danger'}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Detail modal */}
      {selected && <DetailModal item={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

