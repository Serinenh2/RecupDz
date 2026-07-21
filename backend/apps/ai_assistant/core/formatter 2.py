"""
Response Formatter — transforms raw tool results into user-facing output.

Supports multiple output strategies (text, JSON, markdown, structured)
and LLM-powered natural language formatting.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.interfaces import (
    Context,
    FormattedResponse,
    Formatter,
    LLMProvider,
    OutputFormat,
    ReasoningResult,
    ToolResult,
)
from apps.ai_assistant.core.prompts import PromptRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Format Strategy (Strategy Pattern)
# ---------------------------------------------------------------------------

class FormatStrategy(ABC):
    """Base class for formatting strategies."""

    @property
    @abstractmethod
    def format_type(self) -> OutputFormat:
        ...

    @abstractmethod
    def format(
        self,
        results: List[ToolResult],
        context: Context,
        reasoning: Optional[ReasoningResult] = None,
    ) -> str:
        ...


class TextFormatStrategy(FormatStrategy):
    """Plain text formatting — extracts readable text from results."""

    @property
    def format_type(self) -> OutputFormat:
        return OutputFormat.TEXT

    def format(
        self,
        results: List[ToolResult],
        context: Context,
        reasoning: Optional[ReasoningResult] = None,
    ) -> str:
        parts: List[str] = []
        for result in results:
            if result.success and result.data is not None:
                parts.append(self._stringify(result.data))
            elif result.error:
                parts.append(f"[Erreur: {result.error}]")
        return "\n\n".join(parts) if parts else "Aucun résultat disponible."

    def _stringify(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False, indent=2)
        if isinstance(data, list):
            return "\n".join(self._stringify(item) for item in data)
        return str(data)


class JSONFormatStrategy(FormatStrategy):
    """JSON formatting — structured output."""

    @property
    def format_type(self) -> OutputFormat:
        return OutputFormat.JSON

    def format(
        self,
        results: List[ToolResult],
        context: Context,
        reasoning: Optional[ReasoningResult] = None,
    ) -> str:
        output: Dict[str, Any] = {
            "results": [],
            "metadata": {
                "result_count": len(results),
                "success_count": sum(1 for r in results if r.success),
            },
        }
        if reasoning:
            output["reasoning"] = {
                "conclusion": reasoning.conclusion,
                "confidence": reasoning.confidence,
            }

        for result in results:
            entry: Dict[str, Any] = {
                "tool": result.tool_name,
                "success": result.success,
            }
            if result.data is not None:
                entry["data"] = result.data
            if result.error:
                entry["error"] = result.error
            output["results"].append(entry)

        return json.dumps(output, ensure_ascii=False, indent=2)


class MarkdownFormatStrategy(FormatStrategy):
    """Markdown formatting — for rich UI rendering."""

    @property
    def format_type(self) -> OutputFormat:
        return OutputFormat.MARKDOWN

    def format(
        self,
        results: List[ToolResult],
        context: Context,
        reasoning: Optional[ReasoningResult] = None,
    ) -> str:
        parts: List[str] = []
        for result in results:
            if result.success and result.data is not None:
                parts.append(self._to_markdown(result))
            elif result.error:
                parts.append(f"> **Erreur** ({result.tool_name}): {result.error}")
        return "\n\n---\n\n".join(parts) if parts else "_Aucun résultat._"

    def _to_markdown(self, result: ToolResult) -> str:
        data = result.data
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            lines = [f"### {result.tool_name}\n"]
            for key, val in data.items():
                lines.append(f"- **{key}**: {val}")
            return "\n".join(lines)
        if isinstance(data, list):
            lines = [f"### {result.tool_name}\n"]
            for item in data:
                lines.append(f"- {item}")
            return "\n".join(lines)
        return str(data)


class StructuredFormatStrategy(FormatStrategy):
    """Structured formatting — combines text with metadata."""

    @property
    def format_type(self) -> OutputFormat:
        return OutputFormat.STRUCTURED

    def format(
        self,
        results: List[ToolResult],
        context: Context,
        reasoning: Optional[ReasoningResult] = None,
    ) -> str:
        sections: List[str] = []

        success_results = [r for r in results if r.success]
        error_results = [r for r in results if not r.success]

        if success_results:
            sections.append("**Résultats:**\n")
            for r in success_results:
                sections.append(self._format_single(r))

        if error_results:
            sections.append("\n**Erreurs:**\n")
            for r in error_results:
                sections.append(f"- {r.tool_name}: {r.error}")

        if reasoning and reasoning.chain_of_thought:
            sections.append("\n**Raisonnement:**")
            for i, thought in enumerate(reasoning.chain_of_thought, 1):
                sections.append(f"  {i}. {thought}")

        return "\n".join(sections) if sections else "Aucun résultat."

    def _format_single(self, result: ToolResult) -> str:
        if isinstance(result.data, dict):
            lines = [f"**{result.tool_name}:**"]
            for k, v in result.data.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        return f"**{result.tool_name}:** {result.data}"


# ---------------------------------------------------------------------------
# LLM-Powered Formatter
# ---------------------------------------------------------------------------

class LLMFormatter(Formatter):
    """
    Uses the LLM to produce natural language responses from raw results.
    Falls back to strategy-based formatting if LLM is unavailable.
    """

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        registry: Optional[PromptRegistry] = None,
        fallback_strategy: Optional[FormatStrategy] = None,
    ) -> None:
        self._llm = llm
        self._registry = registry or PromptRegistry()
        self._strategies: Dict[OutputFormat, FormatStrategy] = {
            OutputFormat.TEXT: TextFormatStrategy(),
            OutputFormat.JSON: JSONFormatStrategy(),
            OutputFormat.MARKDOWN: MarkdownFormatStrategy(),
            OutputFormat.STRUCTURED: StructuredFormatStrategy(),
        }
        self._fallback = fallback_strategy or TextFormatStrategy()

    def format(
        self,
        results: List[ToolResult],
        context: Context,
        reasoning: Optional[ReasoningResult] = None,
        *,
        output_format: OutputFormat = OutputFormat.TEXT,
    ) -> FormattedResponse:
        # JSON and structured bypass LLM formatting — always use strategy
        if output_format in (OutputFormat.JSON, OutputFormat.STRUCTURED):
            strategy = self._strategies.get(output_format, self._fallback)
            text = strategy.format(results, context, reasoning)
            return FormattedResponse(text=text, format=output_format)

        # For text/markdown, try LLM if available
        if self._llm and self._llm.is_available():
            try:
                text = self._llm_format(results, context, output_format)
                return FormattedResponse(text=text, format=output_format)
            except Exception as exc:
                logger.warning("LLM formatting failed: %s — using strategy fallback", exc)

        strategy = self._strategies.get(output_format, self._fallback)
        text = strategy.format(results, context, reasoning)
        return FormattedResponse(text=text, format=output_format)

    def _llm_format(
        self,
        results: List[ToolResult],
        context: Context,
        output_format: OutputFormat,
    ) -> str:
        user_message = ""
        for msg in reversed(context.messages):
            if msg.role.value == "user":
                user_message = msg.content
                break

        results_text = self._results_to_text(results)
        language = context.metadata.get("language", "fr")

        prompt = self._registry.render(
            "response_formatting",
            results=results_text,
            user_message=user_message,
            language=language,
        )

        system = (
            "Tu es un formateur de réponses expert. "
            "Tu transformes des données brutes en réponses claires et utiles."
        )
        if output_format == OutputFormat.MARKDOWN:
            system += " Utilise le formatage markdown."

        return self._llm.generate(prompt, system_prompt=system, temperature=0.4, max_tokens=1500)

    def _results_to_text(self, results: List[ToolResult]) -> str:
        parts: List[str] = []
        for r in results:
            if r.success and r.data is not None:
                data_str = json.dumps(r.data, ensure_ascii=False) if not isinstance(r.data, str) else r.data
                parts.append(f"[{r.tool_name}] {data_str}")
            elif r.error:
                parts.append(f"[{r.tool_name}] ERREUR: {r.error}")
        return "\n".join(parts)

    def register_strategy(self, strategy: FormatStrategy) -> None:
        self._strategies[strategy.format_type] = strategy
