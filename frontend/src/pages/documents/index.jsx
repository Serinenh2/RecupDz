import { useEffect, useState, useMemo } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import {
  FileText, Plus, Search, X, Save, Edit, Trash2,
  Download, Shield, AlertTriangle, CheckCircle2,
  Clock, XCircle, Clipboard, BarChart3, Calendar, Truck, ShoppingCart, FileSignature, Receipt
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
const blAPI = {
  getAll:  (p)    => api.get('/bl/', { params: p }),
  create:  (d)    => api.post('/bl/', d),
  update:  (id,d) => api.patch(`/bl/${id}/`, d),
  delete:  (id)   => api.delete(`/bl/${id}/`),
  pdf:     (d)    => api.post('/bl/generate-bl/', d, { responseType:'blob' }),
  word:    (d)    => api.post('/bl/generate-bl-word/', d, { responseType:'blob' }),
}
const bcAPI = {
  getAll:  (p)    => api.get('/bc/', { params: p }),
  create:  (d)    => api.post('/bc/', d),
  update:  (id,d) => api.patch(`/bc/${id}/`, d),
  delete:  (id)   => api.delete(`/bc/${id}/`),
  pdf:     (d)    => api.post('/bc/generate-bc/', d, { responseType:'blob' }),
  word:    (d)    => api.post('/bc/generate-bc-word/', d, { responseType:'blob' }),
}
const recupAPI = { getAll: () => api.get('/recuperateurs/?page_size=200') }
const tracaAPI = { getAll: (p) => api.get('/traceability/', { params: p }) }
const eliminateurAPI = { getAll: () => api.get('/operateurs/?type_operateur=ELIMINATEUR&page_size=200') }
const destinatairesAPI = {
  getAll: (type) => api.get('/operateurs/', { params: { type_operateur: type, page_size: 200 } }),
}

const TABS = [
  { key:'bl',       label:'BL',       icon:Truck,         desc:"Bon de Livraison — émis par le récupérateur vers l'éliminateur ou le valorisateur" },
  { key:'bc',       label:'BC',       icon:ShoppingCart,  desc:"Bon de Commande — document commercial avec prix unitaires, TVA et Total TTC" },
  { key:'proforma', label:'Proforma', icon:FileSignature, desc:'Proforma — devis préalable, même contenu que le Bon de Commande' },
  { key:'bsd',      label:'BSD',      icon:FileText,      desc:'Bordereaux de Suivi des Déchets — documents de traçabilité obligatoires' },
  { key:'dsd',      label:'DSD',      icon:AlertTriangle, desc:'Déclarations des Déchets Spéciaux Dangereux — formulaire annuel officiel' },
  { key:'facture',  label:'Facture',  icon:Receipt,       desc:'Facture — document de facturation, même contenu que le Bon de Commande' },
  { key:'pv',       label:'PV',       icon:Clipboard,     desc:'Procès-Verbaux de contrôle environnemental' },
  { key:'rapports', label:'Rapports', icon:BarChart3,     desc:'Rapports environnementaux périodiques' },
]
const BL_ST = {
  BROUILLON: { label:'Brouillon', badge:'badge-gray',   icon:Clock        },
  EMIS:      { label:'Émis',      badge:'badge-blue',   icon:FileText     },
  VALIDE:    { label:'Validé',    badge:'badge-green',  icon:CheckCircle2 },
  ARCHIVE:   { label:'Archivé',   badge:'badge-gray',   icon:XCircle      },
}
const BC_ST = {
  BROUILLON: { label:'Brouillon', badge:'badge-gray',   icon:Clock        },
  EMIS:      { label:'Émis',      badge:'badge-blue',   icon:FileText     },
  VALIDE:    { label:'Validé',    badge:'badge-green',  icon:CheckCircle2 },
  ARCHIVE:   { label:'Archivé',   badge:'badge-gray',   icon:XCircle      },
}
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

const DECHETS_MENAGERS = [
  'Déchets ménagers mélangés',
  'Papier et carton',
  'Verre',
  'Plastiques divers',
  'Métaux ferreux',
  'Métaux non ferreux',
  'Textiles et vêtements',
  'Déchets verts / de jardin',
  "Déchets d'emballage",
  'Encombrants ménagers',
  'Déchets alimentaires',
  'Bois et dérivés',
  "Déchets d'équipements électriques et électroniques (DEEE)",
  'Déchets inertes de chantier',
]

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

// ── Description Déchet Picker (full nomenclature, used by BL lines) ──────────
function DescriptionDechetPicker({ value, onChange }) {
  const [search, setSearch] = useState(value || '')
  const [open,   setOpen]   = useState(false)

  useEffect(() => { setSearch(value || '') }, [value])

  const filtered = useMemo(() =>
    NOMENCLATURE
      .filter(n =>
        !search ||
        n.code.includes(search.split(' ')[0]) ||
        n.nom_fr.toLowerCase().includes(search.toLowerCase())
      )
      .slice(0, 40)
  , [search])

  const select = (n) => {
    setSearch(n.nom_fr)
    setOpen(false)
    onChange(n.nom_fr)
  }

  return (
    <div className="relative">
      <input
        value={search}
        onChange={e => { setSearch(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Plastique PET..."
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

// ── BL Form (Bon de Livraison) ─────────────────────────────────────────────────
function BLForm({ bl, currentUser, onSave, onClose }) {
  const isEdit = !!bl?.id
  const { register, handleSubmit, watch, setValue, control, reset } = useForm({
    defaultValues: bl || {
      statut: 'BROUILLON',
      destinataire_type: 'ELIMINATEUR',
      date_livraison: new Date().toISOString().split('T')[0],
      mode_livraison: 'ENLEVEMENT',
      lignes: [{ ref_article:'', description:'', quantite:'', unite:'KG', stockage:'' }],
    }
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'lignes' })
  const [saving,       setSaving]       = useState(false)
  const [generating,   setGenerating]   = useState(false)
  const [destinataires,setDestinataires]= useState([])
  const destinataireType = watch('destinataire_type')

  useEffect(() => { if (bl) reset(bl) }, [bl])

  useEffect(() => {
    if (!destinataireType) return
    destinatairesAPI.getAll(destinataireType).then(r => setDestinataires(r.data.results || r.data)).catch(()=>{})
  }, [destinataireType])

  const onSubmit = async (data) => {
    setSaving(true)
    if (!data.montant_reference && data.montant_reference !== 0) delete data.montant_reference
    try {
      if (isEdit) { await blAPI.update(bl.id, data); toast.success('BL mis à jour') }
      else        { await blAPI.create(data);          toast.success('BL créé') }
      onSave()
    } catch { toast.error('Erreur') }
    finally { setSaving(false) }
  }

  const buildBlData = () => ({
    numero:                 bl?.numero || '',
    recuperateur:           bl?.recuperateur || currentUser?.recuperateur_id,
    destinataire_type:      watch('destinataire_type'),
    destinataire:           watch('destinataire'),
    ref_client:             watch('ref_client'),
    client_rc:              watch('client_rc'),
    client_nif:             watch('client_nif'),
    client_numero_article:  watch('client_numero_article'),
    client_nis:             watch('client_nis'),
    client_telephone:       watch('client_telephone'),
    client_fax:             watch('client_fax'),
    client_email:           watch('client_email'),
    pieces_liees:           watch('pieces_liees'),
    mode_livraison:         watch('mode_livraison'),
    montant_reference:      watch('montant_reference'),
    date_livraison:         watch('date_livraison'),
    lignes:                 watch('lignes'),
    chauffeur_nom:          watch('chauffeur_nom'),
    camion_immatriculation: watch('camion_immatriculation'),
    statut:                 watch('statut'),
  })

  const downloadPdf = async () => {
    setGenerating(true)
    try {
      const formData = buildBlData()
      const res = await blAPI.pdf(formData)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download', `${formData.numero||'BL'}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BL téléchargé !')
    } catch { toast.error('Erreur génération PDF') }
    finally { setGenerating(false) }
  }

  const downloadWord = async () => {
    setGenerating(true)
    try {
      const formData = buildBlData()
      const res = await blAPI.word(formData)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download', `${formData.numero||'BL'}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BL téléchargé (Word) !')
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
      <div className="card p-3 bg-primary-50 border-primary-200 flex items-center gap-2">
        <Shield size={14} className="text-primary-600 flex-shrink-0"/>
        <p className="text-sm font-semibold text-primary-800">Émetteur : {currentUser?.recuperateur_nom}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <F label="Destinataire — type" req>
          <select {...register('destinataire_type',{required:true})} className="input"
            onChange={e=>{ setValue('destinataire_type', e.target.value); setValue('destinataire','') }}>
            <option value="ELIMINATEUR">Éliminateur de déchets</option>
            <option value="VALORISATEUR">Valorisateur de déchets</option>
            <option value="CET">Centre d'Enfouissement Technique (CET)</option>
          </select>
        </F>
        <F label={watch('destinataire_type')==='CET' ? 'CET — nom (commune)' : 'Destinataire — raison sociale'} req>
          <select {...register('destinataire',{required:true})} className="input">
            <option value="">-- Sélectionner --</option>
            {destinataires.map(d => <option key={d.id} value={d.id}>{d.raison_sociale}</option>)}
          </select>
        </F>
      </div>

      <div className="card p-4 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Client (facturation)</p>
        <div className="grid grid-cols-2 gap-3">
          <F label="Réf. client"><input {...register('ref_client')} className="input" placeholder="Code court (ex: FOSSIL)..."/></F>
          <F label="N° RC client"><input {...register('client_rc')} className="input"/></F>
          <F label="NIF client"><input {...register('client_nif')} className="input"/></F>
          <F label="N° Article client"><input {...register('client_numero_article')} className="input"/></F>
          <F label="N° I.S. client"><input {...register('client_nis')} className="input"/></F>
          <F label="Tél. client"><input {...register('client_telephone')} className="input"/></F>
          <F label="Fax client"><input {...register('client_fax')} className="input"/></F>
          <F label="Email client"><input {...register('client_email')} type="email" className="input"/></F>
          <F label="Pièces liées"><input {...register('pieces_liees')} className="input" placeholder="Réf. bon de commande, soumission..."/></F>
          <F label="Mode de livraison">
            <select {...register('mode_livraison')} className="input">
              <option value="ENLEVEMENT">Enlèvement</option>
              <option value="LIVRAISON">Livraison</option>
            </select>
          </F>
          <F label="Montant de référence (DZD)"><input {...register('montant_reference')} type="number" step="0.01" className="input" placeholder="0.00"/></F>
        </div>
      </div>

      {watch('destinataire_type') === 'CET' && (
        <div className="card p-3 bg-amber-50 border border-amber-300 flex items-start gap-2 rounded-xl">
          <AlertTriangle size={15} className="text-amber-600 flex-shrink-0 mt-0.5"/>
          <div className="text-xs text-amber-800 space-y-0.5">
            <p className="font-semibold">Réglementation CET — Loi n°01-19 / Décret n°06-104</p>
            <p>Les Centres d'Enfouissement Technique <strong>n'acceptent pas</strong> les déchets spéciaux (S) ni les déchets spéciaux dangereux (SD/DSD). Seuls les déchets ménagers et assimilés sont autorisés.</p>
          </div>
        </div>
      )}

      <F label="Date de livraison" req>
        <DateInput value={watch('date_livraison')||''} onChange={v=>setValue('date_livraison',v)}/>
      </F>

      <div className="card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Description (Nature des déchets)</p>
          <button type="button" onClick={()=>append({ ref_article:'', description:'', quantite:'', unite:'KG', stockage:'' })}
            className="text-xs font-semibold text-primary-600 hover:underline">+ Ajouter une ligne</button>
        </div>
        {fields.map((f, i) => (
          <div key={f.id} className="space-y-2 pb-3 border-b border-[#E2E8F0] last:border-0">
            <div className="grid grid-cols-12 gap-2 items-end">
              <div className="col-span-3">
                {i===0 && <label className="label text-[10px]">Réf. article</label>}
                <input {...register(`lignes.${i}.ref_article`)} className="input" placeholder="Réf..."/>
              </div>
              <div className="col-span-9">
                {i===0 && <label className="label text-[10px]">Description (Nature des déchets)</label>}
                {watch('destinataire_type') === 'CET' ? (
                  <select {...register(`lignes.${i}.description`)} className="input">
                    <option value="">— Sélectionner la désignation —</option>
                    {DECHETS_MENAGERS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                ) : (
                  <>
                    <DescriptionDechetPicker
                      value={watch(`lignes.${i}.description`) || ''}
                      onChange={text => setValue(`lignes.${i}.description`, text)}
                    />
                    <input type="hidden" {...register(`lignes.${i}.description`)} />
                  </>
                )}
              </div>
            </div>
            <div className="grid grid-cols-12 gap-2 items-end">
              <div className="col-span-3">
                {i===0 && <label className="label text-[10px]">Quantité</label>}
                <input {...register(`lignes.${i}.quantite`)} className="input" type="number"/>
              </div>
              <div className="col-span-3">
                {i===0 && <label className="label text-[10px]">Unité</label>}
                <select {...register(`lignes.${i}.unite`)} className="input">
                  <option value="KG">KG</option>
                  <option value="TONNE">Tonne</option>
                  <option value="M3">m³</option>
                  <option value="LITRE">Litre</option>
                  <option value="UNITE">Unité</option>
                </select>
              </div>
              <div className="col-span-4">
                {i===0 && <label className="label text-[10px]">Stockage</label>}
                <input {...register(`lignes.${i}.stockage`)} className="input" placeholder="Ibc, Fût..."/>
              </div>
              <div className="col-span-2 flex justify-end">
                {fields.length>1 && (
                  <button type="button" onClick={()=>remove(i)} className="btn-ghost p-1.5 text-red-400 hover:text-red-600">
                    <Trash2 size={14}/>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card p-4 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Chauffeur</p>
        <div className="grid grid-cols-2 gap-3">
          <F label="Nom de chauffeur"><input {...register('chauffeur_nom')} className="input"/></F>
          <F label="Immatriculation de camion"><input {...register('camion_immatriculation')} className="input"/></F>
        </div>
      </div>

      <F label="Statut">
        <select {...register('statut')} className="input">
          {Object.entries(BL_ST).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}
        </select>
      </F>

      <div className="flex gap-3 pt-2 border-t border-[#E2E8F0]">
        <button type="submit" disabled={saving||generating} className="btn-primary">
          <Save size={15}/> {saving?'Enregistrement...':isEdit?'Mettre à jour':'Créer le BL'}
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

function BLCard({ doc, onEdit, onDelete, onPdf, onWord }) {
  const st = BL_ST[doc.statut] || BL_ST.BROUILLON
  const Icon = st.icon
  return (
    <div className="card p-4 hover:shadow-md transition-all">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-primary-50 flex items-center justify-center flex-shrink-0">
          <Truck size={18} className="text-primary-600"/>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-bold text-primary-700 text-sm">{doc.numero}</span>
            <span className={`badge ${st.badge} text-[10px]`}><Icon size={9} className="mr-0.5"/>{st.label}</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold border bg-slate-50 text-slate-600 border-slate-200">
              {doc.destinataire_type_display || doc.destinataire_type}
            </span>
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-300 mt-0.5">
            {doc.destinataire_nom}
          </p>
          <div className="flex flex-wrap gap-x-4 text-xs text-slate-400 mt-1">
            <span>{(doc.lignes||[]).length} ligne(s)</span>
            <span className="flex items-center gap-1"><Calendar size={10}/>{doc.date_livraison}</span>
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
          <button onClick={()=>onDelete(doc.id,'bl')} className="btn-ghost p-1.5 text-slate-400 hover:text-red-500">
            <Trash2 size={13}/>
          </button>
        </div>
      </div>
    </div>
  )
}

// ── BC Form (Bon de Commande) ─────────────────────────────────────────────────
function BCForm({ bc, currentUser, onSave, onClose, typeDocument = 'BC' }) {
  const isEdit = !!bc?.id
  const isFacture = typeDocument === 'FACTURE'
  const docLabel = typeDocument === 'PROFORMA' ? 'Proforma' : typeDocument === 'FACTURE' ? 'Facture' : 'BC'
  const { register, handleSubmit, watch, setValue, control, reset } = useForm({
    defaultValues: bc || {
      statut: 'BROUILLON',
      type_document: typeDocument,
      date_commande: new Date().toISOString().split('T')[0],
      tva_pct: 19,
      lignes: [{ ref_article:'', description:'', quantite:'', unite:'KG', prix_unitaire:'', remise_pct:0, tva_pct:'' }],
    }
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'lignes' })
  const [saving,     setSaving]     = useState(false)
  const [generating, setGenerating] = useState(false)

  useEffect(() => { if (bc) reset(bc) }, [bc])

  const calcTotaux = () => {
    const lignes  = watch('lignes') || []
    const tva_pct = parseFloat(watch('tva_pct') || 19)
    let ht = 0, tva = 0
    lignes.forEach(l => {
      const qte    = parseFloat(l.quantite || 0)
      const pu     = parseFloat(l.prix_unitaire || 0)
      const remise = parseFloat(l.remise_pct || 0)
      const ligneTva = (l.tva_pct !== undefined && l.tva_pct !== '') ? parseFloat(l.tva_pct) : tva_pct
      const ligneHt  = qte * pu * (1 - remise / 100)
      ht  += ligneHt
      tva += ligneHt * ligneTva / 100
    })
    return { ht, tva, ttc: ht + tva }
  }

  const { ht, tva, ttc } = calcTotaux()
  const fmt = (n) => n.toLocaleString('fr-FR', { minimumFractionDigits: 2 })

  const onSubmit = async (data) => {
    setSaving(true)
    if (!isEdit) data.type_document = typeDocument
    try {
      if (isEdit) { await bcAPI.update(bc.id, data); toast.success(`${docLabel} mis${isFacture?'e':''} à jour`) }
      else        { await bcAPI.create(data);          toast.success(`${docLabel} créé${isFacture?'e':''}`) }
      onSave()
    } catch { toast.error('Erreur') }
    finally { setSaving(false) }
  }

  const buildBcData = () => ({
    numero:               bc?.numero || '',
    type_document:        bc?.type_document || typeDocument,
    recuperateur:         bc?.recuperateur || currentUser?.recuperateur_id,
    ref_client:           watch('ref_client'),
    client_nom:           watch('client_nom'),
    client_adresse:       watch('client_adresse'),
    client_rc:            watch('client_rc'),
    client_nif:           watch('client_nif'),
    client_numero_article:watch('client_numero_article'),
    client_nis:           watch('client_nis'),
    client_telephone:     watch('client_telephone'),
    client_fax:           watch('client_fax'),
    client_email:         watch('client_email'),
    date_commande:        watch('date_commande'),
    date_echeance:        watch('date_echeance'),
    pieces_liees:         watch('pieces_liees'),
    mode_paiement:        watch('mode_paiement'),
    reference_paiement:   watch('reference_paiement'),
    tva_pct:              watch('tva_pct'),
    lignes:               watch('lignes'),
    statut:               watch('statut'),
  })

  const downloadPdf = async () => {
    setGenerating(true)
    try {
      const res = await bcAPI.pdf(buildBcData())
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download', `${bc?.numero||(docLabel)}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success(`${docLabel} téléchargé${isFacture?'e':''} !`)
    } catch { toast.error('Erreur génération PDF') }
    finally { setGenerating(false) }
  }

  const downloadWord = async () => {
    setGenerating(true)
    try {
      const res = await bcAPI.word(buildBcData())
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download', `${bc?.numero||(docLabel)}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success(`${docLabel} téléchargé${isFacture?'e':''} (Word) !`)
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
      <div className="card p-3 bg-primary-50 border-primary-200 flex items-center gap-2">
        <Shield size={14} className="text-primary-600 flex-shrink-0"/>
        <p className="text-sm font-semibold text-primary-800">Émetteur : {currentUser?.recuperateur_nom}</p>
      </div>

      {/* Client */}
      <div className="card p-4 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Client</p>
        <div className="grid grid-cols-2 gap-3">
          <F label="Réf. client">
            <input {...register('ref_client')} className="input" placeholder="Code court (ex: FOSSIL)..."/>
          </F>
          <F label="Nom de client" req>
            <input {...register('client_nom', {required:true})} className="input" placeholder="Raison sociale..."/>
          </F>
          <F label="Adresse client">
            <textarea {...register('client_adresse')} className="input" rows={2} placeholder="Adresse..."/>
          </F>
          <F label="N° RC client">
            <input {...register('client_rc')} className="input"/>
          </F>
          <F label="NIF client">
            <input {...register('client_nif')} className="input"/>
          </F>
          <F label="N° Article client">
            <input {...register('client_numero_article')} className="input"/>
          </F>
          <F label="N° I.S. client">
            <input {...register('client_nis')} className="input"/>
          </F>
          <F label="Tél. client">
            <input {...register('client_telephone')} className="input"/>
          </F>
          <F label="Fax client">
            <input {...register('client_fax')} className="input"/>
          </F>
          <F label="Email client">
            <input {...register('client_email')} type="email" className="input"/>
          </F>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <F label="Date de commande" req>
          <DateInput value={watch('date_commande')||''} onChange={v=>setValue('date_commande',v)}/>
        </F>
        <F label="Échéance">
          <DateInput value={watch('date_echeance')||''} onChange={v=>setValue('date_echeance',v)}/>
        </F>
        <F label="Pièces liées">
          <input {...register('pieces_liees')} className="input" placeholder="Réf. devis, proforma..."/>
        </F>
      </div>

      {isFacture && (
        <div className="grid grid-cols-2 gap-3">
          <F label="Mode de paiement">
            <select {...register('mode_paiement')} className="input">
              <option value="">--</option>
              <option value="Espèces">Espèces</option>
              <option value="Chèque">Chèque</option>
              <option value="Virement">Virement</option>
              <option value="Traite">Traite</option>
            </select>
          </F>
          <F label="Référence de paiement">
            <input {...register('reference_paiement')} className="input" placeholder="N° chèque, virement..."/>
          </F>
        </div>
      )}

      {/* Lignes */}
      <div className="card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">Description (Nature des déchets)</p>
          <button type="button"
            onClick={()=>append({ ref_article:'', description:'', quantite:'', unite:'KG', prix_unitaire:'', remise_pct:0, tva_pct:'' })}
            className="text-xs font-semibold text-primary-600 hover:underline">+ Ajouter une ligne</button>
        </div>

        {fields.map((f, i) => {
          const qte    = parseFloat(watch(`lignes.${i}.quantite`)||0)
          const pu     = parseFloat(watch(`lignes.${i}.prix_unitaire`)||0)
          const remise = parseFloat(watch(`lignes.${i}.remise_pct`)||0)
          const ligneHt = qte * pu * (1 - remise / 100)
          return (
          <div key={f.id} className="space-y-2 pb-3 border-b border-[#E2E8F0] last:border-0">
            <div className="grid grid-cols-12 gap-2 items-end">
              <div className="col-span-2">
                {i===0 && <label className="label text-[10px]">Réf. article</label>}
                <input {...register(`lignes.${i}.ref_article`)} className="input" placeholder="Réf..."/>
              </div>
              <div className="col-span-4">
                {i===0 && <label className="label text-[10px]">Description</label>}
                <select {...register(`lignes.${i}.description`)} className="input">
                  <option value="">— Sélectionner —</option>
                  {DECHETS_MENAGERS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                {i===0 && <label className="label text-[10px]">Quantité</label>}
                <input {...register(`lignes.${i}.quantite`)} className="input" type="number" step="any"/>
              </div>
              <div className="col-span-2">
                {i===0 && <label className="label text-[10px]">Unité</label>}
                <select {...register(`lignes.${i}.unite`)} className="input">
                  <option value="KG">KG</option>
                  <option value="TONNE">Tonne</option>
                  <option value="M3">m³</option>
                  <option value="LITRE">Litre</option>
                  <option value="UNITE">Unité</option>
                </select>
              </div>
              <div className="col-span-2">
                {i===0 && <label className="label text-[10px]">Prix unit. (DZ)</label>}
                <input {...register(`lignes.${i}.prix_unitaire`)} className="input" type="number" step="any" placeholder="0.00"/>
              </div>
            </div>
            <div className="grid grid-cols-12 gap-2 items-end">
              <div className="col-span-2">
                {i===0 && <label className="label text-[10px]">Remise %</label>}
                <input {...register(`lignes.${i}.remise_pct`)} className="input" type="number" step="0.01" placeholder="0.00"/>
              </div>
              <div className="col-span-2">
                {i===0 && <label className="label text-[10px]">Tva %</label>}
                <input {...register(`lignes.${i}.tva_pct`)} className="input" type="number" step="0.01" placeholder={watch('tva_pct')||'19'}/>
              </div>
              <div className="col-span-6">
                {i===0 && <label className="label text-[10px]">Total HT</label>}
                <div className="input bg-slate-50 text-slate-500 text-xs flex items-center">
                  {fmt(ligneHt)} DZ
                </div>
              </div>
              <div className="col-span-2 flex justify-end">
                {fields.length > 1 && (
                  <button type="button" onClick={()=>remove(i)} className="btn-ghost p-1.5 text-red-400 hover:text-red-600">
                    <Trash2 size={14}/>
                  </button>
                )}
              </div>
            </div>
          </div>
        )})}

        {/* Récapitulatif */}
        <div className="mt-2 pt-3 border-t border-[#E2E8F0] flex flex-col items-end gap-1 text-sm">
          <div className="flex gap-6">
            <span className="text-slate-500">Total HT</span>
            <span className="font-semibold w-28 text-right">{fmt(ht)} DZ</span>
          </div>
          <div className="flex gap-6 items-center">
            <span className="text-slate-500">TVA</span>
            <div className="flex items-center gap-1">
              <input {...register('tva_pct')} type="number" className="input w-16 text-sm py-1" step="0.01"/>
              <span className="text-slate-400 text-xs">%</span>
              <span className="font-semibold w-28 text-right">{fmt(tva)} DZ</span>
            </div>
          </div>
          <div className="flex gap-6 font-bold text-primary-700">
            <span>Total TTC</span>
            <span className="w-28 text-right">{fmt(ttc)} DZ</span>
          </div>
        </div>
      </div>

      <F label="Statut">
        <select {...register('statut')} className="input">
          {Object.entries(BC_ST).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}
        </select>
      </F>

      <div className="flex gap-3 pt-2 border-t border-[#E2E8F0]">
        <button type="submit" disabled={saving||generating} className="btn-primary">
          <Save size={15}/> {saving?'Enregistrement...':isEdit?'Mettre à jour':`Créer ${isFacture?'la':'le'} ${docLabel}`}
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

function BCCard({ doc, onEdit, onDelete, onPdf, onWord }) {
  const st   = BC_ST[doc.statut] || BC_ST.BROUILLON
  const Icon = st.icon
  const total = (doc.lignes||[]).reduce((acc, l) =>
    acc + (parseFloat(l.quantite||0) * parseFloat(l.prix_unitaire||0)), 0)
  return (
    <div className="card p-4 hover:shadow-md transition-all">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center flex-shrink-0">
          <ShoppingCart size={18} className="text-emerald-600"/>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-bold text-emerald-700 text-sm">{doc.numero}</span>
            <span className={`badge ${st.badge} text-[10px]`}><Icon size={9} className="mr-0.5"/>{st.label}</span>
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-300 mt-0.5">{doc.client_nom || '—'}</p>
          <div className="flex flex-wrap gap-x-4 text-xs text-slate-400 mt-1">
            <span>{(doc.lignes||[]).length} ligne(s)</span>
            <span className="flex items-center gap-1"><Calendar size={10}/>{doc.date_commande}</span>
            {total > 0 && <span className="font-semibold text-emerald-600">TTC ≈ {(total * (1 + parseFloat(doc.tva_pct||19)/100)).toLocaleString('fr-FR',{minimumFractionDigits:2})} DZ</span>}
          </div>
        </div>
        <div className="flex gap-1 flex-shrink-0">
          <button onClick={()=>onPdf(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-emerald-600" title="PDF"><Download size={13}/></button>
          <button onClick={()=>onWord(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-emerald-600" title="Word"><FileText size={13}/></button>
          <button onClick={()=>onEdit(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-emerald-600"><Edit size={13}/></button>
          <button onClick={()=>onDelete(doc.id,'bc')} className="btn-ghost p-1.5 text-slate-400 hover:text-red-500"><Trash2 size={13}/></button>
        </div>
      </div>
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
  const [tab,      setTab]      = useState('bl')
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
      if (tab==='bl')                        res = await blAPI.getAll(p)
      else if (tab==='bc')                   res = await bcAPI.getAll({ ...p, type_document:'BC' })
      else if (tab==='proforma')             res = await bcAPI.getAll({ ...p, type_document:'PROFORMA' })
      else if (tab==='facture')              res = await bcAPI.getAll({ ...p, type_document:'FACTURE' })
      else if (tab==='bsd')                  res = await bsdAPI.getAll(p)
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
      if (type==='bl')       await blAPI.delete(id)
      else if (type==='bc' || type==='proforma' || type==='facture') await bcAPI.delete(id)
      else if (type==='bsd') await bsdAPI.delete(id)
      else if (type==='dsd') await dsdAPI.delete(id)
      else                   await pvAPI.delete(id)
      toast.success('Supprimé'); load()
    } catch { toast.error('Erreur') }
  }

  const handleBlPdf = async (doc) => {
    try {
      const res = await blAPI.pdf(doc)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`${doc.numero||'BL'}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BL téléchargé')
    } catch { toast.error('Erreur PDF') }
  }

  const handleBcPdf = async (doc) => {
    try {
      const res = await bcAPI.pdf(doc)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/pdf'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`${doc.numero||'BC'}.pdf`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BC téléchargé')
    } catch { toast.error('Erreur PDF') }
  }

  const handleBcWord = async (doc) => {
    try {
      const res = await bcAPI.word(doc)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`${doc.numero||'BC'}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BC téléchargé (Word)')
    } catch { toast.error('Erreur Word') }
  }

  const handleBlWord = async (doc) => {
    try {
      const res = await blAPI.word(doc)
      const url = window.URL.createObjectURL(new Blob([res.data],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}))
      const a   = document.createElement('a')
      a.href = url; a.setAttribute('download',`${doc.numero||'BL'}.docx`)
      document.body.appendChild(a); a.click(); a.remove()
      window.URL.revokeObjectURL(url)
      toast.success('BL téléchargé (Word)')
    } catch { toast.error('Erreur Word') }
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
    if (tab==='bl')  return 'Nouveau BL'
    if (tab==='bc')  return 'Nouveau BC'
    if (tab==='proforma') return 'Nouveau Proforma'
    if (tab==='facture') return 'Nouvelle Facture'
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
          {tab==='bl'      && items.map(doc=><BLCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handleBlPdf} onWord={handleBlWord}/>)}
          {(tab==='bc'||tab==='proforma'||tab==='facture') && items.map(doc=><BCCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handleBcPdf} onWord={handleBcWord}/>)}
          {tab==='bsd'     && items.map(doc=><BSDCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handleBsdPdf} onWord={handleBsdWord}/>)}
          {tab==='dsd'     && items.map(doc=><DSDCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handleDsdPdf} onWord={handleDsdWord}/>)}
          {(tab==='pv'||tab==='rapports') && items.map(doc=><PVCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handlePvPdf} onWord={handlePvWord}/>)}
        </div>
      )}

      <Modal
        open={showForm}
        onClose={()=>{setShowForm(false);setEditing(null)}}
        title={editing ? `Modifier ${tab.toUpperCase()}` : getBtnLabel()}
        size={tab==='dsd' || tab==='bc' || tab==='proforma' || tab==='facture' ? 'max-w-3xl' : 'max-w-2xl'}>
        {tab==='bl' && (
          <BLForm bl={editing} currentUser={user}
            onSave={handleSave} onClose={()=>{setShowForm(false);setEditing(null)}}/>
        )}
        {(tab==='bc'||tab==='proforma'||tab==='facture') && (
          <BCForm bc={editing} currentUser={user}
            typeDocument={tab==='proforma' ? 'PROFORMA' : tab==='facture' ? 'FACTURE' : 'BC'}
            onSave={handleSave} onClose={()=>{setShowForm(false);setEditing(null)}}/>
        )}
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
