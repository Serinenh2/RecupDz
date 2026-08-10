"""
Rate Limiter — token bucket and sliding window rate limiting.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: float
    retry_after: float = 0.0

    def to_headers(self) -> Dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_at)),
            "Retry-After": str(int(self.retry_after)) if self.retry_after > 0 else "0",
        }

    def to_dict(self) -> Dict[str, any]:
        return {
            "allowed": self.allowed,
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at,
            "retry_after": self.retry_after,
        }


class TokenBucket:
    """Token bucket algorithm for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float, refill_interval: float = 1.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.refill_interval = refill_interval
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> RateLimitResult:
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return RateLimitResult(
                allowed=True,
                limit=self.capacity,
                remaining=int(self.tokens),
                reset_at=time.time() + (self.capacity - self.tokens) / self.refill_rate * self.refill_interval,
            )
        else:
            wait_time = (tokens - self.tokens) / self.refill_rate * self.refill_interval
            return RateLimitResult(
                allowed=False,
                limit=self.capacity,
                remaining=0,
                reset_at=time.time() + wait_time,
                retry_after=wait_time,
            )

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate / self.refill_interval
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class SlidingWindowCounter:
    """Sliding window counter for rate limiting."""

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: list[float] = []

    def check(self) -> RateLimitResult:
        now = time.time()
        cutoff = now - self.window_seconds
        self._requests = [t for t in self._requests if t > cutoff]

        if len(self._requests) < self.limit:
            self._requests.append(now)
            return RateLimitResult(
                allowed=True,
                limit=self.limit,
                remaining=self.limit - len(self._requests),
                reset_at=self._requests[0] + self.window_seconds if self._requests else now + self.window_seconds,
            )
        else:
            oldest = self._requests[0]
            wait_time = oldest + self.window_seconds - now
            return RateLimitResult(
                allowed=False,
                limit=self.limit,
                remaining=0,
                reset_at=oldest + self.window_seconds,
                retry_after=max(0, wait_time),
            )


class RateLimiter:
    """
    Multi-key rate limiter with configurable strategies.
    """

    def __init__(
        self,
        default_limit: int = 60,
        default_window: float = 60.0,
        strategy: str = "sliding_window",
    ) -> None:
        self._default_limit = default_limit
        self._default_window = default_window
        self._strategy = strategy
        self._limiters: Dict[str, SlidingWindowCounter | TokenBucket] = {}
        self._blocked: Dict[str, float] = {}

    def check(
        self,
        key: str,
        limit: Optional[int] = None,
        window: Optional[float] = None,
    ) -> RateLimitResult:
        """Check rate limit for a key."""
        # Check if blocked
        if key in self._blocked:
            if time.time() < self._blocked[key]:
                remaining = self._blocked[key] - time.time()
                return RateLimitResult(
                    allowed=False,
                    limit=limit or self._default_limit,
                    remaining=0,
                    reset_at=self._blocked[key],
                    retry_after=remaining,
                )
            else:
                del self._blocked[key]

        limiter = self._get_or_create(key, limit, window)
        return limiter.check()

    def block(self, key: str, duration_seconds: float) -> None:
        """Temporarily block a key."""
        self._blocked[key] = time.time() + duration_seconds

    def unblock(self, key: str) -> None:
        self._blocked.pop(key, None)

    def reset(self, key: Optional[str] = None) -> None:
        if key:
            self._limiters.pop(key, None)
            self._blocked.pop(key, None)
        else:
            self._limiters.clear()
            self._blocked.clear()

    def stats(self) -> Dict[str, any]:
        return {
            "strategy": self._strategy,
            "active_limiters": len(self._limiters),
            "blocked_keys": len(self._blocked),
            "default_limit": self._default_limit,
            "default_window": self._default_window,
        }

    def _get_or_create(
        self,
        key: str,
        limit: Optional[int],
        window: Optional[float],
    ) -> SlidingWindowCounter | TokenBucket:
        if key not in self._limiters:
            effective_limit = limit or self._default_limit
            effective_window = window or self._default_window

            if self._strategy == "token_bucket":
                self._limiters[key] = TokenBucket(
                    capacity=effective_limit,
                    refill_rate=effective_limit / effective_window,
                )
            else:
                self._limiters[key] = SlidingWindowCounter(
                    limit=effective_limit,
                    window_seconds=effective_window,
                )

        return self._limiters[key]
