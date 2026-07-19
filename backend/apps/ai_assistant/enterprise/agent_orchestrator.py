"""
Agent Orchestrator — production-ready workflow engine.

Workflow (Hermes-first):
    User → Hermes (tool needed?) → AI Router (fast match) → Tool → Repo → DB → Hermes (response)

Responsibilities:
    1. Conversation Management — load/store history, context windowing
    2. Hermes Gate — LLM determines if a business tool is required
    3. AI Router — fast deterministic tool matching (when Hermes says tool needed)
    4. Entity Extraction — waste codes, BSD numbers, dates, names
    5. Tool Execution — via adapter layer → 22 domain tools → repositories → DB
    6. Response Generation — Hermes generates final answer with tool data
    7. Follow-ups + Memory — contextual questions + conversation storage

Architecture:
    - All dependencies injected via constructor (DI)
    - No Django model access — uses services and repositories only
    - Hermes NEVER accesses the database — communicates only through this orchestrator
    - Each step is independently testable
    - Comprehensive observability (tracing, metrics, audit)

Policies:
    - AI NEVER invents data — all facts come from tools or explicitly stated knowledge
    - Hermes is the single decision gate for tool usage
    - AI Router provides fast deterministic refinement after Hermes
    - Tool execution result JSON is passed verbatim to Hermes for response generation
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from apps.ai_assistant.core.interfaces import (
    Context,
    ExecutionPlan,
    FormattedResponse,
    Message,
    Role,
    TaskStep,
    ToolResult,
)

logger = logging.getLogger(__name__)


# ── Workflow States ───────────────────────────────────────────────────


class WorkflowState(str, Enum):
    RECEIVED = "received"
    CONVERSATION_LOADED = "conversation_loaded"
    HERMES_GATE = "hermes_gate"
    AI_ROUTER_REFINED = "ai_router_refined"
    ENTITIES_EXTRACTED = "entities_extracted"
    TOOL_SELECTED = "tool_selected"
    TOOL_EXECUTED = "tool_executed"
    RESPONSE_GENERATED = "response_generated"
    FOLLOWUPS_GENERATED = "followups_generated"
    MEMORY_STORED = "memory_stored"
    COMPLETED = "completed"
    ERROR = "error"


# ── Data Contracts ────────────────────────────────────────────────────


@dataclass(frozen=True)
class HermesDecision:
    """Result of Hermes gate — does the user need a business tool?"""
    tool_needed: bool
    tool: str  # tool name or "none" or "greeting"
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""


@dataclass(frozen=True)
class EntityExtraction:
    """Extracted entities from the user message."""
    waste_codes: List[str] = field(default_factory=list)
    bsd_numbers: List[str] = field(default_factory=list)
    agrement_numbers: List[str] = field(default_factory=list)
    years: List[str] = field(default_factory=list)
    quantities: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    percentages: List[str] = field(default_factory=list)
    raw_entities: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "waste_codes": self.waste_codes,
            "bsd_numbers": self.bsd_numbers,
            "agrement_numbers": self.agrement_numbers,
            "years": self.years,
            "quantities": self.quantities,
            "emails": self.emails,
            "phones": self.phones,
            "percentages": self.percentages,
        }

    @property
    def has_entities(self) -> bool:
        return bool(
            self.waste_codes or self.bsd_numbers or self.agrement_numbers
            or self.years or self.quantities
        )


@dataclass(frozen=True)
class ToolSelection:
    """Selected tool and parameters."""
    tool: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # "hermes+ai_router" | "hermes" | "ai_router" | "none"


@dataclass
class OrchestratorResult:
    """Complete result from the orchestrator."""
    success: bool
    message: str
    data: Any = None
    followups: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data or {},
            "followups": self.followups,
            "meta": self.meta,
        }


# ── System Prompts ────────────────────────────────────────────────────

_HERMES_GATE_PROMPT = (
    "You are the intent analyzer for RECUP-DZ, a waste management platform in Algeria.\n"
    "Given the user message AND conversation history, determine if a business tool is needed.\n\n"
    "AVAILABLE TOOLS:\n{tools_desc}\n\n"
    "RULES:\n"
    "1. Return ONLY a JSON object — no commentary, no markdown.\n"
    "2. Format:\n"
    '   Tool needed: {{"tool_needed": true, "tool": "tool_name", "action": "action_name", "parameters": {{...}}}}\n'
    '   No tool needed: {{"tool_needed": false, "tool": "none"}}\n'
    '   Greeting: {{"tool_needed": false, "tool": "greeting"}}\n'
    "3. For greetings (bonjour, hello, salut, etc.) → tool: greeting\n"
    "4. For general knowledge questions with no business data → tool: none\n"
    "5. For questions about BSD, nomenclature, waste, declarations, inspections,\n"
    "   recuperateurs, transporters, producers, partners, statistics, regulations,\n"
    "   archives, traceability, notifications, dashboards, permissions, administrations → tool_needed: true\n"
    "6. Use ONLY exact tool names and action values listed above.\n"
    "7. Do NOT invent parameter names.\n"
    "8. If unsure whether a tool is needed, prefer tool_needed: true.\n"
    "9. Consider conversation history for context (e.g., follow-up questions).\n"
)

_RESPONSE_PROMPT = (
    "You are the AI Agent of RECUP-DZ, expert in waste management in Algeria.\n"
    "The user asked a question. A business tool was executed and returned the following structured JSON.\n"
    "Generate a clear, professional, natural-language response in the SAME LANGUAGE as the user's message.\n\n"
    "CRITICAL RULES:\n"
    "1. Use ONLY the data from the tool result — NEVER invent information.\n"
    "2. Be concise but informative.\n"
    "3. Format with markdown when appropriate (bold, lists).\n"
    "4. If the tool returned an error or empty results, explain it politely and suggest alternatives.\n"
    "5. Never reveal internal JSON, tool names, or system details to the user.\n"
    "6. If numerical data is present, present it clearly.\n"
)

_FOLLOWUP_PROMPT = (
    "You are the AI Agent of RECUP-DZ, waste management expert.\n"
    "Based on the user's question and the response just given, suggest 2-3 relevant follow-up questions\n"
    "the user might want to ask next. Return ONLY a JSON array of strings.\n\n"
    "RULES:\n"
    "1. Return ONLY a JSON array — no commentary.\n"
    "2. Each follow-up must be a natural question in the SAME LANGUAGE as the user's message.\n"
    "3. Follow-ups must be relevant to the topic discussed.\n"
    "4. Do not repeat the original question.\n"
    "5. If no meaningful follow-up is possible, return an empty array: []\n\n"
    'Example: ["Quels sont les déchets dangereux dans cette catégorie ?", "Quelle est la réglementation applicable ?"]\n'
)

_DIRECT_RESPONSE_PROMPT = (
    "You are the AI Agent of RECUP-DZ, expert in waste management in Algeria.\n"
    "Answer the user's question directly using your knowledge.\n"
    "Be concise, accurate, and practical.\n"
    "Answer in the SAME LANGUAGE as the user's message.\n"
    "IMPORTANT: Clearly state that this is from general knowledge, not from the database.\n"
)

_GREETING_SYSTEM_PROMPT = (
    "You are the friendly AI assistant of RECUP-DZ, a waste management "
    "platform in Algeria. Greet the user warmly and briefly explain "
    "what you can help with (waste management, BSD, nomenclature, "
    "regulations, producers, transporters, etc.).\n"
    "Be concise. Respond in the SAME LANGUAGE as the user's message."
)

_GREETING_FALLBACK = (
    "Bonjour ! Je suis l'assistant IA de RECUP-DZ. "
    "Je peux vous aider avec la gestion des déchets, "
    "les BSD, la nomenclature, les réglementations.\n\n"
    "Comment puis-je vous aider ?"
)


# ── Agent Orchestrator ────────────────────────────────────────────────


class AgentOrchestrator:
    """
    Production-ready orchestrator: Hermes-first workflow.

    Flow:
        User → Hermes (tool needed?) → AI Router (fast match) → Tool → Repo → DB → Hermes (response)

    Usage:
        orchestrator = AgentOrchestrator(container)
        result = orchestrator.orchestrate(
            message="Quels sont les déchets dangereux ?",
            user_id="123",
            conversation_id="conv_abc",
        )
        print(result.to_dict())
    """

    def __init__(self, container: Any) -> None:
        self._c = container
        self._ai_router_instance = None

    # ==================================================================
    # Public API
    # ==================================================================

    def orchestrate(
        self,
        message: str,
        user_id: str = "",
        conversation_id: str = "",
        contexte_supp: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the Hermes-first workflow.

        Steps:
            1. Receive message + start trace + cache check
            2. Load conversation history
            3. Hermes gate — does the user need a business tool?
            4. AI Router — fast deterministic tool matching (if tool needed)
            5. Entity extraction
            6. Tool execution → structured JSON
            7. Hermes generates final response + follow-ups
            8. Memory storage

        Returns: {"success", "message", "data", "meta", "followups"}
        """
        request_id = uuid.uuid4().hex[:12]
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex[:8]}"
        start = time.monotonic()
        state = WorkflowState.RECEIVED
        trace_id = ""

        try:
            # ── Step 1: Receive + trace + cache ───────────────────────
            root_span = self._c.tracer.start_trace(
                f"orchestrate:{request_id}",
                user_id=user_id,
                message=message[:100],
            )
            trace_id = root_span.trace_id

            from apps.ai_assistant.infrastructure.audit.audit import AuditAction
            self._c.audit.log_simple(
                action=AuditAction.CHAT,
                user_id=user_id,
                resource_type="message",
                resource_id=request_id,
                details={"message": message[:200], "conversation_id": conversation_id},
            )

            cache_key = self._c.cache.make_key("orchestrate", message, user_id)
            cached = self._c.cache.get(cache_key)
            if cached:
                self._c.metrics.inc_counter("ai.orchestrator.cache.hit")
                elapsed = (time.monotonic() - start) * 1000
                self._c.tracer.finish_trace(trace_id)
                return self._build_response(
                    success=True,
                    message=cached["message"],
                    data=cached.get("data", {}),
                    followups=cached.get("followups", []),
                    meta={
                        "request_id": request_id,
                        "cached": True,
                        "elapsed_ms": round(elapsed, 1),
                        "trace_id": trace_id,
                        "workflow_state": WorkflowState.COMPLETED.value,
                    },
                )
            self._c.metrics.inc_counter("ai.orchestrator.cache.miss")

            # ── Hermes availability guard ──────────────────────────────
            hermes_up = self._hermes_available()
            if not hermes_up:
                logger.warning("Hermes/Ollama is unreachable — using AI Router only")
                self._c.metrics.inc_counter("ai.orchestrator.hermes.unavailable")

            # ── Step 2: Conversation Management ───────────────────────
            span = self._c.tracer.start_span(trace_id, "2_conversation_management")
            conversation_history = self._load_conversation(
                conversation_id, user_id, message,
            )
            ctx = self._build_context(
                message, conversation_id, user_id, contexte_supp,
            )
            state = WorkflowState.CONVERSATION_LOADED
            self._c.tracer.finish_span(span)

            # ── Step 3: Hermes Gate — tool needed? ────────────────────
            span = self._c.tracer.start_span(trace_id, "3_hermes_gate")
            hermes_decision = self._hermes_gate(ctx, message, conversation_history, hermes_up)
            state = WorkflowState.HERMES_GATE
            self._c.tracer.finish_span(span)

            # ── Step 4: AI Router refinement (if tool needed) ─────────
            span = self._c.tracer.start_span(trace_id, "4_ai_router_refinement")
            tool_selection = self._refine_tool_selection(
                hermes_decision, message, hermes_up,
            )
            state = WorkflowState.AI_ROUTER_REFINED
            self._c.tracer.finish_span(span)

            tool_name = tool_selection.tool
            action = tool_selection.action
            parameters = tool_selection.parameters
            selection_source = tool_selection.source

            # ── Step 5: Entity Extraction ─────────────────────────────
            span = self._c.tracer.start_span(trace_id, "5_entity_extraction")
            entities = self._extract_entities(message)
            state = WorkflowState.ENTITIES_EXTRACTED
            self._c.tracer.finish_span(span)

            # ── Step 6: Tool Execution ────────────────────────────────
            span = self._c.tracer.start_span(trace_id, "6_tool_execution")
            if tool_name in ("none", "greeting"):
                tool_result_data = None
                tool_results: List[ToolResult] = []
            else:
                tool_results = self._execute_tool(tool_name, parameters, ctx, message)
                tool_result_data = tool_results[0].data if tool_results else None
            state = WorkflowState.TOOL_EXECUTED
            self._c.tracer.finish_span(span)

            # ── Anti-hallucination guard ──────────────────────────────
            self._validate_tool_data(tool_name, tool_result_data, message)

            # ── Step 7a: Hermes generates response ────────────────────
            span = self._c.tracer.start_span(trace_id, "7a_response_generation")
            response_text = self._generate_response(
                message=message,
                tool_name=tool_name,
                tool_result=tool_result_data,
                context=ctx,
                conversation_history=conversation_history,
                hermes_up=hermes_up,
            )
            state = WorkflowState.RESPONSE_GENERATED
            self._c.tracer.finish_span(span)

            # ── Step 7b: Follow-up Generation ─────────────────────────
            span = self._c.tracer.start_span(trace_id, "7b_followup_generation")
            followups = self._generate_followups(
                message=message,
                response=response_text,
                tool_name=tool_name,
                tool_result=tool_result_data,
                conversation_history=conversation_history,
                hermes_up=hermes_up,
            )
            state = WorkflowState.FOLLOWUPS_GENERATED
            self._c.tracer.finish_span(span)

            # ── Step 7c: Memory Storage ───────────────────────────────
            span = self._c.tracer.start_span(trace_id, "7c_memory_storage")
            self._store_memory(conversation_id, message, response_text, {
                "tool": tool_name,
                "tool_needed": hermes_decision.tool_needed,
                "entities": entities.to_dict(),
            })
            state = WorkflowState.MEMORY_STORED
            self._c.tracer.finish_span(span)

            # ── Merge data + cache + finalize ─────────────────────────
            response_data = self._merge_tool_data(tool_results)

            self._c.cache.set(cache_key, {
                "message": response_text,
                "data": response_data,
                "followups": followups,
            }, ttl=300)

            elapsed = (time.monotonic() - start) * 1000
            state = WorkflowState.COMPLETED

            self._c.metrics.record_request("ai.orchestrate", "POST", 200, elapsed)
            self._c.metrics.inc_counter("ai.orchestrator.responses.total")
            self._c.tracer.finish_trace(trace_id)

            return self._build_response(
                success=True,
                message=response_text,
                data=response_data,
                followups=followups,
                meta={
                    "request_id": request_id,
                    "tool_needed": hermes_decision.tool_needed,
                    "tool_used": tool_name if tool_name not in ("none", "greeting") else None,
                    "tool_action": action,
                    "selection_source": selection_source,
                    "entities": entities.to_dict(),
                    "hermes_confidence": hermes_decision.confidence,
                    "cached": False,
                    "elapsed_ms": round(elapsed, 1),
                    "trace_id": trace_id,
                    "workflow_state": state.value,
                },
            )

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            self._c.metrics.inc_counter("ai.orchestrator.errors.total")
            from apps.ai_assistant.infrastructure.audit.audit import AuditAction
            self._c.audit.log_simple(
                action=AuditAction.ERROR,
                user_id=user_id,
                resource_type="orchestrator",
                resource_id=request_id,
                error_message=str(exc),
            )
            if trace_id:
                self._c.tracer.finish_trace(trace_id)
            logger.exception("Orchestrator error: %s", exc)
            return self._build_response(
                success=False,
                message="Une erreur est survenue. Veuillez réessayer.",
                followups=[],
                meta={
                    "request_id": request_id,
                    "error": str(exc),
                    "elapsed_ms": round(elapsed, 1),
                    "trace_id": trace_id,
                    "workflow_state": WorkflowState.ERROR.value,
                },
            )

    # ==================================================================
    # Step 2: Conversation Management
    # ==================================================================

    def _load_conversation(
        self,
        conversation_id: str,
        user_id: str,
        current_message: str,
    ) -> List[Dict[str, str]]:
        """
        Load conversation history from memory service.

        Returns list of {"role": "user"|"assistant", "content": "..."} dicts.
        If a conversation summary exists, it is prepended as a system message
        so the LLM has context about earlier turns.

        No Django model access — uses memory manager only.
        """
        # Get summary context if available
        summary = self._c.memory.get_tracker_summary(conversation_id)

        history = self._c.memory.get_conversation_history(conversation_id)
        result: List[Dict[str, str]] = []

        # Prepend summary as system context
        if summary:
            result.append({
                "role": "system",
                "content": summary.to_context_string(),
            })

        for msg in history:
            role = "user" if msg.role == Role.USER else "assistant"
            result.append({"role": role, "content": msg.content})
        return result

    def _build_context(
        self,
        message: str,
        conversation_id: str,
        user_id: str,
        contexte_supp: Optional[Dict[str, Any]] = None,
    ) -> Context:
        """Build the context object for downstream steps."""
        extra = dict(contexte_supp or {})
        extra.pop("conversation_id", None)
        extra.pop("user_id", None)
        return self._c.context_builder.build(
            message,
            conversation_id=conversation_id,
            user_id=user_id,
            **extra,
        )

    # ==================================================================
    # Step 3: Hermes Gate — the single decision point
    # ==================================================================

    def _hermes_gate(
        self,
        ctx: Context,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        hermes_up: bool = True,
    ) -> HermesDecision:
        """
        Hermes determines if a business tool is needed.

        This is the SINGLE decision gate. Hermes sees:
        - System prompt with all available tools
        - Conversation history (trimmed)
        - User message

        Returns HermesDecision with tool_needed=True/False.
        If Hermes is down, falls back to AI Router directly.
        """
        if not hermes_up:
            # Hermes down — try AI Router as fallback gate
            ai_result = self._try_ai_router(message)
            if ai_result is not None:
                return HermesDecision(
                    tool_needed=True,
                    tool=ai_result.get("tool", "none"),
                    action=ai_result.get("action", ""),
                    parameters=ai_result.get("parameters", {}),
                    confidence=ai_result.get("confidence", 0.5),
                    reasoning="ai_router_fallback",
                )
            return HermesDecision(
                tool_needed=False, tool="none", confidence=0.0,
                reasoning="hermes_unavailable_no_ai_router_match",
            )

        # Build tools description for Hermes
        tools_desc = self._build_tools_description()

        system_prompt = _HERMES_GATE_PROMPT.format(tools_desc=tools_desc)
        history = self._trim_history(conversation_history, max_turns=10)

        try:
            raw = self._c.ollama.chat(
                message=message,
                history=history,
                system_prompt=system_prompt,
            )
            decision = self._parse_hermes_gate(raw)

            # Validate tool name exists in registry
            tool_name = decision.get("tool", "none")
            if tool_name not in ("none", "greeting") and tool_name not in self._c.tool_registry:
                logger.warning("Hermes chose unknown tool '%s' — treating as none", tool_name)
                return HermesDecision(
                    tool_needed=False, tool="none", confidence=0.3,
                    reasoning=f"unknown_tool:{tool_name}",
                )

            tool_needed = decision.get("tool_needed", False)
            if tool_name in ("none", "greeting"):
                tool_needed = False

            return HermesDecision(
                tool_needed=tool_needed,
                tool=tool_name,
                action=decision.get("action", ""),
                parameters=decision.get("parameters", {}),
                confidence=0.9 if tool_needed else 0.5,
                reasoning=decision.get("reasoning", ""),
            )

        except Exception as exc:
            logger.warning("Hermes gate failed: %s", exc)
            return HermesDecision(
                tool_needed=False, tool="none", confidence=0.0,
                reasoning=f"hermes_error:{exc}",
            )

    # ==================================================================
    # Step 4: AI Router Refinement
    # ==================================================================

    def _refine_tool_selection(
        self,
        hermes_decision: HermesDecision,
        message: str,
        hermes_up: bool,
    ) -> ToolSelection:
        """
        AI Router refines Hermes' decision with fast deterministic matching.

        Flow:
            - If Hermes said "no tool" → return none
            - If Hermes said "greeting" → return greeting
            - If Hermes said tool needed → AI Router validates/refines
            - If AI Router agrees → use AI Router's precise parameters
            - If AI Router doesn't match → trust Hermes' selection
        """
        # ── Hermes said no tool needed ────────────────────────────────
        if not hermes_decision.tool_needed:
            if hermes_decision.tool == "greeting":
                return ToolSelection(tool="greeting", action="", parameters={}, source="hermes")
            return ToolSelection(tool="none", action="", parameters={}, source="hermes")

        # ── Hermes said tool needed — AI Router refines ───────────────
        ai_result = self._try_ai_router(message)

        if ai_result is not None:
            ai_tool = ai_result.get("tool", "none")
            ai_action = ai_result.get("action", "")
            ai_params = ai_result.get("parameters", {})
            ai_conf = ai_result.get("confidence", 0.0)

            # AI Router matches same tool → use AI Router's precise parameters
            if ai_tool == hermes_decision.tool and ai_conf >= 0.5:
                params = {**ai_params}
                if ai_action and "action" not in params:
                    params["action"] = ai_action
                logger.info(
                    "AI Router refined Hermes: %s.%s (conf=%.2f)",
                    ai_tool, ai_action, ai_conf,
                )
                self._c.metrics.inc_counter("ai.refinement.ai_router_match")
                return ToolSelection(
                    tool=ai_tool,
                    action=ai_action,
                    parameters=params,
                    source="hermes+ai_router",
                )

            # AI Router matches different tool with high confidence → use AI Router
            if ai_conf >= 0.7:
                params = {**ai_params}
                if ai_action and "action" not in params:
                    params["action"] = ai_action
                logger.info(
                    "AI Router overrode Hermes: %s.%s vs Hermes %s (conf=%.2f)",
                    ai_tool, ai_action, hermes_decision.tool, ai_conf,
                )
                self._c.metrics.inc_counter("ai.refinement.ai_router_override")
                return ToolSelection(
                    tool=ai_tool,
                    action=ai_action,
                    parameters=params,
                    source="ai_router",
                )

            # AI Router low confidence or no match → trust Hermes
            self._c.metrics.inc_counter("ai.refinement.hermes_trusted")
            return ToolSelection(
                tool=hermes_decision.tool,
                action=hermes_decision.action,
                parameters={**hermes_decision.parameters},
                source="hermes",
            )

        # ── AI Router returned nothing → trust Hermes ─────────────────
        self._c.metrics.inc_counter("ai.refinement.hermes_trusted_no_router")
        return ToolSelection(
            tool=hermes_decision.tool,
            action=hermes_decision.action,
            parameters={**hermes_decision.parameters},
            source="hermes",
        )

    # ==================================================================
    # Step 5: Entity Extraction
    # ==================================================================

    def _extract_entities(self, message: str) -> EntityExtraction:
        """
        Extract entities from the user message.

        Uses regex patterns for structured data (waste codes, BSD numbers, etc.)
        No LLM call — deterministic extraction.
        """
        import re

        waste_codes = list(set(re.findall(r"\b(\d{1,2}\.\d{2}\.\d{2})\b", message)))
        bsd_numbers = list(set(re.findall(
            r"\b(BSD[- ]?\d{4,})\b", message, re.IGNORECASE,
        )))
        agrement_numbers = list(set(re.findall(
            r"\b(agré?ment[- ]?\d{3,})\b", message, re.IGNORECASE,
        )))
        years = list(set(re.findall(r"\b(20[0-9]{2})\b", message)))
        quantities = list(set(re.findall(
            r"\b(\d+(?:[.,]\d+)?\s*(?:tonnes?|kg|tons?|kilos?))\b",
            message, re.IGNORECASE,
        )))
        emails = list(set(re.findall(
            r"\b([\w.+-]+@[\w-]+\.[\w.-]+)\b", message,
        )))
        phones = list(set(re.findall(r"\b(\+?\d{10,13})\b", message)))
        percentages = list(set(re.findall(r"\b(\d+(?:[.,]\d+)?\s*%)\b", message)))

        raw_entities = []
        for code in waste_codes:
            raw_entities.append({"type": "waste_code", "value": code})
        for bsd in bsd_numbers:
            raw_entities.append({"type": "bsd_number", "value": bsd})

        return EntityExtraction(
            waste_codes=waste_codes,
            bsd_numbers=bsd_numbers,
            agrement_numbers=agrement_numbers,
            years=years,
            quantities=quantities,
            emails=emails,
            phones=phones,
            percentages=percentages,
            raw_entities=raw_entities,
        )

    # ==================================================================
    # Step 6: Tool Execution
    # ==================================================================

    def _execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        ctx: Context,
        user_message: str,
    ) -> List[ToolResult]:
        """Execute the selected tool via the executor adapter."""
        plan = ExecutionPlan(
            steps=[TaskStep(
                id="step_1",
                tool_name=tool_name,
                description=f"Execute {tool_name}",
                parameters=parameters,
            )],
            metadata={"source": "orchestrator"},
        )
        results = self._c.executor.execute(plan, ctx)

        if all(not r.success for r in results) and results:
            fallback_text = self._fallback_format(results)
            return [ToolResult(
                tool_name="fallback",
                success=True,
                data={"fallback_message": fallback_text},
            )]
        return results

    # ── Anti-hallucination guard ───────────────────────────────────────

    def _validate_tool_data(
        self,
        tool_name: str,
        tool_result: Optional[Any],
        user_message: str,
    ) -> None:
        """Validate tool data for observability (does NOT block execution)."""
        if tool_name in ("none", "greeting"):
            return

        if tool_result is None:
            logger.warning(
                "Anti-hallucination: tool '%s' returned None data for message '%s'",
                tool_name, user_message[:100],
            )
            return

        if isinstance(tool_result, dict):
            if not tool_result:
                logger.warning(
                    "Anti-hallucination: tool '%s' returned empty dict for message '%s'",
                    tool_name, user_message[:100],
                )
            if tool_result.get("error"):
                logger.warning(
                    "Anti-hallucination: tool '%s' returned error: %s",
                    tool_name, tool_result.get("error"),
                )

    # ==================================================================
    # Step 7a: Response Generation (Hermes)
    # ==================================================================

    def _generate_response(
        self,
        message: str,
        tool_name: str,
        tool_result: Optional[Any],
        context: Context,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        hermes_up: bool = True,
    ) -> str:
        """Generate the professional response via Hermes."""
        if tool_name == "greeting":
            system_prompt = _GREETING_SYSTEM_PROMPT
            tool_context = ""
        elif tool_name == "none":
            system_prompt = _DIRECT_RESPONSE_PROMPT
            tool_context = ""
        elif tool_result:
            system_prompt = _RESPONSE_PROMPT
            result_json = json.dumps(tool_result, ensure_ascii=False, default=str)
            if len(result_json) > 3000:
                result_json = result_json[:3000] + '... [truncated]'
            tool_context = f"\n\nTOOL RESULT ({tool_name}):\n{result_json}"
        else:
            system_prompt = _DIRECT_RESPONSE_PROMPT
            tool_context = ""

        history = self._trim_history(conversation_history, max_turns=10)

        if not hermes_up:
            if tool_name == "greeting":
                return _GREETING_FALLBACK
            if tool_result:
                return self._fallback_format([ToolResult(
                    tool_name=tool_name, success=True, data=tool_result,
                )])
            return "Le service IA est temporairement indisponible. Veuillez réessayer."

        try:
            reply = self._c.ollama.chat(
                message=message,
                history=history,
                system_prompt=system_prompt + tool_context,
            )
            if reply and reply.strip():
                return reply.strip()
        except Exception as exc:
            logger.warning("Response generation failed: %s", exc)

        # Fallback: deterministic answer
        if tool_name == "greeting":
            return _GREETING_FALLBACK
        if tool_result:
            return self._fallback_format([ToolResult(
                tool_name=tool_name, success=True, data=tool_result,
            )])
        return "Je suis désolé, une erreur est survenue. Veuillez réessayer."

    # ==================================================================
    # Step 7b: Follow-up Generation
    # ==================================================================

    def _generate_followups(
        self,
        message: str,
        response: str,
        tool_name: str,
        tool_result: Optional[Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        hermes_up: bool = True,
    ) -> List[str]:
        """Generate contextual follow-up questions."""
        if tool_name == "greeting":
            return [
                "Qu'est-ce qu'un BSD ?",
                "Rechercher un code nomenclature",
                "Quels sont les agréments expirés ?",
            ]

        if tool_name == "none":
            return []

        if not hermes_up:
            return []

        try:
            followup_context = f"USER QUESTION: {message}\n\nAGENT RESPONSE: {response[:500]}"
            if tool_result:
                result_summary = json.dumps(tool_result, ensure_ascii=False, default=str)[:500]
                followup_context += f"\n\nTOOL DATA SUMMARY: {result_summary}"

            history = self._trim_history(conversation_history, max_turns=6)

            raw = self._c.ollama.chat(
                message=followup_context,
                history=history,
                system_prompt=_FOLLOWUP_PROMPT,
            )

            if raw:
                raw = raw.strip()
                if raw.startswith("```"):
                    lines = raw.split("\n")
                    raw = "\n".join(l for l in lines if not l.strip().startswith("```"))
                start = raw.find("[")
                end = raw.rfind("]") + 1
                if start != -1 and end > start:
                    followups = json.loads(raw[start:end])
                    if isinstance(followups, list):
                        return [str(f) for f in followups[:3] if f]

        except Exception as exc:
            logger.debug("Follow-up generation failed: %s", exc)

        return []

    # ==================================================================
    # Step 7c: Memory Storage
    # ==================================================================

    def _store_memory(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store conversation in memory (short-term + structured tracker + optional long-term).

        Stores to both:
        1. Short-term memory (Message objects for LLM context window)
        2. ConversationTracker (structured turns with intent, entities, tool history)
        3. Long-term memory (if enabled)
        """
        meta = metadata or {}

        # ── Short-term (for LLM context window) ───────────────────────
        self._c.memory.store_user_message(conversation_id, user_message, meta)
        self._c.memory.store_assistant_message(conversation_id, assistant_message, meta)

        # ── Structured tracker (intent, entities, tool history) ────────
        self._c.memory.store_turn(
            conversation_id,
            role="user",
            content=user_message,
            intent=meta.get("tool", ""),
            entities=meta.get("entities", {}),
            tool_used=meta.get("tool"),
            tool_action=meta.get("tool_action", ""),
            tool_needed=meta.get("tool_needed", False),
            hermes_confidence=meta.get("hermes_confidence", 0.0),
            selection_source=meta.get("selection_source", ""),
        )
        self._c.memory.store_turn(
            conversation_id,
            role="assistant",
            content=assistant_message,
            intent=meta.get("tool", ""),
            tool_used=meta.get("tool"),
            tool_action=meta.get("tool_action", ""),
        )

        # ── Long-term memory (if enabled) ─────────────────────────────
        if self._c.memory.long_term:
            key = f"conv_{conversation_id}_{uuid.uuid4().hex[:6]}"
            content = f"User: {user_message[:200]}\nAssistant: {assistant_message[:200]}"
            self._c.memory.store_long_term(key, content, meta)

    # ==================================================================
    # AI Router Integration
    # ==================================================================

    def _try_ai_router(self, message: str) -> Optional[Dict[str, Any]]:
        """Try the deterministic AI Router. Returns None on no match."""
        try:
            from apps.ai_assistant.enterprise.ai_router import AIRouter
            if self._ai_router_instance is None:
                self._ai_router_instance = AIRouter()
            result = self._ai_router_instance.route(message)
            if result is not None:
                return result.to_dict()
        except Exception as exc:
            logger.warning("AI Router failed: %s", exc)
        return None

    # ==================================================================
    # Helpers
    # ==================================================================

    def _build_tools_description(self) -> str:
        """Build a compact tools description for the Hermes gate prompt."""
        lines = []
        for t in self._c.tool_registry:
            schema = getattr(t, 'parameter_schema', None)
            action_descs = getattr(t, 'action_descriptions', {})
            params_str = ""
            if schema and hasattr(schema, 'fields'):
                params_str = " | params: " + ", ".join(
                    f"{f.name}({'required' if f.required else 'optional'}"
                    + (f", enum={f.enum}" if f.enum else "")
                    + ")"
                    for f in schema.fields
                )
            actions_str = ""
            if action_descs:
                actions_str = "\n    Actions:\n" + "\n".join(
                    f"      - {a}: {d}" for a, d in action_descs.items()
                )
            lines.append(f"- {t.name}: {t.description}{params_str}{actions_str}")
        return "\n".join(lines)

    def _parse_hermes_gate(self, raw: str) -> Dict[str, Any]:
        """Parse the JSON response from Hermes gate."""
        if not raw:
            return {"tool_needed": False, "tool": "none", "reasoning": "empty"}
        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end <= start:
                return {"tool_needed": False, "tool": "none", "reasoning": "no_json"}
            parsed = json.loads(text[start:end])
            return {
                "tool_needed": parsed.get("tool_needed", False),
                "tool": parsed.get("tool", "none"),
                "action": parsed.get("action", ""),
                "parameters": parsed.get("parameters", {}),
                "reasoning": parsed.get("reasoning", ""),
            }
        except json.JSONDecodeError:
            return {"tool_needed": False, "tool": "none", "reasoning": "json_error"}

    def _trim_history(
        self,
        history: Optional[List[Dict[str, str]]],
        max_turns: int = 10,
    ) -> List[Dict[str, str]]:
        """
        Trim conversation history to fit within Hermes context window.

        Keeps the most recent `max_turns` exchanges (user + assistant = 1 turn).
        """
        if not history:
            return []
        max_messages = max_turns * 2
        if len(history) <= max_messages:
            return history
        return history[-max_messages:]

    def _hermes_available(self) -> bool:
        """Check if Hermes/Ollama is reachable. Logs but does not raise."""
        try:
            return self._c.ollama.is_available()
        except Exception:
            return False

    def _merge_tool_data(self, results: List[ToolResult]) -> Any:
        """Merge multiple tool results into a single data dict."""
        if not results:
            return {}
        if len(results) == 1:
            return results[0].data if results[0].data else {}
        merged = {}
        for r in results:
            if r.data and isinstance(r.data, dict):
                merged.update(r.data)
        return merged

    def _fallback_format(self, results: List[ToolResult]) -> str:
        """Deterministic fallback formatting when LLM fails."""
        parts = []
        for r in results:
            if r.error:
                parts.append(f"Erreur: {r.error}")
            elif r.data:
                if isinstance(r.data, dict):
                    for k, v in r.data.items():
                        if isinstance(v, list):
                            parts.append(f"- **{k}**: {len(v)} élément(s)")
                        else:
                            parts.append(f"- **{k}**: {str(v)[:100]}")
                else:
                    parts.append(str(r.data)[:300])
        return "\n".join(parts) if parts else "Aucun résultat."

    def _build_response(
        self,
        success: bool,
        message: str,
        data: Any = None,
        followups: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the standard response envelope."""
        return {
            "success": success,
            "message": message,
            "data": data or {},
            "followups": followups or [],
            "meta": meta or {},
        }
