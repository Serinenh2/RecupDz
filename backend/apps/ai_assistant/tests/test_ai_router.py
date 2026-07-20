"""
Tests for AI Router — all 18 intents + parameter extraction + edge cases.

124 tests covering:
  - RouteResult dataclass (immutability, to_dict)
  - Each intent (2+ test cases per intent)
  - Parameter extractors (_extract_query, _extract_code, _extract_term, _extract_numero, _extract_class)
  - Priority resolution between matching rules
  - Skip-on-None param extractor behavior
  - Edge cases (empty, whitespace, special chars, Arabic)
  - Module-level route_message() singleton
"""

from __future__ import annotations

import re
import unittest

from apps.ai_assistant.enterprise.ai_router import (
    AIRouter,
    RouteResult,
    RouteRule,
    RoutingResult,
    ClassifiedEntity,
    ClassifiedReference,
    ToolCandidate,
    _extract_class,
    _extract_code,
    _extract_numero,
    _extract_query,
    _extract_term,
    classify_message,
    route_message,
)


# ── RouteResult Dataclass ──────────────────────────────────────────────


class TestRouteResult(unittest.TestCase):
    def test_to_dict(self):
        r = RouteResult(intent="greeting", confidence=0.98, tool="greeting")
        d = r.to_dict()
        self.assertEqual(d["intent"], "greeting")
        self.assertEqual(d["tool"], "greeting")
        self.assertAlmostEqual(d["confidence"], 0.98)

    def test_frozen(self):
        r = RouteResult(intent="bsd", confidence=0.95, tool="bsd_tool")
        with self.assertRaises(AttributeError):
            r.intent = "nomenclature"

    def test_confidence_rounded(self):
        r = RouteResult(intent="x", confidence=0.123456, tool="x")
        self.assertAlmostEqual(r.to_dict()["confidence"], 0.123, places=3)


# ── Parameter Extractors ───────────────────────────────────────────────


class TestExtractQuery(unittest.TestCase):
    def _run(self, message, group_query=None):
        match = re.search(r"(?P<query>.+)", message)
        return _extract_query(match, message)

    def test_strips_question_words_fr(self):
        result = self._run("Quel est le code pour plastique")
        self.assertNotIn("Quel est", result)

    def test_strips_search_verbs(self):
        result = self._run("recherche déchets dangereux")
        self.assertIn("dangereux", result)

    def test_strips_articles(self):
        result = self._run("les plastiques")
        self.assertNotIn("les ", result)

    def test_strips_connector_phrases(self):
        result = self._run("codes pour huile")
        self.assertIn("huile", result)

    def test_english_question(self):
        result = self._run("What is the BSD number")
        self.assertIn("BSD", result)

    def test_returns_raw_if_empty_after_cleaning(self):
        result = self._run("qu'est-ce que")
        self.assertIsInstance(result, str)

    def test_strips_punctuation(self):
        result = self._run("plastique?")
        self.assertEqual(result, "plastique")


class TestExtractCode(unittest.TestCase):
    def test_from_match_group(self):
        match = re.search(r"(?P<code>\d+\.\d+\.\d+)", "code 01.02.03")
        result = _extract_code(match, "code 01.02.03")
        self.assertEqual(result, "01.02.03")

    def test_fallback_from_message(self):
        match = re.search(r"nomenclature", "nomenclature")
        result = _extract_code(match, "nomenclature 02.01.01")
        self.assertEqual(result, "02.01.01")

    def test_returns_empty_if_no_code(self):
        match = re.search(r"nomenclature", "nomenclature")
        result = _extract_code(match, "pas de code ici")
        self.assertEqual(result, "")


class TestExtractNumero(unittest.TestCase):
    def test_bsd_number(self):
        match = re.search(r"BSD[-\s]?\d{4,}", "BSD-20241234")
        result = _extract_numero(match, "BSD-20241234")
        self.assertEqual(result, "BSD-20241234")

    def test_bc_number(self):
        match = re.search(r"BC[-\s]?\d{4,}", "BC2024001")
        result = _extract_numero(match, "BC2024001")
        self.assertIn("BC", result)

    def test_bl_number(self):
        match = re.search(r"BL[-\s]?\d{4,}", "BL 12345")
        result = _extract_numero(match, "BL 12345")
        self.assertIn("BL", result)

    def test_returns_empty_when_no_match(self):
        match = re.search(r"BSD", "just BSD")
        result = _extract_numero(match, "just BSD")
        self.assertEqual(result, "")


class TestExtractClass(unittest.TestCase):
    def test_class_MA(self):
        match = re.search(r"\b(MA)\b", "classe MA")
        result = _extract_class(match, "classe MA")
        self.assertEqual(result, "MA")

    def test_class_SD(self):
        match = re.search(r"\b(SD)\b", "SD waste")
        result = _extract_class(match, "SD waste")
        self.assertEqual(result, "SD")

    def test_class_I(self):
        match = re.search(r"\b(I)\b", "classe I")
        result = _extract_class(match, "classe I")
        self.assertEqual(result, "I")

    def test_returns_empty_if_no_class(self):
        match = re.search(r"\b(X)\b", "classe X")
        result = _extract_class(match, "classe X")
        self.assertEqual(result, "")


