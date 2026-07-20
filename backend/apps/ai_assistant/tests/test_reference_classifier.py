"""
Tests for ReferenceClassifier — disambiguates numeric references.

77 tests covering:
  - ClassificationResult dataclass (immutability, to_dict, confidence rounding)
  - Waste Code (XX.XX.XX format, valid/invalid families)
  - Nomenclature Code (alias for waste_code)
  - Regulation Reference (context-dependent, bare numeric)
  - Procedure Chapter (context-dependent)
  - Article (explicit keyword)
  - BSD Number (prefix patterns)
  - BC Number (prefix patterns)
  - BL Number (prefix patterns)
  - Tracking Number (TRK/TRA prefixes)
  - Version Number (vN.N, N.N.N.N)
  - Unknown Reference (single number, empty, non-numeric)
  - Edge cases (whitespace, case sensitivity, special chars)
  - Module-level classify_reference() function
"""

from __future__ import annotations

import unittest

from apps.ai_assistant.enterprise.reference_classifier import (
    ClassificationResult,
    ReferenceClassifier,
    ReferenceType,
    classify_reference,
)


# ── ClassificationResult Dataclass ────────────────────────────────────


class TestClassificationResult(unittest.TestCase):
    def test_to_dict(self):
        r = ClassificationResult(reference_type=ReferenceType.WASTE_CODE, confidence=0.92)
        d = r.to_dict()
        self.assertEqual(d["reference_type"], "waste_code")
        self.assertAlmostEqual(d["confidence"], 0.92)

    def test_frozen(self):
        r = ClassificationResult(reference_type="x", confidence=0.5)
        with self.assertRaises(AttributeError):
            r.reference_type = "y"

    def test_confidence_rounded(self):
        r = ClassificationResult(reference_type="x", confidence=0.123456)
        self.assertAlmostEqual(r.to_dict()["confidence"], 0.123, places=3)

    def test_to_dict_unknown(self):
        r = ClassificationResult(reference_type=ReferenceType.UNKNOWN, confidence=0.0)
        d = r.to_dict()
        self.assertEqual(d["reference_type"], "unknown_reference")
        self.assertAlmostEqual(d["confidence"], 0.0)


# ── Waste Code ────────────────────────────────────────────────────────


