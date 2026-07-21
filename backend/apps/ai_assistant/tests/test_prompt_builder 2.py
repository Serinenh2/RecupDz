"""
Tests for PromptBuilder — assembles the final prompt sent to Hermes.

Covers:
    - PromptSection / PromptContext data contracts
    - PromptBuilder.build() — all injection channels
    - build_gate_prompt() — Hermes gate shortcut
    - build_response_prompt() — greeting / no-tool / with-tool
    - build_followup_prompt() — follow-up generation
    - History trimming, tool result truncation
    - Priority ordering of sections
    - Framework independence (no Django imports)
"""

import unittest
from unittest.mock import MagicMock

from apps.ai_assistant.enterprise.prompt_builder import (
    POLICY_ANTI_HALLUCINATION,
    POLICY_CONCISE,
    POLICY_LANGUAGE_MATCH,
    POLICY_NO_INTERNAL_LEAK,
    _DEFAULT_MAX_HISTORY,
    _DEFAULT_POLICIES,
    _LABEL_COMPANY,
    _LABEL_LANGUAGE,
    _LABEL_POLICIES,
    _LABEL_ROLE,
    _LABEL_RULES,
    _LABEL_SYSTEM,
    _LABEL_TOOLS,
    _MAX_TOOL_RESULT_CHARS,
    PromptBuilder,
    PromptContext,
    PromptSection,
)


# ════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════


def _make_builder(**kwargs) -> PromptBuilder:
    return PromptBuilder(**kwargs)


def _make_history(n: int = 4) -> list:
    """Create n conversation messages (alternating user/assistant)."""
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"Message {i}"})
    return msgs


# ════════════════════════════════════════════════════════════════════════
# Data Contract: PromptSection
# ════════════════════════════════════════════════════════════════════════


class TestPromptSection(unittest.TestCase):

    def test_creation(self):
        s = PromptSection(label="test", content="hello", priority=10)
        self.assertEqual(s.label, "test")
        self.assertEqual(s.content, "hello")
        self.assertEqual(s.priority, 10)

    def test_default_priority(self):
        s = PromptSection(label="x", content="y")
        self.assertEqual(s.priority, 0)

    def test_to_dict(self):
        s = PromptSection(label="L", content="C", priority=5)
        d = s.to_dict()
        self.assertEqual(d["label"], "L")
        self.assertEqual(d["content"], "C")
        self.assertEqual(d["priority"], 5)

    def test_to_dict_default_priority_omitted(self):
        s = PromptSection(label="L", content="C")
        d = s.to_dict()
        self.assertNotIn("priority", d)

    def test_frozen(self):
        s = PromptSection(label="x", content="y")
        with self.assertRaises(AttributeError):
            s.label = "z"


# ════════════════════════════════════════════════════════════════════════
# Data Contract: PromptContext
# ════════════════════════════════════════════════════════════════════════


