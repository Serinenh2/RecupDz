"""
Dependency Injection Container — wires all components together.

Uses Factory Pattern for creation and Strategy Pattern for swappable implementations.
All dependencies are resolved lazily on first access.

Architecture chain:
    Frontend → AI Gateway → Conversation Manager → Planner → Reasoner →
    Router → Tool Executor → Repositories → Services → Database → Hermes3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Container:
    """
    Central DI container. Access services via properties.

    Usage:
        container = Container()
        result = container.pipeline.handle("Quels sont les déchets dangereux ?")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._singletons: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------

    @property
    def cache(self):
        from apps.ai_assistant.infrastructure.caching.cache import CacheManager, InMemoryCache
        return self._get_or_create("cache", lambda: CacheManager(
            backend=InMemoryCache(
                max_size=self._config.get("cache_max_size", 1000),
                default_ttl=self._config.get("cache_ttl", 300.0),
            ),
            prefix="ai",
            default_ttl=self._config.get("cache_ttl", 300.0),
        ))

    @property
    def metrics(self):
        from apps.ai_assistant.infrastructure.metrics.collector import MetricsCollector
        return self._get_or_create("metrics", MetricsCollector)

    @property
    def tracer(self):
        from apps.ai_assistant.infrastructure.tracing.tracer import Tracer
        return self._get_or_create("tracer", Tracer)

    @property
    def audit(self):
        from apps.ai_assistant.infrastructure.audit.audit import AuditLogger
        return self._get_or_create("audit", lambda: AuditLogger(max_events=5000))

    @property
    def health(self):
        from apps.ai_assistant.infrastructure.monitoring.health import HealthCheck
        return self._get_or_create("health", HealthCheck)

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    @property
    def ollama(self):
        from apps.ai_assistant.services.ollama_service import OllamaService
        return self._get_or_create("ollama", lambda: OllamaService(
            base_url=self._config.get("ollama_url", "http://localhost:11434"),
            model=self._config.get("ollama_model", "hermes3"),
            timeout=self._config.get("ollama_timeout", 120),
        ))

    @property
    def conversation_manager(self):
        from apps.ai_assistant.conversation_manager import ConversationManager
        return self._get_or_create("conversation_manager",
                                   lambda: ConversationManager(ollama=self.ollama))

    # ------------------------------------------------------------------
    # Core Adapters (bridge tools framework → core interfaces)
    # ------------------------------------------------------------------

    @property
    def llm(self):
        from apps.ai_assistant.enterprise.adapters import OllamaLLMAdapter
        return self._get_or_create("llm", lambda: OllamaLLMAdapter(self.ollama))

    @property
    def intent_router(self):
        from apps.ai_assistant.intent_router import IntentRouter
        return self._get_or_create("intent_router", IntentRouter)

    @property
    def router(self):
        from apps.ai_assistant.enterprise.adapters import IntentRouterAdapter
        return self._get_or_create("router",
                                   lambda: IntentRouterAdapter(self.intent_router))

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @property
    def tool_registry(self):
        from apps.ai_assistant.tools.tool_registry import ToolRegistry

        def build():
            registry = ToolRegistry()
            count = registry.discover_package("apps.ai_assistant.tools")
            rag_count = registry.discover_package("apps.ai_assistant.rag")
            logger.info("ToolRegistry auto-discovered %d tools + %d RAG tools", count, rag_count)
            return registry

        return self._get_or_create("tool_registry", build)

    @property
    def tool_executor(self):
        from apps.ai_assistant.tools.tool_executor import ToolExecutor, LoggingMiddleware
        def build():
            executor = ToolExecutor(self.tool_registry, default_timeout=15.0)
            executor.add_middleware(LoggingMiddleware())
            return executor
        return self._get_or_create("tool_executor", build)

    @property
    def executor(self):
        from apps.ai_assistant.enterprise.adapters import ToolExecutorAdapter
        return self._get_or_create("executor",
                                   lambda: ToolExecutorAdapter(self.tool_executor))

    # ------------------------------------------------------------------
    # Planner + Reasoner (core interfaces)
    # ------------------------------------------------------------------

    @property
    def agent_config(self):
        from apps.ai_assistant.core.config import AgentConfig
        return self._get_or_create("agent_config", lambda: AgentConfig(
            enable_planning=self._config.get("enable_planning", False),
            enable_reasoning=self._config.get("enable_reasoning", False),
            max_plan_steps=self._config.get("max_plan_steps", 5),
        ))

    @property
    def memory_config(self):
        from apps.ai_assistant.core.config import MemoryConfig
        return self._get_or_create("memory_config", MemoryConfig)

    @property
    def planner(self):
        from apps.ai_assistant.core.planner import LLMPlanner
        from apps.ai_assistant.core.prompts import PromptRegistry
        registry = PromptRegistry()
        return self._get_or_create("planner",
                                   lambda: LLMPlanner(self.llm, self.agent_config, registry))

    @property
    def reasoner(self):
        from apps.ai_assistant.core.reasoning import LLMReasoner
        from apps.ai_assistant.core.prompts import PromptRegistry
        registry = PromptRegistry()
        return self._get_or_create("reasoner",
                                   lambda: LLMReasoner(self.llm, self.agent_config, registry))

    @property
    def formatter(self):
        from apps.ai_assistant.enterprise.adapters import DeterministicFormatter
        return self._get_or_create("formatter", DeterministicFormatter)

    # ------------------------------------------------------------------
    # Context Builder
    # ------------------------------------------------------------------

    @property
    def context_builder(self):
        from apps.ai_assistant.core.context import DefaultContextBuilder, DataProvider
        dp = DataProvider()
        return self._get_or_create("context_builder",
                                   lambda: DefaultContextBuilder(data_provider=dp))

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    @property
    def memory(self):
        from apps.ai_assistant.core.memory import MemoryManager
        return self._get_or_create("memory",
                                   lambda: MemoryManager(self.memory_config))

    # ------------------------------------------------------------------
    # RAG
    # ------------------------------------------------------------------

    @property
    def rag_config(self):
        from apps.ai_assistant.core.config import RAGConfig
        return self._get_or_create("rag_config", lambda: RAGConfig(
            enabled=self._config.get("rag_enabled", True),
            top_k=self._config.get("rag_top_k", 5),
            min_score=self._config.get("rag_min_score", 0.1),
            max_context_chars=self._config.get("rag_max_context_chars", 4000),
            chunk_size=self._config.get("rag_chunk_size", 1000),
            chunk_overlap=self._config.get("rag_chunk_overlap", 200),
            persist_directory=self._config.get("rag_persist_dir", ""),
            auto_index_on_startup=self._config.get("rag_auto_index", True),
            search_before_model=self._config.get("rag_search_before_model", True),
            sources=self._config.get("rag_sources", ["glossary", "nomenclature", "regulations", "procedures"]),
        ))

    @property
    def search_engine(self):
        from apps.ai_assistant.rag.search_engine import SearchEngine
        def build():
            cfg = self.rag_config
            engine = SearchEngine(
                persist_directory=cfg.persist_directory,
                chunk_size=cfg.chunk_size,
                chunk_overlap=cfg.chunk_overlap,
                top_k=cfg.top_k,
                min_score=cfg.min_score,
                max_context_chars=cfg.max_context_chars,
            )
            # Try to load persisted index
            engine.load()
            return engine
        return self._get_or_create("search_engine", build)

    # ------------------------------------------------------------------
    # Orchestrator + Pipeline
    # ------------------------------------------------------------------

    @property
    def orchestrator(self):
        from apps.ai_assistant.enterprise.agent_orchestrator import AgentOrchestrator
        return self._get_or_create("orchestrator",
                                   lambda: AgentOrchestrator(container=self))

    @property
    def pipeline(self):
        from apps.ai_assistant.enterprise.pipeline import EnterprisePipeline
        return self._get_or_create("pipeline", lambda: EnterprisePipeline(container=self))

    @property
    def gateway(self):
        from apps.ai_assistant.enterprise.ai_gateway import AIGateway
        return self._get_or_create("gateway", lambda: AIGateway(container=self))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_or_create(self, key: str, factory) -> Any:
        if key not in self._singletons:
            self._singletons[key] = factory()
            logger.debug("Container: created '%s'", key)
        return self._singletons[key]

    def reset(self) -> None:
        """Clear all singletons (useful for testing)."""
        self._singletons.clear()

    def health_check(self) -> Dict[str, Any]:
        """Check health of all registered services."""
        rag_stats = {}
        try:
            rag_stats = self.search_engine.stats()
        except Exception:
            rag_stats = {"error": "unavailable"}

        return {
            "ollama": self.ollama.health(),
            "tools": self.tool_registry.list_names(),
            "cache_stats": self.cache.stats(),
            "metrics": self.metrics.to_dict(),
            "tracing": self.tracer.stats(),
            "audit": self.audit.stats(),
            "rag": rag_stats,
            "planner_enabled": self._config.get("enable_planning", False),
            "reasoner_enabled": self._config.get("enable_reasoning", False),
        }
