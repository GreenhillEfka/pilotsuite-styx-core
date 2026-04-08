# Migrated from pilotsuite-styx-ha
# Original: custom_components/copilot_ha/core/mupl/action_attribution.py
# HA-specific data gathering (hass.states, device registry, etc.) removed.
# Core receives pre-processed AttributionSignals via REST from HA.
"""Action Attribution Engine — Pure scoring algorithm.

HA gathers raw signals (presence, device ownership, room location,
time patterns) and sends them as AttributionSignal objects.  Core
combines them with weighted confidence scoring and manages history.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AttributionSignal:
    """Pre-processed signal sent from HA to Core.

    Each signal represents one attribution source's opinion about
    who triggered an action, with an associated confidence score.
    """
    source_name: str
    user_id: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttributionResult:
    """Result of action attribution."""
    user_id: str
    confidence: float
    sources: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    entity_id: str = ""
    action: str = ""


@dataclass
class UserAction:
    """Recorded user action with attribution."""
    user_id: str
    entity_id: str
    action: str
    confidence: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    sources: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ActionAttributionEngine:
    """Combines multi-source attribution signals with weighted confidence.

    Unlike the HA-side ActionAttributor, this class does NOT gather raw
    data.  It receives pre-processed ``AttributionSignal`` objects and
    runs the scoring/combining algorithm.

    Usage::

        engine = ActionAttributionEngine(max_history=500)
        signals = [
            AttributionSignal("presence", "andreas", 0.4),
            AttributionSignal("device_ownership", "andreas", 0.3),
        ]
        action = engine.attribute_action("light.kitchen", "turn_on", signals)
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._action_history: List[UserAction] = []
        self._max_history = max_history

    # ------------------------------------------------------------------
    # Core algorithm
    # ------------------------------------------------------------------

    def attribute_action(
        self,
        entity_id: str,
        action: str,
        signals: List[AttributionSignal],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserAction]:
        """Attribute an action to a user based on pre-gathered signals.

        Algorithm:
        1. Collect all signals, grouping by ``user_id``.
        2. For each user, sum the confidence values from all signals.
        3. Pick the user with the highest summed confidence.
        4. Cap confidence at 1.0.
        5. Record in bounded history.

        Args:
            entity_id: The entity that was acted upon.
            action: The action (turn_on, turn_off, etc.).
            signals: Pre-processed attribution signals from HA.
            context: Optional extra context data.

        Returns:
            UserAction with attribution, or None if no signals provided.
        """
        if not signals:
            _LOGGER.debug("No attribution signals for %s / %s", entity_id, action)
            return None

        # Group signals by user, summing confidence
        user_scores: Dict[str, float] = {}
        user_sources: Dict[str, Dict[str, float]] = {}

        for signal in signals:
            uid = signal.user_id
            if uid not in user_scores:
                user_scores[uid] = 0.0
                user_sources[uid] = {}

            user_scores[uid] += signal.confidence
            user_sources[uid][signal.source_name] = signal.confidence
            if signal.metadata:
                user_sources[uid].update(
                    {k: v for k, v in signal.metadata.items()
                     if isinstance(v, (int, float))}
                )

        # Pick user with highest confidence
        best_user = max(user_scores, key=user_scores.get)  # type: ignore[arg-type]
        best_confidence = min(user_scores[best_user], 1.0)

        # Build context with runner-up candidates
        action_context: Dict[str, Any] = dict(context) if context else {}
        action_context["all_candidates"] = {
            u: score for u, score in user_scores.items() if u != best_user
        }

        user_action = UserAction(
            user_id=best_user,
            entity_id=entity_id,
            action=action,
            confidence=best_confidence,
            timestamp=datetime.now(timezone.utc),
            sources=user_sources[best_user],
            context=action_context,
        )

        # Bounded history
        self._action_history.append(user_action)
        if len(self._action_history) > self._max_history:
            self._action_history = self._action_history[-self._max_history:]

        _LOGGER.debug(
            "Attributed action %s on %s to user %s (confidence: %.2f)",
            action, entity_id, best_user, best_confidence,
        )

        return user_action

    # ------------------------------------------------------------------
    # History queries
    # ------------------------------------------------------------------

    def get_user_actions(self, user_id: str, limit: int = 100) -> List[UserAction]:
        """Get recent actions for a specific user."""
        return [a for a in self._action_history if a.user_id == user_id][-limit:]

    def get_entity_actions(self, entity_id: str, limit: int = 100) -> List[UserAction]:
        """Get recent actions for a specific entity."""
        return [a for a in self._action_history if a.entity_id == entity_id][-limit:]

    def get_action_history(self, limit: int = 100) -> List[UserAction]:
        """Get all recent actions."""
        return self._action_history[-limit:]

    def clear_history(self) -> int:
        """Clear all action history. Returns number of entries removed."""
        count = len(self._action_history)
        self._action_history.clear()
        return count

    @property
    def history_size(self) -> int:
        """Current number of entries in history."""
        return len(self._action_history)
