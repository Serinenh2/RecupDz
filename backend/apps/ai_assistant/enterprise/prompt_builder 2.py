"""
Prompt Builder — assembles the final prompt sent to Hermes.

Responsibilities:
    - Inject system instructions (role, identity, base prompt).
    - Inject conversation history (trimmed to max turns).
    - Inject company context (RAG knowledge blocks).
    - Inject business rules (domain-specific constraints).
    - Inject tool results (structured JSON from tool execution).
    - Inject user language (detected language hint).
    - Inject user role (RBAC role for permission-aware responses).
    - Inject AI policies (anti-hallucination, response format rules).

Architecture:
    PromptBuilder is a stateless assembler.  Each call to `build()` returns
    a frozen `PromptContext` that can be consumed by the orchestrator or
    any LLM adapter.

    PromptBuilder ──build()──► PromptContext ──► OllamaService.chat()

Design rules:
    - Zero Django imports.
    - Zero repository access.
    - Zero business logic — only string assembly and trimming.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

_DEFAULT_MAX_HISTORY: int = 10
_MAX_TOOL_RESULT_CHARS: int = 3000

_LANG_FR: str = "fr"
_LANG_EN: str = "en"

_SECTION_SEPARATOR: str = "\n\n"
_LABEL_SYSTEM: str = "=== SYSTEM INSTRUCTIONS ==="
_LABEL_COMPANY: str = "=== COMPANY KNOWLEDGE (RECUP-DZ) ==="
_LABEL_RULES: str = "=== BUSINESS RULES ==="
_LABEL_TOOLS: str = "=== TOOL RESULTS ==="
_LABEL_POLICIES: str = "=== AI POLICIES ==="
_LABEL_ROLE: str = "=== USER ROLE ==="
_LABEL_LANGUAGE: str = "=== LANGUAGE ==="

# ── AI Policy defaults ────────────────────────────────────────────────

POLICY_ANTI_HALLUCINATION: str = (
    "CRITICAL: Use ONLY the data provided in tool results and company "
    "knowledge.  NEVER invent, fabricate, or assume information."
)
POLICY_LANGUAGE_MATCH: str = (
    "Respond in the SAME LANGUAGE as the user's message."
)
POLICY_NO_INTERNAL_LEAK: str = (
    "NEVER reveal internal JSON, tool names, system details, "
    "or database structure to the user."
)
POLICY_CONCISE: str = (
    "Be concise but informative.  Format with markdown when appropriate "
    "(bold, lists)."
)

_DEFAULT_POLICIES: List[str] = [
    POLICY_ANTI_HALLUCINATION,
    POLICY_LANGUAGE_MATCH,
    POLICY_NO_INTERNAL_LEAK,
    POLICY_CONCISE,
]


# ══════════════════════════════════════════════════════════════════════
# Data Contracts
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PromptSection:
    """A single labelled section injected into the system prompt."""

    label: str
    content: str
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "label": self.label,
            "content": self.content,
        }
        if self.priority:
            d["priority"] = self.priority
        return d


@dataclass(frozen=True)
class PromptContext:
    """
    Fully assembled prompt ready to be sent to the LLM.

    Consumed by the orchestrator or any LLM adapter.  Contains the
    assembled system prompt, trimmed conversation history, and metadata
    about what was injected.

    Usage:
        ctx = builder.build(message="Combien de BSD ?", ...)
        ollama.chat(message=ctx.message, history=ctx.history,
                    system_prompt=ctx.system_prompt)
    """

    system_prompt: str
    history: List[Dict[str, str]] = field(default_factory=list)
    message: str = ""
    language: str = ""
    user_role: str = ""
    has_company_knowledge: bool = False
    has_tool_results: bool = False
    has_business_rules: bool = False
    section_count: int = 0
    sections: List[PromptSection] = field(default_factory=list)

    @property
    def has_history(self) -> bool:
        return len(self.history) > 0

    @property
    def prompt_length(self) -> int:
        return len(self.system_prompt)

    @property
    def is_too_long(self) -> bool:
        """Heuristic: system prompt exceeds safe Hermes context window."""
        return self.prompt_length > 8000

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "system_prompt": self.system_prompt,
            "history_length": len(self.history),
            "message_length": len(self.message),
            "language": self.language,
            "user_role": self.user_role,
            "has_company_knowledge": self.has_company_knowledge,
            "has_tool_results": self.has_tool_results,
            "has_business_rules": self.has_business_rules,
            "section_count": self.section_count,
            "prompt_length": self.prompt_length,
        }
        if self.history:
            d["history"] = self.history
        if self.sections:
            d["sections"] = [s.to_dict() for s in self.sections]
        return d

    def to_ollama_kwargs(self) -> Dict[str, Any]:
        """
        Return kwargs compatible with OllamaService.chat().

        Returns:
            Dict with keys: message, history, system_prompt.
        """
        return {
            "message": self.message,
            "history": self.history,
            "system_prompt": self.system_prompt,
        }


# ══════════════════════════════════════════════════════════════════════
# Prompt Builder
# ══════════════════════════════════════════════════════════════════════


class PromptBuilder:
    """
    Stateless assembler for Hermes prompts.

    Each call to `build()` collects all injected sections, trims
    conversation history, and returns a frozen `PromptContext`.

    Usage:
        builder = PromptBuilder()
        ctx = builder.build(
            message="Quels sont les BSD en attente ?",
            system_instructions="You are the AI Agent of RECUP-DZ...",
            conversation_history=[...],
            company_knowledge="...",
            tool_results={"bsd_count": 12},
        )
        ollama.chat(**ctx.to_ollama_kwargs())
    """

    def __init__(
        self,
        *,
        max_history: int = _DEFAULT_MAX_HISTORY,
        max_tool_result_chars: int = _MAX_TOOL_RESULT_CHARS,
    ) -> None:
        self._max_history = max_history
        self._max_tool_result_chars = max_tool_result_chars

    # ════════════════════════════════════════════════════════════════
    # Public API
    # ════════════════════════════════════════════════════════════════

    def build(
        self,
        message: str = "",
        *,
        system_instructions: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        company_knowledge: str = "",
        business_rules: Optional[List[str]] = None,
        tool_results: Optional[Any] = None,
        tool_name: str = "",
        user_language: str = "",
        user_role: str = "",
        ai_policies: Optional[List[str]] = None,
        extra_sections: Optional[List[PromptSection]] = None,
    ) -> PromptContext:
        """
        Assemble a PromptContext from all available inputs.

        Args:
            message: Current user message.
            system_instructions: Base system prompt (identity, role).
            conversation_history: Previous user/assistant message pairs.
            company_knowledge: RAG context block (company knowledge).
            business_rules: Additional domain-specific rules.
            tool_results: Structured JSON from tool execution.
            tool_name: Name of the tool that produced results.
            user_language: Detected language code (fr/en).
            user_role: User's RBAC role.
            ai_policies: Additional AI policy constraints.
            extra_sections: Additional labelled sections to inject.

        Returns:
            Frozen PromptContext with assembled prompt and metadata.
        """
        sections: List[PromptSection] = []
        trimmed_history = self._trim_history(conversation_history)

        # ── Step 1: System instructions (base identity) ─────────────
        if system_instructions:
            sections.append(PromptSection(
                label="system", content=system_instructions, priority=100,
            ))

        # ── Step 2: User role ───────────────────────────────────────
        if user_role:
            sections.append(PromptSection(
                label=_LABEL_ROLE,
                content=f"User role: {user_role}",
                priority=90,
            ))

        # ── Step 3: Language hint ───────────────────────────────────
        if user_language:
            sections.append(PromptSection(
                label=_LABEL_LANGUAGE,
                content=f"User language: {user_language}",
                priority=85,
            ))

        # ── Step 4: Company knowledge (RAG) ─────────────────────────
        if company_knowledge:
            sections.append(PromptSection(
                label=_LABEL_COMPANY,
                content=company_knowledge,
                priority=80,
            ))

        # ── Step 5: Business rules ──────────────────────────────────
        if business_rules:
            rules_text = "\n".join(
                f"- {rule}" for rule in business_rules
            )
            sections.append(PromptSection(
                label=_LABEL_RULES,
                content=rules_text,
                priority=70,
            ))

        # ── Step 6: Tool results ────────────────────────────────────
        if tool_results is not None:
            tool_block = self._format_tool_results(
                tool_results, tool_name,
            )
            sections.append(PromptSection(
                label=_LABEL_TOOLS,
                content=tool_block,
                priority=60,
            ))

        # ── Step 7: AI policies ─────────────────────────────────────
        policies = ai_policies if ai_policies is not None else _DEFAULT_POLICIES
        if policies:
            policies_text = "\n".join(
                f"- {policy}" for policy in policies
            )
            sections.append(PromptSection(
                label=_LABEL_POLICIES,
                content=policies_text,
                priority=50,
            ))

        # ── Step 8: Extra sections ──────────────────────────────────
        if extra_sections:
            sections.extend(extra_sections)

        # ── Assemble ────────────────────────────────────────────────
        sections.sort(key=lambda s: s.priority, reverse=True)
        system_prompt = self._assemble_prompt(sections)

        return PromptContext(
            system_prompt=system_prompt,
            history=trimmed_history,
            message=message,
            language=user_language,
            user_role=user_role,
            has_company_knowledge=bool(company_knowledge),
            has_tool_results=tool_results is not None,
            has_business_rules=bool(business_rules),
            section_count=len(sections),
            sections=list(sections),
        )

    def build_gate_prompt(
        self,
        message: str,
        tools_description: str,
        *,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_language: str = "",
    ) -> PromptContext:
        """
        Build the prompt for the Hermes gate (tool-needed? decision).

        A specialised shortcut for the orchestrator's gate step.

        Args:
            message: Current user message.
            tools_description: Formatted list of available tools.
            conversation_history: Previous messages.
            user_language: Detected language.

        Returns:
            PromptContext optimised for the gate decision.
        """
        gate_instructions = (
            "You are the intent analyzer for RECUP-DZ, a waste management "
            "platform in Algeria.\n"
            "Given the user message AND conversation history, determine if "
            "a business tool is needed.\n\n"
            "AVAILABLE TOOLS:\n"
            f"{tools_description}\n\n"
            "RULES:\n"
            "1. Return ONLY a JSON object — no commentary, no markdown.\n"
            "2. Format:\n"
            '   Tool needed: {{"tool_needed": true, "tool": "tool_name", '
            '"action": "action_name", "parameters": {{...}}}}\n'
            '   No tool needed: {{"tool_needed": false, "tool": "none"}}\n'
            '   Greeting: {{"tool_needed": false, "tool": "greeting"}}\n'
            "3. For greetings (bonjour, hello, salut, etc.) → tool: greeting\n"
            "4. For general knowledge questions with no business data → "
            "tool: none\n"
            "5. For questions about BSD, nomenclature, waste, declarations, "
            "inspections,\n"
            "   recuperateurs, transporters, producers, partners, statistics, "
            "regulations,\n"
            "   archives, traceability, notifications, dashboards, "
            "permissions, administrations → tool_needed: true\n"
            "6. Use ONLY exact tool names and action values listed above.\n"
            "7. Do NOT invent parameter names.\n"
            "8. If unsure whether a tool is needed, prefer tool_needed: true.\n"
            "9. Consider conversation history for context (e.g., follow-up "
            "questions).\n"
        )
        return self.build(
            message=message,
            system_instructions=gate_instructions,
            conversation_history=conversation_history,
            user_language=user_language,
            ai_policies=[],  # Gate needs no anti-hallucination policy
        )

    def build_response_prompt(
        self,
        message: str,
        *,
        tool_results: Optional[Any] = None,
        tool_name: str = "",
        company_knowledge: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_language: str = "",
        user_role: str = "",
    ) -> PromptContext:
        """
        Build the prompt for the response generation step.

        A specialised shortcut for the orchestrator's response generation.

        Args:
            message: Current user message.
            tool_results: Structured JSON from tool execution.
            tool_name: Name of the tool that produced results.
            company_knowledge: RAG context block.
            conversation_history: Previous messages.
            user_language: Detected language.
            user_role: User's RBAC role.

        Returns:
            PromptContext optimised for response generation.
        """
        if tool_name == "greeting":
            instructions = (
                "You are the friendly AI assistant of RECUP-DZ, a waste "
                "management platform in Algeria.  Greet the user warmly "
                "and briefly explain what you can help with.\n"
                "Be concise. Respond in the SAME LANGUAGE as the user's "
                "message."
            )
            policies: List[str] = []
        elif tool_name in ("none", ""):
            instructions = (
                "You are the AI Agent of RECUP-DZ, expert in waste "
                "management in Algeria.\n"
                "Answer the user's question directly using your knowledge.\n"
                "Be concise, accurate, and practical.\n"
                "Answer in the SAME LANGUAGE as the user's message.\n"
                "IMPORTANT: Clearly state that this is from general "
                "knowledge, not from the database."
            )
            policies = [POLICY_LANGUAGE_MATCH]
        else:
            instructions = (
                "You are the AI Agent of RECUP-DZ, expert in waste "
                "management in Algeria.\n"
                "The user asked a question.  A business tool was executed "
                "and returned the following structured JSON.\n"
                "Generate a clear, professional, natural-language response "
                "in the SAME LANGUAGE as the user's message.\n\n"
                "CRITICAL RULES:\n"
                "1. Use ONLY the data from the tool result — NEVER invent "
                "information.\n"
                "2. Be concise but informative.\n"
                "3. Format with markdown when appropriate (bold, lists).\n"
                "4. If the tool returned an error or empty results, explain "
                "it politely and suggest alternatives.\n"
                "5. Never reveal internal JSON, tool names, or system "
                "details to the user.\n"
                "6. If numerical data is present, present it clearly."
            )
            policies = [
                POLICY_ANTI_HALLUCINATION,
                POLICY_NO_INTERNAL_LEAK,
            ]

        return self.build(
            message=message,
            system_instructions=instructions,
            conversation_history=conversation_history,
            company_knowledge=company_knowledge,
            tool_results=tool_results,
            tool_name=tool_name,
            user_language=user_language,
            user_role=user_role,
            ai_policies=policies,
        )

    def build_followup_prompt(
        self,
        message: str,
        response: str,
        *,
        tool_results: Optional[Any] = None,
        tool_name: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_language: str = "",
    ) -> PromptContext:
        """
        Build the prompt for the follow-up generation step.

        Args:
            message: Original user message.
            response: The response that was just generated.
            tool_results: Tool results for context.
            tool_name: Tool name.
            conversation_history: Previous messages.
            user_language: Detected language.

        Returns:
            PromptContext optimised for follow-up generation.
        """
        followup_context = f"USER QUESTION: {message}\n\nAGENT RESPONSE: {response[:500]}"
        if tool_results is not None:
            result_summary = json.dumps(
                tool_results, ensure_ascii=False, default=str,
            )[:500]
            followup_context += f"\n\nTOOL DATA SUMMARY: {result_summary}"

        followup_instructions = (
            "You are the AI Agent of RECUP-DZ, waste management expert.\n"
            "Based on the user's question and the response just given, "
            "suggest 2-3 relevant follow-up questions the user might want "
            "to ask next.  Return ONLY a JSON array of strings.\n\n"
            "RULES:\n"
            "1. Return ONLY a JSON array — no commentary.\n"
            "2. Each follow-up must be a natural question in the SAME "
            "LANGUAGE as the user's message.\n"
            "3. Follow-ups must be relevant to the topic discussed.\n"
            "4. Do not repeat the original question.\n"
            "5. If no meaningful follow-up is possible, return an empty "
            'array: []\n\n'
            'Example: ["Quels sont les déchets dangereux dans cette '
            'catégorie ?", "Quelle est la réglementation applicable ?"]'
        )

        return self.build(
            message=followup_context,
            system_instructions=followup_instructions,
            conversation_history=conversation_history,
            user_language=user_language,
            ai_policies=[POLICY_LANGUAGE_MATCH],
        )

    # ════════════════════════════════════════════════════════════════
    # Internal — Assembly
    # ════════════════════════════════════════════════════════════════

    def _assemble_prompt(self, sections: List[PromptSection]) -> str:
        """
        Concatenate ordered sections into a single system prompt string.
        """
        parts: List[str] = []
        for section in sections:
            if not section.content:
                continue
            parts.append(section.content)
        return _SECTION_SEPARATOR.join(parts)

    def _trim_history(
        self,
        history: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """
        Trim conversation history to the most recent N turns.

        A "turn" is one user message + one assistant message = 2 entries.
        """
        if not history:
            return []
        max_entries = self._max_history * 2
        trimmed = history[-max_entries:]
        return trimmed

    def _format_tool_results(
        self,
        tool_results: Any,
        tool_name: str,
    ) -> str:
        """Format tool results as a labelled block for the system prompt."""
        result_json = json.dumps(
            tool_results, ensure_ascii=False, default=str,
        )
        if len(result_json) > self._max_tool_result_chars:
            result_json = (
                result_json[:self._max_tool_result_chars]
                + "... [truncated]"
            )
        label = f"TOOL RESULT ({tool_name})" if tool_name else "TOOL RESULT"
        return f"{label}:\n{result_json}"
