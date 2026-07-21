"""
Comprehensive tests for the Tool Registry infrastructure.

Covers all 7 framework components:
  - ToolResultResponse (ok, fail, from_exception, to_dict, to_json, merge)
  - ToolContext (permissions, roles, tracing, timeout, factory)
  - BaseTool (execute pipeline, lifecycle hooks, to_schema, validation)
  - ToolRegistry (register, discover, filter, search, tags, disable/enable)
  - ToolFactory (create_from_class_path, create_from_config, batch)
  - ToolExecutor (execute, batch, parallel, timeout, retry, middleware)
  - ToolValidator (via BaseTool integration)
   - Container tool registration (auto-discovery, count, types) — 22 tools
"""

from __future__ import annotations

import json
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_executor import (
    AuditMiddleware,
    ExecutionStats,
    LoggingMiddleware,
    RateLimitMiddleware,
    RetryPolicy,
    ToolExecutor,
    ToolMiddleware,
)
from apps.ai_assistant.tools.tool_factory import ToolConfig, ToolFactory, ToolFactoryError
from apps.ai_assistant.tools.tool_registry import ToolRegistry, ToolRegistryError
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import (
    FieldSchema,
    ParameterSchema,
    SchemaBuilder,
    ToolValidator,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Concrete test tools (no-arg constructors for discover_package)
# ---------------------------------------------------------------------------


class EchoTool(BaseTool):
    name = "echo_tool"
    description = "Echoes input"

    def _execute(self, parameters, context):
        return ToolResultResponse.ok(data=parameters.get("text", ""))


class FailingTool(BaseTool):
    name = "failing_tool"
    description = "Always raises"

    def _execute(self, parameters, context):
        raise ValueError("intentional failure")


class SlowTool(BaseTool):
    name = "slow_tool"
    description = "Sleeps"

    def _execute(self, parameters, context):
        time.sleep(parameters.get("delay", 1.0))
        return ToolResultResponse.ok(data="done")


class PermissionTool(BaseTool):
    name = "permission_tool"
    description = "Requires permission"

    @property
    def required_permissions(self):
        return ["admin"]

    def _execute(self, parameters, context):
        return ToolResultResponse.ok(data="granted")


class SchemaTool(BaseTool):
    name = "schema_tool"
    description = "Has a parameter schema"

    @property
    def parameter_schema(self):
        return ParameterSchema(
            fields=[
                FieldSchema(name="action", type="str", required=True, enum=["search", "list"]),
                FieldSchema(name="query", type="str", required=False, default=""),
            ]
        )

    def _execute(self, parameters, context):
        return ToolResultResponse.ok(data=parameters)


class HookTool(BaseTool):
    """Tool that records lifecycle hook calls."""

    name = "hook_tool"
    description = "Records hooks"

    def __init__(self):
        super().__init__()
        self.before_called = False
        self.after_called = False
        self.error_called = False

    def on_before_execute(self, parameters, context):
        self.before_called = True
        if parameters.get("abort"):
            return ToolResultResponse.fail(message="aborted by pre-hook")
        return None

    def on_after_execute(self, result, parameters, context):
        self.after_called = True

    def on_error(self, exc, parameters, context):
        self.error_called = True
        return None

    def _execute(self, parameters, context):
        if parameters.get("raise_error"):
            raise RuntimeError("hook test error")
        return ToolResultResponse.ok(data="ok")


# ===========================================================================
# Test: ToolResultResponse
# ===========================================================================


class TestToolResultResponse(unittest.TestCase):

    def test_ok(self):
        r = ToolResultResponse.ok(data={"k": "v"}, message="done")
        self.assertTrue(r.success)
        self.assertEqual(r.data, {"k": "v"})
        self.assertEqual(r.message, "done")

    def test_fail(self):
        r = ToolResultResponse.fail(message="bad", data={"x": 1})
        self.assertFalse(r.success)
        self.assertEqual(r.message, "bad")
        self.assertEqual(r.data, {"x": 1})

    def test_fail_no_data(self):
        r = ToolResultResponse.fail(message="bad")
        self.assertEqual(r.data, {})

    def test_from_exception(self):
        try:
            raise ValueError("boom")
        except ValueError as e:
            r = ToolResultResponse.from_exception(e, context="Tool 'test'")
        self.assertFalse(r.success)
        self.assertIn("ValueError", r.message)
        self.assertIn("boom", r.message)
        self.assertIn("Tool 'test'", r.message)

    def test_from_exception_no_context(self):
        r = ToolResultResponse.from_exception(RuntimeError("x"))
        self.assertIn("RuntimeError", r.message)
        self.assertNotIn("Tool", r.message)

    def test_to_dict(self):
        r = ToolResultResponse.ok(data=[1, 2])
        d = r.to_dict()
        self.assertEqual(d, {"success": True, "message": "", "data": [1, 2]})

    def test_to_dict_none_data(self):
        r = ToolResultResponse(success=True, message="m", data=None)
        d = r.to_dict()
        self.assertEqual(d["data"], {})

    def test_to_json(self):
        r = ToolResultResponse.ok(data="hello")
        j = r.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["success"], True)
        self.assertEqual(parsed["data"], "hello")

    def test_with_metadata(self):
        r = ToolResultResponse.ok(data=1)
        r.with_metadata(ts=123, env="test")
        self.assertEqual(r.metadata["ts"], 123)
        self.assertEqual(r.metadata["env"], "test")

    def test_merge_both_ok(self):
        a = ToolResultResponse.ok(data={"x": 1}, message="a")
        b = ToolResultResponse.ok(data={"y": 2}, message="b")
        merged = a.merge(b)
        self.assertTrue(merged.success)
        self.assertEqual(merged.data, {"x": 1, "y": 2})

    def test_merge_first_fails(self):
        a = ToolResultResponse.fail(message="fail a")
        b = ToolResultResponse.ok(data={"y": 2})
        merged = a.merge(b)
        self.assertFalse(merged.success)
        self.assertIn("fail a", merged.message)

    def test_merge_second_fails(self):
        a = ToolResultResponse.ok(data={"x": 1})
        b = ToolResultResponse.fail(message="fail b")
        merged = a.merge(b)
        self.assertFalse(merged.success)

    def test_merge_non_dict_data(self):
        a = ToolResultResponse.ok(data=[1, 2])
        b = ToolResultResponse.ok(data={"key": "val"})
        merged = a.merge(b)
        self.assertTrue(merged.success)
        self.assertEqual(merged.data["result"], [1, 2])
        self.assertEqual(merged.data["key"], "val")


