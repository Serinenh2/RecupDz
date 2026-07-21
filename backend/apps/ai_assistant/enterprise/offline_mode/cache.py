"""
Offline Cache Manager — offline-aware caching with stale-while-revalidate.

Features:
    Multi-level cache: L1 (hot/tiered), L2 (warm), L3 (cold/stale)
    Stale-while-revalidate: serve stale data while refreshing in background
    Automatic expiration with configurable TTL per level
    Cache warming on startup
    Eviction: LRU across all levels
    Statistics per level and overall

Integration:
    Used by OfflineMode to:
    - Cache Ollama responses for offline fallback
    - Cache knowledge search results
    - Cache repository query results
    - Serve cached data when services are DOWN

Architecture:
    ┌─────────────┐   miss   ┌─────────────┐   miss   ┌─────────────┐
    │ L1 (Hot)    │ ────────►│ L2 (Warm)   │ ────────►│ L3 (Cold)   │
    │ TTL: 5min   │          │ TTL: 1hour  │          │ TTL: 24hour │
    └─────────────┘          └─────────────┘          └─────────────┘
          │                        │                        │
          ▼                        ▼                        ▼
       HIT                      HIT                      HIT
       return                   return                   return
"""

from __future__ import annotations

import enum
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Enums & Data structures
# ══════════════════════════════════════════════════════════════════════

class CacheLevel(str, enum.Enum):
    L1_HOT = "l1_hot"
    L2_WARM = "l2_warm"
    L3_COLD = "l3_cold"


@dataclass
class CachedEntry:
    """A cached value with metadata."""
    key: str
    value: Any
    level: CacheLevel
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl_seconds: float = 300.0
    source: str = ""

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl_seconds

    @property
    def is_stale(self) -> bool:
        """Stale = expired but within 2x TTL (still usable as fallback)."""
        age = time.monotonic() - self.created_at
        return self.ttl_seconds < age <= (self.ttl_seconds * 2)

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at


@dataclass(frozen=True)
class CacheStats:
    """Immutable cache statistics."""
    l1_hits: int
    l1_misses: int
    l2_hits: int
    l2_misses: int
    l3_hits: int
    l3_misses: int
    total_entries: int
    total_size_bytes: int
    evictions: int
    stale_served: int

    def to_dict(self) -> Dict[str, Any]:
        total_requests = (
            self.l1_hits + self.l1_misses +
            self.l2_hits + self.l2_misses +
            self.l3_hits + self.l3_misses
        )
        total_hits = self.l1_hits + self.l2_hits + self.l3_hits
        return {
            "l1_hits": self.l1_hits,
            "l1_misses": self.l1_misses,
            "l2_hits": self.l2_hits,
            "l2_misses": self.l2_misses,
            "l3_hits": self.l3_hits,
            "l3_misses": self.l3_misses,
            "total_entries": self.total_entries,
            "total_size_bytes": self.total_size_bytes,
            "evictions": self.evictions,
            "stale_served": self.stale_served,
            "total_requests": total_requests,
            "hit_rate": round(total_hits / max(total_requests, 1), 3),
        }


# ══════════════════════════════════════════════════════════════════════
# Offline Cache Manager
# ══════════════════════════════════════════════════════════════════════

