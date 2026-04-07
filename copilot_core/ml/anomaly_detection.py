"""P3-004: Anomaly Detection — Outlier Detection, Alerts."""
from __future__ import annotations

import logging
import time
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class AnomalySeverity(Enum):
    """Severity levels for anomalies."""
    LOW = "low"  # Minor deviation
    MEDIUM = "medium"  # Notable deviation
    HIGH = "high"  # Significant deviation
    CRITICAL = "critical"  # Major deviation


@dataclass
class Anomaly:
    """Detected anomaly."""
    id: str
    entity_id: str
    metric: str
    expected_value: float
    actual_value: float
    deviation: float  # Standard deviations from mean
    severity: AnomalySeverity
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricStats:
    """Statistics for a metric."""
    mean: float
    std_dev: float
    min_value: float
    max_value: float
    sample_count: int
    last_updated: float


class AnomalyDetector:
    """Statistical anomaly detection using z-scores."""

    def __init__(
        self,
        window_size: int = 100,
        low_threshold: float = 2.0,
        medium_threshold: float = 3.0,
        high_threshold: float = 4.0,
        critical_threshold: float = 5.0,
    ):
        self.window_size = window_size
        self.thresholds = {
            AnomalySeverity.LOW: low_threshold,
            AnomalySeverity.MEDIUM: medium_threshold,
            AnomalySeverity.HIGH: high_threshold,
            AnomalySeverity.CRITICAL: critical_threshold,
        }
        
        self._data: Dict[str, deque] = {}
        self._stats: Dict[str, MetricStats] = {}
        self._anomalies: List[Anomaly] = []
        self._alert_callbacks: List[callable] = []

    def add_data_point(self, entity_id: str, metric: str, value: float, context: Optional[Dict] = None):
        """Add a data point and check for anomalies."""
        key = f"{entity_id}:{metric}"
        
        # Initialize data structure
        if key not in self._data:
            self._data[key] = deque(maxlen=self.window_size)
        
        # Add value
        self._data[key].append((time.time(), value))
        
        # Update stats
        self._update_stats(key)
        
        # Check for anomaly
        if len(self._data[key]) >= 10:  # Need minimum samples
            anomaly = self._check_anomaly(key, value, context)
            if anomaly:
                self._anomalies.append(anomaly)
                self._trigger_alerts(anomaly)

    def _update_stats(self, key: str):
        """Update statistics for a metric."""
        values = [v for _, v in self._data[key]]
        
        if len(values) < 2:
            return
        
        self._stats[key] = MetricStats(
            mean=statistics.mean(values),
            std_dev=statistics.stdev(values) if len(values) > 1 else 0,
            min_value=min(values),
            max_value=max(values),
            sample_count=len(values),
            last_updated=time.time()
        )

    def _check_anomaly(
        self,
        key: str,
        value: float,
        context: Optional[Dict] = None
    ) -> Optional[Anomaly]:
        """Check if value is anomalous."""
        stats = self._stats.get(key)
        if not stats or stats.std_dev == 0:
            return None
        
        # Calculate z-score
        z_score = abs(value - stats.mean) / stats.std_dev
        
        # Determine severity
        severity = None
        for sev, threshold in sorted(self.thresholds.items(), key=lambda x: x[1], reverse=True):
            if z_score >= threshold:
                severity = sev
                break
        
        if not severity or severity == AnomalySeverity.LOW:
            return None
        
        entity_id, metric = key.split(":", 1)
        
        import hashlib
        anomaly_id = hashlib.sha256(f"{key}{value}{time.time()}".encode()).hexdigest()[:16]
        
        return Anomaly(
            id=anomaly_id,
            entity_id=entity_id,
            metric=metric,
            expected_value=stats.mean,
            actual_value=value,
            deviation=z_score,
            severity=severity,
            context=context or {}
        )

    def _trigger_alerts(self, anomaly: Anomaly):
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                callback(anomaly)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def register_alert_callback(self, callback: callable):
        """Register callback for anomaly alerts."""
        self._alert_callbacks.append(callback)

    def get_anomalies(
        self,
        entity_id: Optional[str] = None,
        severity: Optional[AnomalySeverity] = None,
        limit: int = 100
    ) -> List[Anomaly]:
        """Get detected anomalies."""
        anomalies = self._anomalies
        
        if entity_id:
            anomalies = [a for a in anomalies if a.entity_id == entity_id]
        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]
        
        return anomalies[-limit:]

    def get_stats(self, entity_id: Optional[str] = None) -> Dict[str, MetricStats]:
        """Get metric statistics."""
        if entity_id:
            return {k: v for k, v in self._stats.items() if v.startswith(entity_id)}
        return self._stats.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get anomaly detection summary."""
        severity_counts = {}
        for anomaly in self._anomalies:
            severity_counts[anomaly.severity.value] = severity_counts.get(anomaly.severity.value, 0) + 1
        
        return {
            "total_anomalies": len(self._anomalies),
            "monitored_metrics": len(self._stats),
            "severity_distribution": severity_counts,
            "recent_anomalies": len([a for a in self._anomalies if time.time() - a.timestamp < 3600]),
        }

    def clear_old_anomalies(self, max_age_hours: float = 24):
        """Clear anomalies older than max_age_hours."""
        cutoff = time.time() - (max_age_hours * 3600)
        self._anomalies = [a for a in self._anomalies if a.timestamp > cutoff]


# Global default anomaly detector
default_anomaly_detector: Optional[AnomalyDetector] = None


def init_anomaly_detector(**kwargs) -> AnomalyDetector:
    """Initialize global anomaly detector."""
    global default_anomaly_detector
    default_anomaly_detector = AnomalyDetector(**kwargs)
    return default_anomaly_detector


def record_metric(entity_id: str, metric: str, value: float, **kwargs):
    """Convenience function to record metric."""
    if default_anomaly_detector:
        default_anomaly_detector.add_data_point(entity_id, metric, value, kwargs)


def get_anomalies(**kwargs) -> List[Anomaly]:
    """Convenience function to get anomalies."""
    if default_anomaly_detector:
        return default_anomaly_detector.get_anomalies(**kwargs)
    return []
