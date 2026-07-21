"""
AI Agent — main orchestrator.

Ties together: Context → Route → Plan → Reason → Execute → Format → Response.
All dependencies are injected via the AgentFactory.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.config import AIConfig
from apps.ai_assistant.core.context import DataProvider, DefaultContextBuilder
from apps.ai_assistant.core.executor import DefaultExecutor, ToolRegistry
from apps.ai_assistant.core.formatter import LLMFormatter
from apps.ai_assistant.core.interfaces import (
    Agent,
    Context,
    Executor,
    FormattedResponse,
    Formatter,
    Intent,
    LLMProvider,
    MemoryStore,
    Message,
    OutputFormat,
    Reasoner,
    Router,
    Role,
    Tool,
)
from apps.ai_assistant.core.memory import MemoryManager
from apps.ai_assistant.core.planner import LLMPlanner
from apps.ai_assistant.core.prompts import PromptRegistry
from apps.ai_assistant.core.reasoning import LLMReasoner
from apps.ai_assistant.core.router import RouterFactory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ollama HTTP Client (stdlib only — no new dependencies)
# ---------------------------------------------------------------------------

import json as _json
import urllib.request
import urllib.error


class OllamaClient(LLMProvider):
    """HTTP client for the Ollama API using only stdlib."""

    def __init__(self, config: AIConfig) -> None:
        self._config = config.ollama
        self._system_prompt_cache: Optional[str] = None

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self._config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt
        if stop:
            payload["options"]["stop"] = stop

        return self._post(self._config.generate_url, payload)

    def generate_structured(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        raw = self.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._extract_json(raw)

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(self._config.tags_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    # -- internal --

    def _post(self, url: str, payload: Dict[str, Any]) -> str:
        data = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        last_error: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                with urllib.request.urlopen(
                    req,
                    timeout=self._config.timeout_seconds,
                ) as resp:
                    body = resp.read().decode("utf-8")
                    result = _json.loads(body)
                    return result.get("response", "")
            except urllib.error.URLError as exc:
                last_error = exc
                logger.warning(
                    "Ollama request failed (attempt %d/%d): %s",
                    attempt + 1, self._config.max_retries + 1, exc,
                )
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_delay_seconds * (attempt + 1))

        raise ConnectionError(
            f"Ollama unreachable after {self._config.max_retries + 1} attempts: {last_error}"
        )

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """Extract a JSON object from LLM output, handling markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            raise ValueError(f"No JSON object found in LLM output: {text[:200]}")

        try:
            return _json.loads(text[start:end])
        except _json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from LLM: {exc}") from exc


# ---------------------------------------------------------------------------
# AI Agent (Orchestrator)
# ---------------------------------------------------------------------------

