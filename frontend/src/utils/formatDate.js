/**
 * formatDateFR — affichage JJ/MM/AAAA
 * Convertit une date ISO (YYYY-MM-DD, éventuellement avec heure) reçue de l'API
 * en format JJ/MM/AAAA. Valeurs vides ou déjà dans un autre format : inchangées.
 */
export function formatDateFR(value) {
  if (!value) return ''
  const datePart = String(value).split('T')[0]
  const parts = datePart.split('-')
  if (parts.length !== 3) return value
  const [y, m, d] = parts
  if (y.length !== 4 || isNaN(y) || isNaN(m) || isNaN(d)) return value
  return `${d}/${m}/${y}`
}
