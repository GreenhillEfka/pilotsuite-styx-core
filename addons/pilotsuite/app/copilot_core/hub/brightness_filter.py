"""Shared cloud-resilient brightness filter for Hub modules.

Extracts the common moving-average + hysteresis logic used by both
``helligkeit_module.py`` (12% hysteresis) and ``light_intelligence.py``
(15% hysteresis).

Usage::

    from copilot_core.hub.brightness_filter import CloudResilientFilter

    _filter = CloudResilientFilter(window_size=10, hysteresis_pct=12.0)
    _filter.add_reading(45_000.0)
    stable_lux = _filter.get_filtered()
"""

from __future__ import annotations

from collections import deque


class CloudResilientFilter:
    """Moving-average brightness filter with hysteresis for cloud resilience.

    Smooths outdoor lux readings by maintaining a sliding window of recent
    values.  Small fluctuations (below ``hysteresis_pct`` of the last stable
    value) are suppressed to prevent automation flicker during cloud cover.

    Args:
        window_size: Number of readings in the sliding window (default 10).
        hysteresis_pct: Percent change required to update the stable value.
    """

    def __init__(
        self,
        window_size: int = 10,
        hysteresis_pct: float = 12.0,
    ) -> None:
        self._history: deque[float] = deque(maxlen=window_size)
        self._hysteresis_pct = hysteresis_pct
        self._last_stable: float | None = None

    def add_reading(self, lux: float) -> None:
        """Append a new lux reading to the sliding window."""
        self._history.append(lux)

    def get_filtered(self) -> float:
        """Return the filtered (cloud-resilient) outdoor brightness.

        Returns 0.0 when no readings are available.
        """
        if not self._history:
            return 0.0

        current_avg = sum(self._history) / len(self._history)

        if self._last_stable is not None and self._last_stable > 0:
            delta_pct = abs(current_avg - self._last_stable) / self._last_stable * 100
            if delta_pct < self._hysteresis_pct:
                return self._last_stable

        self._last_stable = current_avg
        return current_avg

    def reset(self) -> None:
        """Clear all readings and the stable value."""
        self._history.clear()
        self._last_stable = None

    @property
    def reading_count(self) -> int:
        """Number of readings currently in the window."""
        return len(self._history)

    @property
    def last_stable(self) -> float | None:
        """Last stable filtered value, or None if never computed."""
        return self._last_stable
