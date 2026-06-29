import { useState, useMemo } from 'react'
import { Search, X, BookOpen, ChevronDown, ChevronRight, Globe } from 'lucide-react'
import { GLOSSAIRE, CATEGORIES } from './glossaireData'

// ── Class badge colors ────────────────────────────────────────────────────────
const CLASSE_CFG = {
  MA: 'bg-primary-100 text-primary-700 border border-primary-200',
  I:  'bg-emerald-100 text-emerald-700 border border-emerald-200',
  S:  'bg-amber-100 text-amber-700 border border-amber-200',
  SD: 'bg-red-100 text-red-700 border border-red-200',
}

const CAT_COLORS = {
  general:       'bg-primary-500',
  types:         'bg-teal-500',
  acteurs:       'bg-violet-500',
  documents:     'bg-primary-500',
  operations:    'bg-emerald-500',
  danger:        'bg-red-500',
  juridique:     'bg-amber-500',
  installations: 'bg-slate-500',
}

// ── Term Card ─────────────────────────────────────────────────────────────────
function TermCard({ terme, lang }) {
  const [open, setOpen] = useState(false)
  const showFr = lang === 'fr' || lang === 'both'
  const showAr = lang === 'ar' || lang === 'both'

  return (
    <div className={`card overflow-hidden transition-all ${open ? 'shadow-lg' : 'hover:shadow-md'}`}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-4 p-4 text-left hover:bg-slate-50 dark:hover:bg-[#16240D]/50 transition-colors"
      >
        {/* Number */}
        <div className="w-8 h-8 rounded-lg bg-primary-50 flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="text-xs font-black text-primary-600">{String(terme.id).padStart(2,'0')}</span>
        </div>

        {/* Terms */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="flex-1">
              {showFr && (
                <p className="font-bold text-slate-900 dark:text-white text-sm leading-tight">{terme.terme_fr}</p>
              )}
              {showAr && (
                <p className={`font-bold text-slate-700 dark:text-slate-200 text-sm leading-tight mt-0.5 ${lang === 'ar' ? 'text-right' : ''}`}
                  dir="rtl" style={{ fontFamily: '"Cairo", sans-serif' }}>
                  {terme.terme_ar}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {terme.classe && (
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${CLASSE_CFG[terme.classe]}`}>
                  {terme.classe}
                </span>
              )}
              {open
                ? <ChevronDown size={14} className="text-slate-400" />
                : <ChevronRight size={14} className="text-slate-400" />
              }
            </div>
          </div>
        </div>
      </button>

      {/* Expanded definition */}
      {open && (
        <div className="border-t border-[#E2E8F0] dark:border-[#2B3D1E]">
          {showFr && (
            <div className="px-5 py-4 bg-primary-50/30 dark:bg-primary-900/10">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-5 h-5 rounded bg-primary-500 flex items-center justify-center text-white text-[9px] font-black flex-shrink-0">FR</span>
                <span className="text-xs font-bold text-primary-700 dark:text-primary-300">Français</span>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {terme.definition_fr}
              </p>
            </div>
          )}
          {showAr && (
            <div className="px-5 py-4 bg-emerald-50/30 dark:bg-emerald-900/10 border-t border-[#E2E8F0] dark:border-[#2B3D1E]">
              <div className="flex items-center justify-end gap-2 mb-2">
                <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300">العربية</span>
                <span className="w-5 h-5 rounded bg-emerald-600 flex items-center justify-center text-white text-[9px] font-black flex-shrink-0">AR</span>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed text-right"
                dir="rtl" style={{ fontFamily: '"Cairo", sans-serif' }}>
                {terme.definition_ar}
              </p>
            </div>
          )}
          {/* Reference */}
          {terme.reference && (
            <div className="px-5 py-2.5 bg-slate-50 dark:bg-[#16240D]/50 border-t border-[#E2E8F0] dark:border-[#2B3D1E] flex items-center justify-between">
              <span className="text-[10px] text-slate-400 font-mono">Réf: {terme.reference}</span>
              {terme.classe && (
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${CLASSE_CFG[terme.classe]}`}>
                  Classe {terme.classe}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Category Section ──────────────────────────────────────────────────────────
function CategorySection({ category, termes, lang, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  const catColor = CAT_COLORS[category.id] || 'bg-slate-500'

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 py-2 text-left group"
      >
        <div className={`w-2 h-8 rounded-full ${catColor} flex-shrink-0`} />
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <span className="font-bold text-slate-900 dark:text-white">{category.label_fr}</span>
            <span className="text-slate-400 text-sm" dir="rtl" style={{ fontFamily: '"Cairo", sans-serif' }}>
              {category.label_ar}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 dark:bg-[#2B3D1E] text-slate-500">
            {termes.length}
          </span>
          {open
            ? <ChevronDown size={15} className="text-slate-400" />
            : <ChevronRight size={15} className="text-slate-400" />
          }
        </div>
      </button>

      {open && (
        <div className="space-y-2 pl-4 border-l-2 border-slate-100 dark:border-[#2B3D1E]">
          {termes.length === 0 ? (
            <p className="text-sm text-slate-400 py-2">Aucun terme dans cette catégorie</p>
          ) : (
            termes.map(t => <TermCard key={t.id} terme={t} lang={lang} />)
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function GlossairePage() {
  const [search,      setSearch]      = useState('')
  const [lang,        setLang]        = useState('both')   // fr | ar | both
  const [classeFilter,setClasseFilter]= useState('')
  const [catFilter,   setCatFilter]   = useState('')
  const [viewMode,    setViewMode]    = useState('grouped') // grouped | flat

  // Filter logic
  const filtered = useMemo(() => {
    return GLOSSAIRE.filter(t => {
      const matchSearch = !search || (
        t.terme_fr.toLowerCase().includes(search.toLowerCase()) ||
        t.terme_ar.includes(search) ||
        t.definition_fr.toLowerCase().includes(search.toLowerCase()) ||
        t.definition_ar.includes(search)
      )
      const matchClasse = !classeFilter || t.classe === classeFilter
      const matchCat    = !catFilter    || t.categorie === catFilter
      return matchSearch && matchClasse && matchCat
    })
  }, [search, classeFilter, catFilter])

  // Group by category
  const grouped = useMemo(() => {
    return CATEGORIES.map(cat => ({
      category: cat,
      termes:   filtered.filter(t => t.categorie === cat.id),
    })).filter(g => g.termes.length > 0)
  }, [filtered])

  return (
    <div className="space-y-5 max-w-4xl mx-auto">

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <BookOpen size={24} className="text-primary-600" />
            Glossaire des déchets
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {GLOSSAIRE.length} termes — Français / العربية
          </p>
          <p className="text-slate-400 text-xs mt-0.5" dir="rtl" style={{ fontFamily: '"Cairo", sans-serif' }}>
            مسرد مصطلحات النفايات — {GLOSSAIRE.length} مصطلح
          </p>
        </div>
        {/* Lang switcher */}
        <div className="flex gap-1 bg-slate-100 dark:bg-[#16240D] rounded-xl p-1">
          {[
            { key: 'both', label: 'FR / AR', icon: '🌐' },
            { key: 'fr',   label: 'Français', icon: '🇫🇷' },
            { key: 'ar',   label: 'العربية',  icon: '🇩🇿' },
          ].map(l => (
            <button key={l.key} onClick={() => setLang(l.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
                ${lang === l.key
                  ? 'bg-white dark:bg-[#2B3D1E] text-slate-900 dark:text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'}`}>
              {l.icon} {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats chips */}
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map(cat => {
          const count = GLOSSAIRE.filter(t => t.categorie === cat.id).length
          const color = CAT_COLORS[cat.id] || 'bg-slate-500'
          return (
            <button key={cat.id}
              onClick={() => setCatFilter(catFilter === cat.id ? '' : cat.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border-2 transition-all
                ${catFilter === cat.id
                  ? `${color} text-white border-transparent`
                  : 'border-slate-200 text-slate-600 hover:border-slate-300 bg-white dark:bg-[#16240D] dark:border-[#2B3D1E] dark:text-slate-300'}`}>
              {cat.label_fr}
              <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-black
                ${catFilter === cat.id ? 'bg-white/30 text-white' : 'bg-slate-100 text-slate-500'}`}>
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Filters bar */}
      <div className="card p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-56">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher un terme en français أو بالعربية..."
            className="input pl-9 text-sm"
          />
          {search && (
            <button onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <X size={13} />
            </button>
          )}
        </div>
        <select value={classeFilter} onChange={e => setClasseFilter(e.target.value)}
          className="input w-40 text-sm">
          <option value="">Toutes classes</option>
          <option value="MA">MA — Ménagers</option>
          <option value="I">I — Inertes</option>
          <option value="S">S — Spéciaux</option>
          <option value="SD">SD — Dangereux</option>
        </select>
        <div className="flex gap-1 bg-slate-100 dark:bg-[#16240D] rounded-xl p-1 ml-auto">
          <button onClick={() => setViewMode('grouped')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
              ${viewMode === 'grouped' ? 'bg-white dark:bg-[#2B3D1E] shadow-sm text-slate-900' : 'text-slate-500'}`}>
            Par catégorie
          </button>
          <button onClick={() => setViewMode('flat')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all
              ${viewMode === 'flat' ? 'bg-white dark:bg-[#2B3D1E] shadow-sm text-slate-900' : 'text-slate-500'}`}>
            Tout afficher
          </button>
        </div>
        <span className="text-xs text-slate-400">{filtered.length} terme(s)</span>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2 text-xs">
        {[
          { cls:'MA', label:'Ménagers et Assimilés' },
          { cls:'I',  label:'Inertes'              },
          { cls:'S',  label:'Spéciaux'             },
          { cls:'SD', label:'Spéciaux Dangereux'   },
        ].map(c => (
          <span key={c.cls} className={`px-2.5 py-1 rounded-full font-semibold ${CLASSE_CFG[c.cls]}`}>
            {c.cls} — {c.label}
          </span>
        ))}
      </div>

      {/* Content */}
      {filtered.length === 0 ? (
        <div className="card p-16 text-center">
          <BookOpen size={40} className="mx-auto mb-3 text-slate-200" />
          <p className="font-semibold text-slate-400">Aucun terme trouvé</p>
          <p className="text-sm text-slate-300 mt-1" dir="rtl" style={{ fontFamily: '"Cairo", sans-serif' }}>
            لم يُعثر على أي مصطلح
          </p>
          <button onClick={() => { setSearch(''); setClasseFilter(''); setCatFilter('') }}
            className="btn-secondary btn-sm mt-4">
            Réinitialiser les filtres
          </button>
        </div>
      ) : viewMode === 'grouped' ? (
        <div className="space-y-6">
          {grouped.map((g, i) => (
            <CategorySection
              key={g.category.id}
              category={g.category}
              termes={g.termes}
              lang={lang}
              defaultOpen={i === 0 || !!search || !!catFilter}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(t => <TermCard key={t.id} terme={t} lang={lang} />)}
        </div>
      )}

      {/* Footer note */}
      <div className="card p-4 bg-slate-50/50 dark:bg-[#16240D]/30">
        <p className="text-xs text-slate-400 leading-relaxed">
          <span className="font-semibold text-slate-500">Références réglementaires :</span>{' '}
          Loi n°01-19 du 12 décembre 2001 relative à la gestion, au contrôle et à l'élimination des déchets —
          Décret exécutif n°06-104 du 28 février 2006 fixant la nomenclature des déchets —
          Décret exécutif n°05-315 du 10 septembre 2005 fixant les modalités de déclaration des déchets spéciaux dangereux.
        </p>
        <p className="text-xs text-slate-400 leading-relaxed mt-1 text-right" dir="rtl"
          style={{ fontFamily: '"Cairo", sans-serif' }}>
          <span className="font-semibold text-slate-500">المراجع التنظيمية:</span>{' '}
          القانون رقم 01-19 المؤرخ في 12 ديسمبر 2001 المتعلق بتسيير النفايات ومراقبتها وإزالتها —
          المرسوم التنفيذي رقم 06-104 المؤرخ في 28 فبراير 2006 الذي يحدد تسمية النفايات —
          المرسوم التنفيذي رقم 05-315 المؤرخ في 10 سبتمبر 2005 الذي يحدد كيفيات التصريح بالنفايات الخاصة الخطرة.
        </p>
      </div>

    </div>
  )
}
