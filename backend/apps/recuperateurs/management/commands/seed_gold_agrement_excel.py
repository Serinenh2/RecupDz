"""
Importe la structure officielle de l'agrément SARL Gold Environment Service
(Nomenclature_Agrement_Gold_Environment.xlsx — Décret 06-104) :

1. Importe les 140 codes de nomenclature (classe S/SD) dans la table Nomenclature.
2. Crée une catégorie de spécialisation dédiée "Déchets spéciaux et spéciaux
   dangereux — Agrément Gold Environment" contenant les 38 sections officielles
   du document, chacune devenant une SousCategorieSpecialisation avec un
   DetailSpecialisation lié à tous ses codes précis.
3. Assigne CETTE structure UNIQUEMENT au récupérateur SARL Gold Environment
   (compte admin_gold) — aucun autre récupérateur n'y a accès par défaut.
   Pour donner cette même structure à un autre récupérateur, allez dans
   Django Admin > Récupérateurs > [récupérateur] > champ Spécialisation et
   cochez les détails souhaités (chaque détail correspond à une section).

Usage: python manage.py seed_gold_agrement_excel
Idempotent — relancer ne crée pas de doublons.
"""
from django.core.management.base import BaseCommand
from apps.nomenclature.models import Nomenclature
from apps.recuperateurs.models import Recuperateur
from apps.recuperateurs.models_specialisation import (
    CategorieSpecialisation, SousCategorieSpecialisation, DetailSpecialisation,
)

