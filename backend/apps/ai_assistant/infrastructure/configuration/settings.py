"""
Enterprise Configuration — centralized configuration management.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class OllamaSettings:
    """Ollama LLM settings."""
    base_url: str = "http://localhost:11434"
    model: str = "hermes3:latest"
    timeout: float = 30.0
    max_retries: int = 3
    temperature: float = 0.7
    max_tokens: int = 2048


@dataclass
class CacheSettings:
    """Cache settings."""
    backend: str = "memory"  # memory, redis
    max_size: int = 1000
    default_ttl: float = 300.0
    redis_url: Optional[str] = None


@dataclass
class RateLimitSettings:
    """Rate limiting settings."""
    enabled: bool = True
    strategy: str = "sliding_window"
    default_limit: int = 60
    default_window: float = 60.0
    chat_limit: int = 30
    chat_window: float = 60.0


@dataclass
class SecuritySettings:
    """Security settings."""
    max_message_length: int = 10000
    max_parameter_length: int = 1000
    sanitize_input: bool = True
    block_on_threat: bool = False
    audit_enabled: bool = True


@dataclass
class MonitoringSettings:
    """Monitoring and observability settings."""
    health_check_enabled: bool = True
    metrics_enabled: bool = True
    metrics_namespace: str = "ai_assistant"
    tracing_enabled: bool = True
    tracing_service_name: str = "ai_assistant"
    audit_enabled: bool = True
    audit_max_events: int = 10000
    performance_profiling: bool = False


@dataclass
class AgentSettings:
    """AI agent settings."""
    max_tool_rounds: int = 5
    default_confidence_threshold: float = 0.6
    clarification_threshold: float = 0.4
    enable_streaming: bool = True
    enable_tool_calling: bool = True
    fallback_response: str = (
        "Je peux vous aider avec la gestion des dechets speciaux. "
        "Comment puis-je vous aider?"
    )


@dataclass
class EnterpriseConfig:
    """
    Centralized enterprise configuration.
    Loads from environment variables with sensible defaults.
    """

    # Sub-configs
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    rate_limit: RateLimitSettings = field(default_factory=RateLimitSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)

    # General
    debug: bool = False
    log_level: str = "INFO"
    api_version: str = "v1"

    @classmethod
    def from_env(cls) -> "EnterpriseConfig":
        """Load configuration from environment variables."""
        config = cls()

        # Ollama
        config.ollama.base_url = os.getenv("OLLAMA_BASE_URL", config.ollama.base_url)
        config.ollama.model = os.getenv("OLLAMA_MODEL", config.ollama.model)
        config.ollama.timeout = float(os.getenv("OLLAMA_TIMEOUT", str(config.ollama.timeout)))

        # Cache
        config.cache.backend = os.getenv("CACHE_BACKEND", config.cache.backend)
        config.cache.redis_url = os.getenv("REDIS_URL")
        config.cache.default_ttl = float(os.getenv("CACHE_TTL", str(config.cache.default_ttl)))

        # Rate Limiting
        config.rate_limit.enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        config.rate_limit.default_limit = int(os.getenv("RATE_LIMIT_DEFAULT", str(config.rate_limit.default_limit)))

        # Security
        config.security.sanitize_input = os.getenv("SANITIZE_INPUT", "true").lower() == "true"
        config.security.audit_enabled = os.getenv("AUDIT_ENABLED", "true").lower() == "true"

        # Monitoring
        config.monitoring.metrics_enabled = os.getenv("METRICS_ENABLED", "true").lower() == "true"
        config.monitoring.tracing_enabled = os.getenv("TRACING_ENABLED", "true").lower() == "true"

        # Agent
        config.agent.max_tool_rounds = int(os.getenv("MAX_TOOL_ROUNDS", str(config.agent.max_tool_rounds)))

        # General
        config.debug = os.getenv("DEBUG", "false").lower() == "true"
        config.log_level = os.getenv("LOG_LEVEL", config.log_level)

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "debug": self.debug,
            "log_level": self.log_level,
            "api_version": self.api_version,
            "ollama": {
                "base_url": self.ollama.base_url,
                "model": self.ollama.model,
                "timeout": self.ollama.timeout,
            },
            "cache": {
                "backend": self.cache.backend,
                "max_size": self.cache.max_size,
                "default_ttl": self.cache.default_ttl,
            },
            "rate_limit": {
                "enabled": self.rate_limit.enabled,
                "strategy": self.rate_limit.strategy,
                "default_limit": self.rate_limit.default_limit,
            },
            "security": {
                "sanitize_input": self.security.sanitize_input,
                "audit_enabled": self.security.audit_enabled,
            },
            "monitoring": {
                "metrics_enabled": self.monitoring.metrics_enabled,
                "tracing_enabled": self.monitoring.tracing_enabled,
            },
            "agent": {
                "max_tool_rounds": self.agent.max_tool_rounds,
                "enable_streaming": self.agent.enable_streaming,
                "enable_tool_calling": self.agent.enable_tool_calling,
            },
        }
