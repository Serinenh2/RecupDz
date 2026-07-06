from apps.ai_assistant.models import KnowledgeBase

KNOWLEDGE_BASE_DATA = [
    {
        'categorie': 'loi',
        'titre': 'Loi n°01-19 du 12 décembre 2001 relative à la gestion, au contrôle et à l\'élimination des déchets',
        'contenu': '''La Loi n°01-19 constitue le cadre législatif principal de la gestion des déchets en Algérie.

PRINCIPES FONDAMENTAUX:
- Principe de prévention et de réduction à la source
- Principe de responsabilité du producteur
- Principe pollueur-payeur
- Principe de proximité du traitement
- Principe de traçabilité

OBLIGATIONS:
- Tout producteur de déchets doit en assurer la gestion conformément à la réglementation
- La collecte, le transport, le traitement et l'élimination des déchets sont soumis à autorisation
- Les exploitants de décharges contrôlées doivent détenir un agrément
- Les récupérateurs doivent être agréés selon la catégorie de déchets traités

SECTIONS CONCERNÉES:
- Titre I: Dispositions générales
- Titre II: Gestion des déchets ménagers et assimilés
- Titre III: Gestion des déchets spéciaux
- Titre IV: Gestion des déchets dangereux
- Titre V: Infractions et sanctions
- Titre VI: Dispositions transitoires et finales''',
        'reference_reglementaire': 'Loi n°01-19 du 12 décembre 2001, J.O. n°78',
        'tags': ['loi', 'gestion', 'dechets', 'producteur', 'responsabilite', 'elimination'],
    },
    {
        'categorie': 'decret',
        'titre': 'Décret exécutif n°06-104 fixant la nomenclature des déchets',
        'contenu': '''Le Décret exécutif n°06-104 établit la nomenclature nationale des déchets conforme à la règlementation européenne.

CATEGORIES DE DECHETS:
- Déchets Ménagers et Assimilés (MA): collecte et traitement par les APC
- Déchets Inertes (I): matériaux de construction, témoins
- Déchets Spéciaux (S): huiles usagées, pneus, DEEE, métaux
- Déchets Spéciaux Dangereux (SD): solvants, acides, bases, déchets hospitaliers

CLASSIFICATION PAR CODE:
Chaque déchet reçoit un code à 6 chiffres selon:
- Les 2 premiers chiffres: chapitre (20=ménagers, 17=construction, 13=huiles, 16=équipements)
- Les 2 chiffres du milieu: sous-chapitre
- Les 2 derniers chiffres: code spécifique

OBLIGATIONS:
- BSD obligatoire pour les déchets spéciaux (S)
- BSD obligatoire pour les déchets spéciaux dangereux (SD)
- Traçabilité obligatoire via BSD électronique
- Tenue d'un registre des déchets pour les producteurs''',
        'reference_reglementaire': 'Décret exécutif n°06-104 du 11 février 2006',
        'tags': ['decret', 'nomenclature', 'codes', 'classification', 'categorie', 'MA', 'I', 'S', 'SD'],
    },
    {
        'categorie': 'decret',
        'titre': 'Décret exécutif n°05-315 fixant les modalités de déclaration des déchets spéciaux dangereux',
        'contenu': '''Le Décret exécutif n°05-315 détermine les modalités de surveillance et de déclaration des déchets spéciaux dangereux (DSD).

OBLIGATIONS DE DECLARATION:
- Les producteurs de DSD doivent déclarer mensuellement/trimestriellement
- La déclaration doit mentionner: nature, quantité, destination, traitement
- Les récupérateurs et valorisateurs doivent déclarer leurs activités

FORMULAIRE DE DECLARATION:
- Quantité produite par type de déchet
- Quantité traitée par filière
- Quantité éliminée
- Quantité entreposée
- Coordonnées du prestataire

SANCTIONS:
- Défaut de déclaration: amende
- Fausse déclaration: sanctions pénales
- Délai de déclaration: 15 jours après la fin du trimestre''',
        'reference_reglementaire': 'Décret exécutif n°05-315 du 1er octobre 2005',
        'tags': ['decret', 'declaration', 'DSD', 'dangereux', 'surveillance', 'trimestriel'],
    },
    {
        'categorie': 'referentiel',
        'titre': 'Référentiel national des codes déchets Algérie',
        'contenu': '''Le référentiel national classe les déchets selon leur origine et leur dangerosité.

CHAPITRE 20 - DÉCHETS MÉNAGERS ET ASSIMILÉS:
- 20.01: Fractions collectées séparément (papier, verre, métal, plastique, textile)
- 20.02: Déchets de parcs et jardins
- 20.03: Autres déchets municipaux

CHAPITRE 17 - DÉCHETS DE CONSTRUCTION:
- 17.01: Béton, briques, tuiles
- 17.02: Bois, verre, matières plastiques
- 17.04: Métaux (cuivre, aluminium, fer)

CHAPITRE 16 - DÉCHETS D'ÉQUIPEMENTS:
- 16.01: Véhicules hors d'usage
- 16.02: Déchets d'équipements électriques et électroniques (DEEE)
- 16.06: Piles et accumulateurs

CHAPITRE 13 - HUILES ET LIQUIDES:
- 13.01: Huiles hydrauliques
- 13.02: Huiles moteur et lubrifiantes
- 13.03: Isolants PCB/PCT

CHAPITRE 07 - SOLVANTS ET PRODUITS CHIMIQUES:
- 07.01: Eaux de nettoyage, solvants
- 07.02: Eaux de lavage
- 07.03: Boues aqueuses

CHAPITRE 14 - SUBSTANCES OZONODEPLETRICES:
- 14.06: CFC, HCFC, HFC

CHAPITRE 19 - DÉCHETS D'INSTALLATIONS:
- 19.08: Résidus de traitement des eaux
- 19.09: Boues de traitement

CHAPITRE 18 - DÉCHETS HOSPITALIERS:
- 18.01: Déchets de soins médicaux''',
        'reference_reglementaire': 'Décret exécutif n°06-104 - Référentiel National',
        'tags': ['referentiel', 'codes', 'chapitres', 'classification', 'nomenclature'],
    },
    {
        'categorie': 'procedure',
        'titre': 'Procédure de demande d\'agrément pour récupérateurs',
        'contenu': '''La procédure d'obtention d'agrément pour exercer en tant que récupérateur de déchets en Algérie.

ETAPES DE LA DEMANDE:
1. Constitution du dossier administratif
2. Dépôt auprès de l'autorité compétente (Wilaya ou Ministère selon catégorie)
3. Instruction du dossier
4. Visite de contrôle des installations
5. Délivrance ou refus de l'agrément

DOSSIER REQUIS:
- Formulaire de demande dûment rempli
- Extrait de rôle (RC, NIF, NIS pour les personnes morales)
- Plan de situation des installations
- Description du processus de traitement
- Liste des déchets concernés
- Certificats de formation du personnel
- Étude d'impact environnemental (selon catégorie)

CATEGORIES ET AUTORITES:
- CAT1 (MA/I): Déclaration simple auprès de l'APC
- CAT2 (S): Agrément Wilaya - DPE
- CAT3 (SD): Agrément Ministère de l'Environnement
- CAT4 (Carte Pro): Carte professionnelle de l'administration

DUREE DE VALIDITE:
- Agrément Wilaya: 3 ans renouvelable
- Agrément Ministère: 5 ans renouvelable
- Carte professionnelle: 1 an renouvelable

RENOUVELLEMENT:
- Dossier de renouvellement à déposer 3 mois avant expiration
- Maintien des conditions d'agrément requises
- Rapport d'activité annuel''',
        'reference_reglementaire': 'Procédure administrative - Loi 01-19',
        'tags': ['agrement', 'procedure', 'demande', 'dossier', 'renouvellement', 'categorie'],
    },
    {
        'categorie': 'procedure',
        'titre': 'Procédure d\'émission et de suivi des BSD',
        'contenu': '''Procédure réglementaire pour l'émission, le transport et la réception des Bordereaux de Suivi des Déchets.

EMISSION DU BSD:
- Remplissage par le producteur (générateur)
- Signature du producteur obligatoire
- Identification du récupérateur/transporteur agréé
- Description précise du déchet: code, quantité, conditionnement
- Date prévue d'enlèvement

TRANSPORT:
- Le transporteur signe le BSD
- Le BSD accompagne obligatoirement le chargement
- En cas de refus par le receveur: consignation immédiate

RECEPTION:
- Le récepteur (valorisateur/éliminateur) signe dans les 5 jours
- Conservation du BSD original pendant 3 ans
- Transmission d'une copie au producteur

CAS PARTICULIERS:
- Déchets hospitaliers (SD): protocole spécial
- DSD (Déchets Spéciaux Dangereux): BSD obligatoire
- Transit: visa de transit obligatoire

SIGNATURES REQUISES:
1. Signature du générateur (producteur)
2. Signature du transporteur
3. Signature du récepteur (valorisateur/éliminateur)

NUMEROTATION:
- Numéro unique par BSD
- Série annuelle
- Mention de la wilaya d'émission''',
        'reference_reglementaire': 'Loi 01-19 - Articles 27 à 35',
        'tags': ['BSD', 'bordereau', 'suivi', 'transport', 'signature', 'emission', 'reception'],
    },
    {
        'categorie': 'referentiel',
        'titre': 'Liste des agréments et catégories de récupérateurs',
        'contenu': '''Référentiel des agréments pour les récupérateurs de déchets en Algérie.

CATÉGORIE 1: DÉCHETS NON DANGEREUX (MA/I)
- Collecte: Ménagers et assimilés, inertes
- Valorisation: Tri, conditionnement
- Pas d'agrément nécessaire
- Déclaration à l'APC

CATÉGORIE 2: DÉCHETS SPÉCIAUX (S)
- Types: Huiles usagées, pneus, DEEE, ferraille, batteries
- Agrément: DPE de la Wilaya
- Validité: 3 ans
- Renouvellement: Dépôt dossier 3 mois avant expiration

CATÉGORIE 3: DÉCHETS SPÉCIAUX DANGEREUX (SD)
- Types: Solvants, acides, bases, déchets hospitaliers, PCB
- Agrément: Ministère de l'Environnement
- Validité: 5 ans
- Étude d'impact environnementale obligatoire

CATÉGORIE 4: CARTE PROFESSIONNELLE
- Transporteurs de déchets
- Carte annuelle délivrée par l'administration
- Condition: Formation professionnelle

CRITÈRES D'ÉLIGIBILITÉ:
- Capacité technique et financière
- Personnel qualifié
- Installations conformes
- Plan de gestion des déchets
- Assurance responsabilité civile''',
        'reference_reglementaire': 'Référentiel National des Déchets - Loi 01-19',
        'tags': ['agrement', 'categorie', 'CAT1', 'CAT2', 'CAT3', 'CAT4', 'recuperateur', 'vocation'],
    },
    {
        'categorie': 'glossaire',
        'titre': 'Glossaire bilingue des termes de gestion des déchets',
        'contenu': '''Glossaire des termes techniques en français et arabe relatifs à la gestion des déchets.

TERMES PRINCIPAUX:
- Déchet: نفاية (Nafaya) - Toute substance ou objet dont le détenteur se défait
- Producteur: مولنفايات (Moulinifayat) - Toute personne dont l'activité produit des déchets
- Récupérateur: قابل للنفايات (Qabil lil-Nafayat) - Personne traitant les déchets pour récupération
- Valorisateur: معالج (Moualij) - Exploitant traitant les déchets pour valorisation
- Éliminateur: مكثف (Moukathef) - Exploitant traitant les déchets par élimination
- Transporteur: ناقل (Naqil) - Personne assurant le transport des déchets
- Agrément: رخصة (Rakhsa) - Autorisation administrative d'exercer
- BSD: سجل متابعة النفايات (Sijil Mutaba'at an-Nafayat) - Bordereau de suivi des déchets
- CET: مركز طمر (Markaz Tamr) - Centre d'enfouissement technique
- Décharge: مطرح (Mtarh) - Lieu d'élimination des déchets
- Dangerosité: خطورة (Khatoura) - Risque pour l'environnement ou la santé
- Traçabilité: تتبع (Tatbîq) - Capacité de suivre le déchet depuis sa production jusqu'à son élimination

CATÉGORIES:
- MA: ménagers et assimilés ( ménagers et assimilés)
- I: inertes (خامل)
- S: spéciaux (خاص)
- SD: spéciaux dangereux (خاص خطر)''',
        'reference_reglementaire': 'Glossaire technique - RECUP-DZ',
        'langue': 'fr',
        'tags': ['glossaire', 'terminologie', 'francais', 'arabe', 'bilingue'],
    },
    {
        'categorie': 'glossaire',
        'titre': 'Glossaire arabe des termes de gestion des déchets',
        'contenu': '''المصطلحات المتعلقة بإدارة النفايات في الجزائر

المصطلحات الرئيسية:
- النفايات: Déchets (Nafayat) - المواد أو الأشياء التي يتخلص منها حاملها
- المولد: Producteur (Moulinif) - كل شخص أنتج نفايات من نشاطه
- المعالج: Récupérateur/Valorisateur (Moualij) - شخص يعالج النفايات
- الناقل: Transporteur (Naqil) - الشخص الذي ينقل النفايات
- الرخصة: Agrément (Rakhsa) - إذن إداري لممارسة النشاط
- سجل المتابعة: BSD (Sijil al-Mutaba'a) - وثيقة متابعة النفايات
- مركز الطمر Technique: CET (Markaz at-Tamr at-Tiqni) - موقع دفن النفايات
- الخطورة: Dangerosité (Khatoura) - خطر على البيئة أو الصحة
- التتبع: Traçabilité (Tatbîq) - إمكانية تتبع النفايات

التصنيفات:
- نفايات منزلية: MA (Ménagers et assimilés) - نفايات منزلية ومشابهة
- نفايات خاملة: I (Inertes) - مواد بناء خاملة
- نفايات خاصة: S (Spéciaux) - نفايات تحتاج معاملة خاصة
- نفايات خاصة خطرة: SD (Spéciaux Dangereux) - نفايات خاصة تشكل خطرا''',
        'reference_reglementaire': 'Glossaire technique - RECUP-DZ',
        'langue': 'ar',
        'tags': ['glossaire', 'terminologie', 'arabe', 'francais', 'bilingue'],
    },
    {
        'categorie': 'faq',
        'titre': 'FAQ - Questions fréquentes sur la réglementation des déchets en Algérie',
        'contenu': '''Réponses aux questions fréquemment posées sur la gestion des déchets en Algérie.

Q: Quels déchets sont concernés par la Loi 01-19 ?
R: Tous les déchets produits en Algérie, qu'ils soient ménagers, industriels, hospitaliers, ou agricoles.

Q: Qu'est-ce qu'un BSD et quand est-il obligatoire ?
R: Le BSD (Bordereau de Suivi des Déchets) est obligatoire pour:
- Tous les déchets spéciaux (S): huiles usagées, pneus, DEEE
- Tous les déchets spéciaux dangereux (SD): solvants, acides, déchets hospitaliers
- Tous les déchets en transit

Q: Quelle est la différence entre CAT2 et CAT3 ?
R: 
- CAT2: Déchets Spéciaux (S) non dangereux - Agrément Wilaya
- CAT3: Déchets Spéciaux Dangereux (SD) - Agrément Ministère

Q: Comment obtenir un agrément de récupérateur ?
R: Dépôt du dossier complet auprès de la DPE de la wilaya (CAT2) ou du Ministère de l'Environnement (CAT3).

Q: Que faire si mon agrément expire bientôt ?
R: Déposer une demande de renouvellement 3 mois avant la date d'expiration avec le rapport d'activité annuel.

Q: Qui peut émettre un BSD ?
R: Seul le producteur (générateur) de déchets peut émettre un BSD.

Q: Quelles sont les sanctions en cas de non-conformité ?
R: Amendes administratives, fermeture administrative, poursuites pénales selon la gravité.

Q: Comment déclarer mes déchets trimestriellement ?
R: Via le module Déclarations de la plateforme RECUP-DZ dans les 15 jours suivant la fin du trimestre.''',
        'reference_reglementaire': 'FAQ - Loi 01-19',
        'tags': ['FAQ', 'questions', 'reponses', 'frequentes'],
    },
    {
        'categorie': 'guide',
        'titre': 'Guide de conformité réglementaire pour les récupérateurs',
        'contenu': '''Guide pour garantir la conformité réglementaire des activités de récupération de déchets en Algérie.

DOCUMENTS OBLIGATOIRES:
- Agrément en cours de validité
- Assurance responsabilité civile
- Registre des entrées/sorties de déchets
- BSD pour chaque opération de déchets spéciaux
- Déclarations trimestrielles

VERIFICATIONS MENSUELLES:
- Validité des agréments
- BSD émis et reçus
- Stocks entreposés conformément à la réglementation
- Personnel formé et habilité

ALERTES A SURVEILLER:
- Expiration d'agrément dans moins de 30 jours
- BSD en retard de signature
- Dépassement des quantités autorisées
- Déchets stockés au-delà des durées autorisées
- Documents manquants dans les dossiers

BONNES PRATIQUES:
- Tenue à jour du registre des déchets
- Archivage des BSD pendant 3 ans minimum
- Formation continue du personnel
- Contrôle régulier des installations
- Notification des incidents à l'administration

CONTACTS UTILES:
- DPE de la wilaya: pour agréments locaux
- Ministère de l'Environnement: pour agréments nationaux
- Inspection des installations: contrôles''',
        'reference_reglementaire': 'Guide pratique - Loi 01-19',
        'tags': ['guide', 'conformite', 'bonnes pratiques', 'verification'],
    },
    {
        'categorie': 'guide',
        'titre': 'Guide de remplissage du BSD électronique',
        'contenu': '''Guide étape par étape pour remplir le Bordereau de Suivi des Déchets électronique.

PARTIE 1 - IDENTIFICATION DU PRODUCTEUR:
- Raison sociale et adresse du générateur
- NIF, NIS, RC
- Activité exercée
- Responsable du site

PARTIE 2 - IDENTIFICATION DU RECUPÉRATEUR:
- Nom et agrément du récupérateur
- Adresse de l'installation de traitement
- Numéro d'agrément

PARTIE 3 - CARACTÉRISATION DU DÉCHET:
- Code nomenclature (6 chiffres)
- Désignation du déchet
- Quantité en kg ou tonnes
- Nature du conditionnement
- Classe (MA/I/S/SD)

PARTIE 4 - TRANSPORT:
- Nom et agrément du transporteur
- Immatriculation du véhicule
- Date de ramassage
- Cachet et signature du chauffeur

PARTIE 5 - RÉCEPTION:
- Date de réception
- Quantité reçue
- Signature du récepteur
- Observations éventuelles

VALIDATION:
- Signature du producteur obligatoire avant transport
- Signature du récepteur dans les 5 jours
- Archivage électronique automatique''',
        'reference_reglementaire': 'Guide BSD électronique - RECUP-DZ',
        'tags': ['BSD', 'guide', 'remplissage', 'electronique', 'etapes'],
    },
    {
        'categorie': 'procedure',
        'titre': 'Procédure de gestion des déchets hospitaliers',
        'contenu': '''Procédure spécifique pour la gestion des déchets hospitaliers et des déchets infectieux.

CLASSIFICATION:
- Déchets infectieux: seringues, compames, pansements souillés
- Déchets anatomiques: pièces anatomiques, organes
- Déchets pharmaceutiques: médicaments périmés
- Déchets chimiques et cytotoxiques

OBLIGATIONS DES ÉTABLISSEMENTS:
- Tri immédiat à la source
- Emballage spécifique (jaune, rouge selon catégorie)
- Étiquetage avec date et nature du déchet
- Traçabilité complète via BSD

TRAITEMENT:
- Stérilisation pour les déchets infectieux
- Incinération pour déchets anatomiques et cytotoxiques
- Élimination en CET dédié pour déchets non traités

FOURNISSEURS AGRÉÉS:
- Récupérateurs CAT3 pour DSD hospitaliers uniquement
- Transporteurs avec agrément transport DSD
- Installations d'élimination autorisées

DECLARATIONS:
- Mensuelles à la DPE de la wilaya
- Mention des quantités par catégorie
- Copie BSD au fournisseur et à l'administration''',
        'reference_reglementaire': 'Décret 05-315 - Déchets Hospitaliers',
        'tags': ['hospitalier', 'infectieux', 'sterilisation', 'incineration', 'DSD', 'DASRI'],
    },
    {
        'categorie': 'procedure',
        'titre': 'Procédure de déclaration trimestrielle des déchets',
        'contenu': '''Procédure pour la déclaration trimestrielle des déchets spéciaux et spéciaux dangereux.

DECLARATION TRIMESTRIELLE (Décret 05-315):
- Délai: 15 jours après la fin de chaque trimestre
- Périodes: Janvier-Mars, Avril-Juin, Juillet-Septembre, Octobre-Décembre

CONTENU DE LA DECLARATION:
a) Déchets produits:
   - Code et nature du déchet
   - Quantité produite (kg/tonnes)
   - Déchets stockés en fin de période
   - Déchets éliminés/valorises

b) Traitement réalisé:
   - Quantité traitée par filière
   - Nom et agrément du prestataire
   - Quantité réintroduite dans le circuit économique

c) Déchets en stocks:
   - Quantité stockée par type
   - Durée de stockage
   - Mesures de sécurité mises en place

DEPOT:
- Par voie électronique via plateforme RECUP-DZ
- Copie papier à la DPE de la wilaya
- Accusé de réception obligatoire

SANCTIONS:
- Défaut de déclaration: amende 50 000 à 500 000 DA
- Fausse déclaration: sanctions pénales''',
        'reference_reglementaire': 'Décret exécutif n°05-315 du 1er octobre 2005',
        'tags': ['declaration', 'trimestrielle', 'DSD', 'quantite', 'stock'],
    },
    {
        'categorie': 'referentiel',
        'titre': 'Types de conditionnement des déchets',
        'contenu': '''Types de conditionnement utilisés pour le stockage et le transport des déchets en Algérie.

CONDITIONNEMENTS STANDARDS:
- En vrac: Déchets non conditionnés, chargés directement (gravier, sable, débris de béton)
- Sac: Sacs en plastique ou en papier pour déchets légers (plastiques, papiers)
- Big Bag: Grands sacs flexibles (1 m³) pour déchets en vrac légers
- Carton: Cartons pour déchets légers et secs (papiers, cartons)
- Fût: Fûts métalliques ou plastiques pour liquides et boues (huiles, solvants)
- Bidon: Bidons plastiques pour liquides (huiles usagées, eaux contaminées)
- Palette: Palettes pour le transport de fûts et cartons empilés
- Conteneur: Conteneurs métalliques pour grands volumes (DEEE, ferraille)

CONDITIONNEMENTS PAR TYPE DE DÉCHET:
- Huiles usagées: Fûts ou bidons
- Plastiques: Sac ou Big Bag
- Métaux: Conteneur ou palette
- Papier/carton: Carton ou sac
- Verre: Sac ou conteneur
- Textiles: Sac
- Batteries: Palette ou conteneur
- Pneus: En vrac ou conteneur

NORMES DE CONDITIONNEMENT:
- Les déchets dangereux (SD) doivent être conditionnés dans des emballages homologués
- Étiquetage obligatoire avec code nomenclature et pictogramme de danger
- Fermeture hermétique pour les déchets toxiques ou inflammables
- Non mélange des déchets compatibles''',
        'reference_reglementaire': 'Guide pratique - RECUP-DZ',
        'tags': ['conditionnement', 'emballage', 'transport', 'stockage', 'sac', 'fut', 'bidon', 'palette', 'conteneur'],
    },
    {
        'categorie': 'referentiel',
        'titre': 'Référentiel des codes déchets courants',
        'contenu': '''Référentiel des codes déchets les plus couramment rencontrés en Algérie.

DECHETS MÉNAGERS ET ASSIMILÉS (MA):
- 20.01.01: Papier et carton (ورق وكرتون)
- 20.01.02: Verre (زجاج)
- 20.01.08: Déchets de cuisine biodégradables (نفايات المطبخ)
- 20.01.10: Vêtements (ملابس)
- 20.01.11: Textiles (نسيج)
- 20.01.36: Équipements électriques et électroniques mis au rebut
- 20.02.01: Déchets biodégradables (نفايات قابلة للتحلل)
- 20.03.01: Déchets municipaux en mélange (نفايات بلدية مختلطة)

DECHETS INERTES (I):
- 17.01.01: Béton (خرسانة)
- 17.01.02: Briques (طوب)
- 17.01.07: Mélanges de béton, briques, tuiles
- 17.02.01: Bois (خشب)
- 17.02.02: Verre inerte (زجاج خامل)
- 17.02.03: Matières plastiques (مواد بلاستيكية)
- 17.04.01: Cuivre, bronze, laiton (نحاس وبرونز)
- 17.04.02: Aluminium (ألمنيوم)
- 17.04.05: Fer et acier (حديد وفولاذ)
- 17.04.07: Métaux en mélange (معادن مختلطة)

DECHETS SPÉCIAUX (S):
- 13.01.01: Huiles hydrauliques chlorées
- 13.02.01: Huiles moteur, de boîte de vitesses et de lubrification usagées
- 16.01.03: Pneus hors d'usage (إطارات خارج الخدمة)
- 16.06.01: Batteries au plomb (بطاريات الرصاص)
- 16.06.02: Batteries Ni-Cd (بطاريات نيكل كادميوم)

DECHETS SPÉCIAUX DANGEREUX (SD):
- 13.01.09: Huiles hydrauliques minérales chlorées
- 13.03.01: Huiles isolantes contenant des PCB
- 07.01.01: Eaux de nettoyage et lessives aqueuses
- 07.01.03: Solvants halogénés organiques
- 07.01.04: Autres solvants organiques
- 08.01.11: Déchets de peintures contenant des solvants organiques
- 14.06.01: Chlorofluorocarbures (CFC, HCFC, HFC)
- 16.05.04: Produits chimiques dangereux (dont périmés)
- 18.01.03: Déchets infectieux des hôpitaux (نفايات طبية معدية)
- 19.08.07: Solutions et boues provenant de la régénération''',
        'reference_reglementaire': 'Décret exécutif n°06-104 - Nomenclature',
        'langue': 'fr',
        'tags': ['referentiel', 'codes', 'courants', 'frequents', 'recherche'],
    },
]


def importer_connaissances():
    creees = 0
    mises_a_jour = 0
    for item in KNOWLEDGE_BASE_DATA:
        obj, created = KnowledgeBase.objects.get_or_create(
            reference_reglementaire=item['reference_reglementaire'],
            titre=item['titre'],
            defaults={
                'categorie': item['categorie'],
                'contenu': item['contenu'],
                'langue': item.get('langue', 'fr'),
                'tags': item.get('tags', []),
                'est_active': True,
            },
        )
        if created:
            creees += 1
        else:
            if not obj.est_active:
                obj.est_active = True
                obj.save()
                mises_a_jour += 1
    return {'creees': creees, 'mises_a_jour': mises_a_jour}
