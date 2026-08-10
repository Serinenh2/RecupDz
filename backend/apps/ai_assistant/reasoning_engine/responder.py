"""
Response Stage — formats and returns the final response.

Assembles a structured response from validated results.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.reasoning_engine.pipeline import PipelineContext, PipelineStage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response Format
# ---------------------------------------------------------------------------

@dataclass
class ResponseFormat:
    """Controls how the response is formatted."""
    include_sources: bool = True
    include_confidence: bool = True
    include_suggestions: bool = True
    include_metadata: bool = False
    max_length: int = 4096
    language: str = "fr"


# ---------------------------------------------------------------------------
# Response Builder
# ---------------------------------------------------------------------------

class ResponseBuilder:
    """Builds the final response dict."""

    def __init__(self, fmt: Optional[ResponseFormat] = None) -> None:
        self._format = fmt or ResponseFormat()

    def build(self, context: PipelineContext) -> Dict[str, Any]:
        response: Dict[str, Any] = {
            "answer": self._build_answer(context),
            "intent": context.intent.value if context.intent else "unknown",
            "confidence": round(context.intent_confidence, 2),
        }

        if self._format.include_sources:
            response["sources"] = self._extract_sources(context)

        if self._format.include_suggestions:
            response["suggestions"] = context.suggestions

        if self._format.include_metadata:
            response["metadata"] = {
                "execution_time_ms": context.execution_time_ms,
                "tools_used": [t.get("name", "") for t in context.selected_tools],
                "entities_found": len(context.extracted_entities),
            }

        return response

    def _build_answer(self, context: PipelineContext) -> str:
        """Build the answer string from tool results."""
        # Check for direct answer from LLM
        if context.llm_response:
            return context.llm_response

        # Assemble from tool results
        parts: List[str] = []

        for result in context.tool_results:
            if isinstance(result, dict):
                if "answer" in result:
                    parts.append(str(result["answer"]))
                elif "message" in result:
                    parts.append(str(result["message"]))
                elif "data" in result:
                    data = result["data"]
                    if isinstance(data, str):
                        parts.append(data)
                    elif isinstance(data, list):
                        parts.append(f"Found {len(data)} results")
                    elif isinstance(data, dict):
                        parts.append(str(data))

        if parts:
            answer = "\n\n".join(parts)
            # Truncate if too long
            if len(answer) > self._format.max_length:
                answer = answer[: self._format.max_length - 3] + "..."
            return answer

        # Fallback
        if context.error_message:
            return f"I apologize, but I encountered an issue: {context.error_message}"

        return "I wasn't able to find a specific answer to your question. Could you please rephrase?"

    def _extract_sources(self, context: PipelineContext) -> List[Dict[str, Any]]:
        """Extract source references from results."""
        sources: List[Dict[str, Any]] = []

        for result in context.tool_results:
            if isinstance(result, dict) and "sources" in result:
                for src in result["sources"]:
                    if isinstance(src, dict):
                        sources.append(src)
                    elif isinstance(src, str):
                        sources.append({"name": src})

        return sources


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class ResponseStage(PipelineStage):
    """
    Stage 7: Build and return the final response.

    Assembles answer, sources, suggestions, and metadata.
    """

    name = "response"
    order = 70

    def __init__(
        self,
        builder: Optional[ResponseBuilder] = None,
        response_format: Optional[ResponseFormat] = None,
    ) -> None:
        self._builder = builder or ResponseBuilder(response_format)

    def process(self, context: PipelineContext) -> None:
        context.response = self._builder.build(context)

        # Add suggestions if not already set
        if not context.suggestions:
            context.suggestions = self._generate_suggestions(context)
            context.response["suggestions"] = context.suggestions

        logger.debug("Response built: %d chars", len(context.response.get("answer", "")))

    def _generate_suggestions(self, context: PipelineContext) -> List[str]:
        """Generate follow-up suggestions based on context."""
        suggestions: List[str] = []

        if context.intent and context.intent.value == "question":
            suggestions.append("Would you like more details on this topic?")
            suggestions.append("Do you have any other questions?")

        return suggestions
