"""
ReportTool — generates operational reports.

Actions: traceability_report, declaration_report, waste_report,
         partner_report, period_report
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class ReportTool(BaseTool):
    """Tool for generating operational reports."""

    name = "rapport_tool"
    description = (
        "Generation de rapports operationnels : traceabilite, "
        "declarations, dechets, partenaires, et rapports par periode."
    )

    def __init__(self) -> None:
        super().__init__()
        self._trace_repo = None
        self._decl_repo = None
        self._nom_repo = None
        self._bsd_repo = None

    @property
    def _traceability_repository(self):
        if self._trace_repo is None:
            from apps.ai_assistant.repositories.traceability_repository import TraceabilityRepository
            self._trace_repo = TraceabilityRepository()
        return self._trace_repo

    @property
    def _declaration_repository(self):
        if self._decl_repo is None:
            from apps.ai_assistant.repositories.declaration_repository import DeclarationRepository
            self._decl_repo = DeclarationRepository()
        return self._decl_repo

    @property
    def _nomenclature_repository(self):
        if self._nom_repo is None:
            from apps.ai_assistant.repositories.nomenclature_repository import NomenclatureRepository
            self._nom_repo = NomenclatureRepository()
        return self._nom_repo

    @property
    def _bsd_repository(self):
        if self._bsd_repo is None:
            from apps.ai_assistant.repositories.bsd_repository import BSDRepository
            self._bsd_repo = BSDRepository()
        return self._bsd_repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "traceability_report": "Generer un rapport de traitebilite operations, quantites et statuts. Parametres optionnels: recuperateur_id (int), date_from (str), date_to (str)",
            "declaration_report": "Generer un rapport des declarations par recuperateur et/ou annee. Parametres optionnels: recuperateur_id (int), annee (str)",
            "waste_report": "Generer un rapport sur les nomenclatures de dechets et leur dangerosite. Parametre optionnel: classe (str) pour filtrer par classe de dechet",
            "partner_report": "Generer un rapport des partenaires d'un recuperateur (generateurs, transporteurs, eliminateurs, valoriseurs). Parametre requis: recuperateur_id (int)",
            "period_report": "Generer un rapport sur une periode definite. Parametres requis: date_from (str, YYYY-MM-DD), date_to (str, YYYY-MM-DD)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "traceability_report", "declaration_report",
                "waste_report", "partner_report", "period_report"
            ], description="Type de rapport")
            .field("recuperateur_id", "int", required=False, description="ID recuperateur")
            .field("date_from", "str", required=False, description="Date debut (YYYY-MM-DD)")
            .field("date_to", "str", required=False, description="Date fin (YYYY-MM-DD)")
            .field("annee", "str", required=False, description="Annee")
            .field("classe", "str", required=False, description="Classe de dechet")
            .field("limit", "int", required=False, default=50, min_value=1, max_value=200)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "traceability_report": self._traceability_report,
            "declaration_report": self._declaration_report,
            "waste_report": self._waste_report,
            "partner_report": self._partner_report,
            "period_report": self._period_report,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _traceability_report(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        records = self._traceability_repository.list(
            limit=params.get("limit", 50),
            recuperateur_id=recuperateur_id
        )

        total_qty = self._traceability_repository.sum_quantities(
            recuperateur_id=recuperateur_id,
            date_from=date_from,
            date_to=date_to
        )

        by_status = self._traceability_repository.count_by_status(recuperateur_id=recuperateur_id)
        by_class = self._traceability_repository.count_by_waste_class(recuperateur_id=recuperateur_id)

        return ToolResultResponse.ok(
            data={
                "records": records,
                "summary": {
                    "total_quantity": total_qty,
                    "by_status": by_status,
                    "by_waste_class": by_class,
                    "record_count": len(records),
                },
                "period": {"from": date_from, "to": date_to},
            },
            message=f"Rapport de traceabilite: {len(records)} operations, {total_qty:.2f} unites"
        )

    def _declaration_report(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        annee = params.get("annee")

        filters = {}
        if recuperateur_id:
            filters["recuperateur_id"] = recuperateur_id
        if annee:
            filters["annee"] = annee

        declarations = self._declaration_repository.list(
            limit=params.get("limit", 50),
            **filters
        )

        total = self._declaration_repository.count(**filters)
        by_status = {}
        for statut in ["BROUILLON", "SOUMISE", "VALIDEE", "ARCHIVEE"]:
            by_status[statut] = self._declaration_repository.count(statut=statut, **filters)

        return ToolResultResponse.ok(
            data={
                "declarations": declarations,
                "summary": {"total": total, "by_status": by_status},
                "annee": annee,
            },
            message=f"Rapport declarations: {total} declaration(s)"
        )

    def _waste_report(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        classe = params.get("classe")

        if classe:
            nomenclatures = self._nomenclature_repository.filter_by_class(classe, limit=params.get("limit", 50))
        else:
            nomenclatures = self._nomenclature_repository.list(limit=params.get("limit", 50))

        dangerous = self._nomenclature_repository.filter_dangerous(limit=50)

        return ToolResultResponse.ok(
            data={
                "nomenclatures": nomenclatures,
                "dangerous_count": len(dangerous),
                "total_count": len(nomenclatures),
                "classe_filter": classe,
            },
            message=f"Rapport dechets: {len(nomenclatures)} codes, {len(dangerous)} dangereux"
        )

    def _partner_report(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        from apps.ai_assistant.repositories.operateur_repository import OperateurRepository
        repo = OperateurRepository()

        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Parametre 'recuperateur_id' requis")

        generateurs = repo.filter_by_recuperateur(recuperateur_id, "GENERATEUR")
        transporteurs = repo.filter_by_recuperateur(recuperateur_id, "TRANSPORTEUR")
        eliminateurs = repo.filter_by_recuperateur(recuperateur_id, "ELIMINATEUR")
        valoriseurs = repo.filter_by_recuperateur(recuperateur_id, "VALORISATEUR")

        return ToolResultResponse.ok(
            data={
                "generateurs": {"count": len(generateurs), "items": generateurs},
                "transporteurs": {"count": len(transporteurs), "items": transporteurs},
                "eliminateurs": {"count": len(eliminateurs), "items": eliminateurs},
                "valoriseurs": {"count": len(valoriseurs), "items": valoriseurs},
            },
            message=f"Rapport partenaires: {len(generateurs)}G, {len(transporteurs)}T, "
                    f"{len(eliminateurs)}E, {len(valoriseurs)}V"
        )

    def _period_report(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        if not date_from or not date_to:
            return ToolResultResponse.fail("Parametres 'date_from' et 'date_to' requis")

        records = self._traceability_repository.filter_by_date_range(
            date_from, date_to, limit=params.get("limit", 100)
        )

        total_qty = self._traceability_repository.sum_quantities(
            date_from=date_from, date_to=date_to
        )

        by_class = self._traceability_repository.count_by_waste_class()

        return ToolResultResponse.ok(
            data={
                "records": records,
                "summary": {
                    "total_quantity": total_qty,
                    "record_count": len(records),
                    "by_waste_class": by_class,
                },
                "period": {"from": date_from, "to": date_to},
            },
            message=f"Rapport periode {date_from} - {date_to}: {len(records)} operations"
        )
