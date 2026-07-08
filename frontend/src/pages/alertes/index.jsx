import { useEffect, useState, useMemo } from 'react'
import {
  Bell, AlertTriangle, XCircle, Clock, CheckCircle2,
  Shield, RefreshCw, Search, ChevronRight, X,
  FileText, Award, Ban, Info, Zap, Eye
} from 'lucide-react'
import api from '../../api'
import { NOMENCLATURE } from '../nomenclature/nomenclatureData'
import { useAuthStore } from '../../store'
import { formatDateFR } from '../../utils/formatDate'
import toast from 'react-hot-toast'

// ── API ───────────────────────────────────────────────────────────────────────
const alertesAPI = {
  getAll:       () => api.get('/recuperateurs/agrements/alerts/'),
  verifierDroit:(data) => api.post('/recuperateurs/verifier-droit/', data),
  getRecups:    () => api.get('/recuperateurs/?page_size=200'),
}

// ── Type config ───────────────────────────────────────────────────────────────
const TYPE_CFG = {
  AGREMENT_EXPIRE:             { icon: XCircle,       color: 'text-red-600',    bg: 'bg-red-50',    border: 'border-red-500',  label: 'Agrément expiré'              },
  AGREMENT_EXPIRATION_URGENTE: { icon: AlertTriangle,  color: 'text-red-600',    bg: 'bg-red-50',    border: 'border-red-500',  label: 'Expiration urgente'           },
  AGREMENT_EXPIRATION_PROCHE:  { icon: Clock,          color: 'text-amber-600',  bg: 'bg-amber-50',  border: 'border-amber-400',label: 'Expiration proche'            },
  SANS_AGREMENT_ENREGISTRE:    { icon: FileText,       color: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-400',label: 'Agrément non enregistré'     },
  SANS_AGREMENT_DSD:           { icon: Ban,            color: 'text-red-700',    bg: 'bg-red-100',   border: 'border-red-600',  label: 'Sans agrément — Interdit'     },
  AGREMENT_EXPIRE_OPERATION:   { icon: XCircle,        color: 'text-red-700',    bg: 'bg-red-100',   border: 'border-red-600',  label: 'Agrément expiré — Interdit'  },
  CODE_NON_AUTORISE:           { icon: Shield,         color: 'text-red-700',    bg: 'bg-red-100',   border: 'border-red-600',  label: 'Code non autorisé'            },
}

const SEV_CFG = {
  critical: { badge: 'bg-red-600 text-white',   label: 'CRITIQUE'        },
  warning:  { badge: 'bg-amber-500 text-white',  label: 'AVERTISSEMENT'   },
  info:     { badge: 'bg-primary-500 text-white',   label: 'INFORMATION'     },
}

// ── Spinner ───────────────────────────────────────────────────────────────────
function Spinner() {
  return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// ── Alert Card ────────────────────────────────────────────────────────────────
function AlertCard({ alert }) {
  const cfg     = TYPE_CFG[alert.type] || TYPE_CFG.AGREMENT_EXPIRE
  const sevCfg  = SEV_CFG[alert.severity] || SEV_CFG.warning
  const Icon    = cfg.icon

  return (
    <div className={`card p-5 border-l-4 ${cfg.border} ${cfg.bg} dark:bg-opacity-10 transition-all hover:shadow-lg`}>
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className={`w-11 h-11 rounded-xl bg-white flex items-center justify-center flex-shrink-0 shadow-sm`}>
          <Icon size={22} className={cfg.color} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-black ${sevCfg.badge}`}>
              {sevCfg.label}
            </span>
            <span className="text-xs font-bold text-slate-600 dark:text-slate-300">
              {cfg.label}
            </span>
            {alert.jours_restants !== undefined && alert.jours_restants !== null && (
              <span className={`text-xs font-bold ${alert.jours_restants <= 30 ? 'text-red-600' : 'text-amber-600'}`}>
                ⏱ {alert.jours_restants} jours restants
              </span>
            )}
          </div>

          <p className="font-bold text-slate-900 dark:text-white text-sm mb-1">{alert.titre}</p>

          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{alert.message}</p>

          {/* Meta */}
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-3 text-xs text-slate-400">
            {alert.recuperateur && (
              <span className="flex items-center gap-1 font-semibold text-slate-600">
                <Shield size={11} /> {alert.recuperateur}
              </span>
            )}
            {alert.wilaya && (
              <span className="flex items-center gap-1">
                📍 Wilaya {alert.wilaya}
              </span>
            )}
            {alert.date && (
              <span className="flex items-center gap-1">
                📅 {formatDateFR(alert.date)}
              </span>
            )}
            {alert.code_dechet && (
              <span className="flex items-center gap-1 font-mono text-primary-600 font-bold">
                [{alert.code_dechet}] {alert.classe_dechet}
              </span>
            )}
          </div>

          {/* Action button */}
          {alert.action && (
            <div className="mt-3">
              <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold
                ${alert.severity === 'critical'
                  ? 'bg-red-600 text-white'
                  : 'bg-amber-500 text-white'}`}>
                <ChevronRight size={12} /> {alert.action}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Vérificateur de droit ─────────────────────────────────────────────────────
function VerificateurDroit({ recuperateurs, currentUser }) {
  const isRecup = currentUser?.role === 'RECUPERATEUR'
  const [recupId,  setRecupId]  = useState(isRecup ? (currentUser?.recuperateur_id || '') : '')
  const [code,     setCode]     = useState('')
  const [result,   setResult]   = useState(null)
  const [checking, setChecking] = useState(false)
  const [codeSearch, setCodeSearch] = useState('')

  const filteredCodes = useMemo(() =>
    NOMENCLATURE.filter(n =>
      n.code.includes(codeSearch) ||
      n.nom_fr.toLowerCase().includes(codeSearch.toLowerCase())
    ).slice(0, 30)
  , [codeSearch])

  const handleVerify = async () => {
    if (!recupId || !code) {
      toast.error('Sélectionnez un récupérateur et un code déchet')
      return
    }
    setChecking(true)
    setResult(null)
    try {
      const nom = NOMENCLATURE.find(n => n.code === code)
      const res = await alertesAPI.verifierDroit({
        recuperateur_id: recupId,
        code_dechet:     code,
        classe_dechet:   nom?.classe || '',
      })
      setResult(res.data)
    } catch {
      toast.error('Erreur lors de la vérification')
    } finally {
      setChecking(false)
    }
  }

  const selectedNom = NOMENCLATURE.find(n => n.code === code)

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
          <Zap size={20} className="text-primary-600" />
        </div>
        <div>
          <h3 className="font-bold text-slate-900 dark:text-white">Vérificateur de droit de collecte</h3>
          <p className="text-xs text-slate-500">Vérifiez si un récupérateur est autorisé à collecter un déchet</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Récupérateur — auto-sélectionné pour un profil récupérateur, sélectionnable sinon */}
        <div>
          <label className="label">Récupérateur</label>
          {isRecup ? (
            <div className="input flex items-center bg-slate-50 dark:bg-[#16240D] text-slate-600 dark:text-slate-300">
              {currentUser?.recuperateur_nom || '—'}
            </div>
          ) : (
            <select value={recupId} onChange={e => { setRecupId(e.target.value); setResult(null) }}
              className="input">
              <option value="">-- Sélectionner --</option>
              {recuperateurs.map(r => (
                <option key={r.id} value={r.id}>
                  {r.nom_raison_sociale} — {r.type_display || r.type_recuperateur}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Code déchet */}
        <div>
          <label className="label">Code déchet</label>
          <div className="relative">
            <input value={codeSearch} onChange={e => { setCodeSearch(e.target.value); setCode(''); setResult(null) }}
              placeholder="Rechercher un code déchet..."
              className="input" />
            {codeSearch && !code && (
              <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-white dark:bg-[#16240D] border border-[#E2E8F0] dark:border-[#2B3D1E] rounded-xl shadow-xl max-h-52 overflow-y-auto">
                {filteredCodes.map(n => (
                  <button key={n.code} type="button"
                    onClick={() => { setCode(n.code); setCodeSearch(`${n.code} — ${n.nom_fr.slice(0,50)}`); setResult(null) }}
                    className="w-full flex items-start gap-2 px-3 py-2.5 hover:bg-slate-50 dark:hover:bg-[#16240D] text-left text-xs">
                    <span className="font-mono font-bold text-primary-700 flex-shrink-0">{n.code}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold flex-shrink-0
                      ${n.classe === 'SD' ? 'bg-red-100 text-red-700' :
                        n.classe === 'S'  ? 'bg-amber-100 text-amber-700' :
                        'bg-slate-100 text-slate-600'}`}>{n.classe}</span>
                    <span className="text-slate-600 truncate">{n.nom_fr}</span>
                  </button>
                ))}
                {filteredCodes.length === 0 && (
                  <p className="text-center py-4 text-slate-400 text-xs">Aucun résultat</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Selected code info */}
      {selectedNom && code && (
        <div className={`flex items-center gap-3 p-3 rounded-xl border
          ${selectedNom.classe === 'SD' ? 'bg-red-50 border-red-200' :
            selectedNom.classe === 'S'  ? 'bg-amber-50 border-amber-200' :
            'bg-green-50 border-green-200'}`}>
          <span className={`px-2.5 py-1 rounded-lg text-xs font-black
            ${selectedNom.classe === 'SD' ? 'bg-red-200 text-red-800' :
              selectedNom.classe === 'S'  ? 'bg-amber-200 text-amber-800' :
              'bg-green-200 text-green-800'}`}>
            {selectedNom.classe}
          </span>
          <div>
            <span className="font-mono font-bold text-sm">{selectedNom.code}</span>
            <span className="mx-2 text-slate-400">—</span>
            <span className="text-sm text-slate-700">{selectedNom.nom_fr}</span>
          </div>
          {(selectedNom.classe === 'S' || selectedNom.classe === 'SD') && (
            <span className="ml-auto text-xs font-bold text-red-600 flex items-center gap-1">
              <AlertTriangle size={12} /> Agrément requis
            </span>
          )}
        </div>
      )}

      <button onClick={handleVerify} disabled={checking || !recupId || !code}
        className="btn-primary w-full justify-center py-2.5">
        {checking
          ? <span className="flex items-center gap-2"><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Vérification...</span>
          : <span className="flex items-center gap-2"><Shield size={16} /> Vérifier le droit de collecte</span>
        }
      </button>

      {/* Result */}
      {result && (
        <div className={`rounded-2xl p-5 border-2 ${
          result.autorise
            ? 'bg-emerald-50 border-emerald-400 dark:bg-emerald-900/20'
            : 'bg-red-50 border-red-500 dark:bg-red-900/20'
        }`}>
          <div className="flex items-center gap-3 mb-3">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center
              ${result.autorise ? 'bg-emerald-100' : 'bg-red-100'}`}>
              {result.autorise
                ? <CheckCircle2 size={24} className="text-emerald-600" />
                : <XCircle     size={24} className="text-red-600" />
              }
            </div>
            <div>
              <p className={`text-lg font-black ${result.autorise ? 'text-emerald-800' : 'text-red-800'}`}>
                {result.autorise ? '✅ Collecte AUTORISÉE' : '🚫 Collecte NON AUTORISÉE'}
              </p>
              {result.alerte && (
                <p className="text-xs font-bold text-red-600 mt-0.5">{result.alerte.titre}</p>
              )}
            </div>
          </div>
          {result.alerte && (
            <div className="bg-white dark:bg-[#16240D] rounded-xl p-4">
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {result.alerte.message}
              </p>
              {result.alerte.action_requise && (
                <div className="mt-3 flex items-center gap-2">
                  <span className="px-3 py-1.5 rounded-xl text-xs font-bold bg-red-600 text-white flex items-center gap-1.5">
                    <ChevronRight size={12} />
                    {result.alerte.action_requise === 'RENOUVELLEMENT_AGREMENT' && 'Renouveler l\'agrément'}
                    {result.alerte.action_requise === 'DEMANDE_AGREMENT'        && 'Soumettre une demande d\'agrément'}
                    {result.alerte.action_requise === 'EXTENSION_AGREMENT'      && 'Demander une extension d\'agrément'}
                  </span>
                  <span className="text-xs text-slate-400">
                    Réf: Décret exécutif n°06-104
                  </span>
                </div>
              )}
              {result.alerte.codes_autorises && (
                <div className="mt-3">
                  <p className="text-xs font-bold text-slate-500 mb-2">Codes autorisés par votre agrément :</p>
                  <div className="flex flex-wrap gap-1">
                    {result.alerte.codes_autorises.slice(0,15).map(c => (
                      <span key={c} className="px-2 py-0.5 rounded bg-primary-50 text-primary-700 border border-primary-200 text-xs font-mono font-bold">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function AlertesPage() {
  const { user: currentUser } = useAuthStore()
  const [alerts,        setAlerts]        = useState([])
  const [recuperateurs, setRecuperateurs] = useState([])
  const [loading,       setLoading]       = useState(true)
  const [search,        setSearch]        = useState('')
  const [severityFilter,setSeverityFilter]= useState('')
  const [typeFilter,    setTypeFilter]    = useState('')
  const [tab,           setTab]           = useState('alertes') // alertes | verifier

  const load = async () => {
    setLoading(true)
    try {
      const [alertRes, recupRes] = await Promise.all([
        alertesAPI.getAll(),
        alertesAPI.getRecups(),
      ])
      const alertData = alertRes.data.alerts || []
      const recupData = recupRes.data.results || recupRes.data
      setAlerts(alertData)
      setRecuperateurs(recupData)
    } catch {
      toast.error('Erreur chargement des alertes')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // Auto refresh every 2 minutes
  useEffect(() => {
    const interval = setInterval(load, 120000)
    return () => clearInterval(interval)
  }, [])

  const filtered = alerts.filter(a => {
    const matchSearch  = !search || a.message.toLowerCase().includes(search.toLowerCase()) ||
      (a.recuperateur || '').toLowerCase().includes(search.toLowerCase())
    const matchSev  = !severityFilter || a.severity === severityFilter
    const matchType = !typeFilter     || a.type     === typeFilter
    return matchSearch && matchSev && matchType
  })

  const critical = alerts.filter(a => a.severity === 'critical').length
  const warning  = alerts.filter(a => a.severity === 'warning').length

  const uniqueTypes = [...new Set(alerts.map(a => a.type))]

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Bell size={24} className="text-red-500" />
            Alertes réglementaires
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Conformité aux agréments — Loi n°01-19 et Décret exécutif n°06-104
          </p>
        </div>
        <button onClick={load} className="btn-secondary btn-sm">
          <RefreshCw size={14} /> Actualiser
        </button>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-3">
        <div className="card p-4 flex items-center gap-3 border-l-4 border-red-500">
          <XCircle size={22} className="text-red-500 flex-shrink-0" />
          <div>
            <p className="text-2xl font-black text-red-600">{critical}</p>
            <p className="text-xs text-slate-500 leading-tight">Alertes critiques</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-3 border-l-4 border-amber-400">
          <AlertTriangle size={22} className="text-amber-500 flex-shrink-0" />
          <div>
            <p className="text-2xl font-black text-amber-600">{warning}</p>
            <p className="text-xs text-slate-500 leading-tight">Avertissements</p>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-3 border-l-4 border-slate-300">
          <Bell size={22} className="text-slate-400 flex-shrink-0" />
          <div>
            <p className="text-2xl font-black text-slate-700">{alerts.length}</p>
            <p className="text-xs text-slate-500 leading-tight">Total alertes</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 dark:bg-[#16240D] rounded-xl p-1 w-fit">
        {[
          { key: 'alertes',  label: `Alertes actives (${alerts.length})`, icon: Bell   },
          { key: 'verifier', label: 'Vérifier un droit',                  icon: Shield },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-all
              ${tab === t.key
                ? 'bg-white dark:bg-[#2B3D1E] text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-700'}`}>
            <t.icon size={14} />{t.label}
          </button>
        ))}
      </div>

      {/* ── TAB ALERTES ───────────────────────────────────────────────── */}
      {tab === 'alertes' && (
        <>
          {/* Filters */}
          <div className="card p-4 flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-48">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Rechercher récupérateur, message..."
                className="input pl-9 text-sm" />
              {search && <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"><X size={13} /></button>}
            </div>
            <select value={severityFilter} onChange={e => setSeverityFilter(e.target.value)} className="input w-44 text-sm">
              <option value="">Toutes sévérités</option>
              <option value="critical">🔴 Critique</option>
              <option value="warning">🟡 Avertissement</option>
              <option value="info">🔵 Information</option>
            </select>
            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className="input w-56 text-sm">
              <option value="">Tous les types</option>
              {uniqueTypes.map(t => (
                <option key={t} value={t}>{TYPE_CFG[t]?.label || t}</option>
              ))}
            </select>
          </div>

          {/* List */}
          {loading ? <Spinner /> : filtered.length === 0 ? (
            <div className="card p-16 text-center">
              <CheckCircle2 size={40} className="mx-auto mb-3 text-emerald-300" />
              <p className="font-bold text-slate-500">Aucune alerte active</p>
              <p className="text-sm text-slate-400 mt-1">
                Tous les récupérateurs sont en conformité réglementaire
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Critical first */}
              {filtered.filter(a => a.severity === 'critical').map(a => (
                <AlertCard key={a.id} alert={a} />
              ))}
              {/* Then warnings */}
              {filtered.filter(a => a.severity === 'warning').map(a => (
                <AlertCard key={a.id} alert={a} />
              ))}
              {/* Then others */}
              {filtered.filter(a => a.severity !== 'critical' && a.severity !== 'warning').map(a => (
                <AlertCard key={a.id} alert={a} />
              ))}
            </div>
          )}
        </>
      )}

      {/* ── TAB VÉRIFIER ──────────────────────────────────────────────── */}
      {tab === 'verifier' && (
        <div className="space-y-4 max-w-3xl">
          <div className="card p-4 bg-primary-50/50 border-primary-200">
            <div className="flex items-start gap-3">
              <Info size={16} className="text-primary-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-primary-800">
                <p className="font-bold mb-1">Comment fonctionne le vérificateur ?</p>
                <ul className="space-y-0.5 text-xs text-primary-700 list-disc list-inside">
                  <li>Les déchets MA et I ne nécessitent pas d'agrément</li>
                  <li>Les déchets S et SD exigent un agrément valide</li>
                  <li>Le code déchet doit figurer dans l'agrément du récupérateur</li>
                  <li>Un agrément expiré ou suspendu invalide tout droit de collecte</li>
                </ul>
              </div>
            </div>
          </div>
          <VerificateurDroit recuperateurs={recuperateurs} currentUser={currentUser} />
        </div>
      )}

    </div>
  )
}
