"""
Tool Selection Stage — resolves which tool to execute from the plan.

Selects concrete tool from tool_registry based on plan step tool_name.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from apps.ai_assistant.reasoning_engine.pipeline import Intent, PipelineContext, PipelineStage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Selection Strategy
# ---------------------------------------------------------------------------

class ToolSelectionStrategy:
    """Strategy interface for selecting tools from plan steps."""

    def select_tool(
        self,
        tool_name: str,
        context: PipelineContext,
        available_tools: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class DefaultToolSelection(ToolSelectionStrategy):
    """Default tool selection — matches tool_name to registry."""

    def __init__(
        self,
        tool_aliases: Optional[Dict[str, str]] = None,
        tool_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        self._aliases = tool_aliases or {
            "search_knowledge": "entity_search",
            "direct_response": "direct_response",
            "fetch_entity": "entity_search",
            "analyze_entity": "analysis_tool",
            "generate_analysis": "analysis_tool",
            "generate_answer": "direct_response",
            "generate_recommendation": "recommendation_tool",
            "execute_command": "command_tool",
            "gather_context": "entity_search",
        }
        self._configs = tool_configs or {}

    def select_tool(
        self,
        tool_name: str,
        context: PipelineContext,
        available_tools: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        # Resolve alias
        resolved = self._aliases.get(tool_name, tool_name)

        # Check availability
        if available_tools is not None and resolved not in available_tools:
            logger.warning("Tool '%s' (resolved: '%s') not available", tool_name, resolved)
            return None

        config = self._configs.get(resolved, {})

        return {
            "name": resolved,
            "original_step": tool_name,
            "parameters": context.plan_steps[-1].get("parameters", {}) if context.plan_steps else {},
            "config": config,
        }


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class ToolSelectionStage(PipelineStage):
    """
    Stage 4: Select concrete tool(s) from the execution plan.

    Uses ToolSelectionStrategy to map plan step names → concrete tools.
    """

    name = "tool_selection"
    order = 40

    def __init__(
        self,
        strategy: Optional[ToolSelectionStrategy] = None,
        tool_registry: Any = None,
    ) -> None:
        self._strategy = strategy or DefaultToolSelection()
        self._tool_registry = tool_registry

    def should_run(self, context: PipelineContext) -> bool:
        return bool(context.plan_steps) and context.intent not in (Intent.GREETING, Intent.CHITCHAT)

    def process(self, context: PipelineContext) -> None:
        # Get available tools from registry
        available_tools = self._get_available_tools()

        selected: List[Dict[str, Any]] = []

        for step in context.plan_steps:
            tool_name = step.get("tool_name", "")
            if not tool_name:
                continue

            tool = self._strategy.select_tool(tool_name, context, available_tools)
            if tool is not None:
                # Merge step parameters into tool parameters
                step_params = step.get("parameters", {})
                tool["parameters"].update(step_params)
                tool["step_id"] = step.get("id", "")
                selected.append(tool)
            else:
                logger.debug("Skipping unavailable tool: %s", tool_name)

        context.selected_tools = selected

        if selected:
            context.current_tool = selected[0].get("name", "")
        else:
            context.current_tool = ""
            context.error_message = "No matching tool found for this request"

        logger.debug("Selected %d tools: %s", len(selected), [t["name"] for t in selected])

    def _get_available_tools(self) -> Optional[List[str]]:
        """Get list of available tools from registry."""
        if self._tool_registry is not None and hasattr(self._tool_registry, "list_tools"):
            try:
                tools = self._tool_registry.list_tools()
                if isinstance(tools, list):
                    return [t.get("name", "") if isinstance(t, dict) else str(t) for t in tools]
            except Exception as exc:
                logger.warning("Failed to list tools: %s", exc)
        return None
