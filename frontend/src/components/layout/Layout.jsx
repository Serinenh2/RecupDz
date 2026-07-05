import { useState } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Package, FileText,
  BarChart3, LogOut, ChevronLeft, ChevronRight,
  Menu, Moon, Sun, Leaf, Shield, BookOpen, X, User,
  Bell, GraduationCap, Building2, FolderOpen, Bot
} from 'lucide-react'
import { useAuthStore } from '../../store'
import AIAssistantPage from '../../pages/ai/index'
import clsx from 'clsx'

const NAV_BASE = [
  { to: '/dashboard',      icon: LayoutDashboard, label: 'Tableau de bord',     permission: null },
  { to: '/operateurs',     icon: Building2,        label: 'Opérateurs',          permission: 'operateurs.view_operateur' },
  { to: '/tracabilite',    icon: Package,          label: 'Traçabilité',         permission: 'traceability.view_traceability' },
  { to: '/documents',      icon: FileText,         label: 'Documents',           permission: 'archive.view_document' },
  { to: '/stats',          icon: BarChart3,        label: 'Statistiques',        permission: null },
  { to: '/nomenclature',   icon: BookOpen,         label: 'Nomenclature',        permission: null },
  { to: '/glossaire',      icon: GraduationCap,    label: 'Glossaire',           permission: null },
  { to: '/archive',        icon: FolderOpen,       label: 'Archive',             permission: 'archive.view_document' },
  { to: '/alertes',        icon: Bell,             label: 'Alertes',             permission: null },
]

function getNav(user) {
  const nav = [...NAV_BASE]
  if (user?.role === 'SUPERADMIN' || user?.role === 'ADMIN' || user?.is_superuser) {
    nav.push({ to: '/admin/roles', icon: Shield, label: 'Gestion Rôles', permission: null })
  }
  return nav
}

function Sidebar({ collapsed, onToggle, mobileOpen, onClose }) {
  const { user, logout, hasPermission } = useAuthStore()
  const navigate  = useNavigate()
  const location  = useLocation()
  const initials  = `${user?.first_name?.[0] || ''}${user?.last_name?.[0] || ''}`.toUpperCase() || 'U'
  const allPerms  = user?.permissions || []

  const filteredNav = getNav(user).filter(item => {
    if (!item.permission) return true
    if (user?.is_superuser) return true
    return allPerms.includes(item.permission)
  })

  return (
    <>
      {mobileOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />
      )}
      <aside className={clsx(
        'fixed top-0 left-0 h-full z-40 flex flex-col',
        'bg-white dark:bg-[#16240D]',
        'border-r border-[#E2E8F0] dark:border-[#2B3D1E] shadow-lg',
        'transition-all duration-300',
        collapsed ? 'w-[72px]' : 'w-[260px]',
        'lg:translate-x-0',
        mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      )}>

        {/* Logo */}
        <div className={clsx(
          'flex items-center h-16 px-4 border-b border-[#E2E8F0] dark:border-[#2B3D1E] flex-shrink-0',
          collapsed ? 'justify-center' : 'gap-3'
        )}>
          <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center flex-shrink-0">
            <Leaf className="w-4 h-4 text-white" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden flex-1">
              <span className="font-black text-slate-900 dark:text-white text-sm tracking-tight">Recup <span className="font-arabiya font-normal">نفاية</span></span>
            </div>
          )}
          <button onClick={onToggle}
            className="hidden lg:flex ml-auto w-6 h-6 rounded-md hover:bg-slate-100 dark:hover:bg-[#2B3D1E] items-center justify-center">
            {collapsed
              ? <ChevronRight className="w-4 h-4 text-slate-400" />
              : <ChevronLeft  className="w-4 h-4 text-slate-400" />
            }
          </button>
          {mobileOpen && (
            <button onClick={onClose} className="lg:hidden ml-auto">
              <X className="w-4 h-4 text-slate-400" />
            </button>
          )}
        </div>

        {/* User pill */}
        {!collapsed && (
          <div className="mx-3 mt-3 p-3 rounded-xl bg-[#F1F5F9] dark:bg-[#2B3D1E] flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-800 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
              {initials}
            </div>
            <div className="overflow-hidden flex-1">
              <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">
                {user?.first_name} {user?.last_name}
              </p>
              <span className="text-[0.6rem] text-slate-400">{user?.role_display || user?.role}</span>
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {filteredNav.map(item => {
            const active = location.pathname === item.to ||
              (item.to !== '/dashboard' && location.pathname.startsWith(item.to))
            return (
              <NavLink key={item.to} to={item.to} onClick={onClose}
                className={clsx(
                  'nav-item',
                  active && 'nav-item-active',
                  collapsed && 'justify-center px-0'
                )}>
                <item.icon className={clsx('flex-shrink-0', collapsed ? 'w-5 h-5' : 'w-4 h-4')} />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            )
          })}
        </nav>

        {/* Bottom — Profile + Logout */}
        <div className="px-2 pb-4 border-t border-[#E2E8F0] dark:border-[#2B3D1E] pt-2 space-y-0.5">
          <NavLink to="/profil" onClick={onClose}
            className={clsx(
              'nav-item',
              location.pathname === '/profil' && 'nav-item-active',
              collapsed && 'justify-center px-0'
            )}>
            <User className={clsx('flex-shrink-0', collapsed ? 'w-5 h-5' : 'w-4 h-4')} />
            {!collapsed && <span>Mon Profil</span>}
          </NavLink>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className={clsx(
              'nav-item w-full text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10',
              collapsed && 'justify-center px-0'
            )}>
            <LogOut className={clsx('flex-shrink-0', collapsed ? 'w-5 h-5' : 'w-4 h-4')} />
            {!collapsed && <span>Déconnexion</span>}
          </button>
        </div>
      </aside>
    </>
  )
}

function Header({ onMenu }) {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  const toggleDark = () => {
    const isDark = document.documentElement.classList.toggle('dark')
    setDark(isDark)
  }
  return (
    <header className="h-16 bg-white dark:bg-[#16240D] border-b border-[#E2E8F0] dark:border-[#2B3D1E] flex items-center px-4 gap-3 sticky top-0 z-20">
      <button onClick={onMenu} className="lg:hidden p-2 rounded-xl hover:bg-slate-100">
        <Menu className="w-5 h-5 text-slate-500" />
      </button>
      <div className="flex-1" />
      <button onClick={toggleDark} className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-[#16240D]">
        {dark
          ? <Sun  className="w-4 h-4 text-slate-500" />
          : <Moon className="w-4 h-4 text-slate-500" />
        }
      </button>
    </header>
  )
}

export default function Layout() {
  const [collapsed,  setCollapsed]  = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#0D1B0A] flex">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed(c => !c)}
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
      />
      <div className={clsx(
        'flex-1 flex flex-col min-h-screen transition-all duration-300',
        'lg:ml-[260px]',
        collapsed && 'lg:ml-[72px]'
      )}>
        <Header onMenu={() => setMobileOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 max-w-[1600px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
      <AIAssistantPage />
    </div>
  )
}
