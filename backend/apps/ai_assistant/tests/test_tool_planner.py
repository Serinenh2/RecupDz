"""
Tests for ToolPlanner — execution plan generation from DecisionProposal.

Covers:
    - DecisionProposal data contract
    - ExecutionPlan data contract
    - ToolStep data contract
    - CostEstimate data contract
    - ConflictInfo data contract
    - Single tool planning
    - Batch planning (sequential / parallel)
    - Dependency detection
    - Conflict detection
    - Cost estimation
    - Confirmation rules
    - Fallback plan generation
    - Edge cases
    - Framework independence
"""

import unittest

from apps.ai_assistant.enterprise.tool_planner import (
    ConflictInfo,
    CostEstimate,
    DecisionProposal,
    ExecutionMode,
    ExecutionPlan,
    ToolPlanner,
    ToolStep,
    _TOOL_META,
    _WRITE_ACTIONS,
)


# ════════════════════════════════════════════════════════════════════════
# Data Contract: DecisionProposal
# ════════════════════════════════════════════════════════════════════════


class TestDecisionProposal(unittest.TestCase):
    def test_has_tool_true(self):
        p = DecisionProposal(tool="waste_tool", action="search")
        self.assertTrue(p.has_tool)

    def test_has_tool_none(self):
        p = DecisionProposal(tool="none")
        self.assertFalse(p.has_tool)

    def test_has_tool_greeting(self):
        p = DecisionProposal(tool="greeting")
        self.assertFalse(p.has_tool)

    def test_has_tool_empty(self):
        p = DecisionProposal(tool="")
        self.assertFalse(p.has_tool)

    def test_is_write_create(self):
        p = DecisionProposal(tool="bsd_tool", action="create")
        self.assertTrue(p.is_write)

    def test_is_write_update(self):
        p = DecisionProposal(tool="declaration_tool", action="update")
        self.assertTrue(p.is_write)

    def test_is_write_delete(self):
        p = DecisionProposal(tool="archive_tool", action="delete")
        self.assertTrue(p.is_write)

    def test_is_write_index(self):
        p = DecisionProposal(tool="rag_knowledge_tool", action="index")
        self.assertTrue(p.is_write)

    def test_is_not_write_search(self):
        p = DecisionProposal(tool="waste_tool", action="search")
        self.assertFalse(p.is_write)

    def test_is_not_write_list(self):
        p = DecisionProposal(tool="bsd_tool", action="list")
        self.assertFalse(p.is_write)

    def test_is_valid(self):
        p = DecisionProposal(
            tool="waste_tool", action="search", missing=[],
        )
        self.assertTrue(p.is_valid)

    def test_is_valid_no_tool(self):
        p = DecisionProposal(tool="none", missing=[])
        self.assertFalse(p.is_valid)

    def test_is_valid_with_missing(self):
        p = DecisionProposal(
            tool="waste_tool", action="search",
            missing=[{"name": "query"}],
        )
        self.assertFalse(p.is_valid)

    def test_to_dict_basic(self):
        p = DecisionProposal(
            message="test", tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=0.9,
        )
        d = p.to_dict()
        self.assertEqual(d["tool"], "waste_tool")
        self.assertEqual(d["action"], "search")
        self.assertAlmostEqual(d["confidence"], 0.9, places=3)
        self.assertNotIn("reasoning", d)
        self.assertNotIn("missing", d)

    def test_to_dict_with_optionals(self):
        p = DecisionProposal(
            tool="waste_tool", action="search",
            confidence=0.9, reasoning="because", missing=[{"name": "q"}],
        )
        d = p.to_dict()
        self.assertEqual(d["reasoning"], "because")
        self.assertEqual(len(d["missing"]), 1)


# ════════════════════════════════════════════════════════════════════════
# Data Contract: ToolStep
# ════════════════════════════════════════════════════════════════════════


