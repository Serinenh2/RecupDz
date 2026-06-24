import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store'

import Layout   from './components/layout/Layout'
import LoginPage from './pages/auth/LoginPage'
import DashboardPage from './pages/dashboard/DashboardPage'
import RecuperateursPage from './pages/recuperateurs/RecuperateursPage'
import RecuperateurFormPage from './pages/recuperateurs/RecuperateurFormPage'
import OperateursPage    from './pages/operateurs/index'
import AdministrationPage from './pages/administration/index'
import NomenclaturePage  from './pages/nomenclature/index'
import GlossairePage    from './pages/glossaire/index'
import AlertesPage      from './pages/alertes/index'
import InspectionsPage  from './pages/inspections/index'
import StatsPage        from './pages/stats/index'
import ArchivePage      from './pages/archive/index'
import AdminRolesPage   from './pages/admin/roles/index'
import ProfilPage       from './pages/profil/ProfilPage'
import DocumentsPage from './pages/documents/index'
import TracabilitePage from './pages/tracabilite/index'
import AIAssistantPage from './pages/ai/index'
import BSDPage from './pages/bsd/index'
import DeclarationsPage from './pages/declarations/index'

function PrivateRoute({ children }) {
  const user    = useAuthStore(s => s.user)
  const loading = useAuthStore(s => s.loading)
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-3 border-primary-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-500 text-sm">Chargement...</p>
      </div>
    </div>
  )
  return user ? children : <Navigate to="/login" replace />
}

function AdminRoute({ children }) {
  const user = useAuthStore(s => s.user)
  if (user && !user.is_superuser && user.role !== 'SUPERADMIN' && user.role !== 'ADMIN') {
    return <Navigate to="/dashboard" replace />
  }
  return children
}

function RequirePermission({ permission, children }) {
  const user          = useAuthStore(s => s.user)
  const hasPermission = useAuthStore(s => s.hasPermission)
  if (user && !user.is_superuser && !hasPermission(permission)) {
    return <Navigate to="/dashboard" replace />
  }
  return children
}

export default function App() {
  const loadUser = useAuthStore(s => s.loadUser)
  useEffect(() => { loadUser() }, [])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard"           element={<DashboardPage />} />
        <Route path="recuperateurs"       element={<RecuperateursPage />} />
        <Route path="recuperateurs/new"   element={<RecuperateurFormPage />} />
        <Route path="recuperateurs/:id"   element={<RecuperateurFormPage />} />
        <Route path="recuperateurs/:id/edit" element={<RecuperateurFormPage />} />
        <Route path="operateurs"          element={<OperateursPage />} />
        <Route path="administration"      element={<AdministrationPage />} />
        <Route path="nomenclature"        element={<NomenclaturePage />} />
        <Route path="glossaire"           element={<GlossairePage />} />
        <Route path="alertes"             element={<AlertesPage />} />
        <Route path="inspections"         element={<InspectionsPage />} />
        <Route path="stats"               element={<StatsPage />} />
        <Route path="archive"             element={<ArchivePage />} />
        <Route path="documents"           element={<DocumentsPage />} />
        <Route path="admin/roles"         element={<AdminRoute><AdminRolesPage /></AdminRoute>} />
        <Route path="profil"              element={<ProfilPage />} />
        <Route path="tracabilite"         element={<RequirePermission permission="traceability.view_traceability"><TracabilitePage /></RequirePermission>} />
        <Route path="bsd"                 element={<BSDPage />} />
        <Route path="declarations"        element={<DeclarationsPage />} />
        <Route path="assistant-ia"       element={<AIAssistantPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}