class TestPromptContext(unittest.TestCase):

    def _make_ctx(self, **overrides) -> PromptContext:
        defaults = dict(
            system_prompt="You are helpful.",
            history=[],
            message="",
            language="",
            user_role="",
            has_company_knowledge=False,
            has_tool_results=False,
            has_business_rules=False,
            section_count=0,
            sections=[],
        )
        defaults.update(overrides)
        return PromptContext(**defaults)

    def test_creation_minimal(self):
        ctx = self._make_ctx()
        self.assertEqual(ctx.system_prompt, "You are helpful.")
        self.assertEqual(ctx.history, [])
        self.assertEqual(ctx.message, "")

    def test_has_history_true(self):
        ctx = self._make_ctx(history=[{"role": "user", "content": "hi"}])
        self.assertTrue(ctx.has_history)

    def test_has_history_false(self):
        ctx = self._make_ctx(history=[])
        self.assertFalse(ctx.has_history)

    def test_prompt_length(self):
        ctx = self._make_ctx(system_prompt="hello")
        self.assertEqual(ctx.prompt_length, 5)

    def test_is_too_long_false(self):
        ctx = self._make_ctx(system_prompt="short")
        self.assertFalse(ctx.is_too_long)

    def test_is_too_long_true(self):
        ctx = self._make_ctx(system_prompt="x" * 9000)
        self.assertTrue(ctx.is_too_long)

    def test_to_dict_minimal(self):
        ctx = self._make_ctx()
        d = ctx.to_dict()
        self.assertEqual(d["system_prompt"], "You are helpful.")
        self.assertEqual(d["history_length"], 0)
        self.assertEqual(d["message_length"], 0)
        self.assertFalse(d["has_company_knowledge"])
        self.assertFalse(d["has_tool_results"])
        self.assertFalse(d["has_business_rules"])
        self.assertEqual(d["section_count"], 0)
        self.assertNotIn("history", d)

    def test_to_dict_with_history(self):
        hist = [{"role": "user", "content": "hi"}]
        ctx = self._make_ctx(history=hist)
        d = ctx.to_dict()
        self.assertEqual(d["history_length"], 1)
        self.assertEqual(d["history"], hist)

    def test_to_dict_with_sections(self):
        sections = [PromptSection(label="L", content="C")]
        ctx = self._make_ctx(sections=sections)
        d = ctx.to_dict()
        self.assertEqual(len(d["sections"]), 1)
        self.assertEqual(d["sections"][0]["label"], "L")

    def test_to_dict_metadata(self):
        ctx = self._make_ctx(
            language="fr", user_role="admin",
            has_company_knowledge=True, has_tool_results=True,
            has_business_rules=True, section_count=5,
        )
        d = ctx.to_dict()
        self.assertEqual(d["language"], "fr")
        self.assertEqual(d["user_role"], "admin")
        self.assertTrue(d["has_company_knowledge"])
        self.assertTrue(d["has_tool_results"])
        self.assertTrue(d["has_business_rules"])
        self.assertEqual(d["section_count"], 5)

    def test_to_ollama_kwargs(self):
        ctx = self._make_ctx(
            system_prompt="sys",
            history=[{"role": "user", "content": "hi"}],
            message="hello",
        )
        kw = ctx.to_ollama_kwargs()
        self.assertEqual(kw["system_prompt"], "sys")
        self.assertEqual(kw["message"], "hello")
        self.assertEqual(len(kw["history"]), 1)

    def test_frozen(self):
        ctx = self._make_ctx()
        with self.assertRaises(AttributeError):
            ctx.system_prompt = "new"


