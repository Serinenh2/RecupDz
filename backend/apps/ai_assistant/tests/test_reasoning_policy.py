"""
Tests for AIReasoningPolicy — framework-independent deterministic reasoning.

Covers all 11 responsibilities, edge cases, integration with real modules,
data contract serialization, and the full analyze() pipeline.
"""

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from apps.ai_assistant.enterprise.reasoning_policy import (
    AIReasoningPolicy,
    BusinessKnowledgeDirective,
    ClarificationDecision,
    ConfidenceReport,
    CONFIDENCE_THRESHOLD,
    EntityAnalysis,
    IntentAnalysis,
    LanguageInfo,
    ParameterReport,
    ReasoningResult,
    ReasoningStep,
    ResponseValidation,
    ToolDecision,
    WEIGHT_ENTITIES,
    WEIGHT_INTENT,
    WEIGHT_REFERENCES,
    WEIGHT_SEARCH,
    WEIGHT_TOOL_SELECTION,
)


# ════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════


def _make_policy() -> AIReasoningPolicy:
    """Create a policy with mocked dependencies."""
    policy = AIReasoningPolicy()
    policy._router = MagicMock()
    policy._ref_classifier = MagicMock()
    policy._param_validator = MagicMock()
    return policy


def _mock_routing(
    intent: str = "waste_search",
    tool: str = "waste_tool",
    confidence: float = 0.95,
    parameters: dict = None,
    candidates=None,
):
    """Create a mock RoutingResult."""
    mock = MagicMock()
    mock.intent = intent
    mock.tool = tool
    mock.confidence = confidence
    mock.parameters = parameters or {}
    mock.candidates = candidates or []
    return mock


def _mock_validation(valid: bool = True, missing: list = None):
    """Create a mock ValidationResult."""
    mock = MagicMock()
    mock.valid = valid
    mock.missing_parameters = missing or []
    return mock


def _mock_ref_result(ref_type: str = "waste_code", conf: float = 0.9):
    """Create a mock ClassificationResult."""
    mock = MagicMock()
    mock.reference_type = ref_type
    mock.confidence = conf
    return mock


# ════════════════════════════════════════════════════════════════════════
# Data Contract Tests
# ════════════════════════════════════════════════════════════════════════


class TestReasoningStep(unittest.TestCase):
    def test_to_dict_basic(self):
        step = ReasoningStep(
            step="1_test",
            input_summary="hello",
            output_summary="ok",
            confidence=0.9,
            reasoning="test",
        )
        d = step.to_dict()
        self.assertEqual(d["step"], "1_test")
        self.assertEqual(d["confidence"], 0.9)
        self.assertNotIn("elapsed_ms", d)
        self.assertNotIn("details", d)

    def test_to_dict_with_optional(self):
        step = ReasoningStep(
            step="1_test",
            input_summary="hello",
            output_summary="ok",
            confidence=0.9,
            reasoning="test",
            elapsed_ms=1.234,
            details={"key": "value"},
        )
        d = step.to_dict()
        self.assertAlmostEqual(d["elapsed_ms"], 1.23, places=1)
        self.assertEqual(d["details"]["key"], "value")


class TestLanguageInfo(unittest.TestCase):
    def test_to_dict_basic(self):
        li = LanguageInfo(language="fr", confidence=0.9)
        d = li.to_dict()
        self.assertEqual(d["language"], "fr")
        self.assertAlmostEqual(d["confidence"], 0.9, places=3)
        self.assertNotIn("is_bilingual", d)
        self.assertNotIn("detected_keywords", d)

    def test_to_dict_bilingual(self):
        li = LanguageInfo(
            language="fr", confidence=0.8,
            is_bilingual=True, detected_keywords=["bonjour", "hello"],
        )
        d = li.to_dict()
        self.assertTrue(d["is_bilingual"])
        self.assertEqual(len(d["detected_keywords"]), 2)


class TestIntentAnalysis(unittest.TestCase):
    def test_to_dict_basic(self):
        ia = IntentAnalysis(intent="waste_search", tool="waste_tool", confidence=0.95)
        d = ia.to_dict()
        self.assertEqual(d["intent"], "waste_search")
        self.assertNotIn("is_greeting", d)
        self.assertNotIn("candidates", d)

    def test_to_dict_greeting(self):
        ia = IntentAnalysis(
            intent="greeting", tool="greeting",
            confidence=1.0, is_greeting=True,
        )
        d = ia.to_dict()
        self.assertTrue(d["is_greeting"])


class TestEntityAnalysis(unittest.TestCase):
    def test_has_entities(self):
        ea = EntityAnalysis(waste_codes=["15.01.06"], total_entities=1)
        self.assertTrue(ea.has_entities)

    def test_no_entities(self):
        ea = EntityAnalysis()
        self.assertFalse(ea.has_entities)

    def test_to_dict_empty(self):
        d = EntityAnalysis().to_dict()
        self.assertEqual(d["total_entities"], 0)
        self.assertNotIn("waste_codes", d)

    def test_to_dict_with_data(self):
        ea = EntityAnalysis(
            waste_codes=["15.01.06"],
            bsd_numbers=["BSD-2024-0001"],
            total_entities=2,
        )
        d = ea.to_dict()
        self.assertEqual(d["total_entities"], 2)
        self.assertIn("15.01.06", d["waste_codes"])


class TestConfidenceReport(unittest.TestCase):
    def test_to_dict(self):
        cr = ConfidenceReport(
            overall=0.85, passes_threshold=True,
            breakdown={"intent": 0.95}, weights={"intent": 0.30},
        )
        d = cr.to_dict()
        self.assertTrue(d["passes_threshold"])
        self.assertIn("threshold", d)
        self.assertAlmostEqual(d["breakdown"]["intent"], 0.95, places=3)


class TestBusinessKnowledgeDirective(unittest.TestCase):
    def test_defaults(self):
        bk = BusinessKnowledgeDirective()
        self.assertTrue(bk.must_search_business_first)
        self.assertTrue(bk.company_data_before_model)
        self.assertTrue(bk.rag_always_run)
        self.assertTrue(bk.search_before_llm)

    def test_to_dict(self):
        d = BusinessKnowledgeDirective().to_dict()
        self.assertTrue(d["must_search_business_first"])


