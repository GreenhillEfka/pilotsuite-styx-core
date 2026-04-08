"""Predictive Maintenance Engine for PilotSuite (v6.1.0).

Device health scoring, degradation tracking, and failure prediction
using statistical models on device metrics history.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class DeviceMetric:
    """A single device metric reading."""

    device_id: str
    metric: str  # battery_level, response_time_ms, error_count, uptime_pct
    value: float
    timestamp: str = ""


@dataclass
class DeviceHealth:
    """Health assessment for a single device."""

    device_id: str
    name: str
    device_type: str  # sensor, actuator, controller, gateway
    health_score: float = 100.0  # 0-100
    status: str = "healthy"  # healthy, degraded, warning, critical
    degradation_rate: float = 0.0  # % per day
    estimated_days_to_failure: int = -1  # -1 = no prediction
    last_seen: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class MaintenanceSummary:
    """Summary across all monitored devices."""

    total_devices: int = 0
    healthy: int = 0
    degraded: int = 0
    warning: int = 0
    critical: int = 0
    avg_health_score: float = 100.0
    devices_needing_attention: list[dict[str, Any]] = field(default_factory=list)
    upcoming_maintenance: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = True


# ── Health scoring thresholds ─────────────────────────────────────────────

_THRESHOLDS = {
    "battery_level": {"warning": 20.0, "critical": 10.0, "unit": "%", "inverted": True},
    "response_time_ms": {"warning": 2000.0, "critical": 5000.0, "unit": "ms"},
    "error_count": {"warning": 5.0, "critical": 20.0, "unit": "errors"},
    "uptime_pct": {"warning": 95.0, "critical": 80.0, "unit": "%", "inverted": True},
    "signal_strength": {"warning": -75.0, "critical": -85.0, "unit": "dBm", "inverted": True},
    "temperature_c": {"warning": 60.0, "critical": 80.0, "unit": "°C"},
}

# Device type specific weights
_TYPE_WEIGHTS = {
    "sensor": {"battery_level": 0.4, "response_time_ms": 0.2, "signal_strength": 0.2, "uptime_pct": 0.2},
    "actuator": {"response_time_ms": 0.3, "error_count": 0.3, "uptime_pct": 0.3, "signal_strength": 0.1},
    "controller": {"uptime_pct": 0.4, "error_count": 0.3, "response_time_ms": 0.2, "temperature_c": 0.1},
    "gateway": {"uptime_pct": 0.5, "error_count": 0.2, "response_time_ms": 0.2, "temperature_c": 0.1},
}


class PredictiveMaintenanceEngine:
    """Monitors device health and predicts failures.

    Features:
    - Health score calculation per device (0-100)
    - Degradation rate tracking
    - Time-to-failure estimation
    - Maintenance recommendations
    - Priority-based attention list
    """

    def __init__(self) -> None:
        self._devices: dict[str, DeviceHealth] = {}
        self._history: dict[str, list[DeviceMetric]] = {}  # device_id -> metrics list
        self._max_history = 168  # 7 days hourly

    def register_device(
        self,
        device_id: str,
        name: str,
        device_type: str = "sensor",
    ) -> None:
        """Register a device for monitoring."""
        if device_id not in self._devices:
            self._devices[device_id] = DeviceHealth(
                device_id=device_id,
                name=name,
                device_type=device_type,
                last_seen=datetime.now(timezone.utc).isoformat(),
            )
            self._history[device_id] = []

    def ingest_metric(self, device_id: str, metric: str, value: float) -> None:
        """Ingest a metric reading for a device."""
        if device_id not in self._devices:
            return

        ts = datetime.now(timezone.utc).isoformat()
        dm = DeviceMetric(device_id, metric, value, ts)

        history = self._history.setdefault(device_id, [])
        history.append(dm)
        if len(history) > self._max_history:
            history[:] = history[-self._max_history:]

        # Update current metrics
        self._devices[device_id].metrics[metric] = value
        self._devices[device_id].last_seen = ts

    def ingest_metrics_batch(self, metrics: list[dict[str, Any]]) -> int:
        """Ingest multiple metrics at once.

        Expected: [{"device_id": "...", "metric": "...", "value": ...}, ...]
        """
        count = 0
        for m in metrics:
            did = m.get("device_id", "")
            metric = m.get("metric", "")
            value = m.get("value", 0)
            if did and metric:
                self.ingest_metric(did, metric, float(value))
                count += 1
        return count

    def evaluate_device(self, device_id: str) -> DeviceHealth | None:
        """Evaluate health for a single device."""
        device = self._devices.get(device_id)
        if not device:
            return None

        score = self._calculate_health_score(device)
        device.health_score = round(score, 1)
        device.status = self._score_to_status(score)
        device.degradation_rate = self._calculate_degradation(device_id)
        device.estimated_days_to_failure = self._estimate_days_to_failure(device)
        device.issues = self._identify_issues(device)
        device.recommendations = self._generate_recommendations(device)

        return device

    def evaluate_all(self) -> list[DeviceHealth]:
        """Evaluate all registered devices."""
        results = []
        for device_id in self._devices:
            result = self.evaluate_device(device_id)
            if result:
                results.append(result)
        return results

    def get_summary(self) -> MaintenanceSummary:
        """Get maintenance summary across all devices."""
        self.evaluate_all()

        healthy = sum(1 for d in self._devices.values() if d.status == "healthy")
        degraded = sum(1 for d in self._devices.values() if d.status == "degraded")
        warning = sum(1 for d in self._devices.values() if d.status == "warning")
        critical = sum(1 for d in self._devices.values() if d.status == "critical")

        scores = [d.health_score for d in self._devices.values()]
        avg_score = sum(scores) / len(scores) if scores else 100.0

        # Devices needing attention (score < 70)
        attention = sorted(
            [d for d in self._devices.values() if d.health_score < 70],
            key=lambda d: d.health_score,
        )

        # Upcoming maintenance (devices with predicted failure)
        upcoming = sorted(
            [d for d in self._devices.values() if 0 < d.estimated_days_to_failure <= 30],
            key=lambda d: d.estimated_days_to_failure,
        )

        return MaintenanceSummary(
            total_devices=len(self._devices),
            healthy=healthy,
            degraded=degraded,
            warning=warning,
            critical=critical,
            avg_health_score=round(avg_score, 1),
            devices_needing_attention=[
                {
                    "device_id": d.device_id,
                    "name": d.name,
                    "health_score": d.health_score,
                    "status": d.status,
                    "issues": d.issues,
                }
                for d in attention[:10]
            ],
            upcoming_maintenance=[
                {
                    "device_id": d.device_id,
                    "name": d.name,
                    "days_to_failure": d.estimated_days_to_failure,
                    "recommendations": d.recommendations,
                }
                for d in upcoming[:10]
            ],
        )

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        """Get device health details."""
        device = self._devices.get(device_id)
        if not device:
            return None
        self.evaluate_device(device_id)
        return {
            "device_id": device.device_id,
            "name": device.name,
            "device_type": device.device_type,
            "health_score": device.health_score,
            "status": device.status,
            "degradation_rate": device.degradation_rate,
            "estimated_days_to_failure": device.estimated_days_to_failure,
            "last_seen": device.last_seen,
            "metrics": device.metrics,
            "issues": device.issues,
            "recommendations": device.recommendations,
        }

    @property
    def device_count(self) -> int:
        return len(self._devices)

    # ── Internal scoring ──────────────────────────────────────────────

    def _calculate_health_score(self, device: DeviceHealth) -> float:
        """Calculate composite health score (0-100)."""
        if not device.metrics:
            return 100.0

        weights = _TYPE_WEIGHTS.get(device.device_type, _TYPE_WEIGHTS["sensor"])
        total_weight = 0.0
        weighted_score = 0.0

        for metric, weight in weights.items():
            if metric in device.metrics:
                value = device.metrics[metric]
                metric_score = self._score_metric(metric, value)
                weighted_score += metric_score * weight
                total_weight += weight

        if total_weight == 0:
            return 100.0

        return weighted_score / total_weight

    def _score_metric(self, metric: str, value: float) -> float:
        """Score a single metric (0-100)."""
        threshold = _THRESHOLDS.get(metric)
        if not threshold:
            return 100.0

        warn = threshold["warning"]
        crit = threshold["critical"]
        inverted = threshold.get("inverted", False)

        if inverted:
            # Higher is better (uptime, signal)
            if value >= warn:
                return 100.0
            elif value >= crit:
                return 30 + 70 * (value - crit) / (warn - crit)
            else:
                return max(0, 30 * value / crit) if crit != 0 else 0
        else:
            # Lower is better (errors, response time, temperature)
            if value <= warn:
                return 100.0
            elif value <= crit:
                return 30 + 70 * (crit - value) / (crit - warn)
            else:
                return max(0, 30 * (1 - (value - crit) / crit))

    @staticmethod
    def _score_to_status(score: float) -> str:
        if score >= 80:
            return "healthy"
        elif score >= 60:
            return "degraded"
        elif score >= 30:
            return "warning"
        return "critical"

    def _calculate_degradation(self, device_id: str) -> float:
        """Calculate degradation rate (%/day) from history."""
        history = self._history.get(device_id, [])
        if len(history) < 10:
            return 0.0

        # Look at health-relevant metrics over time
        battery_readings = [
            m for m in history if m.metric == "battery_level"
        ]
        if len(battery_readings) >= 2:
            first = battery_readings[0].value
            last = battery_readings[-1].value
            days = len(battery_readings) / 24.0  # assume hourly
            if days > 0 and first > last:
                return round((first - last) / days, 2)

        return 0.0

    def _estimate_days_to_failure(self, device: DeviceHealth) -> int:
        """Estimate days until device needs maintenance."""
        if device.degradation_rate <= 0:
            return -1

        # Battery-based prediction
        battery = device.metrics.get("battery_level")
        if battery is not None and device.degradation_rate > 0:
            days = (battery - 5.0) / device.degradation_rate  # fail at 5%
            return max(0, int(days))

        # Score-based prediction
        if device.health_score < 100 and device.degradation_rate > 0:
            days = device.health_score / device.degradation_rate
            return max(0, int(days))

        return -1

    def _identify_issues(self, device: DeviceHealth) -> list[str]:
        """Identify current issues based on metrics."""
        issues = []
        for metric, value in device.metrics.items():
            threshold = _THRESHOLDS.get(metric)
            if not threshold:
                continue

            warn = threshold["warning"]
            crit = threshold["critical"]
            inverted = threshold.get("inverted", False)
            unit = threshold.get("unit", "")

            if inverted:
                if value < crit:
                    issues.append(f"{metric}: {value}{unit} (kritisch)")
                elif value < warn:
                    issues.append(f"{metric}: {value}{unit} (Warnung)")
            else:
                if value > crit:
                    issues.append(f"{metric}: {value}{unit} (kritisch)")
                elif value > warn:
                    issues.append(f"{metric}: {value}{unit} (Warnung)")

        return issues

    def _generate_recommendations(self, device: DeviceHealth) -> list[str]:
        """Generate maintenance recommendations."""
        recs = []

        battery = device.metrics.get("battery_level")
        if battery is not None and battery < 20:
            recs.append("Batterie ersetzen oder aufladen")

        if device.metrics.get("error_count", 0) > 10:
            recs.append("Gerät neu starten oder zurücksetzen")

        if device.metrics.get("response_time_ms", 0) > 3000:
            recs.append("Netzwerkverbindung prüfen")

        signal = device.metrics.get("signal_strength")
        if signal is not None and signal < -80:
            recs.append("Gerät näher an Gateway/Router platzieren")

        if device.metrics.get("temperature_c", 0) > 70:
            recs.append("Belüftung verbessern, Überhitzung möglich")

        if device.health_score < 30:
            recs.append("Gerät austauschen empfohlen")

        if not recs and device.health_score < 80:
            recs.append("Regelmäßige Wartung durchführen")

        return recs
