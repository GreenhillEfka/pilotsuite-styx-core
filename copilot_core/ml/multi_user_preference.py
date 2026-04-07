"""Multi-User Preference Learning — Personalized automation per user."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class PreferenceCategory(Enum):
    """Preference categories."""
    TEMPERATURE = "temperature"
    LIGHTING = "lighting"
    MEDIA = "media"
    SCHEDULE = "schedule"
    SCENES = "scenes"
    NOTIFICATIONS = "notifications"


@dataclass
class UserPreference:
    """User preference entry."""
    user_id: str
    category: PreferenceCategory
    entity_id: str
    preferred_value: Any
    confidence: float
    context: Dict[str, Any] = field(default_factory=dict)
    learned_at: float = field(default_factory=lambda: time.time())
    usage_count: int = 0


@dataclass
class UserPattern:
    """Learned user pattern."""
    user_id: str
    pattern_type: str
    trigger: Dict[str, Any]
    action: Dict[str, Any]
    confidence: float
    occurrences: int
    last_seen: float


class MultiUserPreferenceLearner:
    """
    Learns and applies per-user preferences for personalized automation.
    
    Implements federated learning approach:
    - Per-user preference profiles
    - Context-aware recommendations
    - Confidence-weighted predictions
    """

    def __init__(self, min_confidence: float = 0.7):
        self._preferences: Dict[str, List[UserPreference]] = defaultdict(list)
        self._patterns: Dict[str, List[UserPattern]] = defaultdict(list)
        self._user_profiles: Dict[str, Dict] = {}
        self._min_confidence = min_confidence

    def record_preference(
        self,
        user_id: str,
        category: PreferenceCategory,
        entity_id: str,
        value: Any,
        context: Optional[Dict] = None,
    ):
        """Record or update a user preference."""
        # Find existing preference
        for pref in self._preferences[user_id]:
            if pref.category == category and pref.entity_id == entity_id:
                # Update existing
                pref.preferred_value = value
                pref.confidence = min(1.0, pref.confidence + 0.1)
                pref.usage_count += 1
                pref.context.update(context or {})
                return
        
        # Create new preference
        pref = UserPreference(
            user_id=user_id,
            category=category,
            entity_id=entity_id,
            preferred_value=value,
            confidence=0.5,
            context=context or {},
        )
        self._preferences[user_id].append(pref)
        logger.info(f"Preference recorded: {user_id} prefers {entity_id}={value}")

    def learn_pattern(
        self,
        user_id: str,
        trigger: Dict[str, Any],
        action: Dict[str, Any],
    ):
        """Learn a user automation pattern."""
        # Check if similar pattern exists
        for pattern in self._patterns[user_id]:
            if self._patterns_match(pattern.trigger, trigger):
                pattern.occurrences += 1
                pattern.last_seen = time.time()
                pattern.confidence = min(1.0, pattern.occurrences / 10.0)
                return
        
        # Create new pattern
        pattern = UserPattern(
            user_id=user_id,
            pattern_type=trigger.get("type", "custom"),
            trigger=trigger,
            action=action,
            confidence=0.3,
            occurrences=1,
            last_seen=time.time(),
        )
        self._patterns[user_id].append(pattern)
        logger.info(f"Pattern learned: {user_id} — {trigger} → {action}")

    def _patterns_match(self, p1: Dict, p2: Dict) -> bool:
        """Check if two patterns are similar."""
        return (
            p1.get("type") == p2.get("type") and
            p1.get("entity_id") == p2.get("entity_id") and
            p1.get("time_range") == p2.get("time_range")
        )

    def get_preference(
        self,
        user_id: str,
        category: PreferenceCategory,
        entity_id: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> Optional[Any]:
        """Get preferred value for user."""
        prefs = self._preferences.get(user_id, [])
        
        candidates = [
            p for p in prefs
            if p.category == category and
            (entity_id is None or p.entity_id == entity_id) and
            p.confidence >= self._min_confidence
        ]
        
        if not candidates:
            return None
        
        # Context-aware selection
        if context:
            for pref in candidates:
                if self._context_matches(pref.context, context):
                    return pref.preferred_value
        
        # Return highest confidence
        return max(candidates, key=lambda p: p.confidence).preferred_value

    def _context_matches(self, pref_context: Dict, query_context: Dict) -> bool:
        """Check if preference context matches query context."""
        for key, value in query_context.items():
            if key in pref_context and pref_context[key] != value:
                return False
        return True

    def get_pattern_suggestions(
        self,
        user_id: str,
        current_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get automation pattern suggestions for current context."""
        patterns = self._patterns.get(user_id, [])
        
        suggestions = []
        for pattern in patterns:
            if pattern.confidence >= self._min_confidence:
                if self._context_matches(pattern.trigger, current_context):
                    suggestions.append({
                        "pattern": pattern.pattern_type,
                        "action": pattern.action,
                        "confidence": pattern.confidence,
                        "occurrences": pattern.occurrences,
                    })
        
        return sorted(suggestions, key=lambda s: s["confidence"], reverse=True)

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get complete user profile."""
        prefs = self._preferences.get(user_id, [])
        patterns = self._patterns.get(user_id, [])
        
        return {
            "user_id": user_id,
            "preferences_count": len(prefs),
            "patterns_count": len(patterns),
            "categories": list(set(p.category.value for p in prefs)),
            "avg_confidence": sum(p.confidence for p in prefs) / len(prefs) if prefs else 0,
            "top_preferences": [
                {"category": p.category.value, "entity": p.entity_id, "value": p.preferred_value}
                for p in sorted(prefs, key=lambda x: x.confidence, reverse=True)[:5]
            ],
        }

    def merge_profiles(self, user_ids: List[str]) -> Dict[str, Any]:
        """Merge multiple user profiles for shared spaces."""
        merged = {}
        all_prefs = []
        
        for uid in user_ids:
            all_prefs.extend(self._preferences.get(uid, []))
        
        # Group by category and entity
        by_entity = defaultdict(list)
        for pref in all_prefs:
            by_entity[f"{pref.category.value}:{pref.entity_id}"].append(pref)
        
        # Average preferences
        for key, prefs in by_entity.items():
            if len(prefs) == 1:
                merged[key] = prefs[0].preferred_value
            else:
                # Average numeric values, pick mode for categorical
                values = [p.preferred_value for p in prefs]
                if all(isinstance(v, (int, float)) for v in values):
                    merged[key] = sum(values) / len(values)
                else:
                    # Most common
                    merged[key] = max(set(values), key=values.count)
        
        return merged

    def get_stats(self) -> Dict[str, Any]:
        """Get learner statistics."""
        total_prefs = sum(len(p) for p in self._preferences.values())
        total_patterns = sum(len(p) for p in self._patterns.values())
        
        return {
            "users": len(self._preferences),
            "total_preferences": total_prefs,
            "total_patterns": total_patterns,
            "avg_preferences_per_user": total_prefs / len(self._preferences) if self._preferences else 0,
        }


default_preference_learner: Optional[MultiUserPreferenceLearner] = None


def init_preference_learner(min_confidence: float = 0.7) -> MultiUserPreferenceLearner:
    global default_preference_learner
    default_preference_learner = MultiUserPreferenceLearner(min_confidence=min_confidence)
    return default_preference_learner