# ════════════════════════════════════════════════════════════════════════
# PromptBuilder — build()
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderBuild(unittest.TestCase):

    def setUp(self):
        self.builder = _make_builder()

    def test_empty_build(self):
        ctx = self.builder.build()
        self.assertEqual(ctx.message, "")
        self.assertEqual(ctx.section_count, 1)  # default policies only

    def test_system_instructions(self):
        ctx = self.builder.build(system_instructions="You are helpful.")
        self.assertIn("You are helpful.", ctx.system_prompt)
        self.assertEqual(ctx.section_count, 2)  # system + policies

    def test_company_knowledge(self):
        ctx = self.builder.build(
            system_instructions="Base",
            company_knowledge="BSD info here",
        )
        self.assertIn("BSD info here", ctx.system_prompt)
        self.assertTrue(ctx.has_company_knowledge)

    def test_company_knowledge_not_present(self):
        ctx = self.builder.build(system_instructions="Base")
        self.assertFalse(ctx.has_company_knowledge)

    def test_business_rules(self):
        rules = ["Rule 1: be polite", "Rule 2: be concise"]
        ctx = self.builder.build(
            system_instructions="Base",
            business_rules=rules,
        )
        self.assertIn("Rule 1: be polite", ctx.system_prompt)
        self.assertIn("Rule 2: be concise", ctx.system_prompt)
        self.assertTrue(ctx.has_business_rules)

    def test_business_rules_empty_list(self):
        ctx = self.builder.build(
            system_instructions="Base",
            business_rules=[],
        )
        self.assertFalse(ctx.has_business_rules)

    def test_tool_results_dict(self):
        data = {"count": 5, "items": ["a", "b"]}
        ctx = self.builder.build(
            system_instructions="Base",
            tool_results=data,
            tool_name="waste_tool",
        )
        self.assertIn("waste_tool", ctx.system_prompt)
        self.assertIn('"count": 5', ctx.system_prompt)
        self.assertTrue(ctx.has_tool_results)

    def test_tool_results_none_not_injected(self):
        ctx = self.builder.build(
            system_instructions="Base",
            tool_results=None,
        )
        self.assertFalse(ctx.has_tool_results)

    def test_tool_results_truncation(self):
        huge = {"data": "x" * 5000}
        ctx = self.builder.build(
            system_instructions="Base",
            tool_results=huge,
            tool_name="test_tool",
        )
        self.assertIn("[truncated]", ctx.system_prompt)

    def test_user_language(self):
        ctx = self.builder.build(
            system_instructions="Base",
            user_language="fr",
        )
        self.assertEqual(ctx.language, "fr")
        self.assertIn("fr", ctx.system_prompt)

    def test_user_role(self):
        ctx = self.builder.build(
            system_instructions="Base",
            user_role="admin",
        )
        self.assertEqual(ctx.user_role, "admin")
        self.assertIn("admin", ctx.system_prompt)

    def test_ai_policies_custom(self):
        policies = ["Custom policy A", "Custom policy B"]
        ctx = self.builder.build(
            system_instructions="Base",
            ai_policies=policies,
        )
        self.assertIn("Custom policy A", ctx.system_prompt)
        self.assertIn("Custom policy B", ctx.system_prompt)

    def test_ai_policies_default(self):
        ctx = self.builder.build(system_instructions="Base")
        for p in _DEFAULT_POLICIES:
            self.assertIn(p, ctx.system_prompt)

    def test_ai_policies_empty_list_no_policies(self):
        ctx = self.builder.build(
            system_instructions="Base",
            ai_policies=[],
        )
        self.assertNotIn("CRITICAL:", ctx.system_prompt)
        self.assertNotIn("NEVER invent", ctx.system_prompt)

    def test_extra_sections(self):
        extra = PromptSection(label="CUSTOM", content="extra data", priority=95)
        ctx = self.builder.build(
            system_instructions="Base",
            extra_sections=[extra],
        )
        self.assertIn("extra data", ctx.system_prompt)

    def test_message_passed_through(self):
        ctx = self.builder.build(
            message="Combien de BSD ?",
            system_instructions="Base",
        )
        self.assertEqual(ctx.message, "Combien de BSD ?")

    def test_section_count(self):
        ctx = self.builder.build(
            system_instructions="Base",
            company_knowledge="RAG",
            business_rules=["Rule 1"],
            tool_results={"k": "v"},
            user_language="fr",
            user_role="admin",
        )
        self.assertGreaterEqual(ctx.section_count, 6)


# ════════════════════════════════════════════════════════════════════════
# PromptBuilder — History Trimming
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderHistory(unittest.TestCase):

    def test_empty_history(self):
        builder = _make_builder()
        ctx = builder.build(conversation_history=[])
        self.assertEqual(ctx.history, [])

    def test_none_history(self):
        builder = _make_builder()
        ctx = builder.build(conversation_history=None)
        self.assertEqual(ctx.history, [])

    def test_short_history_not_trimmed(self):
        builder = _make_builder(max_history=10)
        hist = _make_history(4)
        ctx = builder.build(conversation_history=hist)
        self.assertEqual(len(ctx.history), 4)

    def test_long_history_trimmed(self):
        builder = _make_builder(max_history=3)
        hist = _make_history(10)
        ctx = builder.build(conversation_history=hist)
        # max_history=3 → max_entries=6 → last 6
        self.assertEqual(len(ctx.history), 6)

    def test_history_preserves_order(self):
        builder = _make_builder(max_history=10)
        hist = _make_history(6)
        ctx = builder.build(conversation_history=hist)
        self.assertEqual(ctx.history[0]["content"], "Message 0")
        self.assertEqual(ctx.history[-1]["content"], "Message 5")

    def test_custom_max_history(self):
        builder = _make_builder(max_history=1)
        hist = _make_history(8)
        ctx = builder.build(conversation_history=hist)
        # max_history=1 → max_entries=2 → last 2
        self.assertEqual(len(ctx.history), 2)

    def test_odd_history_count(self):
        builder = _make_builder(max_history=2)
        hist = _make_history(5)
        ctx = builder.build(conversation_history=hist)
        self.assertEqual(len(ctx.history), 4)


