"""
Circuit Breaker — prevents cascading failures via state machine.

States:
    CLOSED   → Normal operation. Failures counted. Trips to OPEN after threshold.
    OPEN     → All calls blocked. After cooldown, transitions to HALF_OPEN.
    HALF_OPEN → One probe call allowed. Success → CLOSED. Failure → OPEN.

Integration:
    Used by OfflineMode to wrap Ollama, KnowledgeSearch, and Database calls.
    When circuit is OPEN, the call is short-circuited to fallback/cache.

Thread-safety:
    All state transitions protected by threading.RLock.

Architecture:
    ┌─────────┐  failure_threshold   ┌──────┐  cooldown   ┌───────────┐
    │ CLOSED   │ ──────────────────► │ OPEN │ ──────────► │ HALF_OPEN │
    └─────────┘                      └──────┘             └───────────┘
         ▲                                                      │
         │                success                               │
         └──────────────────────────────────────────────────────┘
         │                                                      │
         │    success                          failure           │
         │◄─────────────────────────────────────────────────────┘
    ┌──────┐
    │CLOSED│
    └──────┘
"""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ══════════════════════════════════════════════════════════════════════
# Enums & Data structures
# ══════════════════════════════════════════════════════════════════════

class CircuitState(str, enum.Enum):
    """Three states of the circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitEvent(str, enum.Enum):
    """Events that trigger state transitions."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    REJECT = "reject"
    OPEN = "open"
    HALF_OPEN = "half_open"
    CLOSE = "close"


@dataclass(frozen=True)
class CircuitMetrics:
    """Immutable snapshot of circuit breaker statistics."""
    state: CircuitState
    failure_count: int
    success_count: int
    total_calls: int
    consecutive_failures: int
    last_failure_time: float
    last_success_time: float
    last_state_change: float
    time_in_state: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "consecutive_failures": self.consecutive_failures,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "last_state_change": self.last_state_change,
            "time_in_state": round(self.time_in_state, 2),
        }


@dataclass
class CircuitBreakerConfig:
    """Configuration for a CircuitBreaker instance."""
    name: str = "unnamed"
    failure_threshold: int = 5
    success_threshold: int = 3
    cooldown_seconds: float = 30.0
    half_open_max_calls: int = 1
    timeout_seconds: float = 10.0
    excluded_exceptions: tuple = ()


# ══════════════════════════════════════════════════════════════════════
# Circuit Breaker
# ══════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """Thread-safe circuit breaker with configurable thresholds.

    Usage:
        cb = CircuitBreaker(CircuitBreakerConfig(name="ollama", failure_threshold=3))
        result = cb.call(my_function, arg1, arg2)  # Raises CircuitOpenError if OPEN

        # Or check state before calling:
        if cb.allow_request():
            result = my_function(arg1)
            cb.record_success()
        else:
            result = fallback()
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None) -> None:
        import threading
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._consecutive_failures = 0
        self._last_failure_time = 0.0
        self._last_success_time = 0.0
        self._last_state_change = time.monotonic()
        self._half_open_calls = 0
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allow_request(self) -> bool:
        """Check if a request is allowed through the circuit.

        Returns True if circuit is CLOSED or HALF_OPEN (with capacity).
        Returns False if circuit is OPEN.
        """
        with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self._config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            # OPEN
            return False

    def record_success(self) -> None:
        """Record a successful call. May transition state."""
        with self._lock:
            self._success_count += 1
            self._total_calls += 1
            self._last_success_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_failures = 0
                self._half_open_calls = 0
                self._transition(CircuitState.CLOSED, CircuitEvent.CLOSE)

            elif self._state == CircuitState.CLOSED:
                self._consecutive_failures = 0

    def record_failure(self, exception: Optional[Exception] = None) -> None:
        """Record a failed call. May trip the circuit to OPEN."""
        with self._lock:
            if exception and isinstance(exception, self._config.excluded_exceptions):
                return

            self._failure_count += 1
            self._total_calls += 1
            self._consecutive_failures += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls = 0
                self._transition(CircuitState.OPEN, CircuitEvent.OPEN)

            elif self._state == CircuitState.CLOSED:
                if self._consecutive_failures >= self._config.failure_threshold:
                    self._transition(CircuitState.OPEN, CircuitEvent.OPEN)

    def record_timeout(self) -> None:
        """Record a timeout as a failure."""
        self.record_failure()

    def reset(self) -> None:
        """Force reset to CLOSED state."""
        with self._lock:
            self._transition(CircuitState.CLOSED, CircuitEvent.CLOSE)
            self._failure_count = 0
            self._consecutive_failures = 0
            self._half_open_calls = 0

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute fn if circuit allows; otherwise raise CircuitOpenError.

        Automatically records success/failure.
        """
        if not self.allow_request():
            raise CircuitOpenError(
                f"Circuit '{self.name}' is OPEN — "
                f"retry after {self._time_until_half_open():.1f}s"
            )

        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except self._config.excluded_exceptions:
            raise
        except Exception as exc:
            self.record_failure(exc)
            raise

    def metrics(self) -> CircuitMetrics:
        """Return an immutable snapshot of circuit statistics."""
        with self._lock:
            return CircuitMetrics(
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                total_calls=self._total_calls,
                consecutive_failures=self._consecutive_failures,
                last_failure_time=self._last_failure_time,
                last_success_time=self._last_success_time,
                last_state_change=self._last_state_change,
                time_in_state=time.monotonic() - self._last_state_change,
            )

    def is_available(self) -> bool:
        """Quick check — is the circuit allowing requests?"""
        return self.allow_request()

    def to_dict(self) -> Dict[str, Any]:
        return self.metrics().to_dict()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_transition_to_half_open(self) -> None:
        """Transition OPEN → HALF_OPEN after cooldown expires."""
        if self._state != CircuitState.OPEN:
            return

        elapsed = time.monotonic() - self._last_state_change
        if elapsed >= self._config.cooldown_seconds:
            self._transition(CircuitState.HALF_OPEN, CircuitEvent.HALF_OPEN)

    def _transition(self, new_state: CircuitState, event: CircuitEvent) -> None:
        """Perform state transition with logging."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.monotonic()
        self._half_open_calls = 0
        logger.info(
            "CircuitBreaker '%s': %s → %s (event=%s)",
            self.name, old_state.value, new_state.value, event.value,
        )

    def _time_until_half_open(self) -> float:
        """Seconds remaining until circuit can transition to HALF_OPEN."""
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.monotonic() - self._last_state_change
        remaining = self._config.cooldown_seconds - elapsed
        return max(0.0, remaining)


# ══════════════════════════════════════════════════════════════════════
# Exception
# ══════════════════════════════════════════════════════════════════════

class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""
    pass
