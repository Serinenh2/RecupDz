import { useState, useMemo } from 'react'
import { Search, X, Package } from 'lucide-react'
import { NOMENCLATURE_ENTREPRISE } from './nomenclatureEntreprise'

const COND_BADGE = {
  Kilogramme: 'badge-blue',
  Unité:      'badge-green',
}

export default function NomenclaturePage() {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return NOMENCLATURE_ENTREPRISE.filter(item =>
      !q ||
      item.designation.toLowerCase().includes(q) ||
      item.reference.toLowerCase().includes(q)
    )
  }, [search])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Nomenclature</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Catalogue des désignations de l'entreprise — {NOMENCLATURE_ENTREPRISE.length} articles
        </p>
      </div>

      {/* Search */}
      <div className="card p-4">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher par désignation ou référence..."
            className="input pl-9 text-sm" />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          {filtered.length === 0 ? (
            <p className="text-center py-10 text-slate-400 text-sm">Aucun résultat</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 dark:bg-[#2B3D1E] border-b border-gray-200 dark:border-[#2B3D1E]">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Désignation</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Référence</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide w-40">Conditionnement</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(item => (
                  <tr key={item.reference} className="border-b border-gray-50 dark:border-[#2B3D1E] last:border-0 hover:bg-primary-50/40 dark:hover:bg-[#2B3D1E]/40 transition-colors">
                    <td className="px-4 py-3 flex items-center gap-2 text-slate-800 dark:text-slate-100">
                      <Package size={14} className="text-primary-500 flex-shrink-0" />
                      {item.designation}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs font-bold text-primary-700 bg-primary-50 px-2 py-1 rounded">
                        {item.reference}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${COND_BADGE[item.conditionnement] || 'badge-gray'}`}>
                        {item.conditionnement}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
