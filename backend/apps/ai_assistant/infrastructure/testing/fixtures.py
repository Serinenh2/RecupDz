"""
Testing Utilities — fixtures and mocks for AI module testing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch


class AITestCase:
    """Base test case for AI module tests."""

    def setUp(self) -> None:
        self.config = self._default_config()
        self.metrics = self._default_metrics()
        self.cache = self._default_cache()
        self.audit = self._default_audit()
        self.profiler = self._default_profiler()

    def tearDown(self) -> None:
        if hasattr(self, "cache") and self.cache:
            self.cache.clear()
        if hasattr(self, "audit") and self.audit:
            self.audit.clear()
        if hasattr(self, "profiler") and self.profiler:
            self.profiler.reset()

    @staticmethod
    def _default_config():
        from apps.ai_assistant.infrastructure.configuration.settings import EnterpriseConfig
        return EnterpriseConfig()

    @staticmethod
    def _default_metrics():
        from apps.ai_assistant.infrastructure.metrics.collector import MetricsCollector
        return MetricsCollector()

    @staticmethod
    def _default_cache():
        from apps.ai_assistant.infrastructure.caching.cache import CacheManager
        return CacheManager()

    @staticmethod
    def _default_audit():
        from apps.ai_assistant.infrastructure.audit.audit import AuditLogger
        return AuditLogger()

    @staticmethod
    def _default_profiler():
        from apps.ai_assistant.infrastructure.performance.profiler import Profiler
        return Profiler()

    def create_tool_context(self, **kwargs: Any):
        from apps.ai_assistant.tools.tool_context import ToolContext
        return ToolContext.create(**kwargs)

    def create_mock_tool(self, name: str = "mock_tool", success: bool = True, data: Any = None):
        from apps.ai_assistant.tools.base_tool import BaseTool
        from apps.ai_assistant.tools.tool_result import ToolResultResponse

        class MockTool(BaseTool):
            name = name
            description = f"Mock tool: {name}"

            def _execute(self, parameters, context):
                if success:
                    return ToolResultResponse.ok(data=data or {"mock": True})
                return ToolResultResponse.fail("Mock failure")

        return MockTool()


@dataclass
class MockOllamaService:
    """Mock Ollama service for testing."""

    available: bool = True
    response_text: str = "Mock response"
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 10.0

    def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
        time.sleep(self.latency_ms / 1000)
        return {
            "message": {"content": self.response_text},
            "tool_calls": self.tool_calls,
            "done": True,
        }

    def chat_simple(self, prompt: str, **kwargs: Any) -> str:
        time.sleep(self.latency_ms / 1000)
        return self.response_text

    def generate_structured(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        time.sleep(self.latency_ms / 1000)
        return {"intent": "question", "confidence": 0.8, "entities": {}}

    def is_available(self) -> bool:
        return self.available

    def health(self) -> Dict[str, Any]:
        return {"status": "healthy" if self.available else "unhealthy"}


@dataclass
class MockToolRegistry:
    """Mock tool registry for testing."""

    tools: Dict[str, Any] = field(default_factory=dict)

    def register(self, tool: Any) -> None:
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[Any]:
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description}
            for t in self.tools.values()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self.tools


def create_test_context(
    message: str = "Test message",
    user_id: str = "test_user",
    conversation_id: str = "test_conv",
    roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a test context for gateway testing."""
    return {
        "message": message,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "user_roles": roles or ["recuperateur"],
    }


def assert_tool_result(result: Dict[str, Any], success: bool = True) -> None:
    """Assert a tool result has the expected structure."""
    assert "success" in result
    assert "message" in result
    assert "data" in result
    assert result["success"] == success


def assert_route_decision(decision: Any, intent: str = None, tool: str = None) -> None:
    """Assert a route decision has the expected structure."""
    assert hasattr(decision, "intent")
    assert hasattr(decision, "confidence")
    assert hasattr(decision, "action")
    if intent:
        assert decision.intent.value == intent
    if tool:
        assert decision.tool_name == tool
