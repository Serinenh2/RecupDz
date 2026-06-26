"""
Pré-remplit les désignations précises de déchets (4ème niveau de la cascade
Traçabilité) — 131 désignations réparties sur les 8 codes d'emballage
(15.01.01 à 15.01.08), importées depuis le fichier Excel fourni par le client
(nomenclature_dechets_emballage.xlsx). Français uniquement, comme demandé.

Usage: python manage.py seed_designations
Idempotent — relancer ne crée pas de doublons (get_or_create sur id_recup_dz).
"""
from django.core.management.base import BaseCommand
from apps.nomenclature.models import Nomenclature, DesignationDechet

# (id_recup_dz, code_nomenclature, designation, matiere)
DATA = [
    ('PLA-001', '15.01.02', 'Bouteille d\'eau PET', 'PET'),
    ('PLA-002', '15.01.02', 'Préforme PET', 'PET'),
    ('PLA-003', '15.01.02', 'Flacon PET', 'PET'),
    ('PLA-004', '15.01.02', 'Bidon PEHD', 'PEHD'),
    ('PLA-005', '15.01.02', 'Flacon PEHD', 'PEHD'),
    ('PLA-006', '15.01.02', 'Jerrican PEHD', 'PEHD'),
    ('PLA-007', '15.01.02', 'Film étirable PEBD', 'PEBD'),
    ('PLA-008', '15.01.02', 'Housse plastique', 'PEBD'),
    ('PLA-009', '15.01.02', 'Sac plastique', 'PEBD'),
    ('PLA-010', '15.01.02', 'Big Bag PP', 'PP'),
    ('PLA-021', '15.01.02', 'Bouchon PET', 'PET'),
    ('PLA-022', '15.01.02', 'Barquette PET', 'PET'),
    ('PLA-023', '15.01.02', 'Bouteille huile PET', 'PET'),
    ('PLA-024', '15.01.02', 'Fût PEHD', 'PEHD'),
    ('PLA-025', '15.01.02', 'Seau PEHD', 'PEHD'),
    ('PLA-026', '15.01.02', 'Caisse plastique PEHD', 'PEHD'),
    ('PLA-027', '15.01.02', 'Film rétractable PEBD', 'PEBD'),
    ('PLA-028', '15.01.02', 'Sachet PEBD', 'PEBD'),
    ('PLA-029', '15.01.02', 'Film agricole PEBD', 'PEBD'),
    ('PLA-030', '15.01.02', 'Sac tissé PP', 'PP'),
    ('PLA-031', '15.01.02', 'Sac non tissé PP', 'PP'),
    ('PLA-032', '15.01.02', 'Boîte alimentaire PP', 'PP'),
    ('PLA-033', '15.01.02', 'Pot de yaourt PP', 'PP'),
    ('PLA-034', '15.01.02', 'Capsule PP', 'PP'),
    ('PLA-035', '15.01.02', 'Film multicouche', 'Multicouche'),
    ('PLA-036', '15.01.02', 'Emballage souple multicouche', 'Multicouche'),
    ('PLA-037', '15.01.02', 'Blister PVC', 'PVC'),
    ('PLA-038', '15.01.02', 'Flacon PVC', 'PVC'),
    ('PLA-039', '15.01.02', 'Boîtier PS', 'PS'),
    ('PLA-040', '15.01.02', 'Barquette PS', 'PS'),
    ('PLA-041', '15.01.02', 'Mousse PSE d\'emballage', 'PSE'),
    ('PLA-042', '15.01.02', 'Calage en polystyrène', 'PSE'),
    ('PLA-043', '15.01.02', 'Tube cosmétique PE', 'PE'),
    ('PLA-044', '15.01.02', 'Recharge détergent souple', 'PE'),
    ('PLA-045', '15.01.02', 'Filet d\'emballage plastique', 'PE'),
    ('PLA-046', '15.01.02', 'Bouteille PET eau gazeuse', 'pet'),
    ('PLA-047', '15.01.02', 'Bouteille PET jus de fruits', 'pet'),
    ('PLA-048', '15.01.02', 'Bouteille PEHD détergent', 'pehd'),
    ('PLA-049', '15.01.02', 'Film plastique d\'emballage', 'pebd'),
    ('BOIS-001', '15.01.03', 'Palette Europe', 'BOIS'),
    ('BOIS-002', '15.01.03', 'Palette perdue', 'BOIS'),
    ('BOIS-003', '15.01.03', 'Palette CP', 'BOIS'),
    ('BOIS-004', '15.01.03', 'Palette bois cassée', 'BOIS'),
    ('BOIS-005', '15.01.03', 'Caisse en bois', 'BOIS'),
    ('BOIS-006', '15.01.03', 'Caisse-palette', 'BOIS'),
    ('BOIS-007', '15.01.03', 'Cagette en bois', 'BOIS'),
    ('BOIS-008', '15.01.03', 'Touret en bois', 'BOIS'),
    ('BOIS-009', '15.01.03', 'Touret de câble', 'BOIS'),
    ('BOIS-010', '15.01.03', 'Bois de calage', 'BOIS'),
    ('BOIS-011', '15.01.03', 'Coins de calage', 'BOIS'),
    ('BOIS-012', '15.01.03', 'Chevrons d’emballage', 'BOIS'),
    ('BOIS-013', '15.01.03', 'Planches de protection', 'BOIS'),
    ('BOIS-014', '15.01.03', 'Cadre d’emballage bois', 'BOIS'),
    ('BOIS-015', '15.01.03', 'Caisse d’exportation', 'BOIS'),
    ('BOIS-016', '15.01.03', 'Coffre d’emballage', 'BOIS'),
    ('BOIS-017', '15.01.03', 'Berceau en bois', 'BOIS'),
    ('BOIS-018', '15.01.03', 'Séparateur en bois', 'BOIS'),
    ('BOIS-019', '15.01.03', 'Conteneur bois', 'BOIS'),
    ('BOIS-020', '15.01.03', 'Caisse ajourée', 'BOIS'),
    ('BOIS-021', '15.01.03', 'Palette traitée HT', 'BOIS'),
    ('BOIS-022', '15.01.03', 'Palette consignée', 'BOIS'),
    ('BOIS-023', '15.01.03', 'Palette industrielle', 'BOIS'),
    ('BOIS-024', '15.01.03', 'Palette légère', 'BOIS'),
    ('BOIS-025', '15.01.03', 'Palette lourde', 'BOIS'),
    ('MET-001', '15.01.04', 'Fût acier 200 L', 'Acier'),
    ('MET-002', '15.01.04', 'Fût acier galvanisé', 'Acier galvanisé'),
    ('MET-003', '15.01.04', 'Fût inox', 'Inox'),
    ('MET-004', '15.01.04', 'Bidon métallique', 'Acier'),
    ('MET-005', '15.01.04', 'Canette aluminium', 'Aluminium'),
    ('MET-006', '15.01.04', 'Boîte de conserve', 'Fer blanc'),
    ('MET-007', '15.01.04', 'Aérosol vide', 'Acier'),
    ('MET-008', '15.01.04', 'Couvercle métallique', 'Acier'),
    ('MET-009', '15.01.04', 'Capsule métallique', 'Acier'),
    ('MET-010', '15.01.04', 'Seau métallique', 'Acier'),
    ('MET-011', '15.01.04', 'Boîte de peinture vide', 'Acier'),
    ('MET-012', '15.01.04', 'Tambour métallique', 'Acier'),
    ('MET-013', '15.01.04', 'Container métallique', 'Acier'),
    ('MET-014', '15.01.04', 'Cerclage métallique', 'Acier'),
    ('MET-015', '15.01.04', 'Boîte aluminium', 'Aluminium'),
    ('MET-016', '15.01.04', 'Tube aluminium', 'Aluminium'),
    ('MET-017', '15.01.04', 'Opercule aluminium', 'Aluminium'),
    ('MET-018', '15.01.04', 'Barquette aluminium', 'Aluminium'),
    ('MET-019', '15.01.04', 'Capsule de bouteille', 'Acier'),
    ('MET-020', '15.01.04', 'Bidon métallique 5 L', 'Acier'),
    ('COM-001', '15.01.05', 'Carton de lait multicouche', 'Carton/Plastique/Aluminium'),
    ('COM-002', '15.01.05', 'Brique de jus alimentaire', 'Carton/Plastique/Aluminium'),
    ('COM-003', '15.01.05', 'Emballage Tetra Pak', 'Carton/PE/Aluminium'),
    ('COM-004', '15.01.05', 'Sachet alimentaire multicouche', 'Plastique multicouches'),
    ('COM-005', '15.01.05', 'Sachet café aluminisé', 'Plastique/Aluminium'),
    ('COM-006', '15.01.05', 'Emballage de chips', 'Plastique/Aluminium'),
    ('COM-007', '15.01.05', 'Blister médicament', 'Plastique/Aluminium'),
    ('COM-008', '15.01.05', 'Tube dentifrice', 'Plastique/Aluminium'),
    ('VER-001', '15.01.07', 'Bouteilles en verre', 'verre'),
    ('VER-002', '15.01.07', 'Flacons en verre', 'verre'),
    ('VER-003', '15.01.07', 'Pots en verre', 'verre'),
    ('VER-004', '15.01.07', 'Bocaux en verre', 'verre'),
    ('VER-005', '15.01.07', 'Verre d\'emballage cassé', 'verre'),
    ('VER-006', '15.01.07', 'Bouteilles en verre coloré', 'Verre vert, brun ou autre'),
    ('VER-007', '15.01.07', 'Bouteilles en verre transparent', 'Verre blanc ou incolore'),
    ('VER-008', '15.01.07', 'Bouteille en verre boisson', 'verre'),
    ('TEX-001', '15.01.08', 'Sacs en tissu', 'TEXTILE'),
    ('TEX-002', '15.01.08', 'Sacs en jute', 'TEXTILE'),
    ('TEX-003', '15.01.08', 'Sacs tissés en fibres synthétiques', 'TEXTILE'),
    ('TEX-004', '15.01.08', 'Housses textiles d\'emballage', 'TEXTILE'),
    ('TEX-005', '15.01.08', 'Filets textiles d\'emballage', 'TEXTILE'),
    ('TEX-006', '15.01.08', 'Big-bag textile en polypropylène', 'TEXTILE'),
    ('PAP-001', '15.01.01', 'Carton ondulé', 'Carton'),
    ('PAP-002', '15.01.01', 'Carton plat', 'Carton'),
    ('PAP-003', '15.01.01', 'Boîte en carton', 'Carton'),
    ('PAP-004', '15.01.01', 'Caisse en carton', 'Carton'),
    ('PAP-005', '15.01.01', 'Papier kraft', 'Papier'),
    ('PAP-006', '15.01.01', 'Sac en papier', 'Papier'),
    ('PAP-007', '15.01.01', 'Sachet en papier', 'Papier'),
    ('PAP-008', '15.01.01', 'Mandrin en carton', 'Carton'),
    ('PAP-009', '15.01.01', 'Séparateur en carton', 'Carton'),
    ('PAP-010', '15.01.01', 'Plateau en carton', 'Carton'),
    ('MEL-001', '15.01.06', 'Emballage papier/plastique', 'Papier/Plastique'),
    ('MEL-002', '15.01.06', 'Emballage carton/plastique', 'Carton/Plastique'),
    ('MEL-003', '15.01.06', 'Emballage papier/aluminium', 'Papier/Aluminium'),
    ('MEL-004', '15.01.06', 'Emballage carton/aluminium', 'Carton/Aluminium'),
    ('MEL-005', '15.01.06', 'Gobelet multicouche', 'Papier/Plastique'),
    ('MEL-006', '15.01.06', 'Sachet multicouche', 'Mélange de matériaux'),
    ('MEL-007', '15.01.06', 'Emballage complexe non séparable', 'Mélange de matériaux'),
    ('MEL-008', '15.01.06', 'Étiquette composite', 'Papier/Plastique'),
    ('PAP-011', '15.01.01', 'Cartons dechets', 'CARTON'),
    ('PAP-013', '15.01.01', 'Mandrin rebut', 'CARTON'),
    ('PAP-014', '15.01.01', 'Ceinture carton rebut', 'CARTON'),
    ('PLA-011', '15.01.02', 'Sachets usagees', 'PLASTIQUE'),
    ('BOIS-025', '15.01.03', 'Palette bois rebut', 'BOIS'),
    ('PLA-012', '15.01.02', 'Palatte de PEHD', 'PEHD'),
]


class Command(BaseCommand):
    help = "Importe les désignations précises de déchets d'emballage (depuis Excel client)"

    def handle(self, *args, **options):
        created = skipped = missing_code = 0

        for id_recup, code, designation, matiere in DATA:
            nomenclature = Nomenclature.objects.filter(code=code).first()
            if not nomenclature:
                missing_code += 1
                self.stdout.write(self.style.WARNING(
                    f"  ⚠️  Code {code} introuvable en nomenclature — '{designation}' ignoré."
                ))
                continue

            obj, was_created = DesignationDechet.objects.get_or_create(
                id_recup_dz=id_recup,
                defaults={
                    'nomenclature': nomenclature,
                    'designation': designation,
                    'matiere': matiere,
                }
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ {created} désignation(s) créée(s), {skipped} déjà existante(s)"
            + (f", {missing_code} ignorée(s) (code nomenclature manquant)" if missing_code else "")
        ))
        if missing_code:
            self.stdout.write(self.style.WARNING(
                "⚠️  Des codes nomenclature sont manquants — vérifiez que setup.py "
                "contient bien les codes 15.01.01 à 15.01.08 et relancez `python setup.py`."
            ))
