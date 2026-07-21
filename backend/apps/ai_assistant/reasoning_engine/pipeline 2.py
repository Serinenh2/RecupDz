"""
Pipeline — orchestrates the reasoning stages.

Defines the stage interface, shared context, and the pipeline runner.
Each stage receives a PipelineContext, mutates it, and returns a status.
The pipeline chains stages and collects a trace of the full reasoning path.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class Intent(str, Enum):
    UNKNOWN = "unknown"
    GREETING = "greeting"
    QUESTION = "question"
    COMMAND = "command"
    CLARIFICATION = "clarification"
    CHITCHAT = "chitchat"
    ENTITY_LOOKUP = "entity_lookup"
    ANALYSIS = "analysis"
    RECOMMENDATION = "recommendation"


# ---------------------------------------------------------------------------
# Tool Execution
# ---------------------------------------------------------------------------

@dataclass
class ToolExecution:
    """Result of executing a single tool."""
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    success: bool = True
    error: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "result": self.result,
            "success": self.success,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


# ---------------------------------------------------------------------------
# Stage Result
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    """Outcome of a single pipeline stage."""
    stage_name: str
    status: StageStatus
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Pipeline Context (flowing state through stages)
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """
    Mutable state that flows through the pipeline.
    Every stage reads from and writes to this object.
    """
    # -- input --
    question: str = ""
    user_id: str = ""
    conversation_id: str = ""
    language: str = "fr"
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- intent detection output --
    intent: Intent = Intent.UNKNOWN
    intent_confidence: float = 0.0
    intent_entities: Dict[str, Any] = field(default_factory=dict)

    # -- entity extraction output --
    extracted_entities: List[Dict[str, Any]] = field(default_factory=list)
    primary_entity: Optional[Dict[str, Any]] = None

    # -- planning output --
    plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    plan_reasoning: str = ""

    # -- tool selection output --
    selected_tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    current_tool: str = ""

    # -- execution output --
    executed_tools: List[Dict[str, Any]] = field(default_factory=list)
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    execution_success: bool = True
    execution_summary: str = ""
    tool_results: List[Any] = field(default_factory=list)
    fail_fast: bool = True

    # -- validation output --
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    validated_data: Dict[str, Any] = field(default_factory=dict)

    # -- response output --
    response: Dict[str, Any] = field(default_factory=dict)
    response_text: str = ""
    response_metadata: Dict[str, Any] = field(default_factory=dict)

    # -- error handling --
    error_message: str = ""

    # -- suggestions --
    suggestions: List[str] = field(default_factory=list)

    # -- LLM response --
    llm_response: str = ""

    # -- timing --
    execution_time_ms: float = 0.0

    # -- trace --
    trace: List[StageResult] = field(default_factory=list)

    # -- helpers --
    def set(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def add_trace(self, result: StageResult) -> None:
        self.trace.append(result)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "intent": self.intent.value,
            "intent_confidence": self.intent_confidence,
            "entities": self.extracted_entities,
            "plan_steps": len(self.plan_steps),
            "selected_tools": self.selected_tools,
            "execution_success": self.execution_success,
            "validation_passed": self.validation_passed,
            "response": self.response_text[:200],
            "trace_stages": len(self.trace),
        }


# ---------------------------------------------------------------------------
# Pipeline Result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Final output of the entire pipeline."""
    status: PipelineStatus
    context: PipelineContext
    total_elapsed_ms: float = 0.0
    error: Optional[str] = None

    @property
    def response(self) -> str:
        return self.context.response_text

    @property
    def success(self) -> bool:
        return self.status == PipelineStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "response": self.response,
            "total_elapsed_ms": round(self.total_elapsed_ms, 1),
            "stages": [
                {
                    "name": t.stage_name,
                    "status": t.status.value,
                    "elapsed_ms": round(t.elapsed_ms, 1),
                    "error": t.error,
                }
                for t in self.context.trace
            ],
        }


# ---------------------------------------------------------------------------
# Pipeline Stage (ABC)
# ---------------------------------------------------------------------------

class PipelineStage(ABC):
    """
    Interface for a single reasoning pipeline stage.

    Subclasses implement process(). The pipeline calls:
        1. validate(context) — should this stage run?
        2. process(context)  — do the work
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stage identifier."""
        ...

    @property
    def order(self) -> int:
        """Execution order (lower = earlier). Default: 0."""
        return 0

    def should_run(self, context: PipelineContext) -> bool:
        """
        Return True if this stage should execute.
        Override to skip stages based on context.
        """
        return True

    @abstractmethod
    def process(self, context: PipelineContext) -> None:
        """
        Execute the stage. Read from context, write results back.
        Raise nothing — catch exceptions and write them to context.
        """
        ...

    def on_error(self, exc: Exception, context: PipelineContext) -> None:
        """Called if process() raises. Override for custom error handling."""
        pass


# ---------------------------------------------------------------------------
# Pipeline (Orchestrator)
# ---------------------------------------------------------------------------

