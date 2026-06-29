import { useState, useEffect } from 'react'
import { Shield, Users, Check, X, ChevronDown, ChevronUp, Save, Loader2 } from 'lucide-react'
import api from '../../../api'
import clsx from 'clsx'

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

export default function AdminRolesPage() {
  const [roles, setRoles] = useState([])
  const [allPerms, setAllPerms] = useState([])
  const [selectedRole, setSelectedRole] = useState(null)
  const [rolePerms, setRolePerms] = useState(new Set())
  const [saving, setSaving] = useState(false)
  const [expandedModules, setExpandedModules] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/accounts/roles/'),
      api.get('/accounts/permissions/'),
    ]).then(([rolesRes, permsRes]) => {
      setRoles(rolesRes.data)
      setAllPerms(permsRes.data)
      setLoading(false)
    })
  }, [])

  useEffect(() => {
    if (selectedRole) {
      setRolePerms(new Set(selectedRole.permissions_list))
    }
  }, [selectedRole])

  const togglePerm = (perm) => {
    setRolePerms(prev => {
      const next = new Set(prev)
      if (next.has(perm)) next.delete(perm)
      else next.add(perm)
      return next
    })
  }

  const savePermissions = async () => {
    if (!selectedRole) return
    setSaving(true)
    try {
      const permIds = allPerms
        .filter(p => rolePerms.has(`${p.app_label}.${p.codename}`))
        .map(p => p.id)
      await api.put(`/accounts/roles/${selectedRole.id}/permissions/`, { permissions: permIds })
      setRoles(prev => prev.map(r =>
        r.id === selectedRole.id
          ? { ...r, permissions_list: Array.from(rolePerms) }
          : r
      ))
    } finally { setSaving(false) }
  }

  const groupedPerms = allPerms.reduce((acc, p) => {
    if (!acc[p.app_label]) acc[p.app_label] = []
    acc[p.app_label].push(p)
    return acc
  }, {})

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
          <Shield className="w-5 h-5 text-violet-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Gestion des Rôles</h1>
          <p className="text-sm text-slate-500">Configurez les permissions pour chaque rôle</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Roles list */}
        <div className="bg-white dark:bg-[#16240D] rounded-2xl border border-[#E2E8F0] dark:border-[#2B3D1E] p-4">
          <h2 className="font-semibold text-slate-900 dark:text-white mb-3">Rôles</h2>
          <div className="space-y-2">
            {roles.map(role => (
              <button
                key={role.id}
                onClick={() => setSelectedRole(role)}
                className={clsx(
                  'w-full text-left px-4 py-3 rounded-xl border transition-all',
                  selectedRole?.id === role.id
                    ? 'bg-primary-50 dark:bg-primary-900/20 border-primary-300 dark:border-primary-700'
                    : 'bg-[#F8FAFC] dark:bg-[#0D1B0A] border-[#E2E8F0] dark:border-[#2B3D1E] hover:bg-slate-50 dark:hover:bg-[#16240D]'
                )}>
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm text-slate-900 dark:text-white">{role.name}</span>
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    {role.user_count}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  {role.permissions_list.length} permissions
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Permissions matrix */}
        <div className="lg:col-span-2 bg-white dark:bg-[#16240D] rounded-2xl border border-[#E2E8F0] dark:border-[#2B3D1E] p-4">
          {selectedRole ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold text-slate-900 dark:text-white">
                  Permissions — {selectedRole.name}
                </h2>
                <button
                  onClick={savePermissions}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-xl text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Sauvegarder
                </button>
              </div>

              <div className="space-y-3">
                {Object.entries(groupedPerms).map(([module, perms]) => {
                  const expanded = expandedModules[module]
                  const checkedCount = perms.filter(p => rolePerms.has(`${p.app_label}.${p.codename}`)).length
                  return (
                    <div key={module} className="border border-[#E2E8F0] dark:border-[#2B3D1E] rounded-xl overflow-hidden">
                      <button
                        onClick={() => setExpandedModules(prev => ({ ...prev, [module]: !prev[module] }))}
                        className="w-full flex items-center justify-between px-4 py-3 bg-[#F8FAFC] dark:bg-[#0D1B0A] hover:bg-slate-100 dark:hover:bg-[#16240D]">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm text-slate-900 dark:text-white">
                            {MODULE_LABELS[module] || module}
                          </span>
                          <span className="text-xs text-slate-400">
                            {checkedCount}/{perms.length}
                          </span>
                        </div>
                        {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                      </button>
                      {expanded && (
                        <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {perms.map(p => {
                            const key = `${p.app_label}.${p.codename}`
                            const checked = rolePerms.has(key)
                            const action = p.codename.split('_')[0]
                            return (
                              <label
                                key={p.id}
                                className={clsx(
                                  'flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm',
                                  checked
                                    ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                                    : 'hover:bg-slate-50 dark:hover:bg-[#16240D] text-slate-600 dark:text-slate-400'
                                )}>
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => togglePerm(key)}
                                  className="rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                                />
                                <span>{ACTION_LABELS[action] || action}</span>
                                <span className="text-slate-400 text-xs">
                                  {p.codename.replace(/_/g, ' ').replace(action + ' ', '')}
                                </span>
                              </label>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
              <Shield className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-sm">Sélectionnez un rôle pour configurer ses permissions</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