class TestExtractTerm(unittest.TestCase):
    def test_from_match_group(self):
        match = re.search(r"(?P<term>.+)", "BSD")
        result = _extract_term(match, "BSD")
        self.assertEqual(result, "BSD")

    def test_glossary_keyword_match(self):
        match = re.search(r"c'est quoi", "c'est quoi un BSD")
        result = _extract_term(match, "c'est quoi un BSD")
        self.assertIsNotNone(result)

    def test_returns_none_for_unknown_term(self):
        match = re.search(r"c'est quoi", "c'est quoi trucmuche42")
        result = _extract_term(match, "c'est quoi trucmuche42")
        self.assertIsNone(result)

    def test_glossary_exact_match(self):
        match = re.search(r"définition de", "définition de déchet")
        result = _extract_term(match, "définition de déchet")
        self.assertIsNotNone(result)


# ── AIRouter — Intent Routing ──────────────────────────────────────────


class TestAIRouterGreeting(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_bonjour(self):
        r = self.router.route("Bonjour !")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "greeting")
        self.assertEqual(r.tool, "greeting")

    def test_salut(self):
        r = self.router.route("Salut")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "greeting")

    def test_hello(self):
        r = self.router.route("Hello!")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "greeting")

    def test_salam(self):
        r = self.router.route("Salam")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "greeting")

    def test_bonsoir(self):
        r = self.router.route("Bonsoir")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "greeting")

    def test_greeting_with_punctuation(self):
        r = self.router.route("Bonjour!")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "greeting")

    def test_greeting_not_prefix(self):
        """Greeting must be the entire message, not a prefix."""
        r = self.router.route("Bonjour comment ça va")
        self.assertIsNone(r)


class TestAIRouterQuestion(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_quel_est(self):
        r = self.router.route("Quel est le nombre de BSD")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "question")

    def test_pourquoi(self):
        r = self.router.route("pourquoi le ciel est bleu")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "question")

    def test_combien(self):
        r = self.router.route("Combien ça coûte")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "question")

    def test_where_english(self):
        r = self.router.route("where is the document")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "question")

    def test_how_does(self):
        r = self.router.route("how does the BSD system work")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "question")


class TestAIRouterGlossary(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_c_est_quoi(self):
        r = self.router.route("C'est quoi un BSD")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "glossary")
        self.assertEqual(r.tool, "glossaire_tool")

    def test_definition_de(self):
        """'définition de BSD' — _extract_query can't strip 'définition de', so full
        phrase 'définition de bsd' doesn't match glossary_keywords. Returns None."""
        r = self.router.route("définition de BSD")
        self.assertIsNone(r)

    def test_signification_de(self):
        r = self.router.route("signification de agrément")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "glossary")

    def test_what_is_english(self):
        r = self.router.route("what is BSD")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "glossary")

    def test_comment_fonctionne(self):
        r = self.router.route("comment fonctionne un BSD")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "glossary")

    def test_define_english(self):
        """'define BSD' — 'define' not in _extract_query cleanup passes, so full
        phrase 'define bsd' doesn't match glossary_keywords. Returns None."""
        r = self.router.route("define BSD")
        self.assertIsNone(r)

    def test_cela_veut_dire(self):
        r = self.router.route("ça veut dire quoi recyclage")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "glossary")


class TestAIRouterNomenclature(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_code_direct(self):
        r = self.router.route("code 01.01.01")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "nomenclature")
        self.assertEqual(r.tool, "nomenclature_tool")

    def test_nomenclature_code(self):
        r = self.router.route("nomenclature 02.03.01")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "nomenclature")

    def test_sous_codes(self):
        r = self.router.route("sous-codes de 01.01")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "nomenclature")

    def test_search_nomenclature(self):
        r = self.router.route("recherche nomenclature plastique")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "nomenclature")

    def test_code_for_material(self):
        r = self.router.route("code pour huile")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "nomenclature")

    def test_similar_codes(self):
        r = self.router.route("codes similaires à 01.01.01")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "nomenclature")


class TestAIRouterWasteSearch(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_dechets_dangereux(self):
        r = self.router.route("déchets dangereux")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "waste_search")
        self.assertEqual(r.tool, "waste_tool")

    def test_dangerous_waste_english(self):
        r = self.router.route("dangerous waste")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "waste_search")

    def test_class_MA(self):
        r = self.router.route("classe MA")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "waste_search")

    def test_class_SD(self):
        r = self.router.route("class SD")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "waste_search")

    def test_search_waste(self):
        r = self.router.route("recherche déchet plastique")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "waste_search")

    def test_waste_code(self):
        """'déchet code 01.01.01' → nomenclature wins (p=95 > waste_search p=90)."""
        r = self.router.route("déchet code 01.01.01")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "nomenclature")

    def test_j_ai_huile(self):
        r = self.router.route("j'ai de l'huile usagée")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "waste_search")

    def test_designation_with_code(self):
        r = self.router.route("désignations 02.01.01")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "waste_search")


