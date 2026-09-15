import { useState, useEffect } from 'react'
import { Search, Plus, Edit, Trash2, Eye, EyeOff, X, ChevronLeft, ChevronRight } from 'lucide-react'
import { useAuthStore } from '../../store'
import api from '../../api'
import toast from 'react-hot-toast'
import clsx from 'clsx'

const ROLES = {
  SUPERADMIN: 'Super Admin',
  ADMIN: 'Admin',
  RECUPERATEUR: 'Récupérateur',
  RESPONSABLE_COLLECTE: 'Resp. Collecte',
  AGENT_COLLECTE: 'Agent Collecte',
  RESPONSABLE_DECHARGE: 'Resp. Décharge',
  OBSERVATEUR: 'Observateur',
}

const ROLE_BADGE = {
  SUPERADMIN: 'badge-red',
  ADMIN: 'badge-blue',
  RECUPERATEUR: 'badge-green',
  RESPONSABLE_COLLECTE: 'badge-green',
  AGENT_COLLECTE: 'badge-green',
  RESPONSABLE_DECHARGE: 'badge-yellow',
  OBSERVATEUR: 'badge-gray',
}

function UserDialog({ open, onClose, user, onSave, loading }) {
  const isEdit = !!user
  const [showPwd, setShowPwd] = useState(false)
  const [form, setForm] = useState({
    username: '', email: '', first_name: '', last_name: '',
    phone: '', wilaya: '', role: 'OBSERVATEUR', password: '',
  })

  useEffect(() => {
    if (open) {
      setForm(user ? {
        username: user.username || '',
        email: user.email || '',
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        phone: user.phone || '',
        wilaya: user.wilaya || '',
        role: user.role || 'OBSERVATEUR',
        password: '',
      } : {
        username: '', email: '', first_name: '', last_name: '',
        phone: '', wilaya: '', role: 'OBSERVATEUR', password: '',
      })
    }
  }, [open, user])

  if (!open) return null

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white dark:bg-[#16240D] rounded-2xl shadow-xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">{isEdit ? 'Modifier' : 'Nouvel'} Utilisateur</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2B3D1E]"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Prénom</label><input value={form.first_name} onChange={e => set('first_name', e.target.value)} className="input" /></div>
            <div><label className="label">Nom</label><input value={form.last_name} onChange={e => set('last_name', e.target.value)} className="input" /></div>
          </div>
          <div><label className="label">Nom d'utilisateur</label><input value={form.username} onChange={e => set('username', e.target.value)} className="input" disabled={isEdit} /></div>
          <div><label className="label">Email</label><input value={form.email} onChange={e => set('email', e.target.value)} type="email" className="input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Téléphone</label><input value={form.phone} onChange={e => set('phone', e.target.value)} className="input" /></div>
            <div><label className="label">Wilaya</label><input value={form.wilaya} onChange={e => set('wilaya', e.target.value)} className="input" /></div>
          </div>
          <div>
            <label className="label">Rôle</label>
            <select value={form.role} onChange={e => set('role', e.target.value)} className="input">
              {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          {!isEdit && (
            <div>
              <label className="label">Mot de passe</label>
              <div className="relative">
                <input value={form.password} onChange={e => set('password', e.target.value)}
                  type={showPwd ? 'text' : 'password'} className="input pr-10" placeholder="Min. 8 caractères" />
                <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={onClose} className="btn-secondary btn-sm">Annuler</button>
            <button onClick={() => onSave(form)} disabled={loading} className="btn-primary btn-sm">
              {loading ? 'Enregistrement...' : isEdit ? 'Modifier' : 'Créer'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function DeleteDialog({ open, onClose, onConfirm, userName, loading }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white dark:bg-[#16240D] rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold mb-2">Supprimer l'utilisateur</h3>
        <p className="text-sm text-slate-500 mb-4">Voulez-vous vraiment supprimer <strong>{userName}</strong> ?</p>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary btn-sm">Annuler</button>
          <button onClick={onConfirm} disabled={loading} className="btn-danger btn-sm">{loading ? '...' : 'Supprimer'}</button>
        </div>
      </div>
    </div>
  )
}

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [page, setPage] = useState(1)
  const [count, setCount] = useState(0)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
  const [saving, setSaving] = useState(false)
  const currentUser = useAuthStore(s => s.user)

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const params = { page, page_size: 10 }
      if (search) params.search = search
      if (roleFilter) params.role = roleFilter
      const { data } = await api.get('/accounts/users/', { params })
      setUsers(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      toast.error('Erreur lors du chargement des utilisateurs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchUsers() }, [page, search, roleFilter])

  const handleCreate = () => { setSelectedUser(null); setDialogOpen(true) }
  const handleEdit = (u) => { setSelectedUser(u); setDialogOpen(true) }
  const handleDelete = (u) => { setSelectedUser(u); setDeleteOpen(true) }

  const handleSave = async (formData) => {
    setSaving(true)
    try {
      if (selectedUser) {
        await api.patch(`/accounts/users/${selectedUser.id}/`, formData)
        toast.success('Utilisateur modifié')
      } else {
        await api.post('/accounts/users/create/', formData)
        toast.success('Utilisateur créé')
      }
      setDialogOpen(false)
      setSelectedUser(null)
      fetchUsers()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Erreur lors de l\'enregistrement')
    } finally {
      setSaving(false)
    }
  }

  const handleConfirmDelete = async () => {
    setSaving(true)
    try {
      await api.delete(`/accounts/users/${selectedUser.id}/`)
      toast.success('Utilisateur supprimé')
      setDeleteOpen(false)
      setSelectedUser(null)
      fetchUsers()
    } catch (err) {
      toast.error(err.response?.data?.error || 'Erreur lors de la suppression')
    } finally {
      setSaving(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil(count / 10))

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Gestion des Utilisateurs</h1>
        <button onClick={handleCreate} className="btn-primary"><Plus className="w-4 h-4" /> Nouvel Utilisateur</button>
      </div>

      <div className="card p-4 mb-4 flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2 flex-1 min-w-[200px] bg-slate-50 dark:bg-[#1A2E10] rounded-xl px-3 py-2">
          <Search className="w-4 h-4 text-slate-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
            className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-slate-400" placeholder="Rechercher..." />
        </div>
        <select value={roleFilter} onChange={e => { setRoleFilter(e.target.value); setPage(1) }} className="input w-auto min-w-[160px]">
          <option value="">Tous les rôles</option>
          {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E2E8F0] dark:border-[#2B3D1E] bg-slate-50 dark:bg-[#1A2E10]">
                <th className="text-left px-4 py-3 font-medium text-slate-600">Utilisateur</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Email</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Rôle</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Wilaya</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={5} className="text-center py-12 text-slate-400">Chargement...</td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={5} className="text-center py-12 text-slate-400">Aucun utilisateur trouvé</td></tr>
              ) : users.map(u => (
                <tr key={u.id} className="border-b border-[#E2E8F0] dark:border-[#2B3D1E] hover:bg-slate-50 dark:hover:bg-[#1A2E10]">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-800 flex items-center justify-center text-white text-xs font-bold">
                        {(u.first_name?.[0] || u.username?.[0] || 'U').toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium">{u.first_name} {u.last_name}</p>
                        <p className="text-xs text-slate-400">@{u.username}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{u.email || '—'}</td>
                  <td className="px-4 py-3"><span className={clsx('badge', ROLE_BADGE[u.role] || 'badge-gray')}>{ROLES[u.role] || u.role}</span></td>
                  <td className="px-4 py-3 text-slate-500">{u.wilaya || '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => handleEdit(u)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2B3D1E]" title="Modifier"><Edit className="w-3.5 h-3.5 text-slate-500" /></button>
                      {u.id !== currentUser?.id && (
                        <button onClick={() => handleDelete(u)} className="p-1.5 rounded-lg hover:bg-red-50" title="Supprimer"><Trash2 className="w-3.5 h-3.5 text-red-500" /></button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#E2E8F0]">
            <span className="text-xs text-slate-400">{count} résultat(s)</span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30"><ChevronLeft className="w-4 h-4" /></button>
              <span className="text-xs text-slate-500 px-2">{page} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-30"><ChevronRight className="w-4 h-4" /></button>
            </div>
          </div>
        )}
      </div>

      <UserDialog open={dialogOpen} onClose={() => { setDialogOpen(false); setSelectedUser(null) }} user={selectedUser} onSave={handleSave} loading={saving} />
      <DeleteDialog open={deleteOpen} onClose={() => { setDeleteOpen(false); setSelectedUser(null) }} onConfirm={handleConfirmDelete}
        userName={selectedUser ? `${selectedUser.first_name} ${selectedUser.last_name}` : ''} loading={saving} />
    </div>
  )
}
