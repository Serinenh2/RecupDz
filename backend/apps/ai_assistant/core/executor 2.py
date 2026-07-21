"""
Tool Executor — discovers, validates, and runs tools.

Manages the tool registry and executes plan steps sequentially
(or in parallel when enabled).
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from apps.ai_assistant.core.config import ToolConfig
from apps.ai_assistant.core.interfaces import (
    Context,
    ExecutionPlan,
    StepStatus,
    TaskStep,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Central registry of available tools."""

    def __init__(self, config: Optional[ToolConfig] = None) -> None:
        self._config = config or ToolConfig()
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if self._config.disabled_tools and tool.name in self._config.disabled_tools:
            logger.info("Tool '%s' is disabled, skipping registration", tool.name)
            return
        if self._config.enabled_tools and tool.name not in self._config.enabled_tools:
            logger.debug("Tool '%s' not in enabled list, skipping", tool.name)
            return
        self._tools[tool.name] = tool
        logger.info("Tool registered: %s — %s", tool.name, tool.description)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_or_raise(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(
                f"Tool '{name}' not found. Available: {list(self._tools.keys())}"
            )
        return tool

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters_schema": t.parameters_schema,
            }
            for t in self._tools.values()
        ]

    def list_tool_descriptions(self) -> str:
        lines = [f"- {t.name}: {t.description}" for t in self._tools.values()]
        return "\n".join(lines) if lines else "Aucun outil disponible."

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def tool_names(self) -> List[str]:
        return list(self._tools.keys())


# ---------------------------------------------------------------------------
# Executor Implementation
# ---------------------------------------------------------------------------

class DefaultExecutor:
    """
    Executes an execution plan step-by-step.

    Supports sequential and parallel execution modes.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        config: Optional[ToolConfig] = None,
    ) -> None:
        self._registry = registry
        self._config = config or ToolConfig()

    def execute(self, plan: ExecutionPlan, context: Context) -> List[ToolResult]:
        results: List[ToolResult] = []

        if self._config.allow_parallel_execution and len(plan.steps) > 1:
            results = self._execute_parallel(plan, context)
        else:
            results = self._execute_sequential(plan, context)

        success_count = sum(1 for r in results if r.success)
        logger.info(
            "Plan execution complete: %d/%d steps succeeded",
            success_count, len(results),
        )
        return results

    def execute_step(self, step: TaskStep, context: Context) -> ToolResult:
        tool = self._registry.get(step.tool_name)
        if tool is None:
            step.status = StepStatus.FAILED
            step.error = f"Tool '{step.tool_name}' not found"
            return ToolResult(
                tool_name=step.tool_name,
                success=False,
                error=step.error,
            )

        # Validate parameters
        errors = tool.validate_parameters(step.parameters)
        if errors:
            step.status = StepStatus.FAILED
            step.error = f"Parameter validation failed: {errors}"
            return ToolResult(
                tool_name=step.tool_name,
                success=False,
                error=step.error,
            )

        step.status = StepStatus.RUNNING
        start = time.monotonic()
        try:
            result = tool.execute(step.parameters, context)
            elapsed = time.monotonic() - start
            step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
            step.result = result.data
            step.error = result.error
            logger.info(
                "Tool '%s' executed in %.2fs — success=%s",
                step.tool_name, elapsed, result.success,
            )
            return result
        except Exception as exc:
            elapsed = time.monotonic() - start
            step.status = StepStatus.FAILED
            step.error = str(exc)
            logger.error(
                "Tool '%s' failed after %.2fs: %s",
                step.tool_name, elapsed, exc,
            )
            return ToolResult(
                tool_name=step.tool_name,
                success=False,
                error=str(exc),
            )

    # -- internal --

    def _execute_sequential(self, plan: ExecutionPlan, context: Context) -> List[ToolResult]:
        results: List[ToolResult] = []
        for step in plan.steps:
            result = self.execute_step(step, context)
            results.append(result)
            if not result.success:
                logger.warning(
                    "Step '%s' failed, skipping remaining %d steps",
                    step.id, len(plan.steps) - len(results),
                )
                for remaining in plan.steps[len(results) :]:
                    remaining.status = StepStatus.SKIPPED
                break
        return results

    def _execute_parallel(self, plan: ExecutionPlan, context: Context) -> List[ToolResult]:
        results: List[ToolResult] = []
        timeout = self._config.tool_timeout_seconds

        with ThreadPoolExecutor(max_workers=min(len(plan.steps), 4)) as pool:
            future_to_step = {
                pool.submit(self.execute_step, step, context): step
                for step in plan.steps
            }
            for future in as_completed(future_to_step, timeout=timeout):
                step = future_to_step[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    step.status = StepStatus.FAILED
                    step.error = str(exc)
                    results.append(ToolResult(
                        tool_name=step.tool_name,
                        success=False,
                        error=str(exc),
                    ))

        return results
