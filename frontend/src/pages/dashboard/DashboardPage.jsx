import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Users, Package, FileText, AlertTriangle, CheckCircle2, Clock, XCircle, TrendingUp } from 'lucide-react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { recuperateursAPI } from '../../api'

const COLORS = ['#4F46E5','#10b981','#f59e0b','#ef4444','#8b5cf6','#14b8a6','#6b7280']

export default function DashboardPage() {
  const [stats,  setStats]  = useState(null)
  const [alerts, setAlerts] = useState([])

  useEffect(() => {
    recuperateursAPI.stats().then(r => setStats(r.data)).catch(() => {})
    recuperateursAPI.alerts().then(r => setAlerts(r.data.alerts || [])).catch(() => {})
  }, [])

  const TYPE_LABELS = {
    CAT1: 'Sans agrément', CAT2: 'Déchets Spéciaux',
    CAT3: 'Déchets SD',    CAT4: 'Carte Professionnelle'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Tableau de bord</h1>
        <p className="text-slate-500 text-sm mt-0.5">Système de gestion des récupérateurs de déchets — Algérie</p>
      </div>

      {/* Alerts banner */}
      {alerts.length > 0 && (
        <div className="card border-l-4 border-red-500 bg-red-50/40 p-4 flex items-start gap-3">
          <AlertTriangle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-red-800 text-sm">{alerts.length} alerte(s) active(s)</p>
            <p className="text-xs text-red-600 mt-0.5">{alerts[0]?.message}</p>
          </div>
        </div>
      )}

      {/* KPIs */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total récupérateurs', value: stats.total,      icon: Users,        color: 'bg-primary-500' },
            { label: 'Actifs',              value: stats.actifs,     icon: CheckCircle2, color: 'bg-emerald-500' },
            { label: 'Agréments expirant',  value: stats.expirant,   icon: Clock,        color: 'bg-amber-500'   },
            { label: 'Agréments expirés',   value: stats.expires,    icon: XCircle,      color: 'bg-red-500'     },
          ].map(k => (
            <div key={k.label} className="card p-5 flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl ${k.color} flex items-center justify-center flex-shrink-0`}>
                <k.icon size={22} className="text-white" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 dark:text-white">{k.value ?? '—'}</p>
                <p className="text-xs text-slate-500 leading-tight">{k.label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Charts */}
      {stats && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* By type */}
          {stats.par_type?.length > 0 && (
            <div className="card p-5">
              <h3 className="font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <TrendingUp size={16} className="text-primary-600" /> Par catégorie
              </h3>
              <div className="flex gap-4 items-center">
                <ResponsiveContainer width="50%" height={180}>
                  <PieChart>
                    <Pie data={stats.par_type} dataKey="count" cx="50%" cy="50%" outerRadius={70}
                      label={({ percent }) => `${(percent*100).toFixed(0)}%`} labelLine={false}>
                      {stats.par_type.map((_,i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v,n) => [v, TYPE_LABELS[n] || n]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 space-y-2">
                  {stats.par_type.map((r, i) => (
                    <div key={r.type_recuperateur} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ background: COLORS[i%COLORS.length] }} />
                        <span className="text-xs text-slate-600">{TYPE_LABELS[r.type_recuperateur] || r.type_recuperateur}</span>
                      </div>
                      <span className="text-xs font-bold">{r.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* By wilaya */}
          {stats.par_wilaya?.length > 0 && (
            <div className="card p-5">
              <h3 className="font-bold text-slate-900 dark:text-white mb-4">Par wilaya</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={stats.par_wilaya.slice(0,10)} margin={{ bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="wilaya" tick={{ fontSize: 10 }}
                    label={{ value: 'Wilaya', position: 'insideBottom', offset: -10, fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="count" name="Récupérateurs" fill="#4F46E5" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { to: '/tracabilite',       label: 'Nouveau dossier',      icon: Package, color: 'border-emerald-200 hover:border-emerald-400 hover:bg-emerald-50' },
          { to: '/documents',         label: 'BSD / Déclarations',   icon: FileText, color: 'border-amber-200 hover:border-amber-400 hover:bg-amber-50' },
        ].map(item => (
          <Link key={item.label} to={item.to}
            className={`card p-4 flex items-center gap-3 border-2 transition-all ${item.color}`}>
            <item.icon size={18} className="text-slate-600 flex-shrink-0" />
            <span className="text-sm font-semibold text-slate-700 leading-tight">{item.label}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
