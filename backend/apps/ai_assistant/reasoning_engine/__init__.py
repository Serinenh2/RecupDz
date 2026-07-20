"""
AI Reasoning Engine — production-ready pipeline for intelligent request processing.

Pipeline:
    Question → Intent Detection → Entity Extraction → Planning → Tool Selection →
    Execution → Validation → Response

Usage:
    from apps.ai_assistant.reasoning_engine import ReasoningPipeline, PipelineContext

    pipeline = ReasoningPipeline()
    context = pipeline.run("Qu'est-ce qu'une nomenclature?")
    print(context.response)
"""

from apps.ai_assistant.reasoning_engine.pipeline import (
    Intent,
    PipelineContext,
    PipelineResult,
    PipelineStage,
    ReasoningPipeline,
)
from apps.ai_assistant.reasoning_engine.intent_detector import IntentDetectionStage
from apps.ai_assistant.reasoning_engine.entity_extractor import EntityExtractionStage
from apps.ai_assistant.reasoning_engine.planner import PlanningStage
from apps.ai_assistant.reasoning_engine.tool_selector import ToolSelectionStage
from apps.ai_assistant.reasoning_engine.executor import ExecutionStage
from apps.ai_assistant.reasoning_engine.validator import ValidationStage
from apps.ai_assistant.reasoning_engine.responder import ResponseStage

__all__ = [
    # Core
    "Intent",
    "PipelineContext",
    "PipelineResult",
    "PipelineStage",
    "ReasoningPipeline",
    # Stages
    "IntentDetectionStage",
    "EntityExtractionStage",
    "PlanningStage",
    "ToolSelectionStage",
    "ExecutionStage",
    "ValidationStage",
    "ResponseStage",
]
