import { useState, useEffect, useMemo } from 'react'
import {
  Shield, Plus, Search, Edit, Eye, X,
  ChevronLeft, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown,
  Users, Key, Filter, Trash2, Archive, RefreshCw,
  ChevronDown, ChevronUp, Save, AlertTriangle, CheckCircle
} from 'lucide-react'
import { useAuthStore } from '../../../store'
import api from '../../../api'
import toast from 'react-hot-toast'
import clsx from 'clsx'
import { Can } from '../../../components/guards'

const MODULE_LABELS = {
  accounts: 'Utilisateurs',
  recuperateurs: 'Récupérateurs',
  traceability: 'Traçabilité',
  bsd: 'BSD',
  declarations: 'Déclarations',
  inspections: 'Inspections',
  operateurs: 'Opérateurs',
  administration: 'Administration',
  nomenclature: 'Nomenclature',
  archive: 'Archive',
  ai_assistant: 'IA Assistant',
}

const ACTION_LABELS = { view: 'Lire', add: 'Créer', change: 'Modifier', delete: 'Supprimer' }

const ACTION_META = {
  view:   { label: 'Lire',     color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  add:    { label: 'Créer',    color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
  change: { label: 'Modifier', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  delete: { label: 'Supprimer',color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
}

const ROLE_COLORS = {
  super_administrateur: 'from-red-500 to-red-700',
  administrateur: 'from-blue-500 to-blue-700',
  responsable_collecte: 'from-emerald-500 to-emerald-700',
  agent_collecte: 'from-teal-500 to-teal-700',
  responsable_decharge: 'from-amber-500 to-amber-700',
  observateur: 'from-slate-500 to-slate-700',
}

function RoleFormDialog({ open, onClose, role, onSave, loading }) {
  const isEdit = !!role
  const [form, setForm] = useState({ name: '' })
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      setError('')
      setForm(role ? { name: role.name || '' } : { name: '' })
    }
  }, [open, role])

  if (!open) return null

  const handleSave = () => {
    if (!form.name.trim()) { setError('Le nom est requis'); return }
    onSave(form)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white dark:bg-[#16240D] rounded-2xl shadow-xl w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-[#E2E8F0] dark:border-[#2B3D1E]">
          <div className="flex items-center gap-3">
            <div className={clsx('w-9 h-9 rounded-xl flex items-center justify-center', isEdit ? 'bg-primary-100 dark:bg-primary-900/30' : 'bg-emerald-100 dark:bg-emerald-900/30')}>
              {isEdit ? <Edit className="w-4 h-4 text-primary-600" /> : <Plus className="w-4 h-4 text-emerald-600" />}
            </div>
            <h3 className="text-lg font-bold">{isEdit ? 'Modifier' : 'Nouveau'} Rôle</h3>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-[#2B3D1E]"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="label">Nom du rôle <span className="text-red-500">*</span></label>
            <input value={form.name} onChange={e => setForm({ name: e.target.value })}
              className={clsx('input', error && 'ring-2 ring-red-500')}
              placeholder="Ex: Responsable Collecte"
              onKeyDown={e => e.key === 'Enter' && handleSave()} />
            {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
          </div>
          <div className="flex justify-end gap-2 pt-2 border-t border-[#E2E8F0] dark:border-[#2B3D1E]">
            <button onClick={onClose} className="btn-secondary btn-sm">Annuler</button>
            <Can do={isEdit ? 'accounts.change_group' : 'accounts.add_group'}>
              <button onClick={handleSave} disabled={loading} className="btn-primary btn-sm">
                {loading ? 'Enregistrement...' : isEdit ? 'Enregistrer' : 'Créer'}
              </button>
            </Can>
          </div>
        </div>
      </div>
    </div>
  )
}

function DeleteDialog({ open, onClose, onConfirm, roleName, loading }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white dark:bg-[#16240D] rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <h3 className="text-lg font-bold">Supprimer le rôle</h3>
        </div>
        <p className="text-sm text-slate-500 mb-4">
          Voulez-vous vraiment supprimer le rôle <strong>{roleName}</strong> ? Les utilisateurs assignés à ce rôle perdront ses permissions.
        </p>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary btn-sm">Annuler</button>
          <Can do="accounts.delete_group">
            <button onClick={onConfirm} disabled={loading} className="btn-danger btn-sm">
              {loading ? 'Suppression...' : 'Supprimer'}
            </button>
          </Can>
        </div>
      </div>
    </div>
  )
}

function PermissionsEditor({ open, onClose, role, allPerms, onSave, loading }) {
  const [rolePerms, setRolePerms] = useState(new Set())
  const [expandedModules, setExpandedModules] = useState({})
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (open && role) {
      setRolePerms(new Set(role.permissions_list || []))
      setExpandedModules({})
      setSearch('')
    }
  }, [open, role])

  if (!open || !role) return null

  const groupedPerms = allPerms.reduce((acc, p) => {
    if (!acc[p.app_label]) acc[p.app_label] = []
    acc[p.app_label].push(p)
    return acc
  }, {})

  const filteredGrouped = Object.entries(groupedPerms).reduce((acc, [module, perms]) => {
    if (!search) { acc[module] = perms; return acc }
    const q = search.toLowerCase()
    const filtered = perms.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.codename.toLowerCase().includes(q) ||
      (MODULE_LABELS[module] || module).toLowerCase().includes(q)
    )
    if (filtered.length > 0) acc[module] = filtered
    return acc
  }, {})

  const totalPerms = allPerms.length
  const selectedCount = rolePerms.size
  const allSelected = selectedCount === totalPerms

  const togglePerm = (perm) => {
    setRolePerms(prev => {
      const next = new Set(prev)
      if (next.has(perm)) next.delete(perm)
      else next.add(perm)
      return next
    })
  }

  const toggleModule = (module) => {
    const modulePerms = filteredGrouped[module] || []
    const allChecked = modulePerms.every(p => rolePerms.has(`${p.app_label}.${p.codename}`))
    setRolePerms(prev => {
      const next = new Set(prev)
      modulePerms.forEach(p => {
        const key = `${p.app_label}.${p.codename}`
        if (allChecked) next.delete(key)
        else next.add(key)
      })
      return next
    })
  }

  const toggleAll = () => {
    if (allSelected) {
      setRolePerms(new Set())
    } else {
      setRolePerms(new Set(allPerms.map(p => `${p.app_label}.${p.codename}`)))
    }
  }

  const expandAll = () => {
    const all = {}
    Object.keys(filteredGrouped).forEach(m => { all[m] = true })
    setExpandedModules(all)
  }

  const collapseAll = () => setExpandedModules({})

  const handleSave = () => {
    const permIds = allPerms
      .filter(p => rolePerms.has(`${p.app_label}.${p.codename}`))
      .map(p => p.id)
    onSave(permIds)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white dark:bg-[#16240D] rounded-2xl shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[#E2E8F0] dark:border-[#2B3D1E] flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
              <Key className="w-4 h-4 text-primary-600" />
            </div>
            <div>
              <h3 className="text-lg font-bold">Assigner les permissions</h3>
              <p className="text-xs text-slate-500">{role.name}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-[#2B3D1E]"><X className="w-4 h-4" /></button>
        </div>

        {/* Toolbar */}
        <div className="px-5 pt-4 pb-3 border-b border-[#E2E8F0] dark:border-[#2B3D1E] space-y-3 flex-shrink-0">
          {/* Search */}
          <div className="flex items-center gap-2 bg-slate-50 dark:bg-[#1A2E10] rounded-xl px-3 py-2">
            <Search className="w-4 h-4 text-slate-400" />
            <input value={search} onChange={e => setSearch(e.target.value)}
              className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-slate-400"
              placeholder="Rechercher une permission..." />
            {search && (
              <button onClick={() => setSearch('')} className="text-slate-400 hover:text-slate-600">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Actions row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Global Select All */}
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input type="checkbox" checked={allSelected} onChange={toggleAll}
                  className="rounded border-slate-300 text-primary-600 focus:ring-primary-500" />
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Tout sélectionner
                </span>
              </label>
              <span className="text-xs text-slate-400">|</span>
              <span className="text-xs text-slate-500">
                <span className="font-semibold text-primary-600">{selectedCount}</span>
                <span className="text-slate-400"> / {totalPerms}</span> permissions
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <button onClick={expandAll} className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2B3D1E]">
                Tout déplier
              </button>
              <span className="text-slate-300">·</span>
              <button onClick={collapseAll} className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2B3D1E]">
                Tout replier
              </button>
            </div>
          </div>
        </div>

        {/* Module groups */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          {Object.keys(filteredGrouped).length === 0 ? (
            <div className="text-center py-12">
              <Search className="w-10 h-10 mx-auto mb-3 text-slate-300" />
              <p className="text-sm text-slate-400">Aucune permission trouvée</p>
            </div>
          ) : (
            Object.entries(filteredGrouped).map(([module, perms]) => {
              const checkedPerms = perms.filter(p => rolePerms.has(`${p.app_label}.${p.codename}`))
              const moduleChecked = checkedPerms.length
              const moduleTotal = perms.length
              const allChecked = moduleChecked === moduleTotal
              const someChecked = moduleChecked > 0 && !allChecked
              const expanded = expandedModules[module]

              const permsByAction = {}
              perms.forEach(p => {
                const action = p.codename.split('_')[0]
                if (!permsByAction[action]) permsByAction[action] = []
                permsByAction[action].push(p)
              })

              return (
                <div key={module} className="border border-[#E2E8F0] dark:border-[#2B3D1E] rounded-xl overflow-hidden">

                  {/* Module header */}
                  <div className="flex items-center justify-between px-4 py-3 bg-[#F8FAFC] dark:bg-[#0D1B0A]">
                    <label className="flex items-center gap-3 cursor-pointer flex-1 select-none">
                      <input type="checkbox"
                        checked={allChecked}
                        ref={el => { if (el) el.indeterminate = someChecked }}
                        onChange={() => toggleModule(module)}
                        className="rounded border-slate-300 text-primary-600 focus:ring-primary-500" />
                      <div className="flex items-center gap-2">
                        <Shield className="w-4 h-4 text-primary-500" />
                        <span className="font-semibold text-sm text-slate-900 dark:text-white">
                          {MODULE_LABELS[module] || module}
                        </span>
                      </div>
                      <span className={clsx(
                        'badge text-[0.65rem]',
                        allChecked ? 'badge-green' : moduleChecked > 0 ? 'badge-blue' : 'badge-gray'
                      )}>
                        {moduleChecked}/{moduleTotal}
                      </span>
                    </label>
                    <button onClick={() => setExpandedModules(prev => ({ ...prev, [module]: !prev[module] }))}
                      className="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-[#2B3D1E] transition-colors">
                      {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    </button>
                  </div>

                  {/* Permissions grouped by action */}
                  {expanded && (
                    <div className="border-t border-[#E2E8F0] dark:border-[#2B3D1E] p-3 space-y-2">
                      {Object.entries(permsByAction).map(([action, actionPerms]) => {
                        const actionChecked = actionPerms.filter(p => rolePerms.has(`${p.app_label}.${p.codename}`)).length
                        const actionAllChecked = actionChecked === actionPerms.length
                        const actionSomeChecked = actionChecked > 0 && !actionAllChecked

                        return (
                          <div key={action} className="rounded-lg border border-[#E2E8F0] dark:border-[#2B3D1E] overflow-hidden">
                            {/* Action sub-header */}
                            <div className="flex items-center justify-between px-3 py-2 bg-white dark:bg-[#16240D]">
                              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                                <input type="checkbox"
                                  checked={actionAllChecked}
                                  ref={el => { if (el) el.indeterminate = actionSomeChecked }}
                                  onChange={() => {
                                    setRolePerms(prev => {
                                      const next = new Set(prev)
                                      actionPerms.forEach(p => {
                                        const key = `${p.app_label}.${p.codename}`
                                        if (actionAllChecked) next.delete(key)
                                        else next.add(key)
                                      })
                                      return next
                                    })
                                  }}
                                  className="rounded border-slate-300 text-primary-600 focus:ring-primary-500" />
                                <span className={clsx('badge text-[0.6rem]', ACTION_META[action]?.color || 'badge-gray')}>
                                  {ACTION_LABELS[action] || action}
                                </span>
                                <span className="text-xs text-slate-400">
                                  {actionChecked}/{actionPerms.length}
                                </span>
                              </label>
                            </div>

                            {/* Permissions list */}
                            <div className="px-3 pb-2 pt-1 grid grid-cols-1 sm:grid-cols-2 gap-1">
                              {actionPerms.map(p => {
                                const key = `${p.app_label}.${p.codename}`
                                const checked = rolePerms.has(key)
                                return (
                                  <label key={p.id}
                                    className={clsx(
                                      'flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-colors text-sm',
                                      checked
                                        ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                                        : 'hover:bg-slate-50 dark:hover:bg-[#16240D] text-slate-600 dark:text-slate-400'
                                    )}>
                                    <input type="checkbox" checked={checked} onChange={() => togglePerm(key)}
                                      className="rounded border-slate-300 text-primary-600 focus:ring-primary-500" />
                                    <span className="truncate" title={p.codename}>{p.name}</span>
                                  </label>
                                )
                              })}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-5 border-t border-[#E2E8F0] dark:border-[#2B3D1E] flex-shrink-0">
          <span className="text-xs text-slate-400">
            {selectedCount} permission(s) sélectionnée(s)
          </span>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn-secondary btn-sm">Annuler</button>
            <button onClick={handleSave} disabled={loading} className="btn-primary btn-sm">
              {loading ? 'Enregistrement...' : 'Enregistrer'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function RoleDetailPanel({ open, role, onClose, onEdit, onPermissions, onDelete }) {
  if (!open || !role) return null
  const initials = role.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
  const gradientFrom = ROLE_COLORS[role.name.toLowerCase().replace(/\s+/g, '_')] || 'from-primary-500 to-primary-700'

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30" onClick={onClose} />
      <div className="fixed top-0 right-0 h-full w-full max-w-md z-50 bg-white dark:bg-[#16240D] shadow-2xl border-l border-[#E2E8F0] dark:border-[#2B3D1E] overflow-y-auto animate-slide-in">
        <div className="sticky top-0 bg-white dark:bg-[#16240D] border-b border-[#E2E8F0] dark:border-[#2B3D1E] p-4 flex items-center justify-between z-10">
          <h3 className="text-lg font-bold">Détails du Rôle</h3>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-[#2B3D1E]">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 space-y-5">
          {/* Role header */}
          <div className="flex items-center gap-4">
            <div className={clsx('w-14 h-14 rounded-2xl bg-gradient-to-br flex items-center justify-center text-white text-xl font-bold', gradientFrom)}>
              {initials}
            </div>
            <div>
              <p className="text-lg font-bold">{role.name}</p>
              <div className="flex items-center gap-3 mt-1">
                <span className="badge badge-green">
                  <CheckCircle className="w-3 h-3" /> Actif
                </span>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="card p-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Users className="w-4 h-4 text-primary-500" />
                <span className="text-2xl font-bold text-primary-600">{role.user_count}</span>
              </div>
              <p className="text-xs text-slate-500">Utilisateurs</p>
            </div>
            <div className="card p-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Key className="w-4 h-4 text-violet-500" />
                <span className="text-2xl font-bold text-violet-600">{role.permissions_list?.length || 0}</span>
              </div>
              <p className="text-xs text-slate-500">Permissions</p>
            </div>
          </div>

          {/* Permissions list */}
          {role.permissions_list && role.permissions_list.length > 0 && (
            <div className="card p-4">
              <p className="text-sm font-semibold mb-3">Permissions assignées</p>
              <div className="flex flex-wrap gap-1.5">
                {role.permissions_list.map(p => (
                  <span key={p} className="badge badge-gray text-[0.65rem]">{p}</span>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="space-y-2">
            <button onClick={() => onEdit(role)} className="btn-secondary btn-sm w-full justify-start">
              <Edit className="w-4 h-4" /> Modifier le nom
            </button>
            <button onClick={() => onPermissions(role)} className="btn-secondary btn-sm w-full justify-start">
              <Key className="w-4 h-4" /> Gérer les permissions
            </button>
            <button onClick={() => onDelete(role)} className="btn-danger btn-sm w-full justify-start">
              <Trash2 className="w-4 h-4" /> Supprimer le rôle
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

export default function AdminRolesPage() {
  const [roles, setRoles] = useState([])
  const [allPerms, setAllPerms] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sortField, setSortField] = useState('name')
  const [sortDir, setSortDir] = useState('asc')

  const [formOpen, setFormOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [permsOpen, setPermsOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [selectedRole, setSelectedRole] = useState(null)
  const [saving, setSaving] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [rolesRes, permsRes] = await Promise.all([
        api.get('/accounts/roles/'),
        api.get('/accounts/permissions/'),
      ])
      setRoles(rolesRes.data)
      setAllPerms(permsRes.data)
    } catch {
      toast.error('Erreur lors du chargement des données')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const filteredRoles = useMemo(() => {
    let list = [...roles]
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(r => r.name.toLowerCase().includes(q))
    }
    list.sort((a, b) => {
      let av, bv
      if (sortField === 'name') { av = a.name.toLowerCase(); bv = b.name.toLowerCase() }
      else if (sortField === 'user_count') { av = a.user_count; bv = b.user_count }
      else if (sortField === 'permissions_count') { av = a.permissions_list?.length || 0; bv = b.permissions_list?.length || 0 }
      else { av = a.name.toLowerCase(); bv = b.name.toLowerCase() }
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
    return list
  }, [roles, search, sortField, sortDir])

  const handleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <ArrowUpDown className="w-3 h-3 text-slate-300" />
    return sortDir === 'asc' ? <ArrowUp className="w-3 h-3 text-primary-600" /> : <ArrowDown className="w-3 h-3 text-primary-600" />
  }

  const handleCreate = () => { setSelectedRole(null); setFormOpen(true) }
  const handleEdit = (r) => { setSelectedRole(r); setFormOpen(true); setDetailOpen(false) }
  const handleView = (r) => { setSelectedRole(r); setDetailOpen(true) }
  const handlePermissions = (r) => { setSelectedRole(r); setPermsOpen(true); setDetailOpen(false) }
  const handleDelete = (r) => { setSelectedRole(r); setDeleteOpen(true); setDetailOpen(false) }

  const handleSave = async (formData) => {
    setSaving(true)
    try {
      if (selectedRole) {
        await api.patch(`/accounts/roles/${selectedRole.id}/`, formData)
        toast.success('Rôle modifié')
      } else {
        await api.post('/accounts/roles/', formData)
        toast.success('Rôle créé')
      }
      setFormOpen(false)
      setSelectedRole(null)
      fetchData()
    } catch (err) {
      toast.error(err.response?.data?.error || err.response?.data?.detail || 'Erreur lors de l\'enregistrement')
    } finally {
      setSaving(false)
    }
  }

  const handleConfirmDelete = async () => {
    setSaving(true)
    try {
      await api.delete(`/accounts/roles/${selectedRole.id}/`)
      toast.success('Rôle supprimé')
      setDeleteOpen(false)
      setSelectedRole(null)
      if (detailOpen) setDetailOpen(false)
      fetchData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Erreur lors de la suppression')
    } finally {
      setSaving(false)
    }
  }

  const handleSavePermissions = async (permIds) => {
    setSaving(true)
    try {
      await api.put(`/accounts/roles/${selectedRole.id}/permissions/`, { permissions: permIds })
      toast.success('Permissions enregistrées')
      setPermsOpen(false)
      setSelectedRole(null)
      fetchData()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Erreur lors de l\'enregistrement')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
            <Shield className="w-5 h-5 text-violet-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Gestion des Rôles</h1>
            <p className="text-sm text-slate-500">{roles.length} rôle(s) configuré(s)</p>
          </div>
        </div>
        <Can do="accounts.add_group">
          <button onClick={handleCreate} className="btn-primary">
            <Plus className="w-4 h-4" /> Nouveau Rôle
          </button>
        </Can>
      </div>

      {/* Search */}
      <div className="card p-4">
        <div className="flex items-center gap-2 bg-slate-50 dark:bg-[#1A2E10] rounded-xl px-3 py-2">
          <Search className="w-4 h-4 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-slate-400"
            placeholder="Rechercher un rôle..." />
          {search && (
            <button onClick={() => setSearch('')} className="text-slate-400 hover:text-slate-600">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E2E8F0] dark:border-[#2B3D1E] bg-slate-50 dark:bg-[#1A2E10]">
                {[
                  { key: 'name', label: 'Rôle' },
                  { key: 'permissions_count', label: 'Permissions' },
                  { key: 'user_count', label: 'Utilisateurs' },
                ].map(col => (
                  <th key={col.key}
                    className="text-left px-4 py-3 font-medium text-slate-600 dark:text-slate-400 cursor-pointer hover:text-slate-900 select-none"
                    onClick={() => handleSort(col.key)}>
                    <div className="flex items-center gap-1.5">
                      {col.label} <SortIcon field={col.key} />
                    </div>
                  </th>
                ))}
                <th className="text-right px-4 py-3 font-medium text-slate-600 dark:text-slate-400 w-[120px]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="text-center py-16">
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
                      <span className="text-sm text-slate-400">Chargement...</span>
                    </div>
                  </td>
                </tr>
              ) : filteredRoles.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center py-16">
                    <Shield className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                    <p className="text-sm font-medium text-slate-400">Aucun rôle trouvé</p>
                    <p className="text-xs text-slate-300 mt-1">Créez un nouveau rôle pour commencer</p>
                  </td>
                </tr>
              ) : filteredRoles.map(r => {
                const initials = r.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
                const gradientFrom = ROLE_COLORS[r.name.toLowerCase().replace(/\s+/g, '_')] || 'from-primary-500 to-primary-700'
                return (
                  <tr key={r.id}
                    className="border-b border-[#E2E8F0] dark:border-[#2B3D1E] hover:bg-slate-50 dark:hover:bg-[#1A2E10] cursor-pointer"
                    onClick={() => handleView(r)}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className={clsx('w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center text-white text-xs font-bold flex-shrink-0', gradientFrom)}>
                          {initials}
                        </div>
                        <div>
                          <p className="font-medium text-slate-900 dark:text-white">{r.name}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="badge badge-blue">
                        <Key className="w-3 h-3" />
                        {r.permissions_list?.length || 0}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="badge badge-gray">
                        <Users className="w-3 h-3" />
                        {r.user_count}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1" onClick={e => e.stopPropagation()}>
                        <button onClick={() => handleEdit(r)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2B3D1E]" title="Modifier">
                          <Edit className="w-3.5 h-3.5 text-slate-500" />
                        </button>
                        <button onClick={() => handlePermissions(r)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2B3D1E]" title="Permissions">
                          <Key className="w-3.5 h-3.5 text-slate-500" />
                        </button>
                        <button onClick={() => handleDelete(r)} className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/10" title="Supprimer">
                          <Trash2 className="w-3.5 h-3.5 text-red-500" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dialogs */}
      <RoleFormDialog open={formOpen} onClose={() => { setFormOpen(false); setSelectedRole(null) }}
        role={selectedRole} onSave={handleSave} loading={saving} />

      <DeleteDialog open={deleteOpen} onClose={() => { setDeleteOpen(false); setSelectedRole(null) }}
        onConfirm={handleConfirmDelete} roleName={selectedRole?.name} loading={saving} />

      <PermissionsEditor open={permsOpen} onClose={() => { setPermsOpen(false); setSelectedRole(null) }}
        role={selectedRole} allPerms={allPerms} onSave={handleSavePermissions} loading={saving} />

      <RoleDetailPanel open={detailOpen} role={selectedRole} onClose={() => { setDetailOpen(false); setSelectedRole(null) }}
        onEdit={handleEdit} onPermissions={handlePermissions} onDelete={handleDelete} />
    </div>
  )
}
