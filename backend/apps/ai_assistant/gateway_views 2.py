"""
Gateway Views — REST API endpoints for the Enterprise AI Gateway.

Endpoints:
    POST /api/ai/chat/        — main chat (via AIGateway)
    POST /api/ai/chat/stream/ — SSE streaming chat (via AIGateway)
    GET  /api/ai/health/      — full system health check
    GET  /api/ai/capabilities/ — available intents, tools, languages
    GET  /api/ai/metrics/     — Prometheus-compatible metrics
"""

from __future__ import annotations

import json
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import ModulePermission

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton — AIGateway
# ---------------------------------------------------------------------------

_gateway = None


def _get_gateway():
    global _gateway
    if _gateway is None:
        from apps.ai_assistant.enterprise.container import Container
        from apps.ai_assistant.enterprise.ai_gateway import AIGateway
        container = Container()
        _gateway = AIGateway(container=container)
    return _gateway


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated, ModulePermission])
def chat(request: Request) -> Response:
    """Main chat endpoint — routes through the AI Gateway."""
    message = request.data.get("message", "").strip()
    if not message:
        return Response(
            {"success": False, "error": "Message is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps.ai_assistant.enterprise.ai_gateway import GatewayRequest
    gateway = _get_gateway()

    ai_request = GatewayRequest(
        message=message,
        user_id=str(request.user.id),
        conversation_id=request.data.get("conversation_id", ""),
        session_id=request.data.get("session_id", ""),
        lang=request.data.get("lang", "fr"),
        entity_type=request.data.get("entity_type"),
        entity_id=request.data.get("entity_id"),
    )

    result = gateway.handle_raw(ai_request)
    http_status = status.HTTP_200_OK if result["success"] else status.HTTP_500_INTERNAL_SERVER_ERROR
    return Response(result, status=http_status)


@api_view(["POST"])
@permission_classes([IsAuthenticated, ModulePermission])
def chat_stream(request: Request) -> Response:
    """Streaming chat endpoint (SSE) — via AI Gateway."""
    message = request.data.get("message", "").strip()
    if not message:
        return Response(
            {"success": False, "error": "Message is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from django.http import StreamingHttpResponse
    from apps.ai_assistant.enterprise.ai_gateway import GatewayRequest, RequestSource
    gateway = _get_gateway()

    ai_request = GatewayRequest(
        message=message,
        user_id=str(request.user.id),
        conversation_id=request.data.get("conversation_id", ""),
        session_id=request.data.get("session_id", ""),
        lang=request.data.get("lang", "fr"),
        entity_type=request.data.get("entity_type"),
        entity_id=request.data.get("entity_id"),
        source=RequestSource.STREAM,
    )

    response = StreamingHttpResponse(
        gateway.stream(ai_request),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated, ModulePermission])
def health(request: Request) -> Response:
    """Full system health check — checks all infrastructure components."""
    gateway = _get_gateway()
    return Response(gateway.health_check())


@api_view(["GET"])
@permission_classes([IsAuthenticated, ModulePermission])
def capabilities(request: Request) -> Response:
    """List available capabilities, tools, and intents."""
    gateway = _get_gateway()
    return Response(gateway.capabilities())


@api_view(["GET"])
@permission_classes([IsAuthenticated, ModulePermission])
def metrics(request: Request) -> Response:
    """Prometheus-compatible metrics endpoint."""
    gateway = _get_gateway()
    return Response(gateway.metrics())
