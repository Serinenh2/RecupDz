"""
AI Agent — Hermes-powered tool-calling orchestrator.

Pipeline:
    User → Hermes (chooses ONE tool) → Execute Tool → Repository → DB → Response

Hermes NEVER executes SQL. Hermes NEVER accesses Django Models.
Hermes only returns a JSON tool call. The Agent executes it.
"""

from __future__ import annotations

import json as _json
import logging
import time
from typing import Any, Dict, List, Optional

from apps.ai_assistant.services.ollama_service import (
    OllamaConnectionError,
    OllamaError,
    OllamaService,
    OllamaTimeoutError,
)
from apps.ai_assistant.intent_router import IntentRouter
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_executor import ToolExecutor
from apps.ai_assistant.tools.tool_registry import ToolRegistry
from apps.ai_assistant.tools.tool_result import ToolResultResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System Prompt — Hermes must choose ONE tool and return JSON
# ---------------------------------------------------------------------------

_AGENT_SYSTEM_PROMPT = """You are the AI Agent for RECUP-DZ, an Algerian waste management enterprise.

Your ONLY job is to analyze the user's request and choose the best tool to handle it.

RULES:
1. You MUST choose exactly ONE tool from the available tools list.
2. You MUST return a valid JSON object — nothing else, no markdown, no explanation.
3. You NEVER execute SQL queries. You NEVER access databases directly.
4. You ONLY choose which tool to call. The system executes the tool for you.
5. If no tool matches, choose "none" and explain why in the reason field.
6. Reply in the same language the user writes in (French, Arabic, or English).

OUTPUT FORMAT (strict JSON, no extra text):
{{"reason": "...", "tool": "tool_name", "action": "action_name", "parameters": {{"key": "value"}}}}

AVAILABLE TOOLS:
{tools_description}

EXAMPLES:
User: "Quels sont les déchets dangereux ?"
{{"reason": "User asks about dangerous waste", "tool": "waste_tool", "action": "dangerous", "parameters": {{}}}}

User: "Rechercher le code 15.01.06"
{{"reason": "User wants a specific waste code", "tool": "waste_tool", "action": "get_by_code", "parameters": {{"code": "15.01.06"}}}}

User: "Donne-moi les statistiques"
{{"reason": "User wants statistics", "tool": "statistiques_tool", "action": "status_summary", "parameters": {{}}}}

User: "Quelle est la loi 01-19 ?"
{{"reason": "User asks about regulation", "tool": "reglementation_tool", "action": "search", "parameters": {{"query": "loi 01-19"}}}}

User: "Bonjour"
{{"reason": "Greeting — no tool needed", "tool": "none", "action": "greeting", "parameters": {{}}}}
"""


# ---------------------------------------------------------------------------
# Response Formatter — turns tool results into natural language
# ---------------------------------------------------------------------------

_RESPONSE_SYSTEM_PROMPT = """You are the response formatter for RECUP-DZ's AI assistant.

You receive:
1. The user's original question
2. The raw data from a tool execution

Your job: format the data into a clear, concise, professional response.

RULES:
1. Reply in the same language as the user's question.
2. Be concise — no unnecessary text.
3. Use bullet points or numbered lists for clarity.
4. If the data is empty, say so honestly.
5. If the data contains an error, explain it simply.
6. Never invent information — only use the provided data.
"""


# ---------------------------------------------------------------------------
# AIAgent
# ---------------------------------------------------------------------------

