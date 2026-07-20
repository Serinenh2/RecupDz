"""
User Memory — per-user profile, preferences, and interaction history.

Stores per-user:
    - Profile data (name, role, permissions, language)
    - Preferences (output format, theme, notifications)
    - Recent actions across sessions
    - Frequently accessed entities
    - Custom notes / bookmarks
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------

@dataclass
class UserProfile:
    """Cached user profile data."""
    user_id: str
    username: str = ""
    display_name: str = ""
    roles: List[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    language: str = "fr"
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "roles": self.roles,
            "language": self.language,
            "last_seen": self.last_seen,
        }


# ---------------------------------------------------------------------------
# User Preferences
# ---------------------------------------------------------------------------

@dataclass
class UserPreferences:
    """User-configurable preferences."""
    output_format: str = "text"     # text | markdown | json
    language: str = "fr"
    theme: str = "light"
    notifications_enabled: bool = True
    auto_summarize: bool = True
    max_context_messages: int = 10
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_format": self.output_format,
            "language": self.language,
            "theme": self.theme,
            "notifications_enabled": self.notifications_enabled,
            "auto_summarize": self.auto_summarize,
            "max_context_messages": self.max_context_messages,
            "custom": self.custom,
        }


# ---------------------------------------------------------------------------
# Action Record (per-user)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UserAction:
    """A user action across sessions."""
    action_type: str
    description: str
    entity_type: str = ""
    entity_id: str = ""
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "description": self.description,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# User Memory
# ---------------------------------------------------------------------------

class UserMemory:
    """
    Per-user in-memory store.

    Stores: profile, preferences, recent actions, frequent entities, bookmarks.
    LRU eviction for memory-boundedness.
    No database access.
    """

    def __init__(
        self,
        max_users: int = 100,
        max_actions_per_user: int = 100,
        max_frequent_entities: int = 20,
    ) -> None:
        self._max_users = max_users
        self._max_actions = max_actions_per_user
        self._max_frequent = max_frequent_entities

        self._profiles: OrderedDict[str, UserProfile] = OrderedDict()
        self._preferences: Dict[str, UserPreferences] = {}
        self._actions: Dict[str, Deque[UserAction]] = {}
        self._frequent_entities: Dict[str, Counter] = {}
        self._bookmarks: Dict[str, OrderedDict[str, Dict[str, Any]]] = {}

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def set_profile(
        self,
        user_id: str,
        *,
        username: str = "",
        display_name: str = "",
        roles: Optional[List[str]] = None,
        permissions: Optional[Set[str]] = None,
        language: str = "fr",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UserProfile:
        with self._lock:
            if user_id not in self._profiles:
                self._evict_if_full()
            profile = self._profiles.get(user_id) or UserProfile(user_id=user_id)
            if username:
                profile.username = username
            if display_name:
                profile.display_name = display_name
            if roles is not None:
                profile.roles = roles
            if permissions is not None:
                profile.permissions = permissions
            profile.language = language
            if metadata:
                profile.metadata.update(metadata)
            profile.last_seen = time.time()
            self._profiles[user_id] = profile
            self._profiles.move_to_end(user_id)
            return profile

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        with self._lock:
            profile = self._profiles.get(user_id)
            if profile:
                profile.last_seen = time.time()
                self._profiles.move_to_end(user_id)
            return profile

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        with self._lock:
            if user_id not in self._profiles:
                self._evict_if_full()
                self._profiles[user_id] = UserProfile(user_id=user_id)
            return self._profiles[user_id]

    def delete_profile(self, user_id: str) -> bool:
        with self._lock:
            deleted = user_id in self._profiles
            self._profiles.pop(user_id, None)
            self._preferences.pop(user_id, None)
            self._actions.pop(user_id, None)
            self._frequent_entities.pop(user_id, None)
            self._bookmarks.pop(user_id, None)
            return deleted

    def list_users(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in reversed(self._profiles.values())]

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def set_preference(self, user_id: str, key: str, value: Any) -> None:
        with self._lock:
            prefs = self._preferences.setdefault(user_id, UserPreferences())
            if hasattr(prefs, key):
                setattr(prefs, key, value)
            else:
                prefs.custom[key] = value

    def get_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        with self._lock:
            prefs = self._preferences.get(user_id)
            if prefs is None:
                return default
            if hasattr(prefs, key):
                return getattr(prefs, key)
            return prefs.custom.get(key, default)

    def get_preferences(self, user_id: str) -> UserPreferences:
        with self._lock:
            return self._preferences.setdefault(user_id, UserPreferences())

    def set_preferences(self, user_id: str, prefs: UserPreferences) -> None:
        with self._lock:
            self._preferences[user_id] = prefs

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def record_action(
        self,
        user_id: str,
        action_type: str,
        description: str,
        entity_type: str = "",
        entity_id: str = "",
        session_id: str = "",
    ) -> UserAction:
        action = UserAction(
            action_type=action_type,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            session_id=session_id,
        )
        with self._lock:
            buf = self._actions.setdefault(user_id, deque(maxlen=self._max_actions))
            buf.append(action)
            # Update frequent entities
            if entity_type and entity_id:
                counter = self._frequent_entities.setdefault(user_id, Counter())
                counter[f"{entity_type}:{entity_id}"] += 1
        return action

    def get_recent_actions(self, user_id: str, limit: int = 10) -> List[UserAction]:
        with self._lock:
            buf = self._actions.get(user_id, deque())
            return list(buf)[-limit:]

    def get_actions_by_entity(self, user_id: str, entity_type: str) -> List[UserAction]:
        with self._lock:
            buf = self._actions.get(user_id, deque())
            return [a for a in buf if a.entity_type == entity_type]

    def get_actions_by_type(self, user_id: str, action_type: str) -> List[UserAction]:
        with self._lock:
            buf = self._actions.get(user_id, deque())
            return [a for a in buf if a.action_type == action_type]

    # ------------------------------------------------------------------
    # Frequent entities
    # ------------------------------------------------------------------

    def get_frequent_entities(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        with self._lock:
            counter = self._frequent_entities.get(user_id, Counter())
            most_common = counter.most_common(limit)
            return [
                {
                    "entity_key": key,
                    "entity_type": key.split(":")[0] if ":" in key else "",
                    "entity_id": key.split(":")[1] if ":" in key else key,
                    "count": count,
                }
                for key, count in most_common
            ]

    # ------------------------------------------------------------------
    # Bookmarks
    # ------------------------------------------------------------------

    def add_bookmark(self, user_id: str, key: str, data: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            bm = self._bookmarks.setdefault(user_id, OrderedDict())
            bm[key] = {"key": key, "data": data or {}, "timestamp": time.time()}

    def get_bookmarks(self, user_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            bm = self._bookmarks.get(user_id, OrderedDict())
            return list(bm.values())

    def remove_bookmark(self, user_id: str, key: str) -> bool:
        with self._lock:
            bm = self._bookmarks.get(user_id, OrderedDict())
            if key in bm:
                del bm[key]
                return True
            return False

    def has_bookmark(self, user_id: str, key: str) -> bool:
        with self._lock:
            bm = self._bookmarks.get(user_id, OrderedDict())
            return key in bm

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_actions(self, user_id: str, query: str, limit: int = 10) -> List[UserAction]:
        query_lower = query.lower()
        with self._lock:
            buf = self._actions.get(user_id, deque())
            return [
                a for a in buf
                if query_lower in a.description.lower() or query_lower in a.action_type.lower()
            ][:limit]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def user_count(self) -> int:
        with self._lock:
            return len(self._profiles)

    def user_stats(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            profile = self._profiles.get(user_id)
            actions = self._actions.get(user_id, deque())
            prefs = self._preferences.get(user_id)
            return {
                "profile": profile.to_dict() if profile else None,
                "actions_count": len(actions),
                "preferences": prefs.to_dict() if prefs else None,
                "frequent_entity_count": len(self._frequent_entities.get(user_id, Counter())),
                "bookmark_count": len(self._bookmarks.get(user_id, OrderedDict())),
            }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def clear_user(self, user_id: str) -> Dict[str, int]:
        counts = {}
        with self._lock:
            counts["profile"] = 1 if self._profiles.pop(user_id, None) else 0
            counts["preferences"] = 1 if self._preferences.pop(user_id, None) else 0
            counts["actions"] = len(self._actions.pop(user_id, deque()))
            counts["frequent"] = 1 if self._frequent_entities.pop(user_id, None) else 0
            counts["bookmarks"] = len(self._bookmarks.pop(user_id, OrderedDict()))
        return counts

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._profiles)
            self._profiles.clear()
            self._preferences.clear()
            self._actions.clear()
            self._frequent_entities.clear()
            self._bookmarks.clear()
            return count

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_if_full(self) -> None:
        while len(self._profiles) >= self._max_users:
            _, oldest_id = self._profiles.popitem(last=False)
            self._preferences.pop(oldest_id, None)
            self._actions.pop(oldest_id, None)
            self._frequent_entities.pop(oldest_id, None)
            self._bookmarks.pop(oldest_id, None)