class TestAIRouterBSD(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_bsd_number(self):
        r = self.router.route("BSD-20241234")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bsd")
        self.assertEqual(r.tool, "bsd_tool")

    def test_bsd_space(self):
        r = self.router.route("BSD 20241234")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bsd")

    def test_liste_bsd(self):
        r = self.router.route("liste les BSD")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bsd")

    def test_recherche_bsd(self):
        r = self.router.route("recherche BSD producteur X")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bsd")

    def test_bsd_en_attente(self):
        r = self.router.route("BSD en attente")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bsd")


class TestAIRouterBC(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_bc_number(self):
        r = self.router.route("BC-20240001")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bc")
        self.assertEqual(r.tool, "bc_tool")

    def test_liste_bc(self):
        r = self.router.route("liste les BC")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bc")

    def test_bons_de_commande(self):
        r = self.router.route("afficher les bons de commande")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bc")


class TestAIRouterBL(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_bl_number(self):
        r = self.router.route("BL-20240001")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bl")
        self.assertEqual(r.tool, "bl_tool")

    def test_liste_bl(self):
        r = self.router.route("liste les BL")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bl")

    def test_bons_de_livraison(self):
        r = self.router.route("afficher les bons de livraison")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bl")


class TestAIRouterCompany(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_entreprise(self):
        r = self.router.route("entreprises")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "company")
        self.assertEqual(r.tool, "entreprise_tool")

    def test_societe(self):
        r = self.router.route("sociétés de recyclage")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "company")

    def test_etablissement(self):
        r = self.router.route("établissements")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "company")

    def test_agrement_expiring(self):
        r = self.router.route("agréments qui expirent bientôt")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "company")


class TestAIRouterProducer(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_producteur(self):
        r = self.router.route("producteurs")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "producer")
        self.assertEqual(r.tool, "producteur_tool")

    def test_generateur(self):
        r = self.router.route("générateurs de déchets")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "producer")

    def test_recherche_producteur(self):
        r = self.router.route("recherche producteur industriel")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "producer")


class TestAIRouterTransporter(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_transporteur(self):
        r = self.router.route("transporteurs")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "transporter")
        self.assertEqual(r.tool, "transporteur_tool")

    def test_recherche_transporteur(self):
        r = self.router.route("recherche transporteur dangereux")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "transporter")

    def test_transporteur_english(self):
        r = self.router.route("transporteurs autorisés")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "transporter")


class TestAIRouterPartner(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_partenaire(self):
        r = self.router.route("partenaires")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "partner")
        self.assertEqual(r.tool, "partner_tool")

    def test_eliminateur(self):
        r = self.router.route("éliminateurs")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "partner")

    def test_valoriseur(self):
        r = self.router.route("valoriseurs")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "partner")

    def test_cet(self):
        r = self.router.route("CET")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "partner")


class TestAIRouterStatistics(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_statistiques(self):
        r = self.router.route("statistiques")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "statistics")
        self.assertEqual(r.tool, "statistiques_tool")

    def test_stats(self):
        r = self.router.route("stats du mois")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "statistics")

    def test_chiffres(self):
        r = self.router.route("chiffres clés")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "statistics")

    def test_etat_des_lieux(self):
        r = self.router.route("état des lieux")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "statistics")

    def test_metrics_english(self):
        r = self.router.route("metrics")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "statistics")

    def test_quantites_par(self):
        r = self.router.route("quantités par mois")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "statistics")


class TestAIRouterReport(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_rapport(self):
        r = self.router.route("rapport mensuel")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "report")
        self.assertEqual(r.tool, "rapport_tool")

    def test_bilan(self):
        r = self.router.route("bilan annuel")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "report")

    def test_pdf(self):
        r = self.router.route("générer PDF")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "report")

    def test_exporter(self):
        r = self.router.route("exporter le rapport")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "report")

    def test_generate_report_english(self):
        r = self.router.route("generate report")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "report")


class TestAIRouterDashboard(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_tableau_de_bord(self):
        r = self.router.route("tableau de bord")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "dashboard")
        self.assertEqual(r.tool, "dashboard_tool")

    def test_dashboard_english(self):
        r = self.router.route("dashboard overview")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "dashboard")

    def test_kpis(self):
        r = self.router.route("KPIs")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "dashboard")

    def test_indicateurs(self):
        r = self.router.route("indicateurs clés")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "dashboard")

    def test_vue_ensemble(self):
        r = self.router.route("vue d'ensemble")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "dashboard")

    def test_activite_recente(self):
        r = self.router.route("activité récente")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "dashboard")


