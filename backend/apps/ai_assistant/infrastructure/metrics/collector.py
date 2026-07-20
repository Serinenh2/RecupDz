"""
Metrics Collector — Prometheus-compatible metrics collection.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    help_text: str = ""


class MetricsCollector:
    """
    Thread-safe metrics collector with Prometheus-compatible output.
    """

    def __init__(self, namespace: str = "ai_assistant") -> None:
        self._namespace = namespace
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._labels: Dict[str, Dict[str, str]] = {}
        self._lock = threading.RLock()
        self._start_time = time.time()

    # -- Counter --

    def inc_counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            key = self._key(name, labels)
            self._counters[key] += value
            self._labels[key] = labels

    # -- Gauge --

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            key = self._key(name, labels)
            self._gauges[key] = value
            self._labels[key] = labels

    def inc_gauge(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            key = self._key(name, labels)
            self._gauges[key] += value
            self._labels[key] = labels

    def dec_gauge(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            key = self._key(name, labels)
            self._gauges[key] -= value
            self._labels[key] = labels

    # -- Histogram --

    def observe_histogram(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            key = self._key(name, labels)
            self._histograms[key].append(value)
            self._labels[key] = labels

    # -- Convenience --

    def timer(self, name: str, **labels: str) -> "_TimerContext":
        """Context manager for timing operations."""
        return _TimerContext(self, name, labels)

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record an HTTP request metric."""
        self.inc_counter("http_requests_total", endpoint=endpoint, method=method, status=str(status_code))
        self.observe_histogram("http_request_duration_ms", duration_ms, endpoint=endpoint, method=method)

    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
    ) -> None:
        """Record a tool execution metric."""
        self.inc_counter("tool_calls_total", tool_name=tool_name, success=str(success))
        self.observe_histogram("tool_call_duration_ms", duration_ms, tool_name=tool_name)

    def record_llm_call(
        self,
        model: str,
        success: bool,
        duration_ms: float,
        tokens: int = 0,
    ) -> None:
        """Record an LLM call metric."""
        self.inc_counter("llm_calls_total", model=model, success=str(success))
        self.observe_histogram("llm_call_duration_ms", duration_ms, model=model)
        if tokens > 0:
            self.inc_counter("llm_tokens_total", model=model, value=float(tokens))

    # -- Query --

    def get_counter(self, name: str, **labels: str) -> float:
        key = self._key(name, labels)
        return self._counters.get(key, 0.0)

    def get_gauge(self, name: str, **labels: str) -> float:
        key = self._key(name, labels)
        return self._gauges.get(key, 0.0)

    def get_histogram(self, name: str, **labels: str) -> Dict[str, float]:
        key = self._key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}
        sorted_vals = sorted(values)
        count = len(sorted_vals)
        return {
            "count": count,
            "sum": round(sum(sorted_vals), 2),
            "avg": round(sum(sorted_vals) / count, 2),
            "min": round(sorted_vals[0], 2),
            "max": round(sorted_vals[-1], 2),
            "p50": round(sorted_vals[count // 2], 2),
            "p95": round(sorted_vals[int(count * 0.95)], 2) if count >= 20 else round(sorted_vals[-1], 2),
            "p99": round(sorted_vals[int(count * 0.99)], 2) if count >= 100 else round(sorted_vals[-1], 2),
        }

    # -- Export --

    def to_dict(self) -> Dict[str, Any]:
        """Export all metrics as a dictionary."""
        with self._lock:
            return {
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: self.get_histogram(k.split("|")[0])
                    for k in self._histograms
                },
            }

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: List[str] = []

        with self._lock:
            for key, value in self._counters.items():
                name = key.split("|")[0]
                labels = self._labels.get(key, {})
                label_str = self._format_labels(labels)
                lines.append(f"{self._namespace}_{name}{label_str} {value}")

            for key, value in self._gauges.items():
                name = key.split("|")[0]
                labels = self._labels.get(key, {})
                label_str = self._format_labels(labels)
                lines.append(f"{self._namespace}_{name}{label_str} {value}")

            for key in self._histograms:
                name = key.split("|")[0]
                stats = self.get_histogram(name)
                labels = self._labels.get(key, {})
                for stat_name, stat_value in stats.items():
                    label_str = self._format_labels({**labels, "quantile": stat_name})
                    lines.append(f"{self._namespace}_{name}{label_str} {stat_value}")

        return "\n".join(lines)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._labels.clear()
            self._start_time = time.time()

    def _key(self, name: str, labels: Dict[str, str]) -> str:
        label_parts = ":".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}|{label_parts}" if label_parts else name

    @staticmethod
    def _format_labels(labels: Dict[str, str]) -> str:
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(parts) + "}"


class _TimerContext:
    """Context manager for timing metric observations."""

    def __init__(self, collector: MetricsCollector, name: str, labels: Dict[str, str]) -> None:
        self._collector = collector
        self._name = name
        self._labels = labels
        self._start: float = 0

    def __enter__(self) -> "_TimerContext":
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed = (time.monotonic() - self._start) * 1000
        self._collector.observe_histogram(self._name, elapsed, **self._labels)