# ════════════════════════════════════════════════════════════════════════
# PromptBuilder — Priority Ordering
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderPriority(unittest.TestCase):

    def test_system_before_company_knowledge(self):
        builder = _make_builder()
        ctx = builder.build(
            system_instructions="Identity prompt",
            company_knowledge="RAG data here",
        )
        sys_pos = ctx.system_prompt.find("Identity prompt")
        rag_pos = ctx.system_prompt.find("RAG data here")
        self.assertLess(sys_pos, rag_pos)

    def test_company_before_tool_results(self):
        builder = _make_builder()
        ctx = builder.build(
            system_instructions="Base",
            company_knowledge="RAG data",
            tool_results={"key": "value"},
            tool_name="test_tool",
        )
        rag_pos = ctx.system_prompt.find("RAG data")
        tool_pos = ctx.system_prompt.find("test_tool")
        self.assertLess(rag_pos, tool_pos)

    def test_role_before_language(self):
        builder = _make_builder()
        ctx = builder.build(
            system_instructions="Base",
            user_role="admin",
            user_language="fr",
        )
        role_pos = ctx.system_prompt.find("admin")
        lang_pos = ctx.system_prompt.find("fr")
        self.assertLess(role_pos, lang_pos)

    def test_policies_last(self):
        builder = _make_builder()
        ctx = builder.build(
            system_instructions="Base",
            company_knowledge="RAG",
            ai_policies=["My policy"],
        )
        policy_pos = ctx.system_prompt.find("My policy")
        base_pos = ctx.system_prompt.find("Base")
        self.assertGreater(policy_pos, base_pos)


# ════════════════════════════════════════════════════════════════════════
# PromptBuilder — build_gate_prompt()
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderGate(unittest.TestCase):

    def setUp(self):
        self.builder = _make_builder()

    def test_gate_basic(self):
        ctx = self.builder.build_gate_prompt(
            message="Bonjour",
            tools_description="- waste_tool: Search wastes",
        )
        self.assertIn("waste_tool", ctx.system_prompt)
        self.assertIn("Bonjour", ctx.message)
        self.assertIn("intent analyzer", ctx.system_prompt)

    def test_gate_has_tools_description(self):
        tools = "- waste_tool: Search\n- bsd_tool: BSD operations"
        ctx = self.builder.build_gate_prompt(
            message="test", tools_description=tools,
        )
        self.assertIn("waste_tool", ctx.system_prompt)
        self.assertIn("bsd_tool", ctx.system_prompt)

    def test_gate_with_history(self):
        hist = [{"role": "user", "content": "hi"}]
        ctx = self.builder.build_gate_prompt(
            message="follow up", tools_description="",
            conversation_history=hist,
        )
        self.assertEqual(len(ctx.history), 1)

    def test_gate_no_policies(self):
        ctx = self.builder.build_gate_prompt(
            message="test", tools_description="",
        )
        self.assertNotIn("CRITICAL:", ctx.system_prompt)
        self.assertNotIn("NEVER invent", ctx.system_prompt)

    def test_gate_with_language(self):
        ctx = self.builder.build_gate_prompt(
            message="test", tools_description="",
            user_language="fr",
        )
        self.assertIn("fr", ctx.system_prompt)

    def test_gate_returns_prompt_context(self):
        ctx = self.builder.build_gate_prompt(
            message="test", tools_description="",
        )
        self.assertIsInstance(ctx, PromptContext)


# ════════════════════════════════════════════════════════════════════════
# PromptBuilder — build_response_prompt()
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderResponse(unittest.TestCase):

    def setUp(self):
        self.builder = _make_builder()

    def test_greeting(self):
        ctx = self.builder.build_response_prompt(
            message="Bonjour", tool_name="greeting",
        )
        self.assertIn("friendly AI assistant", ctx.system_prompt)
        self.assertNotIn("CRITICAL:", ctx.system_prompt)
        self.assertNotIn("NEVER invent", ctx.system_prompt)

    def test_no_tool(self):
        ctx = self.builder.build_response_prompt(
            message="What is waste?", tool_name="none",
        )
        self.assertIn("general knowledge", ctx.system_prompt)
        self.assertIn("SAME LANGUAGE", ctx.system_prompt)

    def test_empty_tool_name(self):
        ctx = self.builder.build_response_prompt(
            message="test", tool_name="",
        )
        self.assertIn("general knowledge", ctx.system_prompt)

    def test_with_tool_results(self):
        data = {"count": 10}
        ctx = self.builder.build_response_prompt(
            message="How many BSD?",
            tool_results=data,
            tool_name="bsd_tool",
        )
        self.assertIn("bsd_tool", ctx.system_prompt)
        self.assertIn('"count": 10', ctx.system_prompt)
        self.assertIn("CRITICAL:", ctx.system_prompt)

    def test_with_company_knowledge(self):
        ctx = self.builder.build_response_prompt(
            message="test",
            tool_results={"x": 1},
            tool_name="waste_tool",
            company_knowledge="Company BSD info",
        )
        self.assertIn("Company BSD info", ctx.system_prompt)
        self.assertIn("waste_tool", ctx.system_prompt)

    def test_with_history(self):
        hist = [{"role": "user", "content": "previous"}]
        ctx = self.builder.build_response_prompt(
            message="follow up",
            tool_results={"k": "v"},
            tool_name="waste_tool",
            conversation_history=hist,
        )
        self.assertEqual(len(ctx.history), 1)

    def test_with_role(self):
        ctx = self.builder.build_response_prompt(
            message="test",
            tool_results={"k": "v"},
            tool_name="waste_tool",
            user_role="admin",
        )
        self.assertIn("admin", ctx.system_prompt)

    def test_returns_prompt_context(self):
        ctx = self.builder.build_response_prompt(
            message="test", tool_name="none",
        )
        self.assertIsInstance(ctx, PromptContext)


