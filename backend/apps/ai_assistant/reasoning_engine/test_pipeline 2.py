"""
Integration test for the AI Reasoning Engine pipeline.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from apps.ai_assistant.reasoning_engine import (
    ReasoningPipeline,
    PipelineContext,
    IntentDetectionStage,
    EntityExtractionStage,
    PlanningStage,
    ToolSelectionStage,
    ExecutionStage,
    ValidationStage,
    ResponseStage,
)


def test_full_pipeline():
    """Test the complete pipeline with a question."""
    print("=== Test 1: Full Pipeline ===")

    pipeline = ReasoningPipeline()
    result = pipeline.run("Qu'est-ce qu'une nomenclature?")
    context = result.context

    print(f"Intent: {context.intent}")
    print(f"Confidence: {context.intent_confidence:.0%}")
    print(f"Entities: {context.extracted_entities}")
    print(f"Plan steps: {len(context.plan_steps)}")
    print(f"Selected tools: {len(context.selected_tools)}")
    print(f"Executed tools: {len(context.executed_tools)}")
    print(f"Validation: {len(context.validation_results)}")
    print(f"Answer: {context.response_text[:100] if context.response_text else 'N/A'}...")
    print()
    assert context.intent is not None
    assert result.success
    print("✓ Full pipeline test passed\n")


def test_greeting():
    """Test greeting intent."""
    print("=== Test 2: Greeting ===")

    pipeline = ReasoningPipeline()
    result = pipeline.run("Bonjour!")
    context = result.context

    print(f"Intent: {context.intent}")
    print(f"Answer: {context.response_text[:80] if context.response_text else 'N/A'}")
    print()
    assert context.intent.value == "greeting"
    print("✓ Greeting test passed\n")


def test_entity_lookup():
    """Test entity lookup with code."""
    print("=== Test 3: Entity Lookup ===")

    pipeline = ReasoningPipeline()
    result = pipeline.run("Qu'est-ce que le code 15.01.06?")
    context = result.context

    print(f"Intent: {context.intent}")
    print(f"Entities: {context.extracted_entities}")
    print(f"Primary entity: {context.primary_entity}")
    print()
    assert len(context.extracted_entities) > 0
    print("✓ Entity lookup test passed\n")


def test_custom_stages():
    """Test pipeline with custom stages."""
    print("=== Test 4: Custom Stages ===")

    pipeline = ReasoningPipeline(stages=[
        IntentDetectionStage(),
        EntityExtractionStage(),
        PlanningStage(),
        ResponseStage(),
    ])

    result = pipeline.run("Bonjour!")
    context = result.context
    print(f"Intent: {context.intent}")
    print(f"Response: {context.response}")
    print()
    assert context.response is not None
    print("✓ Custom stages test passed\n")


def test_pipeline_result():
    """Test PipelineResult."""
    print("=== Test 5: PipelineResult ===")

    pipeline = ReasoningPipeline()
    result = pipeline.run("Test question")

    print(f"Success: {result.success}")
    print(f"Execution time: {result.total_elapsed_ms:.1f}ms")
    print(f"Stages run: {len(result.context.trace)}")
    print()
    assert result.success is True
    print("✓ PipelineResult test passed\n")


def test_stage_ordering():
    """Test that stages are ordered correctly."""
    print("=== Test 6: Stage Ordering ===")

    pipeline = ReasoningPipeline()
    stage_names = [s.name for s in pipeline._stages]

    print(f"Stage order: {stage_names}")

    # Verify order
    assert stage_names.index("intent_detection") < stage_names.index("entity_extraction")
    assert stage_names.index("entity_extraction") < stage_names.index("planning")
    assert stage_names.index("planning") < stage_names.index("tool_selection")
    assert stage_names.index("tool_selection") < stage_names.index("execution")
    assert stage_names.index("execution") < stage_names.index("validation")
    assert stage_names.index("validation") < stage_names.index("response")
    print("✓ Stage ordering test passed\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("AI Reasoning Engine - Integration Tests")
    print("=" * 60 + "\n")

    try:
        test_full_pipeline()
        test_greeting()
        test_entity_lookup()
        test_custom_stages()
        test_pipeline_result()
        test_stage_ordering()

        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
