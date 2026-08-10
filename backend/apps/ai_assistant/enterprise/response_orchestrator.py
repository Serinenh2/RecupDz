"""
Response Orchestrator — generates the final AI response from tool results, knowledge, and memory.

Responsibilities:
    1. Receive tool results from ExecutionOrchestrator
    2. Receive knowledge context from KnowledgeSearchEngine
    3. Receive conversation history from ConversationOrchestrator
    4. Call PromptBuilder to assemble the prompt
    5. Call Hermes (Ollama) to generate the response text
    6. Validate the response (quality, hallucination markers, internal leaks)
    7. Generate follow-up questions
    8. Return the final structured response

Architecture:
    ResponseOrchestrator is a stateless pipeline component.
    It receives all inputs and returns a complete response.
    It NEVER accesses repositories or executes business tools.

    ExecutionOrchestrator ──results──► ResponseOrchestrator ──► ConversationOrchestrator

    ┌──────────────────────────────────────────────────┐
    │            ResponseOrchestrator                    │
    │                                                   │
    │  Tool Results ─┐                                  │
    │  Knowledge ────┼──► PromptBuilder ──► Hermes ──► Validate ──► Response
    │  History ──────┤                                  │
    │  Message ──────┘                                  │
    └──────────────────────────────────────────────────┘

Constraints:
    - Zero Django imports
    - Zero repository access
    - Zero business tool execution
    - All dependencies injected via constructor (DI)
    - Never re-raises exceptions — always returns safe fallback
    - French error messages throughout
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════

_RESPONSE_MAX_LENGTH = 4000
_FOLLOWUP_MAX_COUNT = 3
_HALLUCINATION_MARKERS = (
    "je ne sais pas",
    "i don't know",
    "je ne suis pas sûr",
    "i'm not sure",
    "hypothetically",
    "peut-être que",
    "il se pourrait que",
)


@dataclass(frozen=True)
class ResponseInput:
    """All inputs needed to generate a response.

    Aggregates tool results, knowledge, history, and user context
    into a single immutable input object.
    """

    message: str
    tool_results: Optional[Any] = None
    tool_name: str = ""
    knowledge_context: str = ""
    conversation_history: Optional[List[Dict[str, str]]] = None
    user_id: str = ""
    user_language: str = ""
    user_role: str = ""

    @property
    def has_tool_results(self) -> bool:
        return self.tool_results is not None

    @property
    def has_knowledge(self) -> bool:
        return bool(self.knowledge_context)

    @property
    def has_history(self) -> bool:
        return bool(self.conversation_history)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message[:100],
            "tool_name": self.tool_name,
            "has_tool_results": self.has_tool_results,
            "has_knowledge": self.has_knowledge,
            "has_history": self.has_history,
            "user_id": self.user_id,
        }


@dataclass(frozen=True)
class ResponseOutput:
    """Final structured response from the ResponseOrchestrator."""

    success: bool
    response_text: str
    followups: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "response_text": self.response_text,
            "followups": list(self.followups),
            "meta": dict(self.meta),
        }


# ══════════════════════════════════════════════════════════════════════
# Main orchestrator
# ══════════════════════════════════════════════════════════════════════


class ResponseOrchestrator:
    """Generates the final AI response from tool results, knowledge, and memory.

    Stateless pipeline component — each call to generate() is independent.
    NEVER accesses repositories or executes business tools.
    Never exposes Python exceptions — all errors return safe fallback results.
    """

    def __init__(
        self,
        *,
        container: Any = None,
        max_response_length: int = _RESPONSE_MAX_LENGTH,
        max_followups: int = _FOLLOWUP_MAX_COUNT,
    ) -> None:
        self._container = container
        self._max_response_length = max_response_length
        self._max_followups = max_followups

    # ------------------------------------------------------------------
    # Lazy-resolved dependencies (DI via container)
    # ------------------------------------------------------------------

    @property
    def _prompt_builder(self) -> Any:
        if self._container is None:
            return None
        try:
            return self._container.prompt_builder
        except Exception:
            return None

    @property
    def _llm(self) -> Any:
        """OllamaService — the LLM chat endpoint."""
        if self._container is None:
            return None
        try:
            return self._container.ollama
        except Exception:
            return None

    @property
    def _safety_layer(self) -> Any:
        if self._container is None:
            return None
        try:
            return self._container.safety_layer
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, input_data: ResponseInput) -> ResponseOutput:
        """Generate a complete response from tool results, knowledge, and memory.

        Steps:
            1. Build prompt via PromptBuilder
            2. Call Hermes (Ollama) to generate text
            3. Generate follow-up questions
            4. Validate response quality
            5. Return structured ResponseOutput

        Returns a ResponseOutput — never raises.
        """
        start = time.monotonic()

        try:
            # ── Stage 1: Build prompt ──────────────────────────────
            prompt_ctx = self._build_prompt(input_data)

            # ── Stage 2: Call LLM ──────────────────────────────────
            response_text = self._call_llm(input_data, prompt_ctx)

            # ── Stage 3: Generate follow-ups ───────────────────────
            followups = self._generate_followups(input_data)

            # ── Stage 4: Validate ──────────────────────────────────
            response_text = self._validate_response(response_text, input_data)

            # ── Stage 5: Assemble output ───────────────────────────
            elapsed = (time.monotonic() - start) * 1000
            return self._assemble_output(
                response_text, followups, input_data, elapsed,
            )

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.debug("ResponseOrchestrator.generate failed: %s", exc)
            return ResponseOutput(
                success=False,
                response_text=self._fallback_response(input_data),
                followups=[],
                meta={
                    "error": str(exc),
                    "elapsed_ms": round(elapsed, 1),
                    "fallback": True,
                },
            )

    def generate_with_trace(
        self, input_data: ResponseInput,
    ) -> tuple:
        """Same as generate() but also returns the PromptContext for debugging.

        Returns (ResponseOutput, Optional[PromptContext]).
        """
        prompt_ctx = None
        start = time.monotonic()

        try:
            prompt_ctx = self._build_prompt(input_data)
            response_text = self._call_llm(input_data, prompt_ctx)
            followups = self._generate_followups(input_data)
            response_text = self._validate_response(response_text, input_data)
            elapsed = (time.monotonic() - start) * 1000
            output = self._assemble_output(
                response_text, followups, input_data, elapsed,
            )
            return output, prompt_ctx

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.debug("ResponseOrchestrator.generate_with_trace failed: %s", exc)
            output = ResponseOutput(
                success=False,
                response_text=self._fallback_response(input_data),
                followups=[],
                meta={
                    "error": str(exc),
                    "elapsed_ms": round(elapsed, 1),
                    "fallback": True,
                },
            )
            return output, prompt_ctx

    # ------------------------------------------------------------------
    # Internal — Prompt building
    # ------------------------------------------------------------------

    def _build_prompt(self, input_data: ResponseInput) -> Any:
        """Call PromptBuilder to assemble the prompt context."""
        pb = self._prompt_builder
        if pb is None:
            return None
        try:
            return pb.build_response_prompt(
                message=input_data.message,
                tool_results=input_data.tool_results,
                tool_name=input_data.tool_name,
                company_knowledge=input_data.knowledge_context,
                conversation_history=input_data.conversation_history,
                user_language=input_data.user_language,
                user_role=input_data.user_role,
            )
        except Exception as exc:
            logger.debug("PromptBuilder.build_response_prompt failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal — LLM call
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        input_data: ResponseInput,
        prompt_ctx: Any,
    ) -> str:
        """Call Hermes via OllamaService.chat() to generate the response text.

        Returns the response string — falls back to deterministic format on failure.
        """
        llm = self._llm
        if llm is None or not self._llm_available(llm):
            logger.debug("LLM unavailable — using fallback")
            return self._deterministic_response(input_data)

        try:
            if prompt_ctx is not None:
                # PromptContext provides system_prompt and history
                system_prompt = prompt_ctx.system_prompt
                history = prompt_ctx.history
            else:
                system_prompt = self._fallback_system_prompt(input_data)
                history = input_data.conversation_history or []

            response = llm.chat(
                message=input_data.message,
                history=history,
                system_prompt=system_prompt,
            )
            if not response or not response.strip():
                return self._deterministic_response(input_data)
            return response.strip()

        except Exception as exc:
            logger.debug("LLM call failed: %s", exc)
            return self._deterministic_response(input_data)

    def _llm_available(self, llm: Any) -> bool:
        """Check if the LLM service is reachable."""
        try:
            return llm.is_available()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal — Follow-up generation
    # ------------------------------------------------------------------

    def _generate_followups(self, input_data: ResponseInput) -> List[str]:
        """Generate 2-3 contextual follow-up questions via LLM.

        Returns a list of follow-up strings — empty on failure.
        """
        if input_data.tool_name in ("greeting", ""):
            return self._greeting_followups(input_data)

        llm = self._llm
        if llm is None or not self._llm_available(llm):
            return []

        pb = self._prompt_builder
        if pb is None:
            return []

        try:
            # Use the response from the last generate() call
            # For follow-ups, we need the response text — use a placeholder
            # that the caller can override
            followup_ctx = pb.build_followup_prompt(
                message=input_data.message,
                response="",  # Will be overridden by caller if needed
                tool_results=input_data.tool_results,
                tool_name=input_data.tool_name,
                conversation_history=input_data.conversation_history,
                user_language=input_data.user_language,
            )

            raw = llm.chat(
                message=f"USER QUESTION: {input_data.message[:300]}\n\nGenerate 2-3 follow-up questions as a JSON array.",
                history=[],
                system_prompt=followup_ctx.system_prompt if followup_ctx else self._FOLLOWUP_SYSTEM_PROMPT,
            )
            return self._parse_followups(raw)

        except Exception as exc:
            logger.debug("Follow-up generation failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal — Validation
    # ------------------------------------------------------------------

    def _validate_response(
        self,
        text: str,
        input_data: ResponseInput,
    ) -> str:
        """Validate response quality and safety.

        Checks:
            1. Not empty
            2. Not too long
            3. No hallucination markers
            4. No internal data leaks (tool names, JSON)
            5. Output safety via AISafetyLayer
        """
        if not text:
            return self._fallback_response(input_data)

        # Truncate if too long
        if len(text) > self._max_response_length:
            text = text[:self._max_response_length] + "\n\n[Réponse tronquée]"

        # Check for hallucination markers (low-confidence hedging)
        text_lower = text.lower()
        for marker in _HALLUCINATION_MARKERS:
            if marker in text_lower:
                logger.debug("Hallucination marker detected: %s", marker)
                break

        # Check for internal data leaks
        leak_patterns = ('"tool":', '"action":', '"parameters":', "ToolResult(")
        for pattern in leak_patterns:
            if pattern in text:
                text = text.replace(pattern, "[donnée filtrée]")
                logger.debug("Internal leak pattern filtered: %s", pattern)

        # Output safety via AISafetyLayer
        text = self._safety_output_check(text)

        return text

    def _safety_output_check(self, text: str) -> str:
        """Run output safety check via AISafetyLayer if available."""
        sl = self._safety_layer
        if sl is None:
            return text
        try:
            check = sl.check_output(text=text)
            if check.blocked:
                sanitized = sl.sanitize_output(text=text)
                logger.info("ResponseOrchestrator output sanitized")
                return sanitized or "Contenu filtré par la couche de sécurité."
            return text
        except Exception:
            return text

    # ------------------------------------------------------------------
    # Internal — Fallbacks
    # ------------------------------------------------------------------

    def _deterministic_response(self, input_data: ResponseInput) -> str:
        """Generate a deterministic response without LLM."""
        tool_results = input_data.tool_results

        # Greeting
        if input_data.tool_name == "greeting":
            return (
                "Bonjour ! Je suis l'assistant IA de RECUP-DZ, "
                "expert en gestion des déchets en Algérie.\n\n"
                "Je peux vous aider avec :\n"
                "- La recherche de codes déchets (nomenclature)\n"
                "- Les bordereaux de suivi (BSD)\n"
                "- Les déclarations DSD\n"
                "- Les inspections et la réglementation\n"
                "- La traçabilité des déchets\n\n"
                "Comment puis-je vous aider ?"
            )

        # No tool data
        if tool_results is None:
            return (
                "J'ai reçu votre question. Malheureusement, je ne peux pas "
                "fournir de réponse précise pour le moment. "
                "Veuillez réessayer ou reformuler votre question."
            )

        # Tool data available — format deterministically
        return self._format_tool_data(tool_results, input_data.tool_name)

    def _format_tool_data(
        self,
        tool_results: Any,
        tool_name: str,
    ) -> str:
        """Format tool results into a readable response without LLM."""
        if hasattr(tool_results, "messages") and tool_results.messages:
            parts = []
            for msg in tool_results.messages:
                if isinstance(msg, str) and msg.strip():
                    parts.append(msg.strip())
            if parts:
                return "\n\n".join(parts)

        if isinstance(tool_results, dict):
            lines = []
            for key, value in tool_results.items():
                if value is not None:
                    lines.append(f"**{key}** : {value}")
            if lines:
                return "\n\n".join(lines)

        if isinstance(tool_results, (list, tuple)):
            items = [str(r) for r in tool_results if r]
            if items:
                return "\n\n".join(items)

        return (
            "Les données ont été récupérées avec succès. "
            "Veuillez consulter les résultats ci-dessus."
        )

    def _fallback_response(self, input_data: ResponseInput) -> str:
        """Safe fallback response when everything fails."""
        if input_data.tool_name == "greeting":
            return (
                "Bonjour ! Je suis l'assistant IA de RECUP-DZ. "
                "Comment puis-je vous aider ?"
            )
        return (
            "Une erreur est survenue lors de la génération de la réponse. "
            "Veuillez réessayer."
        )

    def _greeting_followups(self, input_data: ResponseInput) -> List[str]:
        """Standard follow-ups for greeting messages."""
        return [
            "Rechercher un code déchet",
            "Consulter un bordereau",
            "Poser une question sur la réglementation",
        ]

    @staticmethod
    def _parse_followups(raw: str) -> List[str]:
        """Parse follow-up questions from LLM JSON array response."""
        if not raw:
            return []
        import json
        text = raw.strip()
        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        try:
            items = json.loads(text)
            if isinstance(items, list):
                return [str(q).strip() for q in items if q][:3]
        except (json.JSONDecodeError, TypeError):
            pass
        # Try to find array in text
        import re
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                items = json.loads(match.group())
                if isinstance(items, list):
                    return [str(q).strip() for q in items if q][:3]
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    # ------------------------------------------------------------------
    # Internal — Assembly
    # ------------------------------------------------------------------

    def _assemble_output(
        self,
        response_text: str,
        followups: List[str],
        input_data: ResponseInput,
        elapsed_ms: float,
    ) -> ResponseOutput:
        """Assemble the final ResponseOutput."""
        return ResponseOutput(
            success=True,
            response_text=response_text,
            followups=followups[:self._max_followups],
            meta={
                "tool_name": input_data.tool_name,
                "has_tool_results": input_data.has_tool_results,
                "has_knowledge": input_data.has_knowledge,
                "response_length": len(response_text),
                "followup_count": len(followups),
                "elapsed_ms": round(elapsed_ms, 1),
            },
        )

    # ------------------------------------------------------------------
    # Constants
    # ------------------------------------------------------------------

    _FOLLOWUP_SYSTEM_PROMPT = (
        "You are the AI Agent of RECUP-DZ, waste management expert.\n"
        "Based on the user's question and the response just given, "
        "suggest 2-3 relevant follow-up questions the user might want "
        "to ask next.  Return ONLY a JSON array of strings.\n"
        "Example: [\"Question 1 ?\", \"Question 2 ?\"]\n"
        "Questions should be in the SAME LANGUAGE as the user's message."
    )

    @staticmethod
    def _fallback_system_prompt(input_data: ResponseInput) -> str:
        """Build a basic system prompt when PromptBuilder is unavailable."""
        if input_data.tool_name == "greeting":
            return (
                "You are the friendly AI assistant of RECUP-DZ, "
                "a waste management platform in Algeria."
            )
        return (
            "You are the AI Agent of RECUP-DZ, expert in waste "
            "management in Algeria. Answer using ONLY the provided data."
        )