# ════════════════════════════════════════════════════════════════════════
# PromptBuilder — build_followup_prompt()
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderFollowup(unittest.TestCase):

    def setUp(self):
        self.builder = _make_builder()

    def test_followup_basic(self):
        ctx = self.builder.build_followup_prompt(
            message="How many BSD?",
            response="Il y a 12 BSD en attente.",
        )
        self.assertIn("How many BSD?", ctx.message)
        self.assertIn("Il y a 12 BSD", ctx.message)
        self.assertIn("follow-up", ctx.system_prompt.lower())
        self.assertIn("JSON array", ctx.system_prompt)

    def test_followup_with_tool_results(self):
        ctx = self.builder.build_followup_prompt(
            message="test",
            response="result here",
            tool_results={"count": 5},
            tool_name="waste_tool",
        )
        self.assertIn("TOOL DATA SUMMARY", ctx.message)
        self.assertIn('"count": 5', ctx.message)

    def test_followup_without_tool_results(self):
        ctx = self.builder.build_followup_prompt(
            message="test", response="answer",
        )
        self.assertNotIn("TOOL DATA SUMMARY", ctx.message)

    def test_followup_with_history(self):
        hist = [{"role": "user", "content": "old"}]
        ctx = self.builder.build_followup_prompt(
            message="q", response="a",
            conversation_history=hist,
        )
        self.assertEqual(len(ctx.history), 1)

    def test_followup_response_truncated(self):
        long_response = "x" * 1000
        ctx = self.builder.build_followup_prompt(
            message="q", response=long_response,
        )
        self.assertIn("x" * 500, ctx.message)
        self.assertNotIn("x" * 501, ctx.message)

    def test_followup_tool_results_truncated(self):
        huge = {"data": "y" * 2000}
        ctx = self.builder.build_followup_prompt(
            message="q", response="a",
            tool_results=huge,
        )
        self.assertIn("TOOL DATA SUMMARY", ctx.message)

    def test_followup_returns_prompt_context(self):
        ctx = self.builder.build_followup_prompt(
            message="q", response="a",
        )
        self.assertIsInstance(ctx, PromptContext)


# ════════════════════════════════════════════════════════════════════════
# PromptBuilder — Tool Result Formatting
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderToolResults(unittest.TestCase):

    def test_tool_result_with_name(self):
        builder = _make_builder()
        ctx = builder.build(
            tool_results={"x": 1}, tool_name="my_tool",
        )
        self.assertIn("TOOL RESULT (my_tool)", ctx.system_prompt)

    def test_tool_result_without_name(self):
        builder = _make_builder()
        ctx = builder.build(tool_results={"x": 1})
        self.assertIn("TOOL RESULT:", ctx.system_prompt)

    def test_tool_result_truncation_at_limit(self):
        builder = _make_builder(max_tool_result_chars=100)
        data = {"key": "a" * 200}
        ctx = builder.build(tool_results=data)
        self.assertIn("[truncated]", ctx.system_prompt)

    def test_tool_result_list(self):
        builder = _make_builder()
        data = [1, 2, 3]
        ctx = builder.build(tool_results=data, tool_name="list_tool")
        self.assertIn("[1, 2, 3]", ctx.system_prompt)

    def test_tool_result_string(self):
        builder = _make_builder()
        ctx = builder.build(tool_results="simple string", tool_name="s_tool")
        self.assertIn("simple string", ctx.system_prompt)

    def test_tool_result_nested_dict(self):
        builder = _make_builder()
        data = {"outer": {"inner": "value"}}
        ctx = builder.build(tool_results=data)
        self.assertIn("inner", ctx.system_prompt)


