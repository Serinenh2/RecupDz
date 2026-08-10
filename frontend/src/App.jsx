import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store'
import { ProtectedRoute } from './components/guards'

import Layout   from './components/layout/Layout'
import LoginPage from './pages/auth/LoginPage'
import DashboardPage from './pages/dashboard/DashboardPage'
import OperateursPage    from './pages/operateurs/index'
import NomenclaturePage  from './pages/nomenclature/index'
import GlossairePage    from './pages/glossaire/index'
import AlertesPage      from './pages/alertes/index'
import InspectionsPage  from './pages/inspections/index'
import StatsPage        from './pages/stats/index'
import ArchivePage      from './pages/archive/index'
import AdminRolesPage   from './pages/admin/roles/index'
import AdminPermissionsPage from './pages/admin/permissions/index'
import UsersPage         from './pages/users/index'
import ProfilPage       from './pages/profil/ProfilPage'
import DocumentsPage from './pages/documents/index'
import TracabilitePage from './pages/tracabilite/index'

import AdministrationLayout from './pages/administration/Layout'
import AdministrationUsersPage from './pages/administration/users/index'
import AdministrationRolesPage from './pages/administration/roles/index'
import AdministrationPermissionsPage from './pages/administration/permissions/index'
import AdministrationAuditLogsPage from './pages/administration/audit-logs/index'
import AdministrationOrganizationPage from './pages/administration/organization/index'
import AdministrationSettingsPage from './pages/administration/settings/index'

export default function App() {
  const loadUser = useAuthStore(s => s.loadUser)
  useEffect(() => { loadUser() }, [])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/dashboard" replace />} />

        <Route path="dashboard" element={
          <ProtectedRoute><DashboardPage /></ProtectedRoute>
        } />

        <Route path="operateurs" element={
          <ProtectedRoute permission="operateurs.view_operateur"><OperateursPage /></ProtectedRoute>
        } />

        <Route path="tracabilite" element={
          <ProtectedRoute permission="traceability.view_traceability"><TracabilitePage /></ProtectedRoute>
        } />

        <Route path="documents" element={
          <ProtectedRoute permission="archive.view_document"><DocumentsPage /></ProtectedRoute>
        } />

        <Route path="stats" element={
          <ProtectedRoute><StatsPage /></ProtectedRoute>
        } />

        <Route path="nomenclature" element={
          <ProtectedRoute><NomenclaturePage /></ProtectedRoute>
        } />

        <Route path="glossaire" element={
          <ProtectedRoute><GlossairePage /></ProtectedRoute>
        } />

        <Route path="archive" element={
          <ProtectedRoute permission="archive.view_document"><ArchivePage /></ProtectedRoute>
        } />

        <Route path="alertes" element={
          <ProtectedRoute><AlertesPage /></ProtectedRoute>
        } />

        <Route path="inspections" element={
          <ProtectedRoute><InspectionsPage /></ProtectedRoute>
        } />

        {/* Admin routes — legacy */}
        <Route path="admin/roles" element={
          <ProtectedRoute role="SUPERADMIN"><AdminRolesPage /></ProtectedRoute>
        } />

        <Route path="admin/permissions" element={
          <ProtectedRoute role="SUPERADMIN"><AdminPermissionsPage /></ProtectedRoute>
        } />

        <Route path="users" element={
          <ProtectedRoute role="SUPERADMIN"><UsersPage /></ProtectedRoute>
        } />

        {/* Administration section */}
        <Route path="administration" element={
          <ProtectedRoute role="SUPERADMIN"><AdministrationLayout /></ProtectedRoute>
        }>
          <Route index element={<Navigate to="/administration/users" replace />} />

          <Route path="users" element={
            <ProtectedRoute role="SUPERADMIN"><AdministrationUsersPage /></ProtectedRoute>
          } />

          <Route path="roles" element={<Navigate to="/admin/roles" replace />} />

          <Route path="permissions" element={
            <ProtectedRoute role="SUPERADMIN"><AdministrationPermissionsPage /></ProtectedRoute>
          } />

          <Route path="audit-logs" element={
            <ProtectedRoute role="SUPERADMIN"><AdministrationAuditLogsPage /></ProtectedRoute>
          } />

          <Route path="organization" element={
            <ProtectedRoute role="SUPERADMIN"><AdministrationOrganizationPage /></ProtectedRoute>
          } />

          <Route path="settings" element={
            <ProtectedRoute role="SUPERADMIN"><AdministrationSettingsPage /></ProtectedRoute>
          } />
        </Route>

        {/* Profile */}
        <Route path="profil" element={
          <ProtectedRoute><ProfilPage /></ProtectedRoute>
        } />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}