# ===========================================================================
# Test: ToolContext
# ===========================================================================


class TestToolContext(unittest.TestCase):

    def test_defaults(self):
        ctx = ToolContext()
        self.assertTrue(ctx.request_id)
        self.assertEqual(ctx.language, "fr")
        self.assertEqual(ctx.total_timeout_seconds, 30.0)

    def test_factory(self):
        ctx = ToolContext.create(
            user_id="u1",
            conversation_id="c1",
            user_roles=["admin"],
            permissions=["read", "write"],
            language="en",
            timeout=60.0,
            entity_type="bsd",
            entity_id="123",
        )
        self.assertEqual(ctx.user_id, "u1")
        self.assertEqual(ctx.conversation_id, "c1")
        self.assertEqual(ctx.user_roles, ["admin"])
        self.assertEqual(ctx.language, "en")
        self.assertEqual(ctx.total_timeout_seconds, 60.0)
        self.assertEqual(ctx.entity_type, "bsd")
        self.assertTrue(ctx.has_permission("read"))
        self.assertTrue(ctx.has_permission("write"))

    def test_permissions(self):
        ctx = ToolContext()
        self.assertFalse(ctx.has_permission("admin"))
        ctx.grant_permission("admin")
        self.assertTrue(ctx.has_permission("admin"))

    def test_grant_permissions_batch(self):
        ctx = ToolContext()
        ctx.grant_permissions(["a", "b", "c"])
        self.assertTrue(ctx.has_permission("a"))
        self.assertTrue(ctx.has_permission("b"))

    def test_superadmin_bypasses_permissions(self):
        ctx = ToolContext(user_roles=["superadmin"])
        self.assertTrue(ctx.has_permission("anything"))

    def test_has_role(self):
        ctx = ToolContext(user_roles=["Admin", "User"])
        self.assertTrue(ctx.has_role("admin"))
        self.assertTrue(ctx.has_role("USER"))
        self.assertFalse(ctx.has_role("guest"))

    def test_trace(self):
        ctx = ToolContext()
        ctx.trace("event1", {"key": "value"})
        ctx.trace("event2")
        self.assertEqual(len(ctx.trace_log), 2)
        self.assertEqual(ctx.trace_log[0]["event"], "event1")
        self.assertEqual(ctx.trace_log[0]["details"], {"key": "value"})
        self.assertEqual(ctx.trace_log[1]["event"], "event2")
        self.assertEqual(ctx.trace_log[1]["details"], {})

    def test_elapsed_seconds(self):
        ctx = ToolContext()
        time.sleep(0.01)
        self.assertGreater(ctx.elapsed_seconds, 0)

    def test_remaining_timeout(self):
        ctx = ToolContext(total_timeout_seconds=1.0)
        self.assertLessEqual(ctx.remaining_timeout, 1.0)

    def test_is_expired(self):
        ctx = ToolContext(total_timeout_seconds=0.0)
        time.sleep(0.01)
        self.assertTrue(ctx.is_expired())

    def test_to_dict(self):
        ctx = ToolContext.create(user_id="u1", language="en")
        d = ctx.to_dict()
        self.assertEqual(d["user_id"], "u1")
        self.assertEqual(d["language"], "en")
        self.assertIn("request_id", d)
        self.assertIn("elapsed_seconds", d)