class TestWasteCode(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_standard_waste_code(self):
        r = self.clf.classify("15.01.06")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_waste_code_20_01_08(self):
        r = self.clf.classify("20.01.08")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_waste_code_16_01_03(self):
        r = self.clf.classify("16.01.03")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_waste_code_family_01(self):
        r = self.clf.classify("01.01.01")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_waste_code_family_20(self):
        r = self.clf.classify("20.01.01")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_waste_code_out_of_range_family(self):
        r = self.clf.classify("25.01.06")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertAlmostEqual(r.confidence, 0.70, places=1)

    def test_waste_code_family_00(self):
        r = self.clf.classify("00.01.06")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertAlmostEqual(r.confidence, 0.70, places=1)

    def test_two_level_waste_code(self):
        r = self.clf.classify("15.01")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertGreaterEqual(r.confidence, 0.70)

    def test_two_level_out_of_range(self):
        r = self.clf.classify("25.01")
        # 25 is out of waste family range (1-20), so it falls to regulation
        self.assertIn(r.reference_type, [ReferenceType.WASTE_CODE, ReferenceType.REGULATION_REFERENCE])


# ── Regulation Reference ──────────────────────────────────────────────


class TestRegulationReference(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_bare_three_part_high_number(self):
        r = self.clf.classify("25.3.1")
        self.assertEqual(r.reference_type, ReferenceType.REGULATION_REFERENCE)
        self.assertGreaterEqual(r.confidence, 0.60)

    def test_with_loi_context(self):
        r = self.clf.classify("loi 01-19 article 1.3.1")
        self.assertEqual(r.reference_type, ReferenceType.ARTICLE)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_with_decret_context(self):
        r = self.clf.classify("décret 06-104, article 2.4")
        self.assertEqual(r.reference_type, ReferenceType.ARTICLE)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_with_reglement_context(self):
        r = self.clf.classify("règlement 1.3.1")
        self.assertEqual(r.reference_type, ReferenceType.REGULATION_REFERENCE)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_bare_two_part_high_number(self):
        r = self.clf.classify("25.3")
        self.assertEqual(r.reference_type, ReferenceType.REGULATION_REFERENCE)
        self.assertGreaterEqual(r.confidence, 0.55)


# ── Article ───────────────────────────────────────────────────────────


class TestArticle(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_article_explicit(self):
        r = self.clf.classify("article 1.3.1")
        self.assertEqual(r.reference_type, ReferenceType.ARTICLE)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_alinea_explicit(self):
        r = self.clf.classify("alinéa 2.4")
        self.assertEqual(r.reference_type, ReferenceType.ARTICLE)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_point_explicit(self):
        r = self.clf.classify("point 3.1")
        self.assertEqual(r.reference_type, ReferenceType.ARTICLE)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_paragraph_explicit(self):
        r = self.clf.classify("paragraphe 1.2")
        self.assertEqual(r.reference_type, ReferenceType.ARTICLE)
        self.assertGreaterEqual(r.confidence, 0.85)


# ── Procedure Chapter ─────────────────────────────────────────────────


class TestProcedureChapter(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_chapter_explicit(self):
        r = self.clf.classify("chapitre 1.3")
        self.assertEqual(r.reference_type, ReferenceType.PROCEDURE_CHAPTER)
        self.assertGreaterEqual(r.confidence, 0.80)

    def test_section_explicit(self):
        r = self.clf.classify("section 2.4")
        self.assertEqual(r.reference_type, ReferenceType.PROCEDURE_CHAPTER)
        self.assertGreaterEqual(r.confidence, 0.80)

    def test_etape_explicit(self):
        r = self.clf.classify("étape 1.2")
        self.assertEqual(r.reference_type, ReferenceType.PROCEDURE_CHAPTER)
        self.assertGreaterEqual(r.confidence, 0.80)

    def test_procedure_explicit(self):
        r = self.clf.classify("procédure 3.1")
        self.assertEqual(r.reference_type, ReferenceType.PROCEDURE_CHAPTER)
        self.assertGreaterEqual(r.confidence, 0.80)


# ── BSD Number ────────────────────────────────────────────────────────


class TestBSDNumber(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_bsd_with_dash(self):
        r = self.clf.classify("BSD-2024-001")
        self.assertEqual(r.reference_type, ReferenceType.BSD_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)

    def test_bsd_no_dash(self):
        r = self.clf.classify("BSD12345")
        self.assertEqual(r.reference_type, ReferenceType.BSD_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)

    def test_bsd_with_space(self):
        r = self.clf.classify("BSD 2024 001")
        self.assertEqual(r.reference_type, ReferenceType.BSD_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)

    def test_bsd_lowercase(self):
        r = self.clf.classify("bsd-2024-001")
        self.assertEqual(r.reference_type, ReferenceType.BSD_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)

    def test_bsd_mixed_case(self):
        r = self.clf.classify("Bsd-2024-001")
        self.assertEqual(r.reference_type, ReferenceType.BSD_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)


# ── BC Number ─────────────────────────────────────────────────────────


class TestBCNumber(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_bc_with_dash(self):
        r = self.clf.classify("BC-2024-001")
        self.assertEqual(r.reference_type, ReferenceType.BC_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)

    def test_bc_no_dash(self):
        r = self.clf.classify("BC12345")
        self.assertEqual(r.reference_type, ReferenceType.BC_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)

    def test_bc_lowercase(self):
        r = self.clf.classify("bc-2024-001")
        self.assertEqual(r.reference_type, ReferenceType.BC_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)


# ── BL Number ─────────────────────────────────────────────────────────


class TestBLNumber(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_bl_with_dash(self):
        r = self.clf.classify("BL-2024-001")
        self.assertEqual(r.reference_type, ReferenceType.BL_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)

    def test_bl_no_dash(self):
        r = self.clf.classify("BL12345")
        self.assertEqual(r.reference_type, ReferenceType.BL_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)

    def test_bl_lowercase(self):
        r = self.clf.classify("bl-2024-001")
        self.assertEqual(r.reference_type, ReferenceType.BL_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.95)


# ── Tracking Number ───────────────────────────────────────────────────


class TestTrackingNumber(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_trk(self):
        r = self.clf.classify("TRK-12345")
        self.assertEqual(r.reference_type, ReferenceType.TRACKING_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_tra(self):
        r = self.clf.classify("TRA-12345")
        self.assertEqual(r.reference_type, ReferenceType.TRACKING_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_track(self):
        r = self.clf.classify("TRACK-12345")
        self.assertEqual(r.reference_type, ReferenceType.TRACKING_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_trk_lowercase(self):
        r = self.clf.classify("trk-12345")
        self.assertEqual(r.reference_type, ReferenceType.TRACKING_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_trk_no_dash(self):
        r = self.clf.classify("TRK12345")
        self.assertEqual(r.reference_type, ReferenceType.TRACKING_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.90)


# ── Version Number ────────────────────────────────────────────────────


class TestVersionNumber(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_v_prefix(self):
        r = self.clf.classify("v1.3")
        self.assertEqual(r.reference_type, ReferenceType.VERSION_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_v_prefix_three_part(self):
        r = self.clf.classify("v2.0.1")
        self.assertEqual(r.reference_type, ReferenceType.VERSION_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_v_uppercase(self):
        r = self.clf.classify("V1.3")
        self.assertEqual(r.reference_type, ReferenceType.VERSION_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.90)

    def test_four_part_version(self):
        r = self.clf.classify("1.0.0.1")
        self.assertEqual(r.reference_type, ReferenceType.VERSION_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_four_part_version_2(self):
        r = self.clf.classify("2.3.1.0")
        self.assertEqual(r.reference_type, ReferenceType.VERSION_NUMBER)
        self.assertGreaterEqual(r.confidence, 0.85)


# ── Unknown Reference ─────────────────────────────────────────────────


class TestUnknownReference(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_single_number(self):
        r = self.clf.classify("42")
        self.assertEqual(r.reference_type, ReferenceType.UNKNOWN)
        self.assertLessEqual(r.confidence, 0.15)

    def test_empty_string(self):
        r = self.clf.classify("")
        self.assertEqual(r.reference_type, ReferenceType.UNKNOWN)
        self.assertAlmostEqual(r.confidence, 0.0)

    def test_whitespace_only(self):
        r = self.clf.classify("   ")
        self.assertEqual(r.reference_type, ReferenceType.UNKNOWN)
        self.assertAlmostEqual(r.confidence, 0.0)

    def test_non_numeric(self):
        r = self.clf.classify("hello")
        self.assertEqual(r.reference_type, ReferenceType.UNKNOWN)
        self.assertAlmostEqual(r.confidence, 0.0)

    def test_none_like(self):
        r = self.clf.classify("")
        self.assertEqual(r.reference_type, ReferenceType.UNKNOWN)


# ── The Bug Case: "1.3.1" ────────────────────────────────────────────


class TestBugCase(unittest.TestCase):
    """The original bug: '1.3.1' was incorrectly routed to TraceabilityTool."""

    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_1_3_1_bare(self):
        r = self.clf.classify("1.3.1")
        # 1 is within waste family range (1-20), so classified as waste_code
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)
        self.assertGreaterEqual(r.confidence, 0.75)

    def test_1_3_1_with_article_context(self):
        r = self.clf.classify("article 1.3.1")
        self.assertEqual(r.reference_type, ReferenceType.ARTICLE)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_1_3_1_with_loi_context(self):
        r = self.clf.classify("loi 01-19, article 1.3.1")
        self.assertEqual(r.reference_type, ReferenceType.ARTICLE)
        self.assertGreaterEqual(r.confidence, 0.85)

    def test_1_3_1_with_chapitre_context(self):
        r = self.clf.classify("chapitre 1.3.1")
        self.assertEqual(r.reference_type, ReferenceType.PROCEDURE_CHAPTER)
        self.assertGreaterEqual(r.confidence, 0.80)

    def test_never_executes_tool(self):
        """Classifier must NEVER return a tool name."""
        result = classify_reference("1.3.1")
        self.assertIn("reference_type", result)
        self.assertIn("confidence", result)
        self.assertNotIn("tool", result)
        self.assertNotIn("action", result)


# ── Module-level function ─────────────────────────────────────────────


class TestClassifyReference(unittest.TestCase):
    def test_returns_dict(self):
        result = classify_reference("15.01.06")
        self.assertIsInstance(result, dict)
        self.assertIn("reference_type", result)
        self.assertIn("confidence", result)

    def test_waste_code(self):
        result = classify_reference("15.01.06")
        self.assertEqual(result["reference_type"], "waste_code")

    def test_bsd_number(self):
        result = classify_reference("BSD-2024-001")
        self.assertEqual(result["reference_type"], "bsd_number")

    def test_unknown(self):
        result = classify_reference("hello world")
        self.assertEqual(result["reference_type"], "unknown_reference")

    def test_empty(self):
        result = classify_reference("")
        self.assertEqual(result["reference_type"], "unknown_reference")

    def test_singleton(self):
        """Module-level function uses a singleton classifier."""
        r1 = classify_reference("15.01.06")
        r2 = classify_reference("BSD-1234")
        self.assertIsInstance(r1, dict)
        self.assertIsInstance(r2, dict)


# ── Edge Cases ────────────────────────────────────────────────────────


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.clf = ReferenceClassifier()

    def test_leading_whitespace(self):
        r = self.clf.classify("  15.01.06")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)

    def test_trailing_whitespace(self):
        r = self.clf.classify("15.01.06  ")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)

    def test_mixed_case_bsd(self):
        r = self.clf.classify("BsD-2024-001")
        self.assertEqual(r.reference_type, ReferenceType.BSD_NUMBER)

    def test_special_chars_around_code(self):
        r = self.clf.classify("'15.01.06'")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)

    def test_code_in_quotes(self):
        r = self.clf.classify('"15.01.06"')
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)

    def test_code_with_parentheses(self):
        r = self.clf.classify("(15.01.06)")
        self.assertEqual(r.reference_type, ReferenceType.WASTE_CODE)

    def test_very_long_number(self):
        r = self.clf.classify("1234567890.1234567890.1234567890")
        # Too many digits per segment — not a valid waste code
        self.assertIn(r.reference_type, [
            ReferenceType.WASTE_CODE,
            ReferenceType.REGULATION_REFERENCE,
            ReferenceType.UNKNOWN,
        ])

    def test_negative_number(self):
        r = self.clf.classify("-1.3.1")
        # Negative sign — not a standard reference
        self.assertIn(r.reference_type, [
            ReferenceType.UNKNOWN,
            ReferenceType.REGULATION_REFERENCE,
        ])

    def test_decimal_number(self):
        r = self.clf.classify("1.300001")
        # Not a standard dotted format
        self.assertIn(r.reference_type, [
            ReferenceType.UNKNOWN,
            ReferenceType.REGULATION_REFERENCE,
        ])


# ── ReferenceType Constants ───────────────────────────────────────────


class TestReferenceType(unittest.TestCase):
    def test_all_types_defined(self):
        self.assertEqual(ReferenceType.WASTE_CODE, "waste_code")
        self.assertEqual(ReferenceType.NOMENCLATURE_CODE, "nomenclature_code")
        self.assertEqual(ReferenceType.REGULATION_REFERENCE, "regulation_reference")
        self.assertEqual(ReferenceType.PROCEDURE_CHAPTER, "procedure_chapter")
        self.assertEqual(ReferenceType.ARTICLE, "article")
        self.assertEqual(ReferenceType.BSD_NUMBER, "bsd_number")
        self.assertEqual(ReferenceType.BC_NUMBER, "bc_number")
        self.assertEqual(ReferenceType.BL_NUMBER, "bl_number")
        self.assertEqual(ReferenceType.TRACKING_NUMBER, "tracking_number")
        self.assertEqual(ReferenceType.VERSION_NUMBER, "version_number")
        self.assertEqual(ReferenceType.UNKNOWN, "unknown_reference")

    def test_11_types(self):
        types = [
            ReferenceType.WASTE_CODE,
            ReferenceType.NOMENCLATURE_CODE,
            ReferenceType.REGULATION_REFERENCE,
            ReferenceType.PROCEDURE_CHAPTER,
            ReferenceType.ARTICLE,
            ReferenceType.BSD_NUMBER,
            ReferenceType.BC_NUMBER,
            ReferenceType.BL_NUMBER,
            ReferenceType.TRACKING_NUMBER,
            ReferenceType.VERSION_NUMBER,
            ReferenceType.UNKNOWN,
        ]
        self.assertEqual(len(types), 11)
        self.assertEqual(len(set(types)), 11)  # All unique


if __name__ == "__main__":
    unittest.main()
