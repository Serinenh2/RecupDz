"""
AI Core Module — Generic, offline AI agent framework.

Orchestrates: Request → Context → Route → Plan → Reason → Execute → Format → Response.
No business logic. No domain knowledge. Pure agent infrastructure.
"""

from apps.ai_assistant.core.agent import AIAgent, AgentFactory
from apps.ai_assistant.core.config import AIConfig, OllamaConfig, MemoryConfig, AgentConfig
from apps.ai_assistant.core.router_agent import (
    RouterAgent,
    RouteDecision,
    Intent,
    ConversationContext,
    RoutingAction,
)
from apps.ai_assistant.core.interfaces import (
    LLMProvider,
    Tool,
    MemoryStore,
    ContextBuilder,
    Planner,
    Reasoner,
    Router,
    Executor,
    Formatter,
    Agent,
)

__all__ = [
    # Router Agent
    "RouterAgent",
    "RouteDecision",
    "Intent",
    "ConversationContext",
    "RoutingAction",
    # Existing core
    "AIAgent",
    "AgentFactory",
    "AIConfig",
    "OllamaConfig",
    "MemoryConfig",
    "AgentConfig",
    "LLMProvider",
    "Tool",
    "MemoryStore",
    "ContextBuilder",
    "Planner",
    "Reasoner",
    "Router",
    "Executor",
    "Formatter",
    "Agent",
]
