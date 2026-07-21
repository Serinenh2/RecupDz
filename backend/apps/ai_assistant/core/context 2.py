"""
Context Builder — assembles the full context for a request.

Pulls together: conversation history, user profile, entity data, domain data.
All via injected dependencies — the builder itself knows nothing about domains.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.core.interfaces import Context, Message, Role

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Provider Protocol (injected)
# ---------------------------------------------------------------------------

class DataProvider:
    """
    Pluggable data provider.

    Register callables that return domain data keyed by entity type.
    The core module does not know what these callables do —
    they are assembled at the application level.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, Callable[[str], Dict[str, Any]]] = {}

    def register(self, entity_type: str, provider: Callable[[str], Dict[str, Any]]) -> None:
        self._providers[entity_type] = provider
        logger.debug("DataProvider registered: %s", entity_type)

    def get(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        provider = self._providers.get(entity_type)
        if provider is None:
            logger.warning("No provider for entity_type='%s'", entity_type)
            return {}
        try:
            return provider(entity_id)
        except Exception as exc:
            logger.error("DataProvider error for %s/%s: %s", entity_type, entity_id, exc)
            return {"error": str(exc)}

    @property
    def available_types(self) -> List[str]:
        return list(self._providers.keys())


# ---------------------------------------------------------------------------
# Context Builder Implementation
# ---------------------------------------------------------------------------

class DefaultContextBuilder:
    """
    Builds a Context from available sources.

    Dependencies are injected via constructor for full DI compliance.
    """

    def __init__(
        self,
        *,
        data_provider: Optional[DataProvider] = None,
        memory_getter: Optional[Callable[[str], List[Message]]] = None,
        metadata_provider: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        self._data_provider = data_provider or DataProvider()
        self._memory_getter = memory_getter
        self._metadata_provider = metadata_provider

    def build(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Context:
        messages: List[Message] = []

        # 1. Conversation history from memory
        if conversation_id and self._memory_getter:
            messages = self._memory_getter(conversation_id)
            logger.debug("Context: loaded %d history messages for conv=%s", len(messages), conversation_id)

        # 2. Current user message
        messages.append(Message(role=Role.USER, content=user_message))

        # 3. Entity data (optional)
        entity_type = kwargs.get("entity_type")
        entity_id = kwargs.get("entity_id")
        domain_data: Dict[str, Any] = {}
        if entity_type and entity_id:
            domain_data = self._data_provider.get(entity_type, entity_id)
            logger.debug("Context: loaded domain data for %s/%s", entity_type, entity_id)

        # 4. Extra metadata from caller
        extra_metadata = kwargs.get("metadata", {})
        if self._metadata_provider and conversation_id:
            try:
                extra_metadata = {**self._metadata_provider(conversation_id), **extra_metadata}
            except Exception as exc:
                logger.warning("Metadata provider error: %s", exc)

        ctx = Context(
            messages=messages,
            user_id=user_id,
            conversation_id=conversation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            domain_data=domain_data,
            metadata=extra_metadata,
        )
        logger.info(
            "Context built: %d messages, entity=%s/%s, user=%s",
            len(messages),
            entity_type or "none",
            entity_id or "none",
            user_id or "anonymous",
        )
        return ctx