# ════════════════════════════════════════════════════════════════════════
# PromptBuilder — Edge Cases
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderEdgeCases(unittest.TestCase):

    def test_all_inputs(self):
        builder = _make_builder()
        ctx = builder.build(
            message="Full test",
            system_instructions="You are the AI.",
            conversation_history=_make_history(6),
            company_knowledge="Company data here",
            business_rules=["Rule A", "Rule B"],
            tool_results={"result": 42},
            tool_name="waste_tool",
            user_language="fr",
            user_role="agent_collecte",
            ai_policies=["Policy X"],
            extra_sections=[
                PromptSection(label="EXTRA", content="extra", priority=40),
            ],
        )
        self.assertIn("You are the AI.", ctx.system_prompt)
        self.assertIn("Company data here", ctx.system_prompt)
        self.assertIn("Rule A", ctx.system_prompt)
        self.assertIn("waste_tool", ctx.system_prompt)
        self.assertIn("fr", ctx.system_prompt)
        self.assertIn("agent_collecte", ctx.system_prompt)
        self.assertIn("Policy X", ctx.system_prompt)
        self.assertIn("extra", ctx.system_prompt)
        self.assertEqual(ctx.message, "Full test")
        self.assertTrue(ctx.has_company_knowledge)
        self.assertTrue(ctx.has_tool_results)
        self.assertTrue(ctx.has_business_rules)

    def test_only_message(self):
        builder = _make_builder()
        ctx = builder.build(message="Hello")
        self.assertEqual(ctx.message, "Hello")
        self.assertEqual(ctx.section_count, 1)  # default policies only

    def test_empty_sections_filtered(self):
        builder = _make_builder()
        ctx = builder.build(
            system_instructions="Base",
            company_knowledge="",
            business_rules=[],
            ai_policies=[],
        )
        self.assertEqual(ctx.section_count, 1)  # only system

    def test_special_characters_in_values(self):
        builder = _make_builder()
        data = {"key": "àéù € ¥"}
        ctx = builder.build(
            system_instructions="Base",
            company_knowledge="Données: 100%",
            tool_results=data,
            user_language="fr",
        )
        self.assertIn("àéù", ctx.system_prompt)
        self.assertIn("100%", ctx.system_prompt)

    def test_builder_custom_max_history(self):
        builder = _make_builder(max_history=2)
        hist = _make_history(20)
        ctx = builder.build(conversation_history=hist)
        self.assertEqual(len(ctx.history), 4)

    def test_builder_custom_max_tool_result_chars(self):
        builder = _make_builder(max_tool_result_chars=50)
        data = {"key": "a" * 100}
        ctx = builder.build(tool_results=data)
        self.assertIn("[truncated]", ctx.system_prompt)


# ════════════════════════════════════════════════════════════════════════
# Framework Independence
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderFrameworkIndependence(unittest.TestCase):

    def test_no_django_imports(self):
        import importlib
        import apps.ai_assistant.enterprise.prompt_builder as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                if stripped.startswith("from ") or stripped.startswith("import "):
                    self.assertNotIn("django", stripped.lower(),
                                     f"Django import found: {stripped}")

    def test_no_model_imports(self):
        import importlib
        import apps.ai_assistant.enterprise.prompt_builder as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    self.assertNotIn("models", stripped.lower(),
                                     f"Model import found: {stripped}")

    def test_no_repository_imports(self):
        import importlib
        import apps.ai_assistant.enterprise.prompt_builder as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("from ") or stripped.startswith("import "):
                    self.assertNotIn("repository", stripped.lower(),
                                     f"Repository import found: {stripped}")

    def test_dataclasses_frozen(self):
        self.assertTrue(PromptContext.__dataclass_params__.frozen)
        self.assertTrue(PromptSection.__dataclass_params__.frozen)

    def test_no_orm_queries(self):
        import importlib
        import apps.ai_assistant.enterprise.prompt_builder as mod
        source = importlib.util.find_spec(mod.__name__).origin
        with open(source, "r") as f:
            content = f.read()
        self.assertNotIn(".objects.", content)
        self.assertNotIn(".save(", content)
        self.assertNotIn(".delete(", content)
        self.assertNotIn(".filter(", content)
        self.assertNotIn(".all()", content)


