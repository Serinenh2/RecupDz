"""
Tests for ClarificationManager — ambiguity detection and question generation.

Covers:
    - Ambiguous references (low confidence dotted numerics)
    - Low confidence routing
    - Close candidates (gap < threshold)
    - Clear routing (no clarification needed)
    - Edge cases (empty input, single candidate, high confidence)
    - Reference type filtering (BSD/BC/BL/ tracking excluded)
    - Question formatting (French)
    - Data class to_dict() contracts
    - Crash safety (never raises)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from apps.ai_assistant.enterprise.clarification_manager import (
    ClarificationManager,
    ClarificationOption,
    ClarificationResult,
)


# ---------------------------------------------------------------------------
# Helpers — lightweight fakes for ToolCandidate / ClassifiedReference
# ---------------------------------------------------------------------------

@dataclass
class FakeCandidate:
    tool: str = ""
    intent: str = ""
    confidence: float = 0.0
    priority: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: str = "rule"


@dataclass
class FakeReference:
    reference: str = ""
    reference_type: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr() -> ClarificationManager:
    return ClarificationManager()


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


class TestClarificationOption:
    def test_to_dict_full(self) -> None:
        opt = ClarificationOption(
            label="code déchet",
            tool="waste_tool",
            action="get_by_code",
            parameters={"code": "15.01.01"},
            confidence=0.9,
        )
        d = opt.to_dict()
        assert d["label"] == "code déchet"
        assert d["tool"] == "waste_tool"
        assert d["action"] == "get_by_code"
        assert d["parameters"] == {"code": "15.01.01"}
        assert d["confidence"] == 0.9

    def test_to_dict_minimal(self) -> None:
        opt = ClarificationOption(label="x", tool="t", action="a")
        d = opt.to_dict()
        assert "parameters" not in d
        assert "confidence" not in d

    def test_frozen(self) -> None:
        opt = ClarificationOption(label="x", tool="t", action="a")
        with pytest.raises(AttributeError):
            opt.label = "y"  # type: ignore[misc]


class TestClarificationResult:
    def test_to_dict(self) -> None:
        r = ClarificationResult(
            question="Est-ce un code déchet ?",
            options=[ClarificationOption(label="oui", tool="w", action="s")],
            original_message="1.3.1",
            reason="ambiguous_reference",
        )
        d = r.to_dict()
        assert d["question"] == "Est-ce un code déchet ?"
        assert len(d["options"]) == 1
        assert d["original_message"] == "1.3.1"
        assert d["reason"] == "ambiguous_reference"


# ---------------------------------------------------------------------------
# No clarification needed
# ---------------------------------------------------------------------------


class TestNoClarificationNeeded:
    def test_no_candidates(self, mgr: ClarificationManager) -> None:
        result = mgr.analyze("hello")
        assert result is None

    def test_single_high_confidence_candidate(self, mgr: ClarificationManager) -> None:
        c = FakeCandidate(tool="waste_tool", intent="waste_search", confidence=0.95)
        result = mgr.analyze("déchets dangereux", candidates=[c])
        assert result is None

    def test_no_references(self, mgr: ClarificationManager) -> None:
        result = mgr.analyze("bonjour", classified_references=[])
        assert result is None

    def test_high_confidence_reference(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="BSD-2024-0001", reference_type="bsd_number", confidence=0.97)
        result = mgr.analyze("BSD-2024-0001", classified_references=[ref])
        assert result is None

    def test_two_candidates_large_gap(self, mgr: ClarificationManager) -> None:
        c1 = FakeCandidate(tool="waste_tool", confidence=0.95)
        c2 = FakeCandidate(tool="bsd_tool", confidence=0.40)
        result = mgr.analyze("query", candidates=[c1, c2])
        assert result is None


# ---------------------------------------------------------------------------
# Ambiguous references
# ---------------------------------------------------------------------------


class TestAmbiguousReference:
    def test_waste_code_below_threshold(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="1.3.1", reference_type="waste_code", confidence=0.80)
        result = mgr.analyze("1.3.1", classified_references=[ref])
        assert result is not None
        assert result.reason == "ambiguous_reference"
        assert "1.3.1" in result.question
        assert len(result.options) == 3

    def test_options_have_correct_tools(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="15.01", reference_type="waste_code", confidence=0.75)
        result = mgr.analyze("15.01", classified_references=[ref])
        assert result is not None
        tools = [opt.tool for opt in result.options]
        assert "waste_tool" in tools
        assert "reglementation_tool" in tools
        assert "glossaire_tool" in tools

    def test_parameters_filled_for_get_by_code(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="1.3.1", reference_type="waste_code", confidence=0.80)
        result = mgr.analyze("1.3.1", classified_references=[ref])
        assert result is not None
        code_opt = [o for o in result.options if o.action == "get_by_code"][0]
        assert code_opt.parameters == {"code": "1.3.1"}

    def test_parameters_filled_for_by_reference(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="1.3.1", reference_type="waste_code", confidence=0.80)
        result = mgr.analyze("1.3.1", classified_references=[ref])
        assert result is not None
        ref_opt = [o for o in result.options if o.action == "by_reference"][0]
        assert ref_opt.parameters == {"reference": "1.3.1"}

    def test_parameters_filled_for_search(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="1.3.1", reference_type="waste_code", confidence=0.80)
        result = mgr.analyze("1.3.1", classified_references=[ref])
        assert result is not None
        search_opt = [o for o in result.options if o.action == "search"][0]
        assert search_opt.parameters == {"query": "1.3.1"}

    def test_regulation_reference_type(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="2.5.1", reference_type="regulation_reference", confidence=0.70)
        result = mgr.analyze("article 2.5.1", classified_references=[ref])
        assert result is not None
        assert result.reason == "ambiguous_reference"
        # regulation should be first option
        assert result.options[0].tool == "reglementation_tool"

    def test_procedure_chapter_type(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="3.1", reference_type="procedure_chapter", confidence=0.80)
        result = mgr.analyze("chapitre 3.1", classified_references=[ref])
        assert result is not None
        assert result.options[0].tool == "glossaire_tool"

    def test_unknown_reference_type(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="99.99.99", reference_type="unknown_reference", confidence=0.30)
        result = mgr.analyze("99.99.99", classified_references=[ref])
        assert result is not None
        assert result.options[0].tool == "waste_tool"

    def test_article_type(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="5.2", reference_type="article", confidence=0.80)
        result = mgr.analyze("article 5.2", classified_references=[ref])
        assert result is not None
        assert result.options[0].tool == "reglementation_tool"

    def test_question_in_french(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="1.3.1", reference_type="waste_code", confidence=0.80)
        result = mgr.analyze("1.3.1", classified_references=[ref])
        assert result is not None
        assert "interprétations" in result.question
        assert "1.3.1" in result.question


# ---------------------------------------------------------------------------
# Reference type filtering — BSD/BC/BL/tracking excluded
# ---------------------------------------------------------------------------


class TestReferenceTypeFiltering:
    def test_bsd_number_skipped(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="BSD-2024-0001", reference_type="bsd_number", confidence=0.50)
        result = mgr.analyze("BSD-2024-0001", classified_references=[ref])
        assert result is None

    def test_bc_number_skipped(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="BC-2024-0001", reference_type="bc_number", confidence=0.50)
        result = mgr.analyze("BC-2024-0001", classified_references=[ref])
        assert result is None

    def test_bl_number_skipped(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="BL-2024-0001", reference_type="bl_number", confidence=0.50)
        result = mgr.analyze("BL-2024-0001", classified_references=[ref])
        assert result is None

    def test_tracking_number_skipped(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="TRK-0001", reference_type="tracking_number", confidence=0.50)
        result = mgr.analyze("TRK-0001", classified_references=[ref])
        assert result is None

    def test_version_number_skipped(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="v1.3.1", reference_type="version_number", confidence=0.50)
        result = mgr.analyze("v1.3.1", classified_references=[ref])
        assert result is None


# ---------------------------------------------------------------------------
# Low confidence routing
# ---------------------------------------------------------------------------


class TestLowConfidenceRouting:
    def test_best_below_threshold(self, mgr: ClarificationManager) -> None:
        c1 = FakeCandidate(tool="waste_tool", intent="waste_search", confidence=0.35)
        c2 = FakeCandidate(tool="nomenclature_tool", intent="nomenclature_search", confidence=0.30)
        result = mgr.analyze("qsdfjkl", candidates=[c1, c2])
        assert result is not None
        assert result.reason == "low_confidence"

    def test_options_from_candidates(self, mgr: ClarificationManager) -> None:
        c1 = FakeCandidate(tool="waste_tool", intent="waste_search", confidence=0.40)
        c2 = FakeCandidate(tool="bsd_tool", intent="bsd_search", confidence=0.35)
        result = mgr.analyze("query", candidates=[c1, c2])
        assert result is not None
        assert len(result.options) == 2
        assert result.options[0].tool == "waste_tool"
        assert result.options[1].tool == "bsd_tool"

    def test_question_in_french(self, mgr: ClarificationManager) -> None:
        c1 = FakeCandidate(tool="waste_tool", confidence=0.40)
        c2 = FakeCandidate(tool="bsd_tool", confidence=0.35)
        result = mgr.analyze("query", candidates=[c1, c2])
        assert result is not None
        assert "Je ne suis pas sûr" in result.question


# ---------------------------------------------------------------------------
# Close candidates
# ---------------------------------------------------------------------------


class TestCloseCandidates:
    def test_gap_below_threshold(self, mgr: ClarificationManager) -> None:
        c1 = FakeCandidate(tool="waste_tool", confidence=0.82)
        c2 = FakeCandidate(tool="nomenclature_tool", confidence=0.78)
        result = mgr.analyze("nomenclature 15.01", candidates=[c1, c2])
        assert result is not None
        assert result.reason == "close_candidates"

    def test_gap_above_threshold_no_clarification(self, mgr: ClarificationManager) -> None:
        c1 = FakeCandidate(tool="waste_tool", confidence=0.95)
        c2 = FakeCandidate(tool="nomenclature_tool", confidence=0.70)
        result = mgr.analyze("query", candidates=[c1, c2])
        assert result is None

    def test_three_close_candidates(self, mgr: ClarificationManager) -> None:
        c1 = FakeCandidate(tool="waste_tool", confidence=0.80)
        c2 = FakeCandidate(tool="nomenclature_tool", confidence=0.78)
        c3 = FakeCandidate(tool="reglementation_tool", confidence=0.75)
        result = mgr.analyze("query", candidates=[c1, c2, c3])
        assert result is not None
        assert result.reason == "close_candidates"
        assert len(result.options) == 3


# ---------------------------------------------------------------------------
# Priority: references over routing
# ---------------------------------------------------------------------------


class TestPriority:
    def test_reference_checked_before_routing(self, mgr: ClarificationManager) -> None:
        ref = FakeReference(reference="1.3.1", reference_type="waste_code", confidence=0.80)
        c1 = FakeCandidate(tool="waste_tool", confidence=0.95)
        result = mgr.analyze("1.3.1", candidates=[c1], classified_references=[ref])
        assert result is not None
        assert result.reason == "ambiguous_reference"

    def test_no_reference_falls_to_routing(self, mgr: ClarificationManager) -> None:
        c1 = FakeCandidate(tool="waste_tool", confidence=0.40)
        c2 = FakeCandidate(tool="bsd_tool", confidence=0.35)
        result = mgr.analyze("query", candidates=[c1, c2])
        assert result is not None
        assert result.reason == "low_confidence"


# ---------------------------------------------------------------------------
# Crash safety
# ---------------------------------------------------------------------------


class TestCrashSafety:
    def test_none_candidates(self, mgr: ClarificationManager) -> None:
        result = mgr.analyze("test", candidates=None)
        assert result is None

    def test_none_references(self, mgr: ClarificationManager) -> None:
        result = mgr.analyze("test", classified_references=None)
        assert result is None

    def test_empty_message(self, mgr: ClarificationManager) -> None:
        result = mgr.analyze("", candidates=[])
        assert result is None

    def test_broken_candidate_object(self, mgr: ClarificationManager) -> None:
        broken = MagicMock()
        broken.confidence = "not_a_number"
        broken.tool = 123
        broken.intent = None
        result = mgr.analyze("test", candidates=[broken, broken])
        # Should not raise
        assert isinstance(result, (ClarificationResult, type(None)))


# ---------------------------------------------------------------------------
# Candidate → Option conversion
# ---------------------------------------------------------------------------


class TestCandidateToOption:
    def test_known_intent_label(self, mgr: ClarificationManager) -> None:
        c = FakeCandidate(tool="waste_tool", intent="waste_search", confidence=0.90)
        result = mgr.analyze("query", candidates=[c, FakeCandidate(tool="x", confidence=0.30)])
        # Not ambiguous (gap is large), so result is None — test the internal method directly
        opts = ClarificationManager._candidates_to_options([c])
        assert opts[0].label == "consulter les déchets"

    def test_unknown_intent_uses_tool_name(self, mgr: ClarificationManager) -> None:
        c = FakeCandidate(tool="custom_tool", intent="custom_intent", confidence=0.40)
        opts = ClarificationManager._candidates_to_options([c])
        assert opts[0].label == "custom_intent"

    def test_empty_intent_uses_tool_name(self, mgr: ClarificationManager) -> None:
        c = FakeCandidate(tool="waste_tool", intent="", confidence=0.40)
        opts = ClarificationManager._candidates_to_options([c])
        assert opts[0].label == "waste_tool"
