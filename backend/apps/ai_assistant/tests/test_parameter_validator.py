"""
Tests for ToolParameterValidator — pre-execution parameter validation.

Covers:
    - All 22 domain tools and their action-specific required parameters
    - Missing required parameters → structured missing_parameters response
    - OR-logic (authentication, permissions)
    - Unknown tool → pass-through (valid)
    - Unknown action → error
    - Empty parameters → action missing
    - Crash safety → never exposes internal exceptions
    - Data class to_dict() contracts
"""

from __future__ import annotations

import pytest

from apps.ai_assistant.enterprise.parameter_validator import (
    ActionRequirement,
    MissingParameter,
    ToolParameterValidator,
    ValidationResult,
    _is_blank,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def validator() -> ToolParameterValidator:
    return ToolParameterValidator()


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


class TestMissingParameter:
    def test_to_dict_full(self) -> None:
        mp = MissingParameter(name="query", description="Terme de recherche")
        d = mp.to_dict()
        assert d == {"name": "query", "description": "Terme de recherche"}

    def test_to_dict_no_description(self) -> None:
        mp = MissingParameter(name="action")
        d = mp.to_dict()
        assert d == {"name": "action"}

    def test_frozen(self) -> None:
        mp = MissingParameter(name="x")
        with pytest.raises(AttributeError):
            mp.name = "y"  # type: ignore[misc]


class TestValidationResult:
    def test_to_dict_valid(self) -> None:
        r = ValidationResult(valid=True, tool_name="bsd_tool")
        d = r.to_dict()
        assert d["valid"] is True
        assert d["tool_name"] == "bsd_tool"
        assert "missing_parameters" not in d

    def test_to_dict_invalid(self) -> None:
        mp = MissingParameter(name="query")
        r = ValidationResult(valid=False, tool_name="waste_tool", missing_parameters=[mp])
        d = r.to_dict()
        assert d["valid"] is False
        assert d["missing_parameters"] == [{"name": "query"}]

    def test_to_dict_with_action(self) -> None:
        r = ValidationResult(valid=True, tool_name="bsd_tool", action="search")
        d = r.to_dict()
        assert d["action"] == "search"


class TestActionRequirement:
    def test_default_empty(self) -> None:
        r = ActionRequirement(action="list")
        assert r.required == []
        assert r.any_of_groups == []


class TestIsBlank:
    @pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
    def test_blank(self, value: object) -> None:
        assert _is_blank(value) is True

    @pytest.mark.parametrize("value", ["hello", "  hi  ", 0, False, [], "1.3.1"])
    def test_not_blank(self, value: object) -> None:
        assert _is_blank(value) is False


# ---------------------------------------------------------------------------
# Unknown Tool → pass-through
# ---------------------------------------------------------------------------


class TestUnknownTool:
    def test_unknown_tool_is_valid(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("nonexistent_tool", {"action": "search", "query": "test"})
        assert r.valid is True

    def test_unknown_tool_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("nonexistent_tool", {})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Missing Action
# ---------------------------------------------------------------------------


class TestMissingAction:
    @pytest.mark.parametrize(
        "tool_name",
        [
            "traceability_tool",
            "bsd_tool",
            "waste_tool",
            "declaration_tool",
            "nomenclature_tool",
            "entreprise_tool",
            "administration_tool",
            "archive_tool",
            "glossaire_tool",
            "reglementation_tool",
            "inspection_tool",
            "notification_tool",
            "partner_tool",
            "producteur_tool",
            "transporteur_tool",
        ],
    )
    def test_action_required_when_multiple_actions(
        self, validator: ToolParameterValidator, tool_name: str
    ) -> None:
        r = validator.validate(tool_name, {})
        assert r.valid is False
        assert len(r.missing_parameters) == 1
        assert r.missing_parameters[0].name == "action"

    def test_action_not_required_when_single_action(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("rag_tool", {"query": "test"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Unknown Action
# ---------------------------------------------------------------------------


class TestUnknownAction:
    def test_invalid_action(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bsd_tool", {"action": "nonexistent"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "action"
        assert "inconnue" in r.missing_parameters[0].description


# ---------------------------------------------------------------------------
# Traceability Tool
# ---------------------------------------------------------------------------


class TestTraceabilityTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "search"})
        assert r.valid is False
        assert r.action == "search"
        names = [mp.name for mp in r.missing_parameters]
        assert "query" in names

    def test_search_ok(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "search", "query": "test"})
        assert r.valid is True

    def test_get_requires_operation_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "operation_id"

    def test_get_ok(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "get", "operation_id": 1})
        assert r.valid is True

    def test_get_by_numero_requires_numero(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "get_by_numero"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "numero"

    def test_list_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "list"})
        assert r.valid is True

    def test_filter_by_status_requires_statut(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "filter_by_status"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "statut"

    def test_filter_by_waste_code_requires_code_dechet(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("traceability_tool", {"action": "filter_by_waste_code"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "code_dechet"

    def test_filter_by_date_range_requires_both_dates(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("traceability_tool", {"action": "filter_by_date_range"})
        assert r.valid is False
        names = [mp.name for mp in r.missing_parameters]
        assert "date_from" in names
        assert "date_to" in names

    def test_filter_by_date_range_partial_date(self, validator: ToolParameterValidator) -> None:
        r = validator.validate(
            "traceability_tool", {"action": "filter_by_date_range", "date_from": "2024-01-01"}
        )
        assert r.valid is False
        names = [mp.name for mp in r.missing_parameters]
        assert "date_to" in names

    def test_filter_by_date_range_ok(self, validator: ToolParameterValidator) -> None:
        r = validator.validate(
            "traceability_tool",
            {"action": "filter_by_date_range", "date_from": "2024-01-01", "date_to": "2024-12-31"},
        )
        assert r.valid is True

    def test_sum_quantities_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "sum_quantities"})
        assert r.valid is True

    def test_count_by_status_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "count_by_status"})
        assert r.valid is True

    def test_count_by_waste_class_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "count_by_waste_class"})
        assert r.valid is True

    def test_whitespace_query_treated_as_missing(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "search", "query": "   "})
        assert r.valid is False
        assert r.missing_parameters[0].name == "query"

    def test_empty_string_query_treated_as_missing(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "search", "query": ""})
        assert r.valid is False


