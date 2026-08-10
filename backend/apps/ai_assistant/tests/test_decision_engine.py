"""
Comprehensive tests for the AI Decision Engine.

Tests cover:
    - Step 1: User message reception and validation
    - Step 2: Intent detection via AI Router
    - Step 3: Reference classification via ReferenceClassifier
    - Step 4: Entity extraction (regex-based)
    - Step 5: Confidence score calculation
    - Step 6: Search strategy (short queries)
    - Step 7: Tool selection via AI Router
    - Step 8: Parameter validation via ParameterValidator
    - Full pipeline: complete decision flows
    - Edge cases: empty input, missing deps, exceptions
    - Audit trail: every step produces a DecisionLog
    - DecisionResult.to_dict() serialization
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, PropertyMock, patch

from apps.ai_assistant.enterprise.decision_engine import (
    CONFIDENCE_THRESHOLD,
    DecisionEngine,
    DecisionLog,
    DecisionResult,
    _STEP_WEIGHTS,
    _extract_reference_tokens,
    _truncate,
)


# ── Mock Helpers ──────────────────────────────────────────────────────


def _make_mock_container() -> MagicMock:
    c = MagicMock()
    c.cache = MagicMock()
    c.metrics = MagicMock()
    c.tracer = MagicMock()
    c.audit = MagicMock()
    return c


class _FakeRoutingResult:
    """Minimal stand-in for RoutingResult."""

    def __init__(
        self,
        intent: str = "waste_search",
        tool: str = "waste_tool",
        confidence: float = 0.90,
        entities: Optional[List[Any]] = None,
        references: Optional[List[Any]] = None,
        candidates: Optional[List[Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        self.intent = intent
        self.tool = tool
        self.confidence = confidence
        self.entities = entities or []
        self.references = references or []
        self.candidates = candidates or []
        self.parameters = parameters or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "tool": self.tool,
            "entities": [],
            "references": [],
            "candidates": [],
            "parameters": self.parameters,
        }


class _FakeCandidate:
    def __init__(self, tool: str = "waste_tool", intent: str = "waste_search", confidence: float = 0.90):
        self.tool = tool
        self.intent = intent
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {"tool": self.tool, "intent": self.intent, "confidence": self.confidence}


class _FakeClassifyResult:
    def __init__(self, reference_type: str = "unknown_reference", confidence: float = 0.0):
        self.reference_type = reference_type
        self.confidence = confidence


class _FakeValidationResult:
    def __init__(self, valid: bool = True, missing: Optional[List[Any]] = None):
        self.valid = valid
        self.missing_parameters = missing or []

    def to_dict(self) -> Dict[str, Any]:
        return {"valid": self.valid}


class _FakeMissingParam:
    def __init__(self, name: str):
        self.name = name

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name}


class _FakeSearchSourceResult:
    def __init__(self, tool="glossaire_tool", action="search", score=0.90, source="glossary"):
        self.tool = tool
        self.action = action
        self.score = score
        self.source = source
        self.parameters = {}
        self.label = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"tool": self.tool, "action": self.action, "score": self.score}


class _FakeSearchResult:
    def __init__(self, has_result: bool = False, best: Optional[_FakeSearchSourceResult] = None):
        self.has_result = has_result
        self.best_match = best
        self.query = "test"
        self.is_short = True
        self.all_matches = [best] if best else []
        self.needs_clarification = False
        self.clarification_question = None
        self.clarification_options = []


# ── Step 1: User Reception ───────────────────────────────────────────


class TestStep1UserReception(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())

    def test_valid_message_accepted(self):
        result = self.engine.decide("Bonjour")
        log = result.logs[0]
        self.assertEqual(log.step, "1_user")
        self.assertEqual(log.confidence, 1.0)
        self.assertEqual(log.output_summary, "ACCEPTED")

    def test_empty_message_rejected(self):
        result = self.engine.decide("")
        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.logs[0].confidence, 0.0)
        self.assertIn("vide", result.logs[0].reasoning)

    def test_whitespace_only_rejected(self):
        result = self.engine.decide("   ")
        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.logs[0].confidence, 0.0)

    def test_single_char_rejected(self):
        result = self.engine.decide("a")
        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.logs[0].confidence, 0.3)

    def test_special_chars_only_rejected(self):
        result = self.engine.decide("!!!???")
        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.logs[0].confidence, 0.2)

    def test_none_message_rejected(self):
        result = self.engine.decide(None)  # type: ignore
        self.assertTrue(result.needs_clarification)

    def test_log_has_elapsed_ms(self):
        result = self.engine.decide("Test message")
        self.assertGreaterEqual(result.logs[0].elapsed_ms, 0.0)

    def test_log_has_conversation_id(self):
        result = self.engine.decide("Test", {"conversation_id": "abc"})
        self.assertEqual(result.logs[0].details.get("conversation_id"), "abc")


# ── Step 2: Intent Detection ─────────────────────────────────────────


class TestStep2IntentDetection(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())

    def test_waste_search_intent(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="waste_search", tool="waste_tool", confidence=0.92,
        )
        result = self.engine.decide("Quels sont les déchets dangereux ?")
        log = result.logs[1]
        self.assertEqual(log.step, "2_intent_detection")
        self.assertEqual(log.confidence, 0.92)
        self.assertIn("waste_search", log.output_summary)

    def test_no_intent_detected(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = None
        result = self.engine.decide("asdkjfhaskdjfh")
        self.assertTrue(result.needs_clarification)
        log = result.logs[1]
        self.assertEqual(log.confidence, 0.0)

    def test_intent_exception_returns_error(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.side_effect = RuntimeError("boom")
        result = self.engine.decide("déchets")
        self.assertTrue(result.needs_clarification)
        log = result.logs[1]
        self.assertIn("Erreur", log.reasoning)

    def test_greeting_returns_early(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="greeting", tool="greeting", confidence=0.95,
        )
        result = self.engine.decide("Bonjour")
        self.assertEqual(result.tool_name, "greeting")
        self.assertFalse(result.needs_clarification)
        self.assertEqual(len(result.logs), 2)

    def test_intent_log_has_details(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="waste_search", tool="waste_tool", confidence=0.92,
        )
        result = self.engine.decide("déchets dangereux")
        log = result.logs[1]
        self.assertIn("intent", log.details)


# ── Step 3: Reference Classification ─────────────────────────────────


class TestStep3ReferenceClassification(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="waste_search", tool="waste_tool", confidence=0.92,
        )
        self.engine._reference_classifier = MagicMock()

    def test_no_references(self):
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult(
            "unknown_reference", 0.0,
        )
        result = self.engine.decide("Quels sont les déchets ?")
        log = result.logs[2]
        self.assertEqual(log.step, "3_reference_classification")
        self.assertEqual(log.confidence, 0.9)
        self.assertIn("NONE", log.output_summary)

    def test_waste_code_reference(self):
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult(
            "waste_code", 0.95,
        )
        result = self.engine.decide("15.01.06 est quoi ?")
        log = result.logs[2]
        self.assertEqual(log.confidence, 0.95)
        self.assertIn("waste_code", log.output_summary)

    def test_multiple_references(self):
        call_count = [0]

        def classify_side_effect(text):
            call_count[0] += 1
            if "15.01.06" in text:
                return _FakeClassifyResult("waste_code", 0.95)
            return _FakeClassifyResult("bsd_number", 0.97)

        self.engine._reference_classifier.classify.side_effect = classify_side_effect
        result = self.engine.decide("15.01.06 et BSD-2024-001")
        log = result.logs[2]
        self.assertIn("2 refs", log.output_summary)

    def test_reference_exception_returns_error(self):
        self.engine._reference_classifier.classify.side_effect = RuntimeError("boom")
        result = self.engine.decide("15.01.06 test")
        log = result.logs[2]
        self.assertIn("Erreur", log.reasoning)
        self.assertEqual(log.confidence, 0.7)


# ── Step 4: Entity Extraction ────────────────────────────────────────


class TestStep4EntityExtraction(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult()
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()

    def test_waste_code_extracted(self):
        result = self.engine.decide("15.01.06 est un déchet")
        log = result.logs[3]
        self.assertIn("15.01.06", log.details["entities"]["waste_codes"])

    def test_bsd_number_extracted(self):
        result = self.engine.decide("BSD-2024-001 est en attente")
        log = result.logs[3]
        self.assertTrue(len(log.details["entities"]["bsd_numbers"]) > 0)

    def test_date_extracted(self):
        result = self.engine.decide("Le 01/01/2024")
        log = result.logs[3]
        self.assertTrue(len(log.details["entities"]["dates"]) > 0)

    def test_quantity_extracted(self):
        result = self.engine.decide("100 kg de déchets")
        log = result.logs[3]
        self.assertTrue(len(log.details["entities"]["quantities"]) > 0)

    def test_email_extracted(self):
        result = self.engine.decide("Contact: test@example.com")
        log = result.logs[3]
        self.assertIn("test@example.com", log.details["entities"]["emails"])

    def test_no_entities(self):
        result = self.engine.decide("Bonjour comment allez-vous")
        log = result.logs[3]
        self.assertEqual(log.details["total"], 0)
        self.assertGreater(log.confidence, 0.6)

    def test_entity_confidence_scales_with_count(self):
        result_few = self.engine.decide("un déchet")
        result_many = self.engine.decide("15.01.06 BSD-2024-001 01/01/2024 100 kg")
        conf_few = result_few.logs[3].confidence
        conf_many = result_many.logs[3].confidence
        self.assertGreaterEqual(conf_many, conf_few)

    def test_percentages_extracted(self):
        result = self.engine.decide("50% du total")
        log = result.logs[3]
        self.assertIn("50%", log.details["entities"]["percentages"])

    def test_years_extracted(self):
        result = self.engine.decide("pour l'année 2024")
        log = result.logs[3]
        self.assertIn("2024", log.details["entities"]["years"])


# ── Step 5: Confidence Score ─────────────────────────────────────────


class TestStep5ConfidenceScore(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())

    def test_high_confidence_passes(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(confidence=0.95)
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        result = self.engine.decide("Quels sont les déchets dangereux ?")
        log = result.logs[4]
        self.assertEqual(log.step, "5_confidence_score")
        self.assertGreaterEqual(log.confidence, CONFIDENCE_THRESHOLD)
        self.assertIn("PASS", log.output_summary)

    def test_low_confidence_fails(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(confidence=0.30)
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        result = self.engine.decide("x")
        # Step 1 rejects "x" (too short), so we never reach step 5
        self.assertTrue(result.needs_clarification)

    def test_confidence_log_has_breakdown(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(confidence=0.92)
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        result = self.engine.decide("déchets dangereux")
        log = result.logs[4]
        self.assertIn("breakdown", log.details)
        self.assertIn("threshold", log.details)

    def test_weights_sum_to_one(self):
        total = sum(_STEP_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=6)


# ── Step 6: Search Strategy ──────────────────────────────────────────


class TestStep6SearchStrategy(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult()
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        self.engine._search_strategy = MagicMock()

    @patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=False)
    def test_long_query_skips_search(self, mock_is_short):
        result = self.engine.decide("Quels sont les déchets dangereux dans votre base de données ?")
        log = result.logs[5]
        self.assertEqual(log.step, "6_search_strategy")
        self.assertIn("SKIPPED", log.output_summary)

    @patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=True)
    def test_short_query_searches(self, mock_is_short):
        fake_result = _FakeSearchResult(
            has_result=True,
            best=_FakeSearchSourceResult(tool="glossaire_tool", action="search", score=0.85),
        )
        self.engine._search_strategy.search.return_value = fake_result
        result = self.engine.decide("BSD")
        log = result.logs[5]
        self.assertIn("MATCH", log.output_summary)

    @patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=True)
    def test_short_query_no_match(self, mock_is_short):
        self.engine._search_strategy.search.return_value = _FakeSearchResult(has_result=False)
        result = self.engine.decide("xyz")
        log = result.logs[5]
        self.assertIn("NO_MATCH", log.output_summary)

    @patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=True)
    def test_search_exception(self, mock_is_short):
        self.engine._search_strategy.search.side_effect = RuntimeError("boom")
        result = self.engine.decide("test")
        log = result.logs[5]
        self.assertIn("Erreur", log.reasoning)


# ── Step 7: Tool Selection ───────────────────────────────────────────


class TestStep7ToolSelection(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())
        self.engine._ai_router = MagicMock()
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()

    def test_tool_selected(self):
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="waste_search",
            tool="waste_tool",
            confidence=0.92,
            candidates=[_FakeCandidate("waste_tool", "waste_search", 0.92)],
            parameters={"action": "search", "query": "déchets"},
        )
        result = self.engine.decide("Rechercher les déchets")
        log = result.logs[6]
        self.assertEqual(log.step, "7_tool_selection")
        self.assertIn("waste_tool", log.output_summary)

    def test_no_tool_selected(self):
        call_count = [0]
        def classify_side_effect(msg):
            call_count[0] += 1
            if call_count[0] == 1:
                # Step 2: valid intent detection
                return _FakeRoutingResult(intent="question", tool="none", confidence=0.85)
            # Step 7: no tool found
            return _FakeRoutingResult(tool="none", confidence=0.0)
        self.engine._ai_router.classify.side_effect = classify_side_effect
        result = self.engine.decide("asdkjfhaskdjfh")
        log = result.logs[6]
        self.assertIn("NO_TOOL", log.output_summary)

    def test_tool_selection_exception(self):
        call_count = [0]
        def classify_side_effect(msg):
            call_count[0] += 1
            if call_count[0] == 1:
                return _FakeRoutingResult(intent="waste_search", tool="waste_tool", confidence=0.92)
            raise RuntimeError("boom")
        self.engine._ai_router.classify.side_effect = classify_side_effect
        result = self.engine.decide("déchets")
        log = result.logs[6]
        self.assertIn("Erreur", log.reasoning)

    def test_tool_log_has_candidates(self):
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            tool="waste_tool",
            confidence=0.92,
            candidates=[_FakeCandidate(), _FakeCandidate("nomenclature_tool", confidence=0.80)],
            parameters={"action": "search"},
        )
        result = self.engine.decide("déchets")
        log = result.logs[6]
        self.assertEqual(log.details["candidate_count"], 2)


# ── Step 8: Parameter Validation ─────────────────────────────────────


class TestStep8ParameterValidation(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            tool="waste_tool",
            confidence=0.92,
            candidates=[_FakeCandidate()],
            parameters={"action": "search", "query": "déchets"},
        )
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        self.engine._parameter_validator = MagicMock()

    def test_valid_parameters(self):
        self.engine._parameter_validator.validate.return_value = _FakeValidationResult(valid=True)
        result = self.engine.decide("Rechercher les déchets")
        log = result.logs[7]
        self.assertEqual(log.step, "8_parameter_validation")
        self.assertIn("VALID", log.output_summary)

    def test_missing_parameters(self):
        self.engine._parameter_validator.validate.return_value = _FakeValidationResult(
            valid=False,
            missing=[_FakeMissingParam("query")],
        )
        result = self.engine.decide("Rechercher les déchets")
        self.assertTrue(result.needs_clarification)
        self.assertIn("query", result.clarification_question)

    def test_validation_exception(self):
        self.engine._parameter_validator.validate.side_effect = RuntimeError("boom")
        result = self.engine.decide("Rechercher les déchets")
        log = result.logs[7]
        self.assertIn("Erreur", log.reasoning)

    def test_greeting_skips_validation(self):
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="greeting", tool="greeting", confidence=0.95,
        )
        result = self.engine.decide("Bonjour")
        self.assertEqual(result.tool_name, "greeting")
        self.assertEqual(len(result.logs), 2)


# ── Full Pipeline ─────────────────────────────────────────────────────


class TestFullPipeline(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="waste_search",
            tool="waste_tool",
            confidence=0.92,
            candidates=[_FakeCandidate("waste_tool", "waste_search", 0.92)],
            parameters={"action": "search", "query": "déchets dangereux"},
        )
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        self.engine._parameter_validator = MagicMock()
        self.engine._parameter_validator.validate.return_value = _FakeValidationResult(valid=True)
        self.engine._search_strategy = MagicMock()
        self.engine._search_strategy.search.return_value = _FakeSearchResult(has_result=False)

    @patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=False)
    def test_full_pipeline_completes(self, _mock):
        result = self.engine.decide("Quels sont les déchets dangereux ?")
        self.assertFalse(result.needs_clarification)
        self.assertEqual(result.tool_name, "waste_tool")
        self.assertGreaterEqual(result.confidence, CONFIDENCE_THRESHOLD)
        self.assertEqual(len(result.logs), 8)

    @patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=False)
    def test_full_pipeline_has_all_steps(self, _mock):
        result = self.engine.decide("Rechercher les déchets")
        steps = [log.step for log in result.logs]
        self.assertIn("1_user", steps)
        self.assertIn("2_intent_detection", steps)
        self.assertIn("3_reference_classification", steps)
        self.assertIn("4_entity_extraction", steps)
        self.assertIn("5_confidence_score", steps)
        self.assertIn("6_search_strategy", steps)
        self.assertIn("7_tool_selection", steps)
        self.assertIn("8_parameter_validation", steps)

    @patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=False)
    def test_full_pipeline_to_dict(self, _mock):
        result = self.engine.decide("déchets")
        d = result.to_dict()
        self.assertIn("tool_name", d)
        self.assertIn("logs", d)
        self.assertIn("confidence", d)
        self.assertEqual(len(d["logs"]), 8)
        for log_dict in d["logs"]:
            self.assertIn("step", log_dict)
            self.assertIn("confidence", log_dict)
            self.assertIn("elapsed_ms", log_dict)

    @patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=False)
    def test_full_pipeline_elapsed_ms(self, _mock):
        result = self.engine.decide("déchets")
        self.assertGreaterEqual(result.elapsed_ms, 0.0)

    def test_clarification_result_to_dict(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = None
        result = self.engine.decide("asdkjfhaskdjfh")
        d = result.to_dict()
        self.assertTrue(d["needs_clarification"])
        self.assertIn("clarification_question", d)


# ── Clarification Triggers ────────────────────────────────────────────


class TestClarificationTriggers(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())

    def test_empty_message_clarification(self):
        result = self.engine.decide("")
        self.assertTrue(result.needs_clarification)
        self.assertIsNotNone(result.clarification_question)

    def test_no_intent_clarification(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = None
        result = self.engine.decide("asdkjfhaskdjfh")
        self.assertTrue(result.needs_clarification)

    def test_low_confidence_clarification(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(confidence=0.40)
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        result = self.engine.decide("quelque chose de vague")
        self.assertTrue(result.needs_clarification)

    def test_missing_params_clarification(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            tool="waste_tool",
            confidence=0.92,
            candidates=[_FakeCandidate()],
            parameters={"action": "search"},
        )
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        self.engine._parameter_validator = MagicMock()
        self.engine._parameter_validator.validate.return_value = _FakeValidationResult(
            valid=False,
            missing=[_FakeMissingParam("query"), _FakeMissingParam("waste_code")],
        )
        result = self.engine.decide("Rechercher")
        self.assertTrue(result.needs_clarification)
        self.assertIn("query", result.clarification_question)
        self.assertIn("waste_code", result.clarification_question)


# ── DecisionLog ───────────────────────────────────────────────────────


class TestDecisionLog(unittest.TestCase):

    def test_to_dict_basic(self):
        log = DecisionLog(
            step="1_user",
            input_summary="test",
            output_summary="ACCEPTED",
            confidence=1.0,
            reasoning="OK",
            elapsed_ms=0.5,
        )
        d = log.to_dict()
        self.assertEqual(d["step"], "1_user")
        self.assertEqual(d["confidence"], 1.0)
        self.assertEqual(d["elapsed_ms"], 0.5)

    def test_to_dict_with_details(self):
        log = DecisionLog(
            step="test",
            input_summary="in",
            output_summary="out",
            confidence=0.9,
            reasoning="r",
            elapsed_ms=1.0,
            details={"key": "value"},
        )
        d = log.to_dict()
        self.assertIn("details", d)
        self.assertEqual(d["details"]["key"], "value")

    def test_to_dict_no_details_omitted(self):
        log = DecisionLog(
            step="test", input_summary="in", output_summary="out",
            confidence=0.9, reasoning="r", elapsed_ms=1.0,
        )
        d = log.to_dict()
        self.assertNotIn("details", d)


# ── DecisionResult ────────────────────────────────────────────────────


class TestDecisionResult(unittest.TestCase):

    def test_success_result_to_dict(self):
        result = DecisionResult(
            tool_name="waste_tool",
            action="search",
            parameters={"query": "test"},
            confidence=0.92,
            logs=[],
            needs_clarification=False,
            elapsed_ms=10.0,
        )
        d = result.to_dict()
        self.assertEqual(d["tool_name"], "waste_tool")
        self.assertFalse(d["needs_clarification"])

    def test_clarification_result_to_dict(self):
        result = DecisionResult(
            tool_name="none",
            action=None,
            parameters={},
            confidence=0.0,
            needs_clarification=True,
            clarification_question="Which one?",
            clarification_options=[{"label": "A"}, {"label": "B"}],
        )
        d = result.to_dict()
        self.assertTrue(d["needs_clarification"])
        self.assertIn("clarification_question", d)
        self.assertEqual(len(d["clarification_options"]), 2)


# ── Helpers ───────────────────────────────────────────────────────────


class TestHelpers(unittest.TestCase):

    def test_truncate_short(self):
        self.assertEqual(_truncate("hello", 10), "hello")

    def test_truncate_long(self):
        self.assertEqual(_truncate("hello world", 8), "hello...")

    def test_truncate_exact(self):
        self.assertEqual(_truncate("hello", 5), "hello")

    def test_extract_reference_tokens_dotted(self):
        tokens = _extract_reference_tokens("15.01.06 est un code")
        self.assertIn("15.01.06", tokens)

    def test_extract_reference_tokens_prefixed(self):
        tokens = _extract_reference_tokens("BSD-2024-001 est en attente")
        self.assertTrue(any("BSD" in t for t in tokens))

    def test_extract_reference_tokens_deduplication(self):
        tokens = _extract_reference_tokens("15.01.06 et 15.01.06")
        self.assertEqual(tokens.count("15.01.06"), 1)

    def test_extract_reference_tokens_empty(self):
        tokens = _extract_reference_tokens("Bonjour")
        self.assertEqual(len(tokens), 0)


# ── Edge Cases ────────────────────────────────────────────────────────


class TestEdgeCases(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())

    def test_very_long_message(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult()
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        long_msg = "déchets " * 1000
        result = self.engine.decide(long_msg)
        self.assertEqual(result.logs[0].confidence, 1.0)

    def test_unicode_message(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult()
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        result = self.engine.decide("Les déchets dangereux et les substances chimiques")
        self.assertEqual(result.logs[0].confidence, 1.0)

    def test_context_not_required(self):
        result = self.engine.decide("Bonjour")
        self.assertIsNotNone(result)

    def test_none_context_defaults(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="greeting", tool="greeting",
        )
        result = self.engine.decide("Bonjour", None)
        self.assertEqual(result.tool_name, "greeting")

    def test_special_characters_in_message(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult()
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        result = self.engine.decide("Test & test < > €")
        self.assertEqual(result.logs[0].confidence, 1.0)

    def test_mixed_language_message(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult()
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        result = self.engine.decide("Show me les déchets")
        self.assertEqual(result.logs[0].confidence, 1.0)

    def test_numbers_only_message(self):
        result = self.engine.decide("12345")
        # "12345" is 5 chars so passes step 1, but may not match any intent
        self.assertTrue(len(result.logs) >= 2)

    def test_multiple_waste_codes(self):
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult()
        self.engine._reference_classifier = MagicMock()
        self.engine._reference_classifier.classify.return_value = _FakeClassifyResult()
        result = self.engine.decide("15.01.06 20.01.01 17.01.07")
        log = result.logs[3]
        self.assertEqual(len(log.details["entities"]["waste_codes"]), 3)


# ── DecisionResult.elapsed_ms ─────────────────────────────────────────


class TestDecisionResultTiming(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(_make_mock_container())
        self.engine._ai_router = MagicMock()
        self.engine._ai_router.classify.return_value = _FakeRoutingResult(
            intent="greeting", tool="greeting",
        )

    def test_result_has_positive_elapsed(self):
        result = self.engine.decide("Bonjour")
        self.assertGreaterEqual(result.elapsed_ms, 0.0)

    def test_log_entries_have_positive_elapsed(self):
        result = self.engine.decide("Bonjour")
        for log in result.logs:
            self.assertGreaterEqual(log.elapsed_ms, 0.0)


# ── Integration with existing modules ─────────────────────────────────


class TestIntegrationWithExistingModules(unittest.TestCase):
    """Verify the engine works with real instances (not mocks)."""

    def test_real_ai_router(self):
        from apps.ai_assistant.enterprise.ai_router import AIRouter
        engine = DecisionEngine(_make_mock_container())
        engine._ai_router = AIRouter()
        engine._ref_classifier = MagicMock()
        engine._ref_classifier.classify.return_value = _FakeClassifyResult()
        result = engine.decide("Quels sont les déchets dangereux ?")
        self.assertIn(result.tool_name, ("waste_tool", "glossaire_tool", "none"))
        self.assertGreaterEqual(len(result.logs), 2)

    def test_real_reference_classifier(self):
        from apps.ai_assistant.enterprise.reference_classifier import ReferenceClassifier
        engine = DecisionEngine(_make_mock_container())
        engine._ai_router = MagicMock()
        engine._ai_router.classify.return_value = _FakeRoutingResult()
        engine._ref_classifier = ReferenceClassifier()
        result = engine.decide("15.01.06 est quoi ?")
        log = result.logs[2]
        self.assertIn("waste_code", log.output_summary)

    def test_real_full_pipeline(self):
        from apps.ai_assistant.enterprise.ai_router import AIRouter
        from apps.ai_assistant.enterprise.reference_classifier import ReferenceClassifier
        from apps.ai_assistant.enterprise.parameter_validator import ToolParameterValidator

        engine = DecisionEngine(_make_mock_container())
        engine._ai_router = AIRouter()
        engine._ref_classifier = ReferenceClassifier()
        engine._param_validator = ToolParameterValidator()
        engine._search = MagicMock()
        engine._search.search.return_value = _FakeSearchResult(has_result=False)

        with patch("apps.ai_assistant.enterprise.decision_engine.is_short_query", return_value=False):
            result = engine.decide("Quels sont les déchets dangereux ?")
        self.assertFalse(result.needs_clarification)
        self.assertEqual(len(result.logs), 8)
        self.assertGreaterEqual(result.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
