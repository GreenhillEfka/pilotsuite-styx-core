"""
Multi-User Conflict Resolution.

Handles preference conflicts when multiple users have different settings.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

_LOGGER = logging.getLogger(__name__)


class ConflictStrategy(Enum):
    """Strategy for resolving conflicts."""
    FIRST_WRITE_WINS = "first_write_wins"
    LAST_WRITE_WINS = "last_write_wins"
    HIGHEST_PRIORITY = "highest_priority"
    MAJORITY = "majority"
    AVERAGE = "average"
    MEDIAN = "median"


@dataclass
class PreferenceConflict:
    """Represents a preference conflict."""
    preference_key: str
    users: List[str]
    values: Dict[str, Any]
    strategy: ConflictStrategy
    resolved_value: Optional[Any] = None


class ConflictResolver:
    """Resolves conflicts between user preferences."""

    def __init__(self, default_strategy: ConflictStrategy = ConflictStrategy.HIGHEST_PRIORITY) -> None:
        """Initialize resolver."""
        self._default_strategy = default_strategy
        self._priority_rules: Dict[str, int] = {}

    def resolve(
        self,
        preference_key: str,
        user_values: Dict[str, Any],
        strategy: Optional[ConflictStrategy] = None,
    ) -> Any:
        """Resolve a preference conflict."""
        if len(user_values) <= 1:
            # No conflict
            return list(user_values.values())[0] if user_values else None

        strategy = strategy or self._default_strategy

        if strategy == ConflictStrategy.FIRST_WRITE_WINS:
            return self._first_write_wins(user_values)
        elif strategy == ConflictStrategy.LAST_WRITE_WINS:
            return self._last_write_wins(user_values)
        elif strategy == ConflictStrategy.HIGHEST_PRIORITY:
            return self._highest_priority(user_values)
        elif strategy == ConflictStrategy.MAJORITY:
            return self._majority(user_values)
        elif strategy == ConflictStrategy.AVERAGE:
            return self._average(user_values)
        elif strategy == ConflictStrategy.MEDIAN:
            return self._median(user_values)

        return list(user_values.values())[0]

    def _first_write_wins(self, user_values: Dict[str, Any]) -> Any:
        """First write wins strategy."""
        return list(user_values.values())[0]

    def _last_write_wins(self, user_values: Dict[str, Any]) -> Any:
        """Last write wins strategy."""
        return list(user_values.values())[-1]

    def _highest_priority(self, user_values: Dict[str, Any]) -> Any:
        """Highest priority user wins."""
        if not self._priority_rules:
            return list(user_values.values())[0]

        best_user = max(user_values.keys(), key=lambda u: self._priority_rules.get(u, 0))
        return user_values[best_user]

    def _majority(self, user_values: Dict[str, Any]) -> Any:
        """Majority vote."""
        from collections import Counter
        values = list(user_values.values())
        counter = Counter(values)
        return counter.most_common(1)[0][0] if counter else None

    def _average(self, user_values: Dict[str, Any]) -> Any:
        """Average numeric values."""
        nums = [v for v in user_values.values() if isinstance(v, (int, float))]
        return sum(nums) / len(nums) if nums else None

    def _median(self, user_values: Dict[str, Any]) -> Any:
        """Median numeric values."""
        nums = sorted([v for v in user_values.values() if isinstance(v, (int, float))])
        n = len(nums)
        if n == 0:
            return None
        if n % 2 == 0:
            return (nums[n // 2 - 1] + nums[n // 2]) / 2
        return nums[n // 2]

    def set_priority(self, user_id: str, priority: int) -> None:
        """Set user priority for conflict resolution."""
        self._priority_rules[user_id] = priority
        _LOGGER.debug("User %s priority set to %d", user_id, priority)


__all__ = ["ConflictStrategy", "PreferenceConflict", "ConflictResolver"]
