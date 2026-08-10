"""
Tool Factory — creates tool instances from configuration dicts.

Supports:
    - Creating tools from Python class paths
    - Creating tools from declarative config dicts
    - Batch-creating tool sets
    - Lazy loading / deferred instantiation
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config Schema
# ---------------------------------------------------------------------------

@dataclass
class ToolConfig:
    """Declarative tool configuration."""
    name: str
    class_path: str  # "apps.ai_assistant.tools.builtin.echo.EchoTool"
    description: str = ""
    enabled: bool = True
    permissions: List[str] = field(default_factory=list)
    timeout: float = 30.0
    tags: List[str] = field(default_factory=list)
    init_params: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class ToolFactoryError(Exception):
    pass


class ToolFactory:
    """
    Creates BaseTool instances from configuration.

    Two modes:
        1. Class-path based: resolves a dotted Python path to a class
        2. Config-based: creates a tool from a ToolConfig dataclass
    """

    _custom_creators: Dict[str, Callable[..., BaseTool]] = {}

    # ------------------------------------------------------------------
    # Class-based creation
    # ------------------------------------------------------------------

    @staticmethod
    def create_from_class_path(
        class_path: str,
        init_params: Optional[Dict[str, Any]] = None,
    ) -> BaseTool:
        """
        Instantiate a tool from a dotted class path.

        Args:
            class_path: e.g. "apps.ai_assistant.tools.builtin.echo.EchoTool"
            init_params: kwargs passed to __init__

        Returns:
            An instance of the tool.

        Raises:
            ToolFactoryError if the class cannot be resolved or instantiated.
        """
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as exc:
            raise ToolFactoryError(
                f"Cannot resolve class '{class_path}': {exc}"
            ) from exc

        if not (isinstance(cls, type) and issubclass(cls, BaseTool)):
            raise ToolFactoryError(
                f"'{class_path}' is not a BaseTool subclass"
            )

        try:
            instance = cls(**(init_params or {}))
        except Exception as exc:
            raise ToolFactoryError(
                f"Cannot instantiate '{class_path}': {exc}"
            ) from exc

        return instance

    # ------------------------------------------------------------------
    # Config-based creation
    # ------------------------------------------------------------------

    @classmethod
    def create_from_config(cls, config: ToolConfig) -> BaseTool:
        """
        Create a tool from a ToolConfig.

        Returns a fully instantiated BaseTool ready for registration.
        """
        # Check for custom creator first
        if config.class_path in cls._custom_creators:
            tool = cls._custom_creators[config.class_path](**config.init_params)
        else:
            tool = cls.create_from_class_path(config.class_path, config.init_params)

        if config.description:
            tool.description = config.description

        return tool

    # ------------------------------------------------------------------
    # Batch creation
    # ------------------------------------------------------------------

    @classmethod
    def create_batch(cls, configs: List[ToolConfig]) -> List[BaseTool]:
        tools: List[BaseTool] = []
        for cfg in configs:
            if not cfg.enabled:
                logger.debug("Skipping disabled tool: %s", cfg.name)
                continue
            try:
                tool = cls.create_from_config(cfg)
                tools.append(tool)
            except ToolFactoryError as exc:
                logger.error("Failed to create tool '%s': %s", cfg.name, exc)
        return tools

    @classmethod
    def create_and_register(
        cls,
        configs: List[ToolConfig],
        registry: ToolRegistry,
    ) -> int:
        """Create tools from configs and register them. Returns count registered."""
        count = 0
        for cfg in configs:
            if not cfg.enabled:
                continue
            try:
                tool = cls.create_from_config(cfg)
                registry.register(tool)
                if cfg.tags:
                    registry.tag(tool.name, *cfg.tags)
                count += 1
            except Exception as exc:
                logger.error("Failed to create+register tool '%s': %s", cfg.name, exc)
        return count

    # ------------------------------------------------------------------
    # Custom creators (Strategy Pattern)
    # ------------------------------------------------------------------

    @classmethod
    def register_creator(cls, class_path: str, creator: Callable[..., BaseTool]) -> None:
        """Register a custom factory function for a given class path."""
        cls._custom_creators[class_path] = creator
        logger.debug("Custom creator registered for '%s'", class_path)

    # ------------------------------------------------------------------
    # Config parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_config_list(raw: List[Dict[str, Any]]) -> List[ToolConfig]:
        """Parse a list of dicts into ToolConfig objects."""
        configs: List[ToolConfig] = []
        for item in raw:
            try:
                configs.append(ToolConfig(
                    name=item["name"],
                    class_path=item["class_path"],
                    description=item.get("description", ""),
                    enabled=item.get("enabled", True),
                    permissions=item.get("permissions", []),
                    timeout=item.get("timeout", 30.0),
                    tags=item.get("tags", []),
                    init_params=item.get("init_params", {}),
                ))
            except KeyError as exc:
                logger.warning("Skipping invalid tool config (missing %s): %s", exc, item)
        return configs