class TestToolStep(unittest.TestCase):
    def test_to_dict_basic(self):
        s = ToolStep(
            step_id="step_1", tool="waste_tool", action="search",
            parameters={"query": "test"},
        )
        d = s.to_dict()
        self.assertEqual(d["step_id"], "step_1")
        self.assertEqual(d["tool"], "waste_tool")
        self.assertNotIn("depends_on", d)
        self.assertNotIn("is_write", d)

    def test_to_dict_with_optionals(self):
        s = ToolStep(
            step_id="step_1", tool="bsd_tool", action="create",
            depends_on=["step_0"], estimated_ms=180.0,
            is_write=True, timeout_ms=60000.0, retry_count=2,
        )
        d = s.to_dict()
        self.assertEqual(d["depends_on"], ["step_0"])
        self.assertTrue(d["is_write"])
        self.assertEqual(d["retry_count"], 2)


# ════════════════════════════════════════════════════════════════════════
# Data Contract: CostEstimate
# ════════════════════════════════════════════════════════════════════════


class TestCostEstimate(unittest.TestCase):
    def test_to_dict(self):
        c = CostEstimate(
            total_ms=500.0, tool_count=2, read_count=1,
            write_count=1, parallel_savings_ms=200.0,
        )
        d = c.to_dict()
        self.assertAlmostEqual(d["total_ms"], 500.0, places=1)
        self.assertEqual(d["tool_count"], 2)
        self.assertEqual(d["read_count"], 1)
        self.assertEqual(d["write_count"], 1)
        self.assertAlmostEqual(d["parallel_savings_ms"], 200.0, places=1)


# ════════════════════════════════════════════════════════════════════════
# Data Contract: ConflictInfo
# ════════════════════════════════════════════════════════════════════════


class TestConflictInfo(unittest.TestCase):
    def test_to_dict(self):
        c = ConflictInfo(
            tool_a="bsd_tool", action_a="create",
            tool_b="bsd_tool", action_b="update",
            reason="conflict",
        )
        d = c.to_dict()
        self.assertEqual(d["tool_a"], "bsd_tool")
        self.assertEqual(d["reason"], "conflict")

    def test_to_dict_no_reason(self):
        c = ConflictInfo(
            tool_a="a", action_a="x", tool_b="b", action_b="y",
        )
        d = c.to_dict()
        self.assertNotIn("reason", d)


# ════════════════════════════════════════════════════════════════════════
# Data Contract: ExecutionPlan
# ════════════════════════════════════════════════════════════════════════


class TestExecutionPlan(unittest.TestCase):
    def test_empty_plan(self):
        p = ExecutionPlan()
        self.assertTrue(p.is_empty)
        self.assertEqual(p.tool_count, 0)
        self.assertIsNone(p.first_tool)
        self.assertIsNone(p.last_tool)
        self.assertFalse(p.has_fallback)
        self.assertFalse(p.has_conflicts)

    def test_non_empty_plan(self):
        step = ToolStep(step_id="s1", tool="waste_tool", action="search")
        p = ExecutionPlan(
            ordered_tools=[step], tool_count=1, is_empty=False,
        )
        self.assertFalse(p.is_empty)
        self.assertEqual(p.tool_count, 1)
        self.assertIs(p.first_tool, step)
        self.assertIs(p.last_tool, step)

    def test_multiple_steps_first_last(self):
        s1 = ToolStep(step_id="s1", tool="a", action="x")
        s2 = ToolStep(step_id="s2", tool="b", action="y")
        p = ExecutionPlan(ordered_tools=[s1, s2], tool_count=2, is_empty=False)
        self.assertIs(p.first_tool, s1)
        self.assertIs(p.last_tool, s2)

    def test_has_fallback(self):
        fb = ExecutionPlan(tool_count=1, is_empty=False)
        p = ExecutionPlan(fallback_plan=fb)
        self.assertTrue(p.has_fallback)

    def test_has_conflicts(self):
        c = ConflictInfo(tool_a="a", action_a="x", tool_b="b", action_b="y")
        p = ExecutionPlan(conflicts=[c])
        self.assertTrue(p.has_conflicts)

    def test_to_dict_empty(self):
        d = ExecutionPlan().to_dict()
        self.assertTrue(d["is_empty"])
        self.assertEqual(d["tool_count"], 0)
        self.assertNotIn("fallback_plan", d)
        self.assertNotIn("conflicts", d)
        self.assertNotIn("confirmation_reason", d)

    def test_to_dict_full(self):
        step = ToolStep(step_id="s1", tool="waste_tool", action="search")
        fb = ExecutionPlan(tool_count=1, is_empty=False)
        c = ConflictInfo(tool_a="a", action_a="x", tool_b="b", action_b="y")
        p = ExecutionPlan(
            ordered_tools=[step],
            execution_mode=ExecutionMode.PARALLEL,
            dependencies={"s1": []},
            estimated_cost=CostEstimate(total_ms=150.0, tool_count=1),
            requires_confirmation=True,
            confirmation_reason="write op",
            fallback_plan=fb,
            conflicts=[c],
            tool_count=1,
            is_empty=False,
        )
        d = p.to_dict()
        self.assertEqual(d["execution_mode"], "parallel")
        self.assertIn("s1", d["dependencies"])
        self.assertTrue(d["requires_confirmation"])
        self.assertEqual(d["confirmation_reason"], "write op")
        self.assertIn("fallback_plan", d)
        self.assertEqual(len(d["conflicts"]), 1)


