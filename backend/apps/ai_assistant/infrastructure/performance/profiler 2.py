"""
Performance Profiler — timing and resource usage tracking.
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimingRecord:
    """Record of a timed operation."""
    name: str
    start_time: float = field(default_factory=time.monotonic)
    end_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        end = self.end_time if self.end_time > 0 else time.monotonic()
        return (end - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 2),
            **self.metadata,
        }


@dataclass
class PerformanceReport:
    """Aggregated performance report."""
    operation: str
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "count": self.count,
            "total_ms": round(self.total_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
        }


class Profiler:
    """
    Thread-safe performance profiler with histogram support.
    """

    def __init__(self, enabled: bool = True, max_records: int = 10000) -> None:
        self._enabled = enabled
        self._max_records = max_records
        self._records: Dict[str, List[TimingRecord]] = defaultdict(list)
        self._lock = threading.RLock()
        self._active: Dict[str, TimingRecord] = {}

    @contextmanager
    def track(self, name: str, **metadata: Any) -> Generator[None, None, None]:
        """Context manager to time a block of code."""
        if not self._enabled:
            yield
            return

        record = TimingRecord(name=name, metadata=metadata)
        thread_id = threading.get_ident()
        key = f"{name}:{thread_id}"
        self._active[key] = record

        try:
            yield
        finally:
            record.end_time = time.monotonic()
            self._store(record)
            self._active.pop(key, None)

    def start(self, name: str, **metadata: Any) -> str:
        """Manual start. Returns a handle for stopping."""
        handle = f"{name}:{threading.get_ident()}:{time.monotonic()}"
        record = TimingRecord(name=name, metadata=metadata)
        self._active[handle] = record
        return handle

    def stop(self, handle: str) -> Optional[TimingRecord]:
        """Manual stop using handle from start()."""
        record = self._active.pop(handle, None)
        if record:
            record.end_time = time.monotonic()
            self._store(record)
        return record

    def report(self, name: Optional[str] = None) -> Dict[str, PerformanceReport]:
        """Generate performance reports."""
        with self._lock:
            names = [name] if name else list(self._records.keys())
            reports: Dict[str, PerformanceReport] = {}

            for op_name in names:
                records = self._records.get(op_name, [])
                if not records:
                    continue

                durations = sorted(r.duration_ms for r in records)
                count = len(durations)

                reports[op_name] = PerformanceReport(
                    operation=op_name,
                    count=count,
                    total_ms=round(sum(durations), 2),
                    min_ms=round(durations[0], 2),
                    max_ms=round(durations[-1], 2),
                    avg_ms=round(sum(durations) / count, 2),
                    p50_ms=round(durations[count // 2], 2),
                    p95_ms=round(durations[int(count * 0.95)], 2) if count >= 20 else round(durations[-1], 2),
                    p99_ms=round(durations[int(count * 0.99)], 2) if count >= 100 else round(durations[-1], 2),
                )

            return reports

    def profile_function(self, func, *args, **kwargs) -> Any:
        """Profile a function call with cProfile."""
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()

        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative")
        stats.print_stats(20)

        logger.debug("Profile of %s:\n%s", func.__name__, stream.getvalue())
        return result

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._active.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "tracked_operations": len(self._records),
                "total_records": sum(len(r) for r in self._records.values()),
            }

    def _store(self, record: TimingRecord) -> None:
        with self._lock:
            records = self._records[record.name]
            if len(records) >= self._max_records:
                records.pop(0)
            records.append(record)
