"""
Workflow Data Models — immutable domain objects for the workflow engine.

Zero external dependencies. Pure dataclasses and enums.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StepType(str, Enum):
    ACTION = "action"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"
    SUBWORKFLOW = "subworkflow"
    WAIT = "wait"
    COMPENSATION = "compensation"


class StepStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    WAITING = "waiting"


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"


class EdgeType(str, Enum):
    NORMAL = "normal"
    CONDITIONAL = "conditional"
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    ON_RETRY = "on_retry"
    DEFAULT = "default"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RecoveryStrategy(str, Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    COMPENSATE = "compensate"
    ABORT = "abort"
    HUMAN_REVIEW = "human_review"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------

@dataclass
class StepInput:
    """Input specification for a workflow step."""
    name: str
    type_hint: str = "any"
    required: bool = True
    default: Any = None
    source_step: Optional[str] = None
    source_key: Optional[str] = None


@dataclass
class StepOutput:
    """Output specification for a workflow step."""
    name: str
    type_hint: str = "any"
    description: str = ""


@dataclass
class StepConfig:
    """Configuration for a single workflow step."""
    id: str
    name: str
    step_type: StepType = StepType.ACTION
    tool_name: Optional[str] = None
    handler: Optional[str] = None
    inputs: List[StepInput] = field(default_factory=list)
    outputs: List[StepOutput] = field(default_factory=list)
    timeout_seconds: float = 60.0
    max_retries: int = 0
    retry_delay_seconds: float = 1.0
    retry_backoff: float = 2.0
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.ABORT
    fallback_value: Any = None
    compensation_step: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None
    priority: Priority = Priority.NORMAL
    enabled: bool = True


@dataclass
class Edge:
    """Directed edge between two steps."""
    id: str
    from_step: str
    to_step: str
    edge_type: EdgeType = EdgeType.NORMAL
    condition: Optional[str] = None
    label: str = ""


@dataclass
class WorkflowDefinition:
    """Complete workflow definition (immutable after creation)."""
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    steps: List[StepConfig] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    timeout_seconds: float = 300.0

    def get_step(self, step_id: str) -> Optional[StepConfig]:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def get_edges_from(self, step_id: str) -> List[Edge]:
        return [e for e in self.edges if e.from_step == step_id]

    def get_edges_to(self, step_id: str) -> List[Edge]:
        return [e for e in self.edges if e.to_step == step_id]

    def get_root_steps(self) -> List[StepConfig]:
        targets = {e.to_step for e in self.edges}
        return [s for s in self.steps if s.id not in targets]

    def get_leaf_steps(self) -> List[StepConfig]:
        sources = {e.from_step for e in self.edges}
        return [s for s in self.steps if s.id not in sources]


@dataclass
class StepState:
    """Mutable state for a single step execution."""
    step_id: str
    status: StepStatus = StepStatus.PENDING
    attempt: int = 0
    max_attempts: int = 1
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    retry_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None

    @property
    def elapsed_ms(self) -> Optional[float]:
        if self.start_time:
            return (time.monotonic() - self.start_time) * 1000
        return None


@dataclass
class WorkflowState:
    """Mutable state for the entire workflow execution."""
    workflow_id: str
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    status: WorkflowStatus = WorkflowStatus.DRAFT
    step_states: Dict[str, StepState] = field(default_factory=dict)
    global_context: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None
    compensation_stack: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_step_state(self, step_id: str) -> StepState:
        if step_id not in self.step_states:
            self.step_states[step_id] = StepState(step_id=step_id)
        return self.step_states[step_id]

    @property
    def duration_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None

    def completed_steps(self) -> List[str]:
        return [sid for sid, s in self.step_states.items()
                if s.status == StepStatus.COMPLETED]

    def failed_steps(self) -> List[str]:
        return [sid for sid, s in self.step_states.items()
                if s.status == StepStatus.FAILED]

    def all_done(self) -> bool:
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.CANCELLED)
            for s in self.step_states.values()
        ) and len(self.step_states) > 0


@dataclass
class WorkflowResult:
    """Final result of a workflow execution."""
    workflow_id: str
    run_id: str
    status: WorkflowStatus
    output: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == WorkflowStatus.COMPLETED