# ===========================================================================
# Test: BaseTool
# ===========================================================================


class TestBaseTool(unittest.TestCase):

    def test_execute_success(self):
        tool = EchoTool()
        ctx = ToolContext()
        result = tool.execute({"text": "hello"}, ctx)
        self.assertTrue(result.success)
        self.assertEqual(result.data, "hello")

    def test_execute_exception_wrapping(self):
        tool = FailingTool()
        ctx = ToolContext()
        result = tool.execute({}, ctx)
        self.assertFalse(result.success)
        self.assertIn("ValueError", result.message)

    def test_validation_fails(self):
        tool = SchemaTool()
        ctx = ToolContext()
        result = tool.execute({}, ctx)
        self.assertFalse(result.success)
        self.assertIn("Validation", result.message)

    def test_validation_passes(self):
        tool = SchemaTool()
        ctx = ToolContext()
        result = tool.execute({"action": "search"}, ctx)
        self.assertTrue(result.success)

    def test_permission_denied(self):
        tool = PermissionTool()
        ctx = ToolContext()
        result = tool.execute({}, ctx)
        self.assertFalse(result.success)
        self.assertIn("Permission", result.message)

    def test_permission_granted(self):
        tool = PermissionTool()
        ctx = ToolContext()
        ctx.grant_permission("admin")
        result = tool.execute({}, ctx)
        self.assertTrue(result.success)

    def test_before_hook_blocks(self):
        tool = HookTool()
        ctx = ToolContext()
        result = tool.execute({"abort": True}, ctx)
        self.assertFalse(result.success)
        self.assertIn("aborted", result.message)
        self.assertTrue(tool.before_called)
        self.assertFalse(tool.after_called)

    def test_after_hook_called(self):
        tool = HookTool()
        ctx = ToolContext()
        tool.execute({}, ctx)
        self.assertTrue(tool.after_called)

    def test_on_error_hook(self):
        tool = HookTool()
        ctx = ToolContext()
        tool.execute({"raise_error": True}, ctx)
        self.assertTrue(tool.error_called)

    def test_to_schema(self):
        tool = SchemaTool()
        schema = tool.to_schema()
        self.assertEqual(schema["name"], "schema_tool")
        self.assertIn("parameters", schema)
        self.assertIn("action", schema["parameters"]["properties"])
        self.assertIn("action", schema["parameters"]["required"])

    def test_name_from_class_var(self):
        class MyCustomTool(BaseTool):
            name = "my_custom"
            def _execute(self, parameters, context):
                return ToolResultResponse.ok()

        tool = MyCustomTool()
        self.assertEqual(tool.name, "my_custom")

    def test_version(self):
        tool = EchoTool()
        self.assertEqual(tool.version, "1.0.0")

    def test_trace_logged(self):
        tool = EchoTool()
        ctx = ToolContext()
        tool.execute({"text": "hi"}, ctx)
        events = [e["event"] for e in ctx.trace_log]
        self.assertIn("tool_start", events)
        self.assertIn("tool_complete", events)


