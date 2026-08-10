"""
Integration test for the Router Agent.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from apps.ai_assistant.core.router_agent import (
    RouterAgent,
    RouteDecision,
    Intent,
    ConversationContext,
    RoutingAction,
)


def test_greeting():
    """Test greeting intent classification."""
    print("=== Test 1: Greeting ===")
    agent = RouterAgent()
    decision = agent.route("Bonjour!")

    print(f"Intent: {decision.intent.value}")
    print(f"Confidence: {decision.confidence:.2f}")
    print(f"Action: {decision.action.value}")
    print(f"Context: {decision.conversation_context.value}")
    print()

    assert decision.intent == Intent.GREETING
    assert decision.confidence >= 0.7
    assert decision.action in (RoutingAction.DIRECT_RESPONSE, RoutingAction.EXECUTE_TOOL)
    print("✓ Greeting test passed\n")


def test_nomenclature_search():
    """Test nomenclature code lookup."""
    print("=== Test 2: Nomenclature Search ===")
    agent = RouterAgent()
    decision = agent.route("Qu'est-ce que le code 15.01.06?")

    print(f"Intent: {decision.intent.value}")
    print(f"Confidence: {decision.confidence:.2f}")
    print(f"Tool: {decision.tool_name}")
    print(f"Entities: {decision.entities}")
    print(f"Context: {decision.conversation_context.value}")
    print()

    assert decision.intent == Intent.ENTITY_LOOKUP
    assert decision.tool_name == "waste_tool"
    assert "nomenclature_code" in decision.entities
    assert decision.entities["nomenclature_code"] == "15.01.06"
    assert decision.conversation_context == ConversationContext.NOMENCLATURE
    print("✓ Nomenclature search test passed\n")


def test_declaration_query():
    """Test declaration query."""
    print("=== Test 3: Declaration Query ===")
    agent = RouterAgent()
    decision = agent.route("Montre-moi les declarations de 2024")

    print(f"Intent: {decision.intent.value}")
    print(f"Tool: {decision.tool_name}")
    print(f"Parameters: {decision.tool_parameters}")
    print(f"Context: {decision.conversation_context.value}")
    print()

    assert decision.intent == Intent.ENTITY_LOOKUP
    assert decision.tool_name == "declaration_tool"
    assert "annee" in decision.tool_parameters
    print("✓ Declaration query test passed\n")


def test_statistics():
    """Test statistics request."""
    print("=== Test 4: Statistics ===")
    agent = RouterAgent()
    decision = agent.route("Affiche-moi les statistiques du recuperateur")

    print(f"Intent: {decision.intent.value}")
    print(f"Tool: {decision.tool_name}")
    print(f"Action: {decision.tool_parameters.get('action')}")
    print()

    assert decision.intent == Intent.STATISTICS
    assert decision.tool_name == "statistiques_tool"
    print("✓ Statistics test passed\n")


def test_regulation():
    """Test regulation query."""
    print("=== Test 5: Regulation ===")
    agent = RouterAgent()
    decision = agent.route("Quelle est la loi sur les dechets dangereux?")

    print(f"Intent: {decision.intent.value}")
    print(f"Tool: {decision.tool_name}")
    print(f"Context: {decision.conversation_context.value}")
    print()

    assert decision.intent == Intent.REGULATION
    assert decision.tool_name == "reglementation_tool"
    assert decision.conversation_context == ConversationContext.REGLEMENTAIRE
    print("✓ Regulation test passed\n")


def test_low_confidence_clarification():
    """Test clarification when confidence is low."""
    print("=== Test 6: Low Confidence Clarification ===")
    agent = RouterAgent()
    decision = agent.route("xyz")

    print(f"Intent: {decision.intent.value}")
    print(f"Confidence: {decision.confidence:.2f}")
    print(f"Action: {decision.action.value}")
    print(f"Clarification: {decision.clarification_question}")
    print()

    # Very short messages should get clarification or low confidence
    assert decision.confidence < 0.8
    print("✓ Low confidence test passed\n")


def test_conversation_context():
    """Test conversation context routing."""
    print("=== Test 7: Conversation Context ===")
    agent = RouterAgent()

    tests = [
        ("Code nomenclature 20.01.01", ConversationContext.NOMENCLATURE),
        ("Declaration DSD 2024", ConversationContext.DECLARATIONS),
        ("BSD en transit", ConversationContext.BSD),
        ("Loi sur les dechets", ConversationContext.REGLEMENTAIRE),
        ("Statistiques mensuelles", ConversationContext.DASHBOARD),
    ]

    for message, expected_ctx in tests:
        decision = agent.route(message)
        print(f"  '{message[:30]}...' → {decision.conversation_context.value}")
        assert decision.conversation_context == expected_ctx

    print()
    print("✓ Conversation context test passed\n")


def test_entity_extraction():
    """Test entity extraction from messages."""
    print("=== Test 8: Entity Extraction ===")
    agent = RouterAgent()

    decision = agent.route("Combien de tonnes de code 15.01.06 en 2024?")

    print(f"Entities: {decision.entities}")
    print()

    assert "nomenclature_code" in decision.entities
    assert "year" in decision.entities
    print("✓ Entity extraction test passed\n")


def test_alternatives():
    """Test alternative tool suggestions."""
    print("=== Test 9: Alternatives ===")
    agent = RouterAgent()
    decision = agent.route("Qu'est-ce qu'une nomenclature?")

    print(f"Primary tool: {decision.tool_name}")
    print(f"Alternatives: {[a['tool_name'] for a in decision.alternatives]}")
    print()

    assert len(decision.alternatives) > 0
    print("✓ Alternatives test passed\n")


def test_to_dict():
    """Test RouteDecision serialization."""
    print("=== Test 10: Serialization ===")
    agent = RouterAgent()
    decision = agent.route("Bonjour!")
    d = decision.to_dict()

    print(f"Keys: {list(d.keys())}")
    assert "intent" in d
    assert "confidence" in d
    assert "action" in d
    assert "tool_name" in d
    print()
    print("✓ Serialization test passed\n")


def test_partner_search():
    """Test partner search."""
    print("=== Test 11: Partner Search ===")
    agent = RouterAgent()
    decision = agent.route("Liste des eliminateurs en wilaya 16")

    print(f"Intent: {decision.intent.value}")
    print(f"Tool: {decision.tool_name}")
    print(f"Parameters: {decision.tool_parameters}")
    print()

    assert decision.intent == Intent.ENTITY_LOOKUP
    assert decision.tool_name == "partner_tool"
    assert decision.tool_parameters.get("wilaya") == "16"
    print("✓ Partner search test passed\n")


def test_report_generation():
    """Test report generation request."""
    print("=== Test 12: Report Generation ===")
    agent = RouterAgent()
    decision = agent.route("Genere un rapport de traceabilite pour janvier 2024")

    print(f"Intent: {decision.intent.value}")
    print(f"Tool: {decision.tool_name}")
    print(f"Parameters: {decision.tool_parameters}")
    print()

    assert decision.intent in (Intent.REPORT, Intent.COMMAND)
    assert decision.tool_name == "rapport_tool"
    print("✓ Report generation test passed\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Router Agent - Integration Tests")
    print("=" * 60 + "\n")

    try:
        test_greeting()
        test_nomenclature_search()
        test_declaration_query()
        test_statistics()
        test_regulation()
        test_low_confidence_clarification()
        test_conversation_context()
        test_entity_extraction()
        test_alternatives()
        test_to_dict()
        test_partner_search()
        test_report_generation()

        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
