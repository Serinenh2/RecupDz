"""
DashboardTool — aggregated KPIs and metrics across all business modules.

Actions: overview, kpis, by_period, by_wilaya, activity_feed
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class DashboardTool(BaseTool):
    """Tool for system-wide KPIs, metrics, and activity monitoring."""

    name = "dashboard_tool"
    description = (
        "Tableau de bord et indicateurs clés du système. "
        "Fournit une vue d'ensemble des récupérateurs, déclarations, "
        "BSD, traçabilité, inspections, et de l'activité récente."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.dashboard_repository import DashboardRepository
            self._repo = DashboardRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "overview": "Vue d'ensemble globale (compteurs toutes catégories). Aucun paramètre requis",
            "kpis": "Indicateurs clés détaillés avec statuts. Aucun paramètre requis",
            "by_period": "Activité des N derniers jours. Paramètre optionnel: days (int, défaut=30)",
            "by_wilaya": "Répartition des récupérateurs par wilaya. Paramètre optionnel: limit (int, défaut=20)",
            "activity_feed": "Fil d'activité récent. Paramètre optionnel: limit (int, défaut=20)",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "overview", "kpis", "by_period", "by_wilaya", "activity_feed",
            ], description="Action à effectuer")
            .field("days", "int", required=False, default=30, min_value=1, max_value=365,
                   description="Nombre de jours (pour action=by_period)")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100,
                   description="Limite de résultats (pour action=by_wilaya ou activity_feed)")
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "overview": self._overview,
            "kpis": self._kpis,
            "by_period": self._by_period,
            "by_wilaya": self._by_wilaya,
            "activity_feed": self._activity_feed,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _overview(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        data = self._repository.get_overview()
        return ToolResultResponse.ok(
            data=data,
            message=f"Vue d'ensemble du {data.get('date', 'N/A')}",
        )

    def _kpis(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        kpis = self._repository.get_kpis()
        return ToolResultResponse.ok(
            data={"kpis": kpis, "count": len(kpis)},
            message=f"{len(kpis)} indicateur(s) clé(s)",
        )

    def _by_period(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        days = params.get("days", 30)
        data = self._repository.get_by_period(days=days)
        return ToolResultResponse.ok(
            data=data,
            message=f"Activité des {days} derniers jours",
        )

    def _by_wilaya(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        limit = params.get("limit", 20)
        data = self._repository.get_by_wilaya(limit=limit)
        return ToolResultResponse.ok(
            data={"wilayas": data, "count": len(data)},
            message=f"Répartition par {len(data)} wilaya(s)",
        )

    def _activity_feed(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        limit = params.get("limit", 20)
        data = self._repository.get_activity_feed(limit=limit)
        return ToolResultResponse.ok(
            data={"activities": data, "count": len(data)},
            message=f"{len(data)} activité(s) récente(s)",
        )
