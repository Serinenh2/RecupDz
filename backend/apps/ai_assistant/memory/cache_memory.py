"""
Cache Memory — TTL-based cache for expensive queries and LLM responses.

Features:
    - Per-key TTL expiry
    - LRU eviction when capacity is reached
    - Namespace/tag-based bulk invalidation
    - Hit/miss statistics
    - Decorator for caching function results
"""

from __future__ import annotations

import functools
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

F = Callable[..., Any]


# ---------------------------------------------------------------------------
# Cache Entry
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """A single cached value."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0
    tags: List[str] = field(default_factory=list)
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def remaining_ttl(self) -> float:
        return max(0.0, self.ttl_seconds - self.age_seconds)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "age_seconds": round(self.age_seconds, 1),
            "remaining_ttl": round(self.remaining_ttl, 1),
            "hit_count": self.hit_count,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# Cache Statistics
# ---------------------------------------------------------------------------

@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired_cleanups: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expired_cleanups": self.expired_cleanups,
            "total": self.total,
            "hit_rate": round(self.hit_rate, 3),
        }


# ---------------------------------------------------------------------------
# Cache Memory
# ---------------------------------------------------------------------------

class CacheMemory:
    """
    In-memory TTL cache with LRU eviction.

    No database. Thread-safe.
    """

    def __init__(self, max_entries: int = 500, default_ttl: float = 300.0) -> None:
        self._max = max_entries
        self._default_ttl = default_ttl
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._stats.misses += 1
                return None
            if entry.is_expired:
                del self._entries[key]
                self._stats.expired_cleanups += 1
                self._stats.misses += 1
                return None
            entry.hit_count += 1
            self._entries.move_to_end(key)
            self._stats.hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        with self._lock:
            # Remove old entry if exists
            if key in self._entries:
                del self._entries[key]
            # Evict if full
            while len(self._entries) >= self._max:
                self._evict_oldest()
            self._entries[key] = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl if ttl is not None else self._default_ttl,
                tags=tags or [],
            )

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        *,
        ttl: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> Any:
        """Get from cache, or compute and store."""
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        self.set(key, value, ttl=ttl, tags=tags)
        return value

    def has(self, key: str) -> bool:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._entries[key]
                return False
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    # ------------------------------------------------------------------
    # Tag-based operations
    # ------------------------------------------------------------------

    def invalidate_by_tag(self, tag: str) -> int:
        """Remove all entries with the given tag."""
        removed = 0
        with self._lock:
            to_remove = [k for k, e in self._entries.items() if tag in e.tags]
            for k in to_remove:
                del self._entries[k]
                removed += 1
        return removed

    def invalidate_by_prefix(self, prefix: str) -> int:
        """Remove all keys starting with prefix."""
        removed = 0
        with self._lock:
            to_remove = [k for k in self._entries if k.startswith(prefix)]
            for k in to_remove:
                del self._entries[k]
                removed += 1
        return removed

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        removed = 0
        with self._lock:
            expired = [k for k, e in self._entries.items() if e.is_expired]
            for k in expired:
                del self._entries[k]
                removed += 1
            self._stats.expired_cleanups += removed
        return removed

    def clear(self) -> int:
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._entries.get(key)
            return entry.to_dict() if entry else None

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._entries.keys())

    def list_entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._entries.values()]

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def stats(self) -> CacheStats:
        return self._stats

    def reset_stats(self) -> None:
        self._stats = CacheStats()

    # ------------------------------------------------------------------
    # Key building
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Build a cache key from parts."""
        raw = ":".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    @staticmethod
    def make_prefix(*parts: Any) -> str:
        """Build a key prefix (not hashed)."""
        return ":".join(str(p) for p in parts) + ":"

    # ------------------------------------------------------------------
    # Decorator
    # ------------------------------------------------------------------

    def cached(
        self,
        ttl: Optional[float] = None,
        prefix: str = "",
        tags: Optional[List[str]] = None,
    ) -> Callable[[F], F]:
        """
        Decorator that caches function results.

        Usage:
            cache = CacheMemory()

            @cache.cached(ttl=60, prefix="search")
            def search_entities(query):
                ...
        """
        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                key_parts = [prefix or func.__name__] + list(args)
                if kwargs:
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                key = self.make_key(*key_parts)
                result = self.get(key)
                if result is not None:
                    return result
                result = func(*args, **kwargs)
                self.set(key, result, ttl=ttl, tags=tags)
                return result
            wrapper.invalidate = lambda *a, **kw: self.delete(  # type: ignore
                self.make_key(*([prefix or func.__name__] + list(a)))
            )
            return wrapper  # type: ignore
        return decorator

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_oldest(self) -> None:
        if self._entries:
            self._entries.popitem(last=False)
            self._stats.evictions += 1