class TestToolDecision(unittest.TestCase):
    def test_to_dict_basic(self):
        td = ToolDecision(tool="waste_tool", action="search", confidence=0.9)
        d = td.to_dict()
        self.assertEqual(d["tool"], "waste_tool")
        self.assertNotIn("needs_search_fallback", d)
        self.assertNotIn("candidate_count", d)

    def test_to_dict_with_fallback(self):
        td = ToolDecision(
            tool="none", confidence=0.1, needs_search_fallback=True,
            candidate_count=3,
        )
        d = td.to_dict()
        self.assertTrue(d["needs_search_fallback"])
        self.assertEqual(d["candidate_count"], 3)


class TestParameterReport(unittest.TestCase):
    def test_to_dict_valid(self):
        pr = ParameterReport(valid=True, tool_name="waste_tool", action="search")
        d = pr.to_dict()
        self.assertTrue(d["valid"])
        self.assertNotIn("missing", d)

    def test_to_dict_invalid(self):
        pr = ParameterReport(
            valid=False, tool_name="waste_tool", action="search",
            missing=[{"name": "query"}],
        )
        d = pr.to_dict()
        self.assertFalse(d["valid"])
        self.assertEqual(len(d["missing"]), 1)


class TestResponseValidation(unittest.TestCase):
    def test_valid(self):
        rv = ResponseValidation(valid=True)
        d = rv.to_dict()
        self.assertTrue(d["valid"])
        self.assertNotIn("errors", d)

    def test_invalid(self):
        rv = ResponseValidation(valid=False, errors=["err1"])
        d = rv.to_dict()
        self.assertFalse(d["valid"])
        self.assertEqual(len(d["errors"]), 1)


class TestClarificationDecision(unittest.TestCase):
    def test_not_needed(self):
        cd = ClarificationDecision(needed=False)
        d = cd.to_dict()
        self.assertFalse(d["needed"])

    def test_needed(self):
        cd = ClarificationDecision(
            needed=True, reason="low_confidence",
            question="Pouvez-vous préciser ?",
        )
        d = cd.to_dict()
        self.assertTrue(d["needed"])
        self.assertEqual(d["reason"], "low_confidence")
        self.assertIn("préciser", d["question"])


class TestReasoningResult(unittest.TestCase):
    def _make_result(self, **overrides):
        defaults = dict(
            message="test",
            steps=[],
            language=LanguageInfo(),
            intent=IntentAnalysis(),
            entities=EntityAnalysis(),
            confidence=ConfidenceReport(),
            business_knowledge=BusinessKnowledgeDirective(),
            tool_decision=ToolDecision(),
            parameter_report=ParameterReport(),
            response_validation=ResponseValidation(),
            clarification=ClarificationDecision(),
        )
        defaults.update(overrides)
        return ReasoningResult(**defaults)

    def test_should_proceed_all_pass(self):
        r = self._make_result(
            confidence=ConfidenceReport(overall=0.9, passes_threshold=True),
            tool_decision=ToolDecision(tool="waste_tool"),
            parameter_report=ParameterReport(valid=True),
            clarification=ClarificationDecision(needed=False),
        )
        self.assertTrue(r.should_proceed)
        self.assertFalse(r.needs_clarification)
        self.assertEqual(r.tool_name, "waste_tool")

    def test_should_proceed_low_confidence(self):
        r = self._make_result(
            confidence=ConfidenceReport(overall=0.5, passes_threshold=False),
            tool_decision=ToolDecision(tool="waste_tool"),
            parameter_report=ParameterReport(valid=True),
            clarification=ClarificationDecision(needed=False),
        )
        self.assertFalse(r.should_proceed)

    def test_should_proceed_clarification_needed(self):
        r = self._make_result(
            confidence=ConfidenceReport(overall=0.9, passes_threshold=True),
            tool_decision=ToolDecision(tool="waste_tool"),
            parameter_report=ParameterReport(valid=True),
            clarification=ClarificationDecision(needed=True),
        )
        self.assertFalse(r.should_proceed)
        self.assertTrue(r.needs_clarification)

    def test_should_proceed_no_tool(self):
        r = self._make_result(
            confidence=ConfidenceReport(overall=0.9, passes_threshold=True),
            tool_decision=ToolDecision(tool="none"),
            parameter_report=ParameterReport(valid=True),
            clarification=ClarificationDecision(needed=False),
        )
        self.assertFalse(r.should_proceed)

    def test_should_proceed_invalid_params(self):
        r = self._make_result(
            confidence=ConfidenceReport(overall=0.9, passes_threshold=True),
            tool_decision=ToolDecision(tool="waste_tool"),
            parameter_report=ParameterReport(valid=False),
            clarification=ClarificationDecision(needed=False),
        )
        self.assertFalse(r.should_proceed)

    def test_to_dict(self):
        r = self._make_result(message="test msg")
        d = r.to_dict()
        self.assertEqual(d["message"], "test msg")
        self.assertIn("steps", d)
        self.assertIn("language", d)
        self.assertIn("intent", d)
        self.assertIn("should_proceed", d)

    def test_tool_decision_properties(self):
        r = self._make_result(
            tool_decision=ToolDecision(
                tool="waste_tool", action="search",
                parameters={"query": "test"},
            ),
        )
        self.assertEqual(r.tool_name, "waste_tool")
        self.assertEqual(r.action, "search")
        self.assertEqual(r.parameters["query"], "test")

    def test_parameters_returns_copy(self):
        r = self._make_result(
            tool_decision=ToolDecision(parameters={"query": "x"}),
        )
        p = r.parameters
        p["query"] = "modified"
        self.assertEqual(r.parameters["query"], "x")

    def test_total_elapsed_ms(self):
        r = self._make_result(total_elapsed_ms=42.5)
        d = r.to_dict()
        self.assertAlmostEqual(d["total_elapsed_ms"], 42.5, places=1)


# ════════════════════════════════════════════════════════════════════════
# Step 1: User Understanding
# ════════════════════════════════════════════════════════════════════════


