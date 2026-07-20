"""
Django Middleware — integrates enterprise infrastructure into Django.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)


class RequestTrackingMiddleware:
    """Adds request ID and timing to all requests."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.request_id = uuid.uuid4().hex[:12]
        request.start_time = time.monotonic()

        response = self.get_response(request)

        elapsed = (time.monotonic() - request.start_time) * 1000
        response["X-Request-ID"] = request.request_id
        response["X-Response-Time"] = f"{elapsed:.1f}ms"

        return response


class SecurityHeadersMiddleware:
    """Adds security headers to all responses."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class RateLimitMiddleware:
    """Rate limiting middleware using infrastructure RateLimiter."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        self._limiter = None

    @property
    def limiter(self):
        if self._limiter is None:
            from apps.ai_assistant.infrastructure.rate_limiting.limiter import RateLimiter
            self._limiter = RateLimiter()
        return self._limiter

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Only rate-limit AI endpoints
        if not request.path.startswith("/api/assistant/") and not request.path.startswith("/api/ai/"):
            return self.get_response(request)

        key = self._get_key(request)
        result = self.limiter.check(key)

        if not result.allowed:
            return JsonResponse(
                {"success": False, "error": "Rate limit exceeded", "retry_after": result.retry_after},
                status=429,
                headers=result.to_headers(),
            )

        response = self.get_response(request)

        for header, value in result.to_headers().items():
            response[header] = value

        return response

    def _get_key(self, request: HttpRequest) -> str:
        user_id = getattr(request, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "unknown"))
        return f"ip:{ip}"


class AuditMiddleware:
    """Audit logging middleware for AI endpoints."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        self._logger = None

    @property
    def audit_logger(self):
        if self._logger is None:
            from apps.ai_assistant.infrastructure.audit.audit import AuditLogger
            self._logger = AuditLogger()
        return self._logger

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.path.startswith("/api/assistant/"):
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        elapsed = (time.monotonic() - start) * 1000

        from apps.ai_assistant.infrastructure.audit.audit import AuditEvent, AuditAction

        event = AuditEvent(
            action=AuditAction.CHAT if "chat" in request.path else AuditAction.READ,
            user_id=str(getattr(request, "user_id", "")),
            resource_type="api",
            resource_id=request.path,
            ip_address=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_id=getattr(request, "request_id", ""),
            duration_ms=elapsed,
            success=200 <= response.status_code < 400,
        )

        self.audit_logger.log(event)
        return response
