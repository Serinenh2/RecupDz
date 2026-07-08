import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { FileText, Download, Eye, AlertTriangle } from 'lucide-react'
import api from '../../api'
import { useAuthStore } from '../../store'
import DateInput from '../../components/common/DateInput'
import toast from 'react-hot-toast'

// Defined once at module scope (not inside the form component) so their identity
// stays stable across re-renders — otherwise React remounts the wrapped <input>
// on every keystroke (this form re-renders on every watch()'d change), which
// makes text fields lose focus after each character typed.
function F({ label, req, children, col }) {
  return (
    <div className={col}>
      <label className="label">{label}{req && <span className="text-red-500 ml-0.5">*</span>}</label>
      {children}
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <div className="bg-slate-100 dark:bg-[#2B3D1E] px-4 py-2 rounded-lg">
      <p className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wide">{children}</p>
    </div>
  )
}

export default function DSDForm({ onClose, prefill = {} }) {
  const { user } = useAuthStore()
  const [generating, setGenerating] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const { register, handleSubmit, watch, setValue } = useForm({
    defaultValues: {
      annee:                 prefill.annee                || new Date().getFullYear().toString(),
      date_transmission:     '',
      statut:                user?.recuperateur_nom ? 'SARL' : '',
      denomination:          user?.recuperateur_nom || '',
      siege_social:          '',
      domaine_activite:      'Collecte et récupération de déchets spéciaux dangereux',
      certification:         '',
      responsable_dechets:   `${user?.first_name || ''} ${user?.last_name || ''}`.trim(),
      code_dechet:           prefill.code_dechet          || '',
      denomination_dechet:   prefill.denomination_dechet  || '',
      quantite_generee:      prefill.quantite_generee     || '0',
      consistance:           prefill.consistance          || '',
      reutilisation_qte:     '0',
      recyclage_qte:         '0',
      valorisation_qte:      '0',
      elimination_qte:       '0',
    }
  })

  const generatePdf = async (data) => {
    const response = await api.post('/declarations/generate-dsd/', data, {
      responseType: 'blob'
    })
    return new Blob([response.data], { type: 'application/pdf' })
  }

  const onSubmit = async (data) => {
    setGenerating(true)
    try {
      const blob = await generatePdf(data)
      const url  = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href  = url
      link.setAttribute('download', `DSD_${data.denomination}_${data.annee}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('DSD générée et téléchargée')
    } catch {
      toast.error('Erreur génération PDF')
    } finally {
      setGenerating(false)
    }
  }

  const onPreview = async (data) => {
    setPreviewing(true)
    try {
      const blob = await generatePdf(data)
      const url  = window.URL.createObjectURL(blob)
      window.open(url, '_blank')
    } catch {
      toast.error('Erreur génération aperçu')
    } finally {
      setPreviewing(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 p-3 rounded-xl bg-amber-50 border border-amber-200">
        <AlertTriangle size={16} className="text-amber-500 flex-shrink-0" />
        <p className="text-xs text-amber-700">
          <strong>Décret exécutif n°05-315</strong> — La déclaration doit être transmise dans un délai n'excédant pas
          3 mois après la clôture de l'année considérée.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

        {/* Identification */}
        <SectionTitle>Identification du générateur et/ou du détenteur</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <F label="Année" req col="">
            <input {...register('annee',{required:true})} className="input" placeholder="2024" />
          </F>
          <F label="Date de transmission" req col="">
            <DateInput value={watch('date_transmission')||''} onChange={v=>setValue('date_transmission',v)} />
          </F>
          <F label="Statut de l'entreprise" req col="">
            <select {...register('statut',{required:true})} className="input">
              <option value="">--</option>
              {['EURL','SARL','SPA','SNC','PHYSIQUE','AUTRE'].map(s=><option key={s}>{s}</option>)}
            </select>
          </F>
          <F label="Dénomination de l'entreprise" req col="">
            <input {...register('denomination',{required:true})} className="input" />
          </F>
          <F label="Siège social" req col="md:col-span-2">
            <input {...register('siege_social',{required:true})} className="input" placeholder="Adresse complète..." />
          </F>
          <F label="Domaine d'activité" req col="">
            <input {...register('domaine_activite',{required:true})} className="input" />
          </F>
          <F label="Certification éventuelle" col="">
            <input {...register('certification')} className="input" placeholder="Agrément n°..." />
          </F>
          <F label="Nom du responsable gestion des déchets" req col="md:col-span-2">
            <input {...register('responsable_dechets',{required:true})} className="input" />
          </F>
        </div>

        {/* Section A */}
        <SectionTitle>A — Nature, quantité et caractéristiques des déchets spéciaux dangereux</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <F label="Matière première utilisée" col="">
            <input {...register('matiere_premiere')} className="input" placeholder="Huiles usagées, solvants..." />
          </F>
          <F label="Dénomination du déchet" req col="">
            <input {...register('denomination_dechet',{required:true})} className="input" />
          </F>
          <F label="Code du déchet" req col="">
            <input {...register('code_dechet',{required:true})} className="input" placeholder="4.1.5, 6.1.5..." />
          </F>
          <F label="Consistance du déchet" col="">
            <select {...register('consistance')} className="input">
              <option value="">--</option>
              <option>Solide</option><option>Liquide</option>
              <option>Gazeux</option><option>Pâteux</option>
              <option>Liquide / Pâteux</option>
            </select>
          </F>
          <F label="Autres précisions (mélanges)" col="md:col-span-2">
            <input {...register('autres_precisions')} className="input" />
          </F>
          <F label="Quantité générée (t/an)" req col="">
            <input {...register('quantite_generee',{required:true})} type="number" step="0.01" className="input" placeholder="0" />
          </F>
          <F label="Composition chimique" col="">
            <input {...register('composition_chimique')} className="input" />
          </F>
          <F label="Critère de dangerosité" req col="md:col-span-2">
            <input {...register('critere_dangerosite',{required:true})} className="input" placeholder="Inflammable, Toxique..." />
          </F>
          <F label="Stockage temporaire (t/an)" col="">
            <input {...register('stockage_temporaire_qte')} type="number" step="0.01" className="input" placeholder="0" />
          </F>
          <F label="Stockage permanent (t/an)" col="">
            <input {...register('stockage_permanent_qte')} type="number" step="0.01" className="input" placeholder="0" />
          </F>
          <F label="Modalités de stockage" col="md:col-span-2">
            <textarea {...register('modalites_stockage')} className="input" rows={2} placeholder="Fûts métalliques, aire étanche..." />
          </F>
        </div>

        {/* Section B */}
        <SectionTitle>B — Modes de traitement</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <F label="Modalités de gestion" col="">
            <textarea {...register('modalites_gestion')} className="input" rows={2} />
          </F>
          <F label="Modalités de contrôle" col="">
            <textarea {...register('modalites_controle')} className="input" rows={2} />
          </F>
          <F label="Modalités d'élimination" col="">
            <textarea {...register('modalites_elimination')} className="input" rows={2} />
          </F>
          <F label="Types d'installation de traitement" col="">
            <input {...register('types_installation')} className="input" />
          </F>
          <F label="Types de traitement" col="">
            <input {...register('types_traitement')} className="input" />
          </F>
          <F label="Quantités traitées (t/an)" col="">
            <input {...register('quantites_traitees')} type="number" step="0.01" className="input" placeholder="0" />
          </F>
          <F label="Rendement du traitement" col="">
            <input {...register('rendement_traitement')} className="input" placeholder="99%" />
          </F>
        </div>

        {/* Section C */}
        <SectionTitle>C — Mesures pour éviter la production de déchets spéciaux dangereux</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <F label="Réutilisation (t/an)" col=""><input {...register('reutilisation_qte')} type="number" step="0.01" className="input" /></F>
          <F label="Recyclage (t/an)" col=""><input {...register('recyclage_qte')} type="number" step="0.01" className="input" /></F>
          <F label="Valorisation (t/an)" col=""><input {...register('valorisation_qte')} type="number" step="0.01" className="input" /></F>
          <F label="Élimination (t/an)" col=""><input {...register('elimination_qte')} type="number" step="0.01" className="input" /></F>
        </div>

        {[
          ['1 — Techniques de minimisation',         'mesures_min_prises',      'mesures_min_envisager'],
          ['2 — Bonnes pratiques environnementales', 'mesures_bpe_prises',      'mesures_bpe_envisager'],
          ['3 — Techniques disponibles',             'mesures_tech_prises',     'mesures_tech_envisager'],
          ['4 — Production plus propre',             'mesures_pp_prises',       'mesures_pp_envisager'],
          ['5 — Gestion préventive des risques',     'mesures_risques_prises',  'mesures_risques_envisager'],
        ].map(([title, pKey, eKey]) => (
          <div key={title} className="card p-3 space-y-2">
            <p className="text-xs font-bold text-slate-600">{title}</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label text-xs">Mesures prises</label>
                <textarea {...register(pKey)} className="input text-xs" rows={2} />
              </div>
              <div>
                <label className="label text-xs">Mesures à envisager</label>
                <textarea {...register(eKey)} className="input text-xs" rows={2} />
              </div>
            </div>
          </div>
        ))}

        {/* Submit */}
        <div className="flex gap-3 pt-3 border-t border-[#E2E8F0] sticky bottom-0 bg-white dark:bg-[#16240D] py-3">
          <button type="submit" disabled={generating || previewing} className="btn-primary">
            {generating
              ? <span className="flex items-center gap-2"><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"/>Génération...</span>
              : <span className="flex items-center gap-2"><Download size={15}/>Télécharger le PDF</span>
            }
          </button>
          <button type="button" disabled={generating || previewing}
            onClick={handleSubmit(onPreview)}
            className="btn-secondary flex items-center gap-2">
            {previewing
              ? <><span className="w-4 h-4 border-2 border-slate-400/30 border-t-slate-500 rounded-full animate-spin"/>Chargement...</>
              : <><Eye size={15}/>Aperçu PDF</>
            }
          </button>
          <button type="button" onClick={onClose} className="btn-secondary ml-auto">Annuler</button>
        </div>
      </form>
    </div>
  )
}
