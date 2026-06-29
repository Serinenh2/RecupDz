import { useEffect, useState, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import {
  FileText, Plus, Search, X, Save, Edit, Trash2,
  Download, Shield, AlertTriangle, CheckCircle2,
  Clock, XCircle, Clipboard, BarChart3, Calendar
} from 'lucide-react'
import api from '../../api'
import { useAuthStore } from '../../store'
import { NOMENCLATURE } from '../nomenclature/nomenclatureData'
import DateInput from '../../components/common/DateInput'
import toast from 'react-hot-toast'

const bsdAPI = {
  getAll:  (p)    => api.get('/bsd/', { params: p }),
  create:  (d)    => api.post('/bsd/', d),
  update:  (id,d) => api.patch(`/bsd/${id}/`, d),
  delete:  (id)   => api.delete(`/bsd/${id}/`),
  pdf:     (d)    => api.post('/bsd/generate-bsd/', d, { responseType:'blob' }),
  word:    (d)    => api.post('/bsd/generate-bsd-word/', d, { responseType:'blob' }),
}
const dsdAPI = {
  getAll:  (p)    => api.get('/declarations/', { params: p }),
  create:  (d)    => api.post('/declarations/', d),
  update:  (id,d) => api.patch(`/declarations/${id}/`, d),
  delete:  (id)   => api.delete(`/declarations/${id}/`),
  pdf:     (d)    => api.post('/declarations/generate-dsd/', d, { responseType:'blob' }),
  pdfById: (id)   => api.get(`/declarations/${id}/generer_pdf/`, { responseType:'blob' }),
  word:    (d)    => api.post('/declarations/generate-dsd-word/', d, { responseType:'blob' }),
  wordById:(id)   => api.post(`/declarations/${id}/generer_word/`, {}, { responseType:'blob' }),
}
const pvAPI = {
  getAll:  (p)    => api.get('/inspections/', { params: p }),
  create:  (d)    => api.post('/inspections/', d),
  update:  (id,d) => api.patch(`/inspections/${id}/`, d),
  delete:  (id)   => api.delete(`/inspections/${id}/`),
  pdf:     (d)    => api.post('/inspections/generate-pv/', d, { responseType:'blob' }),
  pdfById: (id)   => api.get(`/inspections/${id}/generer_pdf/`, { responseType:'blob' }),
  word:    (d)    => api.post('/inspections/generate-pv-word/', d, { responseType:'blob' }),
  wordById:(id)   => api.get(`/inspections/${id}/generer_word/`, { responseType:'blob' }),
}
const recupAPI = { getAll: () => api.get('/recuperateurs/?page_size=200') }
const tracaAPI = { getAll: (p) => api.get('/traceability/', { params: p }) }
const eliminateurAPI = { getAll: () => api.get('/operateurs/?type_operateur=ELIMINATEUR&page_size=200') }

const TABS = [
  { key:'bsd',      label:'BSD',      icon:FileText,      desc:'Bordereaux de Suivi des Déchets — documents de traçabilité obligatoires' },
  { key:'dsd',      label:'DSD',      icon:AlertTriangle, desc:'Déclarations des Déchets Spéciaux Dangereux — formulaire annuel officiel' },
  { key:'pv',       label:'PV',       icon:Clipboard,     desc:'Procès-Verbaux de contrôle environnemental' },
  { key:'rapports', label:'Rapports', icon:BarChart3,     desc:'Rapports environnementaux périodiques' },
]
const BSD_ST = {
  BROUILLON:   { label:'Brouillon',   badge:'badge-gray',   icon:Clock        },
  EMIS:        { label:'Émis',        badge:'badge-blue',   icon:FileText     },
  EN_TRANSIT:  { label:'En transit',  badge:'badge-yellow', icon:Clock        },
  RECEPTIONNE: { label:'Réceptionné', badge:'badge-green',  icon:CheckCircle2 },
  SIGNE:       { label:'Signé',       badge:'badge-green',  icon:CheckCircle2 },
  ARCHIVE:     { label:'Archivé',     badge:'badge-gray',   icon:XCircle      },
}
const DSD_ST = {
  BROUILLON: { label:'Brouillon', badge:'badge-gray',   icon:Clock        },
  SOUMISE:   { label:'Soumise',   badge:'badge-yellow', icon:Clock        },
  VALIDEE:   { label:'Validée',   badge:'badge-green',  icon:CheckCircle2 },
  ARCHIVEE:  { label:'Archivée',  badge:'badge-gray',   icon:XCircle      },
}

const SD_CODES = useMemo => NOMENCLATURE.filter(n => ['S','SD'].includes(n.classe))

function Spinner() {
  return <div className="flex justify-center py-12"><div className="w-7 h-7 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"/></div>
}

function Modal({ open, onClose, title, children, size='max-w-2xl' }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className={`bg-white dark:bg-[#16240D] rounded-2xl shadow-2xl w-full ${size} max-h-[90vh] flex flex-col`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] dark:border-[#2B3D1E] flex-shrink-0">
          <h3 className="font-bold text-slate-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 p-1"><X size={18}/></button>
        </div>
        <div className="p-6 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}

// ── Code Déchet Picker (shared by BSD and DSD) ────────────────────────────────
function CodeDechetPicker({ value, onChange }) {
  const [search, setSearch] = useState(value || '')
  const [open,   setOpen]   = useState(false)

  const filtered = useMemo(() =>
    NOMENCLATURE
      .filter(n => ['S','SD'].includes(n.classe))
      .filter(n =>
        !search ||
        n.code.includes(search.split(' ')[0]) ||
        n.nom_fr.toLowerCase().includes(search.toLowerCase())
      )
      .slice(0, 40)
  , [search])

  const select = (n) => {
    setSearch(`${n.code} — ${n.nom_fr.slice(0,50)}`)
    setOpen(false)
    onChange(n.code, n.nom_fr, n.classe)
  }

  return (
    <div className="relative">
      <input
        value={search}
        onChange={e => { setSearch(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        placeholder="Rechercher un déchet spécial ou dangereux..."
        className="input"
      />
      {open && (
        <div className="absolute z-30 top-full left-0 right-0 mt-1 bg-white dark:bg-[#16240D] border border-[#E2E8F0] rounded-xl shadow-xl max-h-52 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="text-center py-4 text-slate-400 text-xs">Aucun résultat</p>
          ) : filtered.map(n => (
            <button key={n.code} type="button" onClick={() => select(n)}
              className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-slate-50 dark:hover:bg-[#16240D] text-xs">
              <span className="font-mono font-bold text-primary-700 flex-shrink-0 w-16">{n.code}</span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold flex-shrink-0
                ${n.classe==='SD'?'bg-red-100 text-red-700':'bg-amber-100 text-amber-700'}`}>
                {n.classe}
              </span>
              <span className="text-slate-600 dark:text-slate-300 truncate">{n.nom_fr}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Dossier de traçabilité Picker (import depuis un dossier S/SD existant) ────
function DossierPicker({ dossiers = [], onSelect }) {
  const [selected, setSelected] = useState('')

  const handleChange = (e) => {
    const id = e.target.value
    setSelected(id)
    const d = dossiers.find(x => String(x.id) === id)
    if (d) onSelect(d)
  }

  if (dossiers.length === 0) return null

  return (
    <div className="card p-3 bg-primary-50/50 border-primary-200 space-y-2">
      <label className="label flex items-center gap-1.5">
        <Shield size={12} className="text-primary-500"/> Importer depuis un dossier de traçabilité (déchets spéciaux / dangereux)
      </label>
      <select value={selected} onChange={handleChange} className="input">
        <option value="">-- Sélectionner un dossier pour pré-remplir le formulaire --</option>
        {dossiers.map(d => (
          <option key={d.id} value={d.id}>
            {d.numero} — {d.code_dechet} {d.designation_dechet?.slice(0,40)} ({d.quantite} {d.unite_display||d.unite})
          </option>
        ))}
      </select>
      <p className="text-[10px] text-primary-600">
        Les informations du dossier sont importées automatiquement — complétez le reste ci-dessous.
      </p>
    </div>
  )
}

// ── BSD Form ──────────────────────────────────────────────────────────────────
function BSDForm({ bsd, recuperateurs, dossiers, currentUser, onSave, onClose }) {
  const isEdit = !!bsd?.id
  const { register, handleSubmit, watch, setValue, reset } = useForm({
    defaultValues: bsd || {
      statut: 'BROUILLON', unite: 'KG',
      recuperateur: currentUser?.recuperateur_id || '',
      date_emission: new Date().toISOString().split('T')[0],
    }
  })
  const [saving,     setSaving]     = useState(false)
  const [generating, setGenerating] = useState(false)
  const [codeDechet, setCodeDechet] = useState(bsd?.code_dechet || '')
  const isRecup = currentUser?.role === 'RECUPERATEUR'

  useEffect(() => { if (bsd) reset(bsd) }, [bsd])

  const importerDossier = (d) => {
    setCodeDechet(d.code_dechet || '')
    setValue('designation', d.designation_dechet || '')
    setValue('classe', d.classe_dechet || '')
    setValue('quantite', d.quantite || '')
    setValue('unite', d.unite || 'KG')
    setValue('generateur_nom', d.generateur_nom || '')
    setValue('transporteur_nom', d.transporteur_nom || '')
    setValue('recepteur_nom', d.valorisateur_nom || d.eliminateur_nom || d.cet_nom || '')
    if (!isRecup && d.recuperateur) setValue('recuperateur', d.recuperateur)
    toast.success(`Dossier ${d.numero} importé`)
  }

  const onSubmit = async (data) => {
    setSaving(true)
    if (isRecup && currentUser?.recuperateur_id) data.recuperateur = currentUser.recuperateur_id
    data.code_dechet = codeDechet
    try {
      if (isEdit) { await bsdAPI.update(bsd.id, data); toast.success('BSD mis à jour') }
      else        { await bsdAPI.create(data);          toast.success('BSD créé') }
      onSave()
    } catch { toast.error('Erreur') }
    finally { setSaving(false) }
  }

  const buildBsdData = () => ({
    numero:               bsd?.numero || '',
    generateur_nom:       watch('generateur_nom'),
    generateur_adresse:   watch('generateur_adresse'),
    bon_commande:         watch('bon_commande'),
    site_enlevement:      watch('site_enlevement'),
    generateur_tel:       watch('generateur_tel'),
    generateur_fax:       watch('generateur_fax'),
    code_dechet:          codeDechet || watch('code_dechet'),
    designation:          watch('designation'),
    classe:               watch('classe'),
    etat_physique:        watch('etat_physique'),
    autres_precision:     watch('autres_precision'),
    quantite:             watch('quantite'),
    unite:                watch('unite'),
    emballage:            watch('emballage'),
    recuperateur_nom:     isRecup ? currentUser?.recuperateur_nom : recuperateurs.find(r=>String(r.id)===String(watch('recuperateur')))?.nom_raison_sociale,
    recuperateur_adresse: watch('recuperateur_adresse'),
    responsable:          watch('responsable'),
    representant:         watch('representant'),
    fonction:             watch('fonction'),
    transporteur_nom:     watch('transporteur_nom'),
    transporteur_vehicule:watch('transporteur_vehicule'),
    immatriculation:      watch('immatriculation'),
    recepteur_nom:        watch('recepteur_nom'),
    type_traitement:      watch('type_traitement'),
    date_emission:        watch('date_emission'),
    date_reception:       watch('date_reception'),
    statut:               watch('statut'),
  })

  const downloadPdf = async () => {
    setGenerating(true)
    try {
      const formData = buildBsdData()
      const res = await bsdAPI.pdf(formData)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download', `${formData.numero||'BSD'}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BSD téléchargé !')
    } catch { toast.error('Erreur génération PDF') }
    finally { setGenerating(false) }
  }

  const downloadWord = async () => {
    setGenerating(true)
    try {
      const formData = buildBsdData()
      const res = await bsdAPI.word(formData)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download', `${formData.numero||'BSD'}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BSD téléchargé (Word) !')
    } catch { toast.error('Erreur génération Word') }
    finally { setGenerating(false) }
  }

  const F = ({ label, req, children }) => (
    <div>
      <label className="label">{label}{req && <span className="text-red-500 ml-0.5">*</span>}</label>
      {children}
    </div>
  )

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {!isEdit && <DossierPicker dossiers={dossiers} onSelect={importerDossier}/>}
      {isRecup ? (
        <div className="card p-3 bg-primary-50 border-primary-200 flex items-center gap-2">
          <Shield size={14} className="text-primary-600 flex-shrink-0"/>
          <p className="text-sm font-semibold text-primary-800">{currentUser?.recuperateur_nom}</p>
        </div>
      ) : (
        <F label="Récupérateur" req>
          <select {...register('recuperateur',{required:true})} className="input">
            <option value="">-- Sélectionner --</option>
            {recuperateurs.map(r=><option key={r.id} value={r.id}>{r.nom_raison_sociale}</option>)}
          </select>
        </F>
      )}

      <div className="card p-4 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">1. Générateur de déchet</p>
        <div className="grid grid-cols-2 gap-3">
          <F label="Générateur / Producteur" req>
            <input {...register('generateur_nom',{required:true})} className="input" placeholder="Nom du générateur"/>
          </F>
          <F label="Adresse générateur (siège social)">
            <input {...register('generateur_adresse')} className="input" placeholder="Adresse..."/>
          </F>
          <F label="Bon de commande">
            <input {...register('bon_commande')} className="input"/>
          </F>
          <F label="Site d'enlèvement (si différent)">
            <input {...register('site_enlevement')} className="input"/>
          </F>
          <F label="Téléphone">
            <input {...register('generateur_tel')} className="input"/>
          </F>
          <F label="Fax">
            <input {...register('generateur_fax')} className="input"/>
          </F>
        </div>
      </div>

      <F label="Code déchet (S ou SD)" req>
        <CodeDechetPicker
          key={codeDechet}
          value={codeDechet ? `${codeDechet} — ${watch('designation')||''}` : ''}
          onChange={(code, nom, classe) => {
            setCodeDechet(code)
            setValue('designation', nom)
            setValue('classe', classe)
          }}
        />
        <input type="hidden" {...register('designation')}/>
        <input type="hidden" {...register('classe')}/>
        {codeDechet && (
          <p className="text-xs text-primary-600 mt-1 font-mono">Code sélectionné : <strong>{codeDechet}</strong></p>
        )}
      </F>

      <div className="grid grid-cols-2 gap-3">
        <F label="État physique">
          <select {...register('etat_physique')} className="input">
            <option value="">--</option>
            <option value="SOLIDE">Solide</option>
            <option value="LIQUIDE">Liquide</option>
            <option value="PATEUX">Pâteux</option>
            <option value="GAZEUX">Gazeux</option>
          </select>
        </F>
        <F label="Mode de stockage">
          <select {...register('emballage')} className="input">
            <option value="">--</option>
            <option value="FUT">Fût</option>
            <option value="BIG_BAG">Big Bag</option>
            <option value="CAISSE_BOIS">Caisse Bois</option>
            <option value="VRAC_PALETTE">Vrac/palette</option>
          </select>
        </F>
      </div>

      <F label="Autres précisions">
        <input {...register('autres_precision')} className="input"/>
      </F>

      <div className="grid grid-cols-2 gap-3">
        <F label="Quantité" req>
          <input {...register('quantite',{required:true})} type="number" step="0.001" className="input"/>
        </F>
        <F label="Unité">
          <select {...register('unite')} className="input">
            <option value="KG">Kilogramme</option>
            <option value="TONNE">Tonne</option>
            <option value="M3">m³</option>
            <option value="LITRE">Litre</option>
          </select>
        </F>
      </div>

      <div className="card p-4 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">2. Collecteur — Transporteur</p>
        <div className="grid grid-cols-2 gap-3">
          <F label="Transporteur (si différent du récupérateur)">
            <input {...register('transporteur_nom')} className="input"/>
          </F>
          <F label="Siège social du collecteur">
            <input {...register('recuperateur_adresse')} className="input"/>
          </F>
          <F label="Responsable">
            <input {...register('responsable')} className="input"/>
          </F>
          <div className="grid grid-cols-2 gap-2">
            <F label="Représentant"><input {...register('representant')} className="input"/></F>
            <F label="Fonction"><input {...register('fonction')} className="input"/></F>
          </div>
          <F label="Moyen de transport">
            <input {...register('transporteur_vehicule')} className="input" placeholder="Camion, benne..."/>
          </F>
          <F label="Matricule (immatriculation)">
            <input {...register('immatriculation')} className="input"/>
          </F>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <F label="Destinataire / Récepteur (installation de destination)">
          <input {...register('recepteur_nom')} className="input"/>
        </F>
        <F label="Type de traitement">
          <select {...register('type_traitement')} className="input">
            <option value="">--</option>
            <option value="VALORISATION">Valorisation</option>
            <option value="ELIMINATION">Élimination</option>
            <option value="CET">CET</option>
          </select>
        </F>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <F label="Date d'émission" req>
          <DateInput value={watch('date_emission')||''} onChange={v=>setValue('date_emission',v)}/>
        </F>
        <F label="Date de réception">
          <DateInput value={watch('date_reception')||''} onChange={v=>setValue('date_reception',v)}/>
        </F>
      </div>

      <F label="Statut">
        <select {...register('statut')} className="input">
          {Object.entries(BSD_ST).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}
        </select>
      </F>

      <div className="flex gap-3 pt-2 border-t border-[#E2E8F0]">
        <button type="submit" disabled={saving||generating} className="btn-primary">
          <Save size={15}/> {saving?'Enregistrement...':isEdit?'Mettre à jour':'Créer le BSD'}
        </button>
        <button type="button" onClick={downloadPdf} disabled={saving||generating} className="btn-secondary flex items-center gap-2">
          {generating
            ? <><span className="w-4 h-4 border-2 border-slate-400/30 border-t-slate-500 rounded-full animate-spin"/>Génération...</>
            : <><Download size={15}/>Télécharger PDF</>
          }
        </button>
        <button type="button" onClick={downloadWord} disabled={saving||generating} className="btn-secondary flex items-center gap-2">
          <Download size={15}/>Télécharger Word
        </button>
        <button type="button" onClick={onClose} className="btn-secondary">Annuler</button>
      </div>
    </form>
  )
}

// ── DSD Form ──────────────────────────────────────────────────────────────────
function DSDForm({ dsd, recuperateurs, dossiers, currentUser, onSave, onClose }) {
  const isEdit = !!dsd?.id
  const { register, handleSubmit, watch, setValue, reset } = useForm({
    defaultValues: dsd || {
      annee: new Date().getFullYear().toString(),
      statut: 'BROUILLON',
      denomination: currentUser?.recuperateur_nom || '',
      statut_juridique: 'SARL',
      responsable_dechets: `${currentUser?.first_name||''} ${currentUser?.last_name||''}`.trim(),
      recuperateur: currentUser?.recuperateur_id || '',
      reutilisation_qte:'0', recyclage_qte:'0', valorisation_qte:'0', elimination_qte:'0',
    }
  })
  const [saving,     setSaving]     = useState(false)
  const [generating, setGenerating] = useState(false)
  const [codeDechet, setCodeDechet] = useState(dsd?.code_dechet || '')
  const isRecup = currentUser?.role === 'RECUPERATEUR'

  useEffect(() => { if (dsd) reset(dsd) }, [dsd])

  const importerDossier = (d) => {
    setCodeDechet(d.code_dechet || '')
    setValue('denomination_dechet', d.designation_dechet || '')
    setValue('quantite_generee', d.quantite || '')
    setValue('denomination', d.recuperateur_nom || currentUser?.recuperateur_nom || '')
    if (!isRecup && d.recuperateur) setValue('recuperateur', d.recuperateur)
    toast.success(`Dossier ${d.numero} importé`)
  }

  const onSubmit = async (data) => {
    setSaving(true)
    if (isRecup && currentUser?.recuperateur_id) data.recuperateur = currentUser.recuperateur_id
    data.code_dechet = codeDechet
    try {
      if (isEdit) { await dsdAPI.update(dsd.id, data); toast.success('DSD mise à jour') }
      else        { await dsdAPI.create(data);          toast.success('DSD créée') }
      onSave()
    } catch { toast.error('Erreur') }
    finally { setSaving(false) }
  }

  const buildDsdData = () => ({
    annee:               watch('annee'),
    date_transmission:   watch('date_transmission'),
    statut:              watch('statut_juridique'),
    denomination:        watch('denomination'),
    siege_social:        watch('siege_social'),
    domaine_activite:    watch('domaine_activite'),
    certification:       watch('certification'),
    responsable_dechets: watch('responsable_dechets'),
    matiere_premiere:    watch('matiere_premiere'),
    denomination_dechet: watch('denomination_dechet'),
    code_dechet:         codeDechet || watch('code_dechet'),
    consistance:         watch('consistance'),
    autres_precisions:   watch('autres_precisions'),
    quantite_generee:    watch('quantite_generee'),
    composition_chimique:watch('composition_chimique'),
    critere_dangerosite: watch('critere_dangerosite'),
    stockage_temporaire_qte: watch('stockage_temporaire_qte'),
    stockage_permanent_qte:  watch('stockage_permanent_qte'),
    modalites_stockage:  watch('modalites_stockage'),
    modalites_gestion:   watch('modalites_gestion'),
    modalites_controle:  watch('modalites_controle'),
    modalites_elimination: watch('modalites_elimination'),
    types_installation:  watch('types_installation'),
    types_traitement:    watch('types_traitement'),
    quantites_traitees:  watch('quantites_traitees'),
    rendement_traitement:watch('rendement_traitement'),
    reutilisation_qte:   watch('reutilisation_qte'),
    recyclage_qte:       watch('recyclage_qte'),
    valorisation_qte:    watch('valorisation_qte'),
    elimination_qte:     watch('elimination_qte'),
    mesures_min_prises:       watch('mesures_min_prises'),
    mesures_min_envisager:    watch('mesures_min_envisager'),
    mesures_bpe_prises:       watch('mesures_bpe_prises'),
    mesures_bpe_envisager:    watch('mesures_bpe_envisager'),
    mesures_tech_prises:      watch('mesures_tech_prises'),
    mesures_tech_envisager:   watch('mesures_tech_envisager'),
    mesures_pp_prises:        watch('mesures_pp_prises'),
    mesures_pp_envisager:     watch('mesures_pp_envisager'),
    mesures_risques_prises:   watch('mesures_risques_prises'),
    mesures_risques_envisager:watch('mesures_risques_envisager'),
  })

  const downloadPdf = async () => {
    setGenerating(true)
    try {
      const currentData = buildDsdData()
      const res = await dsdAPI.pdf(currentData)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url
      a.setAttribute('download', `DSD_${currentData.denomination||'document'}_${currentData.annee||'2024'}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('PDF DSD téléchargé !')
    } catch { toast.error('Erreur génération PDF') }
    finally { setGenerating(false) }
  }

  const downloadWord = async () => {
    setGenerating(true)
    try {
      const currentData = buildDsdData()
      const res = await dsdAPI.word(currentData)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url
      a.setAttribute('download', `DSD_${currentData.denomination||'document'}_${currentData.annee||'2024'}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('DSD téléchargé (Word) !')
    } catch { toast.error('Erreur génération Word') }
    finally { setGenerating(false) }
  }

  const F = ({ label, req, children, col }) => (
    <div className={col||''}>
      <label className="label">{label}{req && <span className="text-red-500 ml-0.5">*</span>}</label>
      {children}
    </div>
  )
  const Sec = ({ children }) => (
    <div className="bg-slate-100 dark:bg-[#2B3D1E] px-4 py-2 rounded-lg">
      <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">{children}</p>
    </div>
  )

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {!isEdit && <DossierPicker dossiers={dossiers} onSelect={importerDossier}/>}
      <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-50 border border-amber-200">
        <AlertTriangle size={14} className="text-amber-500 flex-shrink-0 mt-0.5"/>
        <p className="text-xs text-amber-700">
          <strong>Décret exécutif n°05-315</strong> — À transmettre dans un délai n'excédant pas 3 mois après la clôture de l'année.
        </p>
      </div>

      <Sec>Identification du générateur</Sec>
      <div className="grid grid-cols-2 gap-3">
        <F label="Année" req col=""><input {...register('annee',{required:true})} className="input" placeholder="2024"/></F>
        <F label="Date de transmission" col="">
          <DateInput value={watch('date_transmission')||''} onChange={v=>setValue('date_transmission',v)}/>
        </F>
        <F label="Statut juridique" req col="">
          <select {...register('statut_juridique',{required:true})} className="input">
            {['EURL','SARL','SPA','SNC','PHYSIQUE','AUTRE'].map(s=><option key={s}>{s}</option>)}
          </select>
        </F>
        <F label="Dénomination" req col="">
          <input {...register('denomination',{required:true})} className="input"/>
        </F>
        <F label="Siège social" req col="col-span-2">
          <input {...register('siege_social',{required:true})} className="input"/>
        </F>
        <F label="Domaine d'activité" col="">
          <input {...register('domaine_activite')} className="input"/>
        </F>
        <F label="Certification" col="">
          <input {...register('certification')} className="input" placeholder="Agrément n°..."/>
        </F>
        <F label="Responsable déchets" req col="col-span-2">
          <input {...register('responsable_dechets',{required:true})} className="input"/>
        </F>
      </div>

      <Sec>A — Nature, quantité et caractéristiques</Sec>
      <div className="grid grid-cols-2 gap-3">
        <F label="Matière première" col="">
          <input {...register('matiere_premiere')} className="input"/>
        </F>
        <F label="Consistance" col="">
          <select {...register('consistance')} className="input">
            <option value="">--</option>
            {['Solide','Liquide','Gazeux','Pâteux','Liquide / Pâteux'].map(s=><option key={s}>{s}</option>)}
          </select>
        </F>

        {/* Code déchet with picker — same as BSD */}
        <F label="Code du déchet (S ou SD)" req col="col-span-2">
          <CodeDechetPicker
            key={codeDechet}
            value={codeDechet ? `${codeDechet} — ${watch('denomination_dechet')||''}` : ''}
            onChange={(code, nom, classe) => {
              setCodeDechet(code)
              setValue('code_dechet', code)
              setValue('denomination_dechet', nom)
            }}
          />
          <input type="hidden" {...register('code_dechet')}/>
          {codeDechet && (
            <p className="text-xs text-primary-600 mt-1 font-mono">
              Code sélectionné : <strong>{codeDechet}</strong>
            </p>
          )}
        </F>

        <F label="Dénomination du déchet" req col="col-span-2">
          <input {...register('denomination_dechet',{required:true})} className="input"
            placeholder="Se remplit automatiquement après sélection du code"/>
        </F>

        <F label="Autres précisions" col="col-span-2">
          <input {...register('autres_precisions')} className="input"/>
        </F>
        <F label="Quantité générée (t/an)" req col="">
          <input {...register('quantite_generee',{required:true})} type="number" step="0.01" className="input"/>
        </F>
        <F label="Composition chimique" col="">
          <input {...register('composition_chimique')} className="input"/>
        </F>
        <F label="Critère de dangerosité" col="col-span-2">
          <input {...register('critere_dangerosite')} className="input" placeholder="H3 Inflammable, H6 Toxique..."/>
        </F>
        <F label="Stockage temporaire (t/an)" col="">
          <input {...register('stockage_temporaire_qte')} type="number" step="0.01" className="input" placeholder="0"/>
        </F>
        <F label="Stockage permanent (t/an)" col="">
          <input {...register('stockage_permanent_qte')} type="number" step="0.01" className="input" placeholder="0"/>
        </F>
        <F label="Modalités de stockage" col="col-span-2">
          <textarea {...register('modalites_stockage')} className="input" rows={2}/>
        </F>
      </div>

      <Sec>B — Modes de traitement</Sec>
      <div className="grid grid-cols-2 gap-3">
        <F label="Modalités de gestion" col=""><textarea {...register('modalites_gestion')} className="input" rows={2}/></F>
        <F label="Modalités de contrôle" col=""><textarea {...register('modalites_controle')} className="input" rows={2}/></F>
        <F label="Modalités d'élimination" col="col-span-2"><textarea {...register('modalites_elimination')} className="input" rows={2}/></F>
        <F label="Types d'installation" col=""><input {...register('types_installation')} className="input"/></F>
        <F label="Types de traitement" col=""><input {...register('types_traitement')} className="input"/></F>
        <F label="Quantités traitées (t/an)" col=""><input {...register('quantites_traitees')} type="number" step="0.01" className="input"/></F>
        <F label="Rendement" col=""><input {...register('rendement_traitement')} className="input" placeholder="99%"/></F>
      </div>

      <Sec>C — Mesures pour éviter la production</Sec>
      <div className="grid grid-cols-4 gap-3">
        <F label="Réutilisation (t/an)" col=""><input {...register('reutilisation_qte')} type="number" step="0.01" className="input"/></F>
        <F label="Recyclage (t/an)" col=""><input {...register('recyclage_qte')} type="number" step="0.01" className="input"/></F>
        <F label="Valorisation (t/an)" col=""><input {...register('valorisation_qte')} type="number" step="0.01" className="input"/></F>
        <F label="Élimination (t/an)" col=""><input {...register('elimination_qte')} type="number" step="0.01" className="input"/></F>
      </div>

      {[
        ['1 — Minimisation',          'mesures_min_prises',      'mesures_min_envisager'],
        ['2 — Bonnes pratiques',       'mesures_bpe_prises',      'mesures_bpe_envisager'],
        ['3 — Techniques disponibles', 'mesures_tech_prises',     'mesures_tech_envisager'],
        ['4 — Production propre',      'mesures_pp_prises',       'mesures_pp_envisager'],
        ['5 — Gestion des risques',    'mesures_risques_prises',  'mesures_risques_envisager'],
      ].map(([t,p,e]) => (
        <div key={t} className="card p-3 space-y-2">
          <p className="text-xs font-bold text-slate-500">{t}</p>
          <div className="grid grid-cols-2 gap-2">
            <div><label className="label text-xs">Mesures prises</label><textarea {...register(p)} className="input text-xs" rows={2}/></div>
            <div><label className="label text-xs">À envisager</label><textarea {...register(e)} className="input text-xs" rows={2}/></div>
          </div>
        </div>
      ))}

      <div className="flex gap-3 pt-3 border-t border-[#E2E8F0] sticky bottom-0 bg-white dark:bg-[#16240D] py-3">
        <button type="submit" disabled={saving} className="btn-primary">
          <Save size={15}/> {saving?'Enregistrement...':isEdit?'Mettre à jour':'Enregistrer la DSD'}
        </button>
        <button type="button" onClick={downloadPdf} disabled={generating} className="btn-secondary">
          <Download size={15}/> {generating?'Génération...':'Télécharger PDF'}
        </button>
        <button type="button" onClick={downloadWord} disabled={generating} className="btn-secondary">
          <Download size={15}/> Télécharger Word
        </button>
        <button type="button" onClick={onClose} className="btn-secondary">Annuler</button>
      </div>
    </form>
  )
}

// ── PV Form ───────────────────────────────────────────────────────────────────
function PVForm({ pv, recuperateurs, dossiers, eliminateurs, currentUser, onSave, onClose }) {
  const isEdit = !!pv?.id
  const { register, handleSubmit, watch, setValue, reset } = useForm({
    defaultValues: pv || {
      type_inspection:'ROUTINE',
      recuperateur: currentUser?.recuperateur_id||'',
      date_inspection: new Date().toISOString().split('T')[0],
    }
  })
  const [saving,     setSaving]     = useState(false)
  const [generating, setGenerating] = useState(false)
  const isRecup = currentUser?.role === 'RECUPERATEUR'
  const recuperateurId = watch('recuperateur')
  const eliminateurId  = watch('eliminateur_id')

  useEffect(() => { if (pv) reset(pv) }, [pv])

  // Renseigne automatiquement l'adresse et l'agrément du récupérateur sélectionné
  useEffect(() => {
    const r = recuperateurs.find(x => String(x.id) === String(recuperateurId))
    if (r) {
      setValue('recuperateur_adresse', [r.commune, r.wilaya ? `W.${r.wilaya}` : ''].filter(Boolean).join(', '))
      setValue('recuperateur_agrement', r.agrement_actif?.numero_agrement || '')
      setValue('recuperateur_agrement_date', r.agrement_actif?.date_delivrance || '')
    }
  }, [recuperateurId, recuperateurs])

  // Renseigne automatiquement l'en-tête du PV à partir de l'opérateur Éliminateur
  // sélectionné (fiche créée une seule fois dans la page Opérateurs et réutilisée ici).
  const importerEliminateur = (op) => {
    setValue('raison_sociale', op.raison_sociale || '')
    setValue('agrement_exploitation', op.num_agrement || '')
    setValue('adresse', op.adresse || '')
    setValue('rc', op.registre_commerce || '')
    setValue('nif', op.nif || '')
    setValue('nis', op.nis || '')
    setValue('telephone', op.telephone || '')
  }

  useEffect(() => {
    if (!eliminateurId) return
    const op = eliminateurs.find(x => String(x.id) === String(eliminateurId))
    if (op) importerEliminateur(op)
  }, [eliminateurId, eliminateurs])

  const importerDossier = (d) => {
    setValue('designation_dechet', d.designation_dechet || '')
    setValue('quantite', d.quantite || '')
    setValue('unite', d.unite_display || d.unite || '')
    setValue('generateur_nom', d.generateur_nom || '')
    if (!isRecup && d.recuperateur) setValue('recuperateur', d.recuperateur)
    if (d.eliminateur) setValue('eliminateur_id', d.eliminateur)
    const note = `Dossier ${d.numero} — ${d.code_dechet} ${d.designation_dechet||''} (${d.quantite} ${d.unite_display||d.unite})`
    if (!watch('observations')) setValue('observations', note)
    toast.success(`Dossier ${d.numero} importé`)
  }

  const onSubmit = async (data) => {
    setSaving(true)
    if (isRecup && currentUser?.recuperateur_id) data.recuperateur = currentUser.recuperateur_id
    try {
      if (isEdit) { await pvAPI.update(pv.id,data); toast.success('PV mis à jour') }
      else        { await pvAPI.create(data);        toast.success('PV créé') }
      onSave()
    } catch { toast.error('Erreur') }
    finally { setSaving(false) }
  }

  const buildPvData = () => {
    const recup = recuperateurs.find(x => String(x.id) === String(watch('recuperateur')))
    return {
      pv_numero:           watch('pv_numero'),
      type_inspection:     watch('type_inspection'),
      date_inspection:     watch('date_inspection'),
      resultat:            watch('resultat'),
      observations:        watch('observations'),
      actions_correctives: watch('actions_correctives'),
      recuperateur:        watch('recuperateur'),
      recuperateur_nom:    isRecup ? currentUser?.recuperateur_nom : recup?.nom_raison_sociale,
      recuperateur_adresse:      watch('recuperateur_adresse'),
      recuperateur_agrement:     watch('recuperateur_agrement'),
      recuperateur_agrement_date:watch('recuperateur_agrement_date'),
      generateur_nom:      watch('generateur_nom'),
      generateur_adresse:  watch('generateur_adresse'),
      designation_dechet:  watch('designation_dechet'),
      quantite:            watch('quantite'),
      unite:               watch('unite'),
      raison_sociale:      watch('raison_sociale'),
      agrement_exploitation: watch('agrement_exploitation'),
      adresse:             watch('adresse'),
      rc:                  watch('rc'),
      nif:                 watch('nif'),
      nis:                 watch('nis'),
      art:                 watch('art'),
      telephone:           watch('telephone'),
      site_incineration:   watch('site_incineration'),
    }
  }

  const downloadPdf = async () => {
    setGenerating(true)
    try {
      const formData = buildPvData()
      const res = await pvAPI.pdf(formData)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download', `PV_${formData.pv_numero||'incineration'}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('PV téléchargé !')
    } catch { toast.error('Erreur génération PDF') }
    finally { setGenerating(false) }
  }

  const downloadWord = async () => {
    setGenerating(true)
    try {
      const formData = buildPvData()
      const res = await pvAPI.word(formData)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download', `PV_${formData.pv_numero||'incineration'}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('PV téléchargé (Word) !')
    } catch { toast.error('Erreur génération Word') }
    finally { setGenerating(false) }
  }

  const F = ({label,req,children}) => (
    <div><label className="label">{label}{req && <span className="text-red-500 ml-0.5">*</span>}</label>{children}</div>
  )

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {!isEdit && <DossierPicker dossiers={dossiers} onSelect={importerDossier}/>}
      {!isRecup && (
        <F label="Récupérateur" req>
          <select {...register('recuperateur',{required:true})} className="input">
            <option value="">-- Sélectionner --</option>
            {recuperateurs.map(r=><option key={r.id} value={r.id}>{r.nom_raison_sociale}</option>)}
          </select>
        </F>
      )}
      <div className="grid grid-cols-2 gap-3">
        <F label="Type de contrôle">
          <select {...register('type_inspection')} className="input">
            <option value="ROUTINE">Contrôle de routine</option>
            <option value="SURPRISE">Contrôle inopiné</option>
            <option value="PLAINTE">Suite à plainte</option>
            <option value="SUIVI">Contrôle de suivi</option>
          </select>
        </F>
        <F label="Date du contrôle" req>
          <DateInput value={watch('date_inspection')||''} onChange={v=>setValue('date_inspection',v)}/>
        </F>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <F label="N° PV"><input {...register('pv_numero')} className="input" placeholder="PV-2024-..."/></F>
        <F label="Résultat">
          <select {...register('resultat')} className="input">
            <option value="">--</option>
            <option value="CONFORME">Conforme</option>
            <option value="NON_CONFORME">Non conforme</option>
            <option value="EN_COURS">En cours d'examen</option>
          </select>
        </F>
      </div>
      <F label="Observations"><textarea {...register('observations')} className="input" rows={3}/></F>
      <F label="Actions correctives"><textarea {...register('actions_correctives')} className="input" rows={2}/></F>

      <div className="card p-4 space-y-3 border-l-4 border-amber-400">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
          Procès-verbal d'incinération — déchet détruit
        </p>
        <div className="grid grid-cols-2 gap-3">
          <F label="Désignation du déchet">
            <input {...register('designation_dechet')} className="input" placeholder="Désignation..."/>
          </F>
          <div className="grid grid-cols-2 gap-2">
            <F label="Quantité"><input {...register('quantite')} className="input"/></F>
            <F label="Unité"><input {...register('unite')} className="input" placeholder="kg, t..."/></F>
          </div>
          <F label="Générateur des déchets">
            <input {...register('generateur_nom')} className="input" placeholder="Raison sociale du générateur"/>
          </F>
          <F label="Adresse du générateur">
            <input {...register('generateur_adresse')} className="input" placeholder="Sise à..."/>
          </F>
        </div>
      </div>

      <div className="card p-4 space-y-3 border-l-4 border-slate-400">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
          Installation d'incinération — Éliminateur (en-tête du PV)
        </p>
        <F label="Éliminateur enregistré">
          <select {...register('eliminateur_id')} className="input">
            <option value="">-- Sélectionner un éliminateur (ou saisir manuellement ci-dessous) --</option>
            {eliminateurs.map(op => <option key={op.id} value={op.id}>{op.raison_sociale}</option>)}
          </select>
          <p className="text-[10px] text-slate-400 mt-1">
            Les informations sont reprises automatiquement de la fiche Opérateur. Modifiez-les ci-dessous si besoin.
          </p>
        </F>
        <div className="grid grid-cols-2 gap-3">
          <F label="Raison sociale"><input {...register('raison_sociale')} className="input"/></F>
          <F label="Agrément d'exploitation N°"><input {...register('agrement_exploitation')} className="input"/></F>
          <F label="Adresse"><input {...register('adresse')} className="input"/></F>
          <F label="Site d'incinération (si différent)"><input {...register('site_incineration')} className="input"/></F>
          <F label="RC"><input {...register('rc')} className="input"/></F>
          <F label="NIF"><input {...register('nif')} className="input"/></F>
          <F label="NIS"><input {...register('nis')} className="input"/></F>
          <F label="ART"><input {...register('art')} className="input"/></F>
          <F label="Téléphone"><input {...register('telephone')} className="input"/></F>
        </div>
      </div>

      <div className="flex gap-3 pt-2 border-t border-[#E2E8F0]">
        <button type="submit" disabled={saving||generating} className="btn-primary">
          <Save size={15}/> {saving?'...':isEdit?'Mettre à jour':'Créer le PV'}
        </button>
        <button type="button" onClick={downloadPdf} disabled={saving||generating} className="btn-secondary flex items-center gap-2">
          {generating
            ? <><span className="w-4 h-4 border-2 border-slate-400/30 border-t-slate-500 rounded-full animate-spin"/>Génération...</>
            : <><Download size={15}/>Télécharger PDF</>
          }
        </button>
        <button type="button" onClick={downloadWord} disabled={saving||generating} className="btn-secondary flex items-center gap-2">
          <Download size={15}/>Télécharger Word
        </button>
        <button type="button" onClick={onClose} className="btn-secondary">Annuler</button>
      </div>
    </form>
  )
}

// ── Cards ─────────────────────────────────────────────────────────────────────
function BSDCard({ doc, onEdit, onDelete, onPdf, onWord }) {
  const st = BSD_ST[doc.statut] || BSD_ST.BROUILLON
  const Icon = st.icon
  return (
    <div className="card p-4 hover:shadow-md transition-all">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-primary-50 flex items-center justify-center flex-shrink-0">
          <FileText size={18} className="text-primary-600"/>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-bold text-primary-700 text-sm">{doc.numero}</span>
            <span className={`badge ${st.badge} text-[10px]`}><Icon size={9} className="mr-0.5"/>{st.label}</span>
            {doc.classe && (
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border
                ${doc.classe==='SD'?'bg-red-50 text-red-700 border-red-200':'bg-amber-50 text-amber-700 border-amber-200'}`}>
                Cl.{doc.classe}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-300 mt-0.5">
            <span className="font-mono text-xs text-slate-400 mr-1">{doc.code_dechet}</span>
            {doc.designation?.slice(0,60)}
          </p>
          <div className="flex flex-wrap gap-x-4 text-xs text-slate-400 mt-1">
            <span className="font-bold text-slate-600">{doc.quantite} {doc.unite}</span>
            {doc.generateur_nom && <span>Gen: {doc.generateur_nom}</span>}
            <span className="flex items-center gap-1"><Calendar size={10}/>{doc.date_emission}</span>
          </div>
        </div>
        <div className="flex gap-1 flex-shrink-0">
          <button onClick={()=>onPdf(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600" title="PDF">
            <Download size={13}/>
          </button>
          <button onClick={()=>onWord(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600" title="Word">
            <FileText size={13}/>
          </button>
          <button onClick={()=>onEdit(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600">
            <Edit size={13}/>
          </button>
          <button onClick={()=>onDelete(doc.id,'bsd')} className="btn-ghost p-1.5 text-slate-400 hover:text-red-600">
            <Trash2 size={13}/>
          </button>
        </div>
      </div>
    </div>
  )
}

function DSDCard({ doc, onEdit, onDelete, onPdf, onWord }) {
  const st = DSD_ST[doc.statut] || DSD_ST.BROUILLON
  const Icon = st.icon
  return (
    <div className="card p-4 hover:shadow-md transition-all border-l-4 border-amber-400">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center flex-shrink-0">
          <AlertTriangle size={18} className="text-amber-600"/>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-amber-700 text-sm">DSD {doc.annee}</span>
            <span className={`badge ${st.badge} text-[10px]`}><Icon size={9} className="mr-0.5"/>{st.label}</span>
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-300 mt-0.5 font-semibold">{doc.denomination}</p>
          <div className="flex flex-wrap gap-x-4 text-xs text-slate-400 mt-1">
            {doc.code_dechet && <span className="font-mono">{doc.code_dechet}</span>}
            {doc.quantite_generee && <span>{doc.quantite_generee} t/an</span>}
            {doc.critere_dangerosite && (
              <span className="text-red-500">{doc.critere_dangerosite.slice(0,40)}</span>
            )}
          </div>
        </div>
        <div className="flex gap-1 flex-shrink-0">
          <button onClick={()=>onPdf(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600" title="PDF">
            <Download size={13}/>
          </button>
          <button onClick={()=>onWord(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600" title="Word">
            <FileText size={13}/>
          </button>
          <button onClick={()=>onEdit(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600">
            <Edit size={13}/>
          </button>
          <button onClick={()=>onDelete(doc.id,'dsd')} className="btn-ghost p-1.5 text-slate-400 hover:text-red-600">
            <Trash2 size={13}/>
          </button>
        </div>
      </div>
    </div>
  )
}

function PVCard({ doc, onEdit, onDelete, onPdf, onWord }) {
  const RES = {
    CONFORME:    { badge:'badge-green'  },
    NON_CONFORME:{ badge:'badge-red'    },
    EN_COURS:    { badge:'badge-yellow' },
  }
  const res = RES[doc.resultat]
  return (
    <div className="card p-4 hover:shadow-md transition-all">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center flex-shrink-0">
          <Clipboard size={18} className="text-purple-600"/>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {doc.pv_numero && <span className="font-mono font-bold text-slate-700 text-sm">{doc.pv_numero}</span>}
            {res && <span className={`badge ${res.badge} text-[10px]`}>{doc.resultat}</span>}
          </div>
          <div className="text-xs text-slate-400 mt-1 flex items-center gap-1">
            <Calendar size={10}/>{doc.date_inspection}
          </div>
          {doc.observations && (
            <p className="text-xs text-slate-500 mt-1 line-clamp-2">{doc.observations}</p>
          )}
        </div>
        <div className="flex gap-1">
          <button onClick={()=>onPdf(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600" title="PDF">
            <Download size={13}/>
          </button>
          <button onClick={()=>onWord(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600" title="Word">
            <FileText size={13}/>
          </button>
          <button onClick={()=>onEdit(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600"><Edit size={13}/></button>
          <button onClick={()=>onDelete(doc.id,'pv')} className="btn-ghost p-1.5 text-slate-400 hover:text-red-600"><Trash2 size={13}/></button>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function DocumentsPage() {
  const { user } = useAuthStore()
  const [tab,      setTab]      = useState('bsd')
  const [items,    setItems]    = useState([])
  const [loading,  setLoading]  = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing,  setEditing]  = useState(null)
  const [search,   setSearch]   = useState('')
  const [recuperateurs, setRecuperateurs] = useState([])
  const [dossiers,      setDossiers]      = useState([])
  const [eliminateurs,  setEliminateurs]  = useState([])

  const isRecup = user?.role === 'RECUPERATEUR'

  useEffect(() => {
    recupAPI.getAll().then(r => setRecuperateurs(r.data.results||r.data)).catch(()=>{})
    eliminateurAPI.getAll().then(r => setEliminateurs(r.data.results||r.data)).catch(()=>{})
    const p = { page_size: 200 }
    if (isRecup && user?.recuperateur_id) p.recuperateur = user.recuperateur_id
    tracaAPI.getAll(p).then(r => {
      const data = r.data.results || r.data
      setDossiers(data.filter(d => ['S','SD'].includes(d.classe_dechet)))
    }).catch(()=>{})
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const p = { page_size:100 }
      if (search) p.search = search
      if (isRecup && user?.recuperateur_id) p.recuperateur = user.recuperateur_id
      let res
      if (tab==='bsd')                       res = await bsdAPI.getAll(p)
      else if (tab==='dsd')                  res = await dsdAPI.getAll(p)
      else if (tab==='pv'||tab==='rapports') res = await pvAPI.getAll(p)
      setItems(res?.data?.results || res?.data || [])
    } catch { toast.error('Erreur chargement') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [tab, search])

  const handleDelete = async (id, type) => {
    if (!window.confirm('Supprimer ?')) return
    try {
      if (type==='bsd') await bsdAPI.delete(id)
      else if (type==='dsd') await dsdAPI.delete(id)
      else await pvAPI.delete(id)
      toast.success('Supprimé'); load()
    } catch { toast.error('Erreur') }
  }

  const handleBsdPdf = async (doc) => {
    try {
      const res = await bsdAPI.pdf(doc)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`${doc.numero||'BSD'}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BSD téléchargé')
    } catch { toast.error('Erreur PDF') }
  }

  const handleBsdWord = async (doc) => {
    try {
      const res = await bsdAPI.word(doc)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`${doc.numero||'BSD'}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BSD téléchargé (Word)')
    } catch { toast.error('Erreur Word') }
  }

  const handleDsdPdf = async (doc) => {
    try {
      const res = await dsdAPI.pdfById(doc.id)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`DSD_${doc.denomination}_${doc.annee}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('DSD téléchargé')
    } catch { toast.error('Erreur PDF') }
  }

  const handleDsdWord = async (doc) => {
    try {
      const res = await dsdAPI.wordById(doc.id)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`DSD_${doc.denomination}_${doc.annee}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('DSD téléchargé (Word)')
    } catch { toast.error('Erreur Word') }
  }

  const handlePvPdf = async (doc) => {
    try {
      const res = await pvAPI.pdfById(doc.id)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`PV_${doc.pv_numero||doc.id}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('PV téléchargé')
    } catch { toast.error('Erreur PDF') }
  }

  const handlePvWord = async (doc) => {
    try {
      const res = await pvAPI.wordById(doc.id)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`PV_${doc.pv_numero||doc.id}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('PV téléchargé (Word)')
    } catch { toast.error('Erreur Word') }
  }

  const handleSave  = () => { setShowForm(false); setEditing(null); load() }
  const handleEdit  = (item) => { setEditing(item); setShowForm(true) }

  const currentTab = TABS.find(t=>t.key===tab)
  const TabIcon    = currentTab?.icon || FileText

  const getBtnLabel = () => {
    if (tab==='bsd') return 'Nouveau BSD'
    if (tab==='dsd') return 'Nouvelle DSD'
    if (tab==='pv')  return 'Nouveau PV'
    return 'Nouveau rapport'
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <FileText size={24} className="text-primary-600"/> Documents et Rapports
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">BSD — DSD — Procès-Verbaux — Rapports</p>
        </div>
        <button onClick={()=>{setEditing(null);setShowForm(true)}} className="btn-primary">
          <Plus size={16}/> {getBtnLabel()}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 flex-wrap">
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button key={t.key} onClick={()=>{setTab(t.key);setItems([]);setSearch('')}}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all border-2
                ${tab===t.key
                  ?'bg-primary-600 text-white border-primary-600 shadow-sm'
                  :'border-[#E2E8F0] text-slate-600 hover:border-primary-300 bg-white dark:bg-[#16240D] dark:border-[#2B3D1E]'}`}>
              <Icon size={15}/> {t.label}
            </button>
          )
        })}
      </div>

      <div className="card p-3 bg-slate-50/50 flex items-center gap-3">
        <TabIcon size={15} className="text-primary-600 flex-shrink-0"/>
        <p className="text-sm text-slate-600">{currentTab?.desc}</p>
      </div>

      <div className="card p-3 flex gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/>
          <input value={search} onChange={e=>setSearch(e.target.value)}
            placeholder={`Rechercher dans les ${currentTab?.label}...`}
            className="input pl-9 text-sm"/>
          {search && (
            <button onClick={()=>setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
              <X size={13} className="text-slate-400"/>
            </button>
          )}
        </div>
      </div>

      {loading ? <Spinner/> : items.length===0 ? (
        <div className="card p-14 text-center">
          <TabIcon size={36} className="mx-auto mb-3 text-slate-200"/>
          <p className="font-semibold text-slate-400">Aucun {currentTab?.label} trouvé</p>
          <button onClick={()=>{setEditing(null);setShowForm(true)}} className="btn-primary mt-4">
            <Plus size={15}/> {getBtnLabel()}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {tab==='bsd'     && items.map(doc=><BSDCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handleBsdPdf} onWord={handleBsdWord}/>)}
          {tab==='dsd'     && items.map(doc=><DSDCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handleDsdPdf} onWord={handleDsdWord}/>)}
          {(tab==='pv'||tab==='rapports') && items.map(doc=><PVCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handlePvPdf} onWord={handlePvWord}/>)}
        </div>
      )}

      <Modal
        open={showForm}
        onClose={()=>{setShowForm(false);setEditing(null)}}
        title={editing ? `Modifier ${tab.toUpperCase()}` : getBtnLabel()}
        size={tab==='dsd' ? 'max-w-3xl' : 'max-w-2xl'}>
        {tab==='bsd' && (
          <BSDForm bsd={editing} recuperateurs={recuperateurs} dossiers={dossiers} currentUser={user}
            onSave={handleSave} onClose={()=>{setShowForm(false);setEditing(null)}}/>
        )}
        {tab==='dsd' && (
          <DSDForm dsd={editing} recuperateurs={recuperateurs} dossiers={dossiers} currentUser={user}
            onSave={handleSave} onClose={()=>{setShowForm(false);setEditing(null)}}/>
        )}
        {(tab==='pv'||tab==='rapports') && (
          <PVForm pv={editing} recuperateurs={recuperateurs} dossiers={dossiers} eliminateurs={eliminateurs} currentUser={user}
            onSave={handleSave} onClose={()=>{setShowForm(false);setEditing(null)}}/>
        )}
      </Modal>
    </div>
  )
}
