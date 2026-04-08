"""Anomaly Detection v2 — Multi-Dimensional Pattern Analysis (v6.2.0).

Advanced anomaly detection with:
- Multi-dimensional pattern analysis (time, value, frequency, correlation)
- Seasonal decomposition (hourly, daily, weekly patterns)
- Correlation-based anomalies (unusual device combinations)
- Severity scoring with context-aware thresholds
- German alerts and explanations
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class DataPoint:
    """A single sensor reading."""

    entity_id: str
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Anomaly:
    """A detected anomaly."""

    anomaly_id: str
    entity_id: str
    anomaly_type: str  # spike, drift, flatline, correlation, seasonal, frequency
    severity: str  # info, warning, critical
    score: float  # 0-100 (100 = most anomalous)
    detected_at: datetime
    value: float
    expected_value: float
    deviation_pct: float
    description_de: str
    description_en: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternProfile:
    """Learned pattern profile for an entity."""

    entity_id: str
    hourly_means: dict[int, float] = field(default_factory=dict)  # hour -> mean
    hourly_stds: dict[int, float] = field(default_factory=dict)  # hour -> std
    daily_means: dict[int, float] = field(default_factory=dict)  # weekday -> mean
    daily_stds: dict[int, float] = field(default_factory=dict)  # weekday -> std
    global_mean: float = 0.0
    global_std: float = 0.0
    min_value: float = float("inf")
    max_value: float = float("-inf")
    total_points: int = 0
    last_updated: datetime | None = None


@dataclass
class CorrelationPair:
    """Correlation between two entities."""

    entity_a: str
    entity_b: str
    correlation: float  # -1 to +1
    sample_count: int = 0


@dataclass
class AnomalySummary:
    """Summary of anomaly detection results."""

    total_entities: int = 0
    total_anomalies: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    anomaly_types: dict[str, int] = field(default_factory=dict)
    top_anomalies: list[dict[str, Any]] = field(default_factory=list)
    entity_health: dict[str, str] = field(default_factory=dict)  # entity -> status


# ── Thresholds ──────────────────────────────────────────────────────────────

# Standard deviations for severity classification
_SEVERITY_THRESHOLDS = {
    "info": 2.0,  # 2 sigma
    "warning": 3.0,  # 3 sigma
    "critical": 4.0,  # 4 sigma
}

# Minimum data points for reliable analysis
_MIN_POINTS_SEASONAL = 168  # 1 week of hourly data
_MIN_POINTS_BASIC = 24  # 1 day of hourly data
_MIN_POINTS_CORRELATION = 48  # 2 days

# Flatline detection
_FLATLINE_THRESHOLD = 12  # consecutive identical values

# Frequency analysis
_FREQUENCY_CHANGE_THRESHOLD = 0.5  # 50% change in reporting frequency


# ── Engine ──────────────────────────────────────────────────────────────────


class AnomalyDetectionEngine:
    """Multi-dimensional anomaly detection engine."""

    def __init__(self, max_history: int = 2016) -> None:
        """Initialize engine.

        Args:
            max_history: Maximum data points per entity (default 2016 = 12 weeks hourly).
        """
        self._max_history = max_history
        self._history: dict[str, list[DataPoint]] = defaultdict(list)
        self._profiles: dict[str, PatternProfile] = {}
        self._anomalies: list[Anomaly] = []
        self._correlations: dict[str, CorrelationPair] = {}
        self._anomaly_counter = 0

    # ── Data ingestion ──────────────────────────────────────────────────

    def ingest(self, entity_id: str, value: float,
               timestamp: datetime | None = None,
               attributes: dict[str, Any] | None = None) -> None:
        """Ingest a single data point."""
        ts = timestamp or datetime.now(tz=timezone.utc)
        dp = DataPoint(
            entity_id=entity_id,
            value=value,
            timestamp=ts,
            attributes=attributes or {},
        )
        history = self._history[entity_id]
        history.append(dp)
        if len(history) > self._max_history:
            self._history[entity_id] = history[-self._max_history:]

    def ingest_batch(self, points: list[dict[str, Any]]) -> int:
        """Ingest a batch of data points.

        Each dict: {"entity_id": str, "value": float, "timestamp"?: str, "attributes"?: dict}
        """
        count = 0
        for p in points:
            entity_id = p.get("entity_id", "")
            value = p.get("value")
            if not entity_id or value is None:
                continue
            ts = None
            if "timestamp" in p:
                try:
                    ts = datetime.fromisoformat(p["timestamp"])
                except (ValueError, TypeError):
                    pass
            self.ingest(entity_id, float(value), ts, p.get("attributes"))
            count += 1
        return count

    # ── Pattern learning ────────────────────────────────────────────────

    def learn_patterns(self, entity_id: str | None = None) -> int:
        """Learn/update pattern profiles.

        Args:
            entity_id: If provided, learn only this entity. Otherwise learn all.

        Returns:
            Number of profiles updated.
        """
        entities = [entity_id] if entity_id else list(self._history.keys())
        updated = 0

        for eid in entities:
            history = self._history.get(eid, [])
            if len(history) < _MIN_POINTS_BASIC:
                continue

            profile = PatternProfile(entity_id=eid)
            values = [dp.value for dp in history]

            # Global statistics
            profile.global_mean = statistics.mean(values)
            profile.global_std = statistics.stdev(values) if len(values) > 1 else 0.0
            profile.min_value = min(values)
            profile.max_value = max(values)
            profile.total_points = len(values)
            profile.last_updated = datetime.now(tz=timezone.utc)

            # Hourly patterns (0-23)
            hourly_buckets: dict[int, list[float]] = defaultdict(list)
            for dp in history:
                hourly_buckets[dp.timestamp.hour].append(dp.value)

            for hour, vals in hourly_buckets.items():
                profile.hourly_means[hour] = statistics.mean(vals)
                profile.hourly_stds[hour] = statistics.stdev(vals) if len(vals) > 1 else 0.0

            # Daily patterns (0=Monday, 6=Sunday)
            daily_buckets: dict[int, list[float]] = defaultdict(list)
            for dp in history:
                daily_buckets[dp.timestamp.weekday()].append(dp.value)

            for day, vals in daily_buckets.items():
                profile.daily_means[day] = statistics.mean(vals)
                profile.daily_stds[day] = statistics.stdev(vals) if len(vals) > 1 else 0.0

            self._profiles[eid] = profile
            updated += 1

        return updated

    def learn_correlations(self) -> int:
        """Learn pairwise correlations between entities."""
        entities = [eid for eid, h in self._history.items()
                    if len(h) >= _MIN_POINTS_CORRELATION]
        learned = 0

        for i, eid_a in enumerate(entities):
            for eid_b in entities[i + 1:]:
                corr = self._calculate_correlation(eid_a, eid_b)
                if corr is not None:
                    key = f"{eid_a}|{eid_b}"
                    self._correlations[key] = CorrelationPair(
                        entity_a=eid_a,
                        entity_b=eid_b,
                        correlation=corr,
                        sample_count=min(
                            len(self._history[eid_a]),
                            len(self._history[eid_b]),
                        ),
                    )
                    learned += 1

        return learned

    # ── Anomaly detection ───────────────────────────────────────────────

    def detect(self, entity_id: str | None = None) -> list[Anomaly]:
        """Run all anomaly detection methods.

        Args:
            entity_id: Detect for specific entity, or all if None.

        Returns:
            List of newly detected anomalies.
        """
        entities = [entity_id] if entity_id else list(self._history.keys())
        new_anomalies: list[Anomaly] = []

        for eid in entities:
            history = self._history.get(eid, [])
            if len(history) < _MIN_POINTS_BASIC:
                continue

            # Ensure profile is up to date
            if eid not in self._profiles:
                self.learn_patterns(eid)

            profile = self._profiles.get(eid)
            if not profile:
                continue

            # Run detection methods
            new_anomalies.extend(self._detect_spikes(eid, history, profile))
            new_anomalies.extend(self._detect_drift(eid, history, profile))
            new_anomalies.extend(self._detect_flatline(eid, history))
            new_anomalies.extend(self._detect_seasonal(eid, history, profile))
            new_anomalies.extend(self._detect_frequency(eid, history))

        # Correlation anomalies (cross-entity)
        if entity_id is None:
            new_anomalies.extend(self._detect_correlation_anomalies())

        self._anomalies.extend(new_anomalies)
        # Keep only recent anomalies (last 500)
        if len(self._anomalies) > 500:
            self._anomalies = self._anomalies[-500:]

        return new_anomalies

    def _detect_spikes(self, entity_id: str, history: list[DataPoint],
                       profile: PatternProfile) -> list[Anomaly]:
        """Detect sudden spikes/drops using z-score."""
        anomalies = []
        if profile.global_std == 0:
            return anomalies

        # Check last 3 data points
        recent = history[-3:]
        for dp in recent:
            z_score = abs(dp.value - profile.global_mean) / profile.global_std

            # Also check against hourly pattern if available
            hourly_mean = profile.hourly_means.get(dp.timestamp.hour)
            hourly_std = profile.hourly_stds.get(dp.timestamp.hour, 0)
            hourly_z = 0.0
            if hourly_std > 0 and hourly_mean is not None:
                hourly_z = abs(dp.value - hourly_mean) / hourly_std

            # Use the more context-aware z-score
            effective_z = max(z_score, hourly_z) if hourly_z > 0 else z_score

            if effective_z >= _SEVERITY_THRESHOLDS["info"]:
                severity = self._z_to_severity(effective_z)
                expected = hourly_mean if hourly_mean is not None else profile.global_mean
                dev_pct = ((dp.value - expected) / expected * 100) if expected != 0 else 0

                anomalies.append(self._create_anomaly(
                    entity_id=entity_id,
                    anomaly_type="spike",
                    severity=severity,
                    score=min(100, effective_z * 20),
                    value=dp.value,
                    expected_value=expected,
                    deviation_pct=dev_pct,
                    detected_at=dp.timestamp,
                    context={"z_score": round(effective_z, 2), "hourly_z": round(hourly_z, 2)},
                ))

        return anomalies

    def _detect_drift(self, entity_id: str, history: list[DataPoint],
                      profile: PatternProfile) -> list[Anomaly]:
        """Detect gradual drift (values slowly moving away from baseline)."""
        anomalies = []
        if len(history) < 48:
            return anomalies

        # Compare recent 24h mean vs historical mean
        recent_values = [dp.value for dp in history[-24:]]
        older_values = [dp.value for dp in history[:-24]]

        if not older_values:
            return anomalies

        recent_mean = statistics.mean(recent_values)
        older_mean = statistics.mean(older_values)
        older_std = statistics.stdev(older_values) if len(older_values) > 1 else 0

        if older_std == 0:
            return anomalies

        drift_z = abs(recent_mean - older_mean) / older_std

        if drift_z >= _SEVERITY_THRESHOLDS["info"]:
            dev_pct = ((recent_mean - older_mean) / older_mean * 100) if older_mean != 0 else 0
            direction = "steigend" if recent_mean > older_mean else "fallend"

            anomalies.append(self._create_anomaly(
                entity_id=entity_id,
                anomaly_type="drift",
                severity=self._z_to_severity(drift_z),
                score=min(100, drift_z * 20),
                value=recent_mean,
                expected_value=older_mean,
                deviation_pct=dev_pct,
                detected_at=history[-1].timestamp,
                context={
                    "drift_z": round(drift_z, 2),
                    "direction": direction,
                    "recent_mean": round(recent_mean, 2),
                    "historical_mean": round(older_mean, 2),
                },
            ))

        return anomalies

    def _detect_flatline(self, entity_id: str, history: list[DataPoint]) -> list[Anomaly]:
        """Detect stuck/frozen sensors (flatline)."""
        anomalies = []
        if len(history) < _FLATLINE_THRESHOLD:
            return anomalies

        recent = history[-_FLATLINE_THRESHOLD:]
        values = [dp.value for dp in recent]

        if len(set(values)) == 1:
            anomalies.append(self._create_anomaly(
                entity_id=entity_id,
                anomaly_type="flatline",
                severity="warning",
                score=60.0,
                value=values[0],
                expected_value=values[0],
                deviation_pct=0.0,
                detected_at=recent[-1].timestamp,
                context={
                    "consecutive_identical": _FLATLINE_THRESHOLD,
                    "stuck_value": values[0],
                },
            ))

        return anomalies

    def _detect_seasonal(self, entity_id: str, history: list[DataPoint],
                         profile: PatternProfile) -> list[Anomaly]:
        """Detect violations of seasonal/time-of-day patterns."""
        anomalies = []
        if len(history) < _MIN_POINTS_SEASONAL:
            return anomalies

        # Check latest point against expected hourly pattern
        latest = history[-1]
        hour = latest.timestamp.hour
        day = latest.timestamp.weekday()

        # Hourly check
        hourly_mean = profile.hourly_means.get(hour)
        hourly_std = profile.hourly_stds.get(hour, 0)

        if hourly_mean is not None and hourly_std > 0:
            z = abs(latest.value - hourly_mean) / hourly_std
            if z >= _SEVERITY_THRESHOLDS["warning"]:
                dev_pct = ((latest.value - hourly_mean) / hourly_mean * 100) if hourly_mean != 0 else 0
                hour_str = f"{hour:02d}:00"

                anomalies.append(self._create_anomaly(
                    entity_id=entity_id,
                    anomaly_type="seasonal",
                    severity=self._z_to_severity(z),
                    score=min(100, z * 20),
                    value=latest.value,
                    expected_value=hourly_mean,
                    deviation_pct=dev_pct,
                    detected_at=latest.timestamp,
                    context={
                        "hour": hour,
                        "hour_str": hour_str,
                        "expected_mean": round(hourly_mean, 2),
                        "expected_std": round(hourly_std, 2),
                        "z_score": round(z, 2),
                    },
                ))

        # Daily check
        daily_mean = profile.daily_means.get(day)
        daily_std = profile.daily_stds.get(day, 0)
        weekdays_de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                       "Freitag", "Samstag", "Sonntag"]

        if daily_mean is not None and daily_std > 0:
            z = abs(latest.value - daily_mean) / daily_std
            if z >= _SEVERITY_THRESHOLDS["critical"]:
                dev_pct = ((latest.value - daily_mean) / daily_mean * 100) if daily_mean != 0 else 0

                anomalies.append(self._create_anomaly(
                    entity_id=entity_id,
                    anomaly_type="seasonal",
                    severity="critical",
                    score=min(100, z * 20),
                    value=latest.value,
                    expected_value=daily_mean,
                    deviation_pct=dev_pct,
                    detected_at=latest.timestamp,
                    context={
                        "weekday": day,
                        "weekday_name": weekdays_de[day],
                        "expected_daily_mean": round(daily_mean, 2),
                        "z_score": round(z, 2),
                    },
                ))

        return anomalies

    def _detect_frequency(self, entity_id: str, history: list[DataPoint]) -> list[Anomaly]:
        """Detect changes in reporting frequency (sensor dropping out)."""
        anomalies = []
        if len(history) < _MIN_POINTS_BASIC * 2:
            return anomalies

        # Calculate intervals between recent and historical data
        mid = len(history) // 2
        older_intervals = self._calculate_intervals(history[:mid])
        recent_intervals = self._calculate_intervals(history[mid:])

        if not older_intervals or not recent_intervals:
            return anomalies

        older_freq = statistics.mean(older_intervals)
        recent_freq = statistics.mean(recent_intervals)

        if older_freq == 0:
            return anomalies

        change_ratio = abs(recent_freq - older_freq) / older_freq

        if change_ratio >= _FREQUENCY_CHANGE_THRESHOLD:
            direction = "langsamer" if recent_freq > older_freq else "schneller"

            anomalies.append(self._create_anomaly(
                entity_id=entity_id,
                anomaly_type="frequency",
                severity="warning" if change_ratio < 1.0 else "critical",
                score=min(100, change_ratio * 50),
                value=recent_freq,
                expected_value=older_freq,
                deviation_pct=change_ratio * 100,
                detected_at=history[-1].timestamp,
                context={
                    "recent_interval_s": round(recent_freq, 1),
                    "historical_interval_s": round(older_freq, 1),
                    "change_ratio": round(change_ratio, 2),
                    "direction": direction,
                },
            ))

        return anomalies

    def _detect_correlation_anomalies(self) -> list[Anomaly]:
        """Detect broken correlations between entities."""
        anomalies = []

        for key, corr_pair in self._correlations.items():
            if abs(corr_pair.correlation) < 0.7:
                continue  # Only check strongly correlated pairs

            hist_a = self._history.get(corr_pair.entity_a, [])
            hist_b = self._history.get(corr_pair.entity_b, [])

            if len(hist_a) < 24 or len(hist_b) < 24:
                continue

            # Calculate recent correlation (last 24 points)
            recent_corr = self._calculate_correlation(
                corr_pair.entity_a, corr_pair.entity_b, window=24
            )

            if recent_corr is None:
                continue

            corr_diff = abs(recent_corr - corr_pair.correlation)

            if corr_diff > 0.5:
                anomalies.append(self._create_anomaly(
                    entity_id=f"{corr_pair.entity_a} <-> {corr_pair.entity_b}",
                    anomaly_type="correlation",
                    severity="warning" if corr_diff < 0.8 else "critical",
                    score=min(100, corr_diff * 100),
                    value=recent_corr,
                    expected_value=corr_pair.correlation,
                    deviation_pct=corr_diff * 100,
                    detected_at=datetime.now(tz=timezone.utc),
                    context={
                        "entity_a": corr_pair.entity_a,
                        "entity_b": corr_pair.entity_b,
                        "historical_correlation": round(corr_pair.correlation, 3),
                        "recent_correlation": round(recent_corr, 3),
                    },
                ))

        return anomalies

    # ── Query ───────────────────────────────────────────────────────────

    def get_anomalies(self, entity_id: str | None = None,
                      severity: str | None = None,
                      anomaly_type: str | None = None,
                      limit: int = 50) -> list[Anomaly]:
        """Get detected anomalies with optional filters."""
        results = self._anomalies

        if entity_id:
            results = [a for a in results if a.entity_id == entity_id]
        if severity:
            results = [a for a in results if a.severity == severity]
        if anomaly_type:
            results = [a for a in results if a.anomaly_type == anomaly_type]

        return results[-limit:]

    def get_profile(self, entity_id: str) -> PatternProfile | None:
        """Get learned pattern profile for an entity."""
        return self._profiles.get(entity_id)

    def get_summary(self) -> AnomalySummary:
        """Get overall anomaly detection summary."""
        type_counts: dict[str, int] = defaultdict(int)
        severity_counts = {"critical": 0, "warning": 0, "info": 0}
        entity_worst: dict[str, str] = {}

        for a in self._anomalies:
            type_counts[a.anomaly_type] += 1
            severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1

            # Track worst severity per entity
            current = entity_worst.get(a.entity_id, "ok")
            if self._severity_rank(a.severity) > self._severity_rank(current):
                entity_worst[a.entity_id] = a.severity

        # Entity health: default to "ok" for entities without anomalies
        entity_health = {}
        for eid in self._history:
            entity_health[eid] = entity_worst.get(eid, "ok")

        # Top anomalies by score
        sorted_anomalies = sorted(self._anomalies, key=lambda a: a.score, reverse=True)
        top = []
        for a in sorted_anomalies[:10]:
            top.append({
                "anomaly_id": a.anomaly_id,
                "entity_id": a.entity_id,
                "type": a.anomaly_type,
                "severity": a.severity,
                "score": round(a.score, 1),
                "description": a.description_de,
            })

        return AnomalySummary(
            total_entities=len(self._history),
            total_anomalies=len(self._anomalies),
            critical=severity_counts["critical"],
            warning=severity_counts["warning"],
            info=severity_counts["info"],
            anomaly_types=dict(type_counts),
            top_anomalies=top,
            entity_health=entity_health,
        )

    def get_correlations(self) -> list[dict[str, Any]]:
        """Get all learned correlations."""
        return [
            {
                "entity_a": c.entity_a,
                "entity_b": c.entity_b,
                "correlation": round(c.correlation, 3),
                "sample_count": c.sample_count,
                "strength": self._correlation_strength(c.correlation),
            }
            for c in self._correlations.values()
        ]

    def clear_anomalies(self, entity_id: str | None = None) -> int:
        """Clear anomalies, optionally for a specific entity."""
        if entity_id:
            before = len(self._anomalies)
            self._anomalies = [a for a in self._anomalies if a.entity_id != entity_id]
            return before - len(self._anomalies)
        else:
            count = len(self._anomalies)
            self._anomalies.clear()
            return count

    # ── Helpers ─────────────────────────────────────────────────────────

    def _create_anomaly(self, entity_id: str, anomaly_type: str, severity: str,
                        score: float, value: float, expected_value: float,
                        deviation_pct: float, detected_at: datetime,
                        context: dict[str, Any]) -> Anomaly:
        """Create an anomaly with bilingual descriptions."""
        self._anomaly_counter += 1
        aid = f"anomaly_{self._anomaly_counter:06d}"

        desc_de = self._describe_anomaly_de(anomaly_type, entity_id, value,
                                             expected_value, deviation_pct, context)
        desc_en = self._describe_anomaly_en(anomaly_type, entity_id, value,
                                             expected_value, deviation_pct, context)

        return Anomaly(
            anomaly_id=aid,
            entity_id=entity_id,
            anomaly_type=anomaly_type,
            severity=severity,
            score=round(score, 1),
            detected_at=detected_at,
            value=round(value, 2),
            expected_value=round(expected_value, 2),
            deviation_pct=round(deviation_pct, 1),
            description_de=desc_de,
            description_en=desc_en,
            context=context,
        )

    def _describe_anomaly_de(self, atype: str, entity: str, value: float,
                              expected: float, dev_pct: float,
                              ctx: dict[str, Any]) -> str:
        """Generate German anomaly description."""
        entity_short = entity.split(".")[-1] if "." in entity else entity

        if atype == "spike":
            direction = "Anstieg" if value > expected else "Abfall"
            return (f"Plötzlicher {direction} bei {entity_short}: "
                    f"{value:.1f} (erwartet: {expected:.1f}, "
                    f"Abweichung: {dev_pct:+.1f}%)")
        elif atype == "drift":
            direction = ctx.get("direction", "verändert")
            return (f"Schleichende Veränderung bei {entity_short}: "
                    f"Werte {direction} (aktuell: {value:.1f}, "
                    f"historisch: {expected:.1f})")
        elif atype == "flatline":
            return (f"Sensor {entity_short} liefert seit "
                    f"{ctx.get('consecutive_identical', 0)} Messungen "
                    f"den gleichen Wert: {value:.1f}")
        elif atype == "seasonal":
            hour = ctx.get("hour_str", "")
            weekday = ctx.get("weekday_name", "")
            if hour:
                return (f"Ungewöhnlicher Wert bei {entity_short} um {hour}: "
                        f"{value:.1f} (normal: {expected:.1f})")
            else:
                return (f"Ungewöhnlicher Wert bei {entity_short} am {weekday}: "
                        f"{value:.1f} (normal: {expected:.1f})")
        elif atype == "frequency":
            return (f"Meldefrequenz von {entity_short} hat sich geändert: "
                    f"Intervall {ctx.get('direction', 'verändert')} "
                    f"({ctx.get('change_ratio', 0):.0%} Änderung)")
        elif atype == "correlation":
            return (f"Korrelation zwischen {ctx.get('entity_a', '')} und "
                    f"{ctx.get('entity_b', '')} hat sich verändert "
                    f"(war: {ctx.get('historical_correlation', 0):.2f}, "
                    f"jetzt: {ctx.get('recent_correlation', 0):.2f})")
        return f"Anomalie bei {entity_short}: {value:.1f}"

    def _describe_anomaly_en(self, atype: str, entity: str, value: float,
                              expected: float, dev_pct: float,
                              ctx: dict[str, Any]) -> str:
        """Generate English anomaly description."""
        entity_short = entity.split(".")[-1] if "." in entity else entity

        if atype == "spike":
            direction = "spike" if value > expected else "drop"
            return (f"Sudden {direction} in {entity_short}: "
                    f"{value:.1f} (expected: {expected:.1f}, "
                    f"deviation: {dev_pct:+.1f}%)")
        elif atype == "drift":
            direction = "increasing" if ctx.get("direction") == "steigend" else "decreasing"
            return (f"Gradual drift in {entity_short}: "
                    f"values {direction} (current: {value:.1f}, "
                    f"historical: {expected:.1f})")
        elif atype == "flatline":
            return (f"Sensor {entity_short} stuck at {value:.1f} "
                    f"for {ctx.get('consecutive_identical', 0)} readings")
        elif atype == "seasonal":
            hour = ctx.get("hour_str", "")
            if hour:
                return (f"Unusual value in {entity_short} at {hour}: "
                        f"{value:.1f} (normal: {expected:.1f})")
            else:
                return (f"Unusual value in {entity_short}: "
                        f"{value:.1f} (normal: {expected:.1f})")
        elif atype == "frequency":
            return (f"Reporting frequency of {entity_short} changed: "
                    f"{ctx.get('change_ratio', 0):.0%} change in interval")
        elif atype == "correlation":
            return (f"Correlation between {ctx.get('entity_a', '')} and "
                    f"{ctx.get('entity_b', '')} changed "
                    f"(was: {ctx.get('historical_correlation', 0):.2f}, "
                    f"now: {ctx.get('recent_correlation', 0):.2f})")
        return f"Anomaly in {entity_short}: {value:.1f}"

    def _calculate_correlation(self, entity_a: str, entity_b: str,
                                window: int | None = None) -> float | None:
        """Calculate Pearson correlation between two entities."""
        hist_a = self._history.get(entity_a, [])
        hist_b = self._history.get(entity_b, [])

        if window:
            hist_a = hist_a[-window:]
            hist_b = hist_b[-window:]

        n = min(len(hist_a), len(hist_b))
        if n < 5:
            return None

        vals_a = [dp.value for dp in hist_a[-n:]]
        vals_b = [dp.value for dp in hist_b[-n:]]

        mean_a = statistics.mean(vals_a)
        mean_b = statistics.mean(vals_b)
        std_a = statistics.stdev(vals_a) if len(vals_a) > 1 else 0
        std_b = statistics.stdev(vals_b) if len(vals_b) > 1 else 0

        if std_a == 0 or std_b == 0:
            return 0.0

        cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(vals_a, vals_b)) / (n - 1)
        return cov / (std_a * std_b)

    @staticmethod
    def _calculate_intervals(history: list[DataPoint]) -> list[float]:
        """Calculate time intervals between consecutive data points in seconds."""
        intervals = []
        for i in range(1, len(history)):
            dt = (history[i].timestamp - history[i - 1].timestamp).total_seconds()
            if dt > 0:
                intervals.append(dt)
        return intervals

    @staticmethod
    def _z_to_severity(z: float) -> str:
        """Map z-score to severity level."""
        if z >= _SEVERITY_THRESHOLDS["critical"]:
            return "critical"
        elif z >= _SEVERITY_THRESHOLDS["warning"]:
            return "warning"
        return "info"

    @staticmethod
    def _severity_rank(severity: str) -> int:
        """Rank severity for comparison."""
        return {"ok": 0, "info": 1, "warning": 2, "critical": 3}.get(severity, 0)

    @staticmethod
    def _correlation_strength(corr: float) -> str:
        """Classify correlation strength."""
        abs_c = abs(corr)
        if abs_c >= 0.9:
            return "very_strong"
        elif abs_c >= 0.7:
            return "strong"
        elif abs_c >= 0.5:
            return "moderate"
        elif abs_c >= 0.3:
            return "weak"
        return "negligible"
