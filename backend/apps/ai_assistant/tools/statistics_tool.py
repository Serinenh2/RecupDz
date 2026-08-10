"""
StatisticsTool — aggregates operational statistics.

Actions: quantities_by_period, quantities_by_waste, status_summary,
         partner_summary, declaration_summary, bsd_summary
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class StatisticsTool(BaseTool):
    """Tool for aggregated operational statistics."""

    name = "statistiques_tool"
    description = (
        "Statistiques et agregats operationnels : quantites traitees "
        "par periode, par type de dechet, par statut, et resume "
        "des declarations et BSD."
    )

    def __init__(self) -> None:
        super().__init__()
        self._trace_repo = None
        self._decl_repo = None
        self._bsd_repo = None
        self._recup_repo = None

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
    def _bsd_repository(self):
        if self._bsd_repo is None:
            from apps.ai_assistant.repositories.bsd_repository import BSDRepository
            self._bsd_repo = BSDRepository()
        return self._bsd_repo

    @property
    def _recuperateur_repository(self):
        if self._recup_repo is None:
            from apps.ai_assistant.repositories.recuperateur_repository import RecuperateurRepository
            self._recup_repo = RecuperateurRepository()
        return self._recup_repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "quantities_by_period": "Calculer la somme des quantites traitees sur une periode. Parametres optionnels: recuperateur_id (int), date_from (str), date_to (str)",
            "quantities_by_waste": "Repartition des quantites par classe de dechet. Parametre optionnel: recuperateur_id (int)",
            "status_summary": "Resume des statuts des operations de traitebilite. Parametre optionnel: recuperateur_id (int)",
            "partner_summary": "Resume des partenaires d'un recuperateur par type. Parametre requis: recuperateur_id (int)",
            "declaration_summary": "Resume des declarations par statut. Parametres optionnels: recuperateur_id (int), annee (str)",
            "bsd_summary": "Resume des BSD (Bordereaux de Suivi des Dechets) par statut. Parametre optionnel: recuperateur_id (int)",
            "recuperateur_overview": "Vue d'ensemble complete d'un recuperateur (traitebilite, BSD, declarations, partenaires). Parametre requis: recuperateur_id (int)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "quantities_by_period", "quantities_by_waste",
                "status_summary", "partner_summary",
                "declaration_summary", "bsd_summary",
                "recuperateur_overview"
            ], description="Action a effectuer")
            .field("recuperateur_id", "int", required=False, description="ID recuperateur (optionnel)")
            .field("date_from", "str", required=False, description="Date debut (YYYY-MM-DD)")
            .field("date_to", "str", required=False, description="Date fin (YYYY-MM-DD)")
            .field("annee", "str", required=False, description="Annee (ex: 2024)")
            .field("days", "int", required=False, default=30, description="Nombre de jours")
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "quantities_by_period": self._quantities_by_period,
            "quantities_by_waste": self._quantities_by_waste,
            "status_summary": self._status_summary,
            "partner_summary": self._partner_summary,
            "declaration_summary": self._declaration_summary,
            "bsd_summary": self._bsd_summary,
            "recuperateur_overview": self._recuperateur_overview,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _quantities_by_period(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        total = self._traceability_repository.sum_quantities(
            recuperateur_id=recuperateur_id,
            date_from=date_from,
            date_to=date_to
        )

        return ToolResultResponse.ok(
            data={
                "total_quantity": total,
                "recuperateur_id": recuperateur_id,
                "date_from": date_from,
                "date_to": date_to,
            },
            message=f"Total: {total:.2f} unites"
        )

    def _quantities_by_waste(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        by_class = self._traceability_repository.count_by_waste_class(recuperateur_id=recuperateur_id)

        return ToolResultResponse.ok(
            data={"by_waste_class": by_class},
            message=f"Repartition par classe de dechet"
        )

    def _status_summary(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        by_status = self._traceability_repository.count_by_status(recuperateur_id=recuperateur_id)

        return ToolResultResponse.ok(
            data={"by_status": by_status},
            message="Resume par statut"
        )

    def _partner_summary(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Parametre 'recuperateur_id' requis")

        from apps.ai_assistant.repositories.operateur_repository import OperateurRepository
        repo = OperateurRepository()

        generateurs = len(repo.filter_by_recuperateur(recuperateur_id, "GENERATEUR"))
        transporteurs = len(repo.filter_by_recuperateur(recuperateur_id, "TRANSPORTEUR"))
        eliminateurs = len(repo.filter_by_recuperateur(recuperateur_id, "ELIMINATEUR"))
        valoriseurs = len(repo.filter_by_recuperateur(recuperateur_id, "VALORISATEUR"))

        return ToolResultResponse.ok(
            data={
                "generateurs": generateurs,
                "transporteurs": transporteurs,
                "eliminateurs": eliminateurs,
                "valoriseurs": valoriseurs,
                "total": generateurs + transporteurs + eliminateurs + valoriseurs,
            },
            message="Resume des partenaires"
        )

    def _declaration_summary(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        annee = params.get("annee")

        filters = {}
        if recuperateur_id:
            filters["recuperateur_id"] = recuperateur_id
        if annee:
            filters["annee"] = annee

        total = self._declaration_repository.count(**filters)
        by_status = {}
        for statut in ["BROUILLON", "SOUMISE", "VALIDEE", "ARCHIVEE"]:
            by_status[statut] = self._declaration_repository.count(statut=statut, **filters)

        return ToolResultResponse.ok(
            data={"total": total, "by_status": by_status, "annee": annee},
            message=f"{total} declaration(s)"
        )

    def _bsd_summary(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        by_status = self._bsd_repository.count_by_status(recuperateur_id=recuperateur_id)

        return ToolResultResponse.ok(
            data={"by_status": by_status},
            message="Resume des BSD"
        )

    def _recuperateur_overview(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        recuperateur_id = params.get("recuperateur_id")
        if not recuperateur_id:
            return ToolResultResponse.fail("Parametre 'recuperateur_id' requis")

        recup = self._recuperateur_repository.get(recuperateur_id)
        if not recup:
            return ToolResultResponse.fail(f"Recuperateur {recuperateur_id} non trouve")

        # Aggregate everything
        from apps.ai_assistant.repositories.operateur_repository import OperateurRepository
        op_repo = OperateurRepository()

        trace_count = self._traceability_repository.count(recuperateur_id=recuperateur_id)
        trace_qty = self._traceability_repository.sum_quantities(recuperateur_id=recuperateur_id)
        bsd_count = self._bsd_repository.count(recuperateur_id=recuperateur_id)
        decl_count = self._declaration_repository.count(recuperateur_id=recuperateur_id)
        partner_count = op_repo.count(recuperateur_id=recuperateur_id)

        return ToolResultResponse.ok(
            data={
                "recuperateur": recup,
                "traceability_records": trace_count,
                "total_quantity": trace_qty,
                "bsd_count": bsd_count,
                "declarations": decl_count,
                "partners": partner_count,
            },
            message=f"Vue d'ensemble de {recup.get('nom_raison_sociale', '')}"
        )
