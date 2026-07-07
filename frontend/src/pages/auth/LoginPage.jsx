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

      {/* LEFT — dark green editorial panel */}
      <div className="hidden lg:flex lg:w-1/2 relative flex-col p-12 lg:p-16 overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #173404 0%, #2D5A0F 60%, #3B6D11 100%)' }}>

        {/* decorative environmental illustrations */}
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 500 600" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <circle cx="60" cy="540" r="180" fill="none" stroke="#97C459" strokeWidth="1" opacity="0.15" />
          <circle cx="60" cy="540" r="240" fill="none" stroke="#97C459" strokeWidth="1" opacity="0.15" />

          {/* foliage branch — bottom left */}
          <g opacity="0.5">
            <path d="M70 600 L70 460 Q70 430 90 400 L110 370" stroke="#27500A" strokeWidth="8" fill="none" strokeLinecap="round" />
            <ellipse cx="100" cy="370" rx="55" ry="35" fill="#2D5A0F" transform="rotate(-30 100 370)" />
            <ellipse cx="60" cy="395" rx="45" ry="28" fill="#27500A" transform="rotate(15 60 395)" />
            <ellipse cx="125" cy="330" rx="48" ry="30" fill="#3B6D11" transform="rotate(-50 125 330)" />
            <ellipse cx="40" cy="340" rx="38" ry="24" fill="#1C3611" transform="rotate(40 40 340)" />
          </g>

          {/* foliage branch — bottom right */}
          <g opacity="0.45" transform="translate(380,520)">
            <path d="M0 80 L0 -20 Q0 -45 -15 -65 L-30 -90" stroke="#27500A" strokeWidth="6" fill="none" strokeLinecap="round" />
            <ellipse cx="-25" cy="-90" rx="40" ry="26" fill="#3B6D11" transform="rotate(-35 -25 -90)" />
            <ellipse cx="15" cy="-70" rx="36" ry="22" fill="#2D5A0F" transform="rotate(25 15 -70)" />
            <ellipse cx="-45" cy="-50" rx="32" ry="20" fill="#27500A" transform="rotate(60 -45 -50)" />
          </g>

          {/* recycling cycle icon — right */}
          <g opacity="0.35" transform="translate(420,150)">
            <circle cx="0" cy="0" r="46" fill="none" stroke="#97C459" strokeWidth="2" />
            <path d="M-30 -10 A30 30 0 0 1 10 -30" stroke="#97C459" strokeWidth="3" fill="none" strokeLinecap="round" />
            <path d="M30 10 A30 30 0 0 1 -10 30" stroke="#97C459" strokeWidth="3" fill="none" strokeLinecap="round" />
            <path d="M-26 -18 L-30 -8 L-18 -10 Z" fill="#97C459" />
            <path d="M26 18 L30 8 L18 10 Z" fill="#97C459" />
          </g>

          {/* small isolated leaf — top */}
          <g opacity="0.4" transform="translate(180,90)">
            <ellipse cx="0" cy="0" rx="32" ry="20" fill="#3B6D11" transform="rotate(-20 0 0)" />
            <ellipse cx="-2" cy="-2" rx="18" ry="10" fill="#5C8C2E" transform="rotate(-20 -2 -2)" />
          </g>
        </svg>

        {/* logo */}
        <div className="relative z-10 flex items-center gap-2.5 mb-16">
          <div className="w-10 h-10 rounded-[10px] bg-primary-600 flex items-center justify-center flex-shrink-0">
            <Leaf className="w-5 h-5 text-white" />
          </div>
          <span className="text-base font-medium text-[#EAF3DE]">Recup <span className="font-arabiya">نفاية</span></span>
        </div>

        <div className="relative z-10 inline-flex items-center gap-2 mb-4 self-start">
          <span className="w-1.5 h-1.5 rounded-full bg-[#97C459]" />
          <span className="text-[11px] font-medium text-[#97C459] tracking-wide">DEPUIS 2022 AU SERVICE DE L'ENVIRONNEMENT</span>
        </div>

        <h1 className="relative z-10 text-[32px] lg:text-[36px] font-medium leading-[1.25] text-[#EAF3DE] mb-5 tracking-tight">
          La plateforme intelligente de gestion des déchets, conforme à la
          réglementation et garante d'une traçabilité complète.
        </h1>

        <p className="relative z-10 text-sm leading-relaxed text-[#C0DD97] max-w-xs">
          Accompagner les récupérateurs agréés dans le suivi conforme et la
          valorisation responsable de chaque déchet collecté.
        </p>

        <div className="relative z-10 flex gap-8 mt-auto">
          <div>
            <p className="text-2xl font-medium text-[#EAF3DE]">208</p>
            <p className="text-[11px] text-[#97C459] mt-0.5">Codes déchets</p>
          </div>
          <div>
            <p className="text-2xl font-medium text-[#EAF3DE]">100%</p>
            <p className="text-[11px] text-[#97C459] mt-0.5">Conformité</p>
          </div>
        </div>
      </div>

      {/* RIGHT — botanical illustration + glassmorphism login card */}
      <div className="flex-1 relative flex items-center justify-center overflow-hidden p-6"
        style={{
          background: `
            linear-gradient(105deg, #234D0C 0%, #234D0C 38%, transparent 38.5%),
            radial-gradient(ellipse at 75% 30%, #3B6D11 0%, #5C8C2E 35%, #8FAE52 60%, #D8E8C2 85%)
          `
        }}>

        {/* botanical illustration — leaves + tuber/root */}
        <svg className="hidden lg:block absolute -right-10 -top-5" width="420" height="520" viewBox="0 0 420 520" aria-hidden="true">
          <path d="M210 480 C190 380 200 280 215 180 C225 110 250 60 290 30" stroke="#1C3611" strokeWidth="10" fill="none" strokeLinecap="round" />
          <path d="M215 180 C150 150 90 160 40 110 C100 130 160 140 215 180 Z" fill="#3B6D11" />
          <path d="M215 180 C150 150 90 160 40 110 C100 145 160 165 215 180 Z" fill="#5C8C2E" opacity="0.7" />
          <path d="M225 150 C290 100 360 90 410 30 C350 70 290 95 225 150 Z" fill="#27500A" />
          <path d="M225 150 C290 110 360 105 410 30 C355 80 290 110 225 150 Z" fill="#3B6D11" opacity="0.7" />
          <path d="M250 90 C300 50 340 20 380 -10 C335 30 295 55 250 90 Z" fill="#173404" />
          <ellipse cx="220" cy="430" rx="34" ry="44" fill="#C77B3E" />
          <ellipse cx="195" cy="450" rx="22" ry="30" fill="#B8682E" />
          <ellipse cx="245" cy="455" rx="20" ry="28" fill="#D08A4A" />
          <ellipse cx="215" cy="475" rx="26" ry="20" fill="#A8602A" />
        </svg>

        {/* mobile logo (left panel hidden below lg) */}
        <div className="lg:hidden absolute top-6 left-6 flex items-center gap-2.5 z-10">
          <div className="w-10 h-10 rounded-[10px] bg-primary-600 flex items-center justify-center flex-shrink-0">
            <Leaf className="w-5 h-5 text-white" />
          </div>
          <span className="text-base font-medium text-white">Recup <span className="font-arabiya">نفاية</span></span>
        </div>

        {/* glassmorphism login card */}
        <div className="relative z-10 w-full max-w-sm rounded-[18px] p-8"
          style={{
            background: 'rgba(255,255,255,0.92)',
            backdropFilter: 'blur(10px)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
          }}>

          <h2 className="text-2xl font-medium text-[#1a1a1a] mb-1">Bienvenue</h2>
          <p className="text-sm text-[#6b6b6b] mb-6">Connectez-vous à votre espace</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-xs text-[#6b6b6b] mb-1.5">Nom d'utilisateur</label>
              <div className={`flex items-center gap-2 bg-[#F4F6EF] rounded-[10px] px-3.5 py-2.5
                ${errors.username ? 'ring-2 ring-red-400' : ''}`}>
                <svg className="w-[15px] h-[15px] text-[#888] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                <input {...register('username', { required: true })}
                  className="flex-1 bg-transparent text-sm text-[#333] placeholder:text-[#999] focus:outline-none"
                  placeholder="admin_gold" autoComplete="username" />
              </div>
            </div>

            <div>
              <label className="block text-xs text-[#6b6b6b] mb-1.5">Mot de passe</label>
              <div className={`flex items-center gap-2 bg-[#F4F6EF] rounded-[10px] px-3.5 py-2.5
                ${errors.password ? 'ring-2 ring-red-400' : ''}`}>
                <svg className="w-[15px] h-[15px] text-[#888] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <input {...register('password', { required: true })}
                  type={showPwd ? 'text' : 'password'}
                  className="flex-1 bg-transparent text-sm text-[#333] placeholder:text-[#999] focus:outline-none"
                  placeholder="••••••••" autoComplete="current-password" />
                <button type="button" onClick={() => setShowPwd(!showPwd)} className="text-[#aaa] hover:text-[#777] flex-shrink-0">
                  {showPwd ? <EyeOff className="w-[15px] h-[15px]" /> : <Eye className="w-[15px] h-[15px]" />}
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading}
              className="w-full text-white text-sm font-medium rounded-[10px] py-3 flex items-center justify-center gap-2 mt-2 transition-opacity hover:opacity-90"
              style={{ background: 'linear-gradient(135deg, #639922, #3B6D11)' }}>
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

          <p className="text-center text-[11px] text-[#999] mt-4">
            Conforme à la Loi n°01-19 et au Décret n°06-104
          </p>
        </div>
      </div>
    </div>
  )
}
