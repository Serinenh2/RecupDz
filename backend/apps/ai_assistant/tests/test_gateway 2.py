"""
Tests for AI Gateway — the single entry point.
"""

import pytest
from unittest.mock import MagicMock, patch

from apps.ai_assistant.enterprise.ai_gateway import (
    AIGateway,
    GatewayContextBuilder,
    GatewayRequest,
    GatewayResponse,
    GatewayValidationError,
    GatewayValidator,
    RequestSource,
)


# ── GatewayRequest ────────────────────────────────────────────────────


class TestGatewayRequest:
    def test_default_values(self):
        req = GatewayRequest(message="hello", user_id="1")
        assert req.message == "hello"
        assert req.user_id == "1"
        assert req.conversation_id == ""
        assert req.lang == "fr"
        assert req.source == RequestSource.API
        assert req.extra == {}

    def test_custom_values(self):
        req = GatewayRequest(
            message="test",
            user_id="42",
            conversation_id="abc",
            lang="en",
            entity_type="bsd",
            entity_id="10",
            source=RequestSource.CLI,
        )
        assert req.conversation_id == "abc"
        assert req.entity_type == "bsd"

    def test_frozen(self):
        req = GatewayRequest(message="test", user_id="1")
        with pytest.raises(AttributeError):
            req.message = "changed"


# ── GatewayValidator ──────────────────────────────────────────────────


class TestGatewayValidator:
    def setup_method(self):
        self.v = GatewayValidator()

    def test_valid_request(self):
        req = GatewayRequest(message="Bonjour", user_id="1")
        validated = self.v.validate(req)
        assert validated.message == "Bonjour"
        assert validated.user_id == "1"
        assert validated.conversation_id.startswith("conv_")

    def test_empty_message(self):
        req = GatewayRequest(message="", user_id="1")
        with pytest.raises(GatewayValidationError) as exc:
            self.v.validate(req)
        assert exc.value.field == "message"

    def test_whitespace_message(self):
        req = GatewayRequest(message="   ", user_id="1")
        with pytest.raises(GatewayValidationError):
            self.v.validate(req)

    def test_message_too_long(self):
        req = GatewayRequest(message="x" * 5001, user_id="1")
        with pytest.raises(GatewayValidationError):
            self.v.validate(req)

    def test_script_injection(self):
        req = GatewayRequest(message="<script>alert(1)</script>", user_id="1")
        with pytest.raises(GatewayValidationError):
            self.v.validate(req)

    def test_javascript_injection(self):
        req = GatewayRequest(message="javascript:alert(1)", user_id="1")
        with pytest.raises(GatewayValidationError):
            self.v.validate(req)

    def test_invalid_lang(self):
        req = GatewayRequest(message="test", user_id="1", lang="zz")
        with pytest.raises(GatewayValidationError):
            self.v.validate(req)

    def test_missing_user_id(self):
        req = GatewayRequest(message="test", user_id="")
        with pytest.raises(GatewayValidationError):
            self.v.validate(req)

    def test_preserves_conversation_id(self):
        req = GatewayRequest(message="test", user_id="1", conversation_id="myconv")
        validated = self.v.validate(req)
        assert validated.conversation_id == "myconv"


# ── GatewayContextBuilder ─────────────────────────────────────────────


class TestGatewayContextBuilder:
    def setup_method(self):
        self.b = GatewayContextBuilder()

    def test_basic_context(self):
        req = GatewayRequest(message="test", user_id="1", conversation_id="c1")
        ctx = self.b.build(req)
        assert ctx["conversation_id"] == "c1"
        assert ctx["lang"] == "fr"

    def test_entity_context(self):
        req = GatewayRequest(
            message="test", user_id="1",
            entity_type="bsd", entity_id="99",
        )
        ctx = self.b.build(req)
        assert ctx["entity_type"] == "bsd"
        assert ctx["entity_id"] == "99"

    def test_extra_merged(self):
        req = GatewayRequest(message="test", user_id="1", extra={"foo": "bar"})
        ctx = self.b.build(req)
        assert ctx["foo"] == "bar"


# ── GatewayResponse ───────────────────────────────────────────────────


class TestGatewayResponse:
    def test_to_dict(self):
        resp = GatewayResponse(
            success=True,
            message="hello",
            followups=["a", "b"],
            intent="greeting",
            confidence=0.95,
            tool_used="none",
            selection_source="default_fallback",
        )
        d = resp.to_dict()
        assert d["success"] is True
        assert d["message"] == "hello"
        assert d["followups"] == ["a", "b"]
        assert d["meta"]["intent"] == "greeting"
        assert d["meta"]["confidence"] == 0.95


# ── AIGateway ─────────────────────────────────────────────────────────


