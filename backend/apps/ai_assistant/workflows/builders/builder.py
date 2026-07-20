"""
Workflow Builder — fluent DSL for constructing workflows.

Usage:
    from apps.ai_assistant.workflows.builders import WorkflowBuilder

    wf = (
        WorkflowBuilder("my_workflow", "Process data")
        .step("fetch", "Fetch Data", tool_name="api_call")
        .step("parse", "Parse", tool_name="parser")
        .step("validate", "Validate", tool_name="validator")
        .step("save", "Save", tool_name="db_write")
        .depends("parse", "fetch")
        .depends("validate", "parse")
        .depends("save", "validate")
        .timeout(120)
        .build()
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from apps.ai_assistant.workflows.models import (
    Edge, EdgeType, Priority, RecoveryStrategy, StepConfig, StepInput,
    StepOutput, StepType, WorkflowDefinition,
)


@dataclass
class StepDef:
    id: str
    name: str
    step_type: StepType = StepType.ACTION
    tool_name: Optional[str] = None
    handler: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    inputs: List[StepInput] = field(default_factory=list)
    outputs: List[StepOutput] = field(default_factory=list)
    timeout_seconds: float = 60.0
    max_retries: int = 0
    retry_delay_seconds: float = 1.0
    retry_backoff: float = 2.0
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.ABORT
    fallback_value: Any = None
    compensation_step: Optional[str] = None
    priority: Priority = Priority.NORMAL
    condition: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class WorkflowBuilder:
    """Fluent builder for constructing WorkflowDefinition objects."""

    def __init__(
        self,
        workflow_id: str,
        name: str,
        description: str = "",
    ) -> None:
        self._id = workflow_id
        self._name = name
        self._description = description
        self._version = "1.0.0"
        self._steps: List[StepDef] = []
        self._timeout = 300.0
        self._tags: List[str] = []
        self._metadata: Dict[str, Any] = {}
        self._input_schema: Dict[str, Any] = {}
        self._output_schema: Dict[str, Any] = {}

    def step(
        self,
        step_id: str,
        name: str,
        *,
        step_type: str = "action",
        tool_name: Optional[str] = None,
        handler: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        recovery: str = "abort",
        fallback: Any = None,
        compensation: Optional[str] = None,
        priority: str = "normal",
        condition: Optional[str] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "WorkflowBuilder":
        sd = StepDef(
            id=step_id,
            name=name,
            step_type=StepType(step_type),
            tool_name=tool_name,
            handler=handler,
            timeout_seconds=timeout,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay,
            retry_backoff=retry_backoff,
            recovery_strategy=RecoveryStrategy(recovery),
            fallback_value=fallback,
            compensation_step=compensation,
            priority=Priority(priority),
            condition=condition,
            enabled=enabled,
            metadata=metadata or {},
        )
        self._steps.append(sd)
        return self

    def depends(self, step_id: str, on_step: str) -> "WorkflowBuilder":
        for s in self._steps:
            if s.id == step_id:
                if on_step not in s.depends_on:
                    s.depends_on.append(on_step)
                break
        return self

    def parallel(self, step_ids: List[str], join_after: Optional[str] = None) -> "WorkflowBuilder":
        for sid in step_ids:
            for s in self._steps:
                if s.id == sid:
                    s.step_type = StepType.PARALLEL
        return self

    def condition(self, step_id: str, expr: str) -> "WorkflowBuilder":
        for s in self._steps:
            if s.id == step_id:
                s.condition = expr
                s.step_type = StepType.CONDITION
        return self

    def timeout(self, seconds: float) -> "WorkflowBuilder":
        self._timeout = seconds
        return self

    def version(self, version: str) -> "WorkflowBuilder":
        self._version = version
        return self

    def tags(self, *tags: str) -> "WorkflowBuilder":
        self._tags.extend(tags)
        return self

    def metadata(self, key: str, value: Any) -> "WorkflowBuilder":
        self._metadata[key] = value
        return self

    def build(self) -> WorkflowDefinition:
        steps = []
        edges = []

        for sd in self._steps:
            step = StepConfig(
                id=sd.id,
                name=sd.name,
                step_type=sd.step_type,
                tool_name=sd.tool_name,
                handler=sd.handler,
                inputs=sd.inputs,
                outputs=sd.outputs,
                timeout_seconds=sd.timeout_seconds,
                max_retries=sd.max_retries,
                retry_delay_seconds=sd.retry_delay_seconds,
                retry_backoff=sd.retry_backoff,
                recovery_strategy=sd.recovery_strategy,
                fallback_value=sd.fallback_value,
                compensation_step=sd.compensation_step,
                priority=sd.priority,
                condition=sd.condition,
                metadata=sd.metadata,
                enabled=sd.enabled,
            )
            steps.append(step)

        for sd in self._steps:
            for dep_id in sd.depends_on:
                edge_type = EdgeType.CONDITIONAL if sd.condition else EdgeType.ON_SUCCESS
                edges.append(Edge(
                    id=f"{dep_id}_to_{sd.id}",
                    from_step=dep_id,
                    to_step=sd.id,
                    edge_type=edge_type,
                    condition=sd.condition,
                ))

        step_ids = {s.id for s in self._steps}
        for sd in self._steps:
            if sd.step_type == StepType.PARALLEL and not sd.depends_on:
                for other in self._steps:
                    if other.id != sd.id and sd.id not in other.depends_on:
                        pass

        return WorkflowDefinition(
            id=self._id,
            name=self._name,
            description=self._description,
            version=self._version,
            steps=steps,
            edges=edges,
            timeout_seconds=self._timeout,
            tags=self._tags,
            metadata=self._metadata,
            input_schema=self._input_schema,
            output_schema=self._output_schema,
        )


def build_linear(
    workflow_id: str,
    name: str,
    steps_data: List[Dict[str, Any]],
    description: str = "",
) -> WorkflowDefinition:
    """Quickly build a linear workflow from a list of step dicts."""
    builder = WorkflowBuilder(workflow_id, name, description)
    prev_id = None
    for i, s in enumerate(steps_data):
        sid = s.get("id", f"step_{i}")
        builder.step(
            sid,
            s.get("name", sid),
            tool_name=s.get("tool_name"),
            timeout=s.get("timeout", 60.0),
            max_retries=s.get("max_retries", 0),
        )
        if prev_id:
            builder.depends(sid, prev_id)
        prev_id = sid
    return builder.build()


def build_parallel_join(
    workflow_id: str,
    name: str,
    branch_steps: List[Dict[str, Any]],
    join_step: Dict[str, Any],
    description: str = "",
) -> WorkflowDefinition:
    """Build a fan-out/fan-in workflow."""
    builder = WorkflowBuilder(workflow_id, name, description)
    branch_ids = []
    for s in branch_steps:
        sid = s["id"]
        builder.step(sid, s.get("name", sid), tool_name=s.get("tool_name"))
        branch_ids.append(sid)

    join_id = join_step["id"]
    builder.step(join_id, join_step.get("name", join_id), tool_name=join_step.get("tool_name"))
    for bid in branch_ids:
        builder.depends(join_id, bid)

    return builder.build()
