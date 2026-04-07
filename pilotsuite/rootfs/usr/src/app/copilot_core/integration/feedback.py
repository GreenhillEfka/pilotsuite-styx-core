"""
Feedback Loop — Adjusts BrainGraph edge weights based on suggestion outcomes.

When a suggestion is accepted, the underlying pattern edges in the
BrainGraph are reinforced (touch_edge with positive delta).
When rejected, edges are weakened (touch_edge with negative delta).

This creates a learning loop: accepted suggestions → stronger patterns →
more confident future suggestions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .bus import BusEvent

_LOGGER = logging.getLogger(__name__)

# Weight adjustment constants
ACCEPT_DELTA = 0.5  # Reinforce edge by this amount on acceptance
REJECT_DELTA = -0.3  # Weaken edge by this amount on rejection
MIN_WEIGHT = 0.05  # Don't let edges decay below this


class FeedbackLoop:
    """Listens for suggestion feedback and adjusts BrainGraph weights.

    Args:
        brain_graph_service: BrainGraphService instance.
        bus: IntegrationBus instance.
    """

    def __init__(self, brain_graph_service, bus) -> None:
        self._bg = brain_graph_service
        self._bus = bus
        self._adjustments_applied = 0

        # Subscribe to feedback events
        self._sub_accepted = bus.subscribe(
            "suggestion.accepted", self._on_suggestion_accepted
        )
        self._sub_rejected = bus.subscribe(
            "suggestion.rejected", self._on_suggestion_rejected
        )
        _LOGGER.info("FeedbackLoop initialized (subscribed to suggestion events)")

    def _on_suggestion_accepted(self, event: BusEvent) -> None:
        """Reinforce edges related to the accepted suggestion."""
        self._adjust_edges(event.data, delta=ACCEPT_DELTA)
        _LOGGER.info(
            "Suggestion accepted → reinforced edges (source=%s)",
            event.data.get("suggestion_id", "?"),
        )

    def _on_suggestion_rejected(self, event: BusEvent) -> None:
        """Weaken edges related to the rejected suggestion."""
        self._adjust_edges(event.data, delta=REJECT_DELTA)
        _LOGGER.info(
            "Suggestion rejected → weakened edges (source=%s)",
            event.data.get("suggestion_id", "?"),
        )

    def _adjust_edges(self, data: Dict[str, Any], delta: float) -> None:
        """Adjust BrainGraph edge weights for a suggestion.

        The suggestion data should contain:
        - ``related_entities``: list of entity IDs involved
        - ``pattern_key``: optional A→B pattern key from habitus miner

        Edges between related entities are reinforced/weakened.
        """
        entities = data.get("related_entities", [])
        pattern_key = data.get("pattern_key")

        if not entities and not pattern_key:
            return

        try:
            self._bg.begin_batch()

            # Adjust edges between related entities
            for i, from_entity in enumerate(entities):
                for to_entity in entities[i + 1:]:
                    # Find existing edge and adjust
                    self._bg.touch_edge(
                        from_node=from_entity,
                        edge_type="correlates",
                        to_node=to_entity,
                        delta=delta,
                        meta_patch={"feedback_source": "suggestion_loop"},
                    )

            # If there's a pattern key (A→B), adjust the triggered_by edge
            if pattern_key and "→" in pattern_key:
                parts = pattern_key.split("→", 1)
                if len(parts) == 2:
                    self._bg.touch_edge(
                        from_node=parts[0].strip(),
                        edge_type="triggered_by",
                        to_node=parts[1].strip(),
                        delta=delta,
                        meta_patch={"feedback_source": "habitus_feedback"},
                    )

            self._bg.commit_batch()
            self._adjustments_applied += 1
        except Exception:
            _LOGGER.exception("Failed to adjust BrainGraph edges for feedback")
            try:
                self._bg.rollback_batch()
            except Exception:
                _LOGGER.debug("BrainGraph rollback also failed", exc_info=True)

    def get_stats(self) -> Dict[str, Any]:
        """Return feedback loop metrics."""
        return {
            "adjustments_applied": self._adjustments_applied,
            "accept_delta": ACCEPT_DELTA,
            "reject_delta": REJECT_DELTA,
        }
