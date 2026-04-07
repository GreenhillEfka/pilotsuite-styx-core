"""Persistent feedback store for habitus mining pattern reinforcement.

Records user decisions (accepted/rejected/snoozed) on automation candidates
and translates them into weight multipliers applied during rule scoring.

Accepted patterns are reinforced (1.5x), rejected patterns are suppressed
(0.1x), snoozed patterns are dampened (0.5x).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Weight multipliers per action
_ACTION_WEIGHTS: dict[str, float] = {
    "accepted": 1.5,
    "rejected": 0.1,
    "snoozed": 0.5,
}

_VALID_ACTIONS = frozenset(_ACTION_WEIGHTS.keys())


class HabitusFeedbackStore:
    """SQLite-free JSON-based persistent feedback store.

    Each feedback record maps a pattern_key (e.g. "light.kitchen:on→motion.kitchen:on")
    to the latest user action and a cumulative confidence_boost.

    Storage: ``<storage_dir>/habitus_feedback.json``
    """

    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._storage_dir / "habitus_feedback.json"
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    # -- public API ----------------------------------------------------------

    def record_feedback(
        self,
        pattern_key: str,
        action: str,
        confidence_boost: float = 0.0,
    ) -> dict[str, Any]:
        """Record a user feedback decision for a pattern.

        Args:
            pattern_key: Identifier for the A->B rule, e.g. "light.kitchen:on->motion.kitchen:on".
            action: One of "accepted", "rejected", "snoozed".
            confidence_boost: Optional extra confidence adjustment (additive).

        Returns:
            The stored record dict.
        """
        if action not in _VALID_ACTIONS:
            raise ValueError(f"Invalid action '{action}', must be one of {sorted(_VALID_ACTIONS)}")

        now_ms = int(time.time() * 1000)
        existing = self._records.get(pattern_key)

        if existing is not None:
            existing["action"] = action
            existing["confidence_boost"] = confidence_boost
            existing["updated_ms"] = now_ms
            existing["count"] = existing.get("count", 0) + 1
            record = existing
        else:
            record = {
                "pattern_key": pattern_key,
                "action": action,
                "confidence_boost": confidence_boost,
                "created_ms": now_ms,
                "updated_ms": now_ms,
                "count": 1,
            }
            self._records[pattern_key] = record

        self._persist()
        _LOGGER.info(
            "Feedback recorded: %s -> %s (boost=%.2f, count=%d)",
            pattern_key, action, confidence_boost, record["count"],
        )
        return record

    def get_feedback_weights(self) -> dict[str, float]:
        """Return pattern_key -> weight multiplier based on last action.

        accepted  -> 1.5
        rejected  -> 0.1
        snoozed   -> 0.5

        Patterns without feedback are not included (implicit weight = 1.0).
        """
        weights: dict[str, float] = {}
        for key, rec in self._records.items():
            action = rec.get("action", "")
            base_weight = _ACTION_WEIGHTS.get(action, 1.0)
            boost = float(rec.get("confidence_boost", 0.0))
            weights[key] = max(0.01, base_weight + boost)
        return weights

    def get_record(self, pattern_key: str) -> dict[str, Any] | None:
        """Get a single feedback record, or None."""
        return self._records.get(pattern_key)

    def get_all_records(self) -> list[dict[str, Any]]:
        """Return all feedback records sorted by updated_ms descending."""
        recs = list(self._records.values())
        recs.sort(key=lambda r: r.get("updated_ms", 0), reverse=True)
        return recs

    def clear(self) -> None:
        """Remove all feedback records."""
        self._records.clear()
        self._persist()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        try:
            if self._file.exists():
                with open(self._file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict) and "records" in data:
                    for rec in data["records"]:
                        pk = rec.get("pattern_key")
                        if pk:
                            self._records[pk] = rec
                _LOGGER.debug("Loaded %d feedback records from %s", len(self._records), self._file)
        except (IOError, json.JSONDecodeError, TypeError, KeyError) as exc:
            _LOGGER.warning("Failed to load feedback store: %s", exc)

    def _persist(self) -> None:
        try:
            import os
            payload = {
                "version": 1,
                "updated_ms": int(time.time() * 1000),
                "records": list(self._records.values()),
            }
            tmp = str(self._file) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, str(self._file))
        except Exception as exc:
            _LOGGER.error("Failed to persist feedback store: %s", exc)
