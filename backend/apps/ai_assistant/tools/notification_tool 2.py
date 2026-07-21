"""
NotificationTool — aggregated alerts from inspections, declarations, BSD, agréments.

Actions: list, get, unread_count, by_type, by_priority, summary
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import ParameterSchema


class NotificationTool(BaseTool):
    """Tool for aggregated system notifications and alerts."""

    name = "notification_tool"
    description = (
        "Notifications et alertes du système. Agège les alertes depuis "
        "les inspections, déclarations, BSD, agréments et traçabilité. "
        "Permet de consulter les notifications par type, priorité, "
        "et d'obtenir un résumé."
    )

    def __init__(self) -> None:
        super().__init__()
        self._repo = None

    @property
    def _repository(self):
        if self._repo is None:
            from apps.ai_assistant.repositories.notification_repository import NotificationRepository
            self._repo = NotificationRepository()
        return self._repo

    @property
    def action_descriptions(self) -> Dict[str, str]:
        return {
            "list": "Lister toutes les notifications. Paramètres optionnels: type (str), priority (str), limit (int)",
            "get": "Obtenir une notification par son ID. Paramètre requis: notification_id (str)",
            "unread_count": "Nombre de notifications non lues. Aucun paramètre requis",
            "by_type": "Filtrer par type. Paramètre requis: type (str parmi: inspection, declaration, agrement, bsd, traceability, system)",
            "by_priority": "Filtrer par priorité. Paramètre requis: priority (str parmi: high, medium, low)",
            "summary": "Résumé des notifications (total, par type, par priorité). Aucun paramètre requis",
        }

    @property
    def parameter_schema(self) -> ParameterSchema:
        from apps.ai_assistant.tools.tool_validator import SchemaBuilder
        return (
            SchemaBuilder()
            .field("action", "str", required=True, enum=[
                "list", "get", "unread_count", "by_type",
                "by_priority", "summary",
            ], description="Action à effectuer")
            .field("notification_id", "str", required=False,
                   description="ID de la notification (pour action=get)")
            .field("type", "str", required=False, enum=[
                "inspection", "declaration", "agrement", "bsd",
                "traceability", "system",
            ], description="Type de notification (pour action=list ou by_type)")
            .field("priority", "str", required=False, enum=[
                "high", "medium", "low",
            ], description="Priorité (pour action=list ou by_priority)")
            .field("limit", "int", required=False, default=20, min_value=1, max_value=100)
            .build()
        )

    def _execute(self, parameters: Dict[str, Any], context: ToolContext) -> ToolResultResponse:
        action = parameters["action"]

        handlers = {
            "list": self._list,
            "get": self._get,
            "unread_count": self._unread_count,
            "by_type": self._by_type,
            "by_priority": self._by_priority,
            "summary": self._summary,
        }

        handler = handlers.get(action)
        if handler is None:
            return ToolResultResponse.fail(f"Action inconnue: {action}")

        return handler(parameters, context)

    def _list(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        type_filter = params.get("type")
        priority_filter = params.get("priority")
        limit = params.get("limit", 20)

        results = self._repository.get_notifications(
            type_filter=type_filter,
            priority_filter=priority_filter,
            limit=limit,
        )
        return ToolResultResponse.ok(
            data={"notifications": results, "count": len(results)},
            message=f"{len(results)} notification(s)",
        )

    def _get(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        notif_id = params.get("notification_id", "")
        if not notif_id:
            return ToolResultResponse.fail("Paramètre 'notification_id' requis")

        all_notifs = self._repository.get_notifications(limit=1000)
        found = next((n for n in all_notifs if n["id"] == notif_id), None)

        if found is None:
            return ToolResultResponse.fail(f"Notification {notif_id} non trouvée")
        return ToolResultResponse.ok(data=found, message="Notification trouvée")

    def _unread_count(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        count = self._repository.get_unread_count()
        return ToolResultResponse.ok(
            data={"unread_count": count},
            message=f"{count} notification(s) non lue(s)",
        )

    def _by_type(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        notif_type = params.get("type", "")
        if not notif_type:
            return ToolResultResponse.fail("Paramètre 'type' requis")

        results = self._repository.get_by_type(notif_type, limit=params.get("limit", 20))
        return ToolResultResponse.ok(
            data={"notifications": results, "count": len(results), "type": notif_type},
            message=f"{len(results)} notification(s) de type {notif_type}",
        )

    def _by_priority(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        priority = params.get("priority", "")
        if not priority:
            return ToolResultResponse.fail("Paramètre 'priority' requis")

        results = self._repository.get_by_priority(priority, limit=params.get("limit", 20))
        return ToolResultResponse.ok(
            data={"notifications": results, "count": len(results), "priority": priority},
            message=f"{len(results)} notification(s) de priorité {priority}",
        )

    def _summary(self, params: Dict[str, Any], ctx: ToolContext) -> ToolResultResponse:
        summary = self._repository.get_summary()
        return ToolResultResponse.ok(
            data=summary,
            message=f"{summary['total']} notification(s) au total",
        )
