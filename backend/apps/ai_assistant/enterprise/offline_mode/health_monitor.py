"""
Service Health Monitor — real-time health tracking for critical services.

Monitors: Ollama, KnowledgeSearch, Database, Cache.
Used by OfflineMode to decide degradation strategy.
Exposes to frontend via OfflineBanner.
"""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceStatus(str, enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ServiceHealth:
    name: str
    status: ServiceStatus
    message: str = ""
    latency_ms: float = 0.0
    last_check: float = 0.0
    last_success: float = 0.0
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 2),
            "last_check": self.last_check,
            "last_success": self.last_success,
            "consecutive_failures": self.consecutive_failures,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SystemHealthReport:
    overall_status: ServiceStatus
    services: Dict[str, ServiceHealth]
    timestamp: float = 0.0
    is_fully_offline: bool = False
    offline_services: List[str] = field(default_factory=list)
    degraded_services: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "services": {k: v.to_dict() for k, v in self.services.items()},
            "timestamp": self.timestamp,
            "is_fully_offline": self.is_fully_offline,
            "offline_services": list(self.offline_services),
            "degraded_services": list(self.degraded_services),
        }

    @property
    def ollama_healthy(self) -> bool:
        s = self.services.get("ollama")
        return s is not None and s.status == ServiceStatus.HEALTHY

    @property
    def knowledge_healthy(self) -> bool:
        s = self.services.get("knowledge_search")
        return s is not None and s.status == ServiceStatus.HEALTHY

    @property
    def database_healthy(self) -> bool:
        s = self.services.get("database")
        return s is not None and s.status == ServiceStatus.HEALTHY


class ServiceHealthMonitor:
    """Tracks health of all critical services with failure tolerance.

    Each service has a check function that returns ServiceHealth.
    Failures are counted — service transitions to DOWN after consecutive_failures_threshold.
    """

    def __init__(
        self,
        *,
        check_interval_seconds: float = 30.0,
        consecutive_failures_threshold: int = 3,
        degraded_latency_ms: float = 2000.0,
    ) -> None:
        import threading
        self._lock = threading.RLock()
        self._check_interval = check_interval_seconds
        self._failure_threshold = consecutive_failures_threshold
        self._degraded_latency = degraded_latency_ms
        self._services: Dict[str, Callable[[], ServiceHealth]] = {}
        self._last_results: Dict[str, ServiceHealth] = {}
        self._last_check_time: float = 0.0
        self._callbacks: List[Callable[[str, ServiceStatus, ServiceStatus], None]] = []

    def register(
        self,
        name: str,
        check_fn: Callable[[], ServiceHealth],
    ) -> None:
        with self._lock:
            self._services[name] = check_fn
            logger.info("HealthMonitor: registered service '%s'", name)

    def on_status_change(
        self,
        callback: Callable[[str, ServiceStatus, ServiceStatus], None],
    ) -> None:
        with self._lock:
            self._callbacks.append(callback)

    def check_service(self, name: str) -> ServiceHealth:
        check_fn = self._services.get(name)
        if check_fn is None:
            return ServiceHealth(
                name=name,
                status=ServiceStatus.UNKNOWN,
                message=f"Service '{name}' not registered",
            )

        start = time.monotonic()
        try:
            result = check_fn()
            elapsed = (time.monotonic() - start) * 1000
            result = ServiceHealth(
                name=result.name,
                status=result.status,
                message=result.message,
                latency_ms=elapsed,
                last_check=time.monotonic(),
                last_success=time.monotonic() if result.status == ServiceStatus.HEALTHY else result.last_success,
                consecutive_failures=0 if result.status == ServiceStatus.HEALTHY else result.consecutive_failures,
                metadata=result.metadata,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            prev = self._last_results.get(name)
            prev_failures = prev.consecutive_failures if prev else 0
            status = ServiceStatus.DOWN if (prev_failures + 1) >= self._failure_threshold else ServiceStatus.DEGRADED
            result = ServiceHealth(
                name=name,
                status=status,
                message=str(exc),
                latency_ms=elapsed,
                last_check=time.monotonic(),
                consecutive_failures=prev_failures + 1,
            )

        old = self._last_results.get(name)
        with self._lock:
            self._last_results[name] = result

        if old and old.status != result.status:
            logger.info(
                "HealthMonitor: '%s' %s → %s",
                name, old.status.value, result.status.value,
            )
            for cb in self._callbacks:
                try:
                    cb(name, old.status, result.status)
                except Exception:
                    pass

        return result

    def check_all(self) -> SystemHealthReport:
        with self._lock:
            names = list(self._services.keys())

        results: Dict[str, ServiceHealth] = {}
        for name in names:
            results[name] = self.check_service(name)

        with self._lock:
            self._last_check_time = time.monotonic()

        return self._build_report(results)

    def get_status(self, name: str) -> ServiceHealth:
        with self._lock:
            if name in self._last_results:
                return self._last_results[name]
        return ServiceHealth(
            name=name,
            status=ServiceStatus.UNKNOWN,
            message="No check performed yet",
        )

    def system_report(self) -> SystemHealthReport:
        with self._lock:
            results = dict(self._last_results)
        if not results:
            return self.check_all()
        return self._build_report(results)

    def needs_check(self) -> bool:
        with self._lock:
            if not self._services:
                return False
            if self._last_check_time == 0:
                return True
            return (time.monotonic() - self._last_check_time) >= self._check_interval

    def reset(self) -> None:
        with self._lock:
            self._last_results.clear()
            self._last_check_time = 0.0

    def _build_report(self, results: Dict[str, ServiceHealth]) -> SystemHealthReport:
        offline = []
        degraded = []
        statuses = []

        for name, health in results.items():
            statuses.append(health.status)
            if health.status == ServiceStatus.DOWN:
                offline.append(name)
            elif health.status == ServiceStatus.DEGRADED:
                degraded.append(name)

        if all(s == ServiceStatus.DOWN for s in statuses) and statuses:
            overall = ServiceStatus.DOWN
            fully_offline = True
        elif any(s == ServiceStatus.DOWN for s in statuses):
            overall = ServiceStatus.DEGRADED
            fully_offline = False
        elif any(s == ServiceStatus.DEGRADED for s in statuses):
            overall = ServiceStatus.DEGRADED
            fully_offline = False
        else:
            overall = ServiceStatus.HEALTHY
            fully_offline = False

        return SystemHealthReport(
            overall_status=overall,
            services=results,
            timestamp=time.time(),
            is_fully_offline=fully_offline,
            offline_services=offline,
            degraded_services=degraded,
        )
