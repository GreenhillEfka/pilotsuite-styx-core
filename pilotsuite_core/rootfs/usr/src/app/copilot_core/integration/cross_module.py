"""
Cross-Module Pattern Discovery.

Discovers correlations BETWEEN modules by analyzing their outputs
over a sliding time window. Identifies patterns like:

  - mood.focus + habitus.morning_routine → "morning_focus_routine"
  - energy.solar_peak + activity.low → "optimal_appliance_time"
  - calendar.meeting + zone.office → "pre-meeting_prep"

These cross-module patterns can suggest new synapses or automations.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from threading import Lock

from .bus import BusEvent

_LOGGER = logging.getLogger(__name__)

# How many evaluation snapshots to retain
DEFAULT_WINDOW_SIZE = 100
# Minimum correlation to report
DEFAULT_MIN_CORRELATION = 0.6


@dataclass(frozen=True)
class CrossPattern:
    """A discovered cross-module correlation."""
    pattern_id: str
    module_a: str
    module_b: str
    correlation: float  # -1.0 to 1.0
    co_occurrence_count: int
    description: str
    discovered_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))


@dataclass(frozen=True)
class ProposedSynapse:
    """A suggested new connection between neurons."""
    from_neuron: str
    to_neuron: str
    proposed_weight: float
    reason: str
    confidence: float


class CrossModuleAnalyzer:
    """Discovers patterns across module boundaries.

    Collects evaluation snapshots via bus events and periodically
    analyzes them for cross-module correlations.

    Args:
        bus: IntegrationBus instance.
        window_size: Number of snapshots to retain.
        min_correlation: Minimum absolute correlation to report.
    """

    def __init__(
        self,
        bus,
        window_size: int = DEFAULT_WINDOW_SIZE,
        min_correlation: float = DEFAULT_MIN_CORRELATION,
    ) -> None:
        self._bus = bus
        self._window_size = window_size
        self._min_correlation = min_correlation
        self._lock = Lock()

        # Sliding window of evaluation snapshots
        # Each entry: {"timestamp_ms": int, "values": {"neuron_id": float, ...}}
        self._snapshots: deque = deque(maxlen=window_size)

        # Discovered patterns (pattern_id → CrossPattern)
        self._patterns: Dict[str, CrossPattern] = {}

        # Subscribe to neuron evaluations
        self._sub_id = bus.subscribe("neuron.evaluated", self._on_evaluation)

        _LOGGER.info(
            "CrossModuleAnalyzer initialized (window=%d, min_corr=%.2f)",
            window_size, min_correlation,
        )

    def _on_evaluation(self, event: BusEvent) -> None:
        """Record a neuron evaluation snapshot."""
        data = event.data
        values = {}
        for key in ("context_values", "state_values", "mood_values"):
            prefix = key.split("_")[0]
            for name, val in data.get(key, {}).items():
                values[f"{prefix}.{name}"] = val

        with self._lock:
            self._snapshots.append({
                "timestamp_ms": event.timestamp_ms,
                "values": values,
            })

    def analyze_correlations(self) -> List[CrossPattern]:
        """Analyze the snapshot window for cross-layer correlations.

        Finds pairs of neurons from different layers whose values
        are correlated above the threshold.

        Returns:
            List of newly discovered CrossPattern objects.
        """
        with self._lock:
            snapshots = list(self._snapshots)

        if len(snapshots) < 10:
            return []

        # Collect time series per neuron
        neuron_ids = set()
        for snap in snapshots:
            neuron_ids.update(snap["values"].keys())

        series: Dict[str, List[float]] = {nid: [] for nid in neuron_ids}
        for snap in snapshots:
            for nid in neuron_ids:
                series[nid].append(snap["values"].get(nid, 0.0))

        # Find cross-layer correlations
        new_patterns = []
        neuron_list = sorted(neuron_ids)

        for i, a in enumerate(neuron_list):
            layer_a = a.split(".")[0]
            for b in neuron_list[i + 1:]:
                layer_b = b.split(".")[0]
                # Only cross-layer correlations
                if layer_a == layer_b:
                    continue

                corr = self._pearson(series[a], series[b])
                if abs(corr) < self._min_correlation:
                    continue

                pattern_id = f"{a}~{b}"
                co_count = sum(
                    1 for va, vb in zip(series[a], series[b])
                    if va > 0.5 and vb > 0.5
                )

                sign = "positively" if corr > 0 else "negatively"
                pattern = CrossPattern(
                    pattern_id=pattern_id,
                    module_a=a,
                    module_b=b,
                    correlation=round(corr, 4),
                    co_occurrence_count=co_count,
                    description=f"{a} and {b} are {sign} correlated (r={corr:.2f})",
                )
                new_patterns.append(pattern)

        # Update stored patterns
        with self._lock:
            for p in new_patterns:
                self._patterns[p.pattern_id] = p

        return new_patterns

    def suggest_new_connections(self) -> List[ProposedSynapse]:
        """Suggest new synapses based on discovered patterns.

        Only suggests connections between neurons that don't already
        have a direct synapse in the topology.
        """
        from copilot_core.api.v1.neuron_layers import SYNAPSE_TOPOLOGY

        existing = {(f, t) for f, t, _ in SYNAPSE_TOPOLOGY}
        proposals = []

        with self._lock:
            patterns = list(self._patterns.values())

        for pattern in patterns:
            pair = (pattern.module_a, pattern.module_b)
            pair_rev = (pattern.module_b, pattern.module_a)
            if pair in existing or pair_rev in existing:
                continue
            if abs(pattern.correlation) < 0.7:
                continue

            proposed_weight = round(pattern.correlation * 0.3, 3)
            proposals.append(ProposedSynapse(
                from_neuron=pattern.module_a,
                to_neuron=pattern.module_b,
                proposed_weight=proposed_weight,
                reason=pattern.description,
                confidence=abs(pattern.correlation),
            ))

        return proposals

    def get_patterns(self) -> List[Dict[str, Any]]:
        """Return all discovered patterns as dicts."""
        with self._lock:
            return [
                {
                    "pattern_id": p.pattern_id,
                    "module_a": p.module_a,
                    "module_b": p.module_b,
                    "correlation": p.correlation,
                    "co_occurrence_count": p.co_occurrence_count,
                    "description": p.description,
                    "discovered_at_ms": p.discovered_at_ms,
                }
                for p in self._patterns.values()
            ]

    def get_stats(self) -> Dict[str, Any]:
        """Return analyzer metrics."""
        with self._lock:
            return {
                "snapshots_collected": len(self._snapshots),
                "window_size": self._window_size,
                "patterns_discovered": len(self._patterns),
                "min_correlation": self._min_correlation,
            }

    @staticmethod
    def _pearson(x: List[float], y: List[float]) -> float:
        """Compute Pearson correlation coefficient."""
        n = len(x)
        if n < 3:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        std_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        std_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

        if std_x < 1e-10 or std_y < 1e-10:
            return 0.0

        return cov / (std_x * std_y)