# ════════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderConstants(unittest.TestCase):

    def test_default_max_history(self):
        self.assertEqual(_DEFAULT_MAX_HISTORY, 10)

    def test_max_tool_result_chars(self):
        self.assertEqual(_MAX_TOOL_RESULT_CHARS, 3000)

    def test_default_policies_count(self):
        self.assertEqual(len(_DEFAULT_POLICIES), 4)

    def test_policy_strings_not_empty(self):
        for p in _DEFAULT_POLICIES:
            self.assertIsInstance(p, str)
            self.assertGreater(len(p), 0)

    def test_label_constants(self):
        self.assertIn("SYSTEM", _LABEL_SYSTEM)
        self.assertIn("COMPANY", _LABEL_COMPANY)
        self.assertIn("BUSINESS", _LABEL_RULES)
        self.assertIn("TOOL", _LABEL_TOOLS)
        self.assertIn("POLICIES", _LABEL_POLICIES)
        self.assertIn("ROLE", _LABEL_ROLE)
        self.assertIn("LANGUAGE", _LABEL_LANGUAGE)


# ════════════════════════════════════════════════════════════════════════
# Integration — Full Pipeline
# ════════════════════════════════════════════════════════════════════════


class TestPromptBuilderIntegration(unittest.TestCase):

    def test_full_gate_then_response_flow(self):
        builder = _make_builder()

        # Step 1: Gate
        gate_ctx = builder.build_gate_prompt(
            message="Quels sont les BSD en attente ?",
            tools_description=(
                "- waste_tool: Search wastes\n"
                "- bsd_tool: BSD operations\n"
                "- declaration_tool: Declarations"
            ),
            conversation_history=[
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour !"},
            ],
            user_language="fr",
        )
        self.assertIn("bsd_tool", gate_ctx.system_prompt)
        self.assertEqual(gate_ctx.language, "fr")
        self.assertEqual(len(gate_ctx.history), 2)

        # Step 2: Response
        tool_data = {"bsd_count": 12, "status": "en_attente"}
        resp_ctx = builder.build_response_prompt(
            message="Quels sont les BSD en attente ?",
            tool_results=tool_data,
            tool_name="bsd_tool",
            company_knowledge="BSD = Bordereau de Suivi des Déchets",
            conversation_history=[
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour !"},
                {"role": "user", "content": "Quels sont les BSD en attente ?"},
            ],
            user_language="fr",
            user_role="responsable_collecte",
        )
        self.assertIn("bsd_tool", resp_ctx.system_prompt)
        self.assertIn("12", resp_ctx.system_prompt)
        self.assertIn("BSD = Bordereau", resp_ctx.system_prompt)
        self.assertIn("responsable_collecte", resp_ctx.system_prompt)
        self.assertTrue(resp_ctx.has_company_knowledge)
        self.assertTrue(resp_ctx.has_tool_results)

        # Step 3: Follow-up
        follow_ctx = builder.build_followup_prompt(
            message="Quels sont les BSD en attente ?",
            response="Il y a 12 BSD en attente de traitement.",
            tool_results=tool_data,
            tool_name="bsd_tool",
            conversation_history=[
                {"role": "user", "content": "Quels sont les BSD en attente ?"},
                {"role": "assistant", "content": "Il y a 12 BSD..."},
            ],
            user_language="fr",
        )
        self.assertIn("JSON array", follow_ctx.system_prompt)
        self.assertEqual(follow_ctx.language, "fr")

    def test_ollama_kwargs_compatibility(self):
        builder = _make_builder()
        ctx = builder.build(
            message="Test",
            system_instructions="You are helpful.",
            user_language="fr",
        )
        kw = ctx.to_ollama_kwargs()
        self.assertIn("message", kw)
        self.assertIn("history", kw)
        self.assertIn("system_prompt", kw)
        self.assertEqual(kw["message"], "Test")
        self.assertEqual(kw["system_prompt"], ctx.system_prompt)


if __name__ == "__main__":
    unittest.main()
