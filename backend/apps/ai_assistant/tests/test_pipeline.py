"""
Unit tests for the Enterprise Pipeline + AgentOrchestrator.

Pipeline flow: User → AgentOrchestrator → AI Router / Hermes → Tool → Repo → DB → Hermes → Response + Follow-ups

Tests cover:
  - Context building
  - Intent understanding (AI Router + Hermes)
  - Tool selection (business-first policy)
  - Tool execution
  - Anti-hallucination guard
  - Response generation
  - Follow-up question generation
  - Caching, metrics, tracing, audit
  - Greeting, direct response, error handling
  - JSON parsing
  - Workflow state machine
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from apps.ai_assistant.core.interfaces import (
    Context,
    ExecutionPlan,
    FormattedResponse,
    Intent,
    Message,
    OutputFormat,
    ReasoningResult,
    Role,
    RouteResult,
    TaskStep,
    ToolResult,
)
from apps.ai_assistant.infrastructure.audit.audit import AuditAction, AuditLogger
from apps.ai_assistant.infrastructure.caching.cache import CacheManager, InMemoryCache
from apps.ai_assistant.infrastructure.metrics.collector import MetricsCollector
from apps.ai_assistant.infrastructure.monitoring.health import HealthCheck
from apps.ai_assistant.infrastructure.tracing.tracer import Tracer


# ---------------------------------------------------------------------------
# Mock Container — wires real infrastructure with mocked core services
# ---------------------------------------------------------------------------


class MockContainer:
    """Fake container for testing the pipeline stages."""

    def __init__(self) -> None:
        # Real infrastructure
        self.cache = CacheManager(
            backend=InMemoryCache(max_size=100, default_ttl=60.0),
            prefix="test",
            default_ttl=60.0,
        )
        self.metrics = MetricsCollector(namespace="test")
        self.tracer = Tracer(service_name="test")
        self.audit = AuditLogger(max_events=1000)
        self.health = HealthCheck(version="test")

        # Mock Ollama — returns tool decision + response + followups
        self.ollama = MagicMock()
        self.ollama.is_available.return_value = True
        self.ollama.chat.side_effect = [
            # Call 1: Hermes gate — tool needed?
            '{"tool_needed": true, "tool": "waste_tool", "action": "search", "parameters": {"query": "test"}}',
            # Call 2: Hermes generate response
            "Found 3 waste codes for test.",
            # Call 3: Hermes generate follow-ups
            '["Quels sont les déchets dangereux ?", "Quelle est la réglementation ?"]',
        ]

        # Mock Context Builder → returns a real Context
        self.context_builder = MagicMock()
        self.context_builder.build.return_value = Context(
            messages=[Message(role=Role.USER, content="test")],
            user_id="u1",
            conversation_id="conv1",
        )

        # Mock Executor → returns real ToolResult list
        self.executor = MagicMock()
        self.executor.execute.return_value = [
            ToolResult(
                tool_name="waste_tool",
                success=True,
                data={"total": 3, "codes": ["15.01.01"]},
            )
        ]

        # Mock Memory
        self.memory = MagicMock()

        # Mock Tool Registry (iterable)
        self.tool_registry = MagicMock()
        self.tool_registry.__iter__ = MagicMock(return_value=iter([]))
        self.tool_registry.__contains__ = MagicMock(return_value=True)

        # Mock Search Engine (RAG)
        self.search_engine = MagicMock()
        self.search_engine.stats.return_value = {"total_chunks": 0, "sources": {}}
        rag_result = MagicMock()
        rag_result.has_results = False
        rag_result.context_text = ""
        self.search_engine.search_for_agent.return_value = rag_result

        # Mock RAG Config
        self.rag_config = MagicMock()
        self.rag_config.sources = ["glossary", "nomenclature", "regulations", "procedures"]


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------


class TestPipelineContextBuilding(unittest.TestCase):
    """Stage 1: Context Builder."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_context_built_with_message(self):
        self.pipeline.handle("test message", user_id="u1")
        self.container.context_builder.build.assert_called_once()
        call_args = self.container.context_builder.build.call_args
        self.assertEqual(call_args[0][0], "test message")

    def test_context_built_with_user_id(self):
        self.pipeline.handle("test", user_id="u1")
        call_args = self.container.context_builder.build.call_args
        self.assertEqual(
            call_args[1].get("user_id", ""), "u1",
        )


