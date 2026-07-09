import { useEffect, useState, useRef, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import {
  FolderOpen, Upload, X, Search, Download, Trash2,
  Edit, Eye, FileText, File, Image, Archive,
  Plus, Save, Calendar, Tag, User, Filter,
  ChevronDown, AlertTriangle, CheckCircle2
} from 'lucide-react'
import api from '../../api'
import { useAuthStore } from '../../store'
import toast from 'react-hot-toast'

// ── API ───────────────────────────────────────────────────────────────────────
const archiveAPI = {
  getAll:  (p)    => api.get('/archive/', { params: p }),
  create:  (d)    => api.post('/archive/', d, { headers: { 'Content-Type': 'multipart/form-data' } }),
  update:  (id,d) => api.patch(`/archive/${id}/`, d, { headers: { 'Content-Type': 'multipart/form-data' } }),
  delete:  (id)   => api.delete(`/archive/${id}/`),
}

// ── Constants ─────────────────────────────────────────────────────────────────
const CATEGORIES = [
  { value: 'AGREMENT',       label: 'Agrément',                    color: 'bg-primary-100 text-primary-700'    },
  { value: 'AUTORISATION',   label: 'Autorisation environnementale',color: 'bg-green-100 text-green-700'  },
  { value: 'CONTRAT',        label: 'Contrat',                     color: 'bg-violet-100 text-violet-700' },
  { value: 'RAPPORT',        label: 'Rapport',                     color: 'bg-amber-100 text-amber-700'  },
  { value: 'DECLARATION',    label: 'Déclaration',                 color: 'bg-orange-100 text-orange-700' },
  { value: 'CORRESPONDANCE', label: 'Correspondance officielle',   color: 'bg-teal-100 text-teal-700'    },
  { value: 'JURIDIQUE',      label: 'Document juridique',          color: 'bg-red-100 text-red-700'      },
  { value: 'TECHNIQUE',      label: 'Document technique',          color: 'bg-slate-100 text-slate-700'  },
  { value: 'PROFORMA',       label: 'Proforma',                    color: 'bg-fuchsia-100 text-fuchsia-700' },
  { value: 'BC',             label: 'Bon de Commande',             color: 'bg-emerald-100 text-emerald-700' },
  { value: 'BL',             label: 'Bon de Livraison',            color: 'bg-sky-100 text-sky-700'      },
  { value: 'FACTURE',        label: 'Facture',                     color: 'bg-rose-100 text-rose-700'    },
  { value: 'AUTRE',          label: 'Autre',                       color: 'bg-gray-100 text-gray-600'    },
]

const EXT_ICONS = {
  pdf:  { icon: FileText, color: 'text-red-500',    bg: 'bg-red-50'    },
  doc:  { icon: FileText, color: 'text-primary-500',   bg: 'bg-primary-50'   },
  docx: { icon: FileText, color: 'text-primary-500',   bg: 'bg-primary-50'   },
  xls:  { icon: FileText, color: 'text-green-500',  bg: 'bg-green-50'  },
  xlsx: { icon: FileText, color: 'text-green-500',  bg: 'bg-green-50'  },
  png:  { icon: Image,    color: 'text-purple-500', bg: 'bg-purple-50' },
  jpg:  { icon: Image,    color: 'text-purple-500', bg: 'bg-purple-50' },
  jpeg: { icon: Image,    color: 'text-purple-500', bg: 'bg-purple-50' },
  zip:  { icon: Archive,  color: 'text-amber-500',  bg: 'bg-amber-50'  },
  rar:  { icon: Archive,  color: 'text-amber-500',  bg: 'bg-amber-50'  },
}

function getExtCfg(ext) {
  return EXT_ICONS[ext?.toLowerCase()] || { icon: File, color: 'text-slate-500', bg: 'bg-slate-50' }
}

function getCatCfg(cat) {
  return CATEGORIES.find(c => c.value === cat) || CATEGORIES[CATEGORIES.length - 1]
}

// Documents générés automatiquement à la validation d'un Proforma/BC/BL/Facture
// portent un tag interne 'dossier:<uuid>' — utilisé pour les regrouper, mais
// caché de l'affichage des tags (avec le tag 'source:...' associé).
const INTERNAL_TAG_PREFIXES = ['dossier:', 'source:']
function visibleTags(doc) {
  if (!doc.tags) return []
  return doc.tags.split(',').map(t => t.trim()).filter(t => t && !INTERNAL_TAG_PREFIXES.some(p => t.startsWith(p)))
}
function getDossierId(doc) {
  if (!doc.tags) return null
  const tag = doc.tags.split(',').map(t => t.trim()).find(t => t.startsWith('dossier:'))
  return tag ? tag.slice('dossier:'.length) : null
}

function formatDate(str) {
  if (!str) return '—'
  return new Date(str).toLocaleDateString('fr-DZ', { day:'2-digit', month:'2-digit', year:'numeric' })
}

function Spinner() {
  return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// ── Upload Zone ───────────────────────────────────────────────────────────────
function UploadZone({ onFileSelect, file }) {
  const [dragging, setDragging] = useState(false)
  const inputRef   = useRef()

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFileSelect(f)
  }

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
        ${dragging
          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
          : file
            ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-900/20'
            : 'border-[#E2E8F0] hover:border-primary-300 hover:bg-primary-50/50 dark:border-[#2B3D1E]'
        }`}>
      <input ref={inputRef} type="file" className="hidden"
        onChange={e => e.target.files[0] && onFileSelect(e.target.files[0])} />
      {file ? (
        <div className="flex flex-col items-center gap-2">
          <CheckCircle2 size={32} className="text-emerald-500" />
          <p className="font-semibold text-emerald-700 text-sm">{file.name}</p>
          <p className="text-xs text-emerald-600">{(file.size / 1024).toFixed(1)} Ko</p>
          <p className="text-xs text-slate-400">Cliquez pour changer</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <div className="w-14 h-14 rounded-2xl bg-primary-50 dark:bg-primary-900/20 flex items-center justify-center">
            <Upload size={26} className="text-primary-500" />
          </div>
          <div>
            <p className="font-semibold text-slate-700 dark:text-slate-200 text-sm">
              Glissez-déposez votre document ici
            </p>
            <p className="text-xs text-slate-400 mt-1">ou cliquez pour parcourir</p>
          </div>
          <p className="text-[10px] text-slate-400">
            PDF, Word, Excel, Images, Archives — Max 50 Mo
          </p>
        </div>
      )}
    </div>
  )
}

// ── Document Form Modal ───────────────────────────────────────────────────────
function DocumentForm({ document, onSave, onClose }) {
  const isEdit = !!document?.id
  const { register, handleSubmit, reset } = useForm({
    defaultValues: document || { categorie: 'AUTRE' }
  })
  const [saving, setSaving] = useState(false)
  const [file,   setFile]   = useState(null)

  useEffect(() => { if (document) reset(document) }, [document])

  const onSubmit = async (data) => {
    if (!isEdit && !file) { toast.error('Veuillez sélectionner un fichier'); return }
    setSaving(true)
    try {
      const fd = new FormData()
      Object.entries(data).forEach(([k, v]) => { if (v !== null && v !== undefined && v !== '') fd.append(k, v) })
      if (file) fd.append('fichier', file)

      if (isEdit) { await archiveAPI.update(document.id, fd); toast.success('Document mis à jour') }
      else        { await archiveAPI.create(fd);              toast.success('Document importé') }
      onSave()
    } catch (e) {
      toast.error('Erreur lors de l\'import')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {/* Upload zone */}
      <div>
        <label className="label">Fichier {!isEdit && <span className="text-red-500">*</span>}</label>
        <UploadZone onFileSelect={setFile} file={file} />
        {isEdit && !file && document?.nom_original && (
          <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
            <File size={11} /> Fichier actuel : {document.nom_original}
            <span className="text-slate-300 ml-1">(laisser vide pour conserver)</span>
          </p>
        )}
      </div>

      {/* Titre */}
      <div>
        <label className="label">Titre <span className="text-red-500">*</span></label>
        <input {...register('titre', { required: true })} className="input"
          placeholder="Titre du document..." />
      </div>

      {/* Catégorie */}
      <div>
        <label className="label">Catégorie</label>
        <select {...register('categorie')} className="input">
          {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>

      {/* Description */}
      <div>
        <label className="label">Description</label>
        <textarea {...register('description')} className="input" rows={3}
          placeholder="Description du document, contexte, référence..." />
      </div>

      {/* Tags */}
      <div>
        <label className="label">
          Tags
          <span className="text-slate-400 font-normal ml-1 text-xs">(séparés par virgule)</span>
        </label>
        <input {...register('tags')} className="input"
          placeholder="ex: 2024, wilaya 16, récupérateur, agrément..." />
      </div>

      <div className="flex gap-3 pt-2 border-t border-[#E2E8F0]">
        <button type="submit" disabled={saving} className="btn-primary">
          <Save size={15} /> {saving ? 'Import en cours...' : isEdit ? 'Mettre à jour' : 'Importer le document'}
        </button>
        <button type="button" onClick={onClose} className="btn-secondary">Annuler</button>
      </div>
    </form>
  )
}

// ── Document Card ─────────────────────────────────────────────────────────────
function DocumentCard({ doc, onEdit, onDelete, onPreview }) {
  const extCfg = getExtCfg(doc.extension)
  const catCfg = getCatCfg(doc.categorie)
  const Icon   = extCfg.icon
  const tags   = visibleTags(doc)

  return (
    <div className="card p-4 hover:shadow-lg transition-all group">
      <div className="flex items-start gap-4">
        {/* File icon */}
        <div className={`w-12 h-12 rounded-xl ${extCfg.bg} flex items-center justify-center flex-shrink-0`}>
          <Icon size={24} className={extCfg.color} />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <p className="font-bold text-slate-900 dark:text-white text-sm truncate">{doc.titre}</p>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${catCfg.color}`}>
                  {catCfg.label}
                </span>
                {doc.extension && (
                  <span className="text-[10px] font-mono text-slate-400 uppercase">.{doc.extension}</span>
                )}
                <span className="text-[10px] text-slate-400">{doc.taille_lisible}</span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <a href={doc.fichier_url || doc.fichier} target="_blank" rel="noopener noreferrer"
                className="btn-ghost p-2 text-slate-400 hover:text-emerald-600" title="Télécharger">
                <Download size={14} />
              </a>
              <button onClick={() => onEdit(doc)}
                className="btn-ghost p-2 text-slate-400 hover:text-primary-600" title="Modifier">
                <Edit size={14} />
              </button>
              <button onClick={() => onDelete(doc.id)}
                className="btn-ghost p-2 text-slate-400 hover:text-red-600" title="Supprimer">
                <Trash2 size={14} />
              </button>
            </div>
          </div>

          {/* Description */}
          {doc.description && (
            <p className="text-xs text-slate-400 mt-1.5 line-clamp-2 leading-relaxed">
              {doc.description}
            </p>
          )}

          {/* Tags */}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {tags.map(tag => (
                <span key={tag} className="flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px]
                  bg-slate-100 text-slate-500 dark:bg-[#2B3D1E] dark:text-slate-400">
                  <Tag size={8} /> {tag}
                </span>
              ))}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center gap-4 mt-2 text-[10px] text-slate-400">
            <span className="flex items-center gap-1">
              <Calendar size={10} /> {formatDate(doc.created_at)}
            </span>
            {doc.uploaded_by_nom && (
              <span className="flex items-center gap-1">
                <User size={10} /> {doc.uploaded_by_nom}
              </span>
            )}
            {doc.nom_original && (
              <span className="font-mono truncate max-w-[200px]">{doc.nom_original}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function ArchivePage() {
  const { user } = useAuthStore()
  const [docs,      setDocs]      = useState([])
  const [loading,   setLoading]   = useState(true)
  const [showForm,  setShowForm]  = useState(false)
  const [editing,   setEditing]   = useState(null)
  const [search,    setSearch]    = useState('')
  const [catFilter, setCatFilter] = useState('')

  const isAdmin = user?.is_superuser || user?.permissions?.includes('archive.add_document') || user?.permissions?.includes('archive.change_document')

  const load = async () => {
    setLoading(true)
    try {
      const p = { page_size: 200 }
      if (search)    p.search    = search
      if (catFilter) p.categorie = catFilter
      const res = await archiveAPI.getAll(p)
      setDocs(res.data.results || res.data)
    } catch { toast.error('Erreur chargement') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [search, catFilter])

  const handleDelete = async (id) => {
    if (!window.confirm('Supprimer ce document définitivement ?')) return
    try { await archiveAPI.delete(id); toast.success('Supprimé'); load() }
    catch { toast.error('Erreur suppression') }
  }

  const handleSave = () => { setShowForm(false); setEditing(null); load() }
  const handleEdit = (doc) => { setEditing(doc); setShowForm(true) }

  // Regroupement par dossier — les documents générés depuis la même opération
  // (Proforma → BC → BL → Facture) partagent un tag 'dossier:<uuid>'.
  const { dossierGroups, standaloneDocs } = useMemo(() => {
    const byDossier = {}
    const standalone = []
    docs.forEach(d => {
      const dId = getDossierId(d)
      if (dId) (byDossier[dId] ||= []).push(d)
      else standalone.push(d)
    })
    const groups = []
    Object.entries(byDossier).forEach(([dId, items]) => {
      if (items.length > 1) groups.push({ dossierId: dId, items })
      else standalone.push(...items)
    })
    return { dossierGroups: groups, standaloneDocs: standalone }
  }, [docs])

  // Stats
  const catCounts = useMemo(() => {
    const c = {}
    docs.forEach(d => { c[d.categorie] = (c[d.categorie] || 0) + 1 })
    return c
  }, [docs])

  const totalSize = useMemo(() => {
    const bytes = docs.reduce((s, d) => s + (d.taille || 0), 0)
    if (bytes < 1024)    return `${bytes} o`
    if (bytes < 1048576) return `${(bytes/1024).toFixed(1)} Ko`
    return `${(bytes/1048576).toFixed(1)} Mo`
  }, [docs])

  return (
    <div className="space-y-5 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <FolderOpen size={24} className="text-amber-500" /> Archive documentaire
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {docs.length} document(s) · {totalSize}
          </p>
        </div>
        {isAdmin && (
          <button onClick={() => { setEditing(null); setShowForm(true) }} className="btn-primary">
            <Upload size={16} /> Importer un document
          </button>
        )}
      </div>

      {/* Category stats */}
      <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
        {CATEGORIES.filter(c => catCounts[c.value]).map(c => (
          <button key={c.value}
            onClick={() => setCatFilter(catFilter === c.value ? '' : c.value)}
            className={`card p-3 text-left border-2 transition-all
              ${catFilter === c.value ? 'border-primary-500' : 'border-transparent hover:border-slate-200'}`}>
            <p className="text-lg font-black text-slate-900 dark:text-white">{catCounts[c.value] || 0}</p>
            <p className={`text-[10px] font-bold mt-0.5 px-1.5 py-0.5 rounded-full inline-block ${c.color}`}>
              {c.label}
            </p>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-52">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher par titre, description, tags..."
            className="input pl-9 text-sm" />
          {search && (
            <button onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2">
              <X size={13} className="text-slate-400" />
            </button>
          )}
        </div>
        <select value={catFilter} onChange={e => setCatFilter(e.target.value)} className="input w-52 text-sm">
          <option value="">Toutes catégories</option>
          {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        {catFilter && (
          <button onClick={() => setCatFilter('')} className="btn-secondary btn-sm">
            <X size={12} /> Réinitialiser
          </button>
        )}
        <span className="text-xs text-slate-400 self-center">{docs.length} document(s)</span>
      </div>

      {/* Documents list */}
      {loading ? <Spinner /> : docs.length === 0 ? (
        <div className="card p-20 text-center">
          <FolderOpen size={48} className="mx-auto mb-4 text-slate-200" />
          <p className="font-bold text-slate-400 text-lg">Archive vide</p>
          <p className="text-sm text-slate-300 mt-1 mb-5">
            {search || catFilter
              ? 'Aucun document ne correspond à votre recherche'
              : 'Importez vos premiers documents'}
          </p>
          {isAdmin && !search && !catFilter && (
            <button onClick={() => { setEditing(null); setShowForm(true) }} className="btn-primary">
              <Upload size={15} /> Importer un document
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {dossierGroups.map(g => (
            <div key={g.dossierId} className="card p-3 border-2 border-primary-200 bg-primary-50/30 space-y-2">
              <div className="flex items-center gap-2 px-1">
                <FolderOpen size={15} className="text-primary-600" />
                <p className="text-xs font-bold text-primary-800 uppercase tracking-wide">
                  Dossier — {g.items.length} documents liés
                </p>
              </div>
              <div className="space-y-2">
                {g.items.map(doc => (
                  <DocumentCard
                    key={doc.id}
                    doc={doc}
                    onEdit={isAdmin ? handleEdit : () => {}}
                    onDelete={isAdmin ? handleDelete : () => {}}
                    onPreview={() => {}}
                  />
                ))}
              </div>
            </div>
          ))}
          <div className="space-y-2">
            {standaloneDocs.map(doc => (
              <DocumentCard
                key={doc.id}
                doc={doc}
                onEdit={isAdmin ? handleEdit : () => {}}
                onDelete={isAdmin ? handleDelete : () => {}}
                onPreview={() => {}}
              />
            ))}
          </div>
        </div>
      )}

      {/* Upload modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-[#16240D] rounded-2xl shadow-2xl w-full max-w-lg max-h-[92vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#E2E8F0] dark:border-[#2B3D1E] flex-shrink-0">
              <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Upload size={18} className="text-primary-600" />
                {editing ? 'Modifier le document' : 'Importer un document'}
              </h3>
              <button onClick={() => { setShowForm(false); setEditing(null) }}
                className="text-slate-400 hover:text-slate-700 p-1">
                <X size={18} />
              </button>
            </div>
            <div className="p-6 overflow-y-auto">
              <DocumentForm
                document={editing}
                onSave={handleSave}
                onClose={() => { setShowForm(false); setEditing(null) }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
