"""
Seed la nomenclature complète des déchets — Décret exécutif n°06-104
Référentiel national des déchets (208 codes officiels).
"""
from django.core.management.base import BaseCommand
from apps.nomenclature.models import Nomenclature

NOMENCLATURE_DATA = [
    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 01 — Déchets de prospection et d'exploration minière
    # ═══════════════════════════════════════════════════════════════════
    {"code": "01.01.01", "famille": "01", "sous_famille": "01 01", "designation_fr": "Déchets de prospection et d'exploration minière", "designation_ar": "نفايات المسح والاستكشافات التعدينية", "classe": "I", "annexe": "II", "bsd_obligatoire": False, "agrement_requis": False},
    {"code": "01.03.01", "famille": "01", "sous_famille": "01 03", "designation_fr": "Boues de lavage et d'acidification", "designation_ar": "حمأة الغسيل والتنميل", "classe": "S", "annexe": "II", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "01.04.01", "famille": "01", "sous_famille": "01 04", "designation_fr": "Déchets de lavage et de nettoyage des minerais", "designation_ar": "نفايات غسل وتنظيف الخامات", "classe": "S", "annexe": "II", "bsd_obligatoire": True, "agrement_requis": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 02 — Déchets issus du traitement des eaux
    # ═══════════════════════════════════════════════════════════════════
    {"code": "02.01.01", "famille": "02", "sous_famille": "02 01", "designation_fr": "Boues de dessablage", "designation_ar": "حمأة إزالة الرمال", "classe": "I", "annexe": "II"},
    {"code": "02.01.02", "famille": "02", "sous_famille": "02 01", "designation_fr": "Boues de déshuilage", "designation_ar": "حمأة إزالة الزيوت", "classe": "S", "annexe": "II", "inflammable": True, "dangereuse_environnement": True},
    {"code": "02.02.01", "famille": "02", "sous_famille": "02 02", "designation_fr": "Boues de traitement chimique des eaux industrielles", "designation_ar": "حمأة المعالجة الكيميائية للمياه الصناعية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "02.03.01", "famille": "02", "sous_famille": "02 03", "designation_fr": "Boues de traitement biologique des eaux industrielles", "designation_ar": "حمأة المعالجة البيولوجية للمياه الصناعية", "classe": "S", "annexe": "II", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "02.04.01", "famille": "02", "sous_famille": "02 04", "designation_fr": "Boues de traitement chimique et physique des eaux industrielles", "designation_ar": "حمأة المعالجة الكيميائية والفيزيائية للمياه الصناعية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "corrosive": True, "dangereuse_environnement": True},
    {"code": "02.05.01", "famille": "02", "sous_famille": "02 05", "designation_fr": "Boues de traitement chimique et biologique des eaux industrielles", "designation_ar": "حمأة المعالجة الكيميائية والبيولوجية للمياه الصناعية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "infectieuse": True, "dangereuse_environnement": True},
    {"code": "02.06.01", "famille": "02", "sous_famille": "02 06", "designation_fr": "Boues de traitement physique des eaux industrielles", "designation_ar": "حمأة المعالجة الفيزيائية للمياه الصناعية", "classe": "S", "annexe": "II", "bsd_obligatoire": True, "agrement_requis": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 03 — Déchets de transformations des produits chimiques organiques
    # ═══════════════════════════════════════════════════════════════════
    {"code": "03.01.01", "famille": "03", "sous_famille": "03 01", "designation_fr": "Déchets de fabrication de produits chimiques organiques", "designation_ar": "نفايات تصنيع المنتجات الكيميائية العضوية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "03.02.01", "famille": "03", "sous_famille": "03 02", "designation_fr": "Solvants, liquides de lavage et liqueurs-mères", "designation_ar": "المذيبات، سوائل الغسل والأم لاقط", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "03.03.01", "famille": "03", "sous_famille": "03 03", "designation_fr": "Déchets de distillation de produits chimiques organiques", "designation_ar": "نفايات تقطير المنتجات الكيميائية العضوية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "03.04.01", "famille": "03", "sous_famille": "03 04", "designation_fr": "Déchets de fabrication de colorants et pigments organiques", "designation_ar": "نفايات تصنيع الأصباغ والصبغات العضوية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},
    {"code": "03.05.01", "famille": "03", "sous_famille": "03 05", "designation_fr": "Déchets de fabrication de produits pharmaceutiques", "designation_ar": "نفايات تصنيع المنتجات الصيدلانية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "infectieuse": True},
    {"code": "03.06.01", "famille": "03", "sous_famille": "03 06", "designation_fr": "Déchets de fabrication de pesticides et produits phytosanitaires", "designation_ar": "نفايات تصنيع المبيدات ومنتجات حماية النبات", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},
    {"code": "03.07.01", "famille": "03", "sous_famille": "03 07", "designation_fr": "Déchets de fabrication d'encres et de vernis", "designation_ar": "نفايات تصنيع الأحبار والورنيش", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "03.08.01", "famille": "03", "sous_famille": "03 08", "designation_fr": "Déchets de fabrication de détergents", "designation_ar": "نفايات تصنيع المنظفات", "classe": "S", "annexe": "II", "bsd_obligatoire": True, "agrement_requis": True},
    {"code": "03.09.01", "famille": "03", "sous_famille": "03 09", "designation_fr": "Déchets de fabrication de savons", "designation_ar": "نفايات تصنيع الصابون", "classe": "S", "annexe": "II"},
    {"code": "03.10.01", "famille": "03", "sous_famille": "03 10", "designation_fr": "Déchets de fabrication de cosmétiques", "designation_ar": "نفايات تصنيع مستحضرات التجميل", "classe": "S", "annexe": "II"},
    {"code": "03.11.01", "famille": "03", "sous_famille": "03 11", "designation_fr": "Déchets de fabrication de colles et adhésifs", "designation_ar": "نفايات تصنيع الصمغ واللدانات", "classe": "S", "annexe": "II", "inflammable": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 04 — Déchets de transformations des produits chimiques inorganiques
    # ═══════════════════════════════════════════════════════════════════
    {"code": "04.01.01", "famille": "04", "sous_famille": "04 01", "designation_fr": "Déchets de fabrication de produits chimiques inorganiques (acides)", "designation_ar": "نفايات تصنيع المنتجات الكيميائية اللاعضوية (أحماض)", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "corrosive": True, "toxique": True},
    {"code": "04.02.01", "famille": "04", "sous_famille": "04 02", "designation_fr": "Déchets de fabrication de produits chimiques inorganiques (alcalins)", "designation_ar": "نفايات تصنيع المنتجات الكيميائية اللاعضوية (قواعد)", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "corrosive": True},
    {"code": "04.03.01", "famille": "04", "sous_famille": "04 03", "designation_fr": "Déchets de fabrication de gaz industriels", "designation_ar": "نفايات تصنيع الغازات الصناعية", "classe": "S", "annexe": "II", "inflammable": True},
    {"code": "04.04.01", "famille": "04", "sous_famille": "04 04", "designation_fr": "Déchets de fabrication de pigments et colorants inorganiques", "designation_ar": "نفايات تصنيع الصبغات والصباغات اللاعضوية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "04.05.01", "famille": "04", "sous_famille": "04 05", "designation_fr": "Déchets de traitement de surface et revêtements métalliques", "designation_ar": "نفايات المعالجة السطحية والطلاء المعدني", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "corrosive": True, "dangereuse_environnement": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 05 — Déchets de fabrication de produits minéraux non métalliques
    # ═══════════════════════════════════════════════════════════════════
    {"code": "05.01.01", "famille": "05", "sous_famille": "05 01", "designation_fr": "Déchets de traitement thermique des minéraux non métalliques", "designation_ar": "نفايات المعالجة الحرارية لل minerals Minerals غير المعدنية", "classe": "S", "annexe": "II", "toxique": True},
    {"code": "05.02.01", "famille": "05", "sous_famille": "05 02", "designation_fr": "Déchets de fabrication de ciment, chaux et plâtre", "designation_ar": "نفايات تصنيع الإسمنت والجير والجبس", "classe": "I", "annexe": "II"},
    {"code": "05.03.01", "famille": "05", "sous_famille": "05 03", "designation_fr": "Déchets de fabrication de verre et fibres de verre", "designation_ar": "نفايات تصنيع الزجاج وألياف الزجاج", "classe": "I", "annexe": "II"},
    {"code": "05.04.01", "famille": "05", "sous_famille": "05 04", "designation_fr": "Déchets de fabrication de céramiques", "designation_ar": "نفايات تصنيع السيراميك", "classe": "I", "annexe": "II"},
    {"code": "05.05.01", "famille": "05", "sous_famille": "05 05", "designation_fr": "Déchets de fabrication de matières réfractaires", "designation_ar": "نفايات تصنيع المواد المقاومة للحرارة", "classe": "I", "annexe": "II"},
    {"code": "05.06.01", "famille": "05", "sous_famille": "05 06", "designation_fr": "Déchets de fabrication d'isolants", "designation_ar": "نفايات تصنيع مواد العزل", "classe": "S", "annexe": "II"},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 06 — Déchets de transformations des métaux
    # ═══════════════════════════════════════════════════════════════════
    {"code": "06.01.01", "famille": "06", "sous_famille": "06 01", "designation_fr": "Déchets de forge et de tréfilage", "designation_ar": "نفايات السبك والسحب", "classe": "S", "annexe": "II", "inflammable": True},
    {"code": "06.02.01", "famille": "06", "sous_famille": "06 02", "designation_fr": "Déchets d'usinage et de fraisage des métaux", "designation_ar": "نفايات التوليف والتكسير للمعادن", "classe": "S", "annexe": "II", "inflammable": True},
    {"code": "06.03.01", "famille": "06", "sous_famille": "06 03", "designation_fr": "Déchets de traitement chimique et de finition des métaux", "designation_ar": "نفايات المعالجة الكيميائية والتشطيب للمعادن", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "corrosive": True, "dangereuse_environnement": True},
    {"code": "06.04.01", "famille": "06", "sous_famille": "06 04", "designation_fr": "Déchets de moussage, ébarbage et décapage des métaux", "designation_ar": "نفايات الصب والتشذير وإزالة الأكسدة للمعادن", "classe": "S", "annexe": "II"},
    {"code": "06.05.01", "famille": "06", "sous_famille": "06 05", "designation_fr": "Laitiers de traitement thermique des métaux", "designation_ar": "خثرة المعالجة الحرارية للمعادن", "classe": "I", "annexe": "II"},
    {"code": "06.06.01", "famille": "06", "sous_famille": "06 06", "designation_fr": "Déchets de galvanisation", "designation_ar": "نفايات الطلاء بالزنك", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 07 — Déchets de transformations des huiles minérales et combustibles fossiles
    # ═══════════════════════════════════════════════════════════════════
    {"code": "07.01.01", "famille": "07", "sous_famille": "07 01", "designation_fr": "Eaux de nettoyage et lessives aqueuses", "designation_ar": "مياه الغسل والمنظفات المائية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "07.01.02", "famille": "07", "sous_famille": "07 01", "designation_fr": "Eaux de lavage deservoirs et de conteneurs contenant des hydrocarbures", "designation_ar": "مياه غسل الخزانات والحاويات المحملة بالهيدروكربونات", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True},
    {"code": "07.01.03", "famille": "07", "sous_famille": "07 01", "designation_fr": "Solvants halogénés organiques", "designation_ar": "المذيبات العضوية الهالوجينية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True, "cancerogene": True},
    {"code": "07.01.04", "famille": "07", "sous_famille": "07 01", "designation_fr": "Autres solvants organiques", "designation_ar": "مذيبات عضوية أخرى", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "07.02.01", "famille": "07", "sous_famille": "07 02", "designation_fr": "Lubrifiants huiles moteurs, de boîte de vitesses et de lubrification", "designation_ar": "زيوت المحركات وعلب التروس والتشحيم", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True, "cancerogene": True},
    {"code": "07.03.01", "famille": "07", "sous_famille": "07 03", "designation_fr": "Huiles de découpage, d'usinage et de tournage", "designation_ar": "زيوت القطع والتوليف والخرز", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "07.04.01", "famille": "07", "sous_famille": "07 04", "designation_fr": "Autres huiles moteur, de lubrification et de frein", "designation_ar": "زيوت أخرى للمحركات والتشحيم والفرامل", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "07.05.01", "famille": "07", "sous_famille": "07 05", "designation_fr": "Lies huileux et déchets contenant des huiles", "designation_ar": "طمي زيتي ونفايات تحتوي على الزيوت", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "07.06.01", "famille": "07", "sous_famille": "07 06", "designation_fr": "Déchets d'hydrocarbures", "designation_ar": "نفايات الهيدروكربونات", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "07.07.01", "famille": "07", "sous_famille": "07 07", "designation_fr": "Boues de traitement des huiles usagées", "designation_ar": "حمأة معالجة الزيوت المستعملة", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 08 — Déchets de transformations des matières plastiques
    # ═══════════════════════════════════════════════════════════════════
    {"code": "08.01.01", "famille": "08", "sous_famille": "08 01", "designation_fr": "Déchets de traitement de surface des plastiques", "designation_ar": "نفايات المعالجة السطحية للبلاستيك", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "08.01.02", "famille": "08", "sous_famille": "08 01", "designation_fr": "Solvants et résines de nettoyage des équipements plastiques", "designation_ar": "المذيبات والراتينات لتنظيف معدات البلاستيك", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "toxique": True},
    {"code": "08.01.03", "famille": "08", "sous_famille": "08 01", "designation_fr": "Déchets de moulage des plastiques", "designation_ar": "نفايات قالب البلاستيك", "classe": "S", "annexe": "II"},
    {"code": "08.02.01", "famille": "08", "sous_famille": "08 02", "designation_fr": "Résidus de polymerisation et de condensation de plastiques", "designation_ar": "بقايا التكاثف والتكثيف للبلاستيك", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "inflammable": True},
    {"code": "08.03.01", "famille": "08", "sous_famille": "08 03", "designation_fr": "Déchets de composition plastique", "designation_ar": "نفايات التراكيب البلاستيكية", "classe": "S", "annexe": "II"},
    {"code": "08.04.01", "famille": "08", "sous_famille": "08 04", "designation_fr": "Déchets de thermoformage de plastiques", "designation_ar": "نفايات التشكيل الحراري للبلاستيك", "classe": "S", "annexe": "II"},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 09 — Déchets de traitement des peaux et du cuir
    # ═══════════════════════════════════════════════════════════════════
    {"code": "09.01.01", "famille": "09", "sous_famille": "09 01", "designation_fr": "Déchets de traitement thermique des peaux et du cuir", "designation_ar": "نفايات المعالجة الحرارية للجلود", "classe": "S", "annexe": "II", "infectieuse": True},
    {"code": "09.02.01", "famille": "09", "sous_famille": "09 02", "designation_fr": "Déchets de tannage des peaux et du cuir", "designation_ar": "نفاياتدباغة الجلود", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "09.03.01", "famille": "09", "sous_famille": "09 03", "designation_fr": "Boues de tannage des peaux et du cuir", "designation_ar": "حمأة دباغة الجلود", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 10 — Déchets de traitement du bois
    # ═══════════════════════════════════════════════════════════════════
    {"code": "10.01.01", "famille": "10", "sous_famille": "10 01", "designation_fr": "Déchets de traitement et d'imprégnation du bois", "designation_ar": "نفايات المعالجة والتغليف للخشب", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},
    {"code": "10.02.01", "famille": "10", "sous_famille": "10 02", "designation_fr": "Déchets de traitement de surface du bois", "designation_ar": "نفايات المعالجة السطحية للخشب", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "10.03.01", "famille": "10", "sous_famille": "10 03", "designation_fr": "Déchets de conservation du bois", "designation_ar": "نفايات حفظ الخشب", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 11 — Déchets de transformation des produits à base de papier
    # ═══════════════════════════════════════════════════════════════════
    {"code": "11.01.01", "famille": "11", "sous_famille": "11 01", "designation_fr": "Boues de traitement des eaux usées de l'industrie papetière", "designation_ar": "حمأة معالجة مياه الصرف من صناعة الورق", "classe": "S", "annexe": "II", "infectieuse": True},
    {"code": "11.02.01", "famille": "11", "sous_famille": "11 02", "designation_fr": "Déchets de fabrication de pâte à papier", "designation_ar": "نفايات تصنيع لب الورق", "classe": "S", "annexe": "II", "toxique": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 12 — Déchets de transformation du coton et des textiles
    # ═══════════════════════════════════════════════════════════════════
    {"code": "12.01.01", "famille": "12", "sous_famille": "12 01", "designation_fr": "Déchets de traitement de surface des textiles", "designation_ar": "نفايات المعالجة السطحية للأقمشة", "classe": "S", "annexe": "II", "toxique": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 13 — Déchets de transformation de la photographie
    # ═══════════════════════════════════════════════════════════════════
    {"code": "13.01.01", "famille": "13", "sous_famille": "13 01", "designation_fr": "Huiles hydrauliques chlorées", "designation_ar": "زيوت هيدروليكية كلورية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},
    {"code": "13.01.02", "famille": "13", "sous_famille": "13 01", "designation_fr": "Solvants et bains de développement de la photographie", "designation_ar": "المذيبات وأ baths التحميل للتصوير الفوتوغرافي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "13.01.03", "famille": "13", "sous_famille": "13 01", "designation_fr": "Bains de fixage de la photographie", "designation_ar": "أ baths التثبيت للتصوير الفوتوغرافي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "13.01.04", "famille": "13", "sous_famille": "13 01", "designation_fr": "Bains de blanchiment de la photographie", "designation_ar": "أ baths التبييض للتصوير الفوتوغرافي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "13.01.05", "famille": "13", "sous_famille": "13 01", "designation_fr": "Bains d'accentuation de la photographie", "designation_ar": "أ baths التمييز للتصوير الفوتوغرافي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "13.01.06", "famille": "13", "sous_famille": "13 01", "designation_fr": "Bains de virage de la photographie", "designation_ar": "أ baths التحويل للتصوير الفوتوغرافي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "13.02.01", "famille": "13", "sous_famille": "13 02", "designation_fr": "Solvants et bains de traitement de la photographie argentique", "designation_ar": "المذيبات وأ baths معالجة التصوير الفضي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "corrosive": True},
    {"code": "13.03.01", "famille": "13", "sous_famille": "13 03", "designation_fr": "Boues de traitement de la photographie", "designation_ar": "حمأة معالجة التصوير الفوتوغرافي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "13.04.01", "famille": "13", "sous_famille": "13 04", "designation_fr": "Déchets d'impression photographique numérique", "designation_ar": "نفايات طباعة التصوير الرقمي", "classe": "S", "annexe": "II"},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 14 — Déchets municipaux et assimilés
    # ═══════════════════════════════════════════════════════════════════
    {"code": "14.01.01", "famille": "14", "sous_famille": "14 01", "designation_fr": "Déchets de collecte sélective des emballages", "designation_ar": "نفايات الجمع الانتقائي للعبوات", "classe": "MA", "annexe": "II"},
    {"code": "14.02.01", "famille": "14", "sous_famille": "14 02", "designation_fr": "Déchets de tri des déchets municipaux", "designation_ar": "نفايات فرز النفايات البلدية", "classe": "MA", "annexe": "II"},
    {"code": "14.03.01", "famille": "14", "sous_famille": "14 03", "designation_fr": "Déchets de compostage des déchets municipaux", "designation_ar": "نفايات التسميد من النفايات البلدية", "classe": "MA", "annexe": "II", "infectieuse": True},
    {"code": "14.04.01", "famille": "14", "sous_famille": "14 04", "designation_fr": "Déchets de méthanisation des déchets municipaux", "designation_ar": "نفايات الميثانة من النفايات البلدية", "classe": "MA", "annexe": "II", "inflammable": True, "infectieuse": True},
    {"code": "14.05.01", "famille": "14", "sous_famille": "14 05", "designation_fr": "Déchets de stationnement et de traitement des déchets municipaux", "designation_ar": "نفايات المحطة ومعالجة النفايات البلدية", "classe": "MA", "annexe": "II", "infectieuse": True},
    {"code": "14.06.01", "famille": "14", "sous_famille": "14 06", "designation_fr": "Déchets de traitement chimique et biologique des déchets municipaux", "designation_ar": "نفايات المعالجة الكيميائية والبيولوجية للنفايات البلدية", "classe": "S", "annexe": "II", "infectieuse": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 15 — Emballages
    # ═══════════════════════════════════════════════════════════════════
    {"code": "15.01.01", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages en papier/carton", "designation_ar": "عبوات من الورق الكرتون", "classe": "MA", "annexe": "II", "bsd_obligatoire": False, "agrement_requis": False},
    {"code": "15.01.02", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages en matières plastiques", "designation_ar": "عبوات من المواد البلاستيكية", "classe": "MA", "annexe": "II"},
    {"code": "15.01.03", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages en bois", "designation_ar": "عبوات من الخشب", "classe": "MA", "annexe": "II"},
    {"code": "15.01.04", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages métalliques", "designation_ar": "عبوات معدنية", "classe": "MA", "annexe": "II"},
    {"code": "15.01.05", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages en verre", "designation_ar": "عبوات زجاجية", "classe": "MA", "annexe": "II"},
    {"code": "15.01.06", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages composites", "designation_ar": "عبوات مركبة", "classe": "MA", "annexe": "II"},
    {"code": "15.01.07", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages en textile", "designation_ar": "عبوات من الأنسجة", "classe": "MA", "annexe": "II"},
    {"code": "15.01.08", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages en mélange", "designation_ar": "عبوات مختلطة", "classe": "MA", "annexe": "II"},
    {"code": "15.01.09", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages souillés (non nettoyés)", "designation_ar": "عبوات ملوثة (غير مغسولة)", "classe": "S", "annexe": "II", "infectieuse": True, "inflammable": True},
    {"code": "15.01.10", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages en papier/cartouche souillés", "designation_ar": "عبوات ورقية ملوثة", "classe": "S", "annexe": "II"},
    {"code": "15.01.11", "famille": "15", "sous_famille": "15 01", "designation_fr": "Emballages en matières plastiques souillés", "designation_ar": "عبوات بلاستيكية ملوثة", "classe": "S", "annexe": "II", "inflammable": True},
    {"code": "15.02.01", "famille": "15", "sous_famille": "15 02", "designation_fr": "Emballages contenant des résidus de substances dangereuses ou contaminés", "designation_ar": "عبوات تحتوي على بقايا مواد خطرة أو ملوثة", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 16 — Véhicules hors d'usage et batteries usagées
    # ═══════════════════════════════════════════════════════════════════
    {"code": "16.01.01", "famille": "16", "sous_famille": "16 01", "designation_fr": "Pneus hors d'usage", "designation_ar": "إطارات منتهية الصلاحية", "classe": "S", "annexe": "II"},
    {"code": "16.01.02", "famille": "16", "sous_famille": "16 01", "designation_fr": "Pneus hors d'usage concassés ou broyés", "designation_ar": "إطارات منتهية الصلاحية مطحونة", "classe": "S", "annexe": "II"},
    {"code": "16.01.03", "famille": "16", "sous_famille": "16 01", "designation_fr": "Pneus hors d'usage en morceaux", "designation_ar": "إطارات منتهية الصلاحية مقطعة", "classe": "S", "annexe": "II"},
    {"code": "16.02.01", "famille": "16", "sous_famille": "16 02", "designation_fr": "Véhicules hors d'usage", "designation_ar": "مركبات منتهية الصلاحية", "classe": "S", "annexe": "II"},
    {"code": "16.02.02", "famille": "16", "sous_famille": "16 02", "designation_fr": "Déchets provenant des véhicules hors d'usage", "designation_ar": "نفايات ناتجة عن المركبات منتهية الصلاحية", "classe": "S", "annexe": "II"},
    {"code": "16.04.01", "famille": "16", "sous_famille": "16 04", "designation_fr": "Batteries au plomb", "designation_ar": "بطاريات رصاص", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "corrosive": True, "dangereuse_environnement": True},
    {"code": "16.05.01", "famille": "16", "sous_famille": "16 05", "designation_fr": "Piles et accumulateurs", "designation_ar": "البطاريات والمراكم", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "corrosive": True, "dangereuse_environnement": True},
    {"code": "16.05.02", "famille": "16", "sous_famille": "16 05", "designation_fr": "Piles et accumulateurs au cadmium", "designation_ar": "بطاريات ومراكم كادميوم", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},
    {"code": "16.05.03", "famille": "16", "sous_famille": "16 05", "designation_fr": "Piles et accumulateurs au mercure", "designation_ar": "بطاريات ومراكم زئبق", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},
    {"code": "16.05.04", "famille": "16", "sous_famille": "16 05", "designation_fr": "Piles et accumulateurs au lithium", "designation_ar": "بطاريات ومراكم ليثيوم", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "inflammable": True, "explosible": True},
    {"code": "16.06.01", "famille": "16", "sous_famille": "16 06", "designation_fr": "Véhicules hors d'usage (fluides)", "designation_ar": "مركبات منتهية الصلاحية (سوائل)", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "16.06.02", "famille": "16", "sous_famille": "16 06", "designation_fr": "Véhicules hors d'usage (composants)", "designation_ar": "مركبات منتهية الصلاحية (مكونات)", "classe": "S", "annexe": "II"},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 17 — Déchets de construction et de démolition
    # ═══════════════════════════════════════════════════════════════════
    {"code": "17.01.01", "famille": "17", "sous_famille": "17 01", "designation_fr": "Béton", "designation_ar": "خرسانة", "classe": "I", "annexe": "II"},
    {"code": "17.01.02", "famille": "17", "sous_famille": "17 01", "designation_fr": "Briques", "designation_ar": "طوب", "classe": "I", "annexe": "II"},
    {"code": "17.01.03", "famille": "17", "sous_famille": "17 01", "designation_fr": "Tuiles et céramiques", "designation_ar": "بلاط وسيراميك", "classe": "I", "annexe": "II"},
    {"code": "17.01.04", "famille": "17", "sous_famille": "17 01", "designation_fr": "Bois de démolition non traité", "designation_ar": "خشب هدم غير معالج", "classe": "I", "annexe": "II"},
    {"code": "17.01.05", "famille": "17", "sous_famille": "17 01", "designation_fr": "Métaux non dangereux", "designation_ar": "معادن غير خطرة", "classe": "I", "annexe": "II"},
    {"code": "17.01.06", "famille": "17", "sous_famille": "17 01", "designation_fr": "Plastiques non dangereux", "designation_ar": "بلاستيك غير خطر", "classe": "I", "annexe": "II"},
    {"code": "17.01.07", "famille": "17", "sous_famille": "17 01", "designation_fr": "Verres non dangereux", "designation_ar": "زجاج غير خطر", "classe": "I", "annexe": "II"},
    {"code": "17.02.01", "famille": "17", "sous_famille": "17 02", "designation_fr": "Bois traité non dangereux", "designation_ar": "خشب معالج غير خطر", "classe": "I", "annexe": "II"},
    {"code": "17.02.02", "famille": "17", "sous_famille": "17 02", "designation_fr": "Plastiques dangereux", "designation_ar": "بلاستيك خطر", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "17.02.03", "famille": "17", "sous_famille": "17 02", "designation_fr": "Bois traité dangereux", "designation_ar": "خشب معالج خطر", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},
    {"code": "17.04.01", "famille": "17", "sous_famille": "17 04", "designation_fr": "Métaux dangereux", "designation_ar": "معادن خطرة", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "17.04.02", "famille": "17", "sous_famille": "17 04", "designation_fr": "Amiante", "designation_ar": "أزبست", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "cancerogene": True},
    {"code": "17.04.03", "famille": "17", "sous_famille": "17 04", "designation_fr": "Peintures contenant des solvants ou d'autres substances dangereuses", "designation_ar": "دهانات تحتوي على مذيبات أو مواد خطرة أخرى", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "inflammable": True},
    {"code": "17.04.04", "famille": "17", "sous_famille": "17 04", "designation_fr": "Matières de remplissage contaminées", "designation_ar": "مواد تعبئة ملوثة", "classe": "S", "annexe": "II", "toxique": True},
    {"code": "17.04.05", "famille": "17", "sous_famille": "17 04", "designation_fr": "Matières de remplissage non contaminées", "designation_ar": "مواد تعبئة غير ملوثة", "classe": "I", "annexe": "II"},
    {"code": "17.04.06", "famille": "17", "sous_famille": "17 04", "designation_fr": "Poussières de démolition", "designation_ar": "غبار الهدم", "classe": "I", "annexe": "II"},
    {"code": "17.04.07", "famille": "17", "sous_famille": "17 04", "designation_fr": "Déchets de déconstruction contenant des substances dangereuses", "designation_ar": "نفايات الهدم تحتوي على مواد خطرة", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "17.06.01", "famille": "17", "sous_famille": "17 06", "designation_fr": "Isolants contenant des substances dangereuses", "designation_ar": "عوازل تحتوي على مواد خطرة", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "cancerogene": True, "dangereuse_environnement": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 18 — Déchets provenant des soins médicaux ou vétérinaires
    # ═══════════════════════════════════════════════════════════════════
    {"code": "18.01.01", "famille": "18", "sous_famille": "18 01", "designation_fr": "Déchets de soins aigus (coupants/tranchants)", "designation_ar": "نفايات العناية الحادة (حادرة/قاطعة)", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True, "toxique": True},
    {"code": "18.01.02", "famille": "18", "sous_famille": "18 01", "designation_fr": "Déchets de soins aigus (non coupants)", "designation_ar": "نفايات العناية الحادة (غير حادة)", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.01.03", "famille": "18", "sous_famille": "18 01", "designation_fr": "Déchets de soins aigus contenant des substances dangereuses", "designation_ar": "نفايات العناية الحادة تحتوي على مواد خطرة", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "18.01.04", "famille": "18", "sous_famille": "18 01", "designation_fr": "Déchets d'implantations médicales", "designation_ar": "نفايات الزرع الطبي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.02.01", "famille": "18", "sous_famille": "18 02", "designation_fr": "Déchets de chirurgie dentaire", "designation_ar": "نفايات جراحة الأسنان", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True, "toxique": True},
    {"code": "18.03.01", "famille": "18", "sous_famille": "18 03", "designation_fr": "Déchets de services de pharmacie et d'analyses médicales", "designation_ar": "نفايات خدمات الصيدلية والتحليلات الطبية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True, "toxique": True},
    {"code": "18.04.01", "famille": "18", "sous_famille": "18 04", "designation_fr": "Déchets d'hémodialyse", "designation_ar": "نفايات غسيل الكلى", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.05.01", "famille": "18", "sous_famille": "18 05", "designation_fr": "Déchets d'ophtalmologie", "designation_ar": "نفايات طب العيون", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.06.01", "famille": "18", "sous_famille": "18 06", "designation_fr": "Déchets des laboratoires de recherche médicale", "designation_ar": "نفايات مختبرات البحث الطبي", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True, "toxique": True},
    {"code": "18.07.01", "famille": "18", "sous_famille": "18 07", "designation_fr": "Déchets vétérinaires", "designation_ar": "نafaيات طب البَر", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.08.01", "famille": "18", "sous_famille": "18 08", "designation_fr": "Autres déchets provenant des soins médicaux", "designation_ar": "نفايات أخرى من الرعاية الطبية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.09.01", "famille": "18", "sous_famille": "18 09", "designation_fr": "Déchets d'actions préventives et curatives non spécifiées", "designation_ar": "نfaidات الإجراءات الوقائية والعلاجية غير المحددة", "classe": "S", "annexe": "II"},
    {"code": "18.10.01", "famille": "18", "sous_famille": "18 10", "designation_fr": "Déchets de bloc opératoire", "designation_ar": "نfaidات غرفة العمليات", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.11.01", "famille": "18", "sous_famille": "18 11", "designation_fr": "Déchets d'autopsie", "designation_ar": "نfaidات التشريح", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.12.01", "famille": "18", "sous_famille": "18 12", "designation_fr": "Fèces, urines et autres déjections", "designation_ar": "البراز والبول ونfaidات أخرى", "classe": "S", "annexe": "II", "infectieuse": True},
    {"code": "18.13.01", "famille": "18", "sous_famille": "18 13", "designation_fr": "Fioles sanguines et déchets contaminés par le sang", "designation_ar": "أنابيب الدم ونfaidات ملوثة بالدم", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},
    {"code": "18.14.01", "famille": "18", "sous_famille": "18 14", "designation_fr": "Matières plastiques jetables contaminées", "designation_ar": "مواد بلاستيكية قابلة للتخلص ملوثة", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 19 — Déchets provenant du traitement des eaux usées
    # ═══════════════════════════════════════════════════════════════════
    {"code": "19.01.01", "famille": "19", "sous_famille": "19 01", "designation_fr": "Boues de traitement biologique des eaux usées", "designation_ar": "حمأة المعالجة البيولوجية لمياه الصرف", "classe": "S", "annexe": "II", "infectieuse": True},
    {"code": "19.02.01", "famille": "19", "sous_famille": "19 02", "designation_fr": "Boues de traitement physique-chimique des eaux usées", "designation_ar": "حمأة المعالجة الكيميائية الفيزيائية لمياه الصرف", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "19.03.01", "famille": "19", "sous_famille": "19 03", "designation_fr": "Boues de traitement chimique des eaux usées", "designation_ar": "حمأة المعالجة الكيميائية لمياه الصرف", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "19.04.01", "famille": "19", "sous_famille": "19 04", "designation_fr": "Boues de stabilisation des eaux usées", "designation_ar": "حمأة تثبيت مياه الصرف", "classe": "S", "annexe": "II"},
    {"code": "19.05.01", "famille": "19", "sous_famille": "19 05", "designation_fr": "Boues d'épaississement des eaux usées", "designation_ar": "حمأة تكثيف مياه الصرف", "classe": "S", "annexe": "II", "infectieuse": True},
    {"code": "19.06.01", "famille": "19", "sous_famille": "19 06", "designation_fr": "Boues de dessalement des eaux saumâtres", "designation_ar": "حمأة تحلية المياه المالحة", "classe": "I", "annexe": "II"},
    {"code": "19.07.01", "famille": "19", "sous_famille": "19 07", "designation_fr": "Lisiers de traitement des eaux usées", "designation_ar": "مسالات معالجة مياه الصرف", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "infectieuse": True, "toxique": True},
    {"code": "19.08.01", "famille": "19", "sous_famille": "19 08", "designation_fr": "Déchets de traitement biologique des eaux usées non spécifiés", "designation_ar": "نfaidات المعالجة البيولوجية لمياه الصرف غير المحددة", "classe": "S", "annexe": "II"},
    {"code": "19.08.02", "famille": "19", "sous_famille": "19 08", "designation_fr": "Déchets de traitement chimique des eaux usées non spécifiés", "designation_ar": "نfaidات المعالجة الكيميائية لمياه الصرف غير المحددة", "classe": "S", "annexe": "II"},
    {"code": "19.08.03", "famille": "19", "sous_famille": "19 08", "designation_fr": "Déchets de traitement physique des eaux usées non spécifiés", "designation_ar": "نfaidات المعالجة الفيزيائية لمياه الصرف غير المحددة", "classe": "S", "annexe": "II"},
    {"code": "19.08.04", "famille": "19", "sous_famille": "19 08", "designation_fr": "Déchets de traitement des eaux usées non spécifiés", "designation_ar": "نfaidات معالجة مياه الصرف غير المحددة", "classe": "S", "annexe": "II"},
    {"code": "19.08.05", "famille": "19", "sous_famille": "19 08", "designation_fr": "Déchets de traitement chimico-physique des eaux usées non spécifiés", "designation_ar": "نfaidات المعالجة الكيميائية الفيزيائية لمياه الصرف غير المحددة", "classe": "S", "annexe": "II"},
    {"code": "19.08.06", "famille": "19", "sous_famille": "19 08", "designation_fr": "Déchets de traitement des eaux de pluie", "designation_ar": "نfaidات معالجة مياه الأمطار", "classe": "I", "annexe": "II"},
    {"code": "19.08.07", "famille": "19", "sous_famille": "19 08", "designation_fr": "Boues de traitement des eaux de pluie", "designation_ar": "حمأة معالجة مياه الأمطار", "classe": "S", "annexe": "II"},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 20 — Déchets municipaux en mélange et déchets encombrants
    # ═══════════════════════════════════════════════════════════════════
    {"code": "20.01.01", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de cuisine et de cantine", "designation_ar": "نfaidات المطبخ والطعام", "classe": "MA", "annexe": "II", "infectieuse": True},
    {"code": "20.01.02", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de produits de la pêche", "designation_ar": "نfaidات منتجات الصيد", "classe": "MA", "annexe": "II", "infectieuse": True},
    {"code": "20.01.03", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de fruits, légumes, viandes, os et produits laitiers", "designation_ar": "نfaidات الفواكه والخضروات واللحوم والعظام ومنتجات الألبان", "classe": "MA", "annexe": "II", "infectieuse": True},
    {"code": "20.01.04", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de boulangerie et pâtisserie", "designation_ar": "نfaidات المخابز والحلويات", "classe": "MA", "annexe": "II"},
    {"code": "20.01.05", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de préparation de repas", "designation_ar": "نfaidات تحضير الوجبات", "classe": "MA", "annexe": "II"},
    {"code": "20.01.06", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de jardins et parcs", "designation_ar": "نfaidات الحدائق والمنتزهات", "classe": "MA", "annexe": "II"},
    {"code": "20.01.07", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de cimetières", "designation_ar": "نfaidات المقابر", "classe": "S", "annexe": "II", "infectieuse": True},
    {"code": "20.01.08", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de dépotoirs", "designation_ar": "نfaidات مدافن النفايات", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "infectieuse": True, "dangereuse_environnement": True},
    {"code": "20.01.09", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de marchés", "designation_ar": "نfaidات الأسواق", "classe": "MA", "annexe": "II"},
    {"code": "20.01.10", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets verts", "designation_ar": "نfaidات الجمع الانتقائي للنفايات الخضراء", "classe": "MA", "annexe": "II"},
    {"code": "20.01.11", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des encombrants", "designation_ar": "نfaidات الجمع الانتقائي للنfaidات الضخمة", "classe": "MA", "annexe": "II"},
    {"code": "20.01.12", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets textiles", "designation_ar": "نfaidات الجمع الانتقائي للنfaidات القماشية", "classe": "MA", "annexe": "II"},
    {"code": "20.01.13", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des métaux", "designation_ar": "نfaidات الجمع الانتقائي للمعادن", "classe": "MA", "annexe": "II"},
    {"code": "20.01.14", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des verres", "designation_ar": "نfaidات الجمع الانتقائي للزجاج", "classe": "MA", "annexe": "II"},
    {"code": "20.01.15", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des papiers/cartons", "designation_ar": "نfaidات الجمع الانتقائي للورق والكرتون", "classe": "MA", "annexe": "II"},
    {"code": "20.01.16", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des matières plastiques", "designation_ar": "نfaidات الجمع الانتقائي للمواد البلاستيكية", "classe": "MA", "annexe": "II"},
    {"code": "20.01.17", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des huiles usagées", "designation_ar": "نfaidات الجمع الانتقائي للزيوت المستعملة", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "20.01.18", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des métaux ferreux", "designation_ar": "نfaidات الجمع الانتقائي للمعادن الحديدية", "classe": "MA", "annexe": "II"},
    {"code": "20.01.19", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des métaux non ferreux", "designation_ar": "نfaidات الجمع الانتقائي للمعادن غير الحديدية", "classe": "MA", "annexe": "II"},
    {"code": "20.01.20", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des appareils électriques et électroniques", "designation_ar": "نfaidات الجمع الانتقائي للأجهزة الكهربائية والإلكترونية", "classe": "S", "annexe": "II"},
    {"code": "20.01.21", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des piles et accumulateurs", "designation_ar": "نfaidات الجمع الانتقائي للبطاريات والمراكم", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
    {"code": "20.01.22", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des médicaments périmés", "designation_ar": "نfaidات الجمع الانتقائي للأدوية منتهية الصلاحية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True},
    {"code": "20.01.23", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des produits chimiques ménagers", "designation_ar": "نfaidات الجمع الانتقائي للمنتجات الكيميائية المنزلية", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "corrosive": True, "inflammable": True},
    {"code": "20.01.24", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des pneus usagés", "designation_ar": "نfaidات الجمع الانتقائي للإطارات المستعملة", "classe": "S", "annexe": "II"},
    {"code": "20.01.25", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des encombrants", "designation_ar": "نfaidات الجمع الانتقائي للأحجام الكبيرة", "classe": "MA", "annexe": "II"},
    {"code": "20.01.26", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets verts", "designation_ar": "نfaidات الجمع الانتقائي للنfaidات الخضراء", "classe": "MA", "annexe": "II"},
    {"code": "20.01.27", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des emballages", "designation_ar": "نfaidات الجمع الانتقائي للعبوات", "classe": "MA", "annexe": "II"},
    {"code": "20.01.28", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de cuisine", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات المطبخ", "classe": "MA", "annexe": "II"},
    {"code": "20.01.29", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de jardins", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات الحدائق", "classe": "MA", "annexe": "II"},
    {"code": "20.01.30", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de boulangerie", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات المخابز", "classe": "MA", "annexe": "II"},
    {"code": "20.01.31", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de préparation de repas", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات تحضير الوجبات", "classe": "MA", "annexe": "II"},
    {"code": "20.01.32", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de cimetières", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات المقابر", "classe": "S", "annexe": "II"},
    {"code": "20.01.33", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de dépotoirs", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات مدافن النفايات", "classe": "SD", "annexe": "III"},
    {"code": "20.01.34", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de marchés", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات الأسواق", "classe": "MA", "annexe": "II"},
    {"code": "20.01.35", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de fruits et légumes", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات الفواكه والخضروات", "classe": "MA", "annexe": "II"},
    {"code": "20.01.36", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de produits de la pêche", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات منتجات الصيد", "classe": "MA", "annexe": "II"},
    {"code": "20.01.37", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de viandes, os et produits laitiers", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات اللحوم والعظام ومنتجات الألبان", "classe": "MA", "annexe": "II"},
    {"code": "20.01.38", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de cuisine et de cantine", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات المطبخ والطعام", "classe": "MA", "annexe": "II"},
    {"code": "20.01.39", "famille": "20", "sous_famille": "20 01", "designation_fr": "Déchets de collecte sélective des déchets de boulangerie et pâtisserie", "designation_ar": "نfaidات الجمع الانتقائي لنfaidات المخابز والحلويات", "classe": "MA", "annexe": "II"},
    {"code": "20.02.01", "famille": "20", "sous_famille": "20 02", "designation_fr": "Déchets municipaux en mélange non triés", "designation_ar": "نfaidات البلدية المختلطة غير الفرز", "classe": "MA", "annexe": "II"},

    # ═══════════════════════════════════════════════════════════════════
    # FAMILLE 21 — Déchets d'incinération de déchets municipaux
    # ═══════════════════════════════════════════════════════════════════
    {"code": "21.01.01", "famille": "21", "sous_famille": "21 01", "designation_fr": "Cendres et mâchefers d'incinération des déchets municipaux", "designation_ar": "رماد ورماد احتراق النfaidات البلدية", "classe": "S", "annexe": "II", "toxique": True, "dangereuse_environnement": True},
    {"code": "21.02.01", "famille": "21", "sous_famille": "21 02", "designation_fr": "Boues d'épuration des fumées d'incinération", "designation_ar": "حمأة تنقية دخان الاحترام", "classe": "SD", "annexe": "III", "bsd_obligatoire": True, "agrement_requis": True, "toxique": True, "dangereuse_environnement": True},
]


class Command(BaseCommand):
    help = 'Peuple la nomenclature complète des déchets (Décret 06-104)'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        skipped = 0

        for data in NOMENCLATURE_DATA:
            obj, was_created = Nomenclature.objects.update_or_create(
                code=data['code'],
                defaults=data,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Nomenclature peuplée : {created} créée(s), {updated} mise(s) à jour, '
            f'{created + updated} total'
        ))
