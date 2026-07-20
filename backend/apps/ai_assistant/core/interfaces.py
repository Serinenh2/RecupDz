"""
Abstract interfaces and protocols for dependency injection.

All components depend only on these contracts.
Implementations are injected at assembly time.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


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


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MemoryType(str, Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    STRUCTURED = "structured"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Message:
    """Immutable chat message."""
    role: Role
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    """Assembled context for a single request."""
    messages: List[Message] = field(default_factory=list)
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    domain_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    """Result of intent classification."""
    intent: Intent
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    tool_hint: Optional[str] = None


@dataclass
class TaskStep:
    """A single step in an execution plan."""
    id: str
    tool_name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Ordered list of steps to fulfill a request."""
    steps: List[TaskStep] = field(default_factory=list)
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningResult:
    """Output of the reasoning engine."""
    chain_of_thought: List[str] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.0
    adjustments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FormattedResponse:
    """Final formatted output."""
    text: str
    format: OutputFormat = OutputFormat.TEXT
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryEntry:
    """A single memory record."""
    key: str
    content: str
    memory_type: MemoryType
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core Interfaces (ABCs)
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Abstraction over the language model backend."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
    ) -> str:
        """Send a prompt to the LLM and return the raw text response."""
        ...

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Prompt the LLM expecting a JSON dict response."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend is reachable and healthy."""
        ...


class Tool(ABC):
    """Base contract for any tool the agent can invoke."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description shown to the planner."""
        ...

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """JSON-Schema describing accepted parameters. Empty dict by default."""
        return {}

    @abstractmethod
    def execute(self, parameters: Dict[str, Any], context: Context) -> ToolResult:
        """Run the tool and return a result."""
        ...

    def validate_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        """Return a list of validation error messages. Empty list = valid."""
        return []


class MemoryStore(ABC):
    """Persistent conversation and knowledge memory."""

    @abstractmethod
    def save(self, entry: MemoryEntry) -> None:
        """Persist a memory entry."""
        ...

    @abstractmethod
    def retrieve(
        self,
        query: str,
        *,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[MemoryEntry]:
        """Retrieve relevant memories, ranked by relevance score."""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a memory entry by key. Returns True if found."""
        ...

    @abstractmethod
    def clear(self, memory_type: Optional[MemoryType] = None) -> int:
        """Clear entries. Returns count deleted."""
        ...


class ContextBuilder(ABC):
    """Assembles context from available data sources."""

    @abstractmethod
    def build(self, user_message: str, conversation_id: Optional[str] = None,
              user_id: Optional[str] = None, **kwargs: Any) -> Context:
        """Build and return a fully populated Context."""
        ...


class Planner(ABC):
    """Decomposes a request into an ordered execution plan."""

    @abstractmethod
    def create_plan(self, context: Context, route: RouteResult) -> ExecutionPlan:
        """Analyse the request and return a step-by-step plan."""
        ...


class Reasoner(ABC):
    """Applies chain-of-thought reasoning to validate or refine a plan."""

    @abstractmethod
    def reason(self, context: Context, plan: ExecutionPlan) -> ReasoningResult:
        """Reason about the plan, returning chain-of-thought and adjustments."""
        ...

    def refine_plan(self, plan: ExecutionPlan, result: ReasoningResult) -> ExecutionPlan:
        """Optionally adjust a plan based on reasoning. Default: no-op."""
        return plan


class Router(ABC):
    """Classifies user intent and selects target tools."""

    @abstractmethod
    def classify(self, context: Context) -> RouteResult:
        """Classify the user's intent and return a routing decision."""
        ...


class Executor(ABC):
    """Runs the steps of an execution plan."""

    @abstractmethod
    def execute(self, plan: ExecutionPlan, context: Context) -> List[ToolResult]:
        """Execute all steps in order, returning results."""
        ...

    @abstractmethod
    def execute_step(self, step: TaskStep, context: Context) -> ToolResult:
        """Execute a single step."""
        ...


class Formatter(ABC):
    """Transforms raw results into a user-facing response."""

    @abstractmethod
    def format(
        self,
        results: List[ToolResult],
        context: Context,
        reasoning: Optional[ReasoningResult] = None,
        *,
        output_format: OutputFormat = OutputFormat.TEXT,
    ) -> FormattedResponse:
        """Format tool results into a polished response."""
        ...


class Agent(ABC):
    """Top-level agent interface — the only entry point for external callers."""

    @abstractmethod
    def handle(
        self,
        user_message: str,
        *,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> FormattedResponse:
        """Process a user message end-to-end and return a formatted response."""
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return component health status."""
        ...