# ===========================================================================
# Test: ToolRegistry
# ===========================================================================


class TestToolRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()

    def test_register_and_get(self):
        tool = EchoTool()
        self.registry.register(tool)
        self.assertIs(self.registry.get("echo_tool"), tool)

    def test_register_non_tool_raises(self):
        with self.assertRaises(ToolRegistryError):
            self.registry.register("not a tool")

    def test_duplicate_raises(self):
        self.registry.register(EchoTool())
        with self.assertRaises(ToolRegistryError):
            self.registry.register(EchoTool())

    def test_unregister(self):
        self.registry.register(EchoTool())
        self.assertTrue(self.registry.unregister("echo_tool"))
        self.assertIsNone(self.registry.get("echo_tool"))

    def test_unregister_nonexistent(self):
        self.assertFalse(self.registry.unregister("nope"))

    def test_disable_enable(self):
        self.registry.register(EchoTool())
        self.registry.disable("echo_tool")
        self.assertIsNone(self.registry.get("echo_tool"))
        self.registry.enable("echo_tool")
        self.registry.register(EchoTool())
        self.assertIsNotNone(self.registry.get("echo_tool"))

    def test_get_or_raise(self):
        self.registry.register(EchoTool())
        tool = self.registry.get_or_raise("echo_tool")
        self.assertEqual(tool.name, "echo_tool")

    def test_get_or_raise_missing(self):
        with self.assertRaises(KeyError):
            self.registry.get_or_raise("nope")

    def test_has(self):
        self.registry.register(EchoTool())
        self.assertTrue(self.registry.has("echo_tool"))
        self.assertFalse(self.registry.has("nope"))

    def test_list_all(self):
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())
        tools = self.registry.list_all()
        self.assertEqual(len(tools), 2)

    def test_list_names_sorted(self):
        self.registry.register(FailingTool())
        self.registry.register(EchoTool())
        self.assertEqual(self.registry.list_names(), ["echo_tool", "failing_tool"])

    def test_list_schemas(self):
        self.registry.register(EchoTool())
        schemas = self.registry.list_schemas()
        self.assertEqual(len(schemas), 1)
        self.assertIn("name", schemas[0])

    def test_list_descriptions(self):
        self.registry.register(EchoTool())
        desc = self.registry.list_descriptions()
        self.assertIn("echo_tool", desc)

    def test_search(self):
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())
        results = self.registry.search("echo")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "echo_tool")

    def test_filter_by_tag(self):
        self.registry.register(EchoTool())
        self.registry.tag("echo_tool", "utility", "test")
        results = self.registry.filter_by_tag("utility")
        self.assertEqual(len(results), 1)

    def test_filter_by_permission(self):
        self.registry.register(PermissionTool())
        results = self.registry.filter_by_permission("admin")
        self.assertEqual(len(results), 1)

    def test_tag_and_list_tags(self):
        self.registry.register(EchoTool())
        self.registry.tag("echo_tool", "a", "b")
        tags = self.registry.list_tags()
        self.assertIn("a", tags)
        self.assertIn("b", tags)

    def test_tag_nonexistent_tool(self):
        with self.assertRaises(KeyError):
            self.registry.tag("nope", "tag")

    def test_len_contains_iter(self):
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())
        self.assertEqual(len(self.registry), 2)
        self.assertIn("echo_tool", self.registry)
        self.assertEqual(len(list(self.registry)), 2)

    def test_discover_package(self):
        count = self.registry.discover_package("apps.ai_assistant.tools")
        self.assertGreater(count, 0)
        self.assertGreater(len(self.registry), 0)
        names = self.registry.list_names()
        self.assertIn("waste_tool", names)
        self.assertIn("bsd_tool", names)

    def test_discover_package_all_22(self):
        self.registry.discover_package("apps.ai_assistant.tools")
        names = self.registry.list_names()
        expected = [
            "administration_tool", "archive_tool", "authentification_tool",
            "bc_tool", "bl_tool", "bsd_tool", "dashboard_tool",
            "declaration_tool", "entreprise_tool", "glossaire_tool",
            "inspection_tool", "nomenclature_tool", "notification_tool",
            "partner_tool", "permissions_tool", "producteur_tool",
            "rapport_tool", "reglementation_tool", "statistiques_tool",
            "traceability_tool", "transporteur_tool", "waste_tool",
        ]
        for name in expected:
            self.assertIn(name, names)

    def test_discover_package_bad_path(self):
        count = self.registry.discover_package("nonexistent.package")
        self.assertEqual(count, 0)


