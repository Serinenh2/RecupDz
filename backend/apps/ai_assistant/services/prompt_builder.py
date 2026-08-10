"""
Prompt Builder — constructs messages and payloads for the Ollama API.

Supports:
    - System/user/assistant message construction
    - Tool definitions (OpenAI-compatible format for Hermes 3)
    - Chat payload assembly
    - Generate payload assembly
    - Conversation history management
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single chat message."""
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d


# ---------------------------------------------------------------------------
# Tool Definition
# ---------------------------------------------------------------------------

@dataclass
class ToolDefinition:
    """A tool exposed to the LLM for function calling."""
    name: str
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }


# ---------------------------------------------------------------------------
# Prompt Builder
# ---------------------------------------------------------------------------

class PromptBuilder:
    """
    Fluent builder for Ollama API payloads.

    Usage:
        payload = (
            PromptBuilder()
            .model("hermes3:latest")
            .system("You are a helpful assistant.")
            .user("What is the capital of France?")
            .temperature(0.7)
            .stream(True)
            .build_chat()
        )
    """

    def __init__(self) -> None:
        self._model: str = ""
        self._messages: List[Message] = []
        self._tools: List[ToolDefinition] = []
        self._temperature: Optional[float] = None
        self._max_tokens: Optional[int] = None
        self._stream: bool = False
        self._format_json: bool = False
        self._format_schema: Optional[Dict[str, Any]] = None
        self._stop: List[str] = []
        self._extra_options: Dict[str, Any] = {}

    # -- model --

    def model(self, model: str) -> PromptBuilder:
        self._model = model
        return self

    # -- messages --

    def system(self, content: str) -> PromptBuilder:
        self._messages.append(Message(role="system", content=content))
        return self

    def user(self, content: str) -> PromptBuilder:
        self._messages.append(Message(role="user", content=content))
        return self

    def assistant(self, content: str) -> PromptBuilder:
        self._messages.append(Message(role="assistant", content=content))
        return self

    def assistant_tool_calls(self, content: str, tool_calls: List[Dict[str, Any]]) -> PromptBuilder:
        self._messages.append(Message(role="assistant", content=content, tool_calls=tool_calls))
        return self

    def tool_result(self, content: str, tool_call_id: str = "") -> PromptBuilder:
        self._messages.append(Message(role="tool", content=content, tool_call_id=tool_call_id))
        return self

    def messages(self, messages: List[Message]) -> PromptBuilder:
        self._messages.extend(messages)
        return self

    def clear_messages(self) -> PromptBuilder:
        self._messages.clear()
        return self

    def last_user_message(self) -> Optional[str]:
        for msg in reversed(self._messages):
            if msg.role == "user":
                return msg.content
        return None

    # -- tools --

    def tool(self, name: str, description: str = "", parameters: Optional[Dict[str, Any]] = None) -> PromptBuilder:
        self._tools.append(ToolDefinition(name=name, description=description, parameters=parameters or {}))
        return self

    def tools(self, tool_defs: List[ToolDefinition]) -> PromptBuilder:
        self._tools.extend(tool_defs)
        return self

    def tool_from_schema(self, schema: Dict[str, Any]) -> PromptBuilder:
        """
        Add a tool from a full OpenAI-compatible tool schema dict.
        Expected: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        func = schema.get("function", schema)
        self._tools.append(ToolDefinition(
            name=func.get("name", ""),
            description=func.get("description", ""),
            parameters=func.get("parameters", {}),
        ))
        return self

    def tools_from_dicts(self, schemas: List[Dict[str, Any]]) -> PromptBuilder:
        for s in schemas:
            self.tool_from_schema(s)
        return self

    # -- options --

    def temperature(self, temp: float) -> PromptBuilder:
        self._temperature = temp
        return self

    def max_tokens(self, tokens: int) -> PromptBuilder:
        self._max_tokens = tokens
        return self

    def stream(self, enabled: bool = True) -> PromptBuilder:
        self._stream = enabled
        return self

    def json_mode(self, schema: Optional[Dict[str, Any]] = None) -> PromptBuilder:
        """Enable JSON output mode. Optional schema for structured output."""
        self._format_json = True
        self._format_schema = schema
        return self

    def stop_sequences(self, sequences: List[str]) -> PromptBuilder:
        self._stop = sequences
        return self

    def option(self, key: str, value: Any) -> PromptBuilder:
        self._extra_options[key] = value
        return self

    # -- build --

    def build_chat(self) -> Dict[str, Any]:
        """Build the full payload for POST /api/chat."""
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": [m.to_dict() for m in self._messages],
            "stream": self._stream,
        }
        options = self._build_options()
        if options:
            payload["options"] = options
        if self._tools:
            payload["tools"] = [t.to_dict() for t in self._tools]
        if self._format_json:
            if self._format_schema:
                payload["format"] = self._format_schema
            else:
                payload["format"] = "json"
        return payload

    def build_generate(self) -> Dict[str, Any]:
        """Build the full payload for POST /api/generate."""
        prompt_parts: List[str] = []
        system: Optional[str] = None
        for msg in self._messages:
            if msg.role == "system":
                system = msg.content
            elif msg.role == "user":
                prompt_parts.append(msg.content)
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")

        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": "\n".join(prompt_parts),
            "stream": self._stream,
        }
        if system:
            payload["system"] = system
        options = self._build_options()
        if options:
            payload["options"] = options
        if self._format_json:
            payload["format"] = "json"
        return payload

    def build_messages(self) -> List[Dict[str, Any]]:
        """Return just the messages list as dicts."""
        return [m.to_dict() for m in self._messages]

    # -- internal --

    def _build_options(self) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        if self._temperature is not None:
            opts["temperature"] = self._temperature
        if self._max_tokens is not None:
            opts["num_predict"] = self._max_tokens
        if self._stop:
            opts["stop"] = self._stop
        opts.update(self._extra_options)
        return opts

    def reset(self) -> PromptBuilder:
        """Reset builder state for reuse."""
        self._messages.clear()
        self._tools.clear()
        self._temperature = None
        self._max_tokens = None
        self._stream = False
        self._format_json = False
        self._format_schema = None
        self._stop.clear()
        self._extra_options.clear()
        return self

    def clone(self) -> PromptBuilder:
        """Create an independent copy."""
        import copy as _copy
        return _copy.deepcopy(self)


# ---------------------------------------------------------------------------
# Convenience Builders
# ---------------------------------------------------------------------------

def simple_prompt(
    user_message: str,
    *,
    system_prompt: str = "",
    model: str = "",
) -> Dict[str, Any]:
    """Build a minimal chat payload."""
    builder = PromptBuilder()
    if model:
        builder.model(model)
    if system_prompt:
        builder.system(system_prompt)
    builder.user(user_message)
    return builder.build_chat()


def tool_chat(
    user_message: str,
    tools: List[Dict[str, Any]],
    *,
    system_prompt: str = "",
    model: str = "",
    history: Optional[List[Message]] = None,
) -> Dict[str, Any]:
    """Build a chat payload with tool definitions."""
    builder = PromptBuilder()
    if model:
        builder.model(model)
    if system_prompt:
        builder.system(system_prompt)
    if history:
        builder.messages(history)
    builder.user(user_message)
    builder.tools_from_dicts(tools)
    return builder.build_chat()