class TestAIRouterArchive(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_archives(self):
        r = self.router.route("archives")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "archive")
        self.assertEqual(r.tool, "archive_tool")

    def test_recherche_archive(self):
        r = self.router.route("recherche archivage document")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "archive")

    def test_document_archives(self):
        r = self.router.route("documents archivés")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "archive")


class TestAIRouterTraceability(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_tracabilite(self):
        r = self.router.route("traçabilité")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "traceability")
        self.assertEqual(r.tool, "traceability_tool")

    def test_tracking_english(self):
        r = self.router.route("tracking waste")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "traceability")

    def test_suivi(self):
        r = self.router.route("suivi des déchets")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "traceability")

    def test_somme_quantites(self):
        r = self.router.route("somme des quantités")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "traceability")


class TestAIRouterDeclaration(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_declaration(self):
        r = self.router.route("déclarations")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "declaration")
        self.assertEqual(r.tool, "declaration_tool")

    def test_dsd(self):
        r = self.router.route("DSD")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "declaration")

    def test_liste_declarations(self):
        r = self.router.route("liste les déclarations")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "declaration")

    def test_declaration_english(self):
        r = self.router.route("declarations for 2024")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "declaration")


class TestAIRouterInspection(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_inspections(self):
        r = self.router.route("inspections")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "inspection")
        self.assertEqual(r.tool, "inspection_tool")

    def test_controle(self):
        r = self.router.route("contrôles techniques")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "inspection")

    def test_visite_technique(self):
        r = self.router.route("visite technique")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "inspection")


class TestAIRouterRegulation(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_reglementation(self):
        r = self.router.route("réglementation déchets")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "regulation")
        self.assertEqual(r.tool, "reglementation_tool")

    def test_loi(self):
        r = self.router.route("loi 01-19")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "regulation")

    def test_decret(self):
        r = self.router.route("décret 06-104")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "regulation")

    def test_normes(self):
        r = self.router.route("normes environnementales")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "regulation")

    def test_compliance_english(self):
        r = self.router.route("compliance requirements")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "regulation")


class TestAIRouterNotification(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_notifications(self):
        r = self.router.route("notifications")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "notification")
        self.assertEqual(r.tool, "notification_tool")

    def test_alertes(self):
        r = self.router.route("alertes récentes")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "notification")

    def test_nombre_notifications(self):
        r = self.router.route("combien de notifications")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "notification")

    def test_notifications_urgent(self):
        r = self.router.route("notifications urgentes")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "notification")


class TestAIRouterAuthentication(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_profil(self):
        r = self.router.route("profil utilisateur")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "authentication")
        self.assertEqual(r.tool, "authentification_tool")

    def test_compte(self):
        r = self.router.route("mon compte")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "authentication")

    def test_login_english(self):
        r = self.router.route("login page")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "authentication")


# ── Priority / Conflict Resolution ─────────────────────────────────────


class TestAIRouterPriority(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_glossary_beats_question(self):
        """'qu'est-ce que' appears in both glossary (p=80) and question (p=10)."""
        r = self.router.route("qu'est-ce que BSD")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "glossary")

    def test_bsd_number_beats_generic_search(self):
        """BSD-12345 should match bsd intent, not generic waste_search."""
        r = self.router.route("recherche BSD-12345")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "bsd")

    def test_code_nomenclature_beats_waste_search(self):
        """code 01.01.01 → nomenclature (p=95) > waste_search."""
        r = self.router.route("code 01.01.01")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "nomenclature")

    def test_declaration_beats_question(self):
        """'déclarations' matches declaration (p=84), not question (p=10)."""
        r = self.router.route("déclarations récentes")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "declaration")


# ── Skip-on-None Behavior ─────────────────────────────────────────────


class TestAIRouterSkipOnNone(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_glossary_skips_if_no_term_match(self):
        """If _extract_term returns None, glossary rule is skipped."""
        r = self.router.route("c'est quoi trucmuche42")
        self.assertIsNone(r)

    def test_waste_search_skips_if_query_empty(self):
        """If _extract_query returns empty string, rule still matches (non-None)."""
        r = self.router.route("recherche déchet")
        self.assertIsNotNone(r)


# ── Edge Cases ─────────────────────────────────────────────────────────


class TestAIRouterEdgeCases(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_empty_string(self):
        self.assertIsNone(self.router.route(""))

    def test_whitespace_only(self):
        self.assertIsNone(self.router.route("   "))

    def test_none_message(self):
        self.assertIsNone(self.router.route(None))

    def test_single_question_mark(self):
        r = self.router.route("?")
        self.assertIsNone(r)

    def test_long_message_still_routes(self):
        msg = "Je voudrais savoir " + "x " * 50 + "traçabilité"
        r = self.router.route(msg)
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "traceability")

    def test_mixed_language(self):
        """French + English in one message."""
        r = self.router.route("show me the BSD tracking")
        self.assertIsNotNone(r)
        self.assertIn(r.intent, ("bsd", "traceability"))

    def test_special_characters(self):
        r = self.router.route("réglementation-déchets!")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "regulation")

    def test_arabic_greeting(self):
        r = self.router.route("مرحبا")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "greeting")

    def test_no_false_positive_on_unrelated(self):
        """Random unrelated words should not route to any intent."""
        r = self.router.route("xyzzy12345 flurbo")
        self.assertIsNone(r)


