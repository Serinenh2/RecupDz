"""
Offline Banner — frontend notification of degraded mode.

Features:
    Generates banner messages for degraded/offline state
    Severity levels: info, warning, error
    Auto-hides when services recover
    Supports multiple simultaneous banners
    French/English bilingual messages
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class BannerSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class BannerMessage:
    id: str
    severity: BannerSeverity
    title: str
    message: str
    details: str = ""
    timestamp: float = 0.0
    auto_hide_seconds: float = 0.0
    service: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "auto_hide_seconds": self.auto_hide_seconds,
            "service": self.service,
            "metadata": dict(self.metadata),
        }

    @property
    def should_auto_hide(self) -> bool:
        if self.auto_hide_seconds <= 0:
            return False
        return (time.time() - self.timestamp) > self.auto_hide_seconds


class OfflineBanner:
    """Manages banner messages for offline/degraded mode."""

    def __init__(self) -> None:
        self._active: Dict[str, BannerMessage] = {}
        self._history: List[BannerMessage] = []

    @property
    def active_banners(self) -> List[BannerMessage]:
        self._prune_expired()
        return list(self._active.values())

    def show(
        self,
        *,
        service: str,
        severity: BannerSeverity,
        title: str,
        message: str,
        details: str = "",
        auto_hide_seconds: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BannerMessage:
        banner_id = f"{service}:{severity.value}"
        banner = BannerMessage(
            id=banner_id,
            severity=severity,
            title=title,
            message=message,
            details=details,
            timestamp=time.time(),
            auto_hide_seconds=auto_hide_seconds,
            service=service,
            metadata=metadata or {},
        )
        self._active[banner_id] = banner
        self._history.append(banner)
        return banner

    def hide(self, banner_id: str) -> bool:
        banner = self._active.pop(banner_id, None)
        return banner is not None

    def hide_all(self) -> int:
        count = len(self._active)
        self._active.clear()
        return count

    def hide_for_service(self, service: str) -> int:
        keys = [k for k in self._active if k.startswith(f"{service}:")]
        for k in keys:
            self._active.pop(k, None)
        return len(keys)

    def get_dict(self) -> Dict[str, Any]:
        self._prune_expired()
        return {
            "has_banners": len(self._active) > 0,
            "banners": [b.to_dict() for b in self._active.values()],
            "count": len(self._active),
        }

    def _prune_expired(self) -> None:
        expired = [k for k, v in self._active.items() if v.should_auto_hide]
        for k in expired:
            self._active.pop(k, None)

    @staticmethod
    def ollama_down_banner() -> BannerMessage:
        return BannerMessage(
            id="ollama:warning",
            severity=BannerSeverity.WARNING,
            title="Modèle IA indisponible",
            message="Hermes 3 est temporairement indisponible. Les réponses utilisent le cache.",
            service="ollama",
        )

    @staticmethod
    def knowledge_down_banner() -> BannerMessage:
        return BannerMessage(
            id="knowledge_search:warning",
            severity=BannerSeverity.WARNING,
            title="Base de connaissances indisponible",
            message="La recherche de connaissances est temporairement indisponible.",
            service="knowledge_search",
        )

    @staticmethod
    def database_down_banner() -> BannerMessage:
        return BannerMessage(
            id="database:error",
            severity=BannerSeverity.ERROR,
            title="Base de données indisponible",
            message="La base de données est temporairement inaccessible.",
            service="database",
        )

    @staticmethod
    def fully_offline_banner() -> BannerMessage:
        return BannerMessage(
            id="system:error",
            severity=BannerSeverity.ERROR,
            title="Mode hors ligne",
            message="Tous les services sont indisponibles. Mode dégradé activé.",
            service="system",
        )
