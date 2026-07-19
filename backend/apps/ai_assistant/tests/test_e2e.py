"""
End-to-end integration tests — Gateway → Orchestrator → Router → Tool.

Uses the REAL AI Router (deterministic regex) with mocked LLM and tool execution.
Tests the full request lifecycle through every layer.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from apps.ai_assistant.core.interfaces import (
    Context,
    Message,
    Role,
    ToolResult,
)
from apps.ai_assistant.enterprise.ai_gateway import (
    AIGateway,
    GatewayRequest,
    GatewayResponse,
    RequestSource,
)
from apps.ai_assistant.infrastructure.audit.audit import AuditLogger
from apps.ai_assistant.infrastructure.caching.cache import CacheManager, InMemoryCache
from apps.ai_assistant.infrastructure.metrics.collector import MetricsCollector
from apps.ai_assistant.infrastructure.monitoring.health import HealthCheck
from apps.ai_assistant.infrastructure.tracing.tracer import Tracer


# ---------------------------------------------------------------------------
# Integration Test Container — real infra, real AI Router, mocked LLM
# ---------------------------------------------------------------------------


class IntegrationContainer:
    """Container for integration tests with real infra and mocked LLM."""

    def __init__(self) -> None:
        self.cache = CacheManager(
            backend=InMemoryCache(max_size=100, default_ttl=60.0),
            prefix="integration_test",
            default_ttl=60.0,
        )
        self.metrics = MetricsCollector(namespace="integration_test")
        self.tracer = Tracer(service_name="integration_test")
        self.audit = AuditLogger(max_events=1000)
        self.health = HealthCheck(version="integration_test")

        self.ollama = MagicMock()
        self.ollama.is_available.return_value = True

        self.context_builder = MagicMock()
        self.context_builder.build.return_value = Context(
            messages=[Message(role=Role.USER, content="test")],
            user_id="u1",
            conversation_id="conv_test",
        )

        self.executor = MagicMock()

        self.memory = MagicMock()

        self.tool_registry = MagicMock()
        self.tool_registry.__iter__ = MagicMock(return_value=iter([]))
        self.tool_registry.__contains__ = MagicMock(return_value=True)

        self.search_engine = MagicMock()
        rag_result = MagicMock()
        rag_result.has_results = False
        rag_result.context_text = ""
        self.search_engine.search_for_agent.return_value = rag_result

        self._orchestrator = None

    @property
    def orchestrator(self):
        if self._orchestrator is None:
            from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
            self._orchestrator = AgentOrchestrator(container=self)
        return self._orchestrator


# ---------------------------------------------------------------------------
# End-to-End Tests
# ---------------------------------------------------------------------------


class TestE2EGreeting(unittest.TestCase):
    """E2E: Greeting → Hermes gate detects 'greeting' → response generated."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool": "greeting"}',
            "Bonjour ! Je suis RECUP-DZ.",
        ]
        self.gateway = AIGateway(container=self.container)

    def test_greeting_routes_through_all_layers(self):
        request = GatewayRequest(message="Bonjour", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertIn("Bonjour", response.message)
        self.assertIsNone(response.tool_used)
        self.assertEqual(response.selection_source, "hermes")
        self.assertTrue(response.elapsed_ms > 0)
        self.assertTrue(response.trace_id)

    def test_greeting_has_followups(self):
        request = GatewayRequest(message="Salut", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertIsInstance(response.followups, list)
        self.assertGreater(len(response.followups), 0)


class TestE2ENomenclature(unittest.TestCase):
    """E2E: 'code 01.01.01' → Hermes gate + AI Router → nomenclature_tool."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "nomenclature_tool", "action": "search"}',
            "Voici les informations sur le code 01.01.01.",
            '[]',
        ]
        self.container.executor.execute.return_value = [
            ToolResult(
                tool_name="nomenclature_tool",
                success=True,
                data={"code": "01.01.01", "description": "Déchets provenant du traitement des déchets"},
            )
        ]
        self.gateway = AIGateway(container=self.container)

    def test_nomenclature_code_routed_to_tool(self):
        request = GatewayRequest(message="code 01.01.01", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertEqual(response.tool_used, "nomenclature_tool")
        self.assertIn(response.selection_source, ("hermes+ai_router", "hermes"))
        self.assertIsNotNone(response.data)


class TestE2EBSD(unittest.TestCase):
    """E2E: 'BSD-20241234' → Hermes gate + AI Router → bsd_tool."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "bsd_tool", "action": "search"}',
            "Voici les détails du BSD-20241234.",
            '[]',
        ]
        self.container.executor.execute.return_value = [
            ToolResult(
                tool_name="bsd_tool",
                success=True,
                data={"numero": "BSD-20241234", "statut": "EN_TRANSIT"},
            )
        ]
        self.gateway = AIGateway(container=self.container)

    def test_bsd_number_routed_to_tool(self):
        request = GatewayRequest(message="BSD-20241234", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertEqual(response.tool_used, "bsd_tool")
        self.assertIn(response.selection_source, ("hermes+ai_router", "hermes"))


class TestE2EWasteSearch(unittest.TestCase):
    """E2E: 'déchets dangereux' → Hermes gate + AI Router → waste_tool."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "waste_tool", "action": "search"}',
            "Voici les déchets dangereux classés.",
            '[]',
        ]
        self.container.executor.execute.return_value = [
            ToolResult(
                tool_name="waste_tool",
                success=True,
                data={"total": 5, "results": [{"code": "15.01.01"}]},
            )
        ]
        self.gateway = AIGateway(container=self.container)

    def test_waste_search_routed_to_tool(self):
        request = GatewayRequest(message="déchets dangereux", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertEqual(response.tool_used, "waste_tool")
        self.assertIn(response.selection_source, ("hermes+ai_router", "hermes"))


class TestE2EDashboard(unittest.TestCase):
    """E2E: 'tableau de bord' → Hermes gate + AI Router → dashboard_tool."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "dashboard_tool", "action": "get"}',
            "Voici le tableau de bord.",
            '[]',
        ]
        self.container.executor.execute.return_value = [
            ToolResult(
                tool_name="dashboard_tool",
                success=True,
                data={"kpi": {"total_bsd": 150}},
            )
        ]
        self.gateway = AIGateway(container=self.container)

    def test_dashboard_routed_to_tool(self):
        request = GatewayRequest(message="tableau de bord", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertEqual(response.tool_used, "dashboard_tool")
        self.assertIn(response.selection_source, ("hermes+ai_router", "hermes"))


class TestE2ERegulation(unittest.TestCase):
    """E2E: 'réglementation' → Hermes gate + AI Router → reglementation_tool."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "reglementation_tool", "action": "search"}',
            "Voici la réglementation applicable.",
            '[]',
        ]
        self.container.executor.execute.return_value = [
            ToolResult(
                tool_name="reglementation_tool",
                success=True,
                data={"lois": ["Loi 01-19"]},
            )
        ]
        self.gateway = AIGateway(container=self.container)

    def test_regulation_routed_to_tool(self):
        request = GatewayRequest(message="réglementation", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertEqual(response.tool_used, "reglementation_tool")
        self.assertIn(response.selection_source, ("hermes+ai_router", "hermes"))


class TestE2ENotification(unittest.TestCase):
    """E2E: 'notifications' → Hermes gate + AI Router → notification_tool."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "notification_tool", "action": "list"}',
            "Vous avez 3 notifications.",
            '[]',
        ]
        self.container.executor.execute.return_value = [
            ToolResult(
                tool_name="notification_tool",
                success=True,
                data={"total": 3, "unread": 2},
            )
        ]
        self.gateway = AIGateway(container=self.container)

    def test_notification_routed_to_tool(self):
        request = GatewayRequest(message="notifications", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertEqual(response.tool_used, "notification_tool")
        self.assertIn(response.selection_source, ("hermes+ai_router", "hermes"))


class TestE2ENoMatchFallsBackToLLM(unittest.TestCase):
    """E2E: Unrelated message → AI Router returns None → Hermes decides."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool": "none", "action": "", "parameters": {}}',
            "Je ne suis pas sûr de comprendre.",
            '[]',
        ]
        self.gateway = AIGateway(container=self.container)

    def test_no_router_match_uses_llm(self):
        request = GatewayRequest(message="xyzzy flurbo random", user_id="u1")
        response = self.gateway.handle(request)

        self.assertTrue(response.success)
        self.assertIsNone(response.tool_used)
        self.assertEqual(response.selection_source, "hermes")


class TestE2ECacheHit(unittest.TestCase):
    """E2E: Second identical request hits cache, no LLM call."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool": "greeting"}',
            "Bonjour ! Je suis RECUP-DZ.",
        ]
        self.gateway = AIGateway(container=self.container)

    def test_second_request_cached(self):
        request = GatewayRequest(message="Bonjour", user_id="u1")

        r1 = self.gateway.handle(request)
        self.assertTrue(r1.success)

        call_count_after_first = self.container.ollama.chat.call_count

        r2 = self.gateway.handle(request)
        self.assertTrue(r2.success)
        self.assertTrue(r2.cached)
        self.assertEqual(self.container.ollama.chat.call_count, call_count_after_first)


