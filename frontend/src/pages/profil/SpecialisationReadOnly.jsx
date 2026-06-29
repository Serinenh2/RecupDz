import { useEffect, useState } from 'react'
import { CheckCircle2, ChevronDown, ChevronRight } from 'lucide-react'
import api from '../../api'

/**
 * SpecialisationReadOnly
 * Affiche la hiérarchie complète (Catégorie > SousCatégorie > Détail) en lecture
 * seule, en surlignant les `DetailSpecialisation` cochés par l'administrateur
 * (assignedIds = liste des IDs de DetailSpecialisation liés au récupérateur).
 */
export default function SpecialisationReadOnly({ assignedIds = [] }) {
  const [hierarchie, setHierarchie] = useState([])
  const [loading, setLoading]       = useState(true)
  const [openCats, setOpenCats]     = useState({})

  useEffect(() => {
    api.get('/recuperateurs/specialisation-hierarchie/')
      .then(r => {
        setHierarchie(r.data)
        // Ouvre automatiquement les catégories qui contiennent au moins un détail assigné
        const open = {}
        r.data.forEach(cat => {
          const hasAssigned = cat.sous_categories.some(sc =>
            sc.details.some(d => assignedIds.includes(d.id))
          )
          if (hasAssigned) open[cat.id] = true
        })
        setOpenCats(open)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const toggleCat = (id) => setOpenCats(prev => ({ ...prev, [id]: !prev[id] }))

  if (loading) {
    return <p className="text-sm text-slate-400 text-center py-6">Chargement...</p>
  }

  if (hierarchie.length === 0) {
    return <p className="text-sm text-slate-400 text-center py-6">Aucune hiérarchie de spécialisation configurée.</p>
  }

  const totalAssigned = assignedIds.length

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500 font-semibold">
        {totalAssigned > 0
          ? `${totalAssigned} type(s) de déchets assigné(s)`
          : "Aucune spécialisation assignée pour l'instant"}
      </p>

      {hierarchie.map(cat => {
        const isOpen = !!openCats[cat.id]
        const catAssignedCount = cat.sous_categories.reduce(
          (sum, sc) => sum + sc.details.filter(d => assignedIds.includes(d.id)).length, 0
        )
        return (
          <div key={cat.id} className={`rounded-xl border overflow-hidden
            ${catAssignedCount > 0 ? 'border-primary-200' : 'border-[#E2E8F0] dark:border-[#2B3D1E]'}`}>
            <button type="button" onClick={() => toggleCat(cat.id)}
              className={`w-full flex items-center justify-between px-4 py-3 transition-colors
                ${catAssignedCount > 0 ? 'bg-primary-50/60 dark:bg-primary-900/10' : 'bg-slate-50 dark:bg-[#16240D]/40'}`}>
              <span className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-200">
                <span className="text-base">{cat.icone}</span> {cat.nom}
                {catAssignedCount > 0 && (
                  <span className="ml-1 px-2 py-0.5 rounded-full bg-primary-600 text-white text-[10px]">
                    {catAssignedCount}
                  </span>
                )}
              </span>
              {isOpen ? <ChevronDown size={15} className="text-slate-400"/> : <ChevronRight size={15} className="text-slate-400"/>}
            </button>

            {isOpen && (
              <div className="px-4 py-3 space-y-3 bg-white dark:bg-[#16240D]">
                {cat.sous_categories.map(sc => (
                  <div key={sc.id}>
                    <p className="text-xs font-bold text-slate-500 mb-1.5">{sc.nom}</p>
                    {sc.details.length === 0 ? (
                      <p className="text-xs text-slate-400 italic pl-2">— (pas de sous-détail, catégorie globale)</p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {sc.details.map(d => {
                          const checked = assignedIds.includes(d.id)
                          return (
                            <span key={d.id}
                              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold
                                ${checked
                                  ? 'bg-primary-600 text-white'
                                  : 'bg-slate-100 dark:bg-[#16240D] text-slate-400 line-through opacity-50'}`}>
                              {checked && <CheckCircle2 size={11}/>}
                              {d.nom}
                            </span>
                          )
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