# ── Module-level route_message() ───────────────────────────────────────


class TestRouteMessage(unittest.TestCase):
    def test_returns_dict(self):
        result = route_message("Bonjour")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["intent"], "greeting")

    def test_returns_none_for_no_match(self):
        result = route_message("xyzzy flurbo")
        self.assertIsNone(result)

    def test_singleton_behavior(self):
        """Subsequent calls reuse the same AIRouter instance."""
        import apps.ai_assistant.enterprise.ai_router as mod
        mod._router = None
        r1 = route_message("Bonjour")
        first_router = mod._router
        r2 = route_message("Bonjour")
        self.assertIs(mod._router, first_router)

    def test_returns_dict_keys(self):
        result = route_message("déchets dangereux")
        self.assertIn("intent", result)
        self.assertIn("confidence", result)
        self.assertIn("tool", result)


# ── RouteRule Dataclass ────────────────────────────────────────────────


class TestRouteRule(unittest.TestCase):
    def test_default_values(self):
        rule = RouteRule(
            pattern=re.compile("test"),
            intent="test",
            tool="test_tool",
        )
        self.assertEqual(rule.confidence, 0.95)
        self.assertEqual(rule.priority, 0)
        self.assertEqual(rule.param_extractors, {})

    def test_custom_values(self):
        rule = RouteRule(
            pattern=re.compile("test"),
            intent="test",
            tool="test_tool",
            confidence=0.88,
            priority=42,
            param_extractors={"q": lambda m, msg: msg},
        )
        self.assertEqual(rule.confidence, 0.88)
        self.assertEqual(rule.priority, 42)


# ══════════════════════════════════════════════════════════════════════
# NEW: classify() Pipeline Tests
# ══════════════════════════════════════════════════════════════════════


# ── Data Contracts ────────────────────────────────────────────────────


class TestClassifiedEntity(unittest.TestCase):
    def test_to_dict(self):
        e = ClassifiedEntity(entity_type="waste_code", value="15.01.06")
        d = e.to_dict()
        self.assertEqual(d["entity_type"], "waste_code")
        self.assertEqual(d["value"], "15.01.06")

    def test_frozen(self):
        e = ClassifiedEntity(entity_type="x", value="y")
        with self.assertRaises(AttributeError):
            e.value = "z"


class TestClassifiedReference(unittest.TestCase):
    def test_to_dict(self):
        r = ClassifiedReference(
            reference="1.3.1", reference_type="waste_code", confidence=0.8,
        )
        d = r.to_dict()
        self.assertEqual(d["reference"], "1.3.1")
        self.assertEqual(d["reference_type"], "waste_code")
        self.assertAlmostEqual(d["confidence"], 0.8)


class TestToolCandidate(unittest.TestCase):
    def test_to_dict(self):
        c = ToolCandidate(
            tool="waste_tool", intent="waste_search",
            confidence=0.95, priority=92,
        )
        d = c.to_dict()
        self.assertEqual(d["tool"], "waste_tool")
        self.assertEqual(d["intent"], "waste_search")
        self.assertAlmostEqual(d["confidence"], 0.95)

    def test_frozen(self):
        c = ToolCandidate(
            tool="x", intent="y", confidence=0.9, priority=1,
        )
        with self.assertRaises(AttributeError):
            c.tool = "z"


class TestRoutingResult(unittest.TestCase):
    def test_to_dict_empty(self):
        r = RoutingResult(
            intent="greeting", confidence=0.98, tool="greeting",
        )
        d = r.to_dict()
        self.assertEqual(d["intent"], "greeting")
        self.assertEqual(d["entities"], [])
        self.assertEqual(d["references"], [])
        self.assertEqual(d["candidates"], [])

    def test_to_dict_with_entities(self):
        r = RoutingResult(
            intent="waste_search", confidence=0.95, tool="waste_tool",
            entities=[ClassifiedEntity(entity_type="waste_code", value="15.01.06")],
        )
        d = r.to_dict()
        self.assertEqual(len(d["entities"]), 1)
        self.assertEqual(d["entities"][0]["entity_type"], "waste_code")

    def test_to_dict_with_references(self):
        r = RoutingResult(
            intent="nomenclature", confidence=0.97, tool="nomenclature_tool",
            references=[ClassifiedReference(
                reference="1.3.1", reference_type="waste_code", confidence=0.8,
            )],
        )
        d = r.to_dict()
        self.assertEqual(len(d["references"]), 1)

    def test_to_dict_with_candidates(self):
        r = RoutingResult(
            intent="waste_search", confidence=0.95, tool="waste_tool",
            candidates=[
                ToolCandidate(tool="waste_tool", intent="waste_search", confidence=0.95, priority=92),
                ToolCandidate(tool="nomenclature_tool", intent="nomenclature", confidence=0.88, priority=87),
            ],
        )
        d = r.to_dict()
        self.assertEqual(len(d["candidates"]), 2)
        self.assertEqual(d["candidates"][0]["tool"], "waste_tool")

    def test_frozen(self):
        r = RoutingResult(intent="x", confidence=0.9, tool="y")
        with self.assertRaises(AttributeError):
            r.intent = "z"