class TestE2EMetaEnvelope(unittest.TestCase):
    """E2E: Response meta dict contains all required fields."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool": "greeting"}',
            "Bonjour !",
        ]
        self.gateway = AIGateway(container=self.container)

    def test_meta_has_all_fields(self):
        request = GatewayRequest(message="Bonjour", user_id="u1")
        response = self.gateway.handle(request)
        d = response.to_dict()

        self.assertIn("success", d)
        self.assertIn("message", d)
        self.assertIn("data", d)
        self.assertIn("followups", d)
        self.assertIn("meta", d)

        meta = d["meta"]
        self.assertIn("request_id", meta)
        self.assertIn("intent", meta)
        self.assertIn("confidence", meta)
        self.assertIn("tool_used", meta)
        self.assertIn("tool_action", meta)
        self.assertIn("selection_source", meta)
        self.assertIn("elapsed_ms", meta)
        self.assertIn("trace_id", meta)
        self.assertIn("cached", meta)


class TestE2EValidation(unittest.TestCase):
    """E2E: Invalid requests are rejected at gateway level."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.gateway = AIGateway(container=self.container)

    def test_empty_message_rejected(self):
        request = GatewayRequest(message="", user_id="u1")
        response = self.gateway.handle(request)

        self.assertFalse(response.success)
        self.assertIn("validation", response.message.lower())

    def test_missing_user_id_rejected(self):
        request = GatewayRequest(message="Bonjour", user_id="")
        response = self.gateway.handle(request)

        self.assertFalse(response.success)

    def test_script_injection_rejected(self):
        request = GatewayRequest(message="<script>alert('xss')</script>", user_id="u1")
        response = self.gateway.handle(request)

        self.assertFalse(response.success)


class TestE2EObservability(unittest.TestCase):
    """E2E: Metrics and audit are recorded through the full flow."""

    def setUp(self):
        self.container = IntegrationContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool": "greeting"}',
            "Bonjour !",
        ]
        self.gateway = AIGateway(container=self.container)

    def test_metrics_recorded(self):
        request = GatewayRequest(message="Bonjour", user_id="u1")
        self.gateway.handle(request)

        metrics = self.container.metrics.to_dict()
        self.assertIn("counters", metrics)
        self.assertGreater(len(metrics["counters"]), 0)

    def test_audit_recorded(self):
        request = GatewayRequest(message="Bonjour", user_id="u1")
        self.gateway.handle(request)

        events = self.container.audit.query()
        self.assertGreater(len(events), 0)


if __name__ == "__main__":
    unittest.main()