class TestStep1UserUnderstanding(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_normal_message(self):
        step, normalised = self.policy._step_user_understanding(
            "Bonjour le monde", {},
        )
        self.assertEqual(step.step, "1_user_understanding")
        self.assertEqual(step.confidence, 1.0)
        self.assertEqual(normalised, "bonjour le monde")

    def test_empty_message(self):
        step, normalised = self.policy._step_user_understanding("", {})
        self.assertEqual(step.confidence, 0.0)
        self.assertIn("EMPTY", step.output_summary)

    def test_none_message(self):
        step, normalised = self.policy._step_user_understanding(None, {})
        self.assertEqual(step.confidence, 0.0)

    def test_whitespace_normalisation(self):
        _, normalised = self.policy._step_user_understanding(
            "  bonjour   le    monde  ", {},
        )
        self.assertEqual(normalised, "bonjour le monde")

    def test_word_count(self):
        step, _ = self.policy._step_user_understanding(
            "un deux trois", {},
        )
        self.assertEqual(step.details["word_count"], 3)

    def test_char_count(self):
        step, _ = self.policy._step_user_understanding("abc", {})
        self.assertEqual(step.details["char_count"], 3)

    def test_context_ignored(self):
        _, normalised = self.policy._step_user_understanding(
            "hello", {"foo": "bar"},
        )
        self.assertEqual(normalised, "hello")


# ════════════════════════════════════════════════════════════════════════
# Step 2: Language Detection
# ════════════════════════════════════════════════════════════════════════


class TestStep2LanguageDetection(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_french(self):
        step, lang = self.policy._step_language_detection(
            "Quels sont les déchets dangereux ?", "quels sont les déchets dangereux ?",
        )
        self.assertEqual(lang.language, "fr")
        self.assertGreater(lang.confidence, 0.5)

    def test_english(self):
        step, lang = self.policy._step_language_detection(
            "What is the waste classification?", "what is the waste classification?",
        )
        self.assertEqual(lang.language, "en")
        self.assertGreater(lang.confidence, 0.5)

    def test_arabic(self):
        step, lang = self.policy._step_language_detection(
            "ما هو التصنيف؟", "ما هو التصنيف؟",
        )
        self.assertEqual(lang.language, "ar")

    def test_unknown(self):
        step, lang = self.policy._step_language_detection("12345", "12345")
        self.assertEqual(lang.language, "unknown")
        self.assertEqual(lang.confidence, 0.0)

    def test_bilingual(self):
        _, lang = self.policy._step_language_detection(
            "Bonjour comment what is this",
            "bonjour comment what is this",
        )
        self.assertTrue(lang.is_bilingual)

    def test_keywords_detected(self):
        _, lang = self.policy._step_language_detection(
            "quels déchets dangereux", "quels déchets dangereux",
        )
        self.assertGreater(len(lang.detected_keywords), 0)

    def test_french_stronger_than_english(self):
        _, lang = self.policy._step_language_detection(
            "quels sont les déchets et what is the regulation",
            "quels sont les déchets et what is the regulation",
        )
        self.assertEqual(lang.language, "fr")

    def test_step_name(self):
        step, _ = self.policy._step_language_detection("bonjour", "bonjour")
        self.assertEqual(step.step, "2_language_detection")


# ════════════════════════════════════════════════════════════════════════
# Step 3: Intent Detection
# ════════════════════════════════════════════════════════════════════════


class TestStep3IntentDetection(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_greeting(self):
        step, intent = self.policy._step_intent_detection(
            "Bonjour", "bonjour",
        )
        self.assertEqual(intent.intent, "greeting")
        self.assertTrue(intent.is_greeting)
        self.assertEqual(intent.confidence, 1.0)

    def test_greeting_english(self):
        _, intent = self.policy._step_intent_detection("Hello", "hello")
        self.assertTrue(intent.is_greeting)

    def test_greeting_salut(self):
        _, intent = self.policy._step_intent_detection("Salut !", "salut !")
        self.assertTrue(intent.is_greeting)

    def test_waste_search(self):
        self.policy._router.classify.return_value = _mock_routing(
            intent="waste_search", tool="waste_tool", confidence=0.95,
        )
        step, intent = self.policy._step_intent_detection(
            "Quels sont les déchets dangereux ?",
            "quels sont les déchets dangereux ?",
        )
        self.assertEqual(intent.intent, "waste_search")
        self.assertEqual(intent.tool, "waste_tool")
        self.assertFalse(intent.is_greeting)

    def test_question_detection(self):
        step, intent = self.policy._step_intent_detection(
            "Qu'est-ce qu'un BSD ?", "qu'est-ce qu'un bsd ?",
        )
        self.assertTrue(intent.is_question)

    def test_question_mark(self):
        _, intent = self.policy._step_intent_detection(
            "Déchets dangereux ?", "déchets dangereux ?",
        )
        self.assertTrue(intent.is_question)

    def test_no_router_fallback_question(self):
        self.policy._router.classify.return_value = None
        _, intent = self.policy._step_intent_detection(
            "What is this?", "what is this?",
        )
        self.assertEqual(intent.intent, "question")
        self.assertEqual(intent.tool, "none")

    def test_no_router_fallback_unknown(self):
        self.policy._router.classify.return_value = None
        _, intent = self.policy._step_intent_detection(
            "xyz123", "xyz123",
        )
        self.assertEqual(intent.intent, "unknown")

    def test_router_exception_fallback(self):
        self.policy._router.classify.side_effect = RuntimeError("fail")
        _, intent = self.policy._step_intent_detection(
            "test", "test",
        )
        self.assertIn(intent.intent, ("question", "unknown"))

    def test_candidates_preserved(self):
        c1 = MagicMock()
        c1.to_dict.return_value = {"tool": "waste_tool", "confidence": 0.95}
        self.policy._router.classify.return_value = _mock_routing(
            candidates=[c1],
        )
        _, intent = self.policy._step_intent_detection("test", "test")
        self.assertEqual(len(intent.candidates), 1)

    def test_step_name(self):
        self.policy._router.classify.return_value = _mock_routing()
        step, _ = self.policy._step_intent_detection("test", "test")
        self.assertEqual(step.step, "3_intent_detection")


# ════════════════════════════════════════════════════════════════════════
# Step 4: Entity Extraction
# ════════════════════════════════════════════════════════════════════════


class TestStep4EntityExtraction(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_waste_code(self):
        step, entities = self.policy._step_entity_extraction(
            "Code déchet 15.01.06", {},
        )
        self.assertIn("15.01.06", entities.waste_codes)
        self.assertEqual(entities.total_entities, 1)

    def test_bsd_number(self):
        _, entities = self.policy._step_entity_extraction(
            "BSD-2024-0001", {},
        )
        self.assertEqual(len(entities.bsd_numbers), 1)

    def test_bc_number(self):
        _, entities = self.policy._step_entity_extraction("BC-2024-55", {})
        self.assertEqual(len(entities.bc_numbers), 1)

    def test_bl_number(self):
        _, entities = self.policy._step_entity_extraction("BL-2024-12", {})
        self.assertEqual(len(entities.bl_numbers), 1)

    def test_date(self):
        _, entities = self.policy._step_entity_extraction(
            "Le 15/03/2024", {},
        )
        self.assertGreater(len(entities.dates), 0)

    def test_quantity(self):
        _, entities = self.policy._step_entity_extraction(
            "5.5 tonnes", {},
        )
        self.assertGreater(len(entities.quantities), 0)

    def test_percentage(self):
        _, entities = self.policy._step_entity_extraction(
            "33.3%", {},
        )
        self.assertGreater(len(entities.percentages), 0)

    def test_email(self):
        _, entities = self.policy._step_entity_extraction(
            "Contact: test@example.com", {},
        )
        self.assertIn("test@example.com", entities.emails)

    def test_agrement(self):
        _, entities = self.policy._step_entity_extraction(
            "Agréement AGR-12345", {},
        )
        self.assertGreater(len(entities.agrement_numbers), 0)

    def test_year(self):
        _, entities = self.policy._step_entity_extraction(
            "Année 2024", {},
        )
        self.assertIn("2024", entities.years)

    def test_no_entities(self):
        _, entities = self.policy._step_entity_extraction("Bonjour", {})
        self.assertFalse(entities.has_entities)
        self.assertEqual(entities.total_entities, 0)

    def test_multiple_entities(self):
        _, entities = self.policy._step_entity_extraction(
            "BSD-2024-0001 code 15.01.06 en 2024", {},
        )
        self.assertGreaterEqual(entities.total_entities, 2)

    def test_step_name(self):
        step, _ = self.policy._step_entity_extraction("test", {})
        self.assertEqual(step.step, "4_entity_extraction")


# ════════════════════════════════════════════════════════════════════════
# Step 5: Reference Classification
# ════════════════════════════════════════════════════════════════════════


class TestStep5ReferenceClassification(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_waste_code_classification(self):
        entities = EntityAnalysis(
            waste_codes=["15.01.06"], total_entities=1,
        )
        self.policy._ref_classifier.classify.return_value = (
            _mock_ref_result("waste_code", 0.95)
        )
        step, result = self.policy._step_reference_classification(
            "code 15.01.06", entities,
        )
        self.assertEqual(len(result.classified_references), 1)
        self.assertEqual(
            result.classified_references[0]["reference_type"], "waste_code",
        )

    def test_bsd_number_classification(self):
        entities = EntityAnalysis(
            bsd_numbers=["BSD-2024-0001"], total_entities=1,
        )
        _, result = self.policy._step_reference_classification(
            "BSD-2024-0001", entities,
        )
        self.assertEqual(len(result.classified_references), 1)
        self.assertEqual(
            result.classified_references[0]["reference_type"], "bsd_number",
        )

    def test_bc_number_classification(self):
        entities = EntityAnalysis(bc_numbers=["BC-2024-55"], total_entities=1)
        _, result = self.policy._step_reference_classification(
            "BC-2024-55", entities,
        )
        self.assertEqual(len(result.classified_references), 1)
        self.assertEqual(
            result.classified_references[0]["reference_type"], "bc_number",
        )

    def test_bl_number_classification(self):
        entities = EntityAnalysis(bl_numbers=["BL-2024-12"], total_entities=1)
        _, result = self.policy._step_reference_classification(
            "BL-2024-12", entities,
        )
        self.assertEqual(len(result.classified_references), 1)
        self.assertEqual(
            result.classified_references[0]["reference_type"], "bl_number",
        )

    def test_agrement_classification(self):
        entities = EntityAnalysis(
            agrement_numbers=["AGR-12345"], total_entities=1,
        )
        _, result = self.policy._step_reference_classification(
            "AGR-12345", entities,
        )
        self.assertEqual(len(result.classified_references), 1)

    def test_no_entities(self):
        entities = EntityAnalysis()
        step, result = self.policy._step_reference_classification(
            "bonjour", entities,
        )
        self.assertEqual(len(result.classified_references), 0)

    def test_multiple_references(self):
        entities = EntityAnalysis(
            waste_codes=["15.01.06", "20.01.01"],
            bsd_numbers=["BSD-2024-0001"],
            total_entities=3,
        )
        self.policy._ref_classifier.classify.return_value = (
            _mock_ref_result("waste_code", 0.9)
        )
        _, result = self.policy._step_reference_classification(
            "codes 15.01.06 20.01.01 BSD-2024-0001", entities,
        )
        self.assertEqual(len(result.classified_references), 3)

    def test_classifier_exception_fallback(self):
        entities = EntityAnalysis(
            waste_codes=["15.01.06"], total_entities=1,
        )
        self.policy._ref_classifier.classify.side_effect = (
            RuntimeError("fail")
        )
        _, result = self.policy._step_reference_classification(
            "code 15.01.06", entities,
        )
        self.assertEqual(len(result.classified_references), 1)
        self.assertEqual(
            result.classified_references[0]["reference_type"], "waste_code",
        )

    def test_step_name(self):
        step, _ = self.policy._step_reference_classification(
            "test", EntityAnalysis(),
        )
        self.assertEqual(step.step, "5_reference_classification")


# ════════════════════════════════════════════════════════════════════════
# Step 6: Confidence Evaluation
# ════════════════════════════════════════════════════════════════════════


class TestStep6ConfidenceEvaluation(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def _make_intent(self, confidence=0.95, intent="waste_search", tool="waste_tool"):
        return IntentAnalysis(
            intent=intent, tool=tool, confidence=confidence,
        )

    def test_high_confidence(self):
        intent = self._make_intent(confidence=0.95)
        entities = EntityAnalysis(total_entities=0)
        step, report = self.policy._step_confidence_evaluation(
            intent, entities, entities,
        )
        self.assertGreaterEqual(report.overall, 0.7)
        self.assertTrue(report.passes_threshold)

    def test_low_confidence(self):
        intent = self._make_intent(confidence=0.10)
        entities = EntityAnalysis(total_entities=0)
        _, report = self.policy._step_confidence_evaluation(
            intent, entities, entities,
        )
        self.assertLess(report.overall, CONFIDENCE_THRESHOLD)
        self.assertFalse(report.passes_threshold)

    def test_weights_sum_to_one(self):
        intent = self._make_intent()
        entities = EntityAnalysis()
        _, report = self.policy._step_confidence_evaluation(
            intent, entities, entities,
        )
        total_weight = sum(report.weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=6)

    def test_breakdown_keys(self):
        intent = self._make_intent()
        entities = EntityAnalysis()
        _, report = self.policy._step_confidence_evaluation(
            intent, entities, entities,
        )
        self.assertIn("intent", report.breakdown)
        self.assertIn("references", report.breakdown)
        self.assertIn("entities", report.breakdown)
        self.assertIn("search", report.breakdown)
        self.assertIn("tool_selection", report.breakdown)

    def test_weight_constants_sum_to_one(self):
        total = (
            WEIGHT_INTENT + WEIGHT_REFERENCES + WEIGHT_ENTITIES
            + WEIGHT_SEARCH + WEIGHT_TOOL_SELECTION
        )
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_with_references(self):
        intent = self._make_intent(confidence=0.95)
        entities = EntityAnalysis(
            classified_references=[
                {"confidence": 0.9}, {"confidence": 0.85},
            ],
            total_entities=2,
        )
        _, report = self.policy._step_confidence_evaluation(
            intent, entities, entities,
        )
        self.assertGreater(report.breakdown["references"], 0.7)

    def test_step_name(self):
        step, _ = self.policy._step_confidence_evaluation(
            self._make_intent(), EntityAnalysis(), EntityAnalysis(),
        )
        self.assertEqual(step.step, "6_confidence_evaluation")


# ════════════════════════════════════════════════════════════════════════
# Step 7: Business Knowledge Priority
# ════════════════════════════════════════════════════════════════════════


class TestStep7BusinessKnowledgePriority(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_always_business_first(self):
        intent = IntentAnalysis(intent="waste_search", tool="waste_tool")
        conf = ConfidenceReport(overall=0.9, passes_threshold=True)
        step, directive = self.policy._step_business_knowledge_priority(
            intent, conf,
        )
        self.assertTrue(directive.must_search_business_first)
        self.assertTrue(directive.company_data_before_model)
        self.assertTrue(directive.rag_always_run)
        self.assertTrue(directive.search_before_llm)

    def test_confidence_ignored(self):
        """Business priority is always enforced regardless of confidence."""
        intent = IntentAnalysis()
        for conf_val in [0.1, 0.5, 0.99]:
            conf = ConfidenceReport(overall=conf_val, passes_threshold=conf_val >= 0.8)
            _, directive = self.policy._step_business_knowledge_priority(
                intent, conf,
            )
            self.assertTrue(directive.must_search_business_first)

    def test_step_name(self):
        step, _ = self.policy._step_business_knowledge_priority(
            IntentAnalysis(), ConfidenceReport(),
        )
        self.assertEqual(step.step, "7_business_knowledge_priority")


# ════════════════════════════════════════════════════════════════════════
# Step 8: Tool Decision
# ════════════════════════════════════════════════════════════════════════


class TestStep8ToolDecision(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_greeting_no_tool(self):
        intent = IntentAnalysis(
            intent="greeting", tool="greeting",
            confidence=1.0, is_greeting=True,
        )
        step, td = self.policy._step_tool_decision("Bonjour", intent, ConfidenceReport())
        self.assertEqual(td.tool, "greeting")
        self.assertEqual(td.action, "")

    def test_waste_search(self):
        intent = IntentAnalysis(
            intent="waste_search", tool="waste_tool", confidence=0.95,
            candidates=[{"tool": "waste_tool"}],
        )
        _, td = self.policy._step_tool_decision(
            "Quels déchets dangereux ?", intent, ConfidenceReport(overall=0.9),
        )
        self.assertEqual(td.tool, "waste_tool")
        self.assertEqual(td.action, "search")
        self.assertIn("query", td.parameters)

    def test_no_tool_search_fallback(self):
        intent = IntentAnalysis(
            intent="unknown", tool="none", confidence=0.2,
        )
        _, td = self.policy._step_tool_decision("test", intent, ConfidenceReport())
        self.assertEqual(td.tool, "none")
        self.assertTrue(td.needs_search_fallback)

    def test_low_confidence_no_tool(self):
        intent = IntentAnalysis(
            intent="question", tool="none", confidence=0.15,
        )
        _, td = self.policy._step_tool_decision("??", intent, ConfidenceReport())
        self.assertEqual(td.tool, "none")

    def test_query_injected_for_search_tools(self):
        intent = IntentAnalysis(
            intent="glossary", tool="glossaire_tool", confidence=0.9,
        )
        _, td = self.policy._step_tool_decision(
            "Qu'est-ce que le TMB ?", intent, ConfidenceReport(),
        )
        self.assertEqual(td.parameters["query"], "Qu'est-ce que le TMB ?")
        self.assertEqual(td.parameters["action"], "search")

    def test_nomenclature_tool(self):
        intent = IntentAnalysis(
            intent="nomenclature", tool="nomenclature_tool", confidence=0.9,
        )
        _, td = self.policy._step_tool_decision(
            "Code 15.01.06", intent, ConfidenceReport(),
        )
        self.assertEqual(td.tool, "nomenclature_tool")
        self.assertIn("query", td.parameters)

    def test_step_name(self):
        intent = IntentAnalysis(
            intent="waste_search", tool="waste_tool", confidence=0.95,
        )
        step, _ = self.policy._step_tool_decision("test", intent, ConfidenceReport())
        self.assertEqual(step.step, "8_tool_decision")


# ════════════════════════════════════════════════════════════════════════
# Step 9: Parameter Validation
# ════════════════════════════════════════════════════════════════════════


class TestStep9ParameterValidation(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_greeting_skipped(self):
        td = ToolDecision(tool="greeting")
        step, pr = self.policy._step_parameter_validation(td)
        self.assertTrue(pr.valid)

    def test_none_tool_skipped(self):
        td = ToolDecision(tool="none")
        _, pr = self.policy._step_parameter_validation(td)
        self.assertTrue(pr.valid)

    def test_valid_params(self):
        self.policy._param_validator.validate.return_value = _mock_validation(
            valid=True,
        )
        td = ToolDecision(
            tool="waste_tool", action="search",
            parameters={"action": "search", "query": "test"},
        )
        _, pr = self.policy._step_parameter_validation(td)
        self.assertTrue(pr.valid)

    def test_invalid_params(self):
        missing = [MagicMock(name="query", description="Search query")]
        missing[0].to_dict.return_value = {"name": "query", "description": "Search query"}
        self.policy._param_validator.validate.return_value = _mock_validation(
            valid=False, missing=missing,
        )
        td = ToolDecision(
            tool="waste_tool", action="search",
            parameters={"action": "search"},
        )
        _, pr = self.policy._step_parameter_validation(td)
        self.assertFalse(pr.valid)
        self.assertEqual(len(pr.missing), 1)

    def test_validator_exception(self):
        self.policy._param_validator.validate.side_effect = RuntimeError("crash")
        td = ToolDecision(
            tool="waste_tool", action="search",
            parameters={"action": "search", "query": "test"},
        )
        _, pr = self.policy._step_parameter_validation(td)
        self.assertFalse(pr.valid)
        self.assertEqual(pr.missing[0]["name"], "validation_error")

    def test_step_name(self):
        td = ToolDecision(tool="greeting")
        step, _ = self.policy._step_parameter_validation(td)
        self.assertEqual(step.step, "9_parameter_validation")


# ════════════════════════════════════════════════════════════════════════
# Step 10: Response Validation
# ════════════════════════════════════════════════════════════════════════


class TestStep10ResponseValidation(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_greeting_valid(self):
        step, rv = self.policy._step_response_validation(
            "Bonjour",
            IntentAnalysis(is_greeting=True),
            EntityAnalysis(),
            ToolDecision(tool="greeting"),
            ParameterReport(valid=True, tool_name="greeting"),
        )
        self.assertTrue(rv.valid)

    def test_greeting_with_tool_invalid(self):
        _, rv = self.policy._step_response_validation(
            "Bonjour",
            IntentAnalysis(is_greeting=True),
            EntityAnalysis(),
            ToolDecision(tool="waste_tool"),
            ParameterReport(valid=True, tool_name="waste_tool"),
        )
        self.assertFalse(rv.valid)
        self.assertTrue(any("Greeting" in e for e in rv.errors))

    def test_tool_no_params_invalid(self):
        _, rv = self.policy._step_response_validation(
            "test",
            IntentAnalysis(intent="waste_search", tool="waste_tool"),
            EntityAnalysis(),
            ToolDecision(tool="waste_tool", parameters={}),
            ParameterReport(valid=True, tool_name="waste_tool"),
        )
        self.assertFalse(rv.valid)

    def test_param_validation_failed(self):
        _, rv = self.policy._step_response_validation(
            "test",
            IntentAnalysis(intent="waste_search", tool="waste_tool"),
            EntityAnalysis(),
            ToolDecision(tool="waste_tool", parameters={"query": "test"}),
            ParameterReport(valid=False, tool_name="waste_tool"),
        )
        self.assertFalse(rv.valid)

    def test_none_tool_valid(self):
        _, rv = self.policy._step_response_validation(
            "test",
            IntentAnalysis(intent="unknown", tool="none"),
            EntityAnalysis(),
            ToolDecision(tool="none"),
            ParameterReport(valid=True, tool_name="none"),
        )
        self.assertTrue(rv.valid)

    def test_step_name(self):
        step, _ = self.policy._step_response_validation(
            "test", IntentAnalysis(), EntityAnalysis(),
            ToolDecision(), ParameterReport(),
        )
        self.assertEqual(step.step, "10_response_validation")


# ════════════════════════════════════════════════════════════════════════
# Step 11: Clarification Rules
# ════════════════════════════════════════════════════════════════════════


class TestStep11ClarificationRules(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_greeting_no_clarification(self):
        step, cd = self.policy._step_clarification_rules(
            ConfidenceReport(overall=1.0, passes_threshold=True),
            ToolDecision(tool="greeting"),
            ParameterReport(valid=True),
            IntentAnalysis(is_greeting=True),
        )
        self.assertFalse(cd.needed)
        self.assertEqual(cd.reason, "greeting")

    def test_low_confidence_triggers(self):
        _, cd = self.policy._step_clarification_rules(
            ConfidenceReport(overall=0.5, passes_threshold=False),
            ToolDecision(tool="waste_tool"),
            ParameterReport(valid=True),
            IntentAnalysis(intent="waste_search"),
        )
        self.assertTrue(cd.needed)
        self.assertEqual(cd.reason, "low_confidence")
        self.assertIn("préciser", cd.question)

    def test_missing_params_triggers(self):
        _, cd = self.policy._step_clarification_rules(
            ConfidenceReport(overall=0.9, passes_threshold=True),
            ToolDecision(tool="waste_tool"),
            ParameterReport(
                valid=False,
                missing=[{"name": "query"}],
                tool_name="waste_tool",
            ),
            IntentAnalysis(intent="waste_search"),
        )
        self.assertTrue(cd.needed)
        self.assertEqual(cd.reason, "missing_parameters")
        self.assertIn("query", cd.question)

    def test_no_tool_search_fallback_no_clarify(self):
        _, cd = self.policy._step_clarification_rules(
            ConfidenceReport(overall=0.7, passes_threshold=False),
            ToolDecision(tool="none", needs_search_fallback=True),
            ParameterReport(valid=True),
            IntentAnalysis(intent="unknown"),
        )
        self.assertFalse(cd.needed)
        self.assertEqual(cd.reason, "search_fallback")

    def test_all_pass_no_clarify(self):
        _, cd = self.policy._step_clarification_rules(
            ConfidenceReport(overall=0.9, passes_threshold=True),
            ToolDecision(tool="waste_tool"),
            ParameterReport(valid=True, tool_name="waste_tool"),
            IntentAnalysis(intent="waste_search"),
        )
        self.assertFalse(cd.needed)
        self.assertEqual(cd.reason, "all_checks_passed")

    def test_step_name(self):
        step, _ = self.policy._step_clarification_rules(
            ConfidenceReport(passes_threshold=True),
            ToolDecision(),
            ParameterReport(valid=True),
            IntentAnalysis(is_greeting=True),
        )
        self.assertEqual(step.step, "11_clarification_rules")


# ════════════════════════════════════════════════════════════════════════
# Full Pipeline Integration
# ════════════════════════════════════════════════════════════════════════


class TestFullPipeline(unittest.TestCase):
    def setUp(self):
        self.policy = _make_policy()

    def test_waste_search_full_pipeline(self):
        self.policy._router.classify.return_value = _mock_routing(
            intent="waste_search", tool="waste_tool", confidence=0.95,
        )
        self.policy._ref_classifier.classify.return_value = (
            _mock_ref_result("waste_code", 0.9)
        )
        self.policy._param_validator.validate.return_value = _mock_validation(
            valid=True,
        )
        result = self.policy.analyze("Quels sont les déchets dangereux ?")

        self.assertIsInstance(result, ReasoningResult)
        self.assertEqual(len(result.steps), 11)
        self.assertEqual(result.tool_name, "waste_tool")
        self.assertEqual(result.action, "search")
        self.assertTrue(result.should_proceed)
        self.assertFalse(result.needs_clarification)

    def test_greeting_pipeline(self):
        result = self.policy.analyze("Bonjour !")
        self.assertTrue(result.should_proceed)
        self.assertEqual(result.tool_name, "greeting")
        self.assertEqual(len(result.steps), 11)

    def test_empty_message_clarification(self):
        result = self.policy.analyze("")
        self.assertFalse(result.should_proceed)
        self.assertTrue(result.needs_clarification)

    def test_unknown_low_confidence_clarification(self):
        self.policy._router.classify.return_value = _mock_routing(
            intent="unknown", tool="none", confidence=0.1,
        )
        result = self.policy.analyze("xyz123")
        self.assertFalse(result.should_proceed)

    def test_param_validation_failure_clarification(self):
        self.policy._router.classify.return_value = _mock_routing(
            intent="waste_search", tool="waste_tool", confidence=0.95,
        )
        self.policy._ref_classifier.classify.return_value = (
            _mock_ref_result("waste_code", 0.9)
        )
        missing = [MagicMock(name="query")]
        missing[0].to_dict.return_value = {"name": "query"}
        self.policy._param_validator.validate.return_value = _mock_validation(
            valid=False, missing=missing,
        )
        result = self.policy.analyze("Cherche")
        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.clarification.reason, "missing_parameters")

    def test_to_dict_serializable(self):
        self.policy._router.classify.return_value = _mock_routing()
        self.policy._ref_classifier.classify.return_value = (
            _mock_ref_result()
        )
        self.policy._param_validator.validate.return_value = _mock_validation()
        result = self.policy.analyze("test")
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(len(d["steps"]), 11)
        self.assertIn("should_proceed", d)

    def test_all_steps_have_names(self):
        self.policy._router.classify.return_value = _mock_routing()
        self.policy._ref_classifier.classify.return_value = (
            _mock_ref_result()
        )
        self.policy._param_validator.validate.return_value = _mock_validation()
        result = self.policy.analyze("test")
        expected_steps = [
            "1_user_understanding",
            "2_language_detection",
            "3_intent_detection",
            "4_entity_extraction",
            "5_reference_classification",
            "6_confidence_evaluation",
            "7_business_knowledge_priority",
            "8_tool_decision",
            "9_parameter_validation",
            "10_response_validation",
            "11_clarification_rules",
        ]
        actual_steps = [s.step for s in result.steps]
        self.assertEqual(actual_steps, expected_steps)

    def test_total_elapsed_positive(self):
        self.policy._router.classify.return_value = _mock_routing()
        self.policy._ref_classifier.classify.return_value = (
            _mock_ref_result()
        )
        self.policy._param_validator.validate.return_value = _mock_validation()
        result = self.policy.analyze("test")
        self.assertGreater(result.total_elapsed_ms, 0)

    def test_search_fallback_no_tool(self):
        self.policy._router.classify.return_value = _mock_routing(
            intent="unknown", tool="none", confidence=0.15,
        )
        result = self.policy.analyze("???")
        self.assertFalse(result.should_proceed)
        self.assertFalse(result.needs_clarification)
        self.assertTrue(result.tool_decision.needs_search_fallback)

    def test_context_ignored(self):
        self.policy._router.classify.return_value = _mock_routing()
        self.policy._ref_classifier.classify.return_value = (
            _mock_ref_result()
        )
        self.policy._param_validator.validate.return_value = _mock_validation()
        result = self.policy.analyze("test", {"extra": "data"})
        self.assertIsInstance(result, ReasoningResult)


# ════════════════════════════════════════════════════════════════════════
# Integration with Real Modules
# ════════════════════════════════════════════════════════════════════════


class TestIntegrationWithRealModules(unittest.TestCase):
    def test_real_router_waste_search(self):
        policy = AIReasoningPolicy()
        policy._ref_classifier = MagicMock()
        policy._param_validator = MagicMock()
        policy._ref_classifier.classify.return_value = (
            _mock_ref_result("waste_code", 0.9)
        )
        policy._param_validator.validate.return_value = _mock_validation(
            valid=True,
        )
        result = policy.analyze("Quels sont les déchets dangereux ?")
        self.assertEqual(result.tool_name, "waste_tool")
        self.assertTrue(result.should_proceed)

    def test_real_router_greeting(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("Bonjour !")
        self.assertEqual(result.tool_name, "greeting")
        self.assertTrue(result.should_proceed)

    def test_real_router_nomenclature(self):
        policy = AIReasoningPolicy()
        policy._ref_classifier = MagicMock()
        policy._param_validator = MagicMock()
        policy._ref_classifier.classify.return_value = (
            _mock_ref_result("waste_code", 0.95)
        )
        policy._param_validator.validate.return_value = _mock_validation(
            valid=True,
        )
        result = policy.analyze("Code déchet 15.01.06")
        self.assertIn(result.tool_name, ("waste_tool", "nomenclature_tool"))

    def test_real_ref_classifier(self):
        policy = AIReasoningPolicy()
        policy._param_validator = MagicMock()
        policy._param_validator.validate.return_value = _mock_validation(
            valid=True,
        )
        result = policy.analyze("Code déchet 15.01.06")
        refs = result.entities.classified_references
        self.assertGreater(len(refs), 0)

    def test_real_all_components(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("Quels sont les déchets dangereux ?")
        self.assertIsInstance(result, ReasoningResult)
        self.assertEqual(len(result.steps), 11)
        self.assertGreater(result.total_elapsed_ms, 0)

    def test_real_empty_message(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("")
        self.assertFalse(result.should_proceed)
        self.assertTrue(result.needs_clarification)

    def test_real_step_count(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("Bonjour")
        self.assertEqual(len(result.steps), 11)


# ════════════════════════════════════════════════════════════════════════
# Edge Cases
# ════════════════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):
    def test_none_message(self):
        policy = AIReasoningPolicy()
        result = policy.analyze(None)
        self.assertFalse(result.should_proceed)
        self.assertTrue(result.needs_clarification)

    def test_very_long_message(self):
        policy = AIReasoningPolicy()
        msg = "a" * 10000
        result = policy.analyze(msg)
        self.assertIsInstance(result, ReasoningResult)

    def test_special_characters(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("Éàèêëïîôùüûÿçœæ!@#$%^&*()")
        self.assertIsInstance(result, ReasoningResult)

    def test_only_punctuation(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("?!?!")
        self.assertIsInstance(result, ReasoningResult)

    def test_numbers_only(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("123456789")
        self.assertIsInstance(result, ReasoningResult)

    def test_mixed_languages(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("Bonjour what are the déchets?")
        self.assertIsInstance(result, ReasoningResult)
        self.assertTrue(result.language.is_bilingual)

    def test_waste_code_in_message(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("15.01.06")
        self.assertGreater(result.entities.total_entities, 0)

    def test_bsd_in_message(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("BSD-2024-0001")
        self.assertGreater(len(result.entities.bsd_numbers), 0)

    def test_percentage_in_message(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("33.3%")
        self.assertGreater(len(result.entities.percentages), 0)

    def test_context_ignored_by_analyze(self):
        policy = AIReasoningPolicy()
        r1 = policy.analyze("test")
        r2 = policy.analyze("test", {"any": "context"})
        self.assertEqual(r1.tool_name, r2.tool_name)

    def test_all_steps_produce_details(self):
        policy = AIReasoningPolicy()
        result = policy.analyze("Bonjour le monde")
        for step in result.steps:
            self.assertIsInstance(step.details, dict)


# ════════════════════════════════════════════════════════════════════════
# Lazy Singleton Tests
# ════════════════════════════════════════════════════════════════════════


class TestLazySingletons(unittest.TestCase):
    def test_router_singleton(self):
        policy = AIReasoningPolicy()
        r1 = policy._get_router()
        r2 = policy._get_router()
        self.assertIs(r1, r2)

    def test_ref_classifier_singleton(self):
        policy = AIReasoningPolicy()
        r1 = policy._get_ref_classifier()
        r2 = policy._get_ref_classifier()
        self.assertIs(r1, r2)

    def test_param_validator_singleton(self):
        policy = AIReasoningPolicy()
        r1 = policy._get_param_validator()
        r2 = policy._get_param_validator()
        self.assertIs(r1, r2)

    def test_injected_overrides_singleton(self):
        policy = AIReasoningPolicy()
        mock = MagicMock()
        policy._router = mock
        self.assertIs(policy._get_router(), mock)


# ════════════════════════════════════════════════════════════════════════
# Weights and Thresholds
# ════════════════════════════════════════════════════════════════════════


class TestWeightsAndThresholds(unittest.TestCase):
    def test_threshold_is_80_percent(self):
        self.assertAlmostEqual(CONFIDENCE_THRESHOLD, 0.80, places=2)

    def test_all_weights_positive(self):
        self.assertGreater(WEIGHT_INTENT, 0)
        self.assertGreater(WEIGHT_REFERENCES, 0)
        self.assertGreater(WEIGHT_ENTITIES, 0)
        self.assertGreater(WEIGHT_SEARCH, 0)
        self.assertGreater(WEIGHT_TOOL_SELECTION, 0)

    def test_weights_sum_to_one(self):
        total = (
            WEIGHT_INTENT + WEIGHT_REFERENCES + WEIGHT_ENTITIES
            + WEIGHT_SEARCH + WEIGHT_TOOL_SELECTION
        )
        self.assertAlmostEqual(total, 1.0, places=6)


# ════════════════════════════════════════════════════════════════════════
# No Django / No Repository / No Tool Execution
# ════════════════════════════════════════════════════════════════════════


class TestFrameworkIndependence(unittest.TestCase):
    def test_no_django_imports_in_module(self):
        """The reasoning_policy module should never import Django."""
        import apps.ai_assistant.enterprise.reasoning_policy as mod
        source = open(mod.__file__).read()
        self.assertNotIn("import django", source)
        self.assertNotIn("from django", source)

    def test_no_repository_imports(self):
        """Should never import from repositories."""
        import apps.ai_assistant.enterprise.reasoning_policy as mod
        source = open(mod.__file__).read()
        self.assertNotIn("from apps.ai_assistant.repositories", source)

    def test_no_model_access(self):
        """Should never import Django models."""
        import apps.ai_assistant.enterprise.reasoning_policy as mod
        source = open(mod.__file__).read()
        self.assertNotIn("from apps.accounts.models", source)
        self.assertNotIn("from apps.nomenclature.models", source)
        self.assertNotIn("from apps.bsd.models", source)

    def test_no_execute_tool_calls(self):
        """Policy should never execute tools."""
        import apps.ai_assistant.enterprise.reasoning_policy as mod
        source = open(mod.__file__).read()
        self.assertNotIn("execute_tool", source)
        self.assertNotIn("tool_executor", source)


if __name__ == "__main__":
    unittest.main()