class OfflineCacheManager:
    """Multi-level cache with stale-while-revalidate support.

    Levels:
        L1 (Hot):    Fast access, short TTL. Most recent / frequently accessed.
        L2 (Warm):   Medium TTL. Previously successful queries.
        L3 (Cold):   Long TTL. Historical data, stale fallback.

    Usage:
        cache = OfflineCacheManager()
        cache.set("query:dechets", result, ttl=300, level=CacheLevel.L1_HOT)
        result = cache.get("query:dechets")  # Returns from L1 → L2 → L3

        # Stale-while-revalidate:
        result = cache.get("query:dechets", allow_stale=True)
        # Returns stale data if fresh data unavailable
    """

    def __init__(
        self,
        l1_max_size: int = 200,
        l1_ttl: float = 300.0,
        l2_max_size: int = 500,
        l2_ttl: float = 3600.0,
        l3_max_size: int = 1000,
        l3_ttl: float = 86400.0,
    ) -> None:
        self._lock = RLock()

        # L1 — Hot (most recent / frequently accessed)
        self._l1: OrderedDict[str, CachedEntry] = OrderedDict()
        self._l1_max = l1_max_size
        self._l1_ttl = l1_ttl

        # L2 — Warm (previously successful queries)
        self._l2: OrderedDict[str, CachedEntry] = OrderedDict()
        self._l2_max = l2_max_size
        self._l2_ttl = l2_ttl

        # L3 — Cold (historical, stale fallback)
        self._l3: OrderedDict[str, CachedEntry] = OrderedDict()
        self._l3_max = l3_max_size
        self._l3_ttl = l3_ttl

        # Statistics
        self._l1_hits = 0
        self._l1_misses = 0
        self._l2_hits = 0
        self._l2_misses = 0
        self._l3_hits = 0
        self._l3_misses = 0
        self._evictions = 0
        self._stale_served = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        key: str,
        *,
        allow_stale: bool = False,
    ) -> Optional[Any]:
        """Retrieve a value from cache. Searches L1 → L2 → L3.

        If allow_stale=True, returns expired entries as fallback.
        Promotes hits to L1 (most recently used).
        """
        with self._lock:
            # L1 lookup
            entry = self._l1.get(key)
            if entry is not None:
                if not entry.is_expired:
                    self._l1_hits += 1
                    entry.last_accessed = time.monotonic()
                    entry.access_count += 1
                    self._l1.move_to_end(key)
                    return entry.value
                elif allow_stale and entry.is_stale:
                    self._stale_served += 1
                    return entry.value
                else:
                    # Expired — demote from L1
                    self._l1.pop(key, None)
                    self._promote_to_l3(entry)

            self._l1_misses += 1

            # L2 lookup
            entry = self._l2.get(key)
            if entry is not None:
                if not entry.is_expired:
                    self._l2_hits += 1
                    entry.last_accessed = time.monotonic()
                    entry.access_count += 1
                    self._l2.move_to_end(key)
                    # Promote to L1
                    self._promote_to_l1(entry)
                    return entry.value
                elif allow_stale and entry.is_stale:
                    self._stale_served += 1
                    return entry.value
                else:
                    self._l2.pop(key, None)
                    self._promote_to_l3(entry)

            self._l2_misses += 1

            # L3 lookup
            entry = self._l3.get(key)
            if entry is not None:
                if not entry.is_expired:
                    self._l3_hits += 1
                    entry.last_accessed = time.monotonic()
                    entry.access_count += 1
                    self._l3.move_to_end(key)
                    # Promote to L2
                    self._promote_to_l2(entry)
                    return entry.value
                elif allow_stale and entry.is_stale:
                    self._stale_served += 1
                    return entry.value
                else:
                    self._l3.pop(key, None)

            self._l3_misses += 1
            return None

    def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: float = 0.0,
        level: CacheLevel = CacheLevel.L1_HOT,
        source: str = "",
    ) -> None:
        """Store a value in the specified cache level."""
        now = time.monotonic()
        actual_ttl = ttl if ttl > 0 else self._ttl_for_level(level)

        entry = CachedEntry(
            key=key,
            value=value,
            level=level,
            created_at=now,
            last_accessed=now,
            ttl_seconds=actual_ttl,
            source=source,
        )

        with self._lock:
            if level == CacheLevel.L1_HOT:
                self._l1[key] = entry
                self._l1.move_to_end(key)
                self._evict_l1()
            elif level == CacheLevel.L2_WARM:
                self._l2[key] = entry
                self._l2.move_to_end(key)
                self._evict_l2()
            else:
                self._l3[key] = entry
                self._l3.move_to_end(key)
                self._evict_l3()

    def delete(self, key: str) -> bool:
        """Remove a key from all levels."""
        with self._lock:
            removed = False
            removed |= self._l1.pop(key, None) is not None
            removed |= self._l2.pop(key, None) is not None
            removed |= self._l3.pop(key, None) is not None
            return removed

    def exists(self, key: str) -> bool:
        """Check if key exists in any level (non-expired)."""
        return self.get(key) is not None

    def clear(self, level: Optional[CacheLevel] = None) -> int:
        """Clear entries from a specific level or all levels. Returns count cleared."""
        with self._lock:
            if level is None:
                count = len(self._l1) + len(self._l2) + len(self._l3)
                self._l1.clear()
                self._l2.clear()
                self._l3.clear()
                return count
            if level == CacheLevel.L1_HOT:
                count = len(self._l1)
                self._l1.clear()
                return count
            if level == CacheLevel.L2_WARM:
                count = len(self._l2)
                self._l2.clear()
                return count
            if level == CacheLevel.L3_COLD:
                count = len(self._l3)
                self._l3.clear()
                return count
            return 0

    def warm(
        self,
        source_fn: Callable[[], Dict[str, Any]],
        level: CacheLevel = CacheLevel.L2_WARM,
        ttl: float = 0.0,
    ) -> int:
        """Warm the cache from a data source function.

        source_fn returns {key: value} pairs to populate.
        Returns count of entries warmed.
        """
        try:
            data = source_fn()
            count = 0
            for key, value in data.items():
                self.set(key, value, level=level, ttl=ttl, source="warm")
                count += 1
            logger.info("Cache warmed: %d entries at level %s", count, level.value)
            return count
        except Exception as exc:
            logger.debug("Cache warm failed: %s", exc)
            return 0

    def invalidate_pattern(self, pattern: str) -> int:
        """Remove all keys matching a prefix pattern. Returns count removed."""
        with self._lock:
            count = 0
            for level_data in (self._l1, self._l2, self._l3):
                keys_to_remove = [k for k in level_data if k.startswith(pattern)]
                for k in keys_to_remove:
                    level_data.pop(k, None)
                    count += 1
            return count

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            total_entries = len(self._l1) + len(self._l2) + len(self._l3)
            size_estimate = sum(
                len(str(e.value)) for entries in (self._l1, self._l2, self._l3)
                for e in entries.values()
            )
            return CacheStats(
                l1_hits=self._l1_hits,
                l1_misses=self._l1_misses,
                l2_hits=self._l2_hits,
                l2_misses=self._l2_misses,
                l3_hits=self._l3_hits,
                l3_misses=self._l3_misses,
                total_entries=total_entries,
                total_size_bytes=size_estimate,
                evictions=self._evictions,
                stale_served=self._stale_served,
            ).to_dict()

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Create a deterministic cache key from parts."""
        raw = ":".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ttl_for_level(self, level: CacheLevel) -> float:
        if level == CacheLevel.L1_HOT:
            return self._l1_ttl
        if level == CacheLevel.L2_WARM:
            return self._l2_ttl
        return self._l3_ttl

    def _promote_to_l1(self, entry: CachedEntry) -> None:
        new_entry = CachedEntry(
            key=entry.key,
            value=entry.value,
            level=CacheLevel.L1_HOT,
            created_at=time.monotonic(),
            last_accessed=time.monotonic(),
            access_count=entry.access_count,
            ttl_seconds=self._l1_ttl,
            source=entry.source,
        )
        self._l1[entry.key] = new_entry
        self._l1.move_to_end(entry.key)
        self._evict_l1()

    def _promote_to_l2(self, entry: CachedEntry) -> None:
        new_entry = CachedEntry(
            key=entry.key,
            value=entry.value,
            level=CacheLevel.L2_WARM,
            created_at=time.monotonic(),
            last_accessed=time.monotonic(),
            access_count=entry.access_count,
            ttl_seconds=self._l2_ttl,
            source=entry.source,
        )
        self._l2[entry.key] = new_entry
        self._l2.move_to_end(entry.key)
        self._evict_l2()

    def _promote_to_l3(self, entry: CachedEntry) -> None:
        new_entry = CachedEntry(
            key=entry.key,
            value=entry.value,
            level=CacheLevel.L3_COLD,
            created_at=entry.created_at,
            last_accessed=time.monotonic(),
            access_count=entry.access_count,
            ttl_seconds=self._l3_ttl,
            source=entry.source,
        )
        self._l3[entry.key] = new_entry
        self._l3.move_to_end(entry.key)
        self._evict_l3()

    def _evict_l1(self) -> None:
        while len(self._l1) > self._l1_max:
            _, evicted = self._l1.popitem(last=False)
            self._promote_to_l3(evicted)
            self._evictions += 1

    def _evict_l2(self) -> None:
        while len(self._l2) > self._l2_max:
            _, evicted = self._l2.popitem(last=False)
            self._promote_to_l3(evicted)
            self._evictions += 1

    def _evict_l3(self) -> None:
        while len(self._l3) > self._l3_max:
            self._l3.popitem(last=False)
            self._evictions += 1
