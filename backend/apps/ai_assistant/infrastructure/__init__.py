"""
Enterprise Infrastructure — production-grade AI module infrastructure.

Provides: Caching, Monitoring, Audit, Metrics, Tracing, Performance,
Rate Limiting, Permissions, Security, Configuration, Testing, Documentation.
"""

from apps.ai_assistant.infrastructure.caching.cache import CacheBackend, CacheManager
from apps.ai_assistant.infrastructure.monitoring.health import HealthCheck, HealthStatus
from apps.ai_assistant.infrastructure.audit.audit import AuditLogger, AuditEvent
from apps.ai_assistant.infrastructure.metrics.collector import MetricsCollector, MetricType
from apps.ai_assistant.infrastructure.tracing.tracer import Tracer, Span
from apps.ai_assistant.infrastructure.performance.profiler import Profiler, PerformanceReport
from apps.ai_assistant.infrastructure.rate_limiting.limiter import RateLimiter, RateLimitResult
from apps.ai_assistant.infrastructure.permissions.framework import PermissionManager, Permission
from apps.ai_assistant.infrastructure.security.sanitizer import InputSanitizer, SecurityLevel
from apps.ai_assistant.infrastructure.configuration.settings import EnterpriseConfig
from apps.ai_assistant.infrastructure.testing.fixtures import AITestCase, MockOllamaService
from apps.ai_assistant.infrastructure.documentation.openapi import APIDocumentation

__all__ = [
    # Caching
    "CacheBackend", "CacheManager",
    # Monitoring
    "HealthCheck", "HealthStatus",
    # Audit
    "AuditLogger", "AuditEvent",
    # Metrics
    "MetricsCollector", "MetricType",
    # Tracing
    "Tracer", "Span",
    # Performance
    "Profiler", "PerformanceReport",
    # Rate Limiting
    "RateLimiter", "RateLimitResult",
    # Permissions
    "PermissionManager", "Permission",
    # Security
    "InputSanitizer", "SecurityLevel",
    # Configuration
    "EnterpriseConfig",
    # Testing
    "AITestCase", "MockOllamaService",
    # Documentation
    "APIDocumentation",
]