class AIAgent(Agent):
    """
    The main agent — processes a user message through the full pipeline.

    Pipeline: Context → Route → Plan → Reason → Execute → Format
    """

    def __init__(
        self,
        *,
        llm: LLMProvider,
        router: Router,
        planner: LLMPlanner,
        reasoner: Reasoner,
        executor: Executor,
        formatter: Formatter,
        memory: MemoryManager,
        context_builder: DefaultContextBuilder,
        config: AIConfig,
        registry: ToolRegistry,
    ) -> None:
        self._llm = llm
        self._router = router
        self._planner = planner
        self._reasoner = reasoner
        self._executor = executor
        self._formatter = formatter
        self._memory = memory
        self._context_builder = context_builder
        self._config = config
        self._registry = registry
        logger.info(
            "AIAgent initialized: model=%s, tools=%d",
            config.ollama.model, registry.tool_count,
        )

    def handle(
        self,
        user_message: str,
        *,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> FormattedResponse:
        request_id = uuid.uuid4().hex[:12]
        start = time.monotonic()
        logger.info("[%s] Processing: '%s'", request_id, user_message[:80])

        # Ensure conversation_id
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        try:
            # 1. Store user message in memory
            self._memory.store_user_message(conversation_id, user_message)

            # 2. Build context
            ctx = self._context_builder.build(
                user_message,
                conversation_id=conversation_id,
                user_id=user_id,
                **kwargs,
            )

            # 3. Route intent
            route = self._router.classify(ctx)
            logger.info(
                "[%s] Intent: %s (%.0f%%), tool_hint=%s",
                request_id, route.intent.value, route.confidence * 100, route.tool_hint,
            )

            # 4. Handle greeting/chitchat directly (no tools needed)
            if route.intent in (Intent.GREETING, Intent.CHITCHAT):
                response = self._handle_direct(ctx, route)
                self._finish(request_id, conversation_id, user_message, response)
                return response

            # 5. Create execution plan
            plan = self._planner.create_plan(ctx, route)

            # 6. Reason about the plan
            reasoning_result = self._reasoner.reason(ctx, plan)
            plan = self._reasoner.refine_plan(plan, reasoning_result)

            logger.info(
                "[%s] Plan: %d steps, reasoning confidence=%.0f%%",
                request_id, len(plan.steps), reasoning_result.confidence * 100,
            )

            # 7. Execute the plan
            results = self._executor.execute(plan, ctx)

            # 8. Format response
            response = self._formatter.format(
                results, ctx, reasoning_result,
                output_format=OutputFormat.TEXT,
            )

            self._finish(request_id, conversation_id, user_message, response)
            return response

        except Exception as exc:
            logger.error("[%s] Pipeline error: %s", request_id, exc, exc_info=True)
            fallback = FormattedResponse(
                text=self._config.agent.fallback_response,
                metadata={"error": str(exc), "request_id": request_id},
            )
            self._finish(request_id, conversation_id, user_message, fallback)
            return fallback

    def health_check(self) -> Dict[str, Any]:
        llm_ok = self._llm.is_available()
        return {
            "status": "healthy" if llm_ok else "degraded",
            "llm_available": llm_ok,
            "model": self._config.ollama.model,
            "tools_registered": self._registry.tool_count,
            "tool_names": self._registry.tool_names,
            "config": self._config.to_dict(),
        }

    # -- internal --

    def _handle_direct(self, ctx: Context, route: "RouteResult") -> FormattedResponse:
        user_message = ""
        for msg in reversed(ctx.messages):
            if msg.role.value == "user":
                user_message = msg.content
                break

        prompt = f"Réponds de manière amicale et concise à: {user_message}"
        try:
            text = self._llm.generate(
                prompt,
                system_prompt=self._config.agent.system_prompt or "Tu es un assistant amical.",
                temperature=0.7,
                max_tokens=512,
            )
        except Exception:
            text = self._config.agent.fallback_response

        return FormattedResponse(text=text, format=OutputFormat.TEXT)

    def _finish(
        self,
        request_id: str,
        conversation_id: str,
        user_message: str,
        response: FormattedResponse,
    ) -> None:
        self._memory.store_assistant_message(conversation_id, response.text)
        elapsed = time.monotonic() - time.monotonic()
        logger.info("[%s] Response sent (%d chars)", request_id, len(response.text))


# ---------------------------------------------------------------------------
# Agent Factory
# ---------------------------------------------------------------------------

class AgentFactory:
    """
    Assembles a fully configured AIAgent with all dependencies.

    This is the ONLY place where concrete implementations are wired together.
    """

    @staticmethod
    def create(
        *,
        config: Optional[AIConfig] = None,
        llm: Optional[LLMProvider] = None,
        memory_store: Optional[MemoryStore] = None,
        tools: Optional[List[Tool]] = None,
        data_provider: Optional[DataProvider] = None,
        use_llm_router: bool = True,
    ) -> AIAgent:
        config = config or AIConfig.from_env()

        # LLM
        if llm is None:
            llm = OllamaClient(config)

        # Prompt registry
        registry = PromptRegistry()

        # Memory
        memory = MemoryManager(config.memory, long_term_store=memory_store)

        # Context builder
        context_builder = DefaultContextBuilder(data_provider=data_provider)

        # Router
        router = RouterFactory.create(llm=llm, use_llm=use_llm_router, registry=registry)

        # Planner
        planner = LLMPlanner(llm=llm, config=config.agent, registry=registry)

        # Reasoner
        reasoner = LLMReasoner(llm=llm, config=config.agent, registry=registry)

        # Tool registry + executor
        tool_registry = ToolRegistry(config.tool)
        if tools:
            for tool in tools:
                tool_registry.register(tool)

        executor = DefaultExecutor(tool_registry, config.tool)

        # Formatter
        formatter = LLMFormatter(llm=llm, registry=registry)

        agent = AIAgent(
            llm=llm,
            router=router,
            planner=planner,
            reasoner=reasoner,
            executor=executor,
            formatter=formatter,
            memory=memory,
            context_builder=context_builder,
            config=config,
            registry=tool_registry,
        )

        logger.info(
            "AgentFactory: assembled AIAgent with %d tools",
            tool_registry.tool_count,
        )
        return agent

    @staticmethod
    def create_with_llm(
        llm: LLMProvider,
        *,
        config: Optional[AIConfig] = None,
        tools: Optional[List[Tool]] = None,
    ) -> AIAgent:
        """Convenience: create an agent with a pre-configured LLM provider."""
        return AgentFactory.create(config=config, llm=llm, tools=tools)
