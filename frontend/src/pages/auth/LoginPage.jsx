import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { Eye, EyeOff, ArrowRight, Leaf } from 'lucide-react'
import { useAuthStore } from '../../store'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const { register, handleSubmit, formState: { errors } } = useForm()
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const login    = useAuthStore(s => s.login)
  const navigate = useNavigate()

  const onSubmit = async (data) => {
    setLoading(true)
    try {
      await login(data.username, data.password)
      navigate('/dashboard')
    } catch (err) {
      if (err.response) toast.error('Identifiants incorrects')
      else toast.error('Impossible de contacter le serveur — vérifiez que le backend est démarré')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">

      {/* LEFT — flat green panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-primary-950 p-12 lg:p-16">
        <div className="flex items-center gap-2.5">
          <div className="w-10 h-10 rounded-[10px] bg-primary-600 flex items-center justify-center flex-shrink-0">
            <Leaf className="w-5 h-5 text-white" />
          </div>
          <span className="text-base font-medium text-primary-50">Recup <span className="font-arabiya">نفاية</span></span>
        </div>

        <div>
          <h1 className="text-[32px] lg:text-[36px] font-medium leading-[1.25] text-primary-50 mb-5 tracking-tight max-w-md">
            La plateforme intelligente de gestion des déchets, conforme à la
            réglementation et garante d'une traçabilité complète.
          </h1>
          <p className="text-sm leading-relaxed text-primary-200 max-w-xs">
            Faciliter le suivi, renforcer la traçabilité et accompagner les acteurs agréés
            dans une gestion responsable des déchets.
          </p>
          <div className="w-10 h-0.5 bg-primary-500 mt-6" />
        </div>
      </div>

      {/* RIGHT — simple login form */}
      <div className="flex-1 flex flex-col bg-[#F8FAFC] p-6">
        {/* mobile logo (left panel hidden below lg) */}
        <div className="lg:hidden flex items-center gap-2.5 mb-10">
          <div className="w-10 h-10 rounded-[10px] bg-primary-600 flex items-center justify-center flex-shrink-0">
            <Leaf className="w-5 h-5 text-white" />
          </div>
          <span className="text-base font-medium text-slate-900">Recup <span className="font-arabiya">نفاية</span></span>
        </div>

        <div className="flex-1 flex items-center justify-center lg:justify-start lg:pl-16">
          <div className="w-full max-w-sm">
            <h2 className="text-2xl font-semibold text-slate-900 mb-1">Bienvenue</h2>
            <p className="text-sm text-slate-500 mb-8">Connectez-vous à votre espace</p>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1.5">Nom d'utilisateur</label>
                <input {...register('username', { required: true })}
                  className={`w-full bg-white border rounded-[10px] px-3.5 py-2.5 text-sm text-slate-800
                    placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-400
                    ${errors.username ? 'border-red-400 ring-2 ring-red-100' : 'border-slate-200'}`}
                  placeholder="admin_indurex" autoComplete="username" />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1.5">Mot de passe</label>
                <div className={`flex items-center bg-white border rounded-[10px] px-3.5
                    ${errors.password ? 'border-red-400 ring-2 ring-red-100' : 'border-slate-200 focus-within:ring-2 focus-within:ring-primary-400'}`}>
                  <input {...register('password', { required: true })}
                    type={showPwd ? 'text' : 'password'}
                    className="flex-1 bg-transparent py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
                    placeholder="••••••••" autoComplete="current-password" />
                  <button type="button" onClick={() => setShowPwd(!showPwd)} className="text-slate-400 hover:text-slate-600 flex-shrink-0">
                    {showPwd ? <EyeOff className="w-[15px] h-[15px]" /> : <Eye className="w-[15px] h-[15px]" />}
                  </button>
                </div>
              </div>

              <button type="submit" disabled={loading}
                className="w-full bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-[10px] py-3 flex items-center justify-center gap-2 mt-2 transition-colors disabled:opacity-60">
                {loading
                  ? <span className="flex items-center gap-2">
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Connexion...
                    </span>
                  : <span className="flex items-center gap-2">
                      Se connecter <ArrowRight className="w-4 h-4" />
                    </span>
                }
              </button>
            </form>

            <p className="text-center text-[11px] text-slate-400 mt-6">
              Conforme à la Loi n°01-19 et au Décret n°06-104
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