# ===========================================================================
# Test: ToolFactory
# ===========================================================================


class TestToolFactory(unittest.TestCase):

    def test_create_from_class_path(self):
        tool = ToolFactory.create_from_class_path(
            "apps.ai_assistant.tools.tool_factory_echo.EchoTool"
            if False else "apps.ai_assistant.tools.waste_tool.WasteTool"
        )
        self.assertIsInstance(tool, BaseTool)
        self.assertEqual(tool.name, "waste_tool")

    def test_create_from_class_path_not_found(self):
        with self.assertRaises(ToolFactoryError):
            ToolFactory.create_from_class_path("nonexistent.module.Tool")

    def test_create_from_class_path_not_tool(self):
        with self.assertRaises(ToolFactoryError):
            ToolFactory.create_from_class_path("json.dumps")

    def test_create_from_config(self):
        config = ToolConfig(
            name="echo",
            class_path="apps.ai_assistant.tools.waste_tool.WasteTool",
            description="custom desc",
        )
        tool = ToolFactory.create_from_config(config)
        self.assertIsInstance(tool, BaseTool)
        self.assertEqual(tool.description, "custom desc")

    def test_create_batch(self):
        configs = [
            ToolConfig(name="a", class_path="apps.ai_assistant.tools.waste_tool.WasteTool"),
            ToolConfig(name="b", class_path="apps.ai_assistant.tools.bsd_tool.BSDTool"),
            ToolConfig(name="c", class_path="apps.ai_assistant.tools.nomenclature_tool.NomenclatureTool",
                        enabled=False),
        ]
        tools = ToolFactory.create_batch(configs)
        self.assertEqual(len(tools), 2)

    def test_create_and_register(self):
        registry = ToolRegistry()
        configs = [
            ToolConfig(
                name="waste",
                class_path="apps.ai_assistant.tools.waste_tool.WasteTool",
                tags=["domain"],
            ),
        ]
        count = ToolFactory.create_and_register(configs, registry)
        self.assertEqual(count, 1)
        self.assertTrue(registry.has("waste_tool"))

    def test_parse_config_list(self):
        raw = [
            {"name": "a", "class_path": "a.b.C"},
            {"name": "b", "class_path": "x.y.Z", "enabled": False},
        ]
        configs = ToolFactory.parse_config_list(raw)
        self.assertEqual(len(configs), 2)
        self.assertTrue(configs[0].enabled)
        self.assertFalse(configs[1].enabled)

    def test_parse_config_list_skips_invalid(self):
        raw = [{"name": "a"}]  # missing class_path
        configs = ToolFactory.parse_config_list(raw)
        self.assertEqual(len(configs), 0)

    def test_register_custom_creator(self):
        custom = MagicMock(return_value=EchoTool())
        ToolFactory.register_creator("custom.path.Tool", custom)
        config = ToolConfig(name="custom", class_path="custom.path.Tool")
        tool = ToolFactory.create_from_config(config)
        custom.assert_called_once()
        self.assertIsInstance(tool, BaseTool)
        ToolFactory._custom_creators.clear()


