import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import {
  User, Shield, Save, Building2, CheckCircle2,
  Award, Plus, X, ChevronDown, ChevronRight, AlertTriangle,
  Ban, XCircle, Edit2, Layers
} from 'lucide-react'
import { useAuthStore } from '../../store'
import api from '../../api'
import { WILAYAS, getCommunesByWilaya } from '../../utils/algeria_geo'
import { NOMENCLATURE } from '../nomenclature/nomenclatureData'
import { NOMENCLATURE_GOLD } from '../nomenclature/nomenclatureGold'
import DateInput from '../../components/common/DateInput'
import { formatDateFR } from '../../utils/formatDate'
import SpecialisationReadOnly from './SpecialisationReadOnly'

// Merged lookup — NOMENCLATURE_GOLD has real designations + dangerosite + annexe
const NOM_MAP = (() => {
  const m = {}
  NOMENCLATURE.forEach(n => { m[n.code] = n })
  NOMENCLATURE_GOLD.forEach(n => { m[n.code] = n })
  return m
})()
import toast from 'react-hot-toast'

const findCode = (code) => NOM_MAP[code] || null

// Defined once at module scope (not inside each form component) so its identity
// stays stable across re-renders — otherwise React remounts the wrapped <input>
// on every keystroke (these forms re-render on every watch()'d change), which
// makes text fields lose focus after each character typed.
function F({ label, req, children, col }) {
  return (
    <div className={col || ''}>
      <label className="label">{label}{req && <span className="text-red-500 ml-0.5">*</span>}</label>
      {children}
    </div>
  )
}

const ETENDUE_CFG = {
  NATIONALE: { label: 'Nationale',     icon: '🇩🇿' },
  WILAYA:    { label: 'Par wilaya',    icon: '📍'  },
  WILAYAS:   { label: 'Multi-wilayas', icon: '🗺️'  },
}

const STATUT_CFG = {
  ACTIF:    { label: 'Actif',    badge: 'badge-green',  icon: CheckCircle2 },
  EXPIRE:   { label: 'Expiré',  badge: 'badge-red',    icon: XCircle      },
  SUSPENDU: { label: 'Suspendu',badge: 'badge-yellow', icon: Ban          },
  REVOQUE:  { label: 'Révoqué', badge: 'badge-red',    icon: XCircle      },
}

