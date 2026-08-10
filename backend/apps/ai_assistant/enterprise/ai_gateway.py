"""
AI Gateway — single entry point for every AI request.

Responsibilities:
    1. Receive user request (validate, sanitize, enrich)
    2. Build AI Context (conversation history, user profile, entity context)
    3. Call AgentOrchestrator (mandatory 7-step workflow)
    4. Return structured response (message, data, follow-ups, metadata)

This is the ONLY class that external callers (views, API, SDK) should use.
All AI logic flows through this gateway.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, List, Optional

from apps.ai_assistant.infrastructure.audit.audit import AuditAction

logger = logging.getLogger(__name__)


# ── Request / Response contracts ──────────────────────────────────────


class RequestSource(str, Enum):
    API = "api"
    CLI = "cli"
    WEBHOOK = "webhook"
    STREAM = "stream"


@dataclass(frozen=True)
class GatewayRequest:
    """Immutable inbound request — the ONLY input to the gateway."""
    message: str
    user_id: str = ""
    conversation_id: str = ""
    session_id: str = ""
    lang: str = "fr"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    source: RequestSource = RequestSource.API
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayResponse:
    """Structured outbound response — the ONLY output from the gateway."""
    success: bool
    message: str
    data: Any = None
    followups: List[str] = field(default_factory=list)
    request_id: str = ""
    intent: str = ""
    confidence: float = 0.0
    tool_used: Optional[str] = None
    tool_action: str = ""
    selection_source: str = ""
    elapsed_ms: float = 0.0
    trace_id: str = ""
    cached: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data or {},
            "followups": self.followups,
            "meta": {
                "request_id": self.request_id,
                "intent": self.intent,
                "confidence": self.confidence,
                "tool_used": self.tool_used,
                "tool_action": self.tool_action,
                "selection_source": self.selection_source,
                "elapsed_ms": round(self.elapsed_ms, 1),
                "trace_id": self.trace_id,
                "cached": self.cached,
                "error": self.error,
            },
        }


# ── Gateway Validators ───────────────────────────────────────────────


class GatewayValidationError(Exception):
    """Raised when request validation fails."""
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class GatewayValidator:
    """Validates and sanitizes incoming requests."""

    MAX_MESSAGE_LENGTH = 5000
    MIN_MESSAGE_LENGTH = 1
    ALLOWED_LANGS = {"fr", "ar", "en"}
    FORBIDDEN_PATTERNS = ["<script", "javascript:", "onerror=", "onload="]

    def validate(self, request: GatewayRequest) -> GatewayRequest:
        """
        Validate the request. Raises GatewayValidationError on failure.
        Returns sanitized request on success.
        """
        # Message
        if not request.message or not request.message.strip():
            raise GatewayValidationError("message", "Message is required and cannot be empty.")

        message = request.message.strip()
        if len(message) > self.MAX_MESSAGE_LENGTH:
            raise GatewayValidationError(
                "message", f"Message exceeds maximum length of {self.MAX_MESSAGE_LENGTH} characters.",
            )

        # Check for injection attempts
        msg_lower = message.lower()
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in msg_lower:
                raise GatewayValidationError("message", "Message contains prohibited content.")

        # Sanitize extra parameters
        sanitizer = None
        if request.extra:
            from apps.ai_assistant.infrastructure.security.sanitizer import InputSanitizer
            sanitizer = InputSanitizer()
            sanitized_extra = sanitizer.sanitize_dict(request.extra)
        else:
            sanitized_extra = request.extra

        # Language
        if request.lang not in self.ALLOWED_LANGS:
            raise GatewayValidationError(
                "lang", f"Unsupported language '{request.lang}'. Allowed: {self.ALLOWED_LANGS}",
            )

        # User ID
        if not request.user_id:
            raise GatewayValidationError("user_id", "User ID is required.")

        return GatewayRequest(
            message=message,
            user_id=request.user_id,
            conversation_id=request.conversation_id or f"conv_{uuid.uuid4().hex[:8]}",
            session_id=request.session_id,
            lang=request.lang,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            source=request.source,
            extra=sanitized_extra,
        )


# ── Gateway Context Builder ──────────────────────────────────────────


class GatewayContextBuilder:
    """Builds the AI context dict from a validated GatewayRequest."""

    def build(self, request: GatewayRequest) -> Dict[str, Any]:
        """Build the contexte_supp dict for the orchestrator."""
        context: Dict[str, Any] = {
            "conversation_id": request.conversation_id,
            "session_id": request.session_id,
            "lang": request.lang,
            "source": request.source.value,
        }

        if request.entity_type:
            context["entity_type"] = request.entity_type
        if request.entity_id:
            context["entity_id"] = request.entity_id

        # Merge any extra context
        context.update(request.extra)

        return context


# ── AI Gateway ───────────────────────────────────────────────────────


class AIGateway:
    """
    Single entry point for every AI request.

    Flow:
        1. Validate + sanitize request
        2. Build AI context
        3. Call AgentOrchestrator (7-step workflow)
        4. Format + return response

    Usage:
        gateway = AIGateway(container)
        response = gateway.handle(GatewayRequest(
            message="Quels sont les déchets dangereux ?",
            user_id="123",
        ))
        print(response.message, response.followups)
    """

    def __init__(self, container: Any) -> None:
        self._c = container
        self._validator = GatewayValidator()
        self._context_builder = GatewayContextBuilder()
        self._orchestrator = None

    @property
    def _orch(self):
        if self._orchestrator is None:
            self._orchestrator = self._c.orchestrator
        return self._orchestrator

    # ==================================================================
    # Public API
    # ==================================================================

    def handle(self, request: GatewayRequest) -> GatewayResponse:
        """
        Process a user request through the full AI workflow.

        Returns GatewayResponse with message, data, follow-ups, and metadata.
        """
        start = time.monotonic()

        # ── 1. Validate ──────────────────────────────────────────────
        try:
            validated = self._validator.validate(request)
        except GatewayValidationError as exc:
            elapsed = (time.monotonic() - start) * 1000
            self._c.metrics.inc_counter("ai.gateway.validation_error")
            self._c.audit.log_simple(
                action=AuditAction.ERROR,
                user_id=request.user_id,
                resource_type="gateway_validation",
                resource_id="",
                error_message=str(exc),
            )
            return GatewayResponse(
                success=False,
                message=f"Erreur de validation: {exc.message}",
                request_id="",
                elapsed_ms=elapsed,
                error=str(exc),
            )

        request_id = uuid.uuid4().hex[:12]

        # ── 2. Build context ─────────────────────────────────────────
        context = self._context_builder.build(validated)

        # ── 3. Call orchestrator ──────────────────────────────────────
        try:
            result = self._orch.orchestrate(
                message=validated.message,
                user_id=validated.user_id,
                conversation_id=validated.conversation_id,
                contexte_supp=context,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.exception("Gateway orchestrator error: %s", exc)
            self._c.metrics.inc_counter("ai.gateway.orchestrator_error")
            self._c.audit.log_simple(
                action=AuditAction.ERROR,
                user_id=validated.user_id,
                resource_type="gateway",
                resource_id=request_id,
                error_message=str(exc),
            )
            return GatewayResponse(
                success=False,
                message="Une erreur interne est survenue. Veuillez réessayer.",
                request_id=request_id,
                elapsed_ms=elapsed,
                error=str(exc),
            )

        # ── 4. Format response ───────────────────────────────────────
        elapsed = (time.monotonic() - start) * 1000
        meta = result.get("meta", {})

        response = GatewayResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            data=result.get("data"),
            followups=result.get("followups", []),
            request_id=meta.get("request_id", request_id),
            intent=meta.get("intent", ""),
            confidence=meta.get("confidence", 0.0),
            tool_used=meta.get("tool_used"),
            tool_action=meta.get("tool_action", ""),
            selection_source=meta.get("selection_source", ""),
            elapsed_ms=elapsed,
            trace_id=meta.get("trace_id", ""),
            cached=meta.get("cached", False),
            error=meta.get("error"),
        )

        # ── 5. Observe ───────────────────────────────────────────────
        self._c.metrics.inc_counter("ai.gateway.requests.total")
        self._c.metrics.record_request("ai.gateway", "POST", 200, elapsed)

        return response

    def handle_raw(self, request: GatewayRequest) -> Dict[str, Any]:
        """Handle and return dict (convenience for views that need raw dict)."""
        return self.handle(request).to_dict()

    def stream(self, request: GatewayRequest) -> Generator[str, None, None]:
        """
        Handle request with SSE streaming.

        Yields SSE-formatted strings:
            data: {"chunk": "...", "done": false}
            data: {"chunk": "...", "done": true, "followups": [...]}
        """
        start = time.monotonic()

        # ── 1. Validate ──────────────────────────────────────────────
        try:
            validated = self._validator.validate(request)
        except GatewayValidationError as exc:
            yield f"data: {json.dumps({'success': False, 'error': str(exc), 'done': True})}\n\n"
            return

        # ── 2. Build context ─────────────────────────────────────────
        context = self._context_builder.build(validated)
        request_id = uuid.uuid4().hex[:12]

        # ── 3. Call orchestrator ──────────────────────────────────────
        try:
            result = self._orch.orchestrate(
                message=validated.message,
                user_id=validated.user_id,
                conversation_id=validated.conversation_id,
                contexte_supp=context,
            )
        except Exception as exc:
            logger.exception("Gateway stream error: %s", exc)
            yield f"data: {json.dumps({'success': False, 'error': str(exc), 'done': True})}\n\n"
            return

        # ── 4. Stream response ───────────────────────────────────────
        meta = result.get("meta", {})
        response_dict = {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "data": result.get("data"),
            "done": True,
            "followups": result.get("followups", []),
            "meta": {
                "request_id": meta.get("request_id", request_id),
                "intent": meta.get("intent", ""),
                "confidence": meta.get("confidence", 0.0),
                "tool_used": meta.get("tool_used"),
                "tool_action": meta.get("tool_action", ""),
                "elapsed_ms": round((time.monotonic() - start) * 1000, 1),
                "trace_id": meta.get("trace_id", ""),
            },
        }

        yield f"data: {json.dumps(response_dict, ensure_ascii=False)}\n\n"

        self._c.metrics.inc_counter("ai.gateway.stream_requests.total")

    # ── Health / Capabilities ─────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Full system health check."""
        return self._c.health_check()

    def capabilities(self) -> Dict[str, Any]:
        """List available capabilities."""
        return {
            "intents": [
                {"name": "greeting", "description": "Greetings and pleasantries"},
                {"name": "question", "description": "Questions about waste management"},
                {"name": "waste_search", "description": "Search nomenclature and waste codes"},
                {"name": "nomenclature", "description": "Nomenclature lookups"},
                {"name": "declaration", "description": "Declaration assistance (DSD, BSD)"},
                {"name": "company", "description": "Company and partner information"},
                {"name": "partner", "description": "Partner and operator lookups"},
                {"name": "statistics", "description": "Statistics and metrics"},
                {"name": "report", "description": "Reporting and summaries"},
                {"name": "regulation", "description": "Regulatory information"},
                {"name": "unknown", "description": "Unrecognized queries"},
            ],
            "tools": self._c.tool_registry.list_names(),
            "languages": ["fr", "ar", "en"],
            "version": "2.0.0",
        }

    def metrics(self) -> Dict[str, Any]:
        """Prometheus-compatible metrics."""
        return {
            "metrics": self._c.metrics.to_dict(),
            "tracing": self._c.tracer.stats(),
            "audit": self._c.audit.stats(),
            "cache": self._c.cache.stats(),
        }
