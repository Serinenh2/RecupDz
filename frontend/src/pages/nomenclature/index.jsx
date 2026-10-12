import { useState, useMemo, useEffect } from 'react'
import { Search, X, Package, AlertTriangle, Leaf, Info, ChevronDown, ChevronRight, BookOpen, Plus, Edit, Trash2 } from 'lucide-react'
import { NOMENCLATURE, FAMILLES } from './nomenclatureData'
import api from '../../api'
import toast from 'react-hot-toast'
import { Can } from '../../components/guards'

const COND_BADGE = {
  Kilogramme: 'badge-blue',
  Unité:      'badge-green',
}

// ── Class config (codes déchets réglementaires) ────────────────────────────────
const CLASSE_CFG = {
  MA: { label:'Ménagers et Assimilés', color:'bg-primary-500',   text:'text-primary-700',   bg:'bg-primary-50',   badge:'badge-blue'   },
  I:  { label:'Inertes',              color:'bg-emerald-500', text:'text-emerald-700',bg:'bg-emerald-50', badge:'badge-green'  },
  S:  { label:'Spéciaux',             color:'bg-amber-500',   text:'text-amber-700',  bg:'bg-amber-50',  badge:'badge-yellow' },
  SD: { label:'Spéciaux Dangereux',   color:'bg-red-500',     text:'text-red-700',    bg:'bg-red-50',    badge:'badge-red'    },
}

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

// ── Rubrique section ────────────────────────────────────────────────────────────
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