class TestPipelineHermesDecision(unittest.TestCase):
    """Stage 2: Hermes decides which tool to call."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_hermes_called_for_decision(self):
        self.pipeline.handle("search waste", user_id="u1")
        self.assertTrue(self.container.ollama.chat.called)

    def test_tool_used_in_meta(self):
        result = self.pipeline.handle("test", user_id="u1")
        self.assertEqual(result["meta"]["tool_used"], "waste_tool")

    def test_plan_type_in_meta(self):
        result = self.pipeline.handle("test", user_id="u1")
        self.assertIn("selection_source", result["meta"])

    def test_tool_used_none_for_no_match(self):
        self.container.ollama.chat.side_effect = [
            '{"tool": "none"}',
            "I don't have a tool for that.",
            '[]',
        ]
        result = self.pipeline.handle("random question", user_id="u1")
        self.assertIsNone(result["meta"]["tool_used"])


class TestPipelineToolExecution(unittest.TestCase):
    """Stage 4: Tool Execution."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_executor_called(self):
        self.pipeline.handle("test", user_id="u1")
        self.container.executor.execute.assert_called_once()

    def test_tool_result_data_in_response(self):
        result = self.pipeline.handle("test", user_id="u1")
        self.assertEqual(result["data"]["total"], 3)

    def test_executor_not_called_for_none_tool(self):
        self.container.ollama.chat.side_effect = [
            '{"tool": "none"}',
            "Here is my answer.",
            '[]',
        ]
        self.pipeline.handle("question", user_id="u1")
        self.container.executor.execute.assert_not_called()


class TestPipelineHermesResponse(unittest.TestCase):
    """Stage 5: Hermes generates the final answer."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_response_from_hermes(self):
        result = self.pipeline.handle("test", user_id="u1")
        self.assertEqual(result["message"], "Found 3 waste codes for test.")

    def test_hermes_called_three_times(self):
        self.pipeline.handle("test", user_id="u1")
        # 1. decide tool, 2. generate response, 3. generate follow-ups
        self.assertEqual(self.container.ollama.chat.call_count, 3)

    def test_fallback_when_hermes_fails(self):
        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "waste_tool", "action": "list"}',
            Exception("Hermes down"),
        ]
        result = self.pipeline.handle("test", user_id="u1")
        self.assertTrue(result["success"])
        # Should fallback to deterministic format
        self.assertIn("élément", result["message"].lower())


class TestPipelineFollowups(unittest.TestCase):
    """Stage 6: Follow-up question generation."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_followups_in_response(self):
        result = self.pipeline.handle("test", user_id="u1")
        self.assertIn("followups", result)
        self.assertIsInstance(result["followups"], list)

    def test_followups_populated(self):
        result = self.pipeline.handle("test", user_id="u1")
        self.assertEqual(len(result["followups"]), 2)

    def test_greeting_followups(self):
        self.container.ollama.chat.side_effect = [
            '{"tool": "greeting"}',
            "Bonjour !",
        ]
        result = self.pipeline.handle("Bonjour !", user_id="u1")
        self.assertEqual(len(result["followups"]), 3)

    def test_no_followups_for_none_tool(self):
        self.container.ollama.chat.side_effect = [
            '{"tool": "none"}',
            "Here is my answer.",
        ]
        result = self.pipeline.handle("random question", user_id="u1")
        self.assertEqual(result["followups"], [])


