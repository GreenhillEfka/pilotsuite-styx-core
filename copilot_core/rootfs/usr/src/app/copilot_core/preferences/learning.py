"""
Preference Learning from User Behavior.

Learns user preferences from implicit and explicit feedback.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json

_LOGGER = logging.getLogger(__name__)


@dataclass
class PreferenceObservation:
    """An observation of user behavior."""
    user_id: str
    preference_key: str
    value: Any
    context: Dict[str, Any]
    timestamp: datetime
    implicit: bool  # True if observed, False if explicitly stated


class PreferenceLearner:
    """Learns user preferences from behavior."""

    def __init__(self, learning_rate: float = 0.1) -> None:
        """Initialize learner."""
        self._learning_rate = learning_rate
        self._observations: Dict[str, List[PreferenceObservation]] = defaultdict(list)
        self._learned_preferences: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def observe(
        self,
        user_id: str,
        preference_key: str,
        value: Any,
        context: Optional[Dict[str, Any]] = None,
        implicit: bool = True,
    ) -> None:
        """Record a preference observation."""
        observation = PreferenceObservation(
            user_id=user_id,
            preference_key=preference_key,
            value=value,
            context=context or {},
            timestamp=datetime.now(),
            implicit=implicit,
        )
        self._observations[user_id].append(observation)
        self._update_learned_preference(user_id, preference_key)

    def _update_learned_preference(self, user_id: str, preference_key: str) -> None:
        """Update learned preference based on observations."""
        observations = [
            o for o in self._observations[user_id]
            if o.preference_key == preference_key
        ]

        if not observations:
            return

        # Weight recent observations more heavily
        now = datetime.now()
        total_weight = 0.0
        weighted_sum = 0.0

        for obs in observations:
            age = (now - obs.timestamp).total_seconds()
            # Decay factor: preferences decay over 7 days
            weight = self._learning_rate * (1.0 / (1.0 + age / (7 * 24 * 3600))))
            if isinstance(obs.value, (int, float)):
                weighted_sum += weight * obs.value
                total_weight += weight

        if total_weight > 0 and weighted_sum:
            self._learned_preferences[user_id][preference_key] = {
                "value": weighted_sum / total_weight,
                "confidence": min(total_weight, 1.0),
                "observation_count": len(observations),
            }

    def get_learned_preference(
        self,
        user_id: str,
        preference_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Get learned preference for user."""
        return self._learned_preferences.get(user_id, {}).get(preference_key)

    def get_suggestions(
        self,
        user_id: str,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get preference suggestions based on learned patterns."""
        suggestions = []
        learned = self._learned_preferences.get(user_id, {})

        for pref_key, data in learned.items():
            confidence = data.get("confidence", 0)
            if confidence > 0.3:  # Only suggest if >30% confidence
                suggestions.append({
                    "key": pref_key,
                    "value": data.get("value"),
                    "confidence": confidence,
                })

        return sorted(suggestions, key=lambda s: s["confidence"], reverse=True)

    def clear_observations(self, user_id: str) -> None:
        """Clear observations for a user."""
        if user_id in self._observations:
            del self._observations[user_id]
        if user_id in self._learned_preferences:
            del self._learned_preferences[user_id]


__all__ = ["PreferenceObservation", "PreferenceLearner"]
