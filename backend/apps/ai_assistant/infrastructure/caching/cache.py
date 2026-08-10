"""
Cache Backend — abstract cache interface with multiple implementations.

Supports: InMemory, Redis (optional), LocalMemory with TTL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache Entry
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """A single cached item with TTL."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.monotonic)
    ttl_seconds: float = 300.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.monotonic)

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at


# ---------------------------------------------------------------------------
# Cache Backend (ABC)
# ---------------------------------------------------------------------------

class CacheBackend(ABC):
    """Abstract cache backend interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        ...

    @abstractmethod
    def set(self, key: str, value: Any, ttl: float = 300.0) -> None:
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        ...

    @abstractmethod
    def clear(self) -> int:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def size(self) -> int:
        ...

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        ...


# ---------------------------------------------------------------------------
# In-Memory Cache (LRU with TTL)
# ---------------------------------------------------------------------------

class InMemoryCache(CacheBackend):
    """
    Thread-safe in-memory LRU cache with TTL and eviction.
    Zero external dependencies.
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0) -> None:
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.access_count += 1
            entry.last_accessed = time.monotonic()
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float = 300.0) -> None:
        with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                del self._cache[key]

            # Evict oldest if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._evictions += 1

            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl if ttl > 0 else self._default_ttl,
            )

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._cache[key]
                return False
            return True

    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "backend": "in_memory",
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            "evictions": self._evictions,
        }


# ---------------------------------------------------------------------------
# Redis Cache Backend (optional)
# ---------------------------------------------------------------------------

class RedisCacheBackend(CacheBackend):
    """
    Redis-backed cache with TTL support.
    Requires `redis` package. Falls back gracefully if unavailable.
    """

    def __init__(self, url: str = "redis://localhost:6379/0", default_ttl: float = 300.0) -> None:
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        try:
            import redis
            self._client = redis.Redis.from_url(url, decode_responses=True)
            self._client.ping()
            self._available = True
        except Exception as exc:
            logger.warning("Redis unavailable, falling back to in-memory: %s", exc)
            self._client = None
            self._available = False
            self._fallback = InMemoryCache(default_ttl=default_ttl)

    def get(self, key: str) -> Optional[Any]:
        if not self._available:
            return self._fallback.get(key)
        try:
            raw = self._client.get(key)
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except Exception:
            self._misses += 1
            return None

    def set(self, key: str, value: Any, ttl: float = 300.0) -> None:
        if not self._available:
            return self._fallback.set(key, value, ttl)
        try:
            self._client.setex(key, int(ttl if ttl > 0 else self._default_ttl), json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("Redis set failed: %s", exc)

    def delete(self, key: str) -> bool:
        if not self._available:
            return self._fallback.delete(key)
        try:
            return bool(self._client.delete(key))
        except Exception:
            return False

    def clear(self) -> int:
        if not self._available:
            return self._fallback.clear()
        try:
            keys = self._client.keys("*")
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception:
            return 0

    def exists(self, key: str) -> bool:
        if not self._available:
            return self._fallback.exists(key)
        try:
            return bool(self._client.exists(key))
        except Exception:
            return False

    def size(self) -> int:
        if not self._available:
            return self._fallback.size()
        try:
            return self._client.dbsize()
        except Exception:
            return 0

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "backend": "redis" if self._available else "in_memory_fallback",
            "available": self._available,
            "size": self.size(),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
        }


# ---------------------------------------------------------------------------
# Cache Manager
# ---------------------------------------------------------------------------

class CacheManager:
    """
    High-level cache with key generation, decorators, and statistics.
    """

    def __init__(
        self,
        backend: Optional[CacheBackend] = None,
        prefix: str = "ai",
        default_ttl: float = 300.0,
    ) -> None:
        self._backend = backend or InMemoryCache()
        self._prefix = prefix
        self._default_ttl = default_ttl

    @property
    def backend(self) -> CacheBackend:
        return self._backend

    def get(self, key: str) -> Optional[Any]:
        full_key = self._full_key(key)
        return self._backend.get(full_key)

    def set(self, key: str, value: Any, ttl: float = 0) -> None:
        full_key = self._full_key(key)
        self._backend.set(full_key, value, ttl if ttl > 0 else self._default_ttl)

    def delete(self, key: str) -> bool:
        full_key = self._full_key(key)
        return self._backend.delete(full_key)

    def clear(self) -> int:
        return self._backend.clear()

    def exists(self, key: str) -> bool:
        full_key = self._full_key(key)
        return self._backend.exists(full_key)

    def get_or_set(
        self,
        key: str,
        factory,
        ttl: float = 0,
    ) -> Any:
        """Get from cache or compute and cache."""
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        self.set(key, value, ttl)
        return value

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern (prefix-based)."""
        count = 0
        full_pattern = self._full_key(pattern)
        if hasattr(self._backend, "_cache"):
            with self._backend._lock:
                keys_to_delete = [
                    k for k in self._backend._cache.keys()
                    if k.startswith(full_pattern)
                ]
                for k in keys_to_delete:
                    del self._backend._cache[k]
                    count += 1
        return count

    def stats(self) -> Dict[str, Any]:
        stats = self._backend.stats()
        stats["prefix"] = self._prefix
        stats["default_ttl"] = self._default_ttl
        return stats

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Generate a deterministic cache key from parts."""
        raw = ":".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:16]
