import { useEffect, useState, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import {
  Users, Plus, Search, X, Save, Edit, Trash2,
  Building2, Truck, Flame, Recycle, MapPin,
  Phone, Mail, Award, Shield, AlertTriangle,
  CheckCircle2, ChevronDown, ChevronRight, Eye,
  Factory, Landmark, TreePine, FileSignature
} from 'lucide-react'
import api from '../../api'
import { WILAYAS, getCommunesByWilaya } from '../../utils/algeria_geo'
import { NOMENCLATURE } from '../nomenclature/nomenclatureData'
import DateInput from '../../components/common/DateInput'
import { formatDateFR } from '../../utils/formatDate'
import toast from 'react-hot-toast'

// ── API ───────────────────────────────────────────────────────────────────────
const opAPI = {
  getAll:  (p)    => api.get('/operateurs/', { params: p }),
  get:     (id)   => api.get(`/operateurs/${id}/`),
  create:  (d)    => api.post('/operateurs/', d),
  update:  (id,d) => api.patch(`/operateurs/${id}/`, d),
  delete:  (id)   => api.delete(`/operateurs/${id}/`),
  verifier:(d)    => api.post('/operateurs/verifier_compatibilite/', d),
}

// ── Type config ───────────────────────────────────────────────────────────────
export const TYPE_CFG = {
  GENERATEUR:   { label: 'Générateur de déchets',               icon: Factory,    color: 'bg-emerald-500',  light: 'bg-emerald-50 text-emerald-700 border-emerald-200',  badge: 'bg-emerald-100 text-emerald-800' },
  TRANSPORTEUR: { label: 'Transporteur de déchets',             icon: Truck,      color: 'bg-amber-500',    light: 'bg-amber-50 text-amber-700 border-amber-200',        badge: 'bg-amber-100 text-amber-800'    },
  ELIMINATEUR:  { label: 'Éliminateur de déchets',              icon: Flame,      color: 'bg-red-500',      light: 'bg-red-50 text-red-700 border-red-200',              badge: 'bg-red-100 text-red-800'        },
  VALORISATEUR: { label: 'Valorisateur de déchets',             icon: Recycle,    color: 'bg-teal-500',     light: 'bg-teal-50 text-teal-700 border-teal-200',           badge: 'bg-teal-100 text-teal-800'      },
  CET:          { label: "Centre d'Enfouissement Technique",     icon: TreePine,   color: 'bg-slate-500',    light: 'bg-slate-50 text-slate-700 border-slate-200',        badge: 'bg-slate-100 text-slate-700'    },
  DIR_WILAYA:   { label: "Direction de l'Environnement Wilaya",  icon: Building2,  color: 'bg-primary-500',     light: 'bg-primary-50 text-primary-700 border-primary-200',           badge: 'bg-primary-100 text-primary-800'      },
  MINISTERE:    { label: "Ministère de l'Environnement",         icon: Landmark,   color: 'bg-violet-500',   light: 'bg-violet-50 text-violet-700 border-violet-200',     badge: 'bg-violet-100 text-violet-800'  },
}

// Types needing agrément
const TYPES_AGREMENT = ['GENERATEUR', 'TRANSPORTEUR', 'ELIMINATEUR']

// Defined once at module scope (not inside the form component) so its identity
// stays stable across re-renders — otherwise React remounts the wrapped <input>
// on every keystroke (this form re-renders on every watch()'d change), which
// makes text fields lose focus after each character typed.
function F({ label, req, children, full }) {
  return (
    <div className={full ? 'col-span-2' : ''}>
      <label className="label">{label}{req && <span className="text-red-500 ml-0.5">*</span>}</label>
      {children}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// ── Modal wrapper ─────────────────────────────────────────────────────────────
function Modal({ open, onClose, title, size = 'max-w-3xl', children }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className={`bg-white dark:bg-[#16240D] rounded-2xl shadow-2xl w-full ${size} max-h-[90vh] flex flex-col`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] dark:border-[#2B3D1E] flex-shrink-0">
          <h3 className="font-bold text-slate-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 p-1"><X size={18} /></button>
        </div>
        <div className="p-6 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}

// ── Code picker ───────────────────────────────────────────────────────────────
function CodesPicker({ value, onChange }) {
  const [search, setSearch] = useState('')
  const [open,   setOpen]   = useState(false)
  const selected = value ? value.split(',').map(s => s.trim()).filter(Boolean) : []

  const filtered = useMemo(() =>
    NOMENCLATURE.filter(n =>
      n.code.includes(search) || n.nom_fr.toLowerCase().includes(search.toLowerCase())
    ).slice(0, 40)
  , [search])

  const toggle = (code) => {
    const next = selected.includes(code)
      ? selected.filter(c => c !== code)
      : [...selected, code]
    onChange(next.join(', '))
  }

  return (
    <div>
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {selected.map(c => {
            const n = NOMENCLATURE.find(x => x.code === c)
            return (
              <span key={c} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs
                bg-primary-50 text-primary-700 border border-primary-200 font-mono font-bold">
                {c}
                <button type="button" onClick={() => toggle(c)} className="text-primary-400 hover:text-red-500 ml-0.5">
                  <X size={9} />
                </button>
              </span>
            )
          })}
        </div>
      )}
      <button type="button" onClick={() => setOpen(!open)}
        className="btn-secondary btn-sm w-full justify-between">
        <span className="flex items-center gap-1.5"><Plus size={12} /> Ajouter des codes déchets autorisés</span>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <div className="mt-1 border border-[#E2E8F0] rounded-xl overflow-hidden">
          <div className="p-2 border-b border-[#E2E8F0]">
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Rechercher..." className="input text-xs" autoFocus />
          </div>
          <div className="max-h-48 overflow-y-auto">
            {filtered.map(n => (
              <button key={n.code} type="button" onClick={() => toggle(n.code)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-left text-xs hover:bg-slate-50 ${selected.includes(n.code) ? 'bg-primary-50' : ''}`}>
                <div className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center ${selected.includes(n.code) ? 'bg-primary-600 border-primary-600' : 'border-slate-300'}`}>
                  {selected.includes(n.code) && <CheckCircle2 size={9} className="text-white" />}
                </div>
                <span className="font-mono font-bold text-primary-700">{n.code}</span>
                <span className={`px-1 rounded text-[9px] font-bold ${n.classe === 'SD' ? 'bg-red-100 text-red-700' : n.classe === 'S' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>{n.classe}</span>
                <span className="text-slate-500 truncate">{n.nom_fr.slice(0, 45)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Operateur Form ────────────────────────────────────────────────────────────
function OperateurForm({ operateur, onSave, onClose }) {
  const isEdit = !!operateur?.id
  const { register, handleSubmit, watch, setValue, reset } = useForm({
    defaultValues: operateur || { type_operateur: 'GENERATEUR', statut: 'ACTIF' }
  })
  const [saving,       setSaving]       = useState(false)
  const [codesValue,   setCodesValue]   = useState(operateur?.codes_dechets_autorises || '')
  const [communes,     setCommunes]     = useState([])

  const type    = watch('type_operateur')
  const wilaya  = watch('wilaya')
  const duree   = watch('duree_agrement')
  const dDebut  = watch('date_debut_agrement')

  const needsAgrement = TYPES_AGREMENT.includes(type)
  const isTransporteur= type === 'TRANSPORTEUR'

  useEffect(() => {
    if (wilaya) setCommunes(getCommunesByWilaya(wilaya))
    else        setCommunes([])
  }, [wilaya])

  useEffect(() => {
    if (dDebut && duree) {
      const d = new Date(dDebut)
      d.setFullYear(d.getFullYear() + parseInt(duree))
      setValue('date_fin_agrement', d.toISOString().split('T')[0])
    }
  }, [dDebut, duree])

  useEffect(() => {
    if (operateur) {
      reset(operateur)
      setCodesValue(operateur.codes_dechets_autorises || '')
      if (operateur.wilaya) setCommunes(getCommunesByWilaya(operateur.wilaya))
    }
  }, [operateur])

  const onSubmit = async (data) => {
  setSaving(true)

  // Nettoyer les champs vides
  if (!data.date_agrement)       delete data.date_agrement
  if (!data.date_debut_agrement) delete data.date_debut_agrement
  if (!data.date_fin_agrement)   delete data.date_fin_agrement
  if (!data.duree_agrement)      delete data.duree_agrement
  if (!data.convention_date)     delete data.convention_date
  if (!data.convention_duree)    delete data.convention_duree

  data.codes_dechets_autorises = codesValue

  try {
    if (isEdit) {
      await opAPI.update(operateur.id, data)
      toast.success('Opérateur mis à jour')
    } else {
      await opAPI.create(data)
      toast.success('Opérateur créé')
    }
    onSave()
  } catch (e) {
    console.error('Erreur:', e.response?.data)
    toast.error('Erreur sauvegarde')
  }
  finally { setSaving(false) }
}

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

      {/* Type selector */}
      <div>
        <label className="label">Type d'opérateur <span className="text-red-500">*</span></label>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {Object.entries(TYPE_CFG).map(([k, v]) => {
            const Icon = v.icon
            return (
              <label key={k} className={`flex items-center gap-2 p-3 rounded-xl border-2 cursor-pointer transition-all
                ${type === k ? `border-current ${v.light}` : 'border-[#E2E8F0] hover:border-slate-300'}`}>
                <input type="radio" {...register('type_operateur')} value={k} className="sr-only" />
                <Icon size={16} className={type === k ? '' : 'text-slate-400'} />
                <span className="text-xs font-semibold leading-tight">{v.label}</span>
              </label>
            )
          })}
        </div>
      </div>

      {/* Identification */}
      <div className="card p-4 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Identification</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <F label="Raison sociale" req full>
            <input {...register('raison_sociale', { required: true })} className="input" placeholder="Nom de l'entreprise..." />
          </F>
          <F label="NIN"><input {...register('nin')} className="input" placeholder="N° Identification Nationale" /></F>
          <F label="NIF"><input {...register('nif')} className="input" placeholder="N° Identification Fiscale" /></F>
          <F label="NIS"><input {...register('nis')} className="input" placeholder="N° Identification Statistique" /></F>
          <F label="Registre de Commerce (RC)">
            <input {...register('registre_commerce')} className="input" placeholder="RC/16/B/..." />
          </F>
          {type === 'GENERATEUR' && (
            <F label="Secteur d'activité">
              <input {...register('secteur_activite')} className="input" placeholder="Industrie, Santé, Agriculture..." />
            </F>
          )}
        </div>
      </div>

      {/* Agrément — only for types needing it */}
      {needsAgrement && (
        <div className="card p-4 space-y-3 border-l-4 border-primary-400">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-2">
            <Award size={12} className="text-primary-500" /> Agrément
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <F label="N° Agrément">
              <input {...register('num_agrement')} className="input" placeholder="AGR-16-..." />
            </F>
            <F label="Date d'agrément">
              <DateInput value={watch('date_agrement')||''} onChange={v=>setValue('date_agrement',v)} />
            </F>
            <F label="Durée (années)">
              <select {...register('duree_agrement')} className="input">
                <option value="">—</option>
                {[1,2,3,4,5].map(n => <option key={n} value={n}>{n} an{n>1?'s':''}</option>)}
              </select>
            </F>
            <F label="Date début">
              <DateInput value={watch('date_debut_agrement')||''} onChange={v=>setValue('date_debut_agrement',v)} />
            </F>
            <F label="Date fin">
              <DateInput value={watch('date_fin_agrement')||''} onChange={v=>setValue('date_fin_agrement',v)} />
            </F>
          </div>
          <div>
            <label className="label">Codes déchets autorisés par l'agrément</label>
            <CodesPicker value={codesValue} onChange={setCodesValue} />
          </div>
        </div>
      )}

      {/* Transporteur specific */}
      {isTransporteur && (
        <div className="card p-4 space-y-3 border-l-4 border-amber-400">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Informations transport</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <F label="Type d'engins">
              <input {...register('type_engins')} className="input" placeholder="Camion-citerne, Benne..." />
            </F>
            <F label="Immatriculation">
              <input {...register('immatriculation')} className="input" placeholder="16-XXXXX-16" />
            </F>
            <F label="Nom du conducteur">
              <input {...register('nom_conducteur')} className="input" placeholder="Nom et prénom" />
            </F>
          </div>
        </div>
      )}

      {/* Convention — CET uniquement */}
      {type === 'CET' && (
        <div className="card p-4 space-y-3 border-l-4 border-slate-400">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-2">
            <FileSignature size={12} className="text-slate-500" /> Convention avec le récupérateur
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <F label="N° Convention" full>
              <input {...register('convention_numero')} className="input" placeholder="CONV-16-2024-..." autoComplete="new-password" />
            </F>
            <F label="Date de la convention">
              <DateInput value={watch('convention_date')||''} onChange={v=>setValue('convention_date',v)} />
            </F>
            <F label="Durée (années)">
              <select {...register('convention_duree')} className="input">
                <option value="">—</option>
                {[1,2,3,4,5,10].map(n => <option key={n} value={n}>{n} an{n>1?'s':''}</option>)}
              </select>
            </F>
          </div>
        </div>
      )}

      {/* Localisation */}
      <div className="card p-4 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Localisation & Contact</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <F label="Wilaya">
            <select {...register('wilaya')} className="input">
              <option value="">-- Sélectionner --</option>
              {WILAYAS.map(w => <option key={w.code} value={w.code}>{w.label}</option>)}
            </select>
          </F>
          <F label="Commune">
            <select {...register('commune')} className="input" disabled={!wilaya}>
              <option value="">-- Sélectionner --</option>
              {communes.map(c => <option key={c.code} value={c.label}>{c.label}</option>)}
            </select>
          </F>
          <F label="Adresse">
            <input {...register('adresse')} className="input" placeholder="Adresse complète" />
          </F>
          <F label="Téléphone">
            <input {...register('telephone')} className="input" placeholder="+213 XX XX XX XX" />
          </F>
          <F label="Email">
            <input {...register('email')} type="email" className="input" placeholder="contact@..." />
          </F>
        </div>
      </div>

      {/* Statut + Notes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <F label="Statut">
          <select {...register('statut')} className="input">
            <option value="ACTIF">Actif</option>
            <option value="INACTIF">Inactif</option>
            <option value="SUSPENDU">Suspendu</option>
          </select>
        </F>
        <F label="Notes">
          <textarea {...register('notes')} className="input" rows={2} placeholder="Notes internes..." />
        </F>
      </div>

      <div className="flex gap-3 pt-2 border-t border-[#E2E8F0]">
        <button type="submit" disabled={saving} className="btn-primary">
          <Save size={15} /> {saving ? 'Enregistrement...' : isEdit ? 'Mettre à jour' : 'Créer l\'opérateur'}
        </button>
        <button type="button" onClick={onClose} className="btn-secondary">Annuler</button>
      </div>
    </form>
  )
}

// ── Operateur Card ────────────────────────────────────────────────────────────
function OperateurCard({ op, onEdit, onDelete, onView }) {
  const cfg  = TYPE_CFG[op.type_operateur] || TYPE_CFG.GENERATEUR
  const Icon = cfg.icon

  return (
    <div className="card p-4 hover:shadow-lg transition-all cursor-pointer" onClick={() => onView(op)}>
      <div className="flex items-start gap-4">
        <div className={`w-11 h-11 rounded-xl ${cfg.color} flex items-center justify-center flex-shrink-0`}>
          <Icon size={20} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-bold text-slate-900 dark:text-white text-sm">{op.raison_sociale}</p>
            <span className={`badge text-[10px] border ${cfg.light}`}>{cfg.label}</span>
            <span className={`badge text-[10px] ${op.statut === 'ACTIF' ? 'badge-green' : op.statut === 'SUSPENDU' ? 'badge-red' : 'badge-gray'}`}>
              {op.statut_display || op.statut}
            </span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1 text-xs text-slate-400">
            {op.wilaya && <span className="flex items-center gap-1"><MapPin size={10} /> W.{op.wilaya}{op.commune ? ` — ${op.commune}` : ''}</span>}
            {op.telephone && <span className="flex items-center gap-1"><Phone size={10} /> {op.telephone}</span>}
            {op.email && <span className="flex items-center gap-1"><Mail size={10} /> {op.email}</span>}
          </div>
          {op.num_agrement && (
            <div className="flex items-center gap-2 mt-1.5">
              <span className="flex items-center gap-1 text-xs font-semibold text-primary-600">
                <Award size={11} /> {op.num_agrement}
              </span>
              {op.agrement_valide !== undefined && (
                <span className={`text-[10px] font-bold ${op.agrement_valide ? 'text-emerald-600' : 'text-red-600'}`}>
                  {op.agrement_valide ? '✅ Valide' : '🔴 Expiré'}
                </span>
              )}
              {op.date_fin_agrement && (
                <span className="text-[10px] text-slate-400">jusqu'au {formatDateFR(op.date_fin_agrement)}</span>
              )}
            </div>
          )}
          {op.type_operateur === 'CET' && op.convention_numero && (
            <div className="flex items-center gap-2 mt-1.5">
              <span className="flex items-center gap-1 text-xs font-semibold text-slate-600">
                <FileSignature size={11} /> {op.convention_numero}
              </span>
              {op.convention_valide !== undefined && (
                <span className={`text-[10px] font-bold ${op.convention_valide ? 'text-emerald-600' : 'text-red-600'}`}>
                  {op.convention_valide ? '✅ Convention valide' : '🔴 Convention expirée'}
                </span>
              )}
              {op.convention_date_fin && (
                <span className="text-[10px] text-slate-400">jusqu'au {formatDateFR(op.convention_date_fin)}</span>
              )}
            </div>
          )}
        </div>
        <div className="flex gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
          <button onClick={() => onView(op)} className="btn-ghost p-2 text-slate-400 hover:text-primary-600"><Eye size={14} /></button>
          <button onClick={() => onEdit(op)} className="btn-ghost p-2 text-slate-400 hover:text-primary-600"><Edit size={14} /></button>
          <button onClick={() => onDelete(op.id)} className="btn-ghost p-2 text-slate-400 hover:text-red-600"><Trash2 size={14} /></button>
        </div>
      </div>
    </div>
  )
}

// ── Detail Panel ──────────────────────────────────────────────────────────────
function DetailPanel({ op, onClose, onEdit }) {
  if (!op) return null
  const cfg  = TYPE_CFG[op.type_operateur] || TYPE_CFG.GENERATEUR
  const Icon = cfg.icon

  const Row = ({ label, value }) => value ? (
    <div className="flex gap-3 text-sm py-1.5 border-b border-slate-50">
      <span className="w-36 text-slate-400 flex-shrink-0">{label}</span>
      <span className="font-medium text-slate-800 dark:text-slate-200">{value}</span>
    </div>
  ) : null

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="fixed inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white dark:bg-[#16240D] h-full overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className={`px-6 py-5 flex items-center justify-between border-b border-[#E2E8F0]`}
          style={{ background: `linear-gradient(135deg, ${cfg.color.replace('bg-','var(--')}33, transparent)` }}>
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 rounded-xl ${cfg.color} flex items-center justify-center flex-shrink-0`}>
              <Icon size={24} className="text-white" />
            </div>
            <div>
              <p className="font-bold text-slate-900 dark:text-white">{op.raison_sociale}</p>
              <p className="text-xs text-slate-500">{cfg.label}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => onEdit(op)} className="btn-secondary btn-sm"><Edit size={13} /></button>
            <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
          </div>
        </div>

        <div className="p-6 space-y-5">
          {/* Identification */}
          <div>
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-3">Identification</p>
            <Row label="NIN"                value={op.nin} />
            <Row label="NIF"                value={op.nif} />
            <Row label="NIS"                value={op.nis} />
            <Row label="Registre Commerce"  value={op.registre_commerce} />
            <Row label="Secteur d'activité" value={op.secteur_activite} />
          </div>

          {/* Agrément */}
          {op.num_agrement && (
            <div className={`card p-4 ${op.agrement_valide ? 'border-emerald-200 bg-emerald-50/30' : 'border-red-200 bg-red-50/30'}`}>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Agrément</p>
                <span className={`badge ${op.agrement_valide ? 'badge-green' : 'badge-red'}`}>
                  {op.agrement_valide ? '✅ Valide' : '🔴 Expiré'}
                </span>
              </div>
              <Row label="N° Agrément"   value={op.num_agrement} />
              <Row label="Date"          value={formatDateFR(op.date_agrement)} />
              <Row label="Du"            value={formatDateFR(op.date_debut_agrement)} />
              <Row label="Au"            value={formatDateFR(op.date_fin_agrement)} />
              {op.codes_dechets_autorises && (
                <div className="mt-3">
                  <p className="text-xs text-slate-400 mb-1.5">Codes autorisés :</p>
                  <div className="flex flex-wrap gap-1">
                    {op.codes_dechets_autorises.split(',').map(c => c.trim()).filter(Boolean).map(c => {
                      const n = NOMENCLATURE.find(x => x.code === c)
                      return (
                        <span key={c} title={n?.nom_fr || ''}
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border
                          ${n?.classe === 'SD' ? 'bg-red-50 text-red-700 border-red-200' :
                            n?.classe === 'S'  ? 'bg-amber-50 text-amber-700 border-amber-200' :
                            'bg-slate-100 text-slate-600 border-slate-200'}`}>
                          {c}
                        </span>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Convention CET */}
          {op.type_operateur === 'CET' && op.convention_numero && (
            <div className={`card p-4 ${op.convention_valide ? 'border-slate-200 bg-slate-50/30' : 'border-red-200 bg-red-50/30'}`}>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                  <FileSignature size={11} /> Convention
                </p>
                <span className={`badge ${op.convention_valide ? 'badge-green' : 'badge-red'}`}>
                  {op.convention_valide ? '✅ Valide' : '🔴 Expirée'}
                </span>
              </div>
              <Row label="N° Convention"  value={op.convention_numero} />
              <Row label="Date"           value={formatDateFR(op.convention_date)} />
              <Row label="Durée"          value={op.convention_duree ? `${op.convention_duree} an${op.convention_duree > 1 ? 's' : ''}` : null} />
              <Row label="Échéance"       value={formatDateFR(op.convention_date_fin)} />
            </div>
          )}

          {/* Transporteur */}
          {op.type_operateur === 'TRANSPORTEUR' && (op.type_engins || op.immatriculation) && (
            <div>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-3">Transport</p>
              <Row label="Type d'engins"     value={op.type_engins} />
              <Row label="Immatriculation"   value={op.immatriculation} />
              <Row label="Conducteur"        value={op.nom_conducteur} />
            </div>
          )}

          {/* Localisation */}
          <div>
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-3">Localisation & Contact</p>
            <Row label="Wilaya"    value={op.wilaya ? `W.${op.wilaya}` : null} />
            <Row label="Commune"   value={op.commune} />
            <Row label="Adresse"   value={op.adresse} />
            <Row label="Téléphone" value={op.telephone} />
            <Row label="Email"     value={op.email} />
          </div>

          {op.notes && (
            <div>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">Notes</p>
              <p className="text-sm text-slate-600 bg-slate-50 rounded-xl p-3">{op.notes}</p>
            </div>
          )}

          <div className="text-xs text-slate-400 border-t border-[#E2E8F0] pt-3">
            <p>Créé le : {op.created_at ? new Date(op.created_at).toLocaleDateString('fr-DZ') : '—'}</p>
            <p>Mis à jour le : {op.updated_at ? new Date(op.updated_at).toLocaleDateString('fr-DZ') : '—'}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function OperateursPage() {
  const [operateurs, setOperateurs] = useState([])
  const [loading,    setLoading]    = useState(true)
  const [showForm,   setShowForm]   = useState(false)
  const [editing,    setEditing]    = useState(null)
  const [viewing,    setViewing]    = useState(null)
  const [search,     setSearch]     = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [statut,     setStatut]     = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const p = { page_size: 200 }
      if (search)     p.search          = search
      if (typeFilter) p.type_operateur  = typeFilter
      if (statut)     p.statut          = statut
      const res = await opAPI.getAll(p)
      setOperateurs(res.data.results || res.data)
    } catch { toast.error('Erreur chargement') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [search, typeFilter, statut])

  const handleDelete = async (id) => {
    if (!window.confirm('Supprimer cet opérateur ?')) return
    try { await opAPI.delete(id); toast.success('Supprimé'); load() }
    catch { toast.error('Erreur suppression') }
  }

  const handleSave = () => { setShowForm(false); setEditing(null); load() }
  const handleEdit = (op) => { setEditing(op); setViewing(null); setShowForm(true) }

  // Group by type
  const grouped = useMemo(() => {
    return Object.keys(TYPE_CFG).map(type => ({
      type,
      operateurs: operateurs.filter(op => op.type_operateur === type),
    })).filter(g => g.operateurs.length > 0 || !typeFilter)
  }, [operateurs, typeFilter])

  // Counts by type
  const counts = useMemo(() => {
    const c = {}
    operateurs.forEach(op => { c[op.type_operateur] = (c[op.type_operateur] || 0) + 1 })
    return c
  }, [operateurs])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Users size={24} className="text-primary-600" /> Opérateurs
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Acteurs et institutions liés aux récupérateurs de déchets — {operateurs.length} enregistré(s)
          </p>
        </div>
        <button onClick={() => { setEditing(null); setShowForm(true) }} className="btn-primary">
          <Plus size={16} /> Nouvel opérateur
        </button>
      </div>

      {/* Type chips */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => setTypeFilter('')}
          className={`px-3 py-1.5 rounded-full text-xs font-bold border-2 transition-all
            ${!typeFilter ? 'bg-slate-700 text-white border-transparent' : 'border-slate-200 text-slate-600 bg-white'}`}>
          Tous ({operateurs.length})
        </button>
        {Object.entries(TYPE_CFG).map(([k, v]) => {
          const Icon  = v.icon
          const count = counts[k] || 0
          return (
            <button key={k} onClick={() => setTypeFilter(typeFilter === k ? '' : k)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border-2 transition-all
                ${typeFilter === k
                  ? `${v.color} text-white border-transparent`
                  : `border-slate-200 text-slate-600 bg-white dark:bg-[#16240D] dark:border-[#2B3D1E] dark:text-slate-300`}`}>
              <Icon size={11} /> {v.label.split(' ')[0]} ({count})
            </button>
          )
        })}
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-52">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher par raison sociale, NIF, RC..."
            className="input pl-9 text-sm" />
          {search && <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2"><X size={13} className="text-slate-400" /></button>}
        </div>
        <select value={statut} onChange={e => setStatut(e.target.value)} className="input w-36 text-sm">
          <option value="">Tous statuts</option>
          <option value="ACTIF">Actif</option>
          <option value="INACTIF">Inactif</option>
          <option value="SUSPENDU">Suspendu</option>
        </select>
        <span className="text-xs text-slate-400 self-center">{operateurs.length} opérateur(s)</span>
      </div>

      {/* List */}
      {loading ? <Spinner /> : operateurs.length === 0 ? (
        <div className="card p-16 text-center">
          <Users size={40} className="mx-auto mb-3 text-slate-200" />
          <p className="font-semibold text-slate-400">Aucun opérateur enregistré</p>
          <p className="text-sm text-slate-300 mt-1">Les opérateurs sont enregistrés une seule fois et réutilisés dans toutes les opérations.</p>
          <button onClick={() => { setEditing(null); setShowForm(true) }} className="btn-primary mt-4">
            <Plus size={15} /> Ajouter le premier opérateur
          </button>
        </div>
      ) : typeFilter ? (
        <div className="space-y-2">
          {operateurs.map(op => (
            <OperateurCard key={op.id} op={op} onEdit={handleEdit} onDelete={handleDelete} onView={setViewing} />
          ))}
        </div>
      ) : (
        // Grouped by type
        <div className="space-y-6">
          {grouped.map(g => {
            if (g.operateurs.length === 0) return null
            const cfg  = TYPE_CFG[g.type]
            const Icon = cfg.icon
            return (
              <div key={g.type}>
                <div className="flex items-center gap-3 mb-3">
                  <div className={`w-7 h-7 rounded-lg ${cfg.color} flex items-center justify-center`}>
                    <Icon size={14} className="text-white" />
                  </div>
                  <h3 className="font-bold text-slate-800 dark:text-white text-sm">{cfg.label}</h3>
                  <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-bold">
                    {g.operateurs.length}
                  </span>
                </div>
                <div className="space-y-2 pl-4 border-l-2 border-slate-100 dark:border-[#2B3D1E]">
                  {g.operateurs.map(op => (
                    <OperateurCard key={op.id} op={op} onEdit={handleEdit} onDelete={handleDelete} onView={setViewing} />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Form modal */}
      <Modal open={showForm} onClose={() => { setShowForm(false); setEditing(null) }}
        title={editing ? `Modifier — ${editing.raison_sociale}` : 'Nouvel opérateur'} size="max-w-3xl">
        <OperateurForm operateur={editing} onSave={handleSave} onClose={() => { setShowForm(false); setEditing(null) }} />
      </Modal>

      {/* Detail panel */}
      {viewing && <DetailPanel op={viewing} onClose={() => setViewing(null)} onEdit={handleEdit} />}
    </div>
  )
}
