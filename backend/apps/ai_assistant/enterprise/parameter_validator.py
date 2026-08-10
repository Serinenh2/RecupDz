"""
Tool Parameter Validator — pre-execution parameter validation.

Validates ALL required parameters BEFORE executing any AI tool.
If a parameter is missing, does NOT execute the tool.
Returns structured missing_parameters so the AI asks the user.
Never exposes internal exceptions.

Architecture:
    Orchestrator → ToolParameterValidator.validate() → (pass) → ToolExecutor
                                                     → (fail) → MissingParameters → AI asks user
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MissingParameter:
    """A single missing parameter."""

    name: str
    description: str = ""

    def to_dict(self) -> Dict[str, str]:
        result: Dict[str, str] = {"name": self.name}
        if self.description:
            result["description"] = self.description
        return result


@dataclass(frozen=True)
class ValidationResult:
    """Result of parameter validation."""

    valid: bool
    tool_name: str = ""
    action: str = ""
    missing_parameters: List[MissingParameter] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"valid": self.valid, "tool_name": self.tool_name}
        if self.action:
            result["action"] = self.action
        if self.missing_parameters:
            result["missing_parameters"] = [mp.to_dict() for mp in self.missing_parameters]
        return result


@dataclass(frozen=True)
class ActionRequirement:
    """Required parameters for a specific action.

    Attributes:
        action: Action name.
        required: Simple required parameter names.
        any_of_groups: Groups where at least ONE param must be present.
                       e.g. [["user_id", "username"]] → at least one required.
    """

    action: str
    required: List[str] = field(default_factory=list)
    any_of_groups: List[List[str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class ToolParameterValidator:
    """Validates tool parameters BEFORE execution.

    Flow:
        1. Look up tool in action-requirements registry.
        2. If action present → validate action-specific params.
        3. If unknown tool → skip (pass through).
        4. Return ``ValidationResult`` with ``missing_parameters`` on failure.

    The built-in registry covers all 22 domain tools.
    New tools can be added via ``register()``.
    """

    def __init__(self) -> None:
        self._requirements: Dict[str, Dict[str, ActionRequirement]] = {}
        self._register_defaults()

    # -- public API --------------------------------------------------------

    def register(
        self,
        tool_name: str,
        action_requirements: Dict[str, ActionRequirement],
    ) -> None:
        """Register or override action requirements for a tool."""
        self._requirements[tool_name] = action_requirements

    def validate(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> ValidationResult:
        """Validate parameters before tool execution.

        Args:
            tool_name: Target tool name.
            parameters: Parameters about to be sent to the tool.

        Returns:
            ``ValidationResult`` — ``valid=True`` means safe to execute.
        """
        try:
            return self._validate_internal(tool_name, parameters)
        except Exception as exc:
            logger.error("Parameter validation crashed for '%s': %s", tool_name, exc)
            return ValidationResult(
                valid=False,
                tool_name=tool_name,
                missing_parameters=[
                    MissingParameter(
                        name="validation_error",
                        description="Erreur interne de validation",
                    )
                ],
            )

    # -- internal ----------------------------------------------------------

    def _validate_internal(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> ValidationResult:
        tool_reqs = self._requirements.get(tool_name)
        if tool_reqs is None:
            return ValidationResult(valid=True, tool_name=tool_name)

        action = str(parameters.get("action", "")).strip() if "action" in parameters else ""
        if not action:
            action_field = self._find_action_field(tool_reqs)
            if action_field is not None:
                return ValidationResult(
                    valid=False,
                    tool_name=tool_name,
                    missing_parameters=[
                        MissingParameter(
                            name="action",
                            description=f"Action à effectuer (valeurs possibles: {', '.join(tool_reqs.keys())})",
                        )
                    ],
                )
            return ValidationResult(valid=True, tool_name=tool_name)

        action_req = tool_reqs.get(action)
        if action_req is None:
            valid_actions = ", ".join(sorted(tool_reqs.keys()))
            return ValidationResult(
                valid=False,
                tool_name=tool_name,
                action=action,
                missing_parameters=[
                    MissingParameter(
                        name="action",
                        description=f"Action '{action}' inconnue. Valeurs possibles: {valid_actions}",
                    )
                ],
            )

        return self._validate_action(tool_name, action_req, parameters)

    def _validate_action(
        self,
        tool_name: str,
        action_req: ActionRequirement,
        parameters: Dict[str, Any],
    ) -> ValidationResult:
        missing: List[MissingParameter] = []

        for param in action_req.required:
            value = parameters.get(param)
            if _is_blank(value):
                missing.append(
                    MissingParameter(
                        name=param,
                        description=f"Paramètre '{param}' requis pour l'action '{action_req.action}'",
                    )
                )

        for group in action_req.any_of_groups:
            if not any(not _is_blank(parameters.get(p)) for p in group):
                missing.append(
                    MissingParameter(
                        name=" OR ".join(group),
                        description=f"Au moins un de {', '.join(group)} est requis pour l'action '{action_req.action}'",
                    )
                )

        if missing:
            return ValidationResult(
                valid=False,
                tool_name=tool_name,
                action=action_req.action,
                missing_parameters=missing,
            )

        return ValidationResult(valid=True, tool_name=tool_name, action=action_req.action)

    @staticmethod
    def _find_action_field(tool_reqs: Dict[str, ActionRequirement]) -> Optional[str]:
        """Check if the tool's actions imply an 'action' param is needed."""
        return "action" if len(tool_reqs) > 1 else None

    # -- default registrations ---------------------------------------------

    def _register_defaults(self) -> None:
        for tool_name, actions in _REQUIREMENTS.items():
            self._requirements[tool_name] = actions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_blank(value: Any) -> bool:
    """True if value is None, empty string, or whitespace-only string."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


# ---------------------------------------------------------------------------
# Built-in Action Requirements — all 22 domain tools
# ---------------------------------------------------------------------------

_R = ActionRequirement  # shorthand

_REQUIREMENTS: Dict[str, Dict[str, ActionRequirement]] = {
    # ── Traceability ──────────────────────────────────────────────────────
    "traceability_tool": {
        "search": _R("search", required=["query"]),
        "get": _R("get", required=["operation_id"]),
        "get_by_numero": _R("get_by_numero", required=["numero"]),
        "list": _R("list"),
        "filter_by_status": _R("filter_by_status", required=["statut"]),
        "filter_by_waste_code": _R("filter_by_waste_code", required=["code_dechet"]),
        "filter_by_date_range": _R("filter_by_date_range", required=["date_from", "date_to"]),
        "sum_quantities": _R("sum_quantities"),
        "count_by_status": _R("count_by_status"),
        "count_by_waste_class": _R("count_by_waste_class"),
    },
    # ── BSD ───────────────────────────────────────────────────────────────
    "bsd_tool": {
        "search": _R("search", required=["query"]),
        "get": _R("get", required=["bsd_id"]),
        "get_by_numero": _R("get_by_numero", required=["numero"]),
        "list": _R("list"),
        "filter_by_status": _R("filter_by_status", required=["statut"]),
        "filter_by_recuperateur": _R("filter_by_recuperateur", required=["recuperateur_id"]),
        "count_by_status": _R("count_by_status"),
    },
    # ── BC ────────────────────────────────────────────────────────────────
    "bc_tool": {
        "search": _R("search", required=["query"]),
        "get": _R("get", required=["bc_id"]),
        "get_by_numero": _R("get_by_numero", required=["numero"]),
        "list": _R("list"),
        "filter_by_type": _R("filter_by_type", required=["type_document"]),
        "filter_by_status": _R("filter_by_status", required=["statut"]),
        "filter_by_recuperateur": _R("filter_by_recuperateur", required=["recuperateur_id"]),
    },
    # ── BL ────────────────────────────────────────────────────────────────
    "bl_tool": {
        "search": _R("search", required=["query"]),
        "get": _R("get", required=["bl_id"]),
        "get_by_numero": _R("get_by_numero", required=["numero"]),
        "list": _R("list"),
        "filter_by_status": _R("filter_by_status", required=["statut"]),
        "filter_by_recuperateur": _R("filter_by_recuperateur", required=["recuperateur_id"]),
    },
    # ── Waste ─────────────────────────────────────────────────────────────
    "waste_tool": {
        "search": _R("search", required=["query"]),
        "get": _R("get", required=["nomenclature_id"]),
        "get_by_code": _R("get_by_code", required=["code"]),
        "list": _R("list"),
        "get_designations": _R("get_designations", required=["nomenclature_id"]),
        "filter_by_class": _R("filter_by_class", required=["classe"]),
        "dangerous": _R("dangerous"),
    },
    # ── Declaration ───────────────────────────────────────────────────────
    "declaration_tool": {
        "search": _R("search", required=["query"]),
        "list": _R("list"),
        "get": _R("get", required=["declaration_id"]),
        "create": _R("create", required=["data"]),
        "update": _R("update", required=["declaration_id", "data"]),
        "status": _R("status", required=["recuperateur_id"]),
    },
    # ── Nomenclature ──────────────────────────────────────────────────────
    "nomenclature_tool": {
        "search": _R("search", required=["term"]),
        "search_by_code": _R("search_by_code", required=["code"]),
        "search_similar": _R("search_similar", required=["term"]),
        "list_children": _R("list_children", required=["parent"]),
    },
    # ── Company (Recuperateur) ────────────────────────────────────────────
    "entreprise_tool": {
        "search": _R("search", required=["query"]),
        "list": _R("list"),
        "get": _R("get", required=["recuperateur_id"]),
        "get_full": _R("get_full", required=["recuperateur_id"]),
        "by_status": _R("by_status", required=["statut"]),
        "by_wilaya": _R("by_wilaya", required=["wilaya"]),
        "agrements_expiring": _R("agrements_expiring"),
    },
    # ── Administration ────────────────────────────────────────────────────
    "administration_tool": {
        "search": _R("search", required=["query"]),
        "get": _R("get", required=["administration_id"]),
        "by_type": _R("by_type", required=["type_administration"]),
        "by_wilaya": _R("by_wilaya", required=["wilaya"]),
        "by_status": _R("by_status", required=["statut"]),
    },
    # ── Archive ───────────────────────────────────────────────────────────
    "archive_tool": {
        "search": _R("search", required=["query"]),
        "get": _R("get", required=["document_id"]),
        "list": _R("list"),
        "filter_by_categorie": _R("filter_by_categorie", required=["categorie"]),
        "get_recent": _R("get_recent"),
    },
    # ── Authentication ────────────────────────────────────────────────────
    "authentication_tool": {
        "get_user": _R("get_user", any_of_groups=[["user_id", "username"]]),
        "search": _R("search", required=["query"]),
        "by_role": _R("by_role", required=["role"]),
        "by_wilaya": _R("by_wilaya", required=["wilaya"]),
        "profile": _R("profile"),
    },
    # ── Permissions ───────────────────────────────────────────────────────
    "permissions_tool": {
        "list_roles": _R("list_roles"),
        "role_detail": _R("role_detail", required=["role"]),
        "user_permissions": _R(
            "user_permissions",
            any_of_groups=[["user_id", "username"]],
        ),
        "check_permission": _R(
            "check_permission",
            required=["permission"],
            any_of_groups=[["user_id", "username"]],
        ),
    },
    # ── Glossary ──────────────────────────────────────────────────────────
    "glossaire_tool": {
        "search": _R("search", required=["query"]),
        "get_definition": _R("get_definition", required=["term"]),
        "search_similar": _R("search_similar", required=["term"]),
    },
    # ── Regulation ────────────────────────────────────────────────────────
    "reglementation_tool": {
        "search": _R("search", required=["query"]),
        "get": _R("get", required=["entry_id"]),
        "by_category": _R("by_category", required=["categorie"]),
        "by_reference": _R("by_reference", required=["reference"]),
        "glossary": _R("glossary"),
    },
    # ── Inspection ────────────────────────────────────────────────────────
    "inspection_tool": {
        "get": _R("get", required=["inspection_id"]),
        "list": _R("list"),
        "filter_by_recuperateur": _R("filter_by_recuperateur", required=["recuperateur_id"]),
        "filter_by_resultat": _R("filter_by_resultat", required=["resultat"]),
        "filter_by_type": _R("filter_by_type", required=["type_inspection"]),
    },
    # ── Notification ──────────────────────────────────────────────────────
    "notification_tool": {
        "list": _R("list"),
        "get": _R("get", required=["notification_id"]),
        "unread_count": _R("unread_count"),
        "by_type": _R("by_type", required=["type"]),
        "by_priority": _R("by_priority", required=["priority"]),
        "summary": _R("summary"),
    },
    # ── Partner (Operateur) ──────────────────────────────────────────────
    "partner_tool": {
        "search": _R("search", required=["query"]),
        "list": _R("list"),
        "get": _R("get", required=["operateur_id"]),
        "by_type": _R("by_type", required=["type_operateur"]),
        "by_wilaya": _R("by_wilaya", required=["wilaya"]),
    },
    # ── Producer ──────────────────────────────────────────────────────────
    "producteur_tool": {
        "search": _R("search", required=["query"]),
        "list": _R("list"),
        "get": _R("get", required=["operateur_id"]),
        "by_wilaya": _R("by_wilaya", required=["wilaya"]),
        "by_recuperateur": _R("by_recuperateur", required=["recuperateur_id"]),
    },
    # ── Transporter ───────────────────────────────────────────────────────
    "transporteur_tool": {
        "search": _R("search", required=["query"]),
        "list": _R("list"),
        "get": _R("get", required=["operateur_id"]),
        "by_wilaya": _R("by_wilaya", required=["wilaya"]),
        "by_recuperateur": _R("by_recuperateur", required=["recuperateur_id"]),
    },
    # ── Statistics ────────────────────────────────────────────────────────
    "statistiques_tool": {
        "quantities_by_period": _R("quantities_by_period"),
        "quantities_by_waste": _R("quantities_by_waste"),
        "status_summary": _R("status_summary"),
        "partner_summary": _R("partner_summary", required=["recuperateur_id"]),
        "declaration_summary": _R("declaration_summary"),
        "bsd_summary": _R("bsd_summary"),
        "recuperateur_overview": _R("recuperateur_overview", required=["recuperateur_id"]),
    },
    # ── Report ────────────────────────────────────────────────────────────
    "rapport_tool": {
        "traceability_report": _R("traceability_report"),
        "declaration_report": _R("declaration_report"),
        "waste_report": _R("waste_report"),
        "partner_report": _R("partner_report", required=["recuperateur_id"]),
        "period_report": _R("period_report", required=["date_from", "date_to"]),
    },
    # ── Dashboard ─────────────────────────────────────────────────────────
    "dashboard_tool": {
        "overview": _R("overview"),
        "kpis": _R("kpis"),
        "by_period": _R("by_period"),
        "by_wilaya": _R("by_wilaya"),
        "activity_feed": _R("activity_feed"),
    },
    # ── RAG ───────────────────────────────────────────────────────────────
    "rag_tool": {
        "search": _R("search", required=["query"]),
    },
}
