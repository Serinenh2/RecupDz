"""
Execution Stage — executes the selected tool(s).

Executes tools sequentially, respecting dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.reasoning_engine.pipeline import PipelineContext, PipelineStage, ToolExecution

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Execution Strategy
# ---------------------------------------------------------------------------

class ExecutionStrategy:
    """Strategy for executing tools."""

    def execute(
        self,
        tools: List[Dict[str, Any]],
        context: PipelineContext,
        tool_executor: Any = None,
    ) -> List[ToolExecution]:
        raise NotImplementedError


class SequentialExecution(ExecutionStrategy):
    """Execute tools sequentially in order."""

    def execute(
        self,
        tools: List[Dict[str, Any]],
        context: PipelineContext,
        tool_executor: Any = None,
    ) -> List[ToolExecution]:
        results: List[ToolExecution] = []

        for tool in tools:
            execution = self._execute_single(tool, context, tool_executor)
            results.append(execution)

            # Stop on failure (unless configured to continue)
            if not execution.success and context.fail_fast:
                logger.warning("Execution stopped: tool '%s' failed", tool.get("name"))
                break

        return results

    def _execute_single(
        self,
        tool: Dict[str, Any],
        context: PipelineContext,
        tool_executor: Any,
    ) -> ToolExecution:
        """Execute a single tool."""
        tool_name = tool.get("name", "unknown")
        parameters = tool.get("parameters", {})

        # Try actual tool executor
        if tool_executor is not None:
            try:
                if hasattr(tool_executor, "execute_tool"):
                    result = tool_executor.execute_tool(tool_name, parameters)
                elif callable(tool_executor):
                    result = tool_executor(tool_name, parameters)
                else:
                    result = {"success": False, "error": "Invalid executor type"}

                return ToolExecution(
                    tool_name=tool_name,
                    parameters=parameters,
                    result=result,
                    success=result.get("success", False) if isinstance(result, dict) else bool(result),
                    error=result.get("error", "") if isinstance(result, dict) else "",
                )

            except Exception as exc:
                logger.error("Tool execution error: %s — %s", tool_name, exc)
                return ToolExecution(
                    tool_name=tool_name,
                    parameters=parameters,
                    result={},
                    success=False,
                    error=str(exc),
                )

        # No executor — return placeholder
        return ToolExecution(
            tool_name=tool_name,
            parameters=parameters,
            result={"status": "simulated", "tool": tool_name},
            success=True,
        )


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class ExecutionStage(PipelineStage):
    """
    Stage 5: Execute selected tools.

    Uses ExecutionStrategy. Default: sequential execution.
    """

    name = "execution"
    order = 50

    def __init__(
        self,
        strategy: Optional[ExecutionStrategy] = None,
        tool_executor: Any = None,
        fail_fast: bool = True,
    ) -> None:
        self._strategy = strategy or SequentialExecution()
        self._tool_executor = tool_executor
        self._fail_fast = fail_fast

    def process(self, context: PipelineContext) -> None:
        context.fail_fast = self._fail_fast

        if not context.selected_tools:
            context.executed_tools = []
            context.execution_summary = "No tools to execute"
            return

        executions = self._strategy.execute(
            context.selected_tools,
            context,
            self._tool_executor,
        )

        context.executed_tools = [e.to_dict() for e in executions]

        # Summary
        success_count = sum(1 for e in executions if e.success)
        context.execution_summary = (
            f"Executed {len(executions)} tools: {success_count} succeeded, "
            f"{len(executions) - success_count} failed"
        )

        # Collect all results
        context.tool_results = []
        for e in executions:
            if e.success and e.result:
                context.tool_results.append(e.result)

        logger.debug(context.execution_summary)
