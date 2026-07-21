"""
Distributed Tracer — request-level tracing with span hierarchy.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """A single trace span."""
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    trace_id: str = ""
    parent_id: Optional[str] = None
    name: str = ""
    start_time: float = field(default_factory=time.monotonic)
    end_time: float = 0.0
    status: str = "ok"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time == 0.0:
            return (time.monotonic() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    @property
    def is_finished(self) -> bool:
        return self.end_time > 0.0

    def finish(self, status: str = "ok") -> None:
        self.end_time = time.monotonic()
        self.status = status

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class Tracer:
    """
    Thread-safe distributed tracer with span hierarchy.
    """

    def __init__(self, service_name: str = "ai_assistant") -> None:
        self._service_name = service_name
        self._traces: Dict[str, List[Span]] = {}
        self._active_spans: Dict[str, Span] = {}
        self._lock = threading.RLock()
        self._completed_traces: List[Dict[str, Any]] = []
        self._max_completed = 1000

    def start_trace(self, name: str, **attributes: Any) -> Span:
        """Start a new trace with a root span."""
        trace_id = uuid.uuid4().hex[:12]
        span = Span(
            trace_id=trace_id,
            name=name,
            attributes={**attributes, "service": self._service_name},
        )
        with self._lock:
            self._traces[trace_id] = [span]
            self._active_spans[trace_id] = span
        return span

    def start_span(
        self,
        trace_id: str,
        name: str,
        parent_id: Optional[str] = None,
        **attributes: Any,
    ) -> Span:
        """Start a child span within a trace."""
        span = Span(
            trace_id=trace_id,
            parent_id=parent_id,
            name=name,
            attributes=attributes,
        )
        with self._lock:
            if trace_id in self._traces:
                self._traces[trace_id].append(span)
        return span

    def finish_span(self, span: Span, status: str = "ok") -> None:
        """Finish a span."""
        span.finish(status)

        with self._lock:
            trace_id = span.trace_id
            if trace_id in self._active_spans:
                active = self._active_spans[trace_id]
                if active.span_id == span.span_id:
                    # Root span finished — complete the trace
                    if trace_id in self._traces:
                        trace_data = self._build_trace(trace_id)
                        self._completed_traces.append(trace_data)
                        if len(self._completed_traces) > self._max_completed:
                            self._completed_traces = self._completed_traces[-self._max_completed:]
                    del self._active_spans[trace_id]

    def finish_trace(self, trace_id: str, status: str = "ok") -> None:
        """Finish all spans in a trace."""
        with self._lock:
            if trace_id in self._active_spans:
                span = self._active_spans[trace_id]
                self.finish_span(span, status)

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a trace by ID."""
        with self._lock:
            return self._build_trace(trace_id) if trace_id in self._traces else None

    def get_active_trace(self) -> Optional[str]:
        """Get the most recent active trace ID."""
        with self._lock:
            if self._active_spans:
                return list(self._active_spans.keys())[-1]
        return None

    def query(
        self,
        service: Optional[str] = None,
        min_duration_ms: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query completed traces."""
        results = self._completed_traces

        if service:
            results = [
                t for t in results
                if any(s.get("attributes", {}).get("service") == service for s in t.get("spans", []))
            ]

        if min_duration_ms is not None:
            results = [t for t in results if t.get("total_duration_ms", 0) >= min_duration_ms]

        return results[-limit:]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_traces": len(self._active_spans),
                "completed_traces": len(self._completed_traces),
                "total_spans": sum(len(spans) for spans in self._traces.values()),
            }

    def _build_trace(self, trace_id: str) -> Dict[str, Any]:
        spans = self._traces.get(trace_id, [])
        total_duration = 0.0
        if spans:
            earliest = min(s.start_time for s in spans)
            latest = max(s.end_time if s.end_time > 0 else time.monotonic() for s in spans)
            total_duration = (latest - earliest) * 1000

        return {
            "trace_id": trace_id,
            "service": self._service_name,
            "total_duration_ms": round(total_duration, 2),
            "span_count": len(spans),
            "spans": [s.to_dict() for s in spans],
        }