# ── 140 codes (code, famille, designation_fr, classe, danger_fr) ──────────────
NOMENCLATURE_DATA = [
    ('01.04.01', '01', 'Boues et autres déchets de forage contenant des hydrocarbures', 'SD', 'Inflammable, Toxique'),
    ('01.01.02', '01', 'Boues provenant du lavage et du nettoyage', 'S', ''),
    ('04.01.02', '04', 'Déchets provenant de la sylviculture', 'S', ''),
    ('05.01.02', '05', 'Produits agrochimiques contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('06.01.02', '06', 'Produits agrochimiques autres que ceux visés à la rubrique 5.1.2', 'S', ''),
    ('01.02.02', '01', 'Boues provenant du lavage et du nettoyage', 'S', ''),
    ('03.02.02', '03', 'Matières impropres à la consommation ou à la transformation', 'S', ''),
    ('04.02.02', '04', 'Boues provenant du traitement in situ des effluents', 'S', ''),
    ('01.03.02', '01', 'Boues provenant du lavage, du nettoyage, de l\'épluchage, de la centrifugation et de la séparation', 'S', ''),
    ('02.03.02', '02', 'Déchets provenant des agents de conservation', 'S', ''),
    ('03.03.02', '03', 'Déchets provenant de l\'extraction par solvants', 'S', ''),
    ('05.03.02', '05', 'Boues provenant du traitement in situ des effluents', 'S', ''),
    ('01.04.02', '01', 'Carbonate de calcium déclassé', 'S', ''),
    ('04.02', '04', 'Boues provenant du traitement in situ des effluents', 'S', ''),
    ('05.02', '05', 'Boues provenant du traitement in situ des effluents', 'S', ''),
    ('01.06.02', '01', 'Matières impropres à la consommation ou à la transformation', 'S', ''),
    ('02.06.02', '02', 'Matières impropres à la consommation ou à la transformation', 'S', ''),
    ('03.06.02', '03', 'Boues provenant du traitement in situ des effluents', 'S', ''),
    ('03.07.02', '03', 'Boues provenant du traitement in situ des effluents', 'S', ''),
    ('01.02.03', '01', 'Composés organiques non halogénés de protection du bois', 'SD', 'Comburante, Inflammable'),
    ('05.02.03', '05', 'Autres produits de protection du bois contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('02.03.03', '02', 'Boues de désencrage provenant du recyclage du papier', 'S', ''),
    ('03.03.03', '03', 'Déchets de boues résiduaires', 'S', ''),
    ('04.03.03', '04', 'Déchets de fibres et boues de fibres provenant de la séparation mécanique', 'S', ''),
    ('07.01.04', '07', 'Boues provenant du traitement in situ des effluents, ne contenant pas de chrome', 'S', ''),
    ('01.01.05', '01', 'Boues de dessalage', 'SD', 'Irritante'),
    ('02.01.05', '02', 'Boues de fond de cuves', 'SD', 'Dangereuse pour l\'environnement'),
    ('03.01.05', '03', 'Boues d\'alkyles acides', 'SD', 'Facilement inflammable, Toxique, Corrosive'),
    ('04.01.05', '04', 'Hydrocarbures accidentellement répandus', 'SD', 'Toxique, Cancérogène, Mutagène, Dangereuse pour l\'environnement'),
    ('05.01.05', '05', 'Boues contenant des hydrocarbures provenant des opérations de maintenance des installations ou des équipements', 'SD', 'Inflammable, Nocive'),
    ('06.01.05', '06', 'Goudrons acides', 'SD', 'Facilement inflammable, Toxique, Cancérogène, Mutagène'),
    ('08.01.05', '08', 'Boues provenant du traitement in situ des effluents contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement, Nocive'),
    ('10.01.05', '10', 'Déchets provenant du nettoyage des hydrocarbures par les bases', 'SD', 'Nocive'),
    ('11.01.05', '11', 'Hydrocarbures contenant des acides', 'SD', 'Toxique, Cancérogène, Mutagène, Dangereuse pour l\'environnement'),
    ('12.01.05', '12', 'Boues provenant du traitement de l\'eau d\'alimentation des chaudières', 'S', ''),
    ('13.01.05', '13', 'Déchets provenant des colonnes de refroidissement', 'S', ''),
    ('14.01.05', '14', 'Argiles de filtration usagées', 'SD', 'Toxique'),
    ('16.01.05', '16', 'Mélange de résidus', 'S', ''),
    ('01.01.06', '01', 'Acide sulfurique et acide sulfureux', 'SD', 'Comburante, Inflammable, Toxique, Corrosive, Irritante'),
    ('02.01.06', '02', 'Acide chlorhydrique', 'SD', 'Inflammable, Toxique, Corrosive, Irritante'),
    ('03.01.06', '03', 'Acide fluorhydrique', 'SD', 'Inflammable, Toxique, Corrosive, Irritante'),
    ('01.02.06', '01', 'Hydroxyde de calcium', 'SD', 'Nocive'),
    ('02.02.06', '02', 'Hydroxyde d\'ammonium', 'SD', 'Nocive, Comburante'),
    ('01.05.06', '01', 'Boues provenant du traitement in situ des effluents contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('01.12.06', '01', 'Produits phytosanitaires inorganiques, agents de protection du bois et autres biocides', 'SD', 'Toxique, Dangereuse pour l\'environnement'),
    ('02.12.06', '02', 'Charbon actif usagé (sauf rubrique 2.7.6)', 'SD', 'Inflammable, Toxique, Irritante'),
    ('03.12.06', '03', 'Noir de carbone', 'S', ''),
    ('01.04.07', '01', 'Résidus de réaction et résidus de distillation halogénés', 'SD', 'Toxique'),
    ('02.04.07', '02', 'Résidus de réaction et résidus de distillation halogénés', 'SD', 'Toxique'),
    ('03.04.07', '03', 'Résidus de réaction et résidus de distillation halogénés', 'SD', 'Toxique'),
    ('04.04.07', '04', 'Résidus de réaction et résidus de distillation halogénés', 'SD', 'Toxique'),
    ('10.04.07', '10', 'Déchets solides contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('04.05.07', '04', 'Résidus de réaction et résidus de distillation halogénés', 'SD', 'Toxique'),
    ('08.05.07', '08', 'Boues provenant du traitement in situ des effluents contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('04.06.07', '04', 'Résidus de réaction et résidus de distillation halogénés', 'SD', 'Toxique'),
    ('05.06.07', '05', 'Autres résidus de réaction et de distillation', 'SD', 'Toxique'),
    ('08.06.07', '08', 'Boues provenant du traitement in situ des effluents contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('04.07.07', '04', 'Résidus de réaction et résidus de distillation halogénés', 'SD', 'Toxique'),
    ('08.07.07', '08', 'Boues provenant du traitement in situ des effluents contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('01.08', '01', 'Peintures et vernis autres que ceux visés à la rubrique 1.1.8', 'S', ''),
    ('02.01.08', '02', 'Déchets provenant du décapage des peintures ou des vernis autres que ceux visés à la rubrique 7.1.8', 'S', ''),
    ('08.01.08', '08', 'Boues aqueuses contenant de la peinture ou du vernis autres que ceux visés à la rubrique 9.1.8', 'S', ''),
    ('02.02.08', '02', 'Boues aqueuses contenant des substances dangereuses', 'S', ''),
    ('02.01.10', '02', 'Cendres volantes de charbon', 'S', ''),
    ('03.01.10', '03', 'Cendres volantes de tourbe et de bois non traité', 'S', ''),
    ('04.01.10', '04', 'Cendres volantes et cendres sous chaudière d\'hydrocarbures', 'SD', 'Irritante, Toxique'),
    ('05.01.10', '05', 'Déchets solides provenant des réactions basées sur le calcium pour la désulfuration des fumées', 'S', ''),
    ('06.01.10', '06', 'Boues des réactions basées sur le calcium pour la désulfuration des fumées', 'S', ''),
    ('08.01.10', '08', 'Cendres volantes provenant des hydrocarbures émulsifiés et utilisés comme combustibles', 'SD', 'Toxique'),
    ('11.01.10', '11', 'Cendres volantes issues de la co-incinération, contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('15.01.10', '15', 'Boues provenant du traitement in situ des effluents contenant des substances dangereuses', 'SD', 'Toxique'),
    ('17.01.10', '17', 'Boues aqueuses provenant du nettoyage des chaudières contenant des substances dangereuses', 'SD', 'Toxique'),
    ('21.01.10', '21', 'Déchets provenant du traitement des eaux de refroidissement', 'S', ''),
    ('06.09.10', '06', 'Poussières de filtration des fumées contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement, Toxique'),
    ('10.09.10', '10', 'Déchets de revêtement contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('06.10.10', '06', 'Poussières de filtration des fumées contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement, Toxique'),
    ('04.08.10', '04', 'Scories et crasses inflammables ou dégageant lors du contact avec l\'eau des gaz inflammables en quantités dangereuses', 'SD', 'Toxique'),
    ('06.08.10', '06', 'Déchets goudronneux provenant de la fabrication des anodes', 'SD', 'Nocive'),
    ('09.08.10', '09', 'Poussières de filtration des fumées contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('11.08.10', '11', 'Boues et gâteaux de filtration provenant de l\'épuration des fumées contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('13.08.10', '13', 'Déchets provenant du traitement des eaux de refroidissement contenant des hydrocarbures', 'SD', 'Inflammable, Nocive'),
    ('02.02.10', '02', 'Laitier non traité', 'S', ''),
    ('03.02.10', '03', 'Déchets solides provenant de l\'épuration des fumées contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('04.01.11', '04', 'Boues de phosphatation', 'SD', 'Nocive'),
    ('05.01.11', '05', 'Boues et gâteaux de filtration contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('09.01.11', '09', 'Déchets de dégraissage contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('08.01.12', '08', 'Émulsions et solutions d\'usinage sans halogènes', 'SD', 'Nocive'),
    ('10.01.12', '10', 'Déchets de cires et graisses', 'SD', 'Nocive'),
    ('11.01.12', '11', 'Déchets de brasage', 'S', ''),
    ('12.01.12', '12', 'Boues d\'usinage contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('16.01.12', '16', 'Boues métalliques (provenant du meulage et de l\'affûtage) contenant des hydrocarbures', 'SD', 'Inflammable, Nocive'),
    ('01.04.13', '01', 'Boues de fond de cuve provenant de la navigation fluviale', 'SD', 'Inflammable, Irritante'),
    ('02.04.13', '02', 'Boues de fond de cuve provenant des canaux des quais de port', 'SD', 'Inflammable, Irritante'),
    ('03.04.13', '03', 'Boues de fond de cuve provenant d\'autre type de navigation', 'SD', 'Inflammable, Nocive'),
    ('02.05.13', '02', 'Boues provenant des séparateurs eau/hydrocarbures', 'SD', 'Nocive'),
    ('03.05.13', '03', 'Boues provenant des déshuileurs', 'SD', 'Nocive'),
    ('01.14', '01', 'Solvants et mélanges de solvants halogénés autres', 'SD', 'Dangereuse pour l\'environnement'),
    ('02.01.14', '02', 'Solvants et mélanges de solvants halogénés autres', 'SD', 'Dangereuse pour l\'environnement'),
    ('01.01.15', '01', 'Absorbants, matériaux filtrants (y compris les filtres à huile non spécifiés ailleurs), chiffons d\'essuyage et vêtements de protection contaminés', 'SD', 'Inflammable, Irritante, Nocive'),
    ('01.02.15', '01', 'Absorbants, matériaux filtrants, chiffons d\'essuyage et vêtements de protection autres que ceux visés à la rubrique 1.2.15', 'S', ''),
    ('02.02.15', '02', 'Pneumatiques hors d\'usage', 'S', ''),
    ('01.01.16', '01', 'Déchets contenant des hydrocarbures', 'SD', 'Inflammable, Toxique'),
    ('01.03.17', '01', 'Mélanges bitumineux contenant du goudron', 'SD', 'Inflammable, Toxique, Cancérogène, Mutagène'),
    ('03.03.17', '03', 'Goudrons et produits goudronnés', 'SD', 'Inflammable, Toxique, Cancérogène, Mutagène'),
    ('01.05.17', '01', 'Terres et cailloux contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('03.05.17', '03', 'Boues de dragage contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('01.07.17', '01', 'Matériaux de construction à base de gypse contaminés par des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('02.01.19', '02', 'Gâteaux de filtration provenant de l\'épuration des fumées', 'SD', 'Toxique'),
    ('04.01.19', '04', 'Déchets secs provenant de l\'épuration des fumées', 'SD', 'Toxique'),
    ('07.01.19', '07', 'Ferrailles non visées à la rubrique 6.1.19', 'S', ''),
    ('08.01.19', '08', 'Cendres volantes contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('10.01.19', '10', 'Cendres sous chaudière contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('01.08.19', '01', 'Déchets provenant du dégrillage', 'S', ''),
    ('02.08.19', '02', 'Déchets provenant du déssablage', 'S', ''),
    ('03.08.19', '03', 'Boues provenant du traitement des eaux urbaines résiduaires', 'S', ''),
    ('10.08.19', '10', 'Boues provenant du traitement biologique des effluents industriels autres que celles visées à la rubrique 9.8.19', 'S', ''),
    ('12.08.19', '12', 'Boues provenant d\'autres traitements des effluents industriels autres que celles visées à la rubrique 9.8', 'S', ''),
    ('01.09.19', '01', 'Déchets solides provenant de la filtration primaire et du dégrillage', 'S', ''),
    ('02.09.19', '02', 'Boues provenant de la clarification de l\'eau', 'S', ''),
    ('03.09.19', '03', 'Boues provenant de la décarbonatation', 'S', ''),
    ('05.09.19', '05', 'Résines échangeuses d\'ions saturées ou usées', 'S', ''),
    ('06.09.19', '06', 'Solutions et boues provenant de la régénération des échangeurs d\'ions', 'S', ''),
    ('01.11.19', '01', 'Argiles de filtration usagées', 'SD', 'Facilement inflammable, Toxique, Cancérogène, Mutagène'),
    ('02.11.19', '02', 'Goudrons acides', 'SD', 'Facilement inflammable, Toxique, Cancérogène, Mutagène'),
    ('04.11.19', '04', 'Déchets provenant du nettoyage des hydrocarbures par les bases', 'SD', 'Toxique'),
    ('05.11.19', '05', 'Boues provenant du traitement in situ des effluents contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('07.11.19', '07', 'Déchets provenant de l\'épuration des gaz de combustion', 'S', ''),
    ('01.13.19', '01', 'Déchets solides provenant de l\'assainissement des sols contenant des substances dangereuses', 'SD', 'Toxique, Dangereuse pour l\'environnement'),
    ('03.13.19', '03', 'Boues provenant de l\'assainissement des sols contenant des substances dangereuses', 'SD', 'Dangereuse pour l\'environnement'),
    ('05.13.19', '05', 'Boues provenant de l\'assainissement des eaux souterraines contenant des substances dangereuses', 'SD', 'Toxique, Dangereuse pour l\'environnement'),
    ('01.01.20', '01', 'Solvants', 'SD', 'Inflammable, Irritante'),
    ('02.01.20', '02', 'Acides', 'SD', 'Inflammable, Irritante, Toxique'),
    ('03.01.20', '03', 'Déchets des bases', 'SD', 'Irritante, Toxique'),
    ('05.01.20', '05', 'Pesticides (produits périmés non phosphatés et non chlorés)', 'SD', 'Toxique, Dangereuse pour l\'environnement'),
    ('10.01.20', '10', 'Peintures, encres, colles et résines contenant des substances dangereuses', 'SD', 'Inflammable, Toxique'),
    ('11.01.20', '11', 'Peintures, encres, colles et résines autres que celles visées à la rubrique 10.1.20', 'S', ''),
    ('12.01.20', '12', 'Détergents contenant des substances dangereuses', 'SD', 'Inflammable, Irritante, Dangereuse pour l\'environnement'),
    ('22.01.20', '22', 'Déchets provenant du nettoyage des conduits de cheminée', 'S', ''),
    ('01.03.20', '01', 'Boues de fossés d\'évacuation des eaux', 'S', ''),
    ('02.03.20', '02', 'Déchets provenant du nettoyage des canalisations d\'évacuation des eaux', 'S', ''),
]

# ── 38 sections officielles, chacune avec ses codes liés ──────────────────────
SECTIONS_DATA = [
    {
        'titre': '4.1  –  Boues de forage et déchets de forage autres',
        'ordre': 0,
        'codes': [
            '01.04.01',
        ],
    },
    {
        'titre': '1.2  –  Déchets provenant de l\'agriculture, de l\'horticulture, de l\'aquaculture, de la sylviculture, de la chasse et de la pêche',
        'ordre': 1,
        'codes': [
            '01.01.02',
            '04.01.02',
            '05.01.02',
            '06.01.02',
        ],
    },
    {
        'titre': '2.2  –  Déchets provenant de la préparation et de la transformation de la viande, des poissons et autres aliments d\'origine animale',
        'ordre': 2,
        'codes': [
            '01.02.02',
            '03.02.02',
            '04.02.02',
            '01.03.02',
            '02.03.02',
            '03.03.02',
            '05.03.02',
            '01.04.02',
            '04.02',
            '05.02',
        ],
    },
    {
        'titre': '6.2  –  Déchets des boulangeries, des pâtisseries et de la confiserie',
        'ordre': 3,
        'codes': [
            '01.06.02',
            '02.06.02',
            '03.06.02',
            '03.07.02',
        ],
    },
    {
        'titre': '1.3  –  Déchets provenant de la transformation du bois et de la fabrication de panneaux et de meubles',
        'ordre': 4,
        'codes': [
        ],
    },
    {
        'titre': '2.3  –  Déchets provenant de la fabrication de produits de protection du bois',
        'ordre': 5,
        'codes': [
            '01.02.03',
            '05.02.03',
        ],
    },
    {
        'titre': '3.3  –  Déchets provenant de la production et de la transformation de pâte à papier, de papier et de carton',
        'ordre': 6,
        'codes': [
            '02.03.03',
            '03.03.03',
            '04.03.03',
        ],
    },
    {
        'titre': '1.4  –  Déchets provenant de l\'industrie du cuir et des fourrures',
        'ordre': 7,
        'codes': [
            '07.01.04',
        ],
    },
    {
        'titre': '1.5  –  Déchets provenant du raffinage du pétrole',
        'ordre': 8,
        'codes': [
            '01.01.05',
            '02.01.05',
            '03.01.05',
            '04.01.05',
            '05.01.05',
            '06.01.05',
            '08.01.05',
            '10.01.05',
            '11.01.05',
            '12.01.05',
            '13.01.05',
            '14.01.05',
            '16.01.05',
        ],
    },
    {
        'titre': '1.6  –  Déchets provenant des procédés chimiques inorganiques',
        'ordre': 9,
        'codes': [
            '01.01.06',
            '02.01.06',
            '03.01.06',
            '01.02.06',
            '02.02.06',
        ],
    },
    {
        'titre': '5.6  –  Boues provenant du traitement in situ des effluents',
        'ordre': 10,
        'codes': [
            '01.05.06',
            '01.12.06',
            '02.12.06',
            '03.12.06',
        ],
    },
    {
        'titre': '4.7  –  Résidus de réaction et résidus de distillation halogénés',
        'ordre': 11,
        'codes': [
            '01.04.07',
            '02.04.07',
            '03.04.07',
            '04.04.07',
            '10.04.07',
        ],
    },
    {
        'titre': '5.7  –  Déchets provenant de la fabrication de produits pharmaceutiques',
        'ordre': 12,
        'codes': [
            '04.05.07',
            '08.05.07',
        ],
    },
    {
        'titre': '6.7  –  Déchets provenant de la fabrication de corps gras, de savons, de détergents, de désinfectants et de cosmétiques',
        'ordre': 13,
        'codes': [
            '04.06.07',
            '05.06.07',
            '08.06.07',
        ],
    },
    {
        'titre': '7.7  –  Déchets de la chimie fine et des produits chimiques non spécifiés ailleurs',
        'ordre': 14,
        'codes': [
            '04.07.07',
            '08.07.07',
            '01.08',
            '02.01.08',
            '08.01.08',
        ],
    },
    {
        'titre': '2.8  –  Déchets provenant de la fabrication de revêtements (matériaux céramiques compris)',
        'ordre': 15,
        'codes': [
            '02.02.08',
        ],
    },
    {
        'titre': '1.10  –  Déchets provenant des centrales électriques et autres installations de combustion (sauf chapitre 19)',
        'ordre': 16,
        'codes': [
            '02.01.10',
            '03.01.10',
            '04.01.10',
            '05.01.10',
            '06.01.10',
            '08.01.10',
            '11.01.10',
            '15.01.10',
            '17.01.10',
            '21.01.10',
        ],
    },
    {
        'titre': '9.10  –  Déchets de la fonderie de métaux ferreux',
        'ordre': 17,
        'codes': [
            '06.09.10',
            '10.09.10',
        ],
    },
    {
        'titre': '10.10  –  Déchets de la fonderie de métaux non ferreux',
        'ordre': 18,
        'codes': [
            '06.10.10',
        ],
    },
    {
        'titre': '8.10  –  Déchets provenant de la fabrication d\'autres métaux sous haute température',
        'ordre': 19,
        'codes': [
            '04.08.10',
            '06.08.10',
            '09.08.10',
            '11.08.10',
            '13.08.10',
        ],
    },
    {
        'titre': '1.2.10  –  Déchets provenant des hauts fourneaux et des aciéries',
        'ordre': 20,
        'codes': [
            '02.02.10',
            '03.02.10',
        ],
    },
    {
        'titre': '1.11  –  Déchets provenant du traitement chimique de surface et du revêtement des métaux et autres matériaux (procédés de zingage, de décapage, de phosphatation, de dégraissage alcalin et d\'anodisation)',
        'ordre': 21,
        'codes': [
            '04.01.11',
            '05.01.11',
            '09.01.11',
        ],
    },
    {
        'titre': '1.12  –  Déchets provenant du façonnage et du traitement physique et mécanique de surface des métaux et matières plastiques',
        'ordre': 22,
        'codes': [
            '08.01.12',
            '10.01.12',
            '11.01.12',
            '12.01.12',
            '16.01.12',
        ],
    },
    {
        'titre': '4.13  –  Boues et déchets de fond de cuve',
        'ordre': 23,
        'codes': [
            '01.04.13',
            '02.04.13',
            '03.04.13',
            '02.05.13',
            '03.05.13',
            '01.14',
            '02.01.14',
        ],
    },
    {
        'titre': '1.15  –  Emballages et déchets d\'emballages contenant des substances dangereuses',
        'ordre': 24,
        'codes': [
            '01.01.15',
            '01.02.15',
            '02.02.15',
            '01.01.16',
        ],
    },
    {
        'titre': '1.7.16  –  Déchets provenant du nettoyage des cuves et des fûts de stockage et de transport (sauf chapitres 5 et 13)',
        'ordre': 25,
        'codes': [
        ],
    },
    {
        'titre': '3.17  –  Mélanges bitumineux, goudrons et produits goudronnés',
        'ordre': 26,
        'codes': [
            '01.03.17',
            '03.03.17',
        ],
    },
    {
        'titre': '5.17  –  Terres (y compris déblais provenant de sites contaminés), cailloux et boues de dragage',
        'ordre': 27,
        'codes': [
            '01.05.17',
            '03.05.17',
        ],
    },
    {
        'titre': '7.17  –  Matériaux de construction à base de gypse',
        'ordre': 28,
        'codes': [
            '01.07.17',
        ],
    },
    {
        'titre': '1.19  –  Déchets provenant de l\'incinération ou de la pyrolyse des déchets',
        'ordre': 29,
        'codes': [
            '02.01.19',
            '04.01.19',
            '07.01.19',
            '08.01.19',
            '10.01.19',
        ],
    },
    {
        'titre': '8.19  –  Déchets provenant des installations de traitement des eaux usées non spécifiés ailleurs',
        'ordre': 30,
        'codes': [
            '01.08.19',
            '02.08.19',
            '03.08.19',
            '10.08.19',
            '12.08.19',
        ],
    },
    {
        'titre': '9.19  –  Déchets provenant de la préparation d\'eau potable et d\'eau à usage industriel',
        'ordre': 31,
        'codes': [
            '01.09.19',
            '02.09.19',
            '03.09.19',
            '05.09.19',
            '06.09.19',
        ],
    },
    {
        'titre': '11.19  –  Déchets provenant de la régénération de l\'huile',
        'ordre': 32,
        'codes': [
            '01.11.19',
            '02.11.19',
            '04.11.19',
            '05.11.19',
            '07.11.19',
        ],
    },
    {
        'titre': '13.19  –  Déchets provenant de l\'assainissement des sols et des eaux souterraines',
        'ordre': 33,
        'codes': [
            '01.13.19',
            '03.13.19',
            '05.13.19',
        ],
    },
    {
        'titre': '1.20  –  Fractions collectées séparément (sauf section 15.1)',
        'ordre': 34,
        'codes': [
            '01.01.20',
            '02.01.20',
            '03.01.20',
            '05.01.20',
            '10.01.20',
            '11.01.20',
            '12.01.20',
            '22.01.20',
        ],
    },
    {
        'titre': '3.20  –  Autres déchets municipaux',
        'ordre': 35,
        'codes': [
            '01.03.20',
            '02.03.20',
        ],
    },
    {
        'titre': 'Légende :',
        'ordre': 36,
        'codes': [
        ],
    },
    {
        'titre': 'SD = Déchets Spéciaux Dangereux',
        'ordre': 37,
        'codes': [
        ],
    },
]

CATEGORIE_NOM = "Déchets spéciaux et spéciaux dangereux — Agrément Gold Environment"


class Command(BaseCommand):
    help = "Importe la structure d'agrément SARL Gold Environment depuis l'Excel officiel"

    def handle(self, *args, **options):
        # ── 1. Codes nomenclature ────────────────────────────────────────────
        created_codes = skipped_codes = 0
        code_objs = {}
        for code, famille, designation_fr, classe, danger_fr in NOMENCLATURE_DATA:
            obj, created = Nomenclature.objects.get_or_create(
                code=code,
                defaults={
                    'famille': famille,
                    'designation_fr': designation_fr,
                    'classe': classe,
                    'designation_ar': '',
                    'bsd_obligatoire': classe in ('S', 'SD'),
                    'agrement_requis': classe in ('S', 'SD'),
                }
            )
            code_objs[code] = obj
            if created:
                created_codes += 1
            else:
                skipped_codes += 1
        self.stdout.write(self.style.SUCCESS(
            f"✅ Nomenclature : {created_codes} code(s) créé(s), {skipped_codes} déjà existant(s)"
        ))

        # ── 2. Catégorie + 38 sections (sous-catégories) + détails liés ──────
        categorie, _ = CategorieSpecialisation.objects.get_or_create(
            nom=CATEGORIE_NOM,
            defaults={'icone': '⚠️', 'ordre': 100},
        )

        all_details = []
        for sec in SECTIONS_DATA:
            sous_cat, _ = SousCategorieSpecialisation.objects.get_or_create(
                categorie=categorie, nom=sec['titre'],
                defaults={'ordre': sec['ordre']},
            )
            # Un détail unique par section, nommé comme la section, classe = SD
            # par défaut (les codes liés ont chacun leur propre classe réelle,
            # affichée dans le frontend ; ce champ sert juste au filtre type MA/SD).
            detail, _ = DetailSpecialisation.objects.get_or_create(
                sous_categorie=sous_cat, nom=sec['titre'][:200],
                defaults={'ordre': 0, 'classe_nomenclature': 'SD'},
            )
            codes_for_detail = [code_objs[c] for c in sec['codes'] if c in code_objs]
            detail.codes_nomenclature.set(codes_for_detail)
            all_details.append(detail)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Structure créée : {len(SECTIONS_DATA)} section(s) avec leurs codes liés"
        ))

        # ── 3. Assignation EXCLUSIVE au récupérateur Gold ────────────────────
        gold = Recuperateur.objects.filter(
            nom_raison_sociale__icontains='Gold Environment'
        ).first()
        if gold:
            gold.specialisation_details.add(*all_details)
            self.stdout.write(self.style.SUCCESS(
                f"✅ {len(all_details)} section(s) assignée(s) à {gold.nom_raison_sociale} "
                f"— visible uniquement par ce récupérateur."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "⚠️  Récupérateur 'Gold Environment' introuvable — lancez d'abord "
                "`python manage.py seed_gold_demo`, puis relancez cette commande."
            ))
