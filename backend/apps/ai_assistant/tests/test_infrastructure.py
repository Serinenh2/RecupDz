"""
Unit tests for infrastructure modules — integration verification.

Tests:
    - CacheManager (LRU, TTL, stats)
    - MetricsCollector (counters, histograms, Prometheus export)
    - Tracer (traces, spans, hierarchy)
    - AuditLogger (logging, querying, stats)
    - HealthCheck (component registration, report)
"""

from __future__ import annotations

import time
import unittest

from apps.ai_assistant.infrastructure.audit.audit import AuditAction, AuditEvent, AuditLogger
from apps.ai_assistant.infrastructure.caching.cache import CacheManager, InMemoryCache
from apps.ai_assistant.infrastructure.metrics.collector import MetricsCollector
from apps.ai_assistant.infrastructure.monitoring.health import (
    ComponentHealth, HealthCheck, HealthStatus,
)
from apps.ai_assistant.infrastructure.tracing.tracer import Tracer


# ---------------------------------------------------------------------------
# CacheManager
# ---------------------------------------------------------------------------


class TestCacheManager(unittest.TestCase):

    def setUp(self):
        self.cache = CacheManager(
            backend=InMemoryCache(max_size=5, default_ttl=10.0),
            prefix="test",
            default_ttl=10.0,
        )

    def test_set_get(self):
        self.cache.set("k1", "v1")
        self.assertEqual(self.cache.get("k1"), "v1")

    def test_prefix_isolation(self):
        other = CacheManager(prefix="other")
        self.cache.set("k1", "v1")
        other.set("k1", "v2")
        self.assertEqual(self.cache.get("k1"), "v1")
        self.assertEqual(other.get("k1"), "v2")

    def test_ttl_expiration(self):
        cache = CacheManager(
            backend=InMemoryCache(max_size=10, default_ttl=0.1),
            default_ttl=0.1,
        )
        cache.set("k1", "v1")
        self.assertEqual(cache.get("k1"), "v1")
        time.sleep(0.15)
        self.assertIsNone(cache.get("k1"))

    def test_lru_eviction(self):
        for i in range(5):
            self.cache.set(f"k{i}", f"v{i}")
        # Adding a 6th item should evict k0
        self.cache.set("k5", "v5")
        self.assertIsNone(self.cache.get("k0"))
        self.assertEqual(self.cache.get("k5"), "v5")

    def test_make_key_deterministic(self):
        k1 = CacheManager.make_key("a", "b", "c")
        k2 = CacheManager.make_key("a", "b", "c")
        self.assertEqual(k1, k2)

    def test_stats(self):
        self.cache.set("a", 1)
        self.cache.get("a")
        self.cache.get("missing")
        stats = self.cache.stats()
        self.assertGreaterEqual(stats["hits"], 1)
        self.assertGreaterEqual(stats["misses"], 1)
        self.assertEqual(stats["size"], 1)

    def test_delete(self):
        self.cache.set("k1", "v1")
        self.assertTrue(self.cache.delete("k1"))
        self.assertIsNone(self.cache.get("k1"))

    def test_clear(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        count = self.cache.clear()
        self.assertEqual(count, 2)
        self.assertIsNone(self.cache.get("a"))


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------


class TestMetricsCollector(unittest.TestCase):

    def setUp(self):
        self.m = MetricsCollector(namespace="test")

    def test_counter(self):
        self.m.inc_counter("requests")
        self.m.inc_counter("requests", value=3)
        self.assertEqual(self.m.get_counter("requests"), 4.0)

    def test_gauge(self):
        self.m.set_gauge("connections", 10)
        self.m.inc_gauge("connections", 5)
        self.assertEqual(self.m.get_gauge("connections"), 15.0)
        self.m.dec_gauge("connections", 3)
        self.assertEqual(self.m.get_gauge("connections"), 12.0)

    def test_histogram(self):
        for v in [10, 20, 30]:
            self.m.observe_histogram("latency", v)
        stats = self.m.get_histogram("latency")
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["avg"], 20.0)

    def test_record_request(self):
        self.m.record_request("/api/chat", "POST", 200, 45.2)
        count = self.m.get_counter("http_requests_total",
                                   endpoint="/api/chat", method="POST", status="200")
        self.assertEqual(count, 1.0)

    def test_record_tool_call(self):
        self.m.record_tool_call("waste_tool", True, 120.5)
        count = self.m.get_counter("tool_calls_total",
                                   tool_name="waste_tool", success="True")
        self.assertEqual(count, 1.0)

    def test_to_dict(self):
        self.m.inc_counter("test")
        data = self.m.to_dict()
        self.assertIn("counters", data)
        self.assertIn("uptime_seconds", data)

    def test_to_prometheus(self):
        self.m.inc_counter("requests")
        prom = self.m.to_prometheus()
        self.assertIn("test_requests", prom)

    def test_reset(self):
        self.m.inc_counter("x")
        self.m.reset()
        self.assertEqual(self.m.get_counter("x"), 0.0)


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


