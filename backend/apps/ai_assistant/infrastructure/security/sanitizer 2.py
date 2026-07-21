"""
Input Sanitizer — security utilities for AI module.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecurityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SanitizationResult:
    """Result of input sanitization."""
    clean: str
    was_modified: bool
    threats_detected: List[str]
    security_level: SecurityLevel

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clean": self.clean,
            "was_modified": self.was_modified,
            "threats_detected": self.threats_detected,
            "security_level": self.security_level.value,
        }


class InputSanitizer:
    """Production input sanitizer for AI module."""

    MAX_MESSAGE_LENGTH = 10000
    MAX_PARAMETER_LENGTH = 1000

    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC)\b)", re.IGNORECASE),
        re.compile(r"(--|;|/\*|\*/|@@|@)", re.IGNORECASE),
        re.compile(r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)", re.IGNORECASE),
    ]

    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"<iframe[^>]*>", re.IGNORECASE),
        re.compile(r"<object[^>]*>", re.IGNORECASE),
        re.compile(r"<embed[^>]*>", re.IGNORECASE),
    ]

    PATH_TRAVERSAL_PATTERNS = [
        re.compile(r"\.\.\/"),
        re.compile(r"\.\.\\"),
        re.compile(r"%2e%2e", re.IGNORECASE),
    ]

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"ignore\s+(all\s+)?prior\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
        re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
        re.compile(r"assistant\s*:", re.IGNORECASE),
        re.compile(r"human\s*:", re.IGNORECASE),
        re.compile(r"###\s*(system|assistant|human)\s*#", re.IGNORECASE),
        re.compile(r"<\|im_start\|>", re.IGNORECASE),
        re.compile(r"<\|im_end\|>", re.IGNORECASE),
        re.compile(r"\[INST\]|\[/INST\]", re.IGNORECASE),
        re.compile(r"<<SYS>>|<</SYS>>", re.IGNORECASE),
    ]

    def sanitize_message(self, message: str) -> SanitizationResult:
        """Sanitize a user chat message."""
        threats: List[str] = []
        original = message
        clean = message

        # Check length
        if len(clean) > self.MAX_MESSAGE_LENGTH:
            clean = clean[: self.MAX_MESSAGE_LENGTH]
            threats.append("message_truncated")

        # Detect SQL injection
        for pattern in self.SQL_INJECTION_PATTERNS:
            if pattern.search(clean):
                threats.append("sql_injection_attempt")
                break

        # Detect XSS
        for pattern in self.XSS_PATTERNS:
            if pattern.search(clean):
                threats.append("xss_attempt")
                clean = pattern.sub("", clean)
                break

        # Detect path traversal
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if pattern.search(clean):
                threats.append("path_traversal_attempt")
                clean = pattern.sub("", clean)
                break

        # Detect prompt injection
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if pattern.search(clean):
                threats.append("prompt_injection_attempt")
                clean = pattern.sub("", clean)
                break

        # HTML escape
        clean = html.escape(clean)

        # Strip null bytes
        clean = clean.replace("\x00", "")

        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()

        # Determine security level
        if not threats:
            level = SecurityLevel.LOW
        elif len(threats) == 1:
            level = SecurityLevel.MEDIUM
        elif len(threats) <= 2:
            level = SecurityLevel.HIGH
        else:
            level = SecurityLevel.CRITICAL

        return SanitizationResult(
            clean=clean,
            was_modified=clean != original,
            threats_detected=threats,
            security_level=level,
        )

    def sanitize_parameter(self, key: str, value: Any) -> Any:
        """Sanitize a tool parameter value."""
        if isinstance(value, str):
            threats: List[str] = []

            # Check length
            if len(value) > self.MAX_PARAMETER_LENGTH:
                value = value[: self.MAX_PARAMETER_LENGTH]
                threats.append("parameter_truncated")

            # Check for injection
            for pattern in self.SQL_INJECTION_PATTERNS:
                if pattern.search(value):
                    threats.append("sql_injection_in_parameter")
                    break

            # Check for XSS
            for pattern in self.XSS_PATTERNS:
                if pattern.search(value):
                    threats.append("xss_in_parameter")
                    value = pattern.sub("", value)
                    break

            # HTML escape
            value = html.escape(value)

            # Strip null bytes
            value = value.replace("\x00", "")

            if threats:
                logger.warning("Threats detected in parameter '%s': %s", key, threats)

        return value

    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize all string values in a dictionary."""
        return {k: self.sanitize_parameter(k, v) for k, v in data.items()}

    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$")
        return bool(pattern.match(email))

    def validate_wilaya(self, code: str) -> bool:
        """Validate Algerian wilaya code (01-58)."""
        try:
            num = int(code)
            return 1 <= num <= 58
        except (ValueError, TypeError):
            return False

    def validate_nomenclature_code(self, code: str) -> bool:
        """Validate nomenclature code format (XX.XX.XX)."""
        pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}$")
        return bool(pattern.match(code))