// ── Codes Picker ──────────────────────────────────────────────────────────────
function CodesPicker({ value, onChange }) {
  const [search,       setSearch]       = useState('')
  const [open,         setOpen]         = useState(false)
  const [classeFilter, setClasseFilter] = useState('')

  const selected = useMemo(() =>
    value ? value.split(',').map(s => s.trim()).filter(Boolean) : []
  , [value])

  const filtered = useMemo(() =>
    Object.values(NOM_MAP)
      .filter(n => !classeFilter || n.classe === classeFilter)
      .filter(n => !search ||
        n.code.toLowerCase().includes(search.toLowerCase()) ||
        n.nom_fr.toLowerCase().includes(search.toLowerCase()))
      .slice(0, 60)
  , [search, classeFilter])

  const toggle = (code) => {
    const next = selected.includes(code)
      ? selected.filter(c => c !== code)
      : [...selected, code]
    onChange(next.join(', '))
  }

  return (
    <div className="space-y-2">
      {selected.length > 0 && (
        <div className="card p-3 bg-slate-50/50 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-slate-500">{selected.length} code(s) sélectionné(s)</p>
            <button type="button" onClick={() => onChange('')}
              className="text-[10px] text-red-500 font-semibold">Tout effacer</button>
          </div>
          <div className="flex flex-wrap gap-1">
            {selected.map(c => {
              const n  = findCode(c)
              const cl = n?.classe || ''
              return (
                <span key={c} title={n?.nom_fr || c}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border
                    ${cl==='SD'?'bg-red-50 text-red-700 border-red-200':
                      cl==='S'?'bg-amber-50 text-amber-700 border-amber-200':
                      'bg-primary-50 text-primary-700 border-primary-200'}`}>
                  <span className="font-mono">{c}</span>
                  <button type="button" onClick={() => toggle(c)}
                    className="opacity-60 hover:opacity-100"><X size={9}/></button>
                </span>
              )
            })}
          </div>
        </div>
      )}

      <button type="button" onClick={() => setOpen(!open)}
        className="btn-secondary btn-sm w-full justify-between">
        <span className="flex items-center gap-2"><Plus size={13}/> Sélectionner des codes déchets</span>
        {open ? <ChevronDown size={13}/> : <ChevronRight size={13}/>}
      </button>

      {open && (
        <div className="border border-[#E2E8F0] rounded-xl overflow-hidden">
          <div className="p-2 border-b border-[#E2E8F0] bg-slate-50 space-y-2">
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Rechercher code ou désignation..." className="input text-xs" autoFocus/>
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                {[
                  {k:'', l:'Tous'},
                  {k:'SD',l:'SD', c:'bg-red-100 text-red-700'},
                  {k:'S', l:'S',  c:'bg-amber-100 text-amber-700'},
                  {k:'D', l:'D',  c:'bg-slate-100 text-slate-600'},
                ].map(f => (
                  <button key={f.k} type="button" onClick={() => setClasseFilter(f.k)}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all
                      ${classeFilter===f.k?'bg-primary-600 text-white':f.c||'bg-slate-100 text-slate-600'}`}>
                    {f.l}
                  </button>
                ))}
              </div>
              <button type="button"
                onClick={() => onChange([...new Set([...selected, ...filtered.map(n=>n.code)])].join(', '))}
                className="text-[10px] text-primary-600 font-semibold hover:underline ml-auto">
                Tout sélectionner ({filtered.length})
              </button>
            </div>
          </div>
          <div className="max-h-52 overflow-y-auto">
            {filtered.map(n => {
              const checked = selected.includes(n.code)
              return (
                <button key={n.code} type="button" onClick={() => toggle(n.code)}
                  className={`w-full flex items-start gap-3 px-3 py-2 text-left transition-all text-xs
                    ${checked?'bg-primary-50 border-l-2 border-primary-500':'hover:bg-slate-50'}`}>
                  <div className={`w-4 h-4 rounded border flex-shrink-0 mt-0.5 flex items-center justify-center
                    ${checked?'bg-primary-600 border-primary-600':'border-slate-300'}`}>
                    {checked && <CheckCircle2 size={10} className="text-white"/>}
                  </div>
                  <div className="flex-1 min-w-0 flex items-start gap-2">
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <span className="font-mono font-bold text-primary-700">{n.code}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold
                        ${n.classe==='SD'?'bg-red-100 text-red-700':
                          n.classe==='S'?'bg-amber-100 text-amber-700':
                          'bg-slate-100 text-slate-600'}`}>
                        {n.classe}
                      </span>
                    </div>
                    <p className="text-slate-600 truncate">{n.nom_fr}</p>
                  </div>
                </button>
              )
            })}
            {filtered.length === 0 && (
              <p className="text-center py-4 text-slate-400 text-xs">Aucun résultat</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Agrement Display (lecture seule) ─────────────────────────────────────────
function AgrementDisplay({ agrement, onEdit }) {
  const [showAll, setShowAll] = useState(false)
  const statutCfg = STATUT_CFG[agrement.statut] || STATUT_CFG.EXPIRE
  const etCfg     = ETENDUE_CFG[agrement.etendue_geo] || {}
  const StIcon    = statutCfg.icon

  const codesList = useMemo(() =>
    agrement.codes_dechets
      ? agrement.codes_dechets.split(',').map(c => c.trim()).filter(Boolean)
      : []
  , [agrement.codes_dechets])

  const MAX     = 20
  const visible = showAll ? codesList : codesList.slice(0, MAX)
  const hidden  = codesList.length - MAX

  return (
    <div className="space-y-4">
      {/* Info cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'N° Agrément',  value: agrement.numero_agrement  },
          { label: 'Délivré le',   value: formatDateFR(agrement.date_delivrance) },
          { label: 'Valide du',    value: formatDateFR(agrement.date_debut)      },
          { label: 'Au',           value: formatDateFR(agrement.date_fin)        },
        ].filter(i => i.value).map(({ label, value }) => (
          <div key={label} className="card p-3 bg-slate-50/50">
            <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
            <p className="font-bold text-slate-800 dark:text-white text-sm mt-0.5">{value}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <span className={`badge ${statutCfg.badge} flex items-center gap-1`}>
          <StIcon size={10}/> {statutCfg.label}
        </span>
        {agrement.etendue_geo && (
          <span className="badge badge-blue">{etCfg.icon} {etCfg.label}</span>
        )}
        {agrement.autorite_delivrance && (
          <span className="text-xs text-slate-500">{agrement.autorite_delivrance}</span>
        )}
      </div>

      {/* Codes table */}
      {codesList.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
              Codes déchets autorisés — {codesList.length} code(s)
            </p>
            {codesList.length > MAX && (
              <button onClick={() => setShowAll(!showAll)}
                className="text-xs text-primary-600 font-semibold hover:underline">
                {showAll ? 'Réduire' : `Voir tous (+${hidden})`}
              </button>
            )}
          </div>
          <div className="overflow-x-auto rounded-xl border border-[#E2E8F0] dark:border-[#2B3D1E]">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-100 dark:bg-[#2B3D1E]">
                  <th className="px-3 py-2 text-left font-bold text-slate-600 w-20">Code</th>
                  <th className="px-3 py-2 text-left font-bold text-slate-600">Désignation (Français)</th>
                  <th className="px-3 py-2 text-center font-bold text-slate-600 w-16">Classe</th>
                  <th className="px-3 py-2 text-center font-bold text-slate-600 w-36">Dangerosité</th>
                  <th className="px-3 py-2 text-center font-bold text-slate-600 w-14">Annexe</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((code, idx) => {
                  const found  = findCode(code)
                  const classe = found?.classe || ''
                  return (
                    <tr key={code}
                      className={`border-t border-[#E2E8F0] dark:border-[#2B3D1E]
                        ${idx%2===0?'bg-white dark:bg-[#16240D]':'bg-slate-50/50 dark:bg-[#16240D]/30'}
                        hover:bg-primary-50/30`}>
                      <td className="px-3 py-1.5">
                        <span className="font-mono font-bold text-primary-700">{code}</span>
                      </td>
                      <td className="px-3 py-1.5 text-slate-700 dark:text-slate-300">
                        {found?.nom_fr || <span className="text-slate-400 italic text-[10px]">Non trouvé</span>}
                      </td>
                      <td className="px-3 py-1.5 text-center">
                        <span className={`inline-flex px-1.5 py-0.5 rounded-full text-[9px] font-bold
                          ${classe==='SD'?'bg-red-100 text-red-700 border border-red-200':
                            classe==='S'?'bg-amber-100 text-amber-700 border border-amber-200':
                            'bg-slate-100 text-slate-600 border border-slate-200'}`}>
                          {classe || '—'}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-[10px] text-slate-600">
                        {found?.dangerosite || '—'}
                      </td>
                      <td className="px-3 py-1.5 text-center">
                        <span className="font-mono font-bold text-[10px] text-slate-500">
                          {found?.annexe || (classe==='SD'?'I':classe==='S'?'II':'III')}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {!showAll && hidden > 0 && (
            <p className="text-[10px] text-slate-400 text-center">
              ... et {hidden} autres codes.{' '}
              <button onClick={() => setShowAll(true)}
                className="text-primary-600 font-semibold hover:underline">
                Voir tous
              </button>
            </p>
          )}
        </div>
      )}

      <button onClick={onEdit} className="btn-secondary btn-sm">
        <Edit2 size={13}/> Modifier l'agrément
      </button>
    </div>
  )
}

// ── Agrement Form ─────────────────────────────────────────────────────────────
function AgrementForm({ agrement, recuperateurId, onSave, onCancel }) {
  const isEdit = !!agrement?.id
  const { register, handleSubmit, watch, setValue } = useForm({
    defaultValues: agrement || {
      type_agrement: 'AVEC_AGREMENT',
      etendue_geo:   'NATIONALE',
      statut:        'ACTIF',
      recuperateur:  recuperateurId,
    }
  })
  const [saving,       setSaving]       = useState(false)
  const [codesValue,   setCodesValue]   = useState(agrement?.codes_dechets || '')
  const [wilayasValue, setWilayasValue] = useState(agrement?.wilayas_couvertes || '')

  const etendueGeo = watch('etendue_geo')
  const duree      = watch('duree_validite_ans')
  const dateDebut  = watch('date_debut')

  useEffect(() => {
    if (dateDebut && duree) {
      const d = new Date(dateDebut)
      d.setFullYear(d.getFullYear() + parseInt(duree))
      setValue('date_fin', d.toISOString().split('T')[0])
    }
  }, [dateDebut, duree])

  const onSubmit = async (data) => {
    setSaving(true)
    data.codes_dechets     = codesValue
    data.wilayas_couvertes = wilayasValue
    data.recuperateur      = recuperateurId
    try {
      if (isEdit) {
        await api.patch(`/recuperateurs/agrements/${agrement.id}/`, data)
        toast.success('Agrément mis à jour')
      } else {
        await api.post('/recuperateurs/agrements/', data)
        toast.success('Agrément créé')
      }
      onSave()
    } catch { toast.error('Erreur lors de la sauvegarde') }
    finally { setSaving(false) }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <F label="Numéro d'agrément" req col="">
          <input {...register('numero_agrement',{required:true})} className="input" placeholder="N° 87"/>
        </F>
        <F label="Autorité de délivrance" col="">
          <input {...register('autorite_delivrance')} className="input"
            placeholder="Ministère de l'Environnement..."/>
        </F>
      </div>

      <div className="card p-4 bg-slate-50/50 space-y-3">
        <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">Validité</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <F label="Date de délivrance" col="">
            <DateInput value={watch('date_delivrance')||''} onChange={v=>setValue('date_delivrance',v)}/>
          </F>
          <F label="Durée (années)" col="">
            <select {...register('duree_validite_ans')} className="input">
              <option value="">—</option>
              {[1,2,3,4,5].map(n=><option key={n} value={n}>{n} an{n>1?'s':''}</option>)}
            </select>
          </F>
          <F label="Date début" col="">
            <DateInput value={watch('date_debut')||''} onChange={v=>setValue('date_debut',v)}/>
          </F>
          <F label="Date fin" col="">
            <DateInput value={watch('date_fin')||''} onChange={v=>setValue('date_fin',v)}/>
          </F>
        </div>
      </div>

      <div className="card p-4 bg-slate-50/50 space-y-3">
        <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">Étendue géographique</p>
        <div className="flex gap-3 flex-wrap">
          {Object.entries(ETENDUE_CFG).map(([k,v]) => (
            <label key={k}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 cursor-pointer transition-all
                ${watch('etendue_geo')===k?'border-primary-500 bg-primary-50':'border-[#E2E8F0] hover:border-primary-200'}`}>
              <input type="radio" {...register('etendue_geo')} value={k} className="sr-only"/>
              <span className="text-lg">{v.icon}</span>
              <span className={`text-sm font-semibold
                ${watch('etendue_geo')===k?'text-primary-700':'text-slate-600'}`}>
                {v.label}
              </span>
            </label>
          ))}
        </div>

        {(etendueGeo==='WILAYA'||etendueGeo==='WILAYAS') && (
          <div>
            <label className="label">Wilaya(s) couverte(s)</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {wilayasValue && wilayasValue.split(',').map(s=>s.trim()).filter(Boolean).map(code => {
                const w = WILAYAS.find(x=>x.code===code)
                return (
                  <span key={code}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs
                      bg-primary-50 text-primary-700 border border-primary-200 font-semibold">
                    W.{code} {w?.nom}
                    <button type="button" onClick={() => {
                      const next = wilayasValue.split(',').map(s=>s.trim()).filter(s=>s&&s!==code)
                      setWilayasValue(next.join(', '))
                    }}><X size={10}/></button>
                  </span>
                )
              })}
            </div>
            <select className="input" onChange={e => {
              if (!e.target.value) return
              const cur = wilayasValue ? wilayasValue.split(',').map(s=>s.trim()).filter(Boolean) : []
              if (!cur.includes(e.target.value)) setWilayasValue([...cur, e.target.value].join(', '))
              e.target.value = ''
            }}>
              <option value="">+ Ajouter une wilaya...</option>
              {WILAYAS.map(w=><option key={w.code} value={w.code}>{w.label}</option>)}
            </select>
          </div>
        )}
      </div>

      <div className="card p-4 bg-slate-50/50 space-y-3">
        <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
          Codes déchets autorisés
        </p>
        <CodesPicker value={codesValue} onChange={setCodesValue}/>
      </div>

      <F label="Statut" col="">
        <select {...register('statut')} className="input">
          <option value="ACTIF">Actif</option>
          <option value="EXPIRE">Expiré</option>
          <option value="SUSPENDU">Suspendu</option>
          <option value="REVOQUE">Révoqué</option>
        </select>
      </F>

      <div className="flex gap-3 pt-2 border-t border-[#E2E8F0]">
        <button type="submit" disabled={saving} className="btn-primary">
          <Save size={15}/>
          {saving ? 'Enregistrement...' : isEdit ? "Mettre à jour l'agrément" : "Enregistrer l'agrément"}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">Annuler</button>
      </div>
    </form>
  )
}

// ── Main Profile Page ─────────────────────────────────────────────────────────
export default function ProfilPage() {
  const { user, loadUser } = useAuthStore()
  const [recup,       setRecup]       = useState(null)
  const [communes,    setCommunes]    = useState([])
  const [savingUser,  setSavingUser]  = useState(false)
  const [savingRec,   setSavingRec]   = useState(false)
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const [agrement,    setAgrement]    = useState(null)
  const [hasAgrement, setHasAgrement] = useState(null)
  const [showAgrForm, setShowAgrForm] = useState(false)
  const [loadingAgr,  setLoadingAgr]  = useState(false)

  const isRecuperateur = !!(user?.role === 'RECUPERATEUR' || user?.recuperateur_id)

  const userForm = useForm({ defaultValues: user || {} })
  const recForm  = useForm({})

  // Load recuperateur fiche
  useEffect(() => {
    if (isRecuperateur) {
      api.get('/accounts/mon-recuperateur/')
        .then(r => {
          setRecup(r.data)
          recForm.reset(r.data)
          if (r.data.wilaya) setCommunes(getCommunesByWilaya(r.data.wilaya))
        }).catch(() => {})
    }
  }, [isRecuperateur])

  // Load agrement
  useEffect(() => {
    if (isRecuperateur && user?.recuperateur_id) {
      setLoadingAgr(true)
      api.get(`/recuperateurs/agrements/?recuperateur=${user.recuperateur_id}&page_size=1`)
        .then(r => {
          const results = r.data.results || r.data
          if (results.length > 0) {
            setAgrement(results[0])
            setHasAgrement(true)
          } else {
            setHasAgrement(false)
          }
        })
        .catch(() => { setHasAgrement(false) })
        .finally(() => setLoadingAgr(false))
    }
  }, [isRecuperateur, user?.recuperateur_id])

  const wilaya = recForm.watch('wilaya')
  useEffect(() => {
    if (wilaya) setCommunes(getCommunesByWilaya(wilaya))
    else setCommunes([])
  }, [wilaya])

  const onSaveUser = async (data) => {
    setSavingUser(true)
    try {
      await api.patch('/accounts/me/', {
        first_name: data.first_name, last_name: data.last_name,
        email: data.email, phone: data.phone,
      })
      await loadUser()
      toast.success('Profil mis à jour')
    } catch { toast.error('Erreur') }
    finally { setSavingUser(false) }
  }

  const onSaveRec = async (data) => {
    setSavingRec(true)
    try {
      // logo n'est jamais modifié depuis ce formulaire (upload dédié via uploadLogo) —
      // renvoyer l'URL texte reçue du GET casserait la validation ImageField du backend.
      const { logo, ...payload } = data
      await api.patch('/accounts/mon-recuperateur/', payload)
      toast.success('Fiche récupérateur mise à jour')
      const r = await api.get('/accounts/mon-recuperateur/')
      setRecup(r.data)
      recForm.reset(r.data)
    } catch { toast.error('Erreur') }
    finally { setSavingRec(false) }
  }

  const uploadLogo = async (file) => {
    if (!file) return
    setUploadingLogo(true)
    try {
      const formData = new FormData()
      formData.append('logo', file)
      const r = await api.patch('/accounts/mon-recuperateur/', formData)
      setRecup(r.data)
      toast.success('Logo mis à jour')
    } catch { toast.error('Erreur upload du logo') }
    finally { setUploadingLogo(false) }
  }

  const onAgrementSaved = async () => {
    setShowAgrForm(false)
    if (user?.recuperateur_id) {
      const r = await api.get(`/recuperateurs/agrements/?recuperateur=${user.recuperateur_id}&page_size=1`)
      const results = r.data.results || r.data
      if (results.length > 0) {
        setAgrement(results[0])
        setHasAgrement(true)
      }
    }
  }

  const initials = `${user?.first_name?.[0]||''}${user?.last_name?.[0]||''}`.toUpperCase() || 'U'
  const ROLES = {
    SUPERADMIN:'Super Admin', ADMIN:'Administrateur',
    INSPECTEUR:'Inspecteur', RECUPERATEUR:'Récupérateur', READONLY:'Lecture seule',
  }
  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Mon Profil</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Vos informations sont utilisées automatiquement dans toutes les opérations
        </p>
      </div>

      {/* Avatar */}
      <div className="card p-5 flex items-center gap-5">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-800
          flex items-center justify-center text-white text-xl font-black flex-shrink-0">
          {initials}
        </div>
        <div>
          <p className="text-lg font-bold text-slate-900 dark:text-white">
            {user?.first_name} {user?.last_name}
          </p>
          <p className="text-sm text-slate-500">{ROLES[user?.role] || user?.role}</p>
          {user?.recuperateur_nom && (
            <p className="text-sm text-primary-600 font-semibold flex items-center gap-1 mt-1">
              <Shield size={12}/> {user.recuperateur_nom}
            </p>
          )}
          {agrement && (
            <p className="text-xs text-emerald-600 font-semibold flex items-center gap-1 mt-0.5">
              <Award size={11}/> Agrément n°{agrement.numero_agrement} — {STATUT_CFG[agrement.statut]?.label}
            </p>
          )}
        </div>
      </div>

      {/* ── Informations personnelles ── */}
      <div className="card p-5">
        <h3 className="font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
          <User size={16} className="text-primary-600"/> Informations personnelles
        </h3>
        <form onSubmit={userForm.handleSubmit(onSaveUser)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <F label="Prénom">
              <input {...userForm.register('first_name')} className="input" placeholder="Prénom"/>
            </F>
            <F label="Nom">
              <input {...userForm.register('last_name')} className="input" placeholder="Nom"/>
            </F>
          </div>
          <F label="Email">
            <input {...userForm.register('email')} type="email" className="input" placeholder="email@..."/>
          </F>
          <F label="Téléphone">
            <input {...userForm.register('phone')} className="input" placeholder="+213 XX XX XX XX"/>
          </F>
          <div className="grid grid-cols-2 gap-4 pt-2 border-t border-[#E2E8F0]">
            <div>
              <label className="label text-slate-400">Nom d'utilisateur</label>
              <input value={user?.username||''} disabled className="input opacity-60 cursor-not-allowed"/>
            </div>
            <div>
              <label className="label text-slate-400">Rôle</label>
              <input value={ROLES[user?.role]||''} disabled className="input opacity-60 cursor-not-allowed"/>
            </div>
          </div>
          <button type="submit" disabled={savingUser} className="btn-primary">
            <Save size={15}/> {savingUser ? 'Enregistrement...' : 'Enregistrer le profil'}
          </button>
        </form>
      </div>

      {/* ── Fiche récupérateur ── */}
      {isRecuperateur && recup && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Building2 size={16} className="text-primary-600"/> Fiche récupérateur
            </h3>
            <span className="badge badge-green text-[10px] flex items-center gap-1">
              <CheckCircle2 size={9}/> Réutilisée dans toutes les opérations
            </span>
          </div>
          <div className="card p-3 bg-primary-50/50 border-primary-200 mb-4">
            <p className="text-xs text-primary-700">
              <strong>ℹ️</strong> Ces informations s'appliquent automatiquement à toutes vos opérations, déclarations et documents.
            </p>
          </div>

          <div className="flex items-center gap-4 mb-5 pb-5 border-b border-[#E2E8F0]">
            <div className="w-16 h-16 rounded-xl border border-[#E2E8F0] dark:border-[#2B3D1E] flex items-center justify-center overflow-hidden bg-slate-50 flex-shrink-0">
              {recup?.logo
                ? <img src={recup.logo} alt="Logo" className="w-full h-full object-contain"/>
                : <Building2 size={22} className="text-slate-300"/>
              }
            </div>
            <div>
              <label className="label mb-1">Logo de l'entreprise</label>
              <label className="btn-secondary btn-sm cursor-pointer inline-flex">
                {uploadingLogo ? 'Envoi...' : 'Choisir un fichier'}
                <input type="file" accept="image/*" className="hidden" disabled={uploadingLogo}
                  onChange={e => uploadLogo(e.target.files?.[0])}/>
              </label>
              <p className="text-[11px] text-slate-400 mt-1">Utilisé dans les documents PDF (BL, BSD...)</p>
            </div>
          </div>

          <form onSubmit={recForm.handleSubmit(onSaveRec)} className="space-y-5">
            {/* Identification */}
            <div className="space-y-3">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">Identification</p>
              <F label="Raison sociale">
                <input {...recForm.register('nom_raison_sociale')} className="input"/>
              </F>
              <div className="grid grid-cols-2 gap-3">
                <F label="Responsable">
                  <input {...recForm.register('responsable')} className="input"/>
                </F>
                <F label="Statut juridique">
                  <select {...recForm.register('statut_juridique')} className="input">
                    <option value="">--</option>
                    {['EURL','SARL','SPA','SNC','PHYSIQUE','AUTRE'].map(s=>(
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </F>
              </div>
              <div className="grid grid-cols-4 gap-3">
                <F label="NIF"><input {...recForm.register('nif')} className="input" placeholder="NIF"/></F>
                <F label="NIS"><input {...recForm.register('nis')} className="input" placeholder="NIS"/></F>
                <F label="RC"><input {...recForm.register('registre_commerce')} className="input" placeholder="RC/..."/></F>
                <F label="N° Article (NA)"><input {...recForm.register('numero_article')} className="input" placeholder="NA"/></F>
              </div>
            </div>

            {/* Localisation */}
            <div className="space-y-3 pt-3 border-t border-[#E2E8F0]">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">Localisation</p>
              <F label="Adresse">
                <textarea {...recForm.register('adresse')} className="input" rows={2}/>
              </F>
              <div className="grid grid-cols-3 gap-3">
                <F label="Wilaya">
                  <select {...recForm.register('wilaya')} className="input">
                    <option value="">-- Wilaya --</option>
                    {WILAYAS.map(w=><option key={w.code} value={w.code}>{w.label}</option>)}
                  </select>
                </F>
                <F label="Commune">
                  <select {...recForm.register('commune')} className="input" disabled={!wilaya}>
                    <option value="">-- Commune --</option>
                    {communes.map(c=><option key={c.code} value={c.label}>{c.label}</option>)}
                  </select>
                </F>
                <F label="Code postal">
                  <input {...recForm.register('code_postal')} className="input" placeholder="35000"/>
                </F>
              </div>
            </div>

            {/* Contact */}
            <div className="space-y-3 pt-3 border-t border-[#E2E8F0]">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">Contact</p>
              <div className="grid grid-cols-3 gap-3">
                <F label="Téléphone">
                  <input {...recForm.register('telephone')} className="input" placeholder="+213..."/>
                </F>
                <F label="Fax">
                  <input {...recForm.register('fax')} className="input" placeholder="+213..."/>
                </F>
                <F label="Email">
                  <input {...recForm.register('email')} type="email" className="input"/>
                </F>
                <F label="Site web">
                  <input {...recForm.register('site_web')} className="input"/>
                </F>
                <F label="Compte bancaire (RIB)">
                  <input {...recForm.register('compte_bancaire')} className="input" placeholder="Banque, agence, RIB..."/>
                </F>
              </div>
            </div>

            <button type="submit" disabled={savingRec} className="btn-primary">
              <Save size={15}/>
              {savingRec ? 'Enregistrement...' : 'Mettre à jour la fiche'}
            </button>
          </form>
        </div>
      )}

      {/* ── Spécialisation du récupérateur (LECTURE SEULE — assignée par l'administrateur) ── */}
      {isRecuperateur && recup && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Layers size={16} className="text-primary-600"/> Spécialisation — Types de déchets récupérés
            </h3>
          </div>
          <div className="card p-3 bg-primary-50/50 border-primary-200 mb-4">
            <p className="text-xs text-primary-700">
              <strong>ℹ️</strong> Cette spécialisation est attribuée par l'administrateur de la plateforme.
              Seuls les codes de la nomenclature correspondant à votre sélection sont affichés dans la page Nomenclature.
              Pour toute modification, contactez l'administrateur.
            </p>
          </div>
          <SpecialisationReadOnly assignedIds={recup.specialisation_details?.map(d => d.id) || []}/>
        </div>
      )}

      {/* ── Section Agrément ── */}
      {isRecuperateur && !loadingAgr && (
        <div className="card p-5">
          <h3 className="font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
            <Award size={16} className="text-primary-600"/> Agrément
          </h3>

          {/* Pas encore répondu — question oui/non */}
          {hasAgrement === false && !showAgrForm && (
            <div className="space-y-4">
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Votre récupérateur dispose-t-il d'un agrément délivré par le Ministère de l'Environnement ?
              </p>
              <div className="flex gap-3 flex-wrap">
                <button onClick={() => setShowAgrForm(true)}
                  className="flex items-center gap-2 px-6 py-3 rounded-xl border-2 border-emerald-500
                    bg-emerald-50 text-emerald-700 font-bold text-sm hover:bg-emerald-100 transition-all">
                  <CheckCircle2 size={16}/> Oui, j'ai un agrément
                </button>
                <div className="flex items-center gap-2 px-6 py-3 rounded-xl border-2 border-slate-200
                  bg-slate-50 text-slate-400 text-sm">
                  <XCircle size={16}/> Non, pas encore
                </div>
              </div>
              <p className="text-xs text-slate-400">
                Sans agrément vous pouvez uniquement récupérer des déchets ordinaires (classe D).
                Les déchets spéciaux (S) et spéciaux dangereux (SD) nécessitent un agrément.
              </p>
            </div>
          )}

          {/* Formulaire de création */}
          {hasAgrement === false && showAgrForm && (
            <div className="space-y-4">
              <div className="card p-3 bg-primary-50 border-primary-200">
                <p className="text-xs text-primary-700 font-semibold flex items-center gap-2">
                  <Award size={12}/>
                  Remplissez les informations de votre agrément une seule fois — elles seront sauvegardées et réutilisées automatiquement.
                </p>
              </div>
              <AgrementForm
                agrement={null}
                recuperateurId={user?.recuperateur_id}
                onSave={onAgrementSaved}
                onCancel={() => setShowAgrForm(false)}
              />
            </div>
          )}

          {/* Affichage agrément existant */}
          {hasAgrement === true && agrement && !showAgrForm && (
            <div className="space-y-4">
              <div className="card p-3 bg-emerald-50 border-emerald-200 flex items-center gap-3">
                <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0"/>
                <div>
                  <p className="text-sm font-bold text-emerald-800">Agrément enregistré</p>
                  <p className="text-xs text-emerald-600">
                    N° {agrement.numero_agrement} —{' '}
                    {agrement.codes_dechets?.split(',').filter(c=>c.trim()).length || 0} codes déchets autorisés
                  </p>
                </div>
              </div>
              <AgrementDisplay agrement={agrement} onEdit={() => setShowAgrForm(true)}/>
            </div>
          )}

          {/* Formulaire de modification */}
          {hasAgrement === true && agrement && showAgrForm && (
            <div className="space-y-4">
              <div className="card p-3 bg-amber-50 border-amber-200">
                <p className="text-xs text-amber-700 font-semibold flex items-center gap-2">
                  <AlertTriangle size={12}/>
                  Modification de l'agrément — les changements s'appliquent à toutes les opérations.
                </p>
              </div>
              <AgrementForm
                agrement={agrement}
                recuperateurId={user?.recuperateur_id}
                onSave={onAgrementSaved}
                onCancel={() => setShowAgrForm(false)}
              />
            </div>
          )}
        </div>
      )}

      {!isRecuperateur && (
        <div className="card p-4 bg-slate-50/50">
          <p className="text-sm text-slate-500 flex items-center gap-2">
            <Shield size={14} className="text-slate-400"/>
            En tant qu'administrateur, gérez les opérateurs depuis la page{' '}
            <Link to="/operateurs" className="text-primary-600 font-semibold hover:underline">Opérateurs</Link>.
            Les agréments sont gérés par chaque récupérateur depuis son propre profil.
          </p>
        </div>
      )}
    </div>
  )
}