class AIAgent:
    """
    Hermes-powered AI Agent.

    Pipeline:
        1. IntentRouter detects intent + entities (fast, rule-based)
        2. Hermes chooses ONE tool (LLM-powered, with context)
        3. Agent executes the tool via ToolExecutor
        4. Hermes formats the result into natural language
        5. Returns response

    Hermes NEVER executes SQL. Hermes NEVER accesses Django Models.
    """

    def __init__(
        self,
        ollama: Optional[OllamaService] = None,
        registry: Optional[ToolRegistry] = None,
        executor: Optional[ToolExecutor] = None,
    ) -> None:
        self._ollama = ollama or OllamaService()
        self._registry = registry or ToolRegistry()
        self._executor = executor or ToolExecutor(self._registry)
        self._intent_router = IntentRouter()
        self._tools_description = self._build_tools_description()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(
        self,
        message: str,
        conversation: Any = None,
        contexte_supp: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the full agent pipeline.

        Returns:
            {
                "success": True/False,
                "message": "natural language response",
                "data": {...},
                "tool_used": "tool_name or None",
                "intent": "detected intent",
                "confidence": 0.0-1.0,
                "elapsed_ms": 0
            }
        """
        start = time.monotonic()

        # 1. Quick intent detection (rule-based)
        intent_decision = self._intent_router.route(message)
        logger.info(
            "Intent: %s (%.0f%%), entities=%d",
            intent_decision.intent,
            intent_decision.confidence * 100,
            len(intent_decision.entities),
        )

        # 2. Greeting — no tool needed
        if intent_decision.intent == "greeting":
            return self._build_result(
                success=True,
                message=self._greeting_response(message),
                tool_used=None,
                intent=intent_decision.intent,
                confidence=intent_decision.confidence,
                elapsed_ms=(time.monotonic() - start) * 1000,
            )

        # 3. Hermes chooses a tool
        tool_call = self._select_tool(message, intent_decision)
        logger.info("Tool selected: %s.%s", tool_call.get("tool"), tool_call.get("action"))

        # 4. No tool — respond directly
        if tool_call.get("tool") == "none":
            response_text = self._respond_directly(message, tool_call.get("reason", ""))
            return self._build_result(
                success=True,
                message=response_text,
                tool_used=None,
                intent=intent_decision.intent,
                confidence=intent_decision.confidence,
                elapsed_ms=(time.monotonic() - start) * 1000,
            )

        # 5. Execute the tool
        tool_name = tool_call.get("tool", "")
        tool_action = tool_call.get("action", "")
        tool_params = tool_call.get("parameters", {})
        tool_params["action"] = tool_action

        ctx = self._build_context(conversation)
        result = self._executor.execute(tool_name, tool_params, ctx)

        # 6. Format the result into natural language
        response_text = self._format_response(message, result)

        return self._build_result(
            success=result.success,
            message=response_text,
            data=result.data,
            tool_used=tool_name,
            intent=intent_decision.intent,
            confidence=intent_decision.confidence,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    def is_available(self) -> bool:
        """Check if Hermes is reachable."""
        return self._ollama.is_available()

    def health(self) -> Dict[str, Any]:
        """Detailed health check."""
        return {
            "ollama": self._ollama.health(),
            "tools_registered": self._registry.list_names(),
            "tool_count": len(self._registry),
        }

    # ------------------------------------------------------------------
    # Step 1: Tool Selection (Hermes)
    # ------------------------------------------------------------------

    def _select_tool(
        self, message: str, intent_decision: Any
    ) -> Dict[str, Any]:
        """Ask Hermes to choose ONE tool based on the message and intent."""
        if not self._ollama.is_available():
            logger.warning("Ollama unavailable — using intent router fallback")
            return self._fallback_tool_selection(intent_decision)

        system_prompt = _AGENT_SYSTEM_PROMPT.format(
            tools_description=self._tools_description,
        )

        # Add intent hint to the message
        enhanced_message = (
            f"[Detected intent: {intent_decision.intent} "
            f"(confidence: {intent_decision.confidence:.0%})]\n"
            f"[Extracted entities: {[e.to_dict() for e in intent_decision.entities]}]\n\n"
            f"User message: {message}"
        )

        try:
            raw = self._ollama.chat(
                message=enhanced_message,
                history=[],
                system_prompt=system_prompt,
            )
            return self._parse_tool_call(raw)

        except (OllamaConnectionError, OllamaTimeoutError, OllamaError) as exc:
            logger.warning("Hermes tool selection failed: %s — using fallback", exc)
            return self._fallback_tool_selection(intent_decision)

    def _parse_tool_call(self, raw: str) -> Dict[str, Any]:
        """Parse Hermes's JSON response into a tool call dict."""
        if not raw:
            return {"tool": "none", "action": "", "parameters": {}, "reason": "Empty response"}

        # Extract JSON from response
        try:
            text = raw.strip()
            # Remove markdown code fences
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end <= start:
                logger.warning("No JSON in Hermes response: %s", text[:200])
                return {"tool": "none", "action": "", "parameters": {}, "reason": "No JSON found"}

            parsed = _json.loads(text[start:end])
            return {
                "tool": parsed.get("tool", "none"),
                "action": parsed.get("action", ""),
                "parameters": parsed.get("parameters", {}),
                "reason": parsed.get("reason", ""),
            }

        except _json.JSONDecodeError as exc:
            logger.warning("Invalid JSON from Hermes: %s", exc)
            return {"tool": "none", "action": "", "parameters": {}, "reason": f"JSON parse error: {exc}"}

    def _fallback_tool_selection(self, intent_decision: Any) -> Dict[str, Any]:
        """Fallback: use IntentRouter's tool hint when Hermes is unavailable."""
        tool = intent_decision.tool
        if not tool:
            return {"tool": "none", "action": "", "parameters": {}, "reason": "No tool matched"}

        # Map intent to action
        action_map = {
            "waste_tool": "search",
            "declaration_tool": "list",
            "partner_tool": "list",
            "company_tool": "list",
            "statistics_tool": "status_summary",
            "report_tool": "waste_report",
            "regulation_tool": "search",
        }

        params = {}
        for entity in intent_decision.entities:
            if entity.type == "waste_code":
                tool = "waste_tool"
                action = "get_by_code"
                params = {"code": entity.value}
                break
            elif entity.type == "bsd_number":
                tool = "declaration_tool"
                action = "search"
                params = {"query": entity.value}
                break

        action = action_map.get(tool, "list")

        return {
            "tool": tool,
            "action": action,
            "parameters": params,
            "reason": f"Fallback from intent router: {intent_decision.intent}",
        }

    # ------------------------------------------------------------------
    # Step 2: Response Formatting (Hermes)
    # ------------------------------------------------------------------

    def _format_response(self, message: str, result: ToolResultResponse) -> str:
        """Format tool result into natural language using Hermes."""
        if not self._ollama.is_available():
            return self._format_response_deterministic(message, result)

        system_prompt = _RESPONSE_SYSTEM_PROMPT
        user_prompt = (
            f"User question: {message}\n\n"
            f"Tool result:\n"
            f"Success: {result.success}\n"
            f"Message: {result.message}\n"
            f"Data: {_json.dumps(result.data, ensure_ascii=False, default=str)[:2000]}"
        )

        try:
            reply = self._ollama.chat(
                message=user_prompt,
                history=[],
                system_prompt=system_prompt,
            )
            if reply and reply.strip():
                return reply.strip()

        except Exception as exc:
            logger.warning("Hermes formatting failed: %s — using deterministic", exc)

        return self._format_response_deterministic(message, result)

    def _format_response_deterministic(self, message: str, result: ToolResultResponse) -> str:
        """Fallback: format response without LLM."""
        if not result.success:
            return f"Erreur: {result.message}"

        if not result.data:
            return result.message or "Aucune donnée disponible."

        # Simple data formatting
        data = result.data
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if isinstance(value, list):
                    lines.append(f"**{key}**: {len(value)} élément(s)")
                elif isinstance(value, (int, float)):
                    lines.append(f"**{key}**: {value}")
                else:
                    lines.append(f"**{key}**: {str(value)[:100]}")
            return "\n".join(lines) if lines else result.message

        return str(data)[:500]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_tools_description(self) -> str:
        """Build a description of all available tools for the system prompt."""
        lines = []
        for tool in self._registry:
            schema = tool.to_schema()
            params = schema.get("parameters", {}).get("properties", {})
            actions = params.get("action", {}).get("enum", [])
            lines.append(f"- {tool.name}: {tool.description}")
            if actions:
                lines.append(f"  Actions: {', '.join(actions)}")
        return "\n".join(lines) if lines else "No tools available."

    def _build_context(self, conversation: Any = None) -> ToolContext:
        """Build a ToolContext from the conversation."""
        if conversation is None:
            return ToolContext()

        user_id = ""
        user_roles = []
        if hasattr(conversation, "user") and conversation.user:
            user_id = str(conversation.user.pk)
            if hasattr(conversation.user, "role"):
                user_roles = [conversation.user.role]

        return ToolContext.create(
            user_id=user_id,
            conversation_id=str(getattr(conversation, "pk", "")),
            user_roles=user_roles,
        )

    def _greeting_response(self, message: str) -> str:
        """Generate a greeting response."""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["bonjour", "bonsoir", "salut", "hello", "hi"]):
            return (
                "Bonjour ! Je suis l'assistant IA de RECUP-DZ. "
                "Je peux vous aider avec la gestion des déchets, "
                "les BSD, la nomenclature, les réglementations, et plus encore.\n\n"
                "Comment puis-je vous aider ?"
            )
        if any(w in msg_lower for w in ["مرحبا", "سلام", "السلام", "أهلا"]):
            return (
                "مرحباً ! أنا مساعد الذكاء الاصطناعي لشركة RECUP-DZ. "
                "يمكنني مساعدتك في إدارة النفايات والبوليصات والتصنيفات واللوائح.\n\n"
                "كيف يمكنني مساعدتك اليوم؟"
            )
        return (
            "Hello! I'm the RECUP-DZ AI assistant. "
            "I can help with waste management, BSD, nomenclature, regulations, and more.\n\n"
            "How can I help you?"
        )

    def _respond_directly(self, message: str, reason: str) -> str:
        """Generate a direct response when no tool is needed."""
        if not self._ollama.is_available():
            return (
                "Je suis l'assistant RECUP-DZ. Je peux vous aider avec :\n"
                "- La nomenclature des déchets\n"
                "- Les BSD (Bordereaux de Suivi)\n"
                "- Les réglementations\n"
                "- Les statistiques\n\n"
                "Posez-moi une question spécifique !"
            )

        try:
            reply = self._ollama.chat(
                message=message,
                history=[],
                system_prompt=(
                    "Tu es l'assistant RECUP-DZ. Réponds de manière concise et professionnelle. "
                    "Si la question nécessite une donnée spécifique, indique que vous pouvez "
                    "rechercher dans les outils disponibles."
                ),
            )
            return reply or "Je ne peux pas répondre à cette question pour le moment."
        except Exception:
            return "Je ne peux pas répondre pour le moment. Veuillez réessayer."

    def _build_result(
        self,
        success: bool,
        message: str,
        data: Any = None,
        tool_used: Optional[str] = None,
        intent: str = "",
        confidence: float = 0.0,
        elapsed_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """Build the standard response dict."""
        return {
            "success": success,
            "message": message,
            "data": data or {},
            "tool_used": tool_used,
            "intent": intent,
            "confidence": round(confidence, 2),
            "elapsed_ms": round(elapsed_ms, 1),
        }