class TestPipelineAntiHallucination(unittest.TestCase):
    """Anti-hallucination guard."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_none_tool_result_no_crash(self):
        self.container.ollama.chat.side_effect = [
            '{"tool": "none"}',
            "Answer.",
        ]
        result = self.pipeline.handle("question", user_id="u1")
        self.assertTrue(result["success"])

    def test_empty_tool_result_no_crash(self):
        self.container.executor.execute.return_value = [
            ToolResult(tool_name="waste_tool", success=True, data={}),
        ]
        result = self.pipeline.handle("test", user_id="u1")
        self.assertTrue(result["success"])

    def test_error_tool_result_no_crash(self):
        self.container.executor.execute.return_value = [
            ToolResult(tool_name="waste_tool", success=False, error="DB error"),
        ]
        result = self.pipeline.handle("test", user_id="u1")
        self.assertTrue(result["success"])


class TestPipelineBusinessFirst(unittest.TestCase):
    """Business-first policy: Hermes is the gate, AI Router refines."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_ai_router_overrides_hermes_different_tool(self):
        mock_router = MagicMock()
        mock_result = MagicMock()
        mock_result.tool = "nomenclature_tool"
        mock_result.action = "search"
        mock_result.parameters = {"term": "plastique"}
        mock_result.confidence = 0.95
        mock_result.to_dict.return_value = {
            "tool": "nomenclature_tool",
            "action": "search",
            "parameters": {"term": "plastique"},
            "confidence": 0.95,
        }
        mock_router.route.return_value = mock_result
        self.pipeline._orch._ai_router_instance = mock_router

        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "waste_tool", "action": "search"}',
            "Here are the plastic codes.",
            '[]',
        ]

        result = self.pipeline.handle("Rechercher les codes plastique", user_id="u1")
        self.assertEqual(result["meta"]["tool_used"], "nomenclature_tool")
        self.assertEqual(result["meta"]["selection_source"], "ai_router")

    def test_hermes_tool_always_used(self):
        self.container.ollama.chat.side_effect = [
            '{"tool_needed": true, "tool": "waste_tool", "action": "list"}',
            "Found waste codes.",
            '[]',
        ]
        result = self.pipeline.handle("Lister les déchets", user_id="u1")
        self.assertEqual(result["meta"]["tool_used"], "waste_tool")


class TestPipelineCacheObservability(unittest.TestCase):
    """Stage 8: Cache, Metrics, Tracing, Audit."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_cache_stored(self):
        self.pipeline.handle("test", user_id="u1")
        self.assertGreater(self.container.cache.stats()["size"], 0)

    def test_metrics_recorded(self):
        self.pipeline.handle("test", user_id="u1")
        self.assertGreaterEqual(
            self.container.metrics.get_counter("ai.orchestrator.responses.total"), 1,
        )

    def test_traces_completed(self):
        self.pipeline.handle("test", user_id="u1")
        stats = self.container.tracer.stats()
        self.assertGreaterEqual(stats["completed_traces"], 1)

    def test_spans_created(self):
        self.pipeline.handle("test", user_id="u1")
        stats = self.container.tracer.stats()
        self.assertGreaterEqual(stats["total_spans"], 3)

    def test_audit_logged(self):
        self.pipeline.handle("test", user_id="u1")
        events = self.container.audit.query(action=AuditAction.CHAT)
        self.assertGreaterEqual(len(events), 1)

    def test_memory_stored(self):
        self.pipeline.handle("test", user_id="u1")
        self.container.memory.store_user_message.assert_called_once()
        self.container.memory.store_assistant_message.assert_called_once()


class TestPipelineCacheHit(unittest.TestCase):
    """Cache hit returns instantly."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_cache_hit_returns_cached(self):
        self.pipeline.handle("cached query", user_id="u1")
        result = self.pipeline.handle("cached query", user_id="u1")
        self.assertTrue(result["meta"]["cached"])

    def test_cache_hit_skips_hermes(self):
        self.pipeline.handle("q", user_id="u1")
        call_count_after_first = self.container.ollama.chat.call_count
        self.pipeline.handle("q", user_id="u1")
        self.assertEqual(self.container.ollama.chat.call_count, call_count_after_first)