# ===========================================================================
# Test: ToolExecutor
# ===========================================================================


class TestToolExecutor(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(EchoTool())
        self.registry.register(FailingTool())
        self.registry.register(SlowTool())
        self.executor = ToolExecutor(self.registry, default_timeout=5.0)

    def test_execute_success(self):
        result = self.executor.execute("echo_tool", {"text": "hi"})
        self.assertTrue(result.success)
        self.assertEqual(result.data, "hi")

    def test_execute_tool_not_found(self):
        result = self.executor.execute("nope", {})
        self.assertFalse(result.success)
        self.assertIn("disponible", result.message.lower())

    def test_execute_with_context(self):
        ctx = ToolContext(user_id="u1")
        result = self.executor.execute("echo_tool", {"text": "x"}, ctx)
        self.assertTrue(result.success)

    def test_execute_exception(self):
        result = self.executor.execute("failing_tool", {})
        self.assertFalse(result.success)
        self.assertIn("erreur", result.message.lower())

    def test_execute_timeout(self):
        result = self.executor.execute(
            "slow_tool", {"delay": 10.0},
            timeout=0.1,
        )
        self.assertFalse(result.success)
        self.assertIn("trop de temps", result.message.lower())

    def test_middleware_before_blocks(self):
        class BlockMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                return ToolResultResponse.fail(message="blocked")
            def after(self, tool, result, parameters, context):
                return result

        self.executor.add_middleware(BlockMiddleware())
        result = self.executor.execute("echo_tool", {"text": "hi"})
        self.assertFalse(result.success)
        self.assertIn("blocked", result.message)

    def test_middleware_after_transforms(self):
        class TransformMiddleware(ToolMiddleware):
            def before(self, tool, parameters, context):
                return None
            def after(self, tool, result, parameters, context):
                result.metadata["transformed"] = True
                return result

        self.executor.add_middleware(TransformMiddleware())
        result = self.executor.execute("echo_tool", {"text": "hi"})
        self.assertTrue(result.metadata.get("transformed"))

    def test_execute_batch(self):
        calls = [
            {"tool": "echo_tool", "parameters": {"text": "a"}},
            {"tool": "echo_tool", "parameters": {"text": "b"}},
        ]
        results = self.executor.execute_batch(calls)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))

    def test_execute_batch_stops_on_failure(self):
        calls = [
            {"tool": "failing_tool", "parameters": {}},
            {"tool": "echo_tool", "parameters": {"text": "a"}},
        ]
        results = self.executor.execute_batch(calls)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)

    def test_execute_parallel(self):
        calls = [
            {"tool": "echo_tool", "parameters": {"text": "a"}},
            {"tool": "echo_tool", "parameters": {"text": "b"}},
            {"tool": "echo_tool", "parameters": {"text": "c"}},
        ]
        results = self.executor.execute_parallel(calls, timeout=5.0)
        self.assertEqual(len(results), 3)

    def test_stats(self):
        self.executor.execute("echo_tool", {"text": "a"})
        self.executor.execute("failing_tool", {})
        stats = self.executor.stats
        self.assertEqual(stats.total_calls, 2)
        self.assertEqual(stats.successful_calls, 1)
        self.assertEqual(stats.failed_calls, 1)
        self.assertGreater(stats.total_time_seconds, 0)

    def test_stats_success_rate(self):
        stats = ExecutionStats()
        self.assertEqual(stats.success_rate, 0.0)
        stats.record("x", True, 0.1)
        stats.record("x", True, 0.1)
        stats.record("x", False, 0.1)
        self.assertAlmostEqual(stats.success_rate, 2 / 3)

    def test_reset_stats(self):
        self.executor.execute("echo_tool", {"text": "a"})
        self.executor.reset_stats()
        self.assertEqual(self.executor.stats.total_calls, 0)

    def test_retry_policy(self):
        call_count = 0
        original_execute = EchoTool._execute

        def flaky_execute(self_tool, parameters, context):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return ToolResultResponse.fail(message="transient")
            return ToolResultResponse.ok(data="recovered")

        EchoTool._execute = flaky_execute
        try:
            executor = ToolExecutor(
                self.registry,
                default_retry=RetryPolicy(max_retries=3, delay_seconds=0.01),
            )
            result = executor.execute("echo_tool", {"text": "x"})
            self.assertTrue(result.success)
            self.assertEqual(call_count, 3)
        finally:
            EchoTool._execute = original_execute

    def test_clear_middleware(self):
        class Dummy(ToolMiddleware):
            def before(self, tool, parameters, context): return None
            def after(self, tool, result, parameters, context): return result

        self.executor.add_middleware(Dummy())
        self.assertEqual(len(self.executor._middleware), 1)
        self.executor.clear_middleware()
        self.assertEqual(len(self.executor._middleware), 0)


