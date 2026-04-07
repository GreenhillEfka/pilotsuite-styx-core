"""P3-005: User Preference Learning — Multi-User Profiles, Conflict Resolution."""
from __future__ import annotations

import logging
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class PreferenceType(Enum):
    """Types of preferences."""
    BINARY = "binary"  # Yes/No
    NUMERIC = "numeric"  # Number value
    CATEGORICAL = "categorical"  # Category selection
    SCHEDULE = "schedule"  # Time-based


@dataclass
class Preference:
    """A user preference."""
    id: str
    user_id: str
    category: str
    key: str
    value: Any
    pref_type: PreferenceType
    confidence: float = 1.0
    learned_at: float = field(default_factory=time.time)
    source: str = "explicit"  # explicit, inferred, learned
    conflict_count: int = 0


@dataclass
class UserProfile:
    """Complete user profile."""
    user_id: str
    name: Optional[str]
    preferences: Dict[str, Preference] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    interaction_count: int = 0


class PreferenceConflict:
    """Represents a conflict between user preferences."""
    
    def __init__(self, preference1: Preference, preference2: Preference, context: str):
        self.preference1 = preference1
        self.preference2 = preference2
        self.context = context
        self.resolved = False
        self.resolution: Optional[str] = None


class UserPreferenceLearner:
    """Learns and manages user preferences with conflict resolution."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._profiles: Dict[str, UserProfile] = {}
        self._conflicts: List[PreferenceConflict] = []
        self._global_preferences: Dict[str, Any] = {}
        
        self._load_profiles()

    def create_profile(self, user_id: str, name: Optional[str] = None) -> UserProfile:
        """Create a new user profile."""
        profile = UserProfile(user_id=user_id, name=name)
        self._profiles[user_id] = profile
        self._save_profiles()
        logger.info(f"Created profile for user: {user_id}")
        return profile

    def set_preference(
        self,
        user_id: str,
        category: str,
        key: str,
        value: Any,
        pref_type: PreferenceType,
        source: str = "explicit",
    ) -> Preference:
        """Set a user preference."""
        import hashlib
        pref_id = hashlib.sha256(f"{user_id}:{category}:{key}".encode()).hexdigest()[:16]
        
        preference = Preference(
            id=pref_id,
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            pref_type=pref_type,
            source=source,
        )
        
        if user_id in self._profiles:
            profile = self._profiles[user_id]
            profile_key = f"{category}:{key}"
            
            # Check for conflicts
            existing = profile.preferences.get(profile_key)
            if existing and existing.value != value:
                self._record_conflict(existing, preference, "value_change")
            
            profile.preferences[profile_key] = preference
            profile.last_active = time.time()
            profile.interaction_count += 1
        
        self._save_profiles()
        return preference

    def infer_preference(
        self,
        user_id: str,
        category: str,
        key: str,
        value: Any,
        confidence: float,
    ) -> Optional[Preference]:
        """Infer a preference from behavior."""
        if user_id not in self._profiles:
            return None
        
        profile = self._profiles[user_id]
        profile_key = f"{category}:{key}"
        
        # Check if we have enough confidence
        if confidence < 0.6:
            return None
        
        # Check for existing preference
        existing = profile.preferences.get(profile_key)
        if existing:
            if existing.source == "explicit":
                # Don't override explicit preferences
                if existing.value != value:
                    self._record_conflict(existing, 
                        Preference("", user_id, category, key, value, PreferenceType.CATEGORICAL),
                        "inferred_vs_explicit")
                return None
            
            # Update inferred preference if confidence is higher
            if confidence > existing.confidence:
                existing.value = value
                existing.confidence = confidence
                existing.learned_at = time.time()
                self._save_profiles()
                return existing
        else:
            # Create new inferred preference
            preference = self.set_preference(
                user_id, category, key, value,
                PreferenceType.CATEGORICAL,
                source="inferred"
            )
            preference.confidence = confidence
            return preference
        
        return None

    def get_preference(
        self,
        user_id: str,
        category: str,
        key: str,
        default: Any = None
    ) -> Any:
        """Get a user preference."""
        if user_id not in self._profiles:
            return default
        
        profile = self._profiles[user_id]
        profile_key = f"{category}:{key}"
        
        preference = profile.preferences.get(profile_key)
        if preference:
            return preference.value
        
        # Fall back to global preference
        global_key = f"{category}:{key}"
        return self._global_preferences.get(global_key, default)

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile."""
        return self._profiles.get(user_id)

    def merge_profiles(self, user_id1: str, user_id2: str) -> Optional[UserProfile]:
        """Merge two user profiles (e.g., when accounts are linked)."""
        if user_id1 not in self._profiles or user_id2 not in self._profiles:
            return None
        
        profile1 = self._profiles[user_id1]
        profile2 = self._profiles[user_id2]
        
        # Merge preferences, recording conflicts
        for key, pref2 in profile2.preferences.items():
            if key in profile1.preferences:
                pref1 = profile1.preferences[key]
                if pref1.value != pref2.value:
                    self._record_conflict(pref1, pref2, "profile_merge")
            else:
                profile1.preferences[key] = pref2
        
        profile1.interaction_count += profile2.interaction_count
        profile1.last_active = max(profile1.last_active, profile2.last_active)
        
        # Remove merged profile
        del self._profiles[user_id2]
        self._save_profiles()
        
        logger.info(f"Merged profile {user_id2} into {user_id1}")
        return profile1

    def _record_conflict(self, pref1: Preference, pref2: Preference, context: str):
        """Record a preference conflict."""
        conflict = PreferenceConflict(pref1, pref2, context)
        self._conflicts.append(conflict)
        pref1.conflict_count += 1
        logger.warning(f"Preference conflict: {pref1.key} vs {pref2.key} in {context}")

    def resolve_conflict(self, conflict_index: int, resolution: str, winner: Preference):
        """Resolve a preference conflict."""
        if conflict_index >= len(self._conflicts):
            return False
        
        conflict = self._conflicts[conflict_index]
        conflict.resolved = True
        conflict.resolution = resolution
        
        # Update losing preference
        loser = conflict.preference1 if winner == conflict.preference2 else conflict.preference2
        loser.confidence *= 0.8  # Reduce confidence
        
        self._save_profiles()
        return True

    def set_global_preference(self, category: str, key: str, value: Any):
        """Set a global default preference."""
        self._global_preferences[f"{category}:{key}"] = value

    def get_conflicts(self, unresolved_only: bool = True) -> List[PreferenceConflict]:
        """Get preference conflicts."""
        if unresolved_only:
            return [c for c in self._conflicts if not c.resolved]
        return self._conflicts.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get preference learning statistics."""
        total_prefs = sum(len(p.preferences) for p in self._profiles.values())
        explicit_prefs = sum(
            sum(1 for pref in p.preferences.values() if pref.source == "explicit")
            for p in self._profiles.values()
        )
        inferred_prefs = total_prefs - explicit_prefs
        
        return {
            "total_users": len(self._profiles),
            "total_preferences": total_prefs,
            "explicit_preferences": explicit_prefs,
            "inferred_preferences": inferred_prefs,
            "unresolved_conflicts": len([c for c in self._conflicts if not c.resolved]),
            "global_preferences": len(self._global_preferences),
        }

    def _save_profiles(self):
        """Save profiles to disk."""
        profiles_file = self.data_dir / "user_profiles.json"
        
        data = {}
        for user_id, profile in self._profiles.items():
            data[user_id] = {
                "user_id": profile.user_id,
                "name": profile.name,
                "preferences": {
                    k: {
                        "id": p.id,
                        "category": p.category,
                        "key": p.key,
                        "value": p.value,
                        "pref_type": p.pref_type.value,
                        "confidence": p.confidence,
                        "learned_at": p.learned_at,
                        "source": p.source,
                        "conflict_count": p.conflict_count,
                    }
                    for k, p in profile.preferences.items()
                },
                "created_at": profile.created_at,
                "last_active": profile.last_active,
                "interaction_count": profile.interaction_count,
            }
        
        with open(profiles_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_profiles(self):
        """Load profiles from disk."""
        profiles_file = self.data_dir / "user_profiles.json"
        
        if not profiles_file.exists():
            return
        
        try:
            with open(profiles_file, 'r') as f:
                data = json.load(f)
            
            for user_id, profile_data in data.items():
                preferences = {}
                for k, pref_data in profile_data.get("preferences", {}).items():
                    preferences[k] = Preference(
                        id=pref_data["id"],
                        user_id=user_id,
                        category=pref_data["category"],
                        key=pref_data["key"],
                        value=pref_data["value"],
                        pref_type=PreferenceType(pref_data["pref_type"]),
                        confidence=pref_data.get("confidence", 1.0),
                        learned_at=pref_data.get("learned_at", 0),
                        source=pref_data.get("source", "explicit"),
                        conflict_count=pref_data.get("conflict_count", 0),
                    )
                
                profile = UserProfile(
                    user_id=user_id,
                    name=profile_data.get("name"),
                    preferences=preferences,
                    created_at=profile_data.get("created_at", 0),
                    last_active=profile_data.get("last_active", 0),
                    interaction_count=profile_data.get("interaction_count", 0),
                )
                self._profiles[user_id] = profile
            
            logger.info(f"Loaded {len(self._profiles)} user profiles")
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")


# Global default preference learner
default_preference_learner: Optional[UserPreferenceLearner] = None


def init_preference_learner(data_dir: str) -> UserPreferenceLearner:
    """Initialize global preference learner."""
    global default_preference_learner
    default_preference_learner = UserPreferenceLearner(data_dir)
    return default_preference_learner