class TestPipelineGreeting(unittest.TestCase):
    """Greeting goes through Hermes gate then response generation."""

    def setUp(self):
        self.container = MockContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool": "greeting"}',
            "Bonjour ! Je suis RECUP-DZ.",
        ]
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_greeting_hermes_called(self):
        result = self.pipeline.handle("Bonjour !", user_id="u1")
        self.assertTrue(result["success"])
        # Hermes gate + response generation = 2 calls
        self.assertEqual(self.container.ollama.chat.call_count, 2)

    def test_greeting_cached(self):
        self.pipeline.handle("Bonjour !", user_id="u1")
        result2 = self.pipeline.handle("Bonjour !", user_id="u1")
        self.assertTrue(result2["meta"]["cached"])


class TestPipelineDirectResponse(unittest.TestCase):
    """No matching tool → Hermes answers directly."""

    def setUp(self):
        self.container = MockContainer()
        self.container.ollama.chat.side_effect = [
            '{"tool": "none"}',
            "The weather in Algiers is sunny.",
            '[]',
        ]
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_no_tool_used(self):
        result = self.pipeline.handle("What's the weather?", user_id="u1")
        self.assertIsNone(result["meta"]["tool_used"])

    def test_response_from_hermes(self):
        result = self.pipeline.handle("random", user_id="u1")
        self.assertEqual(result["message"], "The weather in Algiers is sunny.")


class TestPipelineErrorHandling(unittest.TestCase):
    """Error paths."""

    def setUp(self):
        self.container = MockContainer()
        self.container.context_builder.build.side_effect = RuntimeError("Build failed")
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_exception_returns_error(self):
        result = self.pipeline.handle("test", user_id="u1")
        self.assertFalse(result["success"])
        self.assertIn("erreur", result["message"].lower())

    def test_error_metric(self):
        self.pipeline.handle("test", user_id="u1")
        self.assertGreaterEqual(
            self.container.metrics.get_counter("ai.orchestrator.errors.total"), 1,
        )

    def test_error_audit(self):
        self.pipeline.handle("test", user_id="u1")
        events = self.container.audit.query(action=AuditAction.ERROR)
        self.assertGreaterEqual(len(events), 1)


class TestPipelineParseHermesGate(unittest.TestCase):
    """JSON parsing of Hermes gate responses."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)
        self.orchestrator = self.pipeline._orch

    def test_valid_json(self):
        raw = '{"tool": "waste_tool", "action": "search", "parameters": {"query": "oil"}, "reasoning": "test"}'
        result = self.orchestrator._parse_hermes_gate(raw)
        self.assertEqual(result["tool"], "waste_tool")
        self.assertEqual(result["action"], "search")

    def test_codeblock_json(self):
        raw = '```json\n{"tool": "waste_tool", "action": "list", "parameters": {}, "reasoning": "ok"}\n```'
        result = self.orchestrator._parse_hermes_gate(raw)
        self.assertEqual(result["tool"], "waste_tool")

    def test_invalid_json(self):
        result = self.orchestrator._parse_hermes_gate("not json")
        self.assertEqual(result["tool"], "none")

    def test_empty_string(self):
        result = self.orchestrator._parse_hermes_gate("")
        self.assertEqual(result["tool"], "none")


class TestPipelineResponseEnvelope(unittest.TestCase):
    """Standard response format."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)
        self.orchestrator = self.pipeline._orch

    def test_success_envelope(self):
        result = self.orchestrator._build_response(
            True, "ok", data={"k": "v"}, followups=["q1"], meta={"m": 1},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "ok")
        self.assertEqual(result["data"], {"k": "v"})
        self.assertEqual(result["followups"], ["q1"])
        self.assertEqual(result["meta"], {"m": 1})

    def test_error_envelope(self):
        result = self.orchestrator._build_response(False, "err")
        self.assertFalse(result["success"])
        self.assertEqual(result["data"], {})
        self.assertEqual(result["followups"], [])
        self.assertEqual(result["meta"], {})


