"""
Services Layer — production Ollama integration.

Provides: OllamaService (HTTP), ChatService (multi-turn), PromptBuilder,
StreamHandler, and ResponseParser.
"""

from apps.ai_assistant.services.ollama_service import (
    OllamaConfig,
    OllamaConnectionError,
    OllamaError,
    OllamaModelNotFoundError,
    OllamaService,
    OllamaTimeoutError,
)
from apps.ai_assistant.services.chat_service import (
    ChatService,
    ChatSession,
    ToolCallRequest,
    ToolCallResult,
)
from apps.ai_assistant.services.prompt_builder import (
    Message,
    PromptBuilder,
    ToolDefinition,
    simple_prompt,
    tool_chat,
)
from apps.ai_assistant.services.response_parser import (
    ParsedResponse,
    ResponseParser,
    ToolCall,
)
from apps.ai_assistant.services.streaming import (
    StreamAccumulator,
    StreamChunk,
    StreamCollector,
    StreamHandler,
)

__all__ = [
    "OllamaService",
    "OllamaConfig",
    "OllamaError",
    "OllamaConnectionError",
    "OllamaTimeoutError",
    "OllamaModelNotFoundError",
    "ChatService",
    "ChatSession",
    "ToolCallRequest",
    "ToolCallResult",
    "PromptBuilder",
    "Message",
    "ToolDefinition",
    "simple_prompt",
    "tool_chat",
    "ResponseParser",
    "ParsedResponse",
    "ToolCall",
    "StreamHandler",
    "StreamChunk",
    "StreamAccumulator",
    "StreamCollector",
]
