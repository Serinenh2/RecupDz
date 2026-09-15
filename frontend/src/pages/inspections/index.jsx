import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import {
  Plus, Search, X, Save, Edit, Trash2, Download,
  Shield, FileText, Clipboard, Calendar,
} from 'lucide-react'
import api from '../../api'
import { useAuthStore } from '../../store'
import DateInput from '../../components/common/DateInput'
import { formatDateFR } from '../../utils/formatDate'
import toast from 'react-hot-toast'
import { Can } from '../../components/guards'

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
const recupAPI       = { getAll: () => api.get('/recuperateurs/?page_size=200') }
const eliminateurAPI = { getAll: () => api.get('/operateurs/?type_operateur=ELIMINATEUR&page_size=200') }
const tracaAPI       = { getAll: (p) => api.get('/traceability/', { params: p }) }

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

function F({ label, req, children, col }) {
  return (
    <div className={col || ''}>
      <label className="label">{label}{req && <span className="text-red-500 ml-0.5">*</span>}</label>
      {children}
    </div>
  )
}

function DossierPicker({ dossiers = [], onSelect, label = 'Importer depuis un dossier de traçabilité (déchets spéciaux / dangereux)' }) {
  const [selected, setSelected] = useState('')

  const handleChange = (e) => {
    const id = e.target.value
    setSelected(id)
    const d = dossiers.find(x => String(x.id) === id)
    if (d) onSelect(d)
    setSelected('')
  }

  if (dossiers.length === 0) return null

  return (
    <div className="card p-3 bg-primary-50/50 border-primary-200 space-y-2">
      <label className="label flex items-center gap-1.5">
        <Shield size={12} className="text-primary-500"/> {label}
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
        <Can do={isEdit ? 'inspections.change_inspection' : 'inspections.add_inspection'}>
          <button type="submit" disabled={saving||generating} className="btn-primary">
            <Save size={15}/> {saving?'...':isEdit?'Mettre à jour':'Créer le PV'}
          </button>
        </Can>
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

// ── PV Card ───────────────────────────────────────────────────────────────────
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
            <Calendar size={10}/>{formatDateFR(doc.date_inspection)}
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
          <Can do="inspections.change_inspection">
            <button onClick={()=>onEdit(doc)} className="btn-ghost p-1.5 text-slate-400 hover:text-primary-600"><Edit size={13}/></button>
          </Can>
          <Can do="inspections.delete_inspection">
            <button onClick={()=>onDelete(doc.id)} className="btn-ghost p-1.5 text-slate-400 hover:text-red-600"><Trash2 size={13}/></button>
          </Can>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function InspectionsPage() {
  const { user } = useAuthStore()
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
      const p = { page_size: 100 }
      if (search) p.search = search
      if (isRecup && user?.recuperateur_id) p.recuperateur = user.recuperateur_id
      const res = await pvAPI.getAll(p)
      setItems(res?.data?.results || res?.data || [])
    } catch { toast.error('Erreur chargement') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [search])

  const handleDelete = async (id) => {
    if (!window.confirm('Supprimer ?')) return
    try {
      await pvAPI.delete(id)
      toast.success('Supprimé'); load()
    } catch { toast.error('Erreur') }
  }

  const handlePdf = async (doc) => {
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

  const handleWord = async (doc) => {
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

  const handleSave = () => { setShowForm(false); setEditing(null); load() }
  const handleEdit = (item) => { setEditing(item); setShowForm(true) }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Clipboard size={24} className="text-primary-600"/> Inspections
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Procès-verbaux de contrôle environnemental</p>
        </div>
        <Can do="inspections.add_inspection">
          <button onClick={()=>{setEditing(null);setShowForm(true)}} className="btn-primary">
            <Plus size={16}/> Nouveau PV
          </button>
        </Can>
      </div>

      <div className="card p-3 flex gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/>
          <input value={search} onChange={e=>setSearch(e.target.value)}
            placeholder="Rechercher un PV..."
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
          <Clipboard size={36} className="mx-auto mb-3 text-slate-200"/>
          <p className="font-semibold text-slate-400">Aucun PV trouvé</p>
          <Can do="inspections.add_inspection">
            <button onClick={()=>{setEditing(null);setShowForm(true)}} className="btn-primary mt-4">
              <Plus size={15}/> Nouveau PV
            </button>
          </Can>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map(doc=><PVCard key={doc.id} doc={doc} onEdit={handleEdit} onDelete={handleDelete} onPdf={handlePdf} onWord={handleWord}/>)}
        </div>
      )}

      <Modal
        open={showForm}
        onClose={()=>{setShowForm(false);setEditing(null)}}
        title={editing?.id ? 'Modifier le PV' : 'Nouveau PV'}
        size="max-w-2xl">
        <PVForm pv={editing} recuperateurs={recuperateurs} dossiers={dossiers} eliminateurs={eliminateurs} currentUser={user}
          onSave={handleSave} onClose={()=>{setShowForm(false);setEditing(null)}}/>
      </Modal>
    </div>
  )
}
