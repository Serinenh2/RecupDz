"""
Chat Service — high-level chat abstraction over OllamaService.

Manages: multi-turn conversations, tool-calling loops,
response accumulation, and the LLMProvider interface bridge.
"""

from __future__ import annotations

import json as _json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.services.ollama_service import OllamaConfig, OllamaError, OllamaService
from apps.ai_assistant.services.prompt_builder import Message, PromptBuilder, ToolDefinition
from apps.ai_assistant.services.response_parser import ParsedResponse, ResponseParser, ToolCall
from apps.ai_assistant.services.streaming import StreamChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chat Session
# ---------------------------------------------------------------------------

@dataclass
class ChatSession:
    """Stateful multi-turn conversation."""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: List[Message] = field(default_factory=list)
    system_prompt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_user(self, content: str) -> None:
        self.messages.append(Message(role="user", content=content))

    def add_assistant(self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
        self.messages.append(Message(role="assistant", content=content, tool_calls=tool_calls or []))

    def add_tool_result(self, content: str, tool_call_id: str = "") -> None:
        self.messages.append(Message(role="tool", content=content, tool_call_id=tool_call_id))

    def get_history_dicts(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        if self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})
        result.extend(m.to_dict() for m in self.messages)
        return result

    def clear(self) -> None:
        self.messages.clear()

    @property
    def message_count(self) -> int:
        return len(self.messages)


# ---------------------------------------------------------------------------
# Tool Call Result
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRequest:
    """A tool call requested by the model."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolCallResult:
    """Result of executing a tool call."""
    tool_call_id: str
    name: str
    content: str
    success: bool = True


# ---------------------------------------------------------------------------
# Chat Service
# ---------------------------------------------------------------------------

# Type alias for the tool executor callback
ToolExecutorFn = Callable[[ToolCallRequest], ToolCallResult]


class ChatService:
    """
    High-level chat service.

    Features:
        - Multi-turn conversation management
        - Automatic tool-calling loops (call → execute → feed back → repeat)
        - Streaming support
        - JSON mode
        - LLMProvider interface bridge
    """

    def __init__(
        self,
        ollama: Optional[OllamaService] = None,
        config: Optional[OllamaConfig] = None,
    ) -> None:
        self._ollama = ollama or OllamaService(config)
        self._sessions: Dict[str, ChatSession] = {}

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def create_session(
        self,
        system_prompt: str = "",
        session_id: Optional[str] = None,
    ) -> ChatSession:
        sid = session_id or uuid.uuid4().hex[:12]
        session = ChatSession(session_id=sid, system_prompt=system_prompt)
        self._sessions[sid] = session
        logger.info("Chat session created: %s", sid)
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Simple Chat (no history)
    # ------------------------------------------------------------------

    def chat(
        self,
        user_message: str,
        *,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **options: Any,
    ) -> ParsedResponse:
        """Single-turn chat — no history, no tool calling."""
        return self._ollama.chat_simple(
            user_message,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **options,
        )

    def chat_stream(
        self,
        user_message: str,
        *,
        system_prompt: str = "",
        model: Optional[str] = None,
        on_token: Optional[Callable[[StreamChunk], None]] = None,
        **options: Any,
    ) -> ParsedResponse:
        """Single-turn streaming chat."""
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        return self._ollama.chat(
            messages,
            model=model,
            stream=True,
            on_token=on_token,
            **options,
        )

    # ------------------------------------------------------------------
    # Multi-Turn Chat (with session)
    # ------------------------------------------------------------------

    def send(
        self,
        session_id: str,
        user_message: str,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[ToolExecutorFn] = None,
        max_tool_rounds: int = 5,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        on_token: Optional[Callable[[StreamChunk], None]] = None,
        **options: Any,
    ) -> ParsedResponse:
        """
        Send a message in a session.

        If tools are provided and the model returns tool_calls, this will:
        1. Call tool_executor for each tool call
        2. Feed results back to the model
        3. Repeat until the model stops calling tools or max_tool_rounds is reached
        """
        session = self._sessions.get(session_id)
        if session is None:
            session = self.create_session(session_id=session_id)

        session.add_user(user_message)
        messages = session.get_history_dicts()

        for round_idx in range(max_tool_rounds + 1):
            response = self._ollama.chat(
                messages,
                model=model,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                on_token=on_token,
                **options,
            )

            # No tool calls — we're done
            if not response.has_tool_calls:
                session.add_assistant(response.content)
                return response

            # Model wants tool calls
            if tool_executor is None:
                logger.warning("Model returned tool_calls but no tool_executor provided")
                session.add_assistant(response.content, tool_calls=[tc.to_dict() for tc in response.tool_calls])
                return response

            # Add assistant message with tool_calls to history
            assistant_tool_calls = [tc.to_dict() for tc in response.tool_calls]
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": assistant_tool_calls,
            })

            # Execute each tool call
            for tc in response.tool_calls:
                request = ToolCallRequest(id=tc.id, name=tc.name, arguments=tc.arguments)
                try:
                    result = tool_executor(request)
                except Exception as exc:
                    logger.error("Tool execution failed for '%s': %s", tc.name, exc)
                    result = ToolCallResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=f"Error: {exc}",
                        success=False,
                    )

                tool_msg = {"role": "tool", "content": result.content}
                if tc.id:
                    tool_msg["tool_call_id"] = tc.id
                messages.append(tool_msg)
                session.add_tool_result(result.content, tc.id)

            logger.debug("Tool round %d/%d complete: %d calls executed", round_idx + 1, max_tool_rounds, len(response.tool_calls))

        # Exhausted tool rounds — return last response
        session.add_assistant(response.content)
        return response

    # ------------------------------------------------------------------
    # JSON Mode
    # ------------------------------------------------------------------

    def chat_json(
        self,
        user_message: str,
        *,
        system_prompt: str = "",
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **options: Any,
    ) -> Dict[str, Any]:
        """Chat expecting a JSON dict response."""
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        response = self._ollama.chat(
            messages,
            model=model,
            json_mode=True,
            json_schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
            **options,
        )
        return ResponseParser.extract_json(response.content)

    # ------------------------------------------------------------------
    # LLMProvider Bridge
    # ------------------------------------------------------------------

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
    ) -> str:
        """Bridge to LLMProvider.generate()."""
        return self._ollama.generate_text(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )

    def generate_structured(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Bridge to LLMProvider.generate_structured()."""
        return self._ollama.generate_json(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def is_available(self) -> bool:
        return self._ollama.is_available()

    def health(self) -> Dict[str, Any]:
        return self._ollama.health()
