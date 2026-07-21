"""
Response Parser — extracts structured data from Ollama outputs.

Handles: raw text, JSON extraction, tool-call parsing, error detection,
and markdown-fence stripping.
"""

from __future__ import annotations

import json as _json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parsed Output
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """A single tool-call extracted from the model output."""
    id: str = ""
    name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }


@dataclass
class ParsedResponse:
    """Fully parsed Ollama response."""
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""
    total_duration_ns: int = 0
    eval_count: int = 0
    done: bool = True

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def duration_seconds(self) -> float:
        return self.total_duration_ns / 1_000_000_000 if self.total_duration_ns else 0.0

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"content": self.content}
        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        result["finish_reason"] = self.finish_reason
        result["done"] = self.done
        if self.duration_seconds:
            result["duration_seconds"] = round(self.duration_seconds, 3)
        if self.eval_count:
            result["eval_count"] = self.eval_count
        return result


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ResponseParser:
    """Stateless parser for Ollama API responses."""

    # -- public --

    @staticmethod
    def parse_chat_response(raw: Dict[str, Any]) -> ParsedResponse:
        """Parse a /api/chat response (non-streaming or final chunk)."""
        message = raw.get("message", {})
        content = message.get("content", "")
        tool_calls_raw = message.get("tool_calls", [])

        tool_calls = [
            ResponseParser._parse_tool_call(tc) for tc in tool_calls_raw
        ]

        return ParsedResponse(
            content=content,
            tool_calls=tool_calls,
            raw=raw,
            finish_reason=ResponseParser._extract_finish_reason(raw),
            total_duration_ns=raw.get("total_duration", 0),
            eval_count=raw.get("eval_count", 0),
            done=raw.get("done", True),
        )

    @staticmethod
    def parse_generate_response(raw: Dict[str, Any]) -> ParsedResponse:
        """Parse a /api/generate response."""
        return ParsedResponse(
            content=raw.get("response", ""),
            raw=raw,
            total_duration_ns=raw.get("total_duration", 0),
            eval_count=raw.get("eval_count", 0),
            done=raw.get("done", True),
        )

    @staticmethod
    def parse_stream_chunk(raw: Dict[str, Any]) -> ParsedResponse:
        """Parse a single streaming chunk."""
        message = raw.get("message", {})
        return ParsedResponse(
            content=message.get("content", ""),
            raw=raw,
            done=raw.get("done", False),
        )

    # -- JSON extraction --

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        """
        Extract a JSON object from LLM output.
        Strips markdown fences, finds first {…} block.
        """
        cleaned = ResponseParser._strip_markdown_fences(text)
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end <= start:
            raise ValueError(f"No JSON object found in: {text[:300]}")
        try:
            return _json.loads(cleaned[start:end])
        except _json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

    @staticmethod
    def extract_json_array(text: str) -> List[Any]:
        """Extract a JSON array from LLM output."""
        cleaned = ResponseParser._strip_markdown_fences(text)
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start == -1 or end <= start:
            raise ValueError(f"No JSON array found in: {text[:300]}")
        try:
            return _json.loads(cleaned[start:end])
        except _json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON array: {exc}") from exc

    @staticmethod
    def try_parse_json(text: str) -> Optional[Dict[str, Any]]:
        """Attempt JSON parse, returning None on failure."""
        try:
            return ResponseParser.extract_json(text)
        except ValueError:
            return None

    # -- tool-call parsing --

    @staticmethod
    def _parse_tool_call(raw: Dict[str, Any]) -> ToolCall:
        """Parse a single Ollama tool-call entry."""
        func = raw.get("function", {})
        args_raw = func.get("arguments", {})
        if isinstance(args_raw, str):
            try:
                args_raw = _json.loads(args_raw)
            except (_json.JSONDecodeError, TypeError):
                args_raw = {"raw": args_raw}
        return ToolCall(
            id=raw.get("id", ""),
            name=func.get("name", ""),
            arguments=args_raw if isinstance(args_raw, dict) else {},
        )

    @staticmethod
    def _extract_finish_reason(raw: Dict[str, Any]) -> str:
        done = raw.get("done")
        if done is True:
            return "stop"
        message = raw.get("message", {})
        if message.get("tool_calls"):
            return "tool_calls"
        return ""

    # -- helpers --

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove ```json ... ``` fences."""
        pattern = re.compile(r"```(?:json)?\s*\n?", re.IGNORECASE)
        return pattern.sub("", text).strip()

    @staticmethod
    def is_error_response(raw: Dict[str, Any]) -> bool:
        return "error" in raw

    @staticmethod
    def get_error_message(raw: Dict[str, Any]) -> str:
        return raw.get("error", "Unknown Ollama error")