class TestTracer(unittest.TestCase):

    def setUp(self):
        self.tracer = Tracer(service_name="test")

    def test_start_and_finish_trace(self):
        span = self.tracer.start_trace("op1")
        self.tracer.finish_trace(span.trace_id)
        stats = self.tracer.stats()
        self.assertEqual(stats["completed_traces"], 1)

    def test_child_spans(self):
        root = self.tracer.start_trace("root")
        child = self.tracer.start_span(root.trace_id, "child")
        self.tracer.finish_span(child)
        self.tracer.finish_trace(root.trace_id)
        trace = self.tracer.get_trace(root.trace_id)
        self.assertEqual(trace["span_count"], 2)

    def test_trace_duration(self):
        span = self.tracer.start_trace("op")
        time.sleep(0.01)
        self.tracer.finish_trace(span.trace_id)
        trace = self.tracer.get_trace(span.trace_id)
        self.assertGreater(trace["total_duration_ms"], 0)

    def test_stats(self):
        self.tracer.start_trace("a")
        stats = self.tracer.stats()
        self.assertEqual(stats["active_traces"], 1)

    def test_query(self):
        span = self.tracer.start_trace("q")
        self.tracer.finish_trace(span.trace_id)
        results = self.tracer.query()
        self.assertGreaterEqual(len(results), 1)


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class TestAuditLogger(unittest.TestCase):

    def setUp(self):
        self.audit = AuditLogger(max_events=100)

    def test_log_event(self):
        event = AuditEvent(
            action=AuditAction.CHAT,
            user_id="u1",
            resource_type="message",
            resource_id="r1",
        )
        self.audit.log(event)
        self.assertEqual(self.audit.count(), 1)

    def test_log_simple(self):
        self.audit.log_simple(
            action=AuditAction.TOOL_CALL,
            user_id="u2",
            resource_type="tool",
            resource_id="waste_tool",
        )
        self.assertEqual(self.audit.count(user_id="u2"), 1)

    def test_query_filter_action(self):
        self.audit.log_simple(action=AuditAction.CHAT, user_id="u1")
        self.audit.log_simple(action=AuditAction.TOOL_CALL, user_id="u1")
        chats = self.audit.query(action=AuditAction.CHAT)
        self.assertEqual(len(chats), 1)

    def test_max_events_eviction(self):
        audit = AuditLogger(max_events=3)
        for i in range(5):
            audit.log_simple(action=AuditAction.READ, user_id=f"u{i}")
        self.assertEqual(audit.count(), 3)

    def test_stats(self):
        self.audit.log_simple(action=AuditAction.CHAT, user_id="u1")
        stats = self.audit.stats()
        self.assertEqual(stats["total_events"], 1)
        self.assertIn("chat", stats["by_action"])

    def test_event_to_dict(self):
        event = AuditEvent(action=AuditAction.LOGIN, user_id="u1")
        d = event.to_dict()
        self.assertEqual(d["action"], "login")
        self.assertEqual(d["user_id"], "u1")


# ---------------------------------------------------------------------------
# HealthCheck
# ---------------------------------------------------------------------------


class TestHealthCheck(unittest.TestCase):

    def test_healthy_component(self):
        hc = HealthCheck()
        hc.register(lambda: ComponentHealth(
            name="db", status=HealthStatus.HEALTHY, message="OK",
        ))
        report = hc.check_all()
        self.assertEqual(report.status, HealthStatus.HEALTHY)
        self.assertEqual(len(report.components), 1)

    def test_unhealthy_component(self):
        hc = HealthCheck()
        hc.register(lambda: ComponentHealth(
            name="ollama", status=HealthStatus.UNHEALTHY, message="down",
        ))
        report = hc.check_all()
        self.assertEqual(report.status, HealthStatus.UNHEALTHY)

    def test_degraded_component(self):
        hc = HealthCheck()
        hc.register(lambda: ComponentHealth(
            name="cache", status=HealthStatus.DEGRADED, message="slow",
        ))
        report = hc.check_all()
        self.assertEqual(report.status, HealthStatus.DEGRADED)

    def test_report_to_dict(self):
        hc = HealthCheck(version="2.0")
        hc.register(lambda: ComponentHealth(
            name="x", status=HealthStatus.HEALTHY,
        ))
        report = hc.check_all()
        d = report.to_dict()
        self.assertEqual(d["version"], "2.0")
        self.assertEqual(d["status"], "healthy")

    def test_exception_in_check(self):
        hc = HealthCheck()
        def bad_check():
            raise RuntimeError("crash")
        hc.register(bad_check)
        report = hc.check_all()
        self.assertEqual(report.status, HealthStatus.UNHEALTHY)


if __name__ == "__main__":
    unittest.main()