# ===========================================================================
# Test: ToolValidator (via SchemaBuilder)
# ===========================================================================


class TestToolValidator(unittest.TestCase):

    def test_valid(self):
        schema = ParameterSchema(fields=[
            FieldSchema(name="q", type="str", required=True),
        ])
        v = ToolValidator()
        errors = v.validate({"q": "hello"}, schema)
        self.assertEqual(len(errors), 0)

    def test_missing_required(self):
        schema = ParameterSchema(fields=[
            FieldSchema(name="q", type="str", required=True),
        ])
        errors = ToolValidator().validate({}, schema)
        self.assertEqual(len(errors), 1)
        self.assertIn("q", errors[0].field)

    def test_enum_violation(self):
        schema = ParameterSchema(fields=[
            FieldSchema(name="action", type="str", enum=["a", "b"]),
        ])
        errors = ToolValidator().validate({"action": "c"}, schema)
        self.assertEqual(len(errors), 1)

    def test_schema_builder(self):
        schema = (
            SchemaBuilder()
            .field("action", "str", required=True, enum=["get", "list"])
            .field("limit", "int", default=20)
            .build()
        )
        self.assertEqual(len(schema.fields), 2)
        self.assertTrue(schema.fields[0].required)


# ===========================================================================
# Test: Container Tool Registration
# ===========================================================================


class TestContainerToolRegistry(unittest.TestCase):

    def test_tool_registry_type(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        registry = c.tool_registry
        self.assertIsInstance(registry, ToolRegistry)

    def test_tool_registry_singleton(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        r1 = c.tool_registry
        r2 = c.tool_registry
        self.assertIs(r1, r2)

    def test_tool_registry_has_22_tools(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        registry = c.tool_registry
        self.assertGreaterEqual(len(registry), 22)

    def test_tool_registry_has_expected_tools(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        names = c.tool_registry.list_names()
        for expected in ["waste_tool", "bsd_tool", "nomenclature_tool",
                         "declaration_tool", "dashboard_tool",
                         "administration_tool", "permissions_tool",
                         "rag_knowledge_tool"]:
            self.assertIn(expected, names)

    def test_tool_registry_iterable(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        tools = list(c.tool_registry)
        self.assertGreaterEqual(len(tools), 22)

    def test_tool_executor_type(self):
        from apps.ai_assistant.enterprise.container import Container
        c = Container()
        executor = c.tool_executor
        self.assertIsInstance(executor, ToolExecutor)


if __name__ == "__main__":
    unittest.main()
