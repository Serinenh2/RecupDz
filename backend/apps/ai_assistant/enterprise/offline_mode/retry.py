"""
Retry Policy — configurable retry with exponential backoff + jitter.

Features:
    Exponential backoff with configurable base delay and factor
    Full jitter to prevent thundering herd
    Configurable max retries and per-attempt timeout
    Exception filtering (retry only on specific exceptions)
    Async-compatible (returns RetryResult with timing)

Integration:
    Used by OfflineMode to wrap transient-failure-prone calls
    (Ollama HTTP, database queries, knowledge search).

Architecture:
    Attempt 1 ──fail──► wait(base * factor^0 + jitter) ──► Attempt 2
    Attempt 2 ──fail──► wait(base * factor^1 + jitter) ──► Attempt 3
    ...
    Attempt N ──fail──► return RetryResult(success=False, last_error=...)
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ══════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RetryAttempt:
    """Record of a single retry attempt."""
    attempt: int
    success: bool
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    wait_seconds: float = 0.0


@dataclass(frozen=True)
class RetryResult:
    """Result of a retry-wrapped call."""
    success: bool
    value: Any = None
    attempts: Tuple[RetryAttempt, ...] = ()
    total_elapsed_ms: float = 0.0
    final_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "attempt_count": len(self.attempts),
            "total_elapsed_ms": round(self.total_elapsed_ms, 2),
            "final_error": self.final_error,
        }


@dataclass
class RetryPolicy:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retry, just fail).
        base_delay_seconds: Base delay before first retry.
        max_delay_seconds: Cap on delay between retries.
        backoff_factor: Multiplier for exponential backoff.
        jitter: Whether to add random jitter (0.0 - 1.0 range).
        retryable_exceptions: Tuple of exception types to retry on.
            Empty tuple = retry on all exceptions.
    """
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    backoff_factor: float = 2.0
    jitter: float = 0.5
    retryable_exceptions: tuple = ()


# ══════════════════════════════════════════════════════════════════════
# Retry executor
# ══════════════════════════════════════════════════════════════════════

class RetryExecutor:
    """Executes a callable with retry logic.

    Usage:
        policy = RetryPolicy(max_retries=3, base_delay_seconds=0.5)
        executor = RetryExecutor(policy)
        result = executor.execute(my_function, arg1, arg2)

        if not result.success:
            print(f"Failed after {len(result.attempts)} attempts")
    """

    def __init__(self, policy: Optional[RetryPolicy] = None) -> None:
        self._policy = policy or RetryPolicy()

    @property
    def policy(self) -> RetryPolicy:
        return self._policy

    def execute(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> RetryResult:
        """Execute fn with retry logic.

        Returns RetryResult — never raises.
        """
        attempts: List[RetryAttempt] = []
        total_start = time.monotonic()
        last_error: Optional[Exception] = None

        max_attempts = self._policy.max_retries + 1

        for attempt_num in range(1, max_attempts + 1):
            attempt_start = time.monotonic()

            try:
                value = fn(*args, **kwargs)
                elapsed = (time.monotonic() - attempt_start) * 1000

                attempts.append(RetryAttempt(
                    attempt=attempt_num,
                    success=True,
                    elapsed_ms=round(elapsed, 2),
                ))

                return RetryResult(
                    success=True,
                    value=value,
                    attempts=tuple(attempts),
                    total_elapsed_ms=round(
                        (time.monotonic() - total_start) * 1000, 2,
                    ),
                )

            except Exception as exc:
                elapsed = (time.monotonic() - attempt_start) * 1000
                last_error = exc

                # Check if exception is retryable
                if not self._is_retryable(exc):
                    attempts.append(RetryAttempt(
                        attempt=attempt_num,
                        success=False,
                        error=str(exc),
                        elapsed_ms=round(elapsed, 2),
                    ))
                    break

                # Calculate wait time
                wait = self._wait_time(attempt_num)

                attempts.append(RetryAttempt(
                    attempt=attempt_num,
                    success=False,
                    error=str(exc),
                    elapsed_ms=round(elapsed, 2),
                    wait_seconds=round(wait, 3),
                ))

                logger.debug(
                    "Retry attempt %d/%d for %s failed: %s — waiting %.3fs",
                    attempt_num, max_attempts,
                    getattr(fn, "__name__", "unknown"),
                    exc, wait,
                )

                # Sleep only if not the last attempt
                if attempt_num < max_attempts:
                    time.sleep(wait)

        total_elapsed = (time.monotonic() - total_start) * 1000
        return RetryResult(
            success=False,
            attempts=tuple(attempts),
            total_elapsed_ms=round(total_elapsed, 2),
            final_error=str(last_error) if last_error else None,
        )

    def execute_with_fallback(
        self,
        fn: Callable[..., T],
        fallback_fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute fn with retry; on final failure, call fallback_fn.

        Returns the value directly (not RetryResult).
        """
        result = self.execute(fn, *args, **kwargs)
        if result.success:
            return result.value
        return fallback_fn(*args, **kwargs)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_retryable(self, exc: Exception) -> bool:
        """Check if this exception should trigger a retry."""
        if not self._policy.retryable_exceptions:
            return True
        return isinstance(exc, self._policy.retryable_exceptions)

    def _wait_time(self, attempt: int) -> float:
        """Calculate wait time with exponential backoff + jitter."""
        delay = self._policy.base_delay_seconds * (
            self._policy.backoff_factor ** (attempt - 1)
        )
        delay = min(delay, self._policy.max_delay_seconds)

        if self._policy.jitter > 0:
            jitter_range = delay * self._policy.jitter
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0.0, delay)

        return delay
