"""
Standardised Tool Result — the universal return type for every tool.

Every tool execution MUST return:
    {
        "success": true/false,
        "message": "human-readable status",
        "data": {} / []
    }
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolResultResponse:
    """
    Canonical response envelope for all tool executions.

    Serialises to the exact JSON shape expected by callers:
        { "success": bool, "message": str, "data": Any }
    """

    success: bool
    message: str = ""
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- serialisation --

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data if self.data is not None else {},
        }

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)

    # -- convenience constructors --

    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> ToolResultResponse:
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str, data: Any = None) -> ToolResultResponse:
        return cls(success=False, message=message, data=data or {})

    @classmethod
    def from_exception(cls, exc: Exception, context: str = "") -> ToolResultResponse:
        msg = f"{type(exc).__name__}: {exc}"
        if context:
            msg = f"{context} — {msg}"
        return cls(success=False, message=msg, data={})

    # -- merging --

    def with_metadata(self, **kwargs: Any) -> ToolResultResponse:
        self.metadata.update(kwargs)
        return self

    def merge(self, other: "ToolResultResponse") -> ToolResultResponse:
        """Merge another result into this one (for aggregation)."""
        if not self.success or not other.success:
            return ToolResultResponse.fail(
                message=f"{self.message} | {other.message}",
                data={"primary": self.data, "secondary": other.data},
            )
        combined_data = self.data if isinstance(self.data, dict) else {"result": self.data}
        if isinstance(other.data, dict):
            combined_data = {**combined_data, **other.data}
        else:
            combined_data["secondary"] = other.data
        return ToolResultResponse(
            success=True,
            message=self.message or other.message,
            data=combined_data,
        )
