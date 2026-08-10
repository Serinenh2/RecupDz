"""
AI Safety Layer — production-ready content security and rate limiting.

Responsibilities:
    1. Prompt Injection Detection — detect override attempts, instruction hijacking
    2. Jailbreak Detection — detect DAN exploits, role-play bypass, encoding tricks
    3. Sensitive Data Protection — detect and redact PII (phones, emails, IBANs, etc.)
    4. Confidential Information Filtering — enforce data classification boundaries
    5. Output Validation — validate model responses for safety and quality
    6. Hallucination Mitigation — detect unsupported claims, flag uncertain facts
    7. Rate Limiting Hooks — sliding-window rate limiting per user/conversation

Architecture:
    - Stateless detector methods (no side effects)
    - Thread-safe RateLimitTracker (threading.Lock)
    - All detection via regex + deterministic rules — zero LLM calls
    - Configurable severity thresholds and policies
    - Framework independent — no Django, no ORM, no external services

Usage:
    safety = AISafetyLayer()
    result = safety.check_input(user_message, user_id="u123")
    if not result.is_safe:
        return result.block_response()

    # ... generate response ...

    result = safety.check_output(response_text, context={...})
    if result.has_violations:
        response_text = safety.sanitize_output(response_text)
"""

from __future__ import annotations

import re
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ══════════════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════════════


class ViolationType(str, Enum):
    """Categories of safety violations."""
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    SENSITIVE_DATA = "sensitive_data"
    CONFIDENTIAL_BREACH = "confidential_breach"
    HALLUCINATION = "hallucination"
    OUTPUT_UNSAFE = "output_unsafe"
    RATE_LIMIT = "rate_limit"