# ---------------------------------------------------------------------------
# BSD Tool
# ---------------------------------------------------------------------------


class TestBSDTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bsd_tool", {"action": "search"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "query"

    def test_get_requires_bsd_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bsd_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "bsd_id"

    def test_get_by_numero_requires_numero(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bsd_tool", {"action": "get_by_numero"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "numero"

    def test_filter_by_status_requires_statut(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bsd_tool", {"action": "filter_by_status"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "statut"

    def test_filter_by_recuperateur_requires_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bsd_tool", {"action": "filter_by_recuperateur"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "recuperateur_id"

    def test_list_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bsd_tool", {"action": "list"})
        assert r.valid is True

    def test_count_by_status_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bsd_tool", {"action": "count_by_status"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Waste Tool
# ---------------------------------------------------------------------------


class TestWasteTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("waste_tool", {"action": "search"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "query"

    def test_get_requires_nomenclature_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("waste_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "nomenclature_id"

    def test_get_by_code_requires_code(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("waste_tool", {"action": "get_by_code"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "code"

    def test_filter_by_class_requires_classe(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("waste_tool", {"action": "filter_by_class"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "classe"

    def test_dangerous_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("waste_tool", {"action": "dangerous"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# BC Tool
# ---------------------------------------------------------------------------


class TestBCTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bc_tool", {"action": "search"})
        assert r.valid is False

    def test_get_requires_bc_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bc_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "bc_id"

    def test_filter_by_type_requires_type_document(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bc_tool", {"action": "filter_by_type"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "type_document"


# ---------------------------------------------------------------------------
# BL Tool
# ---------------------------------------------------------------------------


class TestBLTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bl_tool", {"action": "search"})
        assert r.valid is False

    def test_get_requires_bl_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("bl_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "bl_id"


# ---------------------------------------------------------------------------
# Declaration Tool
# ---------------------------------------------------------------------------


class TestDeclarationTool:
    def test_create_requires_data(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("declaration_tool", {"action": "create"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "data"

    def test_update_requires_declaration_id_and_data(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("declaration_tool", {"action": "update"})
        assert r.valid is False
        names = [mp.name for mp in r.missing_parameters]
        assert "declaration_id" in names
        assert "data" in names

    def test_update_partial(self, validator: ToolParameterValidator) -> None:
        r = validator.validate(
            "declaration_tool", {"action": "update", "declaration_id": 1}
        )
        assert r.valid is False
        names = [mp.name for mp in r.missing_parameters]
        assert "data" in names

    def test_status_requires_recuperateur_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("declaration_tool", {"action": "status"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "recuperateur_id"


# ---------------------------------------------------------------------------
# Authentication Tool — OR-logic
# ---------------------------------------------------------------------------


class TestAuthenticationTool:
    def test_get_user_requires_user_id_or_username(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("authentication_tool", {"action": "get_user"})
        assert r.valid is False
        assert " OR " in r.missing_parameters[0].name

    def test_get_user_with_user_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("authentication_tool", {"action": "get_user", "user_id": 1})
        assert r.valid is True

    def test_get_user_with_username(self, validator: ToolParameterValidator) -> None:
        r = validator.validate(
            "authentication_tool", {"action": "get_user", "username": "admin"}
        )
        assert r.valid is True

    def test_get_user_with_both(self, validator: ToolParameterValidator) -> None:
        r = validator.validate(
            "authentication_tool",
            {"action": "get_user", "user_id": 1, "username": "admin"},
        )
        assert r.valid is True

    def test_by_role_requires_role(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("authentication_tool", {"action": "by_role"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "role"


# ---------------------------------------------------------------------------
# Permissions Tool — OR-logic + mixed
# ---------------------------------------------------------------------------


class TestPermissionsTool:
    def test_user_permissions_requires_user_id_or_username(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("permissions_tool", {"action": "user_permissions"})
        assert r.valid is False
        assert " OR " in r.missing_parameters[0].name

    def test_user_permissions_with_username(self, validator: ToolParameterValidator) -> None:
        r = validator.validate(
            "permissions_tool", {"action": "user_permissions", "username": "admin"}
        )
        assert r.valid is True

    def test_check_permission_requires_permission_and_identity(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("permissions_tool", {"action": "check_permission"})
        assert r.valid is False
        names = [mp.name for mp in r.missing_parameters]
        assert "permission" in names
        assert any(" OR " in n for n in names)

    def test_check_permission_partial(self, validator: ToolParameterValidator) -> None:
        r = validator.validate(
            "permissions_tool",
            {"action": "check_permission", "permission": "view"},
        )
        assert r.valid is False
        assert any(" OR " in mp.name for mp in r.missing_parameters)

    def test_check_permission_ok(self, validator: ToolParameterValidator) -> None:
        r = validator.validate(
            "permissions_tool",
            {"action": "check_permission", "permission": "view", "user_id": 1},
        )
        assert r.valid is True

    def test_list_roles_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("permissions_tool", {"action": "list_roles"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Nomenclature Tool
# ---------------------------------------------------------------------------


class TestNomenclatureTool:
    def test_search_requires_term(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("nomenclature_tool", {"action": "search"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "term"

    def test_search_by_code_requires_code(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("nomenclature_tool", {"action": "search_by_code"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "code"

    def test_list_children_requires_parent(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("nomenclature_tool", {"action": "list_children"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "parent"


# ---------------------------------------------------------------------------
# Glossary Tool
# ---------------------------------------------------------------------------


class TestGlossaryTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("glossaire_tool", {"action": "search"})
        assert r.valid is False

    def test_get_definition_requires_term(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("glossaire_tool", {"action": "get_definition"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "term"


# ---------------------------------------------------------------------------
# Regulation Tool
# ---------------------------------------------------------------------------


class TestRegulationTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("reglementation_tool", {"action": "search"})
        assert r.valid is False

    def test_get_requires_entry_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("reglementation_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "entry_id"

    def test_glossary_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("reglementation_tool", {"action": "glossary"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Inspection Tool
# ---------------------------------------------------------------------------


class TestInspectionTool:
    def test_get_requires_inspection_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("inspection_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "inspection_id"

    def test_filter_by_recuperateur_requires_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("inspection_tool", {"action": "filter_by_recuperateur"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "recuperateur_id"

    def test_filter_by_resultat_requires_resultat(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("inspection_tool", {"action": "filter_by_resultat"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "resultat"

    def test_list_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("inspection_tool", {"action": "list"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Notification Tool
# ---------------------------------------------------------------------------


class TestNotificationTool:
    def test_get_requires_notification_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("notification_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "notification_id"

    def test_by_type_requires_type(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("notification_tool", {"action": "by_type"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "type"

    def test_by_priority_requires_priority(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("notification_tool", {"action": "by_priority"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "priority"

    def test_list_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("notification_tool", {"action": "list"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Partner Tool
# ---------------------------------------------------------------------------


class TestPartnerTool:
    def test_get_requires_operateur_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("partner_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "operateur_id"

    def test_by_type_requires_type_operateur(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("partner_tool", {"action": "by_type"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "type_operateur"

    def test_list_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("partner_tool", {"action": "list"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Producer Tool
# ---------------------------------------------------------------------------


class TestProducerTool:
    def test_get_requires_operateur_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("producteur_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "operateur_id"

    def test_by_wilaya_requires_wilaya(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("producteur_tool", {"action": "by_wilaya"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "wilaya"


# ---------------------------------------------------------------------------
# Transporter Tool
# ---------------------------------------------------------------------------


class TestTransporterTool:
    def test_get_requires_operateur_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("transporteur_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "operateur_id"


# ---------------------------------------------------------------------------
# Statistics Tool
# ---------------------------------------------------------------------------


class TestStatisticsTool:
    def test_partner_summary_requires_recuperateur_id(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("statistiques_tool", {"action": "partner_summary"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "recuperateur_id"

    def test_recuperateur_overview_requires_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("statistiques_tool", {"action": "recuperateur_overview"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "recuperateur_id"

    def test_quantities_by_period_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("statistiques_tool", {"action": "quantities_by_period"})
        assert r.valid is True

    def test_bsd_summary_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("statistiques_tool", {"action": "bsd_summary"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Report Tool
# ---------------------------------------------------------------------------


class TestReportTool:
    def test_partner_report_requires_recuperateur_id(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("rapport_tool", {"action": "partner_report"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "recuperateur_id"

    def test_period_report_requires_both_dates(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("rapport_tool", {"action": "period_report"})
        assert r.valid is False
        names = [mp.name for mp in r.missing_parameters]
        assert "date_from" in names
        assert "date_to" in names

    def test_traceability_report_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("rapport_tool", {"action": "traceability_report"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Dashboard Tool
# ---------------------------------------------------------------------------


class TestDashboardTool:
    def test_overview_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("dashboard_tool", {"action": "overview"})
        assert r.valid is True

    def test_kpis_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("dashboard_tool", {"action": "kpis"})
        assert r.valid is True

    def test_activity_feed_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("dashboard_tool", {"action": "activity_feed"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# RAG Tool
# ---------------------------------------------------------------------------


class TestRAGTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("rag_tool", {"action": "search"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "query"

    def test_search_ok(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("rag_tool", {"action": "search", "query": "déchet"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Administration Tool
# ---------------------------------------------------------------------------


class TestAdministrationTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("administration_tool", {"action": "search"})
        assert r.valid is False

    def test_get_requires_administration_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("administration_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "administration_id"

    def test_by_type_requires_type(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("administration_tool", {"action": "by_type"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "type_administration"


# ---------------------------------------------------------------------------
# Archive Tool
# ---------------------------------------------------------------------------


class TestArchiveTool:
    def test_search_requires_query(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("archive_tool", {"action": "search"})
        assert r.valid is False

    def test_get_requires_document_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("archive_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "document_id"

    def test_filter_by_categorie_requires_categorie(
        self, validator: ToolParameterValidator
    ) -> None:
        r = validator.validate("archive_tool", {"action": "filter_by_categorie"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "categorie"

    def test_list_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("archive_tool", {"action": "list"})
        assert r.valid is True

    def test_get_recent_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("archive_tool", {"action": "get_recent"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Company (Entreprise) Tool
# ---------------------------------------------------------------------------


class TestCompanyTool:
    def test_get_requires_recuperateur_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("entreprise_tool", {"action": "get"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "recuperateur_id"

    def test_get_full_requires_recuperateur_id(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("entreprise_tool", {"action": "get_full"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "recuperateur_id"

    def test_by_status_requires_statut(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("entreprise_tool", {"action": "by_status"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "statut"

    def test_by_wilaya_requires_wilaya(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("entreprise_tool", {"action": "by_wilaya"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "wilaya"

    def test_agrements_expiring_no_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("entreprise_tool", {"action": "agrements_expiring"})
        assert r.valid is True


# ---------------------------------------------------------------------------
# Multiple missing params
# ---------------------------------------------------------------------------


class TestMultipleMissing:
    def test_two_missing_params(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("rapport_tool", {"action": "period_report"})
        assert r.valid is False
        assert len(r.missing_parameters) == 2
        names = {mp.name for mp in r.missing_parameters}
        assert names == {"date_from", "date_to"}

    def test_filter_by_date_range_two_missing(self, validator: ToolParameterValidator) -> None:
        r = validator.validate("traceability_tool", {"action": "filter_by_date_range"})
        assert r.valid is False
        assert len(r.missing_parameters) == 2


# ---------------------------------------------------------------------------
# Custom registration
# ---------------------------------------------------------------------------


class TestCustomRegistration:
    def test_register_new_tool(self) -> None:
        v = ToolParameterValidator()
        v.register("my_custom_tool", {
            "run": ActionRequirement("run", required=["input_path"]),
        })
        r = v.validate("my_custom_tool", {"action": "run"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "input_path"

    def test_register_ok(self) -> None:
        v = ToolParameterValidator()
        v.register("my_custom_tool", {
            "run": ActionRequirement("run", required=["input_path"]),
        })
        r = v.validate("my_custom_tool", {"action": "run", "input_path": "/data"})
        assert r.valid is True

    def test_override_existing(self) -> None:
        v = ToolParameterValidator()
        v.register("bsd_tool", {
            "new_action": ActionRequirement("new_action", required=["foo"]),
        })
        r = v.validate("bsd_tool", {"action": "new_action"})
        assert r.valid is False
        assert r.missing_parameters[0].name == "foo"
        # old actions still work? No — we replaced the entire dict
        r2 = v.validate("bsd_tool", {"action": "search", "query": "test"})
        assert r2.valid is False  # "search" no longer registered


# ---------------------------------------------------------------------------
# Crash safety
# ---------------------------------------------------------------------------


class TestCrashSafety:
    def test_validator_never_raises(self) -> None:
        v = ToolParameterValidator()
        # Completely broken input
        r = v.validate("bsd_tool", {"action": 12345})
        assert r.valid is False

    def test_none_parameters(self) -> None:
        v = ToolParameterValidator()
        r = v.validate("bsd_tool", None)  # type: ignore[arg-type]
        # Should not crash — returns valid or invalid, never raises
        assert isinstance(r, ValidationResult)


# ---------------------------------------------------------------------------
# to_dict round-trip
# ---------------------------------------------------------------------------


class TestToDictRoundTrip:
    def test_full_result_to_dict(self) -> None:
        r = ValidationResult(
            valid=False,
            tool_name="waste_tool",
            action="get",
            missing_parameters=[
                MissingParameter(name="nomenclature_id", description="ID nomenclature requis"),
            ],
        )
        d = r.to_dict()
        assert d["valid"] is False
        assert d["tool_name"] == "waste_tool"
        assert d["action"] == "get"
        assert d["missing_parameters"] == [
            {"name": "nomenclature_id", "description": "ID nomenclature requis"}
        ]

    def test_valid_result_no_missing_in_dict(self) -> None:
        r = ValidationResult(valid=True, tool_name="bsd_tool")
        d = r.to_dict()
        assert "missing_parameters" not in d
        assert "action" not in d