class TestPipelineWorkflowState(unittest.TestCase):
    """Workflow state machine."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        self.pipeline = EnterprisePipeline(container=self.container)

    def test_workflow_state_completed(self):
        result = self.pipeline.handle("test", user_id="u1")
        self.assertEqual(result["meta"]["workflow_state"], "completed")

    def test_workflow_state_error(self):
        self.container.context_builder.build.side_effect = RuntimeError("fail")
        result = self.pipeline.handle("test", user_id="u1")
        self.assertEqual(result["meta"]["workflow_state"], "error")


class TestOrchestratorHermesGate(unittest.TestCase):
    """Orchestrator Hermes gate step — determines if a tool is needed."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        self.orchestrator = AgentOrchestrator(container=self.container)

    def test_hermes_gate_called(self):
        self.container.ollama.chat.side_effect = [
            '{"tool": "waste_tool", "action": "search"}',
            "Response",
            '[]',
        ]
        ctx = self.container.context_builder.build("test", user_id="u1")
        result = self.orchestrator._hermes_gate(ctx, "test")
        self.assertTrue(hasattr(result, 'tool_needed'))
        self.assertTrue(hasattr(result, 'tool'))
        self.assertTrue(hasattr(result, 'action'))
        self.assertTrue(hasattr(result, 'confidence'))

    def test_hermes_gate_returns_hermes_decision(self):
        self.container.ollama.chat.side_effect = [
            '{"tool": "waste_tool", "action": "search"}',
            "Response",
            '[]',
        ]
        from apps.ai_assistant.enterprise.agent_orchestrator import HermesDecision
        ctx = self.container.context_builder.build("test", user_id="u1")
        result = self.orchestrator._hermes_gate(ctx, "test")
        self.assertIsInstance(result, HermesDecision)


class TestOrchestratorRefineToolSelection(unittest.TestCase):
    """Orchestrator tool refinement step — Hermes decision refined by AI Router."""

    def setUp(self):
        self.container = MockContainer()
        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator, HermesDecision
        self.orchestrator = AgentOrchestrator(container=self.container)
        self.HermesDecision = HermesDecision

    def test_refine_tool_from_hermes(self):
        hermes_decision = self.HermesDecision(
            tool_needed=True,
            tool="waste_tool",
            action="search",
            parameters={"query": "oil"},
            confidence=0.9,
            reasoning="test",
        )
        result = self.orchestrator._refine_tool_selection(hermes_decision, "test", True)
        self.assertEqual(result.tool, "waste_tool")
        self.assertIn(result.source, ("hermes+ai_router", "hermes"))

    def test_refine_tool_fallback_to_hermes_no_router(self):
        hermes_decision = self.HermesDecision(
            tool_needed=True,
            tool="waste_tool",
            action="list",
            parameters={},
            confidence=0.8,
            reasoning="test",
        )
        result = self.orchestrator._refine_tool_selection(hermes_decision, "test", True)
        self.assertEqual(result.tool, "waste_tool")

    def test_hermes_says_no_tool(self):
        hermes_decision = self.HermesDecision(
            tool_needed=False,
            tool="none",
            action="",
            parameters={},
            confidence=0.5,
            reasoning="no tool needed",
        )
        result = self.orchestrator._refine_tool_selection(hermes_decision, "test", True)
        self.assertEqual(result.tool, "none")

    def test_hermes_says_greeting(self):
        hermes_decision = self.HermesDecision(
            tool_needed=False,
            tool="greeting",
            action="",
            parameters={},
            confidence=0.5,
            reasoning="greeting",
        )
        result = self.orchestrator._refine_tool_selection(hermes_decision, "test", True)
        self.assertEqual(result.tool, "greeting")


if __name__ == "__main__":
    unittest.main()