class ReasoningPipeline:
    """
    Chains PipelineStages into an execution pipeline.

    Stages run in order. If a stage fails, remaining stages are skipped.
    Every stage is traced with timing and status.
    """

    def __init__(self, stages: Optional[List[PipelineStage]] = None) -> None:
        if stages is not None:
            self._stages: List[PipelineStage] = sorted(stages, key=lambda s: s.order)
        else:
            self._stages = self._default_stages()

    @staticmethod
    def _default_stages() -> List[PipelineStage]:
        """Return the default reasoning pipeline stages."""
        # Import here to avoid circular imports
        from apps.ai_assistant.reasoning_engine.intent_detector import IntentDetectionStage
        from apps.ai_assistant.reasoning_engine.entity_extractor import EntityExtractionStage
        from apps.ai_assistant.reasoning_engine.planner import PlanningStage
        from apps.ai_assistant.reasoning_engine.tool_selector import ToolSelectionStage
        from apps.ai_assistant.reasoning_engine.executor import ExecutionStage
        from apps.ai_assistant.reasoning_engine.validator import ValidationStage
        from apps.ai_assistant.reasoning_engine.responder import ResponseStage

        return sorted([
            IntentDetectionStage(),
            EntityExtractionStage(),
            PlanningStage(),
            ToolSelectionStage(),
            ExecutionStage(),
            ValidationStage(),
            ResponseStage(),
        ], key=lambda s: s.order)

    def add_stage(self, stage: PipelineStage) -> ReasoningPipeline:
        self._stages.append(stage)
        self._stages.sort(key=lambda s: s.order)
        return self

    def remove_stage(self, name: str) -> bool:
        before = len(self._stages)
        self._stages = [s for s in self._stages if s.name != name]
        return len(self._stages) < before

    def list_stages(self) -> List[str]:
        return [s.name for s in self._stages]

    def run(
        self,
        question: str,
        *,
        user_id: str = "",
        conversation_id: str = "",
        language: str = "fr",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Execute the full pipeline on a question.

        Returns PipelineResult with the final response and full trace.
        """
        start = time.monotonic()

        ctx = PipelineContext(
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            language=language,
            metadata=metadata or {},
        )

        logger.info("Pipeline start: '%s' (%d stages)", question[:60], len(self._stages))

        failed = False
        for stage in self._stages:
            # Check if stage should run
            if not stage.should_run(ctx):
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.SKIPPED,
                )
                ctx.add_trace(result)
                logger.debug("Stage '%s': SKIPPED", stage.name)
                continue

            # Run stage with timing
            stage_start = time.monotonic()
            try:
                stage.process(ctx)
                elapsed = (time.monotonic() - stage_start) * 1000
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.COMPLETED,
                    elapsed_ms=elapsed,
                )
                ctx.add_trace(result)
                logger.debug("Stage '%s': COMPLETED (%.1fms)", stage.name, elapsed)
            except Exception as exc:
                elapsed = (time.monotonic() - stage_start) * 1000
                stage.on_error(exc, ctx)
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.FAILED,
                    error=str(exc),
                    elapsed_ms=elapsed,
                )
                ctx.add_trace(result)
                logger.error("Stage '%s': FAILED (%.1fms) — %s", stage.name, elapsed, exc)
                failed = True
                break

        total_ms = (time.monotonic() - start) * 1000

        # Determine final status
        if failed:
            failed_stages = [t for t in ctx.trace if t.status == StageStatus.FAILED]
            error_msg = failed_stages[-1].error if failed_stages else "Unknown error"
            status = PipelineStatus.FAILED
        elif any(t.status == StageStatus.SKIPPED for t in ctx.trace):
            status = PipelineStatus.PARTIAL
        else:
            status = PipelineStatus.COMPLETED

        result = PipelineResult(
            status=status,
            context=ctx,
            total_elapsed_ms=total_ms,
            error=error_msg if failed else None,
        )

        logger.info(
            "Pipeline done: %s (%.1fms, %d stages)",
            status.value, total_ms, len(ctx.trace),
        )
        return result

    def run_with_context(self, ctx: PipelineContext) -> PipelineResult:
        """Execute the pipeline on an existing context (for testing/continuation)."""
        start = time.monotonic()
        failed = False
        error_msg = ""

        for stage in self._stages:
            if not stage.should_run(ctx):
                ctx.add_trace(StageResult(stage_name=stage.name, status=StageStatus.SKIPPED))
                continue

            stage_start = time.monotonic()
            try:
                stage.process(ctx)
                elapsed = (time.monotonic() - stage_start) * 1000
                ctx.add_trace(StageResult(stage_name=stage.name, status=StageStatus.COMPLETED, elapsed_ms=elapsed))
            except Exception as exc:
                elapsed = (time.monotonic() - stage_start) * 1000
                stage.on_error(exc, ctx)
                ctx.add_trace(StageResult(stage_name=stage.name, status=StageStatus.FAILED, error=str(exc), elapsed_ms=elapsed))
                error_msg = str(exc)
                failed = True
                break

        total_ms = (time.monotonic() - start) * 1000
        status = PipelineStatus.FAILED if failed else PipelineStatus.COMPLETED
        return PipelineResult(status=status, context=ctx, total_elapsed_ms=total_ms, error=error_msg or None)
