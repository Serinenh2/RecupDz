"""
Ollama Service — HTTP client for the Ollama API.

Endpoint: POST http://localhost:11434/api/chat
Offline only. Uses the `requests` library.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OllamaConfig:
    """Connection and model settings."""
    base_url: str = "http://localhost:11434"
    model: str = "hermes3"
    timeout_seconds: int = 120
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    backoff_factor: float = 2.0

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    @property
    def tags_url(self) -> str:
        return f"{self.base_url}/api/tags"


class OllamaError(Exception):
    """Base exception for Ollama service errors."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class OllamaConnectionError(OllamaError):
    """Cannot reach Ollama server."""
    pass


class OllamaTimeoutError(OllamaError):
    """Request timed out."""
    pass


class OllamaModelNotFoundError(OllamaError):
    """Requested model is not available."""
    pass


class OllamaService:
    """
    Production Ollama client.

    Usage:
        ollama = OllamaService()
        reply = ollama.chat("What are hazardous wastes?")
        reply = ollama.chat(
            "Summarize this",
            history=[{"role": "user", "content": "Tell me about BSDs"},
                     {"role": "assistant", "content": "BSD stands for..."}],
            system_prompt="You are a waste management expert.",
        )
    """

    def __init__(
        self,
        config: Optional[OllamaConfig] = None,
        base_url: str = "http://localhost:11434",
        model: str = "hermes3",
        timeout: int = 120,
    ) -> None:
        if config:
            self._base_url = config.base_url.rstrip("/")
            self._model = config.model
            self._timeout = config.timeout_seconds
            self._max_retries = config.max_retries
            self._retry_delay = config.retry_delay_seconds
            self._backoff_factor = config.backoff_factor
        else:
            self._base_url = base_url.rstrip("/")
            self._model = model
            self._timeout = timeout
            self._max_retries = 2
            self._retry_delay = 1.0
            self._backoff_factor = 2.0
        self._session = requests.Session()
        self._chat_url = f"{self._base_url}/api/chat"
        self._tags_url = f"{self._base_url}/api/tags"
        logger.info("OllamaService initialized: url=%s model=%s", self._base_url, self._model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Send a chat message and return the assistant response text.

        Args:
            message: The user message.
            history: Optional conversation history, list of
                     {"role": "user"|"assistant", "content": "..."} dicts.
            system_prompt: Optional system-level instruction.
            temperature: Optional sampling temperature (0.0-2.0).
            max_tokens: Optional max tokens to generate.

        Returns:
            The assistant response as a plain string.

        Raises:
            OllamaConnectionError: Cannot reach Ollama.
            OllamaTimeoutError: Request timed out.
            OllamaModelNotFoundError: Model not found (HTTP 404).
            OllamaError: Any other HTTP or response error.
        """
        messages = self._build_messages(message, history, system_prompt)
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }
        if temperature is not None:
            payload["options"] = payload.get("options", {})
            payload["options"]["temperature"] = temperature
        if max_tokens is not None:
            payload["options"] = payload.get("options", {})
            payload["options"]["num_predict"] = max_tokens

        last_exc: Optional[Exception] = None
        max_retries = self._max_retries
        delay = self._retry_delay

        for attempt in range(max_retries + 1):
            logger.info(
                "Chat request: model=%s, messages=%d, attempt=%d/%d",
                self._model, len(messages), attempt + 1, max_retries + 1,
            )

            try:
                response = self._session.post(
                    self._chat_url,
                    json=payload,
                    timeout=self._timeout,
                )
            except requests.ConnectionError as exc:
                last_exc = OllamaConnectionError(
                    f"Cannot connect to Ollama at {self._base_url}: {exc}"
                )
                logger.warning(
                    "Ollama connection failed (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1, exc,
                )
                if attempt < max_retries:
                    import time as _time
                    _time.sleep(delay)
                    delay *= self._backoff_factor
                    continue
                raise last_exc from exc
            except requests.Timeout as exc:
                last_exc = OllamaTimeoutError(
                    f"Ollama request timed out after {self._timeout}s"
                )
                logger.warning(
                    "Ollama timeout (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1, exc,
                )
                if attempt < max_retries:
                    import time as _time
                    _time.sleep(delay)
                    delay *= self._backoff_factor
                    continue
                raise last_exc from exc
            except requests.RequestException as exc:
                last_exc = OllamaError(f"Ollama request failed: {exc}")
                logger.warning(
                    "Ollama request error (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1, exc,
                )
                if attempt < max_retries:
                    import time as _time
                    _time.sleep(delay)
                    delay *= self._backoff_factor
                    continue
                raise last_exc from exc

            if response.status_code == 404:
                raise OllamaModelNotFoundError(
                    f"Model '{self._model}' not found. "
                    f"Pull it with: ollama pull {self._model}"
                )

            if response.status_code != 200:
                body = response.text[:500]
                logger.error("Ollama HTTP %d: %s", response.status_code, body)
                raise OllamaError(
                    f"Ollama returned HTTP {response.status_code}: {body}",
                    status_code=response.status_code,
                )

            try:
                data = response.json()
            except ValueError as exc:
                logger.error("Failed to parse Ollama response: %s", exc)
                raise OllamaError("Invalid JSON from Ollama") from exc

            assistant_content = (
                data.get("message", {}).get("content", "")
            )

            logger.info("Chat response: %d chars", len(assistant_content))
            return assistant_content

        raise last_exc or OllamaError("All retry attempts exhausted")

    def is_available(self) -> bool:
        """Health check — can we reach Ollama?"""
        try:
            resp = self._session.get(self._tags_url, timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> List[str]:
        """List available model names."""
        try:
            resp = self._session.get(self._tags_url, timeout=5)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m.get("name", "") for m in models]
        except requests.RequestException as exc:
            logger.warning("Failed to list models: %s", exc)
            return []

    def health(self) -> Dict[str, Any]:
        """Detailed health info."""
        import time
        start = time.monotonic()
        available = self.is_available()
        latency_ms = (time.monotonic() - start) * 1000
        return {
            "status": "healthy" if available else "unavailable",
            "base_url": self._base_url,
            "model": self._model,
            "latency_ms": round(latency_ms, 1),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        """Build the messages list for the API request."""
        messages: List[Dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})
        return messages
