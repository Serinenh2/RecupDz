"""
Streaming Response Handler — processes Ollama's newline-delimited JSON streams.

Ollama streams JSON objects one per line. This module:
    - Reads lines from the HTTP response
    - Parses each line into a ParsedResponse chunk
    - Optionally accumulates into a full response
    - Supports callbacks for real-time token delivery
"""

from __future__ import annotations

import json as _json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional

from apps.ai_assistant.services.response_parser import ParsedResponse, ResponseParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stream Chunk
# ---------------------------------------------------------------------------

@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""
    index: int
    response: ParsedResponse
    elapsed_seconds: float = 0.0

    @property
    def token(self) -> str:
        return self.response.content

    @property
    def is_final(self) -> bool:
        return self.response.done


# ---------------------------------------------------------------------------
# Stream Accumulator
# ---------------------------------------------------------------------------

@dataclass
class StreamAccumulator:
    """Builds a complete ParsedResponse from streaming chunks."""
    content_parts: List[str] = field(default_factory=list)
    tool_calls_raw: List[Dict[str, Any]] = field(default_factory=list)
    final_response: Optional[Dict[str, Any]] = None
    chunk_count: int = 0
    total_eval_count: int = 0

    def add(self, chunk: ParsedResponse) -> None:
        self.chunk_count += 1
        if chunk.content:
            self.content_parts.append(chunk.content)
        if chunk.raw.get("done") and not chunk.raw.get("message", {}).get("content"):
            self.final_response = chunk.raw
            self.total_eval_count = chunk.raw.get("eval_count", 0)

    def build(self) -> ParsedResponse:
        content = "".join(self.content_parts)
        if self.final_response:
            return ResponseParser.parse_chat_response(self.final_response)
        return ParsedResponse(
            content=content,
            done=True,
            eval_count=self.total_eval_count,
        )


# ---------------------------------------------------------------------------
# Stream Handler
# ---------------------------------------------------------------------------

# Type alias for the optional per-token callback
TokenCallback = Callable[[StreamChunk], None]


class StreamHandler:
    """
    Reads and processes a streaming Ollama response.

    Usage:
        handler = StreamHandler()
        for chunk in handler.iter_chunks(response_iter):
            print(chunk.token, end="", flush=True)
        full = handler.get_full_response()
    """

    def __init__(
        self,
        on_token: Optional[TokenCallback] = None,
        accumulate: bool = True,
    ) -> None:
        self._on_token = on_token
        self._accumulate = accumulate
        self._accumulator = StreamAccumulator() if accumulate else None
        self._chunks: List[StreamChunk] = []
        self._start_time: float = 0.0

    def iter_chunks(
        self,
        raw_iterator: Iterator[bytes],
    ) -> Iterator[StreamChunk]:
        """
        Yield StreamChunks from raw byte lines.

        Args:
            raw_iterator: Iterator of byte-lines from the HTTP response.

        Yields:
            StreamChunk objects as they arrive.
        """
        self._start_time = time.monotonic()
        index = 0

        for line_bytes in raw_iterator:
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                raw = _json.loads(line)
            except _json.JSONDecodeError as exc:
                logger.warning("Failed to parse stream line %d: %s — %s", index, line[:100], exc)
                continue

            parsed = ResponseParser.parse_stream_chunk(raw)
            elapsed = time.monotonic() - self._start_time

            chunk = StreamChunk(index=index, response=parsed, elapsed_seconds=elapsed)

            if self._accumulate and self._accumulator is not None:
                self._accumulator.add(parsed)

            self._chunks.append(chunk)

            if self._on_token is not None:
                try:
                    self._on_token(chunk)
                except Exception as exc:
                    logger.error("Token callback error: %s", exc)

            index += 1

            yield chunk

            if parsed.done:
                break

        logger.debug("Stream complete: %d chunks in %.3fs", index, time.monotonic() - self._start_time)

    def get_full_response(self) -> ParsedResponse:
        """Return the accumulated full response after iteration completes."""
        if self._accumulator is not None:
            return self._accumulator.build()
        # Fallback: concatenate from chunks
        content = "".join(c.token for c in self._chunks)
        return ParsedResponse(content=content, done=True)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def total_elapsed(self) -> float:
        if not self._chunks:
            return 0.0
        return self._chunks[-1].elapsed_seconds


# ---------------------------------------------------------------------------
# Streaming Utilities
# ---------------------------------------------------------------------------

class StreamCollector:
    """
    Collects all streaming output into a list of tokens.
    Useful for simple "get the full response" use cases.
    """

    def __init__(self) -> None:
        self._tokens: List[str] = []
        self._done = False

    def collect(self, chunk: StreamChunk) -> None:
        if chunk.token:
            self._tokens.append(chunk.token)
        if chunk.is_final:
            self._done = True

    @property
    def text(self) -> str:
        return "".join(self._tokens)

    @property
    def is_done(self) -> bool:
        return self._done

    def reset(self) -> None:
        self._tokens.clear()
        self._done = False
