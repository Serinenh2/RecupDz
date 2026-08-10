"""Enterprise OfflineMode — resilience layer for production AI systems.

Components:
    CircuitBreaker — prevents cascading failures via state machine
    Retry — configurable retry with exponential backoff + jitter
    FallbackChain — ordered fallback with primary → cache → deterministic
    OfflineCacheManager — offline-aware caching with stale-while-revalidate
    HealthMonitor — real-time health tracking for all critical services
    OfflineBanner — frontend notification of degraded mode
    OfflineMode — top-level orchestrator wiring everything together
"""

from apps.ai_assistant.enterprise.offline_mode.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitEvent,
    CircuitMetrics,
)
from apps.ai_assistant.enterprise.offline_mode.retry import (
    RetryPolicy,
    RetryResult,
)
from apps.ai_assistant.enterprise.offline_mode.fallback import (
    FallbackChain,
    FallbackResult,
    FallbackStep,
)
from apps.ai_assistant.enterprise.offline_mode.cache import (
    OfflineCacheManager,
    CacheLevel,
    CachedEntry,
)
from apps.ai_assistant.enterprise.offline_mode.health_monitor import (
    ServiceHealthMonitor,
    ServiceStatus,
    ServiceHealth,
    SystemHealthReport,
)
from apps.ai_assistant.enterprise.offline_mode.offline_banner import (
    OfflineBanner,
    BannerSeverity,
    BannerMessage,
)
from apps.ai_assistant.enterprise.offline_mode.orchestrator import (
    OfflineMode,
    OfflineModeResult,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitEvent",
    "CircuitMetrics",
    "RetryPolicy",
    "RetryResult",
    "FallbackChain",
    "FallbackResult",
    "FallbackStep",
    "OfflineCacheManager",
    "CacheLevel",
    "CachedEntry",
    "ServiceHealthMonitor",
    "ServiceStatus",
    "ServiceHealth",
    "SystemHealthReport",
    "OfflineBanner",
    "BannerSeverity",
    "BannerMessage",
    "OfflineMode",
    "OfflineModeResult",
]
