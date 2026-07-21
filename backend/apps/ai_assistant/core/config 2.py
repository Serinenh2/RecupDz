"""
Centralised configuration for the AI Core.

All settings are dataclass-based with env-var overrides.
No secrets are hard-coded — values are loaded from the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    val = os.environ.get(key)
    return int(val) if val is not None else default


def _env_float(key: str, default: float = 0.0) -> float:
    val = os.environ.get(key)
    return float(val) if val is not None else default


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Ollama Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OllamaConfig:
    """Connection and model settings for the Ollama backend."""
    base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434"))
    model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "hermes3:latest"))
    timeout_seconds: int = field(default_factory=lambda: _env_int("OLLAMA_TIMEOUT", 120))
    max_retries: int = field(default_factory=lambda: _env_int("OLLAMA_MAX_RETRIES", 2))
    retry_delay_seconds: float = field(default_factory=lambda: _env_float("OLLAMA_RETRY_DELAY", 1.0))
    default_temperature: float = field(default_factory=lambda: _env_float("OLLAMA_TEMPERATURE", 0.7))
    default_max_tokens: int = field(default_factory=lambda: _env_int("OLLAMA_MAX_TOKENS", 2048))
    verify_ssl: bool = field(default_factory=lambda: _env_bool("OLLAMA_VERIFY_SSL", False))

    @property
    def generate_url(self) -> str:
        return f"{self.base_url}/api/generate"

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    @property
    def tags_url(self) -> str:
        return f"{self.base_url}/api/tags"


# ---------------------------------------------------------------------------
# Memory Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemoryConfig:
    """Controls conversation memory behaviour."""
    short_term_max_messages: int = field(default_factory=lambda: _env_int("AI_MEMORY_SHORT_TERM_MAX", 20))
    long_term_max_entries: int = field(default_factory=lambda: _env_int("AI_MEMORY_LONG_TERM_MAX", 500))
    summary_threshold: int = field(default_factory=lambda: _env_int("AI_MEMORY_SUMMARY_THRESHOLD", 15))
    embedding_dimensions: int = field(default_factory=lambda: _env_int("AI_MEMORY_EMBEDDING_DIMS", 384))
    enable_long_term: bool = field(default_factory=lambda: _env_bool("AI_MEMORY_LONG_TERM_ENABLED", True))
    context_window_messages: int = field(default_factory=lambda: _env_int("AI_MEMORY_CONTEXT_WINDOW", 10))
    conversation_max_turns: int = field(default_factory=lambda: _env_int("AI_MEMORY_CONVERSATION_MAX_TURNS", 10))
    auto_summarize: bool = field(default_factory=lambda: _env_bool("AI_MEMORY_AUTO_SUMMARIZE", True))


# ---------------------------------------------------------------------------
# Agent Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentConfig:
    """High-level agent behaviour knobs."""
    max_plan_steps: int = field(default_factory=lambda: _env_int("AI_MAX_PLAN_STEPS", 5))
    max_reasoning_iterations: int = field(default_factory=lambda: _env_int("AI_MAX_REASONING_ITERATIONS", 3))
    enable_planning: bool = field(default_factory=lambda: _env_bool("AI_ENABLE_PLANNING", True))
    enable_reasoning: bool = field(default_factory=lambda: _env_bool("AI_ENABLE_REASONING", True))
    default_language: str = field(default_factory=lambda: _env("AI_DEFAULT_LANGUAGE", "fr"))
    supported_languages: List[str] = field(
        default_factory=lambda: _env("AI_SUPPORTED_LANGUAGES", "fr,ar,en").split(",")
    )
    fallback_response: str = field(
        default_factory=lambda: _env(
            "AI_FALLBACK_RESPONSE",
            "Je suis désolé, je ne peux pas traiter votre demande pour le moment.",
        )
    )
    system_prompt: str = field(default_factory=lambda: _env("AI_SYSTEM_PROMPT", ""))
    log_prompts: bool = field(default_factory=lambda: _env_bool("AI_LOG_PROMPTS", False))
    log_responses: bool = field(default_factory=lambda: _env_bool("AI_LOG_RESPONSES", True))


# ---------------------------------------------------------------------------
# Tool Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolConfig:
    """Registry-level tool settings."""
    enabled_tools: List[str] = field(
        default_factory=lambda: _env("AI_ENABLED_TOOLS", "").split(",") if _env("AI_ENABLED_TOOLS") else []
    )
    disabled_tools: List[str] = field(
        default_factory=lambda: _env("AI_DISABLED_TOOLS", "").split(",") if _env("AI_DISABLED_TOOLS") else []
    )
    tool_timeout_seconds: int = field(default_factory=lambda: _env_int("AI_TOOL_TIMEOUT", 30))
    allow_parallel_execution: bool = field(default_factory=lambda: _env_bool("AI_PARALLEL_TOOLS", False))


# ---------------------------------------------------------------------------
# RAG Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RAGConfig:
    """Retrieval Augmented Generation settings."""
    enabled: bool = field(default_factory=lambda: _env_bool("AI_RAG_ENABLED", True))
    top_k: int = field(default_factory=lambda: _env_int("AI_RAG_TOP_K", 5))
    min_score: float = field(default_factory=lambda: _env_float("AI_RAG_MIN_SCORE", 0.1))
    max_context_chars: int = field(default_factory=lambda: _env_int("AI_RAG_MAX_CONTEXT_CHARS", 4000))
    chunk_size: int = field(default_factory=lambda: _env_int("AI_RAG_CHUNK_SIZE", 1000))
    chunk_overlap: int = field(default_factory=lambda: _env_int("AI_RAG_CHUNK_OVERLAP", 200))
    persist_directory: str = field(default_factory=lambda: _env("AI_RAG_PERSIST_DIR", ""))
    auto_index_on_startup: bool = field(default_factory=lambda: _env_bool("AI_RAG_AUTO_INDEX", True))
    search_before_model: bool = field(default_factory=lambda: _env_bool("AI_RAG_SEARCH_BEFORE_MODEL", True))
    sources: List[str] = field(
        default_factory=lambda: _env(
            "AI_RAG_SOURCES",
            "glossary,nomenclature,regulations,procedures",
        ).split(",")
    )


# ---------------------------------------------------------------------------
# Aggregate Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AIConfig:
    """Top-level configuration container for the entire AI Core."""
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    tool: ToolConfig = field(default_factory=ToolConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)

    @classmethod
    def from_env(cls) -> "AIConfig":
        """Build the config from environment variables."""
        return cls(
            ollama=OllamaConfig(),
            memory=MemoryConfig(),
            agent=AgentConfig(),
            tool=ToolConfig(),
            rag=RAGConfig(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (useful for health-checks)."""
        return {
            "ollama": {
                "base_url": self.ollama.base_url,
                "model": self.ollama.model,
                "timeout": self.ollama.timeout_seconds,
            },
            "memory": {
                "short_term_max": self.memory.short_term_max_messages,
                "long_term_max": self.memory.long_term_max_entries,
            },
            "agent": {
                "max_plan_steps": self.agent.max_plan_steps,
                "enable_planning": self.agent.enable_planning,
                "enable_reasoning": self.agent.enable_reasoning,
                "default_language": self.agent.default_language,
            },
            "tool": {
                "enabled_count": len(self.tool.enabled_tools),
                "disabled_count": len(self.tool.disabled_tools),
            },
            "rag": {
                "enabled": self.rag.enabled,
                "top_k": self.rag.top_k,
                "sources": self.rag.sources,
                "search_before_model": self.rag.search_before_model,
            },
        }
