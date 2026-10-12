// Nomenclature interne de l'entreprise — catalogue des désignations utilisées
// sur les factures/BL (Référence + Conditionnement), distinct de la nomenclature
// réglementaire du Décret 06-104 (voir nomenclatureData.js, toujours utilisée
// pour les codes déchets S/SD des BSD/DSD).
//
// code_dechet / classe : rattachement à un code du Décret 06-104 (onglet "Codes
// déchets"), pour retrouver directement le code officiel à utiliser dans les
// BSD/DSD/traçabilité pour chaque article. Format zero-paddé (15.01.02) pour
// matcher les codes du backend (apps.nomenclature.Nomenclature) — à ne pas
// confondre avec le format court (15.1.2) affiché par nomenclatureData.js.
export const NOMENCLATURE_ENTREPRISE = [
  { designation: 'Palette de PEHD',      reference: 'COMPALPEHD',    conditionnement: 'Kilogramme', code_dechet: '15.01.02', classe: 'MA' },
  { designation: 'Palette Bois Rebut',   reference: 'PALETTE_REB',   conditionnement: 'Unité',      code_dechet: '15.01.03', classe: 'MA' },
  { designation: 'Cartons déchets',      reference: 'REBUTS_CARTONS',conditionnement: 'Kilogramme', code_dechet: '15.01.01', classe: 'MA' },
  { designation: 'Les Saches Usagées',   reference: 'SACHE-USE',     conditionnement: 'Kilogramme', code_dechet: '15.01.02', classe: 'MA' },
  { designation: 'Rebuts Matière PET',   reference: 'REB_MAT_PET',   conditionnement: 'Kilogramme', code_dechet: '15.01.02', classe: 'MA' },
  { designation: 'Ceinture carton Rebut',reference: 'CEINCAR_REB',   conditionnement: 'Kilogramme', code_dechet: '15.01.01', classe: 'MA' },
  { designation: 'BigBag',               reference: 'COMBIGBAG',     conditionnement: 'Unité',      code_dechet: '15.01.02', classe: 'MA' },
  { designation: 'Mandrins Rebut',       reference: 'MANDRINS_REB',  conditionnement: 'Unité',      code_dechet: '15.01.01', classe: 'MA' },
]
