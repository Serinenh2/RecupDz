"""
Tool Registry — discovery, registration, lookup, filtering.

Manages the lifecycle of tools: register, unregister, search,
and export schemas for LLM tool-calling.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any, Dict, Iterator, List, Optional, Set, Type

from apps.ai_assistant.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    pass


class ToolRegistry:
    """
    Central registry for all tools in the system.

    Supports:
        - Explicit registration of tool instances
        - Auto-discovery of BaseTool subclasses in a package
        - Lookup by name, tag, or permission
        - Schema export for LLM integration
        - Duplicate detection
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._tags: Dict[str, Set[str]] = {}  # tag → set of tool names
        self._disabled: Set[str] = set()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        if not isinstance(tool, BaseTool):
            raise ToolRegistryError(
                f"Cannot register '{type(tool).__name__}': not a BaseTool subclass"
            )
        name = tool.name
        if name in self._tools:
            raise ToolRegistryError(
                f"Tool '{name}' already registered. "
                f"Use unregister() first or choose a different name."
            )
        if name in self._disabled:
            logger.info("Tool '%s' is disabled, skipping registration", name)
            return

        self._tools[name] = tool
        logger.info("Tool registered: %s v%s — %s", name, tool.version, tool.description)

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            for tag_tools in self._tags.values():
                tag_tools.discard(name)
            logger.info("Tool unregistered: %s", name)
            return True
        return False

    def disable(self, name: str) -> None:
        self._disabled.add(name)
        self._tools.pop(name, None)

    def enable(self, name: str) -> None:
        self._disabled.discard(name)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_or_raise(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if tool is None:
            available = list(self._tools.keys())
            raise KeyError(f"Tool '{name}' not found. Available: {available}")
        return tool

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_all(self) -> List[BaseTool]:
        return list(self._tools.values())

    def list_names(self) -> List[str]:
        return sorted(self._tools.keys())

    def list_schemas(self) -> List[Dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]

    def list_descriptions(self) -> str:
        lines = [f"- {t.name}: {t.description}" for t in self._tools.values()]
        return "\n".join(lines) if lines else "Aucun outil disponible."

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def filter_by_permission(self, permission: str) -> List[BaseTool]:
        return [t for t in self._tools.values() if permission in t.required_permissions]

    def filter_by_tag(self, tag: str) -> List[BaseTool]:
        names = self._tags.get(tag, set())
        return [self._tools[n] for n in names if n in self._tools]

    def search(self, query: str) -> List[BaseTool]:
        """Simple text search across name and description."""
        query_lower = query.lower()
        return [
            t for t in self._tools.values()
            if query_lower in t.name.lower() or query_lower in t.description.lower()
        ]

    # ------------------------------------------------------------------
    # Tagging
    # ------------------------------------------------------------------

    def tag(self, tool_name: str, *tags: str) -> None:
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' not in registry")
        for tag in tags:
            if tag not in self._tags:
                self._tags[tag] = set()
            self._tags[tag].add(tool_name)

    def list_tags(self) -> List[str]:
        return sorted(self._tags.keys())

    # ------------------------------------------------------------------
    # Bulk Discovery
    # ------------------------------------------------------------------

    def discover_package(self, package_path: str) -> int:
        """
        Auto-discover and register all BaseTool subclasses in a Python package.

        Args:
            package_path: Dotted package path (e.g. "apps.ai_assistant.tools.builtin")

        Returns:
            Number of tools discovered and registered.
        """
        count = 0
        try:
            package = importlib.import_module(package_path)
        except ImportError as exc:
            logger.error("Cannot import package '%s': %s", package_path, exc)
            return 0

        pkg_path = getattr(package, "__path__", None)
        if pkg_path is None:
            logger.warning("'%s' is not a package", package_path)
            return 0

        for importer, module_name, is_pkg in pkgutil.walk_packages(
            path=pkg_path, prefix=package.__name__ + "."
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError as exc:
                logger.warning("Cannot import '%s': %s", module_name, exc)
                continue

            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseTool)
                    and obj is not BaseTool
                    and not inspect.isabstract(obj)
                ):
                    try:
                        instance = obj()
                        self.register(instance)
                        count += 1
                    except Exception as exc:
                        logger.error("Failed to instantiate %s: %s", obj.__name__, exc)

        logger.info("Discovery complete: %d tools registered from '%s'", count, package_path)
        return count

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __iter__(self) -> Iterator[BaseTool]:
        return iter(self._tools.values())

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={list(self._tools.keys())})"
