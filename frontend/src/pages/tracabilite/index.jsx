import { useEffect, useState, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import {
  Package, Plus, Search, X, Save, Edit, Trash2, Eye,
  Truck, Factory, Flame, Recycle, AlertTriangle,
  FileText, Calendar, Shield, CheckCircle2, Clock,
  XCircle, Archive, ChevronRight, Warehouse, Leaf,
  Zap, AlertCircle, GitBranch, Scale
} from 'lucide-react'
import api from '../../api'
import { useAuthStore } from '../../store'
import DateInput from '../../components/common/DateInput'
import toast from 'react-hot-toast'

const opAPI = {
  getAll:  (p)    => api.get('/traceability/', { params: p }),
  create:  (d)    => api.post('/traceability/', d),
  update:  (id,d) => api.patch(`/traceability/${id}/`, d),
  delete:  (id)   => api.delete(`/traceability/${id}/`),
}
const recupAPI  = { getAll: () => api.get('/recuperateurs/?page_size=200&statut=ACTIF') }
const opListAPI = {
  generateurs:   () => api.get('/operateurs/?type_operateur=GENERATEUR&page_size=200'),
  transporteurs: () => api.get('/operateurs/?type_operateur=TRANSPORTEUR&page_size=200'),
  valorisateurs: () => api.get('/operateurs/?type_operateur=VALORISATEUR&page_size=200'),
  eliminateurs:  () => api.get('/operateurs/?type_operateur=ELIMINATEUR&page_size=200'),
  cet:           () => api.get('/operateurs/?type_operateur=CET&page_size=200'),
}

const DESTINATIONS = [
  { key:'STOCKAGE',     label:'Stockage temporaire',         icon:Warehouse,  color:'text-slate-600',  bg:'bg-slate-50'  },
  { key:'VALORISATION', label:'Valorisation / Recyclage',    icon:Recycle,    color:'text-teal-600',   bg:'bg-teal-50'   },
  { key:'ELIMINATION',  label:'Élimination',                 icon:Flame,      color:'text-red-600',    bg:'bg-red-50'    },
  { key:'CET',          label:"Centre d'Enfouissement (CET)",icon:Archive,    color:'text-amber-600',  bg:'bg-amber-50'  },
  { key:'MULTIPLE',     label:'Multi-destinations',          icon:GitBranch,  color:'text-purple-600', bg:'bg-purple-50' },
]

const STATUT_CFG = {
  EN_COURS:   { label:'En cours',      badge:'badge-yellow', icon:Clock        },
  ENLEVEMENT: { label:'Enlèvement',    badge:'badge-yellow', icon:Truck        },
  TRANSPORT:  { label:'Transport',     badge:'badge-yellow', icon:Truck        },
  RECEPTION:  { label:'Réceptionné',   badge:'badge-blue',   icon:Package      },
  TRAITEMENT: { label:'Traitement',    badge:'badge-orange', icon:Zap          },
  TERMINEE:   { label:'Clôturé',       badge:'badge-green',  icon:CheckCircle2 },
  ANNULEE:    { label:'Annulé',        badge:'badge-red',    icon:XCircle      },
}

function Spinner() {
  return <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"/></div>
}

function Modal({ open, onClose, title, children, size='max-w-3xl' }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className={`bg-white dark:bg-[#16240D] rounded-2xl shadow-2xl w-full ${size} max-h-[92vh] flex flex-col`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] dark:border-[#2B3D1E] flex-shrink-0">
          <h3 className="font-bold text-slate-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 p-1"><X size={18}/></button>
        </div>
        <div className="p-6 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}

// ── Repartition Builder ───────────────────────────────────────────────────────
const DEST_OPTIONS = [
  { key:'VALORISATION', label:'Valorisation / Recyclage', icon:Recycle,  color:'text-teal-600',   bg:'bg-teal-50 border-teal-200'   },
  { key:'ELIMINATION',  label:'Élimination',              icon:Flame,    color:'text-red-600',    bg:'bg-red-50 border-red-200'     },
  { key:'CET',          label:"CET (Enfouissement)",      icon:Archive,  color:'text-amber-600',  bg:'bg-amber-50 border-amber-200' },
  { key:'STOCKAGE',     label:'Stockage temporaire',      icon:Warehouse,color:'text-slate-600',  bg:'bg-slate-50 border-slate-200' },
]

function RepartitionBuilder({ quantiteTotale, unite, lists, value, onChange }) {
  const getOps = (type) => {
    if (type === 'VALORISATION') return lists.valorisateurs || []
    if (type === 'ELIMINATION')  return lists.eliminateurs  || []
    if (type === 'CET')          return lists.cet           || []
    return []
  }

  const add = () => onChange([...value, { type:'VALORISATION', quantite:'', operateur:'', operateur_nom:'' }])
  const remove = (i) => onChange(value.filter((_,idx) => idx !== i))
  const update = (i, field, val) => {
    const next = [...value]
    next[i] = { ...next[i], [field]: val }
    if (field === 'type') { next[i].operateur = ''; next[i].operateur_nom = '' }
    if (field === 'operateur') {
      const op = getOps(next[i].type).find(o => String(o.id) === String(val))
      next[i].operateur_nom = op?.raison_sociale || ''
    }
    onChange(next)
  }

  const totalAffecte = value.reduce((s, l) => s + (parseFloat(l.quantite) || 0), 0)
  const qte          = parseFloat(quantiteTotale) || 0
  const restant      = qte - totalAffecte
  const ok           = qte > 0 && Math.abs(restant) < 0.001

  return (
    <div className="space-y-3">
      <div className={`flex items-center gap-3 p-3 rounded-xl border ${ok ? 'bg-emerald-50 border-emerald-200' : restant < 0 ? 'bg-red-50 border-red-300' : 'bg-amber-50 border-amber-200'}`}>
        <Scale size={15} className={ok ? 'text-emerald-600' : restant < 0 ? 'text-red-600' : 'text-amber-600'} />
        <div className="flex-1 text-sm">
          <span className="font-bold">{totalAffecte.toLocaleString('fr-FR',{minimumFractionDigits:0,maximumFractionDigits:3})} {unite}</span>
          <span className="text-slate-400 mx-1">/</span>
          <span className="font-semibold text-slate-600">{qte.toLocaleString('fr-FR',{minimumFractionDigits:0,maximumFractionDigits:3})} {unite} récupérés</span>
          {!ok && restant > 0 && <span className="ml-2 text-amber-700 text-xs font-semibold">— {restant.toLocaleString('fr-FR',{minimumFractionDigits:0,maximumFractionDigits:3})} {unite} non affectés</span>}
          {!ok && restant < 0 && <span className="ml-2 text-red-700 text-xs font-semibold">— Dépassement de {Math.abs(restant).toLocaleString('fr-FR',{minimumFractionDigits:0,maximumFractionDigits:3})} {unite}</span>}
        </div>
        {ok && <CheckCircle2 size={15} className="text-emerald-600 flex-shrink-0"/>}
      </div>

      {value.map((ligne, i) => {
        const cfg = DEST_OPTIONS.find(d => d.key === ligne.type) || DEST_OPTIONS[0]
        const ops = getOps(ligne.type)
        return (
          <div key={i} className={`card p-3 border ${cfg.bg} space-y-2`}>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-400 w-5 text-center">{i+1}</span>
              <select value={ligne.type} onChange={e => update(i,'type',e.target.value)}
                className="input text-xs font-semibold flex-shrink-0 w-52">
                {DEST_OPTIONS.map(d => <option key={d.key} value={d.key}>{d.label}</option>)}
              </select>
              <div className="flex items-center gap-1 flex-shrink-0">
                <input type="number" step="0.001" min="0"
                  value={ligne.quantite}
                  onChange={e => update(i,'quantite',e.target.value)}
                  placeholder="0.000"
                  className="input text-xs w-28 text-right"/>
                <span className="text-xs text-slate-400 flex-shrink-0">{unite}</span>
              </div>
              <button type="button" onClick={() => remove(i)}
                className="btn-ghost p-1.5 text-red-400 hover:text-red-600 ml-auto flex-shrink-0">
                <X size={13}/>
              </button>
            </div>
            {ligne.type !== 'STOCKAGE' ? (
              <div className="pl-7">
                <select value={ligne.operateur} onChange={e => update(i,'operateur',e.target.value)}
                  className="input text-xs w-full">
                  <option value="">-- Sélectionner {cfg.label} --</option>
                  {ops.map(o => <option key={o.id} value={o.id}>{o.raison_sociale}</option>)}
                </select>
              </div>
            ) : (
              <div className="pl-7">
                <input value={ligne.operateur_nom || ''} onChange={e => update(i,'operateur_nom',e.target.value)}
                  placeholder="Lieu de stockage (optionnel)..."
                  className="input text-xs w-full"/>
              </div>
            )}
          </div>
        )
      })}

      <button type="button" onClick={add}
        className="w-full border-2 border-dashed border-slate-300 rounded-xl p-3 text-xs font-semibold text-slate-500 hover:border-primary-400 hover:text-primary-600 hover:bg-primary-50 transition-all flex items-center justify-center gap-2">
        <Plus size={14}/> Ajouter une destination
      </button>
    </div>
  )
}

function TracabiliteForm({ operation, lists, currentUser, onSave, onClose }) {
  const isEdit = !!operation?.id
  const { register, handleSubmit, watch, setValue, reset } = useForm({
    defaultValues: operation || {
      statut: 'EN_COURS', unite: 'KG',
      destination_type: 'VALORISATION',
      date_recuperation: new Date().toISOString().split('T')[0],
      recuperateur: currentUser?.recuperateur_id || '',
    }
  })
  const [saving,        setSaving]        = useState(false)
  const [codeDechet,    setCodeDechet]    = useState(operation?.code_dechet || '')
  const [classe,        setClasse]        = useState(operation?.classe_dechet || '')
  const [typeDechet,    setTypeDechet]    = useState(
    operation?.classe_dechet === 'MA' ? 'MA' :
    ['S','SD'].includes(operation?.classe_dechet) ? 'SD' : ''
  )
  const [sousCategorie, setSousCategorie] = useState('')
  const [sousCategories,setSousCategories]= useState([])
  const [loadingCascade,setLoadingCascade]= useState(false)
  const [designations,     setDesignations]     = useState([])
  const [designationChoisie, setDesignationChoisie] = useState('')
  const [loadingDesignations, setLoadingDesignations] = useState(false)
  const [alertes,       setAlertes]       = useState([])
  const [etape,         setEtape]         = useState(1)

  const initRepartitions = (op) => {
    if (op?.repartitions?.length > 0) return op.repartitions
    if (op?.destination_type && op.destination_type !== 'MULTIPLE') {
      const line = { type: op.destination_type, quantite: op.quantite || '', operateur: '', operateur_nom: '' }
      if (op.destination_type === 'VALORISATION' && op.valorisateur) { line.operateur = op.valorisateur; line.operateur_nom = op.valorisateur_nom || '' }
      if (op.destination_type === 'ELIMINATION'  && op.eliminateur)  { line.operateur = op.eliminateur;  line.operateur_nom = op.eliminateur_nom  || '' }
      if (op.destination_type === 'CET'          && op.cet)          { line.operateur = op.cet;          line.operateur_nom = op.cet_nom          || '' }
      if (op.destination_type === 'STOCKAGE') { line.operateur_nom = op.lieu_stockage_final || '' }
      return [line]
    }
    return []
  }
  const [repartitions, setRepartitions] = useState(() => initRepartitions(operation))

  // 4ème niveau de la cascade : une fois un code réglementaire choisi, charge
  // les désignations précises disponibles pour ce code (ex: code 15.01.02
  // "Emballages plastiques" -> "Bouteille d'eau PET", "Flacon PEHD"...).
  useEffect(() => {
    if (!codeDechet) { setDesignations([]); setDesignationChoisie(''); return }
    setLoadingDesignations(true)
    api.get('/nomenclature/designations/', { params: { code: codeDechet } })
      .then(r => setDesignations(r.data || []))
      .catch(() => setDesignations([]))
      .finally(() => setLoadingDesignations(false))
  }, [codeDechet])

  // Charge, pour le récupérateur connecté, la liste des sous-catégories +
  // détails + codes nomenclature qui lui ont été assignés (Django Admin)
  // pour le type choisi (MA ou SD). Chaque récupérateur peut avoir un mapping
  // différent — voir endpoint /api/recuperateurs/mes-types-dechets/.
  useEffect(() => {
    if (!typeDechet) { setSousCategories([]); return }
    setLoadingCascade(true)
    api.get('/recuperateurs/mes-types-dechets/', { params: { type: typeDechet } })
      .then(r => setSousCategories(r.data.sous_categories || []))
      .catch(() => setSousCategories([]))
      .finally(() => setLoadingCascade(false))
  }, [typeDechet])

  const sousCategorieObj = sousCategories.find(sc => String(sc.id) === sousCategorie)
  // Codes nomenclature UNIQUES de la sous-catégorie choisie (un seul par code,
  // même si plusieurs détails — PET, PEHD, PP, Films... — y sont rattachés ;
  // ces détails apparaîtront ensuite dans le 4ème dropdown "Désignation précise").
  const codesDisponibles = useMemo(() => {
    if (!sousCategorieObj) return []
    const seen = new Map()
    sousCategorieObj.details.forEach(d => {
      d.codes.forEach(c => {
        if (!seen.has(c.code)) seen.set(c.code, c)
      })
    })
    return Array.from(seen.values()).sort((a, b) => a.code.localeCompare(b.code))
  }, [sousCategorieObj])

  const isRecup    = currentUser?.role === 'RECUPERATEUR'
  const destination = watch('destination_type')
  const recupId    = isRecup ? currentUser?.recuperateur_id : watch('recuperateur')
  const needsAgrmt = ['S','SD'].includes(classe)

  useEffect(() => {
    if (!recupId || !codeDechet || !classe) { setAlertes([]); return }
    api.post('/operateurs/verifier_compatibilite/', {
      recuperateur_id: recupId, operateur_id: 0,
      code_dechet: codeDechet, classe_dechet: classe
    }).then(r => setAlertes(r.data.compatible ? [] : (r.data.alertes || [])))
      .catch(() => {})
  }, [recupId, codeDechet, classe])

  useEffect(() => { if (operation) reset(operation) }, [operation])

  // Prix d'achat total = prix unitaire × quantité récupérée (calcul automatique).
  const quantiteWatch = watch('quantite')
  const prixUnitaireWatch = watch('prix_unitaire_ttc')
  useEffect(() => {
    const q = parseFloat(quantiteWatch)
    const pu = parseFloat(prixUnitaireWatch)
    if (!isNaN(q) && !isNaN(pu)) setValue('prix_achat_ttc', (q * pu).toFixed(2))
    else if (!prixUnitaireWatch) setValue('prix_achat_ttc', '')
  }, [quantiteWatch, prixUnitaireWatch])

  // Prix de revient global = prix d'achat total + frais de transport + autres frais.
  // Prix de revient unitaire = prix de revient global / quantité récupérée.
  const prixAchatWatch      = watch('prix_achat_ttc')
  const fraisTransportWatch = watch('frais_transport_ttc')
  const autresFraisWatch    = watch('autres_frais_ttc')
  useEffect(() => {
    const achat    = parseFloat(prixAchatWatch) || 0
    const transport= parseFloat(fraisTransportWatch) || 0
    const autres   = parseFloat(autresFraisWatch) || 0
    const q        = parseFloat(quantiteWatch)
    if (!prixAchatWatch && !fraisTransportWatch && !autresFraisWatch) {
      setValue('prix_revient_global_ttc', '')
      setValue('prix_revient_unitaire_ttc', '')
      return
    }
    const global_ = achat + transport + autres
    setValue('prix_revient_global_ttc', global_.toFixed(2))
    setValue('prix_revient_unitaire_ttc', (!isNaN(q) && q > 0) ? (global_ / q).toFixed(2) : '')
  }, [prixAchatWatch, fraisTransportWatch, autresFraisWatch, quantiteWatch])

  const onSubmit = async (data) => {
    setSaving(true)
    if (isRecup && currentUser?.recuperateur_id) data.recuperateur = currentUser.recuperateur_id
    data.code_dechet   = codeDechet
    data.classe_dechet = classe

    // Répartitions multi-destinations
    if (repartitions.length > 0) {
      data.repartitions    = repartitions
      data.destination_type = repartitions.length === 1 ? repartitions[0].type : 'MULTIPLE'
      // Setter les FK pour compatibilité avec les vues existantes
      const valo = repartitions.find(r => r.type === 'VALORISATION')
      const elim = repartitions.find(r => r.type === 'ELIMINATION')
      const cet  = repartitions.find(r => r.type === 'CET')
      data.valorisateur = valo?.operateur || null
      data.eliminateur  = elim?.operateur || null
      data.cet          = cet?.operateur  || null
      data.quantite_enfouie = cet?.quantite || null
    } else {
      data.repartitions = []
    }

    if (!data.date_livraison)   delete data.date_livraison
    if (!data.date_commande)    delete data.date_commande
    if (!data.quantite_enfouie && !data.quantite_enfouie !== 0) delete data.quantite_enfouie
    if (!data.prix_unitaire_ttc && data.prix_unitaire_ttc !== 0) delete data.prix_unitaire_ttc
    if (!data.prix_achat_ttc && data.prix_achat_ttc !== 0) delete data.prix_achat_ttc
    if (!data.frais_transport_ttc && data.frais_transport_ttc !== 0) delete data.frais_transport_ttc
    if (!data.autres_frais_ttc && data.autres_frais_ttc !== 0) delete data.autres_frais_ttc
    if (!data.prix_revient_global_ttc && data.prix_revient_global_ttc !== 0) delete data.prix_revient_global_ttc
    if (!data.prix_revient_unitaire_ttc && data.prix_revient_unitaire_ttc !== 0) delete data.prix_revient_unitaire_ttc
    try {
      if (isEdit) { await opAPI.update(operation.id, data); toast.success('Dossier mis à jour') }
      else        { await opAPI.create(data);                toast.success('Dossier de traçabilité créé') }
      onSave()
    } catch (e) { console.error('Erreur traçabilité:', e.response?.data); toast.error('Erreur') }
    finally { setSaving(false) }
  }

  const F = ({ label, req, children, col }) => (
    <div className={col||''}>
      <label className="label">{label}{req && <span className="text-red-500 ml-0.5">*</span>}</label>
      {children}
    </div>
  )

  const steps = [
    {n:1, label:'Générateur & Déchet'},
    {n:2, label:'Enlèvement & Transport'},
    {n:3, label:'Destination finale'},
    {n:4, label:'Statut & Clôture'},
  ]

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      {/* Step progress */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {steps.map((s,i) => (
          <div key={s.n} className="flex items-center gap-1 flex-shrink-0">
            <button type="button" onClick={() => setEtape(s.n)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
                ${etape===s.n?'bg-primary-600 text-white':etape>s.n?'bg-emerald-100 text-emerald-700':'bg-slate-100 text-slate-500'}`}>
              {etape>s.n?<CheckCircle2 size={11}/>:<span>{s.n}</span>}
              {s.label}
            </button>
            {i<3&&<ChevronRight size={12} className="text-slate-300 flex-shrink-0"/>}
          </div>
        ))}
      </div>

      {alertes.map((a,i) => (
        <div key={i} className="flex items-start gap-3 p-4 rounded-xl bg-red-50 border border-red-300">
          <AlertTriangle size={16} className="text-red-500 flex-shrink-0 mt-0.5"/>
          <p className="text-sm text-red-700">{a.message}</p>
        </div>
      ))}

      {/* ETAPE 1 */}
      {etape===1 && (
        <div className="space-y-4">
          {isRecup ? (
            <div className="card p-3 bg-primary-50 border-primary-200 flex items-center gap-2">
              <Shield size={14} className="text-primary-600 flex-shrink-0"/>
              <div>
                <p className="text-xs text-primary-500">Récupérateur (vous)</p>
                <p className="font-semibold text-primary-800 text-sm">{currentUser?.recuperateur_nom}</p>
              </div>
            </div>
          ) : (
            <F label="Récupérateur" req>
              <select {...register('recuperateur',{required:!isRecup})} className="input">
                <option value="">-- Sélectionner --</option>
                {lists.recuperateurs.map(r=><option key={r.id} value={r.id}>{r.nom_raison_sociale} ({r.numero_id})</option>)}
              </select>
            </F>
          )}

          <div className="card p-4 space-y-3">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1"><Factory size={11}/> 1. Identification du générateur</p>
            <F label="Générateur des déchets" req>
              <select {...register('generateur',{required:true})} className="input">
                <option value="">-- Sélectionner un générateur enregistré --</option>
                {lists.generateurs.map(g=><option key={g.id} value={g.id}>{g.raison_sociale} — W.{g.wilaya||'?'}</option>)}
              </select>
            </F>
            <div className="grid grid-cols-2 gap-3">
              <F label="Bon de livraison" col=""><input {...register('bon_livraison')} className="input" placeholder="BL-..."/></F>
              <F label="Date livraison" col=""><DateInput value={watch('date_livraison')||''} onChange={v=>setValue('date_livraison',v)}/></F>
              <F label="Bon de commande n°" col=""><input {...register('bon_commande')} className="input" placeholder="BC-..."/></F>
              <F label="Date commande" col=""><DateInput value={watch('date_commande')||''} onChange={v=>setValue('date_commande',v)}/></F>
            </div>
            <F label="Commande client"><input {...register('commande_client')} className="input" placeholder="Référence..."/></F>
          </div>

          <div className="card p-4 space-y-3">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1"><Package size={11}/> Identification du déchet</p>
            <F label="Type de déchets" req>
              <select value={typeDechet} className="input"
                onChange={e => {
                  setTypeDechet(e.target.value)
                  // Reset toute la cascade car la liste proposée change
                  setSousCategorie('')
                  setCodeDechet('')
                  setClasse('')
                  setDesignationChoisie('')
                  setValue('designation_dechet', '')
                  setValue('classe_dechet', '')
                }}>
                <option value="">-- Sélectionner un type --</option>
                <option value="MA">Déchets ménagers et assimilés</option>
                <option value="SD">Déchets spéciaux et spéciaux dangereux</option>
              </select>
            </F>

            {typeDechet === 'MA' && (
              <>
                <F label="Catégorie de déchet" req>
                  {loadingCascade ? (
                    <p className="text-xs text-slate-400 py-2">Chargement...</p>
                  ) : sousCategories.length === 0 ? (
                    <p className="text-xs text-amber-600 py-2">
                      Aucune catégorie ne vous a été assignée pour ce type. Contactez l'administrateur.
                    </p>
                  ) : (
                    <select value={sousCategorie} className="input"
                      onChange={e => {
                        setSousCategorie(e.target.value)
                        setCodeDechet('')
                        setClasse('')
                        setDesignationChoisie('')
                        setValue('designation_dechet', '')
                        setValue('classe_dechet', '')
                      }}>
                      <option value="">-- Sélectionner une catégorie --</option>
                      {sousCategories.map(sc => (
                        <option key={sc.id} value={sc.id}>{sc.nom}</option>
                      ))}
                    </select>
                  )}
                </F>

                {sousCategorie && (
                  <F label="Code réglementaire du déchet" req>
                    <select
                      value={codeDechet}
                      className="input"
                      onChange={e => {
                        const code = e.target.value
                        const c = codesDisponibles.find(x => x.code === code)
                        setDesignationChoisie('')
                        if (c) {
                          setCodeDechet(c.code)
                          setClasse(c.classe)
                          setValue('designation_dechet', c.designation_fr)
                          setValue('classe_dechet', c.classe)
                        } else {
                          setCodeDechet('')
                          setClasse('')
                          setValue('designation_dechet', '')
                          setValue('classe_dechet', '')
                        }
                      }}>
                      <option value="">-- Sélectionner un code déchet --</option>
                      {codesDisponibles.map(c => (
                        <option key={c.code} value={c.code}>
                          {c.code} — {c.designation_fr}
                        </option>
                      ))}
                    </select>
                    <input type="hidden" {...register('designation_dechet')}/>
                    <input type="hidden" {...register('classe_dechet')}/>
                  </F>
                )}

                {codeDechet && (
                  <F label="Désignation précise">
                    {loadingDesignations ? (
                      <p className="text-xs text-slate-400 py-2">Chargement...</p>
                    ) : designations.length === 0 ? (
                  <p className="text-xs text-slate-400 py-2">
                    Aucune désignation précise disponible pour ce code.
                  </p>
                ) : (
                  <select value={designationChoisie} className="input"
                    onChange={e => {
                      const id = e.target.value
                      setDesignationChoisie(id)
                      const d = designations.find(x => String(x.id) === id)
                      if (d) {
                        setValue('designation_dechet', d.designation)
                        setValue('id_recup_dz', d.id_recup_dz)
                      } else {
                        setValue('id_recup_dz', '')
                      }
                    }}>
                    <option value="">-- Sélectionner une désignation --</option>
                    {designations.map(d => (
                      <option key={d.id} value={d.id}>{d.designation}</option>
                    ))}
                  </select>
                )}
                <input type="hidden" {...register('id_recup_dz')}/>
              </F>
            )}

                {codeDechet === '15.01.02' && (
                  <div className="grid grid-cols-2 gap-3">
                    <F label="Couleur" col="">
                      <select {...register('couleur')} className="input">
                        <option value="">-- Sélectionner --</option>
                        <option value="TRANSPARENT">Transparent</option>
                        <option value="BLANC">Blanc</option>
                        <option value="NOIR">Noir</option>
                        <option value="BLEU">Bleu</option>
                        <option value="VERT">Vert</option>
                        <option value="ROUGE">Rouge</option>
                        <option value="JAUNE">Jaune</option>
                        <option value="GRIS">Gris</option>
                        <option value="MARRON">Marron</option>
                        <option value="MULTICOLORE">Multicolore</option>
                      </select>
                    </F>
                    <F label="Niveau de propreté" col="">
                      <select {...register('niveau_proprete')} className="input">
                        <option value="">-- Sélectionner --</option>
                        <option value="TRES_PROPRE">Très propre</option>
                        <option value="PROPRE">Propre</option>
                        <option value="MOYENNEMENT_PROPRE">Moyennement propre</option>
                        <option value="SALE">Sale</option>
                        <option value="TRES_SALE">Très sale</option>
                      </select>
                    </F>
                  </div>
                )}
              </>
            )}

            {typeDechet === 'SD' && (
              <div className="rounded-xl border-2 border-red-300 bg-red-50/60 dark:bg-red-900/10 p-4 space-y-3">
                <p className="text-xs font-bold text-red-700 uppercase tracking-wide flex items-center gap-1.5">
                  <AlertTriangle size={13}/> Déchets spéciaux et spéciaux dangereux — Codes autorisés par l'agrément
                </p>
                <p className="text-xs text-red-600/80">
                  Seuls les codes couverts par l'agrément de {currentUser?.recuperateur_nom || 'votre entreprise'} sont affichés ci-dessous.
                </p>

                <F label="Catégorie de déchet (selon agrément)" req>
                  {loadingCascade ? (
                    <p className="text-xs text-slate-400 py-2">Chargement...</p>
                  ) : sousCategories.length === 0 ? (
                    <p className="text-xs text-amber-600 py-2">
                      Aucune catégorie de déchets spéciaux ne vous a été assignée. Contactez l'administrateur.
                    </p>
                  ) : (
                    <select value={sousCategorie} className="input"
                      onChange={e => {
                        setSousCategorie(e.target.value)
                        setCodeDechet('')
                        setClasse('')
                        setDesignationChoisie('')
                        setValue('designation_dechet', '')
                        setValue('classe_dechet', '')
                      }}>
                      <option value="">-- Sélectionner une catégorie --</option>
                      {sousCategories.map(sc => (
                        <option key={sc.id} value={sc.id}>{sc.nom}</option>
                      ))}
                    </select>
                  )}
                </F>

                {sousCategorie && (
                  <F label="Code réglementaire autorisé" req>
                    <select
                      value={codeDechet}
                      className="input"
                      onChange={e => {
                        const code = e.target.value
                        const c = codesDisponibles.find(x => x.code === code)
                        setDesignationChoisie('')
                        if (c) {
                          setCodeDechet(c.code)
                          setClasse(c.classe)
                          setValue('designation_dechet', c.designation_fr)
                          setValue('classe_dechet', c.classe)
                        } else {
                          setCodeDechet('')
                          setClasse('')
                          setValue('designation_dechet', '')
                          setValue('classe_dechet', '')
                        }
                      }}>
                      <option value="">-- Sélectionner un code déchet --</option>
                      {codesDisponibles.map(c => (
                        <option key={c.code} value={c.code}>
                          {c.code} — {c.designation_fr} ({c.classe})
                        </option>
                      ))}
                    </select>
                    <input type="hidden" {...register('designation_dechet')}/>
                    <input type="hidden" {...register('classe_dechet')}/>
                  </F>
                )}
              </div>
            )}
            {classe&&(
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${classe==='SD'?'bg-red-50 text-red-700 border-red-200':classe==='S'?'bg-amber-50 text-amber-700 border-amber-200':'bg-slate-50 text-slate-600 border-slate-200'}`}>Classe {classe}</span>
                {needsAgrmt&&<span className="text-xs text-red-600 font-bold flex items-center gap-1"><AlertCircle size={12}/>Déchet spécial — agrément obligatoire</span>}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <F label="Désignation AR" col=""><input {...register('designation_ar')} className="input" placeholder="تسمية النفاية..."/></F>
              <F label="État physique" col="">
                <select {...register('etat_physique')} className="input">
                  <option value="">--</option>
                  <option value="SOLIDE">Solide</option>
                  <option value="LIQUIDE">Liquide</option>
                  <option value="BOUEUX">Boueux / Pâteux</option>
                  <option value="GAZEUX">Gazeux</option>
                </select>
              </F>
              <F label="Quantité estimée" req col=""><input {...register('quantite',{required:true})} type="number" step="0.001" className="input" placeholder="0.000"/></F>
              <F label="Unité" req col="">
                <select {...register('unite',{required:true})} className="input">
                  <option value="KG">Kilogramme (kg)</option>
                  <option value="TONNE">Tonne (t)</option>
                  <option value="M3">Mètre cube (m3)</option>
                  <option value="LITRE">Litre (L)</option>
                  <option value="UNITE">Unité</option>
                </select>
              </F>
              <F label="Conditionnement" col="">
                <select {...register('conditionnement')} className="input">
                  <option value="">--</option>
                  {['Fût','Sac','Benne','Citerne','Big bag','Conteneur','Autre'].map(c=><option key={c}>{c}</option>)}
                </select>
              </F>
              <F label="Lieu de stockage" col=""><input {...register('lieu_stockage')} className="input" placeholder="Dépôt, aire..."/></F>
            </div>
            <F label="Caractéristiques de danger"><input {...register('caracteristiques_danger')} className="input" placeholder="H3 Inflammable, H6 Toxique..."/></F>
            <F label="Date de récupération" req><DateInput value={watch('date_recuperation')||''} onChange={v=>setValue('date_recuperation',v)}/></F>
            <div className="grid grid-cols-2 gap-3">
              <F label="Prix unitaire (TTC, DZD)" col=""><input {...register('prix_unitaire_ttc')} type="number" step="0.01" className="input" placeholder="0.00"/></F>
              <F label="Prix d'achat total (TTC, DZD)" col="">
                <input {...register('prix_achat_ttc')} type="number" step="0.01" className="input bg-slate-50 dark:bg-[#16240D]" placeholder="0.00" readOnly/>
              </F>
            </div>
          </div>
          <div className="flex justify-end"><button type="button" onClick={()=>setEtape(2)} className="btn-primary">Étape suivante <ChevronRight size={15}/></button></div>
        </div>
      )}

      {/* ETAPE 2 */}
      {etape===2 && (
        <div className="space-y-4">
          <div className="card p-4 space-y-3">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1"><Package size={11}/> 2. Préparation de l'enlèvement</p>
            <div className="grid grid-cols-2 gap-3">
              <F label="N° Ordre d'enlèvement" col=""><input {...register('ordre_enlevement')} className="input" placeholder="OE-2026-..."/></F>
              <F label="Date prévue de collecte" col=""><DateInput value={watch('date_collecte_prevue')||''} onChange={v=>setValue('date_collecte_prevue',v)}/></F>
              <F label="Date et heure d'enlèvement" col=""><DateInput value={watch('date_enlevement')||''} onChange={v=>setValue('date_enlevement',v)}/></F>
              <F label="Quantité réellement chargée" col=""><input {...register('quantite_chargee')} type="number" step="0.001" className="input"/></F>
              <F label="Adresse exacte d'enlèvement" col=""><input {...register('adresse_enlevement')} className="input" placeholder="Lieu de stockage..."/></F>
              <F label="N° Véhicule" col=""><input {...register('immatriculation')} className="input" placeholder="16-XXXXX-16"/></F>
            </div>
          </div>

          <div className="card p-4 space-y-3">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1">
              <Truck size={11}/> 3. Transporteur
              {needsAgrmt&&<span className="text-red-500 ml-1 text-[10px] font-bold">(Agrément obligatoire — déchets SD/S)</span>}
            </p>
            <F label="Transporteur">
              <select {...register('transporteur')} className="input"
                onChange={e=>{setValue('transporteur',e.target.value);const t=lists.transporteurs.find(x=>String(x.id)===e.target.value);if(t){if(t.nom_conducteur)setValue('chauffeur',t.nom_conducteur);if(t.immatriculation)setValue('immatriculation',t.immatriculation)}}}>
                <option value="">-- Sélectionner ou saisir manuellement --</option>
                {lists.transporteurs.map(t=><option key={t.id} value={t.id}>{t.raison_sociale}</option>)}
              </select>
            </F>
            {needsAgrmt&&(
              <div className="card p-3 bg-amber-50 border-amber-200 space-y-2">
                <p className="text-xs font-bold text-amber-700 flex items-center gap-1"><AlertTriangle size={11}/>Informations d'agrément transporteur requises</p>
                <div className="grid grid-cols-2 gap-2">
                  <F label="N° Agrément" col=""><input {...register('transporteur_agrement')} className="input text-xs" placeholder="AGR-..."/></F>
                  <F label="Date agrément" col=""><DateInput value={watch('transporteur_date_agrement')||''} onChange={v=>setValue('transporteur_date_agrement',v)}/></F>
                  <F label="Statut" col=""><select {...register('transporteur_statut_agrement')} className="input text-xs"><option value="ACTIF">Actif</option><option value="EXPIRE">Expiré</option></select></F>
                  <F label="Type engin" col=""><input {...register('type_engin')} className="input text-xs" placeholder="Camion citerne..."/></F>
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <F label="Chauffeur" col=""><input {...register('chauffeur')} className="input" placeholder="Nom du chauffeur"/></F>
              <F label="Immatriculation" col=""><input {...register('immatriculation')} className="input" placeholder="16-XXXXX-16"/></F>
              <F label="Date et heure de départ" col=""><DateInput value={watch('date_depart')||''} onChange={v=>setValue('date_depart',v)}/></F>
              <F label="Lieu de départ" col=""><input {...register('lieu_depart')} className="input" placeholder="Adresse de départ..."/></F>
              <F label="Itinéraire prévu" col=""><input {...register('itineraire')} className="input" placeholder="Route prévue..."/></F>
              <F label="Incidents éventuels" col="">
                <select {...register('incident')} className="input">
                  <option value="">Aucun incident</option>
                  <option value="ACCIDENT">Accident</option>
                  <option value="FUITE">Fuite</option>
                  <option value="PERTE">Perte de chargement</option>
                  <option value="RETARD">Retard important</option>
                </select>
              </F>
              <F label="Frais de transport (TTC, DZD)" col=""><input {...register('frais_transport_ttc')} type="number" step="0.01" className="input" placeholder="0.00"/></F>
              <F label="Autres frais (TTC, DZD)" col=""><input {...register('autres_frais_ttc')} type="number" step="0.01" className="input" placeholder="0.00"/></F>
            </div>
          </div>
          <div className="flex justify-between">
            <button type="button" onClick={()=>setEtape(1)} className="btn-secondary">Retour</button>
            <button type="button" onClick={()=>setEtape(3)} className="btn-primary">Étape suivante <ChevronRight size={15}/></button>
          </div>
        </div>
      )}

      {/* ETAPE 3 */}
      {etape===3 && (
        <div className="space-y-4">
          <div className="card p-4 space-y-3">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1"><Package size={11}/> 4. Réception chez le destinataire</p>
            <div className="grid grid-cols-2 gap-3">
              <F label="N° BSD" col=""><input {...register('bsd_numero')} className="input" placeholder="BSD-2026-..."/></F>
              <F label="Date d'arrivée" col=""><DateInput value={watch('date_reception')||''} onChange={v=>setValue('date_reception',v)}/></F>
              <F label="Quantité acceptée" col=""><input {...register('quantite_acceptee')} type="number" step="0.001" className="input"/></F>
              <F label="Quantité refusée" col=""><input {...register('quantite_refusee')} type="number" step="0.001" className="input"/></F>
              <F label="Motif de refus" col="col-span-2"><input {...register('motif_refus')} className="input" placeholder="Motif (si applicable)..."/></F>
            </div>
          </div>

          <div className="card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                <GitBranch size={11}/> 5. Répartition de la quantité récupérée
              </p>
              <span className="text-xs text-slate-400">
                Total récupéré : <strong>{watch('quantite')||0} {watch('unite')||'KG'}</strong>
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Distribuez la quantité récupérée sur une ou plusieurs destinations. La somme des quantités affectées doit correspondre à la quantité totale récupérée.
            </p>
            <RepartitionBuilder
              quantiteTotale={watch('quantite')}
              unite={watch('unite')||'KG'}
              lists={lists}
              value={repartitions}
              onChange={setRepartitions}
            />
          </div>
          <div className="flex justify-between">
            <button type="button" onClick={()=>setEtape(2)} className="btn-secondary">Retour</button>
            <button type="button" onClick={()=>setEtape(4)} className="btn-primary">Étape suivante <ChevronRight size={15}/></button>
          </div>
        </div>
      )}

      {/* ETAPE 4 */}
      {etape===4 && (
        <div className="space-y-4">
          <div className="card p-4 space-y-3">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide flex items-center gap-1"><CheckCircle2 size={11}/> 6. Statut et clôture du dossier</p>
            <div className="grid grid-cols-2 gap-3">
              <F label="Prix de revient global (TTC, DZD)" col="">
                <input {...register('prix_revient_global_ttc')} type="number" step="0.01" className="input bg-slate-50 dark:bg-[#16240D]" placeholder="0.00" readOnly/>
              </F>
              <F label="Prix de revient unitaire (TTC, DZD)" col="">
                <input {...register('prix_revient_unitaire_ttc')} type="number" step="0.01" className="input bg-slate-50 dark:bg-[#16240D]" placeholder="0.00" readOnly/>
              </F>
            </div>
            <F label="Statut du dossier">
              <select {...register('statut')} className="input">
                <option value="EN_COURS">En cours</option>
                <option value="ENLEVEMENT">En cours d'enlèvement</option>
                <option value="TRANSPORT">En transport</option>
                <option value="RECEPTION">Réceptionné</option>
                <option value="TRAITEMENT">En traitement</option>
                <option value="TERMINEE">Terminée / Clôturée</option>
                <option value="ANNULEE">Annulé</option>
              </select>
            </F>
            <div className="card p-3 bg-primary-50 border-primary-200">
              <p className="text-xs font-bold text-primary-700 mb-2 flex items-center gap-1"><FileText size={11}/>Documents générés automatiquement à la clôture</p>
              {['BSD clôturé','Certificat de valorisation ou d\'élimination','Historique complet du déchet','Registre de collecte','Rapport de mouvement du déchet'].map(d=>(
                <p key={d} className="text-xs text-primary-600 flex items-center gap-1"><CheckCircle2 size={9}/>{d}</p>
              ))}
            </div>
            <F label="Observations générales"><textarea {...register('observations')} className="input" rows={3} placeholder="Notes, observations..."/></F>
          </div>
          <div className="flex gap-3 pt-2 border-t border-[#E2E8F0]">
            <button type="button" onClick={()=>setEtape(3)} className="btn-secondary">Retour</button>
            <button type="submit" disabled={saving||alertes.length>0} className="btn-primary">
              <Save size={15}/> {saving?'Enregistrement...':isEdit?'Mettre à jour':'Créer le dossier de traçabilité'}
            </button>
            {alertes.length>0&&<span className="text-xs text-red-600 self-center font-semibold flex items-center gap-1"><AlertTriangle size={11}/>Corrigez les alertes</span>}
          </div>
        </div>
      )}
    </form>
  )
}

function OperationCard({ op, onEdit, onDelete, onView }) {
  const st  = STATUT_CFG[op.statut] || STATUT_CFG.EN_COURS
  const dst = DESTINATIONS.find(d=>d.key===op.destination_type) || DESTINATIONS[1]
  const Icon= st.icon
  return (
    <div className="card p-4 hover:shadow-lg transition-all cursor-pointer" onClick={()=>onView(op)}>
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-xl bg-primary-50 flex items-center justify-center flex-shrink-0">
          <Package size={20} className="text-primary-600"/>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-bold text-primary-700 text-sm">{op.numero}</span>
            <span className={`badge ${st.badge} text-[10px]`}><Icon size={9} className="mr-0.5"/>{st.label}</span>
            {op.classe_dechet&&<span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${op.classe_dechet==='SD'?'bg-red-50 text-red-700 border-red-200':op.classe_dechet==='S'?'bg-amber-50 text-amber-700 border-amber-200':'bg-slate-50 text-slate-600 border-slate-200'}`}>Cl.{op.classe_dechet}</span>}
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${dst.bg} ${dst.color}`}><dst.icon size={9} className="inline mr-0.5"/>{dst.label}</span>
          </div>
          <p className="text-sm font-semibold text-slate-800 dark:text-white mt-1">
            <span className="font-mono text-xs text-slate-400 mr-2">{op.code_dechet}</span>
            {op.designation_dechet?.slice(0,60)}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1 text-xs text-slate-400">
            <span className="font-bold text-slate-700 dark:text-slate-200">{op.quantite} {op.unite_display||op.unite}</span>
            {op.generateur_nom&&<span className="flex items-center gap-1"><Factory size={10}/>{op.generateur_nom}</span>}
            {op.transporteur_nom&&<span className="flex items-center gap-1"><Truck size={10}/>{op.transporteur_nom}</span>}
            <span className="flex items-center gap-1"><Calendar size={10}/>{op.date_recuperation}</span>
          </div>
          {op.repartitions?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {op.repartitions.map((r,i) => {
                const d = DEST_OPTIONS.find(x => x.key === r.type) || DEST_OPTIONS[0]
                return (
                  <span key={i} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${d.bg}`}>
                    <d.icon size={9} className={d.color}/>
                    <span className={d.color}>{parseFloat(r.quantite).toLocaleString('fr-FR',{maximumFractionDigits:1})} {op.unite_display||op.unite}</span>
                    {r.operateur_nom && <span className="text-slate-500">· {r.operateur_nom.slice(0,20)}</span>}
                  </span>
                )
              })}
            </div>
          )}
        </div>
        <div className="flex gap-1 flex-shrink-0" onClick={e=>e.stopPropagation()}>
          <button onClick={()=>onView(op)} className="btn-ghost p-2 text-slate-400 hover:text-primary-600"><Eye size={14}/></button>
          <button onClick={()=>onEdit(op)} className="btn-ghost p-2 text-slate-400 hover:text-primary-600"><Edit size={14}/></button>
          <button onClick={()=>onDelete(op.id)} className="btn-ghost p-2 text-slate-400 hover:text-red-600"><Trash2 size={14}/></button>
        </div>
      </div>
    </div>
  )
}

export default function TracabilitePage() {
  const { user } = useAuthStore()
  const [operations, setOperations] = useState([])
  const [loading,    setLoading]    = useState(true)
  const [showForm,   setShowForm]   = useState(false)
  const [editing,    setEditing]    = useState(null)
  const [viewing,    setViewing]    = useState(null)
  const [search,     setSearch]     = useState('')
  const [statut,     setStatut]     = useState('')
  const [lists,      setLists]      = useState({recuperateurs:[],generateurs:[],transporteurs:[],valorisateurs:[],eliminateurs:[],cet:[]})

  const isRecup = user?.role === 'RECUPERATEUR'

  const loadLists = async () => {
    try {
      const [r,g,t,v,e,c] = await Promise.all([recupAPI.getAll(),opListAPI.generateurs(),opListAPI.transporteurs(),opListAPI.valorisateurs(),opListAPI.eliminateurs(),opListAPI.cet()])
      setLists({recuperateurs:r.data.results||r.data,generateurs:g.data.results||g.data,transporteurs:t.data.results||t.data,valorisateurs:v.data.results||v.data,eliminateurs:e.data.results||e.data,cet:c.data.results||c.data})
    } catch {}
  }

  const load = async () => {
    setLoading(true)
    try {
      const p={page_size:100}
      if(search)p.search=search
      if(statut)p.statut=statut
      if(isRecup&&user?.recuperateur_id)p.recuperateur=user.recuperateur_id
      const res=await opAPI.getAll(p)
      setOperations(res.data.results||res.data)
    } catch{toast.error('Erreur de chargement')}
    finally{setLoading(false)}
  }

  useEffect(()=>{loadLists()},[])
  useEffect(()=>{load()},[search,statut])

  const handleDelete=async(id)=>{if(!window.confirm('Supprimer ce dossier ?'))return;try{await opAPI.delete(id);toast.success('Supprimé');load()}catch{toast.error('Erreur')}}
  const handleSave=()=>{setShowForm(false);setEditing(null);load()}
  const handleEdit=(op)=>{setEditing(op);setViewing(null);setShowForm(true)}

  const stats={
    total:operations.length,
    enCours:operations.filter(o=>['EN_COURS','ENLEVEMENT','TRANSPORT','RECEPTION','TRAITEMENT'].includes(o.statut)).length,
    termines:operations.filter(o=>o.statut==='TERMINEE').length,
    alerte:operations.filter(o=>['S','SD'].includes(o.classe_dechet)).length,
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Package size={24} className="text-primary-600"/> Traçabilité des Déchets
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Suivi complet : enlèvement → transport → destination finale → clôture</p>
          {isRecup&&user?.recuperateur_nom&&(
            <p className="text-primary-600 text-sm font-semibold mt-0.5 flex items-center gap-1"><Shield size={13}/>{user.recuperateur_nom}</p>
          )}
        </div>
        <button onClick={()=>{setEditing(null);setShowForm(true)}} className="btn-primary"><Plus size={16}/>Nouveau dossier</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {label:'Total dossiers',value:stats.total,    color:'bg-primary-500',icon:Package      },
          {label:'En cours',      value:stats.enCours,  color:'bg-amber-500',  icon:Clock        },
          {label:'Terminés',      value:stats.termines, color:'bg-emerald-500',icon:CheckCircle2 },
          {label:'Déchets SD/S',  value:stats.alerte,   color:'bg-red-500',    icon:AlertTriangle},
        ].map(k=>(
          <div key={k.label} className="card p-4 flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${k.color} flex items-center justify-center flex-shrink-0`}><k.icon size={18} className="text-white"/></div>
            <div><p className="text-2xl font-black text-slate-900 dark:text-white">{k.value}</p><p className="text-xs text-slate-500">{k.label}</p></div>
          </div>
        ))}
      </div>

      <div className="card p-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-52">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/>
          <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="N° dossier, code déchet, générateur..." className="input pl-9 text-sm"/>
          {search&&<button onClick={()=>setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2"><X size={13} className="text-slate-400"/></button>}
        </div>
        <div className="flex gap-1 bg-slate-100 dark:bg-[#16240D] rounded-xl p-1">
          {[{k:'',l:'Tous'},{k:'EN_COURS',l:'En cours'},{k:'TERMINEE',l:'Terminés'},{k:'ANNULEE',l:'Annulés'}].map(t=>(
            <button key={t.k} onClick={()=>setStatut(t.k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${statut===t.k?'bg-white dark:bg-[#2B3D1E] text-slate-900 shadow-sm':'text-slate-500'}`}>{t.l}</button>
          ))}
        </div>
      </div>

      {loading?<Spinner/>:operations.length===0?(
        <div className="card p-16 text-center">
          <Package size={40} className="mx-auto mb-3 text-slate-200"/>
          <p className="font-semibold text-slate-400 text-lg">Aucun dossier de traçabilité</p>
          <p className="text-sm text-slate-300 mt-1 mb-5">Créez votre premier dossier de suivi de déchet</p>
          <button onClick={()=>{setEditing(null);setShowForm(true)}} className="btn-primary"><Plus size={15}/>Créer un dossier</button>
        </div>
      ):(
        <div className="space-y-2">
          {operations.map(op=><OperationCard key={op.id} op={op} onEdit={handleEdit} onDelete={handleDelete} onView={setViewing}/>)}
        </div>
      )}

      <Modal open={showForm} onClose={()=>{setShowForm(false);setEditing(null)}}
        title={editing?`Modifier dossier — ${editing.numero}`:'Nouveau dossier de traçabilité'} size="max-w-3xl">
        <TracabiliteForm operation={editing} lists={lists} currentUser={user} onSave={handleSave} onClose={()=>{setShowForm(false);setEditing(null)}}/>
      </Modal>

      {viewing&&(
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="fixed inset-0 bg-black/30" onClick={()=>setViewing(null)}/>
          <div className="relative w-full max-w-lg bg-white dark:bg-[#16240D] h-full overflow-y-auto shadow-2xl p-6">
            <div className="flex items-center justify-between mb-5">
              <div>
                <p className="font-bold font-mono text-primary-700 text-lg">{viewing.numero}</p>
                <p className="text-sm text-slate-500 mt-0.5">{viewing.designation_dechet?.slice(0,60)}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={()=>{handleEdit(viewing);setViewing(null)}} className="btn-secondary btn-sm"><Edit size={13}/></button>
                <button onClick={()=>setViewing(null)} className="btn-ghost p-2"><X size={16}/></button>
              </div>
            </div>
            {[
              ['Récupérateur',viewing.recuperateur_nom],['Générateur',viewing.generateur_nom],
              ['Code déchet',viewing.code_dechet],['Désignation',viewing.designation_dechet],
              ['Classe',viewing.classe_dechet],['Quantité totale',`${viewing.quantite} ${viewing.unite_display||viewing.unite}`],
              ['Couleur',viewing.couleur_display],['Niveau de propreté',viewing.niveau_proprete_display],
              ['Date récupération',viewing.date_recuperation],
              ['Prix unitaire (TTC, DZD)',viewing.prix_unitaire_ttc && `${Number(viewing.prix_unitaire_ttc).toLocaleString('fr-FR')} DZD`],
              ['Prix d\'achat total (TTC, DZD)',viewing.prix_achat_ttc && `${Number(viewing.prix_achat_ttc).toLocaleString('fr-FR')} DZD`],
              ['Transporteur',viewing.transporteur_nom],
              ['Chauffeur',viewing.chauffeur],['Immatriculation',viewing.immatriculation],
              ['Frais de transport (TTC, DZD)',viewing.frais_transport_ttc && `${Number(viewing.frais_transport_ttc).toLocaleString('fr-FR')} DZD`],
              ['Autres frais (TTC, DZD)',viewing.autres_frais_ttc && `${Number(viewing.autres_frais_ttc).toLocaleString('fr-FR')} DZD`],
              ['Prix de revient global (TTC, DZD)',viewing.prix_revient_global_ttc && `${Number(viewing.prix_revient_global_ttc).toLocaleString('fr-FR')} DZD`],
              ['Prix de revient unitaire (TTC, DZD)',viewing.prix_revient_unitaire_ttc && `${Number(viewing.prix_revient_unitaire_ttc).toLocaleString('fr-FR')} DZD`],
              ['N° BSD',viewing.bsd_numero],['Observations',viewing.observations],
            ].filter(([,v])=>v).map(([l,v])=>(
              <div key={l} className="flex gap-3 text-sm py-2 border-b border-slate-50 dark:border-[#2B3D1E] last:border-0">
                <span className="w-36 text-slate-400 flex-shrink-0">{l}</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">{v}</span>
              </div>
            ))}

            {/* Répartition des destinations */}
            {viewing.repartitions?.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                  <GitBranch size={11}/> Répartition des destinations
                </p>
                <div className="space-y-2">
                  {viewing.repartitions.map((r, i) => {
                    const d = DEST_OPTIONS.find(x => x.key === r.type) || DEST_OPTIONS[0]
                    return (
                      <div key={i} className={`flex items-center gap-3 p-3 rounded-xl border ${d.bg}`}>
                        <d.icon size={15} className={`flex-shrink-0 ${d.color}`}/>
                        <div className="flex-1 min-w-0">
                          <p className={`text-xs font-bold ${d.color}`}>{d.label}</p>
                          {r.operateur_nom && <p className="text-xs text-slate-500 truncate">{r.operateur_nom}</p>}
                        </div>
                        <span className="font-bold text-sm text-slate-800 dark:text-slate-200 flex-shrink-0">
                          {parseFloat(r.quantite).toLocaleString('fr-FR',{maximumFractionDigits:3})} {viewing.unite_display||viewing.unite}
                        </span>
                      </div>
                    )
                  })}
                  <div className="flex justify-between text-xs font-semibold text-slate-500 px-1 pt-1 border-t border-slate-100">
                    <span>Total affecté</span>
                    <span>{viewing.repartitions.reduce((s,r)=>s+(parseFloat(r.quantite)||0),0).toLocaleString('fr-FR',{maximumFractionDigits:3})} {viewing.unite_display||viewing.unite}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