class Severity(str, Enum):
    """Violation severity levels — CRITICAL blocks, others flag/warn."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CheckPhase(str, Enum):
    """When the check runs in the pipeline."""
    INPUT = "input"
    OUTPUT = "output"
    PROMPT = "prompt"


# ══════════════════════════════════════════════════════════════════════
# Data Contracts
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SafetyViolation:
    """A single detected safety violation."""
    violation_type: ViolationType
    severity: Severity
    description: str
    matched_text: str = ""
    phase: CheckPhase = CheckPhase.INPUT
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "description": self.description,
        }
        if self.matched_text:
            d["matched_text"] = self.matched_text[:100]
        if self.line_number:
            d["line_number"] = self.line_number
        return d


@dataclass(frozen=True)
class Redaction:
    """Records a PII redaction applied to text."""
    original_length: int
    redacted_type: str
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.redacted_type,
            "start": self.start,
            "end": self.end,
            "length": self.original_length,
        }


@dataclass(frozen=True)
class SafetyResult:
    """Aggregated result from all safety checks on a single input/output."""
    phase: CheckPhase
    violations: Tuple[SafetyViolation, ...] = ()
    redactions: Tuple[Redaction, ...] = ()
    sanitized_text: str = ""
    elapsed_ms: float = 0.0

    @property
    def is_safe(self) -> bool:
        """True if no CRITICAL or HIGH violations."""
        return not any(
            v.severity in (Severity.CRITICAL, Severity.HIGH)
            for v in self.violations
        )

    @property
    def has_violations(self) -> bool:
        """True if any violations detected (including LOW/INFO)."""
        return len(self.violations) > 0

    @property
    def blocked(self) -> bool:
        """True if CRITICAL violation — request must be stopped."""
        return any(v.severity == Severity.CRITICAL for v in self.violations)

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.HIGH)

    def block_response(self) -> str:
        """Standard user-facing response when request is blocked."""
        return (
            "Votre message a été bloqué pour des raisons de sécurité. "
            "Veuillez reformuler votre demande."
        )

    def warnings(self) -> List[SafetyViolation]:
        return [v for v in self.violations if v.severity in (Severity.HIGH, Severity.MEDIUM)]

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "phase": self.phase.value,
            "is_safe": self.is_safe,
            "blocked": self.blocked,
            "violation_count": self.violation_count,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }
        if self.violations:
            d["violations"] = [v.to_dict() for v in self.violations]
        if self.redactions:
            d["redactions"] = [r.to_dict() for r in self.redactions]
        if self.sanitized_text:
            d["sanitized_text"] = self.sanitized_text
        return d


# ══════════════════════════════════════════════════════════════════════
# Rate Limiting
# ══════════════════════════════════════════════════════════════════════


@dataclass
class RateLimitConfig:
    """Configuration for a single rate limit window."""
    max_requests: int = 30
    window_seconds: float = 60.0
    cooldown_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")


@dataclass(frozen=True)
class RateLimitStatus:
    """Status of a rate limit check."""
    allowed: bool
    remaining: int
    limit: int
    reset_at: float
    retry_after: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "allowed": self.allowed,
            "remaining": self.remaining,
            "limit": self.limit,
            "reset_at": round(self.reset_at, 1),
        }
        if not self.allowed:
            d["retry_after"] = round(self.retry_after, 1)
        return d


class RateLimitTracker:
    """
    Thread-safe sliding-window rate limiter.

    Tracks request timestamps per key (user_id, conversation_id, etc.)
    and enforces a maximum request count within a rolling time window.

    Thread-safe via threading.Lock.
    """

    def __init__(
        self,
        *,
        max_requests: int = 30,
        window_seconds: float = 60.0,
        cooldown_seconds: float = 0.0,
    ) -> None:
        self._config = RateLimitConfig(
            max_requests=max_requests,
            window_seconds=window_seconds,
            cooldown_seconds=cooldown_seconds,
        )
        self._lock = threading.Lock()
        self._windows: Dict[str, List[float]] = defaultdict(list)
        self._cooldowns: Dict[str, float] = {}

    def check(self, key: str) -> RateLimitStatus:
        """Check if request is allowed for the given key."""
        now = time.monotonic()
        with self._lock:
            return self._check_internal(key, now)

    def record(self, key: str) -> RateLimitStatus:
        """Record a request and return the resulting status."""
        now = time.monotonic()
        with self._lock:
            status = self._check_internal(key, now)
            if status.allowed:
                self._windows[key].append(now)
                self._prune(key, now)
                # Recalculate after recording
                remaining = max(0, self._config.max_requests - len(self._windows.get(key, [])))
                return RateLimitStatus(
                    allowed=True,
                    remaining=remaining,
                    limit=self._config.max_requests,
                    reset_at=now + self._config.window_seconds,
                )
            return status

    def reset(self, key: Optional[str] = None) -> None:
        """Reset tracking data for a key or all keys."""
        with self._lock:
            if key is None:
                self._windows.clear()
                self._cooldowns.clear()
            else:
                self._windows.pop(key, None)
                self._cooldowns.pop(key, None)

    def stats(self) -> Dict[str, Any]:
        """Return current tracking statistics."""
        with self._lock:
            return {
                "active_keys": len(self._windows),
                "config": {
                    "max_requests": self._config.max_requests,
                    "window_seconds": self._config.window_seconds,
                },
            }

    def _check_internal(self, key: str, now: float) -> RateLimitStatus:
        self._prune(key, now)
        timestamps = self._windows.get(key, [])
        remaining = max(0, self._config.max_requests - len(timestamps))

        # Check cooldown
        cooldown_end = self._cooldowns.get(key, 0.0)
        if now < cooldown_end:
            return RateLimitStatus(
                allowed=False,
                remaining=0,
                limit=self._config.max_requests,
                reset_at=cooldown_end,
                retry_after=cooldown_end - now,
            )

        if remaining <= 0:
            oldest = timestamps[0] if timestamps else now
            reset_at = oldest + self._config.window_seconds
            retry_after = max(0.0, reset_at - now)
            return RateLimitStatus(
                allowed=False,
                remaining=0,
                limit=self._config.max_requests,
                reset_at=reset_at,
                retry_after=retry_after,
            )

        return RateLimitStatus(
            allowed=True,
            remaining=remaining,
            limit=self._config.max_requests,
            reset_at=now + self._config.window_seconds,
        )

    def _prune(self, key: str, now: float) -> None:
        timestamps = self._windows.get(key, [])
        cutoff = now - self._config.window_seconds
        pruned = [t for t in timestamps if t > cutoff]
        self._windows[key] = pruned


# ══════════════════════════════════════════════════════════════════════
# Detection Patterns
# ══════════════════════════════════════════════════════════════════════

    # Prompt injection patterns (FR + EN)
_INJECTION_PATTERNS: List[Tuple[str, Severity, str]] = [
    # System override
    (r"(?:ignore|forget|disregard|supprime|oublie|ignorez|annulez)\s+(?:\w+\s+){0,3}(?:instructions?|r[eè]gles?|consignes?|directives?)",
     Severity.CRITICAL, "Instruction override attempt"),
    (r"(?:now|maintenant)\s+you\s+(?:are|will|must|should|act|behave|pretend|play|joue|sois)",
     Severity.CRITICAL, "Role reassignment attempt"),
    (r"(?:new|nouvelles?)\s+(?:system|syst[eè]me)\s+(?:prompt|instruction|consigne|r[eè]gle)",
     Severity.CRITICAL, "System prompt replacement attempt"),
    # Direct override
    (r"(?:you\s+are\s+now|tu\s+es\s+maintenant|devenez|become|soyez)\s+(?:a|un|une|an?)\s+",
     Severity.HIGH, "Persona override attempt"),
    (r"(?:enter|entrez|passer\s+en)\s+(?:developer|d[eé]veloppeur|debug|admin|root|superuser|god)\s+mode",
     Severity.CRITICAL, "Developer mode activation attempt"),
    # Instruction injection via markdown/code
    (r"```\s*\n?\s*(?:system|assistant|user)\s*:",
     Severity.HIGH, "Role label injection in code block"),
    (r"<\|(?:im_start|im_end|system|assistant|user)\|>",
     Severity.CRITICAL, "Chat template injection attempt"),
    # Encoding tricks
    (r"(?:base64|hex|rot13|b16|b32|atob|btoa)\s*[:=]",
     Severity.HIGH, "Encoding bypass attempt"),
    # Data exfiltration
    (r"(?:send|transmit|exfiltrate|envoie|transmets?|exporte?)\s+(?:all\s+)?(?:data|donnees?|donn[eé]es?|keys?|cl[eé]s?|secrets?|mot[s]?\s+de\s+passe)",
     Severity.CRITICAL, "Data exfiltration attempt"),
    # Prompt leaking
    (r"(?:repeat|r[eé]p[eè]te|print|affiche|show|montre|reveal|d[eé]voile|copy|copie)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instruction|consigne|r[eè]gle|configuration)",
     Severity.HIGH, "System prompt leakage attempt"),
    # Multi-language injection
    (r"(?:ignori?er?|verg[eè]ssen?|olvidar)\s+(?:alle?\s+)?(?:vorherigen?\s+)?(?:Anweisungen?|instrucciones?|instructions?)",
     Severity.CRITICAL, "Multi-language instruction override"),
]

# Jailbreak patterns (FR + EN)
_JAILBREAK_PATTERNS: List[Tuple[str, Severity, str]] = [
    # DAN-style
    (r"(?:do\s+anything|fais\s+tout|haz\s+tout|todo)\s+now",
     Severity.CRITICAL, "DAN-style jailbreak attempt"),
    (r"\bDAN\b.*(?:mode|activer|enable|activate)",
     Severity.CRITICAL, "DAN mode activation"),
    # Role-play bypass
    (r"(?:let'?s?\s+play|jouons?\s+(?:a[u]|au|rôle)|imagine\s+(?:that|que|you\s+are|tu\s+es))\s+",
     Severity.HIGH, "Role-play bypass attempt"),
    (r"(?:you\s+are|c'?est|es|es-tu|are\s+you)\s+(?:an?\s+)?(?:unfiltered|unrestricted|sans\s+filtre|sans\s+limit[eè])",
     Severity.HIGH, "Unrestricted mode request"),
    # Hypothetical bypass
    (r"(?:hypoth[eè]tiquement?|hypothetically|in\s+a\s+hypothetical|dans\s+un\s+sc[eé]nario)\s*,?\s*(?:what|que|comment|how)",
     Severity.MEDIUM, "Hypothetical bypass framing"),
    # Token smuggling
    (r"(?:split|d[eé]coupe|s[eé]pare)\s+(?:the|le|la|les)\s+(?:word|mot|r[eé]ponse|answer)\s+into\s+(?:characters|lettres)",
     Severity.HIGH, "Token smuggling attempt"),
    # Fake system message
    (r"\[(?:SYSTEM|SYSTEME|SYS|ADMIN)\s*(?:MESSAGE|MSG|NOTE|NOTE)\]",
     Severity.CRITICAL, "Fake system message injection"),
    (r"(?:important|IMPORTANT)\s*:\s*(?:ignore|oublier|disregard)",
     Severity.CRITICAL, "Priority override injection"),
]

# Sensitive data patterns (French + International)
_SENSITIVE_PATTERNS: List[Tuple[str, Severity, str, str]] = [
    # French phone numbers
    (r"(?:\+33|0033)[\s.-]?[1-9](?:[\s.-]?\d{2}){4}",
     Severity.HIGH, "phone_number", "NUMERO_TELEPHONE"),
    (r"\b0[1-9](?:[\s.-]?\d{2}){4}\b",
     Severity.HIGH, "phone_number", "NUMERO_TELEPHONE"),
    # Email addresses
    (r"[\w.+-]+@[\w-]+\.[\w.-]+",
     Severity.MEDIUM, "email", "ADRESSE_EMAIL"),
    # French IBAN
    (r"\bFR\d{2}[\s]?\d{5}[\s]?\d{5}[\s]?\d{11}\b",
     Severity.HIGH, "iban", "IBAN"),
    # RIB / RIB key
    (r"\b\d{5}\s?\d{5}\s?\d{11}\s?\d{2}\b",
     Severity.MEDIUM, "bank_account", "COMPTE_BANCAIRE"),
    # French social security (NIR)
    (r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b",
     Severity.HIGH, "nir", "NUMERO_SECURITE_SOCIALE"),
    # SIRET (14 digits)
    (r"\b\d{3}[\s.]?\d{3}[\s.]?\d{3}[\s.]?\d{5}\b",
     Severity.MEDIUM, "siret", "SIRET"),
    # SIREN (9 digits)
    (r"\b\d{3}[\s.]?\d{3}[\s.]?\d{3}\b",
     Severity.LOW, "siren", "SIREN"),
    # Credit card numbers
    (r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
     Severity.HIGH, "credit_card", "CARTE_BANCAIRE"),
    # Passwords / secrets in text
    (r"(?:password|mot\s*de\s*passe|passwd|pwd|secret|token|api[_-]?key|clé)\s*[:=]\s*\S+",
     Severity.HIGH, "password", "MOT_DE_PASSE"),
    # IP addresses (internal range)
    (r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b",
     Severity.MEDIUM, "internal_ip", "ADRESSE_IP_INTERNE"),
]

# Confidential keywords per classification level
_CONFIDENTIAL_KEYWORDS: Dict[str, List[str]] = {
    "secret": [
        "confidentiel", "confidential", "secret", "classified",
        "classified", "top secret", "très confidentiel",
        "restricted", "restreint", "pour diffusion restreinte",
    ],
    "internal": [
        "interne uniquement", "internal only", "not for distribution",
        "ne pas diffuser", "usage interne", "proprieté exclusive",
        "proprietary", "do not share", "ne pas partager",
    ],
}

# Hallucination indicators
_HALLUCINATION_PATTERNS: List[Tuple[str, Severity, str]] = [
    (r"(?:according\s+to\s+my\s+knowledge|d'?apr[eè]s\s+(?:mes|mon)\s+(?:connaissances?|savoir))",
     Severity.INFO, "Knowledge attribution (may indicate uncertainty)"),
    (r"(?:i\s+(?:believe|think|suspect|guess)|je\s+(?:pense|crois|suppose|imagine))",
     Severity.INFO, "Subjective qualifier detected"),
    (r"(?:approximately|environ|roughly|aux?\s+alentours\s+de)\s+\d+",
     Severity.LOW, "Approximate figure — verify against source data"),
    (r"(?:i\s+don'?t|je\s+(?:ne\s+)?(?:sais|connais|ai\s+pas))\s+(?:have|avoir)?\s*(?:that|ce|cette|des?)?\s*(?:data|information|donn[eé]e|info)",
     Severity.INFO, "Missing data acknowledgment"),
    (r"(?:studies?\s+(?:show|suggest|indicate)|des?\s+?(?:[eé]tudes?|recherches?)\s+(?:montrent?|sugg[eè]rent?|indiquent?))",
     Severity.MEDIUM, "Unsourced study citation — flag for verification"),
]

# Output safety patterns
_OUTPUT_UNSAFE_PATTERNS: List[Tuple[str, Severity, str]] = [
    (r"(?:you\s+(?:should|must|need\s+to)\s+(?:hack|crack|bypass|circumvent|override))",
     Severity.HIGH, "Unsafe action recommendation"),
    (r"(?:here\s+(?:is|are)\s+(?:the\s+)?(?:password|code|key|token|secret|credential))",
     Severity.HIGH, "Credential exposure in output"),
    (r"\b(?:DROP\s+TABLE|DELETE\s+FROM|UPDATE\s+.*SET|INSERT\s+INTO)\b",
     Severity.HIGH, "SQL statement in response"),
    (r"(?:exec|eval|system|popen|subprocess|os\.system|__import__)\s*\(",
     Severity.HIGH, "Code execution pattern in response"),
]


# ══════════════════════════════════════════════════════════════════════
# AISafetyLayer
# ══════════════════════════════════════════════════════════════════════


class AISafetyLayer:
    """
    Production-ready content security and rate limiting.

    Stateless detection methods — no side effects.
    Thread-safe RateLimitTracker for concurrent requests.

    Usage:
        safety = AISafetyLayer()

        # Check user input
        input_result = safety.check_input(message, user_id="u123")
        if input_result.blocked:
            return input_result.block_response()

        # Check model output
        output_result = safety.check_output(response, context={...})
        response = safety.sanitize_output(response)
    """

    def __init__(
        self,
        *,
        rate_limit_max: int = 30,
        rate_limit_window: float = 60.0,
        rate_limit_cooldown: float = 0.0,
        confidential_keywords: Optional[Dict[str, List[str]]] = None,
        custom_injection_patterns: Optional[List[Tuple[str, Severity, str]]] = None,
        custom_jailbreak_patterns: Optional[List[Tuple[str, Severity, str]]] = None,
        custom_sensitive_patterns: Optional[List[Tuple[str, Severity, str, str]]] = None,
        redact_pii: bool = True,
        max_output_length: int = 10000,
    ) -> None:
        self._redact_pii = redact_pii
        self._max_output_length = max_output_length
        self._injection_patterns = list(_INJECTION_PATTERNS)
        self._jailbreak_patterns = list(_JAILBREAK_PATTERNS)
        self._sensitive_patterns = list(_SENSITIVE_PATTERNS)
        self._confidential_keywords = dict(_CONFIDENTIAL_KEYWORDS)
        self._hallucination_patterns = list(_HALLUCINATION_PATTERNS)
        self._output_unsafe_patterns = list(_OUTPUT_UNSAFE_PATTERNS)

        if custom_injection_patterns:
            self._injection_patterns.extend(custom_injection_patterns)
        if custom_jailbreak_patterns:
            self._jailbreak_patterns.extend(custom_jailbreak_patterns)
        if custom_sensitive_patterns:
            self._sensitive_patterns.extend(custom_sensitive_patterns)
        if confidential_keywords:
            self._confidential_keywords.update(confidential_keywords)

        self._rate_limiter = RateLimitTracker(
            max_requests=rate_limit_max,
            window_seconds=rate_limit_window,
            cooldown_seconds=rate_limit_cooldown,
        )

    # ── Public API ────────────────────────────────────────────────────

    def check_input(
        self,
        text: str,
        *,
        user_id: str = "",
        conversation_id: str = "",
        allowed_topics: Optional[Set[str]] = None,
    ) -> SafetyResult:
        """
        Run all safety checks on user input.

        Checks in order:
            1. Rate limiting
            2. Prompt injection detection
            3. Jailbreak detection
            4. Sensitive data detection (PII)
            5. Confidential information detection

        Returns SafetyResult with violations and sanitized text.
        """
        t0 = time.monotonic()
        violations: List[SafetyViolation] = []
        redactions: List[Redaction] = []

        # 1. Rate limiting
        rate_key = user_id or conversation_id or "anonymous"
        rate_status = self._rate_limiter.record(rate_key)
        if not rate_status.allowed:
            violations.append(SafetyViolation(
                violation_type=ViolationType.RATE_LIMIT,
                severity=Severity.CRITICAL,
                description=(
                    f"Taux de requêtes dépassé: {rate_status.limit} requêtes "
                    f"par {self._rate_limiter._config.window_seconds:.0f}s. "
                    f"Réessayez dans {rate_status.retry_after:.0f}s."
                ),
                phase=CheckPhase.INPUT,
            ))

        # 2. Prompt injection
        violations.extend(self._detect_injection(text, CheckPhase.INPUT))

        # 3. Jailbreak
        violations.extend(self._detect_jailbreak(text, CheckPhase.INPUT))

        # 4. Sensitive data (PII)
        pii_violations, pii_redactions = self._detect_sensitive_data(
            text, CheckPhase.INPUT,
        )
        violations.extend(pii_violations)
        redactions.extend(pii_redactions)

        # 5. Confidential information
        violations.extend(self._detect_confidential(text, CheckPhase.INPUT))

        # Sanitize
        sanitized = text
        if self._redact_pii and redactions:
            sanitized = self._apply_redactions(text, redactions)

        elapsed = (time.monotonic() - t0) * 1000

        return SafetyResult(
            phase=CheckPhase.INPUT,
            violations=tuple(violations),
            redactions=tuple(redactions),
            sanitized_text=sanitized,
            elapsed_ms=elapsed,
        )

    def check_output(
        self,
        text: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> SafetyResult:
        """
        Run safety checks on model output before returning to user.

        Checks:
            1. Output length validation
            2. Unsafe pattern detection
            3. Sensitive data leak detection
            4. Hallucination indicators
            5. Confidential information leak detection
        """
        t0 = time.monotonic()
        violations: List[SafetyViolation] = []
        redactions: List[Redaction] = []

        # 1. Length check
        if len(text) > self._max_output_length:
            violations.append(SafetyViolation(
                violation_type=ViolationType.OUTPUT_UNSAFE,
                severity=Severity.MEDIUM,
                description=f"Réponse excessive: {len(text)} caractères (max {self._max_output_length})",
                phase=CheckPhase.OUTPUT,
            ))

        # 2. Unsafe patterns
        violations.extend(self._detect_output_unsafe(text))

        # 3. Sensitive data leak
        pii_violations, pii_redactions = self._detect_sensitive_data(
            text, CheckPhase.OUTPUT,
        )
        violations.extend(pii_violations)
        redactions.extend(pii_redactions)

        # 4. Hallucination indicators
        violations.extend(self._detect_hallucination(text, context))

        # 5. Confidential leak
        violations.extend(self._detect_confidential(text, CheckPhase.OUTPUT))

        sanitized = text
        if self._redact_pii and redactions:
            sanitized = self._apply_redactions(text, redactions)

        elapsed = (time.monotonic() - t0) * 1000

        return SafetyResult(
            phase=CheckPhase.OUTPUT,
            violations=tuple(violations),
            redactions=tuple(redactions),
            sanitized_text=sanitized,
            elapsed_ms=elapsed,
        )

    def check_prompt(
        self,
        system_prompt: str,
    ) -> SafetyResult:
        """
        Validate a system prompt for safety.

        Checks:
            1. Injection patterns in the prompt itself
            2. Confidential data exposure in prompt
            3. Prompt length sanity check
        """
        t0 = time.monotonic()
        violations: List[SafetyViolation] = []

        # Injection patterns
        violations.extend(self._detect_injection(system_prompt, CheckPhase.PROMPT))

        # Confidential data
        violations.extend(self._detect_confidential(system_prompt, CheckPhase.PROMPT))

        # Length sanity (prompts > 50k chars are suspicious)
        if len(system_prompt) > 50000:
            violations.append(SafetyViolation(
                violation_type=ViolationType.OUTPUT_UNSAFE,
                severity=Severity.MEDIUM,
                description=f"System prompt excessivement long: {len(system_prompt)} caractères",
                phase=CheckPhase.PROMPT,
            ))

        elapsed = (time.monotonic() - t0) * 1000

        return SafetyResult(
            phase=CheckPhase.PROMPT,
            violations=tuple(violations),
            elapsed_ms=elapsed,
        )

    def sanitize_output(self, text: str) -> str:
        """
        Sanitize model output for safe delivery to user.

        Applies:
            1. PII redaction (if enabled)
            2. Length truncation
            3. Internal data pattern removal
        """
        result = text

        # PII redaction
        if self._redact_pii:
            _, redactions = self._detect_sensitive_data(result, CheckPhase.OUTPUT)
            if redactions:
                result = self._apply_redactions(result, redactions)

        # Length truncation
        if len(result) > self._max_output_length:
            result = result[:self._max_output_length] + "\n\n[Réponse tronquée]"

        # Strip internal IP addresses
        result = re.sub(
            r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b",
            "[ADRESSE_IP]",
            result,
        )

        return result

    # ── Rate Limiting API ─────────────────────────────────────────────

    def check_rate_limit(self, key: str) -> RateLimitStatus:
        """Check rate limit without recording (read-only)."""
        return self._rate_limiter.check(key)

    def reset_rate_limit(self, key: Optional[str] = None) -> None:
        """Reset rate limit tracking for a key or all keys."""
        self._rate_limiter.reset(key)

    def rate_limit_stats(self) -> Dict[str, Any]:
        """Return rate limiter statistics."""
        return self._rate_limiter.stats()

    # ── Detection Internals ───────────────────────────────────────────

    def _detect_injection(
        self, text: str, phase: CheckPhase,
    ) -> List[SafetyViolation]:
        """Detect prompt injection patterns."""
        violations: List[SafetyViolation] = []
        text_lower = text.lower()

        for pattern, severity, description in self._injection_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                violations.append(SafetyViolation(
                    violation_type=ViolationType.PROMPT_INJECTION,
                    severity=severity,
                    description=description,
                    matched_text=match.group()[:100],
                    phase=phase,
                ))

        return violations

    def _detect_jailbreak(
        self, text: str, phase: CheckPhase,
    ) -> List[SafetyViolation]:
        """Detect jailbreak patterns."""
        violations: List[SafetyViolation] = []
        text_lower = text.lower()

        for pattern, severity, description in self._jailbreak_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                violations.append(SafetyViolation(
                    violation_type=ViolationType.JAILBREAK,
                    severity=severity,
                    description=description,
                    matched_text=match.group()[:100],
                    phase=phase,
                ))

        return violations

    def _detect_sensitive_data(
        self, text: str, phase: CheckPhase,
    ) -> Tuple[List[SafetyViolation], List[Redaction]]:
        """Detect PII and sensitive data."""
        violations: List[SafetyViolation] = []
        redactions: List[Redaction] = []

        for pattern, severity, pii_type, description in self._sensitive_patterns:
            for match in re.finditer(pattern, text):
                violations.append(SafetyViolation(
                    violation_type=ViolationType.SENSITIVE_DATA,
                    severity=severity,
                    description=description,
                    matched_text=match.group()[:100],
                    phase=phase,
                ))
                redactions.append(Redaction(
                    original_length=len(match.group()),
                    redacted_type=description,
                    start=match.start(),
                    end=match.end(),
                ))

        return violations, redactions

    def _detect_confidential(
        self, text: str, phase: CheckPhase,
    ) -> List[SafetyViolation]:
        """Detect confidential information markers."""
        violations: List[SafetyViolation] = []
        text_lower = text.lower()

        for level, keywords in self._confidential_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    violations.append(SafetyViolation(
                        violation_type=ViolationType.CONFIDENTIAL_BREACH,
                        severity=Severity.HIGH,
                        description=f"Information classifiée '{level}' détectée: '{keyword}'",
                        matched_text=keyword,
                        phase=phase,
                    ))

        return violations

    def _detect_hallucination(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[SafetyViolation]:
        """Detect potential hallucination indicators."""
        violations: List[SafetyViolation] = []

        for pattern, severity, description in self._hallucination_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                violations.append(SafetyViolation(
                    violation_type=ViolationType.HALLUCINATION,
                    severity=severity,
                    description=description,
                    matched_text=match.group()[:100],
                    phase=CheckPhase.OUTPUT,
                ))

        # Check for unverifiable claims if context provides source data
        if context and "source_data" in context:
            source = str(context["source_data"])
            numbers_in_output = set(re.findall(r"\b\d+(?:\.\d+)?\b", text))
            numbers_in_source = set(re.findall(r"\b\d+(?:\.\d+)?\b", source))
            unverifiable = numbers_in_output - numbers_in_source
            if unverifiable and len(unverifiable) > 3:
                violations.append(SafetyViolation(
                    violation_type=ViolationType.HALLUCINATION,
                    severity=Severity.MEDIUM,
                    description=(
                        f"{len(unverifiable)} chiffres dans la réponse "
                        "absents des données source"
                    ),
                    matched_text=", ".join(sorted(unverifiable)[:5]),
                    phase=CheckPhase.OUTPUT,
                ))

        return violations

    def _detect_output_unsafe(
        self, text: str,
    ) -> List[SafetyViolation]:
        """Detect unsafe patterns in model output."""
        violations: List[SafetyViolation] = []

        for pattern, severity, description in self._output_unsafe_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                violations.append(SafetyViolation(
                    violation_type=ViolationType.OUTPUT_UNSAFE,
                    severity=severity,
                    description=description,
                    matched_text=match.group()[:100],
                    phase=CheckPhase.OUTPUT,
                ))

        return violations

    # ── Redaction ─────────────────────────────────────────────────────

    @staticmethod
    def _apply_redactions(text: str, redactions: List[Redaction]) -> str:
        """Apply PII redactions to text, replacing matched spans with placeholders."""
        if not redactions:
            return text

        sorted_redactions = sorted(redactions, key=lambda r: r.start, reverse=True)
        result = text
        for redaction in sorted_redactions:
            placeholder = f"[{redaction.redacted_type}]"
            result = result[:redaction.start] + placeholder + result[redaction.end:]

        return result
