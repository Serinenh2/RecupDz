// Nomenclature interne de l'entreprise — catalogue des désignations utilisées
// sur les factures/BL (Référence + Conditionnement), distinct de la nomenclature
// réglementaire du Décret 06-104 (voir nomenclatureData.js, toujours utilisée
// pour les codes déchets S/SD des BSD/DSD).
export const NOMENCLATURE_ENTREPRISE = [
  { designation: 'Palette de PEHD',      reference: 'COMPALPEHD',    conditionnement: 'Kilogramme' },
  { designation: 'Palette Bois Rebut',   reference: 'PALETTE_REB',   conditionnement: 'Unité'      },
  { designation: 'Cartons déchets',      reference: 'REBUTS_CARTONS',conditionnement: 'Kilogramme' },
  { designation: 'Les Saches Usagées',   reference: 'SACHE-USE',     conditionnement: 'Kilogramme' },
  { designation: 'Rebuts Matière PET',   reference: 'REB_MAT_PET',   conditionnement: 'Kilogramme' },
  { designation: 'Ceinture carton Rebut',reference: 'CEINCAR_REB',   conditionnement: 'Kilogramme' },
  { designation: 'BigBag',               reference: 'COMBIGBAG',     conditionnement: 'Unité'      },
  { designation: 'Mandrins Rebut',       reference: 'MANDRINS_REB',  conditionnement: 'Unité'      },
]