def _mock_container():
    c = MagicMock()
    c.orchestrator.orchestrate.return_value = {
        "success": True,
        "message": "Réponse test",
        "data": {"type": "tool_result"},
        "followups": ["Question 1 ?", "Question 2 ?"],
        "meta": {
            "request_id": "req123",
            "intent": "greeting",
            "confidence": 0.9,
            "tool_used": "none",
            "tool_action": "greet",
            "selection_source": "ai_router",
            "trace_id": "trace1",
        },
    }
    c.metrics.inc_counter = MagicMock()
    c.metrics.record_request = MagicMock()
    c.audit.log_simple = MagicMock()
    c.health_check.return_value = {"ollama": "ok"}
    return c


class TestAIGateway:
    def setup_method(self):
        self.container = _mock_container()
        self.gw = AIGateway(self.container)

    def test_handle_valid(self):
        req = GatewayRequest(message="Bonjour", user_id="1")
        resp = self.gw.handle(req)
        assert resp.success is True
        assert resp.message == "Réponse test"
        assert resp.followups == ["Question 1 ?", "Question 2 ?"]
        assert resp.intent == "greeting"
        assert resp.confidence == 0.9

    def test_handle_calls_orchestrator(self):
        req = GatewayRequest(message="Quels déchets dangereux ?", user_id="1")
        self.gw.handle(req)
        self.container.orchestrator.orchestrate.assert_called_once()
        call_kwargs = self.container.orchestrator.orchestrate.call_args[1]
        assert call_kwargs["message"] == "Quels déchets dangereux ?"
        assert call_kwargs["user_id"] == "1"

    def test_handle_validation_error(self):
        req = GatewayRequest(message="", user_id="1")
        resp = self.gw.handle(req)
        assert resp.success is False
        assert "required" in resp.error.lower() or "empty" in resp.error.lower()
        self.container.orchestrator.orchestrate.assert_not_called()

    def test_handle_orchestrator_exception(self):
        self.container.orchestrator.orchestrate.side_effect = RuntimeError("boom")
        req = GatewayRequest(message="test", user_id="1")
        resp = self.gw.handle(req)
        assert resp.success is False
        assert "erreur interne" in resp.message.lower()

    def test_handle_metrics_recorded(self):
        req = GatewayRequest(message="test", user_id="1")
        self.gw.handle(req)
        self.container.metrics.inc_counter.assert_called()
        self.container.metrics.record_request.assert_called()

    def test_handle_raw(self):
        req = GatewayRequest(message="test", user_id="1")
        result = self.gw.handle_raw(req)
        assert isinstance(result, dict)
        assert result["success"] is True

    def test_handle_stream(self):
        req = GatewayRequest(message="test", user_id="1")
        chunks = list(self.gw.stream(req))
        assert len(chunks) >= 1
        assert "done" in chunks[0]
        assert "Réponse test" in chunks[0]

    def test_stream_validation_error(self):
        req = GatewayRequest(message="", user_id="1")
        chunks = list(self.gw.stream(req))
        assert len(chunks) >= 1
        assert "error" in chunks[0] or "done" in chunks[0]

    def test_health_check(self):
        result = self.gw.health_check()
        self.container.health_check.assert_called_once()
        assert result["ollama"] == "ok"

    def test_capabilities(self):
        caps = self.gw.capabilities()
        assert "intents" in caps
        assert "tools" in caps
        assert "languages" in caps
        assert caps["version"] == "2.0.0"

    def test_metrics(self):
        m = self.gw.metrics()
        assert "metrics" in m
        assert "tracing" in m
        assert "audit" in m

    def test_request_id_assigned(self):
        req = GatewayRequest(message="test", user_id="1")
        resp = self.gw.handle(req)
        assert resp.request_id != ""

    def test_elapsed_ms_populated(self):
        req = GatewayRequest(message="test", user_id="1")
        resp = self.gw.handle(req)
        assert resp.elapsed_ms >= 0


class TestAIGatewayLazyInit:
    def test_orchestrator_created_once(self):
        c = _mock_container()
        gw = AIGateway(c)
        _ = gw._orch
        _ = gw._orch
        # Accessing _orch property multiple times should not re-create
        # (the mock object stays the same)
        assert gw._orch is gw._orch


class TestAIGatewayEdgeCases:
    def test_long_message_accepted(self):
        c = _mock_container()
        gw = AIGateway(c)
        req = GatewayRequest(message="x" * 4999, user_id="1")
        resp = gw.handle(req)
        assert resp.success is True

    def test_special_chars_in_message(self):
        c = _mock_container()
        gw = AIGateway(c)
        req = GatewayRequest(message="Déchets spéciaux: é è ê ë", user_id="1")
        resp = gw.handle(req)
        assert resp.success is True

    def test_arabic_message(self):
        c = _mock_container()
        gw = AIGateway(c)
        req = GatewayRequest(message="مرحبا", user_id="1", lang="ar")
        resp = gw.handle(req)
        assert resp.success is True

    def test_english_message(self):
        c = _mock_container()
        gw = AIGateway(c)
        req = GatewayRequest(message="Hello", user_id="1", lang="en")
        resp = gw.handle(req)
        assert resp.success is True
