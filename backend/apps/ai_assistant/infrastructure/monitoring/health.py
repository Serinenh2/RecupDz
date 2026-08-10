"""
Health Check — system health monitoring with component status.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Aggregated health report."""
    status: HealthStatus
    components: List[ComponentHealth] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "version": self.version,
            "timestamp": self.timestamp,
            "components": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": round(c.latency_ms, 1),
                    **c.metadata,
                }
                for c in self.components
            ],
        }


class HealthCheck:
    """Registry of health check functions."""

    def __init__(self, version: str = "1.0.0") -> None:
        self._checks: List[Callable[[], ComponentHealth]] = []
        self._version = version

    def register(self, check: Callable[[], ComponentHealth]) -> None:
        self._checks.append(check)

    def check_all(self) -> HealthReport:
        components: List[ComponentHealth] = []
        overall = HealthStatus.HEALTHY

        for check_fn in self._checks:
            try:
                start = time.monotonic()
                component = check_fn()
                component.latency_ms = (time.monotonic() - start) * 1000
                components.append(component)

                if component.status == HealthStatus.UNHEALTHY:
                    overall = HealthStatus.UNHEALTHY
                elif component.status == HealthStatus.DEGRADED and overall != HealthStatus.UNHEALTHY:
                    overall = HealthStatus.DEGRADED

            except Exception as exc:
                components.append(ComponentHealth(
                    name=check_fn.__name__,
                    status=HealthStatus.UNHEALTHY,
                    message=str(exc),
                ))
                overall = HealthStatus.UNHEALTHY

        return HealthReport(
            status=overall,
            components=components,
            version=self._version,
        )

    def check_component(self, name: str) -> Optional[ComponentHealth]:
        for check_fn in self._checks:
            if check_fn.__name__ == name:
                try:
                    return check_fn()
                except Exception as exc:
                    return ComponentHealth(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=str(exc),
                    )
        return None
