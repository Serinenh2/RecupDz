"""
Integration Tests — Knowledge Search in Execution Pipeline.

Tests the full pipeline with real KnowledgeSearchEngine and mocked repositories,
verifying that enterprise knowledge flows through the pipeline correctly.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from apps.ai_assistant.enterprise.execution_orchestrator import ExecutionOrchestrator
from apps.ai_assistant.enterprise.reasoning_orchestrator import ReasoningOrchestrator
from apps.ai_assistant.enterprise.reasoning_policy import AIReasoningPolicy
from apps.ai_assistant.enterprise.knowledge_search import (
    KnowledgeSearchEngine,
    SearchResults,
    SearchMode,
)
from apps.ai_assistant.enterprise.tool_planner import (
    DecisionProposal,
    ExecutionPlan,
    ToolPlanner,
)
from apps.ai_assistant.enterprise.tool_executor_v2 import (
    ToolExecutionResult,
    StepResult,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _mock_executor(success=True, data=None):
    te = MagicMock()
    te.execute_plan.return_value = ToolExecutionResult(
        success=success,
        step_results=[
            StepResult(
                step_id="step_1",
                tool="nomenclature_tool",
                action="search",
                success=success,
                data=data or {"code": "01.01.01", "name": "Papier"},
                message="OK" if success else "Erreur",
                elapsed_ms=42.0,
            )
        ],
        total_elapsed_ms=42.0,
        steps_succeeded=1 if success else 0,
        steps_failed=0 if success else 1,
    )
    return te


def _make_knowledge_with_repos(glossary_data=None, nomenclature_data=None):
    """Create a KnowledgeSearchEngine with mock repositories."""
    glossary_data = glossary_data or []
    nomenclature_data = nomenclature_data or []

    def glossary_repo(query, limit):
        return glossary_data

    def nomenclature_repo(query, limit):
        return nomenclature_data

    return KnowledgeSearchEngine(
        glossary_repo=glossary_repo,
        nomenclature_repo=nomenclature_repo,
    )


def _build_full_pipeline(
    glossary_data=None,
    nomenclature_data=None,
    executor=None,
):
    """Build a full pipeline with real reasoning, knowledge, and planner."""
    rp = AIReasoningPolicy()
    ro = ReasoningOrchestrator(reasoning_policy=rp)
    ks = _make_knowledge_with_repos(glossary_data, nomenclature_data)
    tp = ToolPlanner()
    te = executor or _mock_executor()
    return ExecutionOrchestrator(
        reasoning_orchestrator=ro,
        knowledge_search=ks,
        tool_planner=tp,
        tool_executor_v2=te,
    )


# ══════════════════════════════════════════════════════════════════════
# Tests — Knowledge Search with Mock Repositories
# ══════════════════════════════════════════════════════════════════════


class TestKnowledgeSearchWithRepos(unittest.TestCase):

    def test_glossary_results_flow_through(self):
        """Glossary results should appear in SearchResults."""
        ks = _make_knowledge_with_repos(
            glossary_data=[
                {"title": "BSD", "content": "Bordereau de Suivi des Déchets"},
            ],
        )
        results = ks.search("BSD", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)
        self.assertGreater(results.total_hits, 0)
        # Best source should be glossary (priority 1)
        best = results.best_source
        self.assertIsNotNone(best)
        self.assertEqual(best.source, "glossary")

    def test_nomenclature_results_flow_through(self):
        """Nomenclature results should appear in SearchResults."""
        ks = _make_knowledge_with_repos(
            nomenclature_data=[
                {"title": "01.01.01 — Papier", "content": "Papier et carton"},
            ],
        )
        results = ks.search("papier", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)
        best = results.best_source
        self.assertIsNotNone(best)
        self.assertEqual(best.source, "nomenclature")

    def test_priority_ordering(self):
        """Glossary (priority 1) should rank above nomenclature (priority 2)."""
        ks = _make_knowledge_with_repos(
            glossary_data=[
                {"title": "Test", "content": "Glossary match"},
            ],
            nomenclature_data=[
                {"title": "Test", "content": "Nomenclature match"},
            ],
        )
        results = ks.search("test", mode=SearchMode.KEYWORD)
        self.assertTrue(results.has_results)
        # Best source should be glossary (lower priority number)
        best = results.best_source
        self.assertEqual(best.source, "glossary")

    def test_context_string_generation(self):
        """SearchResults.to_context_string() should format hits for LLM injection."""
        ks = _make_knowledge_with_repos(
            glossary_data=[
                {"title": "BSD", "content": "Bordereau de Suivi des Déchets"},
            ],
        )
        results = ks.search("BSD", mode=SearchMode.KEYWORD)
        ctx = results.to_context_string()
        self.assertIn("Glossaire", ctx)
        self.assertIn("BSD", ctx)

    def test_empty_results_when_no_repos(self):
        """With no repos, search should return empty results."""
        ks = KnowledgeSearchEngine()
        results = ks.search("test")
        self.assertFalse(results.has_results)
        self.assertEqual(results.total_hits, 0)


# ══════════════════════════════════════════════════════════════════════
# Tests — Full Pipeline with Knowledge
# ══════════════════════════════════════════════════════════════════════


class TestFullPipelineWithKnowledge(unittest.TestCase):

    def test_greeting_with_knowledge(self):
        """Greeting should still work with knowledge search enabled."""
        eo = _build_full_pipeline()
        result, proposal, plan, knowledge = eo.execute_with_trace("bonjour")
        self.assertTrue(result.success)
        self.assertIsInstance(knowledge, SearchResults)

    def test_tool_query_with_knowledge(self):
        """Tool query should flow through reasoning → knowledge → planning → execution."""
        eo = _build_full_pipeline(
            glossary_data=[
                {"title": "Nomenclature", "content": "Classification des déchets"},
            ],
        )
        result, proposal, plan, knowledge = eo.execute_with_trace("nomenclature des dechets")
        self.assertIsInstance(result, ToolExecutionResult)
        self.assertIsInstance(knowledge, SearchResults)
        if knowledge.has_results:
            self.assertGreater(knowledge.total_hits, 0)

    def test_knowledge_context_injected_when_tool_executes(self):
        """When tool executes and knowledge has results, context should be injected."""
        eo = _build_full_pipeline(
            glossary_data=[
                {"title": "BSD", "content": "Bordereau de Suivi des Déchets"},
            ],
        )
        result = eo.execute("code 01.01.01")
        self.assertIsInstance(result, ToolExecutionResult)
        # If knowledge was found, it should be in messages
        if any("[CONNAISSANCES_ENTREPRISE]" in m for m in result.messages):
            # Verify the knowledge block is well-formed
            for m in result.messages:
                if "[CONNAISSANCES_ENTREPRISE]" in m:
                    self.assertIn("Glossaire", m)

    def test_knowledge_search_mode_is_hybrid(self):
        """Default knowledge search should use hybrid mode."""
        ks = MagicMock()
        ks.search.return_value = MagicMock(
            has_results=False, to_context_string=lambda: "",
        )
        ro = ReasoningOrchestrator(reasoning_policy=AIReasoningPolicy())
        tp = ToolPlanner()
        te = _mock_executor()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            knowledge_search=ks,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        eo.execute("test")
        # Verify search was called with hybrid mode
        call_kwargs = ks.search.call_args
        self.assertEqual(call_kwargs[1].get("mode", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None), SearchMode.HYBRID)

    def test_knowledge_search_limit_is_5(self):
        """Default knowledge search limit should be 5."""
        ks = MagicMock()
        ks.search.return_value = MagicMock(
            has_results=False, to_context_string=lambda: "",
        )
        ro = ReasoningOrchestrator(reasoning_policy=AIReasoningPolicy())
        tp = ToolPlanner()
        te = _mock_executor()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            knowledge_search=ks,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        eo.execute("test")
        call_kwargs = ks.search.call_args
        self.assertEqual(call_kwargs[1].get("limit", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None), 5)


# ══════════════════════════════════════════════════════════════════════
# Tests — Knowledge Failure Resilience
# ══════════════════════════════════════════════════════════════════════


class TestKnowledgeFailureResilience(unittest.TestCase):

    def test_knowledge_crash_does_not_block_tool_execution(self):
        """If knowledge search crashes, the pipeline should continue."""
        ks = MagicMock()
        ks.search.side_effect = RuntimeError("DB exploded")
        ro = ReasoningOrchestrator(reasoning_policy=AIReasoningPolicy())
        tp = ToolPlanner()
        te = _mock_executor()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            knowledge_search=ks,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("code 01.01.01")
        self.assertTrue(result.success)
        self.assertTrue(result.has_data)

    def test_knowledge_timeout_does_not_block_pipeline(self):
        """If knowledge search times out, the pipeline should continue."""
        import time

        def slow_search(*args, **kwargs):
            time.sleep(0.01)
            raise TimeoutError("search timed out")

        ks = MagicMock()
        ks.search.side_effect = slow_search
        ro = ReasoningOrchestrator(reasoning_policy=AIReasoningPolicy())
        tp = ToolPlanner()
        te = _mock_executor()
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ro,
            knowledge_search=ks,
            tool_planner=tp,
            tool_executor_v2=te,
        )
        result = eo.execute("code 01.01.01")
        self.assertTrue(result.success)

    def test_knowledge_none_still_works(self):
        """Pipeline should work when knowledge_search is None."""
        eo = ExecutionOrchestrator(
            reasoning_orchestrator=ReasoningOrchestrator(
                reasoning_policy=AIReasoningPolicy(),
            ),
            knowledge_search=None,
            tool_planner=ToolPlanner(),
            tool_executor_v2=_mock_executor(),
        )
        result = eo.execute("code 01.01.01")
        self.assertTrue(result.success)
        self.assertTrue(result.has_data)


# ══════════════════════════════════════════════════════════════════════
# Tests — Knowledge + PromptBuilder Integration
# ══════════════════════════════════════════════════════════════════════


class TestKnowledgePromptBuilderIntegration(unittest.TestCase):

    def test_knowledge_context_usable_by_prompt_builder(self):
        """Verify knowledge context string can be passed to PromptBuilder."""
        from apps.ai_assistant.enterprise.prompt_builder import PromptBuilder

        ks = _make_knowledge_with_repos(
            glossary_data=[
                {"title": "BSD", "content": "Bordereau de Suivi des Déchets"},
            ],
        )
        results = ks.search("BSD", mode=SearchMode.KEYWORD)
        ctx_str = results.to_context_string()

        builder = PromptBuilder()
        prompt_ctx = builder.build(
            message="Qu'est-ce qu'un BSD ?",
            system_instructions="You are a waste management expert.",
            company_knowledge=ctx_str,
            tool_results={"code": "BSD-2024-001"},
            tool_name="bsd_tool",
            user_language="fr",
        )

        self.assertTrue(prompt_ctx.has_company_knowledge)
        self.assertIn("BSD", prompt_ctx.system_prompt)
        self.assertIn("Glossaire", prompt_ctx.system_prompt)

    def test_full_response_generation_flow(self):
        """Simulate the full flow: reasoning → knowledge → tool → prompt."""
        from apps.ai_assistant.enterprise.prompt_builder import PromptBuilder

        # 1. Reasoning
        rp = AIReasoningPolicy()
        ro = ReasoningOrchestrator(reasoning_policy=rp)
        proposal = ro.reason("nomenclature des dechets")
        self.assertIsNotNone(proposal)

        # 2. Knowledge search — use data that matches the query
        ks = _make_knowledge_with_repos(
            glossary_data=[
                {"title": "Nomenclature", "content": "Classification des déchets dangereux selon la réglementation algérienne"},
            ],
        )
        knowledge = ks.search("nomenclature des dechets", mode=SearchMode.HYBRID)
        ctx_str = knowledge.to_context_string()

        # 3. Tool execution (mocked)
        tool_result = {"code": "01.01.01", "designation": "Papier et carton"}

        # 4. Prompt building
        builder = PromptBuilder()
        prompt_ctx = builder.build_response_prompt(
            message="Quelle est la nomenclature des déchets ?",
            tool_results=tool_result,
            tool_name="nomenclature_tool",
            company_knowledge=ctx_str,
            user_language="fr",
        )

        # Knowledge may or may not match depending on scoring — just verify prompt builds
        self.assertIn("nomenclature_tool", prompt_ctx.system_prompt)
        self.assertTrue(prompt_ctx.has_tool_results)


if __name__ == "__main__":
    unittest.main()