# ════════════════════════════════════════════════════════════════════════
# Single Tool Planning
# ════════════════════════════════════════════════════════════════════════


class TestSingleToolPlanning(unittest.TestCase):
    def setUp(self):
        self.planner = ToolPlanner()

    def test_read_tool(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"action": "search", "query": "test"},
            confidence=0.95,
        )
        plan = self.planner.plan(prop)
        self.assertFalse(plan.is_empty)
        self.assertEqual(plan.tool_count, 1)
        self.assertEqual(plan.execution_mode, ExecutionMode.SEQUENTIAL)
        self.assertEqual(plan.first_tool.tool, "waste_tool")
        self.assertEqual(plan.first_tool.action, "search")
        self.assertFalse(plan.first_tool.is_write)
        self.assertFalse(plan.requires_confirmation)

    def test_write_tool(self):
        prop = DecisionProposal(
            tool="bsd_tool", action="create",
            parameters={"data": {}},
            confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.first_tool.is_write)
        self.assertTrue(plan.requires_confirmation)
        self.assertIn("écriture", plan.confirmation_reason)

    def test_no_tool(self):
        prop = DecisionProposal(tool="none")
        plan = self.planner.plan(prop)
        self.assertTrue(plan.is_empty)
        self.assertEqual(plan.tool_count, 0)

    def test_greeting(self):
        prop = DecisionProposal(tool="greeting")
        plan = self.planner.plan(prop)
        self.assertTrue(plan.is_empty)

    def test_missing_params(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            missing=[{"name": "query"}],
            confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.requires_confirmation)
        self.assertIn("manquants", plan.confirmation_reason)
        self.assertEqual(plan.tool_count, 1)

    def test_low_confidence(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"action": "search", "query": "test"},
            confidence=0.3,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.requires_confirmation)
        self.assertIn("Confiance faible", plan.confirmation_reason)

    def test_has_fallback_for_read(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "test"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.has_fallback)
        self.assertEqual(plan.fallback_plan.first_tool.tool, "rag_knowledge_tool")

    def test_no_fallback_for_write(self):
        prop = DecisionProposal(
            tool="bsd_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertFalse(plan.has_fallback)

    def test_step_timeout_read(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "test"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertEqual(plan.first_tool.timeout_ms, 30000.0)

    def test_step_timeout_write(self):
        prop = DecisionProposal(
            tool="bsd_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertEqual(plan.first_tool.timeout_ms, 60000.0)

    def test_step_retries_read(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertEqual(plan.first_tool.retry_count, 1)

    def test_step_retries_write(self):
        prop = DecisionProposal(
            tool="bsd_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertEqual(plan.first_tool.retry_count, 0)


# ════════════════════════════════════════════════════════════════════════
# Conflict Detection
# ════════════════════════════════════════════════════════════════════════


class TestConflictDetection(unittest.TestCase):
    def setUp(self):
        self.planner = ToolPlanner()

    def test_no_conflict_search(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertFalse(plan.has_conflicts)

    def test_declaration_create_conflict(self):
        prop = DecisionProposal(
            tool="declaration_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.has_conflicts)
        self.assertEqual(len(plan.conflicts), 1)
        self.assertEqual(plan.conflicts[0].tool_b, "declaration_tool")

    def test_bsd_create_conflict(self):
        prop = DecisionProposal(
            tool="bsd_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.has_conflicts)

    def test_notification_list_conflict(self):
        prop = DecisionProposal(
            tool="notification_tool", action="list",
            parameters={}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.has_conflicts)

    def test_conflict_triggers_confirmation(self):
        prop = DecisionProposal(
            tool="bsd_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.requires_confirmation)
        self.assertIn("conflit", plan.confirmation_reason)


# ════════════════════════════════════════════════════════════════════════
# Cost Estimation
# ════════════════════════════════════════════════════════════════════════


class TestCostEstimation(unittest.TestCase):
    def setUp(self):
        self.planner = ToolPlanner()

    def test_read_cost(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertEqual(plan.estimated_cost.total_ms, 150.0)
        self.assertEqual(plan.estimated_cost.read_count, 1)
        self.assertEqual(plan.estimated_cost.write_count, 0)

    def test_write_cost(self):
        prop = DecisionProposal(
            tool="bsd_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertEqual(plan.estimated_cost.write_count, 1)
        self.assertEqual(plan.estimated_cost.read_count, 0)

    def test_all_tools_have_costs(self):
        for tool_name in _TOOL_META:
            prop = DecisionProposal(
                tool=tool_name, action="search",
                parameters={"query": "x"}, confidence=0.9,
            )
            plan = self.planner.plan(prop)
            self.assertGreater(plan.estimated_cost.total_ms, 0, f"{tool_name}")

    def test_unknown_tool_default_cost(self):
        prop = DecisionProposal(
            tool="unknown_tool_xyz", action="do",
            parameters={}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertEqual(plan.estimated_cost.total_ms, 200.0)


# ════════════════════════════════════════════════════════════════════════
# Batch Planning
# ════════════════════════════════════════════════════════════════════════


class TestBatchPlanning(unittest.TestCase):
    def setUp(self):
        self.planner = ToolPlanner()

    def test_empty_batch(self):
        plan = self.planner.plan_batch([])
        self.assertTrue(plan.is_empty)

    def test_single_item_batch(self):
        props = [
            DecisionProposal(
                tool="waste_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        self.assertEqual(plan.tool_count, 1)

    def test_independent_reads_parallel(self):
        props = [
            DecisionProposal(
                tool="waste_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
            DecisionProposal(
                tool="glossaire_tool", action="search",
                parameters={"query": "y"}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        self.assertEqual(plan.execution_mode, ExecutionMode.PARALLEL)
        self.assertEqual(plan.tool_count, 2)
        self.assertGreater(plan.estimated_cost.parallel_savings_ms, 0)

    def test_write_in_batch_sequential(self):
        props = [
            DecisionProposal(
                tool="waste_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
            DecisionProposal(
                tool="bsd_tool", action="create",
                parameters={"data": {}}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        self.assertTrue(plan.requires_confirmation)
        self.assertIn("écriture", plan.confirmation_reason)

    def test_cross_step_conflict(self):
        props = [
            DecisionProposal(
                tool="bsd_tool", action="create",
                parameters={"data": {}}, confidence=0.9,
            ),
            DecisionProposal(
                tool="bsd_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        self.assertTrue(plan.has_conflicts)

    def test_batch_has_fallback(self):
        props = [
            DecisionProposal(
                tool="waste_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        self.assertTrue(plan.has_fallback)

    def test_batch_no_fallback_all_writes(self):
        props = [
            DecisionProposal(
                tool="bsd_tool", action="create",
                parameters={"data": {}}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        self.assertFalse(plan.has_fallback)


# ════════════════════════════════════════════════════════════════════════
# Dependency Detection (Batch)
# ════════════════════════════════════════════════════════════════════════


class TestDependencyDetection(unittest.TestCase):
    def setUp(self):
        self.planner = ToolPlanner()

    def test_no_deps_independent(self):
        props = [
            DecisionProposal(
                tool="waste_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
            DecisionProposal(
                tool="glossaire_tool", action="search",
                parameters={"query": "y"}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        # No deps → parallel
        self.assertEqual(plan.execution_mode, ExecutionMode.PARALLEL)
        for dep_list in plan.dependencies.values():
            self.assertEqual(len(dep_list), 0)

    def test_nomenclature_feeds_into_analytics(self):
        props = [
            DecisionProposal(
                tool="nomenclature_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
            DecisionProposal(
                tool="rapport_tool", action="waste_report",
                parameters={"query": "y"}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        # rapport (analytics) depends on nomenclature
        has_deps = any(
            len(d) > 0 for d in plan.dependencies.values()
        )
        self.assertTrue(has_deps)
        self.assertEqual(plan.execution_mode, ExecutionMode.SEQUENTIAL)


# ════════════════════════════════════════════════════════════════════════
# Fallback Planning
# ════════════════════════════════════════════════════════════════════════


class TestFallbackPlanning(unittest.TestCase):
    def setUp(self):
        self.planner = ToolPlanner()

    def test_read_has_fallback(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.has_fallback)
        fb = plan.fallback_plan
        self.assertEqual(fb.first_tool.tool, "rag_knowledge_tool")
        self.assertEqual(fb.first_tool.action, "search")
        self.assertFalse(fb.requires_confirmation)

    def test_write_no_fallback(self):
        prop = DecisionProposal(
            tool="bsd_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertFalse(plan.has_fallback)

    def test_no_tool_no_fallback(self):
        prop = DecisionProposal(tool="none")
        plan = self.planner.plan(prop)
        self.assertFalse(plan.has_fallback)

    def test_fallback_tool_meta(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        fb_step = plan.fallback_plan.first_tool
        self.assertIn(fb_step.tool, _TOOL_META)


# ════════════════════════════════════════════════════════════════════════
# Tool Metadata
# ════════════════════════════════════════════════════════════════════════


class TestToolMetadata(unittest.TestCase):
    def test_all_tools_have_metadata(self):
        tools = [
            "waste_tool", "declaration_tool", "producteur_tool",
            "transporteur_tool", "partner_tool", "entreprise_tool",
            "statistiques_tool", "rapport_tool", "reglementation_tool",
            "authentification_tool", "bsd_tool", "bc_tool", "bl_tool",
            "inspection_tool", "archive_tool", "traceability_tool",
            "glossaire_tool", "nomenclature_tool", "notification_tool",
            "dashboard_tool", "administration_tool", "permissions_tool",
            "rag_knowledge_tool",
        ]
        for tool in tools:
            self.assertIn(tool, _TOOL_META, f"{tool} missing from _TOOL_META")
            ms, is_write, cat = _TOOL_META[tool]
            self.assertGreater(ms, 0, f"{tool} has zero cost")
            self.assertIsInstance(is_write, bool)
            self.assertIsInstance(cat, str)

    def test_write_actions_defined(self):
        self.assertIn("create", _WRITE_ACTIONS)
        self.assertIn("update", _WRITE_ACTIONS)
        self.assertIn("delete", _WRITE_ACTIONS)
        self.assertIn("archive", _WRITE_ACTIONS)
        self.assertIn("index", _WRITE_ACTIONS)
        self.assertNotIn("search", _WRITE_ACTIONS)
        self.assertNotIn("list", _WRITE_ACTIONS)
        self.assertNotIn("get", _WRITE_ACTIONS)


# ════════════════════════════════════════════════════════════════════════
# Edge Cases
# ════════════════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.planner = ToolPlanner()

    def test_very_long_message(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x" * 10000}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertFalse(plan.is_empty)

    def test_special_characters_in_params(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "Éàèêë!@#$%^&*()"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        self.assertEqual(
            plan.first_tool.parameters["query"], "Éàèêë!@#$%^&*()",
        )

    def test_zero_confidence(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=0.0,
        )
        plan = self.planner.plan(prop)
        self.assertTrue(plan.requires_confirmation)

    def test_max_confidence(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=1.0,
        )
        plan = self.planner.plan(prop)
        self.assertFalse(plan.requires_confirmation)

    def test_parameters_are_copied(self):
        params = {"query": "test"}
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters=params, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        plan.first_tool.parameters["query"] = "modified"
        self.assertEqual(prop.parameters["query"], "test")

    def test_batch_all_invalid(self):
        props = [
            DecisionProposal(tool="waste_tool", missing=[{"name": "q"}]),
            DecisionProposal(tool="bsd_tool", missing=[{"name": "d"}]),
        ]
        plan = self.planner.plan_batch(props)
        self.assertTrue(plan.is_empty)

    def test_batch_mixed_valid_invalid(self):
        props = [
            DecisionProposal(
                tool="waste_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
            DecisionProposal(tool="bsd_tool", missing=[{"name": "d"}]),
        ]
        plan = self.planner.plan_batch(props)
        self.assertEqual(plan.tool_count, 1)
        self.assertFalse(plan.is_empty)


# ════════════════════════════════════════════════════════════════════════
# Framework Independence
# ════════════════════════════════════════════════════════════════════════


class TestFrameworkIndependence(unittest.TestCase):
    def test_no_django_imports(self):
        import apps.ai_assistant.enterprise.tool_planner as mod
        source = open(mod.__file__).read()
        self.assertNotIn("import django", source)
        self.assertNotIn("from django", source)

    def test_no_repository_imports(self):
        import apps.ai_assistant.enterprise.tool_planner as mod
        source = open(mod.__file__).read()
        self.assertNotIn("from apps.ai_assistant.repositories", source)

    def test_no_model_imports(self):
        import apps.ai_assistant.enterprise.tool_planner as mod
        source = open(mod.__file__).read()
        self.assertNotIn("from apps.accounts.models", source)
        self.assertNotIn("from apps.nomenclature.models", source)

    def test_no_execute_calls(self):
        import apps.ai_assistant.enterprise.tool_planner as mod
        source = open(mod.__file__).read()
        self.assertNotIn("execute_tool", source)
        self.assertNotIn("tool_executor", source)

    def test_all_dataclasses_frozen(self):
        from dataclasses import fields
        for cls in [DecisionProposal, ToolStep, CostEstimate,
                    ConflictInfo, ExecutionPlan]:
            # frozen is set at class creation, not per-field
            self.assertTrue(
                getattr(cls, "__dataclass_params__").frozen,
                f"{cls.__name__} is not frozen",
            )


# ════════════════════════════════════════════════════════════════════════
# Integration: Full Pipeline
# ════════════════════════════════════════════════════════════════════════


class TestFullPipeline(unittest.TestCase):
    def setUp(self):
        self.planner = ToolPlanner()

    def test_read_plan_serializable(self):
        prop = DecisionProposal(
            message="test", tool="waste_tool", action="search",
            parameters={"query": "déchets"}, confidence=0.95,
        )
        plan = self.planner.plan(prop)
        d = plan.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["tool_count"], 1)
        self.assertFalse(d["is_empty"])

    def test_write_plan_serializable(self):
        prop = DecisionProposal(
            message="create BSD", tool="bsd_tool", action="create",
            parameters={"data": {}}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        d = plan.to_dict()
        self.assertTrue(d["requires_confirmation"])
        self.assertNotIn("fallback_plan", d)  # write ops have no fallback
        self.assertTrue(len(d["conflicts"]) > 0)

    def test_batch_plan_serializable(self):
        props = [
            DecisionProposal(
                tool="waste_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
            DecisionProposal(
                tool="glossaire_tool", action="search",
                parameters={"query": "y"}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        d = plan.to_dict()
        self.assertEqual(d["tool_count"], 2)
        self.assertEqual(d["execution_mode"], "parallel")

    def test_plan_step_ids_unique(self):
        props = [
            DecisionProposal(
                tool="waste_tool", action="search",
                parameters={"query": "x"}, confidence=0.9,
            ),
            DecisionProposal(
                tool="glossaire_tool", action="search",
                parameters={"query": "y"}, confidence=0.9,
            ),
        ]
        plan = self.planner.plan_batch(props)
        ids = [s.step_id for s in plan.ordered_tools]
        self.assertEqual(len(ids), len(set(ids)))

    def test_fallback_to_dict(self):
        prop = DecisionProposal(
            tool="waste_tool", action="search",
            parameters={"query": "x"}, confidence=0.9,
        )
        plan = self.planner.plan(prop)
        d = plan.to_dict()
        self.assertIn("fallback_plan", d)
        self.assertEqual(d["fallback_plan"]["tool_count"], 1)


if __name__ == "__main__":
    unittest.main()