// ── Modal wrapper ────────────────────────────────────────────────────────────
function ArticleModal({ open, onClose, title, children }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#16240D] rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] dark:border-[#2B3D1E] flex-shrink-0">
          <h3 className="font-bold text-slate-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 p-1"><X size={18} /></button>
        </div>
        <div className="p-6 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}

// ── Code déchet officiel picker (recherche dans les 193 codes du backend) ────
function CodeOfficielPicker({ value, onChange }) {
  const [all, setAll] = useState([])
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)

  useEffect(() => { api.get('/nomenclature/').then(r => setAll(r.data.results || r.data)).catch(() => {}) }, [])

  const filtered = useMemo(() => {
    if (!search) return []
    const q = search.toLowerCase()
    return all.filter(n => n.code.toLowerCase().includes(q) || n.designation_fr.toLowerCase().includes(q)).slice(0, 30)
  }, [search, all])

  return (
    <div className="relative">
      <input
        value={search}
        onChange={e => { setSearch(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder={value ? `${value.code} — ${value.designation_fr}` : 'Rechercher un code déchet officiel (optionnel)...'}
        className="input"
      />
      {value && !search && (
        <button type="button" onClick={() => onChange(null)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-red-500">
          <X size={14} />
        </button>
      )}
      {open && search && (
        <div className="absolute z-30 top-full left-0 right-0 mt-1 bg-white dark:bg-[#16240D] border border-[#E2E8F0] rounded-xl shadow-xl max-h-52 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="text-center py-4 text-slate-400 text-xs">Aucun résultat</p>
          ) : filtered.map(n => (
            <button key={n.id} type="button" onClick={() => { onChange(n); setSearch(''); setOpen(false) }}
              className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-slate-50 dark:hover:bg-[#16240D] text-xs">
              <span className="font-mono font-bold text-primary-700 flex-shrink-0 w-16">{n.code}</span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold flex-shrink-0 ${CLASSE_CFG[n.classe]?.badge || 'badge-gray'}`}>{n.classe}</span>
              <span className="text-slate-600 dark:text-slate-300 truncate">{n.designation_fr}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Formulaire d'ajout / modification d'un article ───────────────────────────
function ArticleForm({ item, onSave, onClose }) {
  const isEdit = !!item?.id
  const [designation, setDesignation]         = useState(item?.designation || '')
  const [reference, setReference]             = useState(item?.reference || '')
  const [conditionnement, setConditionnement] = useState(item?.conditionnement || 'Kilogramme')
  const [codeObj, setCodeObj]                 = useState(
    item?.code_dechet ? { id: item.nomenclature, code: item.code_dechet, designation_fr: item.designation } : null
  )
  const [saving, setSaving] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!designation.trim()) { toast.error('La désignation est requise'); return }
    setSaving(true)
    try {
      const payload = { designation, reference, conditionnement, nomenclature: codeObj?.id || null }
      if (isEdit) await api.patch(`/nomenclature/catalogue-entreprise/${item.id}/`, payload)
      else        await api.post('/nomenclature/catalogue-entreprise/', payload)
      toast.success(isEdit ? 'Article mis à jour' : 'Article ajouté à Mon catalogue')
      onSave()
    } catch {
      toast.error('Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <label className="label">Désignation <span className="text-red-500">*</span></label>
        <input value={designation} onChange={e => setDesignation(e.target.value)} className="input"
          placeholder="ex: Palette de PEHD" autoFocus />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Référence</label>
          <input value={reference} onChange={e => setReference(e.target.value)} className="input" placeholder="ex: COMPALPEHD" />
        </div>
        <div>
          <label className="label">Conditionnement</label>
          <select value={conditionnement} onChange={e => setConditionnement(e.target.value)} className="input">
            <option value="Kilogramme">Kilogramme</option>
            <option value="Unité">Unité</option>
          </select>
        </div>
      </div>
      <div>
        <label className="label">Code déchet officiel</label>
        <CodeOfficielPicker value={codeObj} onChange={setCodeObj} />
      </div>
      <div className="flex gap-3 pt-2 border-t border-[#E2E8F0] dark:border-[#2B3D1E]">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? 'Enregistrement...' : isEdit ? 'Mettre à jour' : "Ajouter l'article"}
        </button>
        <button type="button" onClick={onClose} className="btn-secondary">Annuler</button>
      </div>
    </form>
  )
}

// ── Tab: Catalogue de l'entreprise ──────────────────────────────────────────────
function CatalogueEntreprise() {
  const [items,    setItems]    = useState([])
  const [loading,  setLoading]  = useState(true)
  const [search,   setSearch]   = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing,  setEditing]  = useState(null)

  const load = () => {
    setLoading(true)
    api.get('/nomenclature/catalogue-entreprise/')
      .then(r => setItems(r.data.results || r.data))
      .catch(() => toast.error('Erreur chargement du catalogue'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const handleDelete = async (id) => {
    if (!window.confirm('Supprimer cet article du catalogue ?')) return
    try { await api.delete(`/nomenclature/catalogue-entreprise/${id}/`); toast.success('Article supprimé'); load() }
    catch { toast.error('Erreur suppression') }
  }

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return items.filter(item =>
      !q ||
      item.designation.toLowerCase().includes(q) ||
      (item.reference || '').toLowerCase().includes(q) ||
      (item.code_dechet || '').toLowerCase().includes(q)
    )
  }, [items, search])

  return (
    <div className="space-y-5">
      <div className="card p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-56">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher par désignation, référence ou code déchet..."
            className="input pl-9 text-sm" />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <X size={14} />
            </button>
          )}
        </div>
        <Can do="nomenclature.add_catalogueentreprise">
          <button onClick={() => { setEditing(null); setShowForm(true) }} className="btn-primary btn-sm">
            <Plus size={14} /> Ajouter une désignation déchets
          </button>
        </Can>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <p className="text-center py-10 text-slate-400 text-sm">Chargement...</p>
          ) : filtered.length === 0 ? (
            <p className="text-center py-10 text-slate-400 text-sm">Aucun résultat</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 dark:bg-[#2B3D1E] border-b border-gray-200 dark:border-[#2B3D1E]">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Désignation</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Référence</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide w-40">Code déchet</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide w-40">Conditionnement</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide w-20">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(item => (
                  <tr key={item.id} className="border-b border-gray-50 dark:border-[#2B3D1E] last:border-0 hover:bg-primary-50/40 dark:hover:bg-[#2B3D1E]/40 transition-colors">
                    <td className="px-4 py-3 flex items-center gap-2 text-slate-800 dark:text-slate-100">
                      <Package size={14} className="text-primary-500 flex-shrink-0" />
                      {item.designation}
                    </td>
                    <td className="px-4 py-3">
                      {item.reference && (
                        <span className="font-mono text-xs font-bold text-primary-700 bg-primary-50 px-2 py-1 rounded">
                          {item.reference}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {item.code_dechet ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="font-mono text-xs font-bold text-slate-700 bg-slate-100 px-2 py-1 rounded">
                            {item.code_dechet}
                          </span>
                          <span className={`badge ${CLASSE_CFG[item.classe]?.badge || 'badge-gray'} text-[10px]`}>
                            {item.classe}
                          </span>
                        </span>
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {item.conditionnement && (
                        <span className={`badge ${COND_BADGE[item.conditionnement] || 'badge-gray'}`}>
                          {item.conditionnement}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <Can do="nomenclature.change_catalogueentreprise">
                        <button onClick={() => { setEditing(item); setShowForm(true) }}
                          className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600"><Edit size={13} /></button>
                      </Can>
                      <Can do="nomenclature.delete_catalogueentreprise">
                        <button onClick={() => handleDelete(item.id)}
                          className="btn-ghost p-1.5 text-slate-400 hover:text-red-600"><Trash2 size={13} /></button>
                      </Can>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <ArticleModal open={showForm} onClose={() => { setShowForm(false); setEditing(null) }}
        title={editing ? "Modifier l'article" : 'Ajouter une désignation déchets'}>
        <ArticleForm item={editing}
          onSave={() => { setShowForm(false); setEditing(null); load() }}
          onClose={() => { setShowForm(false); setEditing(null) }} />
      </ArticleModal>
    </div>
  )
}

// ── Tab: Codes déchets réglementaires (Décret 06-104) ──────────────────────────
function CodesDechets() {
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

  const uniqueFamilles = [...new Set(NOMENCLATURE.map(n => n.famille))].sort((a,b) => Number(a)-Number(b))

  return (
    <div className="space-y-5">
      <p className="text-slate-500 text-sm">
        Décret exécutif n° 06-104 du 28 février 2006 — {NOMENCLATURE.length} codes répertoriés
      </p>

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

      {selected && <DetailModal item={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function NomenclaturePage() {
  const [tab, setTab] = useState('entreprise')

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Nomenclature</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Catalogue de l'entreprise et codes déchets réglementaires
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 flex-wrap">
        <button onClick={() => setTab('entreprise')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all border-2
            ${tab==='entreprise'
              ? 'bg-primary-600 text-white border-primary-600 shadow-sm'
              : 'border-[#E2E8F0] text-slate-600 hover:border-primary-300 bg-white dark:bg-[#16240D] dark:border-[#2B3D1E]'}`}>
          <Package size={15}/> Mon catalogue
        </button>
        <button onClick={() => setTab('codes')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all border-2
            ${tab==='codes'
              ? 'bg-primary-600 text-white border-primary-600 shadow-sm'
              : 'border-[#E2E8F0] text-slate-600 hover:border-primary-300 bg-white dark:bg-[#16240D] dark:border-[#2B3D1E]'}`}>
          <BookOpen size={15}/> Codes déchets ({NOMENCLATURE.length})
        </button>
      </div>

      {tab === 'entreprise' ? <CatalogueEntreprise /> : <CodesDechets />}
    </div>
  )
}
