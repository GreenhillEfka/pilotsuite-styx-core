"""User Preference Storage for Multi-User Preference Learning (MUP-L).

Provides persistent storage for user preferences with JSONL backend.
Privacy-first: all data remains local.

Design Doc: docs/MUPL_DESIGN.md
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UserPreferences:
    """Preferences for a single user."""
    
    user_id: str
    name: str = "Unknown"
    preferences: dict[str, Any] = field(default_factory=lambda: {
        "light_brightness": {"default": 0.8, "by_zone": {}},
        "media_volume": {"default": 0.5, "by_zone": {}},
        "temperature": {"default": 21.0, "by_zone": {}},
        "mood_weights": {"comfort": 0.5, "frugality": 0.5, "joy": 0.5},
    })
    patterns: dict[str, Any] = field(default_factory=dict)
    last_seen: str | None = None
    interaction_count: int = 0
    priority: float = 0.5  # For conflict resolution in multi-user scenarios
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "preferences": self.preferences,
            "patterns": self.patterns,
            "last_seen": self.last_seen,
            "interaction_count": self.interaction_count,
            "priority": self.priority,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserPreferences":
        return cls(
            user_id=data.get("user_id", "unknown"),
            name=data.get("name", "Unknown"),
            preferences=data.get("preferences", {}),
            patterns=data.get("patterns", {}),
            last_seen=data.get("last_seen"),
            interaction_count=data.get("interaction_count", 0),
            priority=data.get("priority", 0.5),
        )


@dataclass
class DeviceAffinity:
    """Affinity of devices to users."""
    
    entity_id: str
    primary_user: str | None = None
    usage_distribution: dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "primary_user": self.primary_user,
            "usage_distribution": self.usage_distribution,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceAffinity":
        return cls(
            entity_id=data.get("entity_id", ""),
            primary_user=data.get("primary_user"),
            usage_distribution=data.get("usage_distribution", {}),
        )


class UserPreferenceStore:
    """Persistent storage for user preferences.
    
    Features:
    - JSONL persistence for durability
    - In-memory cache for fast access
    - Privacy-first: all data remains local
    
    Storage format:
    - /data/user_preferences.jsonl - Main user data (one entry per user)
    - /data/device_affinities.jsonl - Device affinity data
    """
    
    def __init__(
        self,
        *,
        data_dir: str = "/data",
        persist: bool = True,
    ):
        self.data_dir = data_dir
        self.persist = persist
        self.users_path = os.path.join(data_dir, "user_preferences.jsonl")
        self.affinities_path = os.path.join(data_dir, "device_affinities.jsonl")
        
        # In-memory cache
        self._users: dict[str, UserPreferences] = {}
        self._affinities: dict[str, DeviceAffinity] = {}
        self._active_users: list[str] = []
        
        # Load on init
        if self.persist:
            self._load()
    
    def _load(self) -> None:
        """Load stored preferences from disk."""
        # Load users
        try:
            with open(self.users_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        data = json.loads(line.strip())
                        user = UserPreferences.from_dict(data)
                        self._users[user.user_id] = user
                    except Exception:
                        continue
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        # Load device affinities
        try:
            with open(self.affinities_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        data = json.loads(line.strip())
                        aff = DeviceAffinity.from_dict(data)
                        self._affinities[aff.entity_id] = aff
                    except Exception:
                        continue
        except FileNotFoundError:
            pass
        except Exception:
            pass
    
    def _save_users(self) -> None:
        """Save all users to disk."""
        if not self.persist:
            return
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Write all users (overwrite)
        with open(self.users_path, "w", encoding="utf-8") as fh:
            for user in self._users.values():
                fh.write(json.dumps(user.to_dict(), ensure_ascii=False) + "\n")
    
    def _save_affinities(self) -> None:
        """Save all device affinities to disk."""
        if not self.persist:
            return
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        with open(self.affinities_path, "w", encoding="utf-8") as fh:
            for aff in self._affinities.values():
                fh.write(json.dumps(aff.to_dict(), ensure_ascii=False) + "\n")
    
    # ==================== User Operations ====================
    
    def get_user(self, user_id: str) -> UserPreferences | None:
        """Get a user by ID."""
        return self._users.get(user_id)
    
    def get_all_users(self) -> dict[str, UserPreferences]:
        """Get all users."""
        return self._users.copy()
    
    def upsert_user(self, user: UserPreferences) -> None:
        """Create or update a user."""
        self._users[user.user_id] = user
        self._save_users()
    
    def update_user_preferences(
        self,
        user_id: str,
        preferences: dict[str, Any],
    ) -> UserPreferences | None:
        """Update preferences for a user.
        
        Merges with existing preferences.
        """
        user = self._users.get(user_id)
        if not user:
            user = UserPreferences(user_id=user_id)
            self._users[user_id] = user
        
        # Deep merge preferences
        for key, value in preferences.items():
            if isinstance(value, dict) and key in user.preferences:
                user.preferences[key].update(value)
            else:
                user.preferences[key] = value
        
        self._save_users()
        return user
    
    def update_user_priority(self, user_id: str, priority: float) -> bool:
        """Update user priority for conflict resolution."""
        user = self._users.get(user_id)
        if not user:
            return False
        
        user.priority = max(0.0, min(1.0, priority))
        self._save_users()
        return True
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user and all associated data."""
        if user_id not in self._users:
            return False
        
        del self._users[user_id]
        
        # Remove from device affinities
        for entity_id, aff in self._affinities.items():
            if aff.primary_user == user_id:
                aff.primary_user = None
            if user_id in aff.usage_distribution:
                del aff.usage_distribution[user_id]
        
        # Remove from active users
        if user_id in self._active_users:
            self._active_users.remove(user_id)
        
        self._save_users()
        self._save_affinities()
        return True
    
    def record_interaction(self, user_id: str) -> None:
        """Record an interaction for a user."""
        user = self._users.get(user_id)
        if user:
            user.interaction_count += 1
            user.last_seen = _now_iso()
            self._save_users()
    
    # ==================== Device Affinity Operations ====================
    
    def get_device_affinity(self, entity_id: str) -> DeviceAffinity | None:
        """Get device affinity for an entity."""
        return self._affinities.get(entity_id)
    
    def update_device_affinity(
        self,
        entity_id: str,
        user_id: str,
        smoothing_alpha: float = 0.1,
    ) -> DeviceAffinity:
        """Update device affinity based on usage.
        
        Uses exponential smoothing to track which users use which devices.
        """
        if entity_id not in self._affinities:
            self._affinities[entity_id] = DeviceAffinity(entity_id=entity_id)
        
        aff = self._affinities[entity_id]
        
        # Update usage distribution with smoothing
        if user_id not in aff.usage_distribution:
            aff.usage_distribution[user_id] = 0.0
        
        # Boost this user, decay others
        for uid in aff.usage_distribution:
            if uid == user_id:
                aff.usage_distribution[uid] += smoothing_alpha
            else:
                aff.usage_distribution[uid] *= (1 - smoothing_alpha)
        
        # Normalize
        total = sum(aff.usage_distribution.values())
        if total > 0:
            for uid in aff.usage_distribution:
                aff.usage_distribution[uid] = round(aff.usage_distribution[uid] / total, 3)
        
        # Update primary user (highest affinity)
        if aff.usage_distribution:
            aff.primary_user = max(
                aff.usage_distribution.keys(),
                key=lambda uid: aff.usage_distribution[uid],
            )
        
        self._save_affinities()
        return aff
    
    # ==================== Active Users ====================
    
    def set_active_users(self, user_ids: list[str]) -> None:
        """Set the list of currently active users."""
        self._active_users = user_ids
    
    def get_active_users(self) -> list[str]:
        """Get the list of currently active users."""
        return self._active_users.copy()
    
    def add_active_user(self, user_id: str) -> None:
        """Add a user to active list."""
        if user_id not in self._active_users:
            self._active_users.append(user_id)
    
    def remove_active_user(self, user_id: str) -> None:
        """Remove a user from active list."""
        if user_id in self._active_users:
            self._active_users.remove(user_id)
    
    # ==================== Aggregation ====================
    
    def get_aggregated_mood(self, user_ids: list[str] | None = None) -> dict[str, float]:
        """Aggregate mood for multiple users.
        
        Args:
            user_ids: Users to aggregate (default: active users)
            
        Returns:
            Aggregated mood dict with comfort, frugality, joy
        """
        if user_ids is None:
            user_ids = self._active_users
        
        if not user_ids:
            return {"comfort": 0.5, "frugality": 0.5, "joy": 0.5}
        
        if len(user_ids) == 1:
            user = self._users.get(user_ids[0])
            if user:
                return user.preferences.get("mood_weights", {"comfort": 0.5, "frugality": 0.5, "joy": 0.5})
            return {"comfort": 0.5, "frugality": 0.5, "joy": 0.5}
        
        # Weighted aggregation by priority
        total_weight = 0.0
        mood = {"comfort": 0.0, "frugality": 0.0, "joy": 0.0}
        
        for user_id in user_ids:
            user = self._users.get(user_id)
            if not user:
                continue
            
            weight = user.priority
            user_mood = user.preferences.get("mood_weights", {})
            
            mood["comfort"] += user_mood.get("comfort", 0.5) * weight
            mood["frugality"] += user_mood.get("frugality", 0.5) * weight
            mood["joy"] += user_mood.get("joy", 0.5) * weight
            total_weight += weight
        
        if total_weight > 0:
            mood = {k: round(v / total_weight, 3) for k, v in mood.items()}
        
        return mood
    
    # ==================== Privacy ====================
    
    def export_user_data(self, user_id: str) -> dict[str, Any] | None:
        """Export all data for a user (privacy/GDPR)."""
        user = self._users.get(user_id)
        if not user:
            return None
        
        # Include relevant device affinities
        affinities = {}
        for entity_id, aff in self._affinities.items():
            if user_id in aff.usage_distribution:
                affinities[entity_id] = aff.usage_distribution
        
        return {
            "user": user.to_dict(),
            "device_affinities": affinities,
            "exported_at": _now_iso(),
        }
    
    # ==================== Generic Extra Storage ====================

    def _load_extra(self, key: str) -> Any:
        """Load a named JSON blob from /data/{key}.json."""
        path = os.path.join(self.data_dir, f"{key}.json")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save_extra(self, key: str, data: Any) -> None:
        """Save a named JSON blob to /data/{key}.json."""
        if not self.persist:
            return
        os.makedirs(self.data_dir, exist_ok=True)
        path = os.path.join(self.data_dir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def clear_all(self) -> None:
        """Clear all stored data (for testing/reset)."""
        self._users.clear()
        self._affinities.clear()
        self._active_users.clear()

        if self.persist:
            for path in [self.users_path, self.affinities_path]:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass


# Singleton instance (lazily initialized)
_store: UserPreferenceStore | None = None


def get_user_preference_store() -> UserPreferenceStore:
    """Get the global UserPreferenceStore instance."""
    global _store
    if _store is None:
        _store = UserPreferenceStore()
    return _store


def init_user_preference_store(**kwargs) -> UserPreferenceStore:
    """Initialize the global UserPreferenceStore with custom config."""
    global _store
    _store = UserPreferenceStore(**kwargs)
    return _store