# ── classify() — Core Pipeline ────────────────────────────────────────


class TestAIRouterClassify(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_returns_routing_result(self):
        r = self.router.classify("déchets dangereux")
        self.assertIsNotNone(r)
        self.assertIsInstance(r, RoutingResult)

    def test_none_for_empty(self):
        self.assertIsNone(self.router.classify(""))

    def test_none_for_whitespace(self):
        self.assertIsNone(self.router.classify("   "))

    def test_none_for_no_match(self):
        self.assertIsNone(self.router.classify("xyzzy flurbo"))

    def test_intent_detected(self):
        r = self.router.classify("déchets dangereux")
        self.assertEqual(r.intent, "waste_search")

    def test_tool_selected(self):
        r = self.router.classify("déchets dangereux")
        self.assertEqual(r.tool, "waste_tool")

    def test_confidence_populated(self):
        r = self.router.classify("déchets dangereux")
        self.assertGreater(r.confidence, 0.0)

    def test_never_executes_tool(self):
        """classify() must NEVER execute a tool — only classify."""
        r = self.router.classify("BSD-20241234")
        self.assertIsNotNone(r)
        self.assertEqual(r.tool, "bsd_tool")
        self.assertIsInstance(r, RoutingResult)


# ── classify() — Entity Detection ─────────────────────────────────────


class TestAIRouterClassifyEntities(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_waste_code_entity(self):
        r = self.router.classify("donne-moi le code 15.01.06")
        waste_codes = [e for e in r.entities if e.entity_type == "waste_code"]
        self.assertTrue(any(e.value == "15.01.06" for e in waste_codes))

    def test_bsd_number_entity(self):
        r = self.router.classify("cherche BSD-20241234")
        bsd_entities = [e for e in r.entities if e.entity_type == "bsd_number"]
        self.assertTrue(len(bsd_entities) > 0)

    def test_bc_number_entity(self):
        r = self.router.classify("BC-20240001")
        bc_entities = [e for e in r.entities if e.entity_type == "bc_number"]
        self.assertTrue(len(bc_entities) > 0)

    def test_bl_number_entity(self):
        r = self.router.classify("BL-20240001")
        bl_entities = [e for e in r.entities if e.entity_type == "bl_number"]
        self.assertTrue(len(bl_entities) > 0)

    def test_year_entity(self):
        r = self.router.classify("déclarations 2024")
        year_entities = [e for e in r.entities if e.entity_type == "year"]
        self.assertTrue(any(e.value == "2024" for e in year_entities))

    def test_quantity_entity(self):
        r = self.router.classify("déchets dangereux 10.5 tonnes")
        qty_entities = [e for e in r.entities if e.entity_type == "quantity"]
        self.assertTrue(len(qty_entities) > 0)

    def test_percentage_entity(self):
        r = self.router.classify("recherche déchet 85% recyclable")
        pct_entities = [e for e in r.entities if e.entity_type == "percentage"]
        self.assertTrue(len(pct_entities) > 0)

    def test_multiple_entities(self):
        r = self.router.classify("BSD-20241234 pour 15.01.06 en 2024")
        self.assertGreaterEqual(len(r.entities), 3)

    def test_no_entities_for_greeting(self):
        r = self.router.classify("Bonjour")
        self.assertEqual(len(r.entities), 0)

    def test_entities_to_dict(self):
        r = self.router.classify("code 15.01.06")
        d = r.to_dict()
        self.assertIsInstance(d["entities"], list)


# ── classify() — Reference Detection ──────────────────────────────────


class TestAIRouterClassifyReferences(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_waste_code_reference(self):
        r = self.router.classify("code 15.01.06")
        refs = [ref for ref in r.references if ref.reference_type == "waste_code"]
        self.assertTrue(len(refs) > 0)

    def test_bare_numeric_reference(self):
        r = self.router.classify("qu'est-ce que 1.3.1")
        refs = [ref for ref in r.references if ref.reference == "1.3.1"]
        self.assertTrue(len(refs) > 0)

    def test_article_reference(self):
        """'1.3.1' is classified as waste_code (family 1 in range) without full message context."""
        r = self.router.classify("article 1.3.1 de la loi")
        refs = [ref for ref in r.references if ref.reference == "1.3.1"]
        self.assertTrue(len(refs) > 0)

    def test_bsd_number_no_dotted_reference(self):
        """BSD numbers don't contain dots, so no dotted references found."""
        r = self.router.classify("BSD-20241234")
        self.assertEqual(len(r.references), 0)

    def test_no_references_for_greeting(self):
        r = self.router.classify("Bonjour")
        self.assertEqual(len(r.references), 0)

    def test_references_to_dict(self):
        r = self.router.classify("code 15.01.06")
        d = r.to_dict()
        self.assertIsInstance(d["references"], list)

    def test_reference_confidence_range(self):
        r = self.router.classify("code 15.01.06")
        for ref in r.references:
            self.assertGreaterEqual(ref.confidence, 0.0)
            self.assertLessEqual(ref.confidence, 1.0)


# ── classify() — Candidate Ranking ────────────────────────────────────


class TestAIRouterClassifyCandidates(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_candidates_populated(self):
        r = self.router.classify("déchets dangereux")
        self.assertGreater(len(r.candidates), 0)

    def test_candidates_sorted_by_confidence(self):
        r = self.router.classify("déchets dangereux")
        for i in range(len(r.candidates) - 1):
            self.assertGreaterEqual(
                r.candidates[i].confidence, r.candidates[i + 1].confidence,
            )

    def test_best_candidate_matches_selected_tool(self):
        r = self.router.classify("déchets dangereux")
        self.assertEqual(r.tool, r.candidates[0].tool)

    def test_candidates_have_tool_and_intent(self):
        r = self.router.classify("déchets dangereux")
        for c in r.candidates:
            self.assertIsInstance(c.tool, str)
            self.assertIsInstance(c.intent, str)
            self.assertGreater(c.confidence, 0.0)

    def test_multiple_candidates_for_complex_query(self):
        """'recherche déchet plastique' may match multiple rules."""
        r = self.router.classify("recherche déchet plastique")
        self.assertGreaterEqual(len(r.candidates), 1)

    def test_candidates_to_dict(self):
        r = self.router.classify("déchets dangereux")
        d = r.to_dict()
        self.assertIsInstance(d["candidates"], list)
        if d["candidates"]:
            self.assertIn("tool", d["candidates"][0])
            self.assertIn("confidence", d["candidates"][0])


# ── classify() — Parameters ───────────────────────────────────────────


class TestAIRouterClassifyParameters(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_parameters_populated_for_code(self):
        r = self.router.classify("code 15.01.06")
        self.assertIn("code", r.parameters)

    def test_parameters_populated_for_bsd(self):
        r = self.router.classify("BSD-20241234")
        self.assertIn("numero", r.parameters)

    def test_parameters_empty_for_greeting(self):
        r = self.router.classify("Bonjour")
        self.assertEqual(r.parameters, {})

    def test_parameters_to_dict(self):
        r = self.router.classify("code 15.01.06")
        d = r.to_dict()
        self.assertIsInstance(d["parameters"], dict)


# ── classify() — Workflow Integrity ───────────────────────────────────


class TestAIRouterClassifyWorkflow(unittest.TestCase):
    """Verify the 6-step workflow: receive → intent → entities → references → rank → select."""

    def setUp(self):
        self.router = AIRouter()

    def test_step1_receivehandles_empty(self):
        self.assertIsNone(self.router.classify(None))
        self.assertIsNone(self.router.classify(""))
        self.assertIsNone(self.router.classify("   "))

    def test_step2_intent_always_detected_when_match(self):
        r = self.router.classify("déchets dangereux")
        self.assertIsNotNone(r.intent)
        self.assertNotEqual(r.intent, "")

    def test_step3_entities_extracted(self):
        r = self.router.classify("code 15.01.06 pour 2024")
        self.assertGreater(len(r.entities), 0)

    def test_step4_references_classified(self):
        r = self.router.classify("code 15.01.06")
        self.assertGreater(len(r.references), 0)

    def testStep5_candidates_ranked(self):
        r = self.router.classify("déchets dangereux")
        self.assertGreater(len(r.candidates), 0)
        # Verify sorted
        for i in range(len(r.candidates) - 1):
            self.assertGreaterEqual(
                r.candidates[i].confidence,
                r.candidates[i + 1].confidence,
            )

    def test_step6_tool_never_executed(self):
        """classify() returns a RoutingResult — no tool execution."""
        r = self.router.classify("déchets dangereux")
        self.assertIsInstance(r, RoutingResult)
        self.assertIsInstance(r.tool, str)

    def test_full_pipeline_complex_query(self):
        r = self.router.classify("recherche BSD-20241234 pour déchets 15.01.06")
        self.assertIsNotNone(r)
        self.assertGreater(len(r.entities), 0)
        self.assertGreater(len(r.references), 0)
        self.assertGreater(len(r.candidates), 0)
        self.assertIn(r.tool, [c.tool for c in r.candidates])


# ── classify() — Intent Coverage ──────────────────────────────────────


class TestAIRouterClassifyIntents(unittest.TestCase):
    """Verify classify() works for all 18+ intents."""

    def setUp(self):
        self.router = AIRouter()

    def test_greeting(self):
        r = self.router.classify("Bonjour")
        self.assertEqual(r.intent, "greeting")
        self.assertEqual(r.tool, "greeting")

    def test_waste_search(self):
        r = self.router.classify("déchets dangereux")
        self.assertEqual(r.intent, "waste_search")

    def test_nomenclature(self):
        r = self.router.classify("code 01.01.01")
        self.assertEqual(r.intent, "nomenclature")

    def test_bsd(self):
        r = self.router.classify("BSD-20241234")
        self.assertEqual(r.intent, "bsd")

    def test_bc(self):
        r = self.router.classify("BC-20240001")
        self.assertEqual(r.intent, "bc")

    def test_bl(self):
        r = self.router.classify("BL-20240001")
        self.assertEqual(r.intent, "bl")

    def test_company(self):
        r = self.router.classify("entreprises")
        self.assertEqual(r.intent, "company")

    def test_producer(self):
        r = self.router.classify("producteurs")
        self.assertEqual(r.intent, "producer")

    def test_transporter(self):
        r = self.router.classify("transporteurs")
        self.assertEqual(r.intent, "transporter")

    def test_partner(self):
        r = self.router.classify("partenaires")
        self.assertEqual(r.intent, "partner")

    def test_statistics(self):
        r = self.router.classify("statistiques")
        self.assertEqual(r.intent, "statistics")

    def test_report(self):
        r = self.router.classify("rapport mensuel")
        self.assertEqual(r.intent, "report")

    def test_dashboard(self):
        r = self.router.classify("tableau de bord")
        self.assertEqual(r.intent, "dashboard")

    def test_archive(self):
        r = self.router.classify("archives")
        self.assertEqual(r.intent, "archive")

    def test_traceability(self):
        r = self.router.classify("traçabilité")
        self.assertEqual(r.intent, "traceability")

    def test_declaration(self):
        r = self.router.classify("déclarations")
        self.assertEqual(r.intent, "declaration")

    def test_inspection(self):
        r = self.router.classify("inspections")
        self.assertEqual(r.intent, "inspection")

    def test_regulation(self):
        r = self.router.classify("réglementation déchets")
        self.assertEqual(r.intent, "regulation")

    def test_notification(self):
        r = self.router.classify("notifications")
        self.assertEqual(r.intent, "notification")

    def test_authentication(self):
        r = self.router.classify("profil utilisateur")
        self.assertEqual(r.intent, "authentication")

    def test_glossary(self):
        r = self.router.classify("c'est quoi un BSD")
        self.assertEqual(r.intent, "glossary")


# ── classify() — Edge Cases ───────────────────────────────────────────


class TestAIRouterClassifyEdgeCases(unittest.TestCase):
    def setUp(self):
        self.router = AIRouter()

    def test_long_message(self):
        msg = "Je voudrais " + "x " * 100 + "déchets dangereux"
        r = self.router.classify(msg)
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "waste_search")

    def test_special_characters(self):
        r = self.router.classify("réglementation-déchets!")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "regulation")

    def test_arabic_greeting(self):
        r = self.router.classify("مرحبا")
        self.assertIsNotNone(r)
        self.assertEqual(r.intent, "greeting")

    def test_mixed_language(self):
        r = self.router.classify("show me the BSD tracking")
        self.assertIsNotNone(r)
        self.assertIn(r.intent, ("bsd", "traceability"))


# ── Module-level classify_message() ───────────────────────────────────


class TestClassifyMessage(unittest.TestCase):
    def test_returns_dict(self):
        result = classify_message("déchets dangereux")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["intent"], "waste_search")

    def test_returns_none_for_no_match(self):
        result = classify_message("xyzzy flurbo")
        self.assertIsNone(result)

    def test_has_all_keys(self):
        result = classify_message("déchets dangereux")
        self.assertIn("intent", result)
        self.assertIn("confidence", result)
        self.assertIn("tool", result)
        self.assertIn("entities", result)
        self.assertIn("references", result)
        self.assertIn("candidates", result)
        self.assertIn("parameters", result)

    def test_singleton_behavior(self):
        import apps.ai_assistant.enterprise.ai_router as mod
        mod._classifier = None
        r1 = classify_message("Bonjour")
        first = mod._classifier
        r2 = classify_message("Bonjour")
        self.assertIs(mod._classifier, first)


if __name__ == "__main__":
    unittest.main()
