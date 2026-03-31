"""Anomaly Detection Engine — Slice 12.

Detects anomalous zone/module behavior and generates alerts.

Features:
- Statistical anomaly detection (z-score, moving average)
- Rule-based anomaly detection (thresholds, patterns)
- Alert routing (Telegram, HA notification, email)
- Anomaly history + trend analysis
- False-positive suppression (learning from feedback)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Type of detected anomaly."""
    VALUE_SPIKE = "value_spike"  # Sudden value change
    VALUE_DROP = "value_drop"  # Sudden value drop
    THRESHOLD_BREACH = "threshold_breach"  # Exceeded threshold
    PATTERN_DEVIATION = "pattern_deviation"  # Deviates from normal pattern
    STATE_FLAP = "state_flap"  # Rapid state changes
    MISSING_DATA = "missing_data"  # Expected data not received
    CORRELATION_BREAK = "correlation_break"  # Expected correlation broken


class AnomalySeverity(Enum):
    """Severity level of anomaly."""
    LOW = "low"  # Informational, no action needed
    MEDIUM = "medium"  # Should be investigated
    HIGH = "high"  # Requires attention
    CRITICAL = "critical"  # Immediate action required


@dataclass
class Anomaly:
    """Detected anomaly with full context."""
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    zone_id: str
    module_id: str
    entity_id: str
    current_value: Any
    expected_value: Any
    threshold: Optional[Any] = None
    deviation_score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[str] = None
    feedback: Optional[str] = None  # User feedback: "false_positive", "valid", etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "entity_id": self.entity_id,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "threshold": self.threshold,
            "deviation_score": self.deviation_score,
            "timestamp": self.timestamp,
            "description": self.description,
            "context": self.context,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "feedback": self.feedback,
        }


@dataclass
class AnomalyHistory:
    """Historical data for anomaly detection."""
    entity_id: str
    values: List[float] = field(default_factory=list)
    timestamps: List[str] = field(default_factory=list)
    mean: float = 0.0
    stddev: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def update(self, value: float, timestamp: str) -> None:
        """Update history with new value."""
        self.values.append(value)
        self.timestamps.append(timestamp)
        
        # Keep last 1000 values
        if len(self.values) > 1000:
            self.values = self.values[-1000:]
            self.timestamps = self.timestamps[-1000:]
        
        # Recalculate statistics
        self._recalculate()
    
    def _recalculate(self) -> None:
        """Recalculate statistics."""
        if not self.values:
            return
        
        self.mean = sum(self.values) / len(self.values)
        self.min_value = min(self.values)
        self.max_value = max(self.values)
        
        if len(self.values) > 1:
            variance = sum((x - self.mean) ** 2 for x in self.values) / len(self.values)
            self.stddev = variance ** 0.5
        
        self.last_updated = datetime.now(timezone.utc).isoformat()
    
    def z_score(self, value: float) -> float:
        """Calculate z-score for a value."""
        if self.stddev == 0:
            return 0.0
        return (value - self.mean) / self.stddev


class AnomalyDetectionEngine:
    """Main anomaly detection engine."""
    
    def __init__(self):
        self._history: Dict[str, AnomalyHistory] = {}
        self._anomalies: Dict[str, Anomaly] = {}
        self._rules: List[Dict[str, Any]] = []
        self._anomaly_counter = 0
        
        # Default thresholds
        self._z_score_threshold = 3.0  # Values beyond 3 stddev are anomalous
        self._spike_threshold = 0.5  # 50% change is a spike
        self._flap_count_threshold = 5  # 5 state changes in window
        self._flap_window_seconds = 60
    
    def add_history(self, entity_id: str, value: float, timestamp: Optional[str] = None) -> None:
        """Add value to history for anomaly detection."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        if entity_id not in self._history:
            self._history[entity_id] = AnomalyHistory(entity_id=entity_id)
        
        self._history[entity_id].update(value, timestamp)
    
    def detect_anomalies(self, entity_id: str, current_value: Any, context: Optional[Dict[str, Any]] = None) -> List[Anomaly]:
        """Detect anomalies for a given entity value."""
        anomalies = []
        
        # Check if we have history
        if entity_id not in self._history or len(self._history[entity_id].values) < 10:
            # Not enough history for statistical detection
            return anomalies
        
        history = self._history[entity_id]
        
        # Statistical anomaly detection (z-score)
        if isinstance(current_value, (int, float)):
            z_score = history.z_score(current_value)
            if abs(z_score) > self._z_score_threshold:
                anomaly = self._create_anomaly(
                    anomaly_type=AnomalyType.VALUE_SPIKE if z_score > 0 else AnomalyType.VALUE_DROP,
                    entity_id=entity_id,
                    current_value=current_value,
                    expected_value=history.mean,
                    deviation_score=abs(z_score),
                    description=f"Value {current_value} deviates {abs(z_score):.2f} stddev from mean {history.mean:.2f}",
                    context=context or {},
                )
                anomalies.append(anomaly)
        
        # Rule-based detection
        for rule in self._rules:
            if rule.get("entity_id") == entity_id or rule.get("entity_pattern", "*") == "*":
                rule_anomaly = self._check_rule(rule, entity_id, current_value, context)
                if rule_anomaly:
                    anomalies.append(rule_anomaly)
        
        return anomalies
    
    def _check_rule(self, rule: Dict[str, Any], entity_id: str, current_value: Any, context: Optional[Dict[str, Any]]) -> Optional[Anomaly]:
        """Check a single rule for anomaly."""
        rule_type = rule.get("type")
        
        if rule_type == "threshold":
            threshold = rule.get("threshold")
            operator = rule.get("operator", ">")
            
            if isinstance(current_value, (int, float)) and isinstance(threshold, (int, float)):
                breached = False
                if operator == ">" and current_value > threshold:
                    breached = True
                elif operator == ">=" and current_value >= threshold:
                    breached = True
                elif operator == "<" and current_value < threshold:
                    breached = True
                elif operator == "<=" and current_value <= threshold:
                    breached = True
                elif operator == "==" and current_value == threshold:
                    breached = True
                
                if breached:
                    return self._create_anomaly(
                        anomaly_type=AnomalyType.THRESHOLD_BREACH,
                        entity_id=entity_id,
                        current_value=current_value,
                        expected_value=threshold,
                        threshold=threshold,
                        description=f"Value {current_value} breached threshold {operator} {threshold}",
                        context=context or {},
                        severity=AnomalySeverity.HIGH if rule.get("severity") == "high" else AnomalySeverity.MEDIUM,
                    )
        
        return None
    
    def _create_anomaly(
        self,
        anomaly_type: AnomalyType,
        entity_id: str,
        current_value: Any,
        expected_value: Any,
        deviation_score: float = 0.0,
        threshold: Optional[Any] = None,
        description: str = "",
        context: Optional[Dict[str, Any]] = None,
        severity: AnomalySeverity = AnomalySeverity.MEDIUM,
    ) -> Anomaly:
        """Create a new anomaly."""
        self._anomaly_counter += 1
        
        # Extract zone_id and module_id from context
        zone_id = (context or {}).get("zone_id", "unknown")
        module_id = (context or {}).get("module_id", "unknown")
        
        anomaly = Anomaly(
            anomaly_id=f"anomaly_{self._anomaly_counter}",
            anomaly_type=anomaly_type,
            severity=severity,
            zone_id=zone_id,
            module_id=module_id,
            entity_id=entity_id,
            current_value=current_value,
            expected_value=expected_value,
            threshold=threshold,
            deviation_score=deviation_score,
            description=description,
            context=context or {},
        )
        
        # Store anomaly
        self._anomalies[anomaly.anomaly_id] = anomaly
        
        return anomaly
    
    def add_rule(self, rule: Dict[str, Any]) -> None:
        """Add a detection rule."""
        self._rules.append(rule)
    
    def get_anomalies(self, entity_id: Optional[str] = None, zone_id: Optional[str] = None, unresolved_only: bool = True) -> List[Dict[str, Any]]:
        """Get anomalies, optionally filtered."""
        anomalies = list(self._anomalies.values())
        
        if unresolved_only:
            anomalies = [a for a in anomalies if not a.resolved]
        
        if entity_id:
            anomalies = [a for a in anomalies if a.entity_id == entity_id]
        
        if zone_id:
            anomalies = [a for a in anomalies if a.zone_id == zone_id]
        
        # Sort by severity (critical first) then timestamp
        severity_order = {
            AnomalySeverity.CRITICAL: 0,
            AnomalySeverity.HIGH: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.LOW: 3,
        }
        anomalies.sort(key=lambda a: (severity_order.get(a.severity, 4), a.timestamp), reverse=True)
        
        return [a.to_dict() for a in anomalies]
    
    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        """Acknowledge an anomaly."""
        if anomaly_id not in self._anomalies:
            return False
        
        self._anomalies[anomaly_id].acknowledged = True
        return True
    
    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """Resolve an anomaly."""
        if anomaly_id not in self._anomalies:
            return False
        
        anomaly = self._anomalies[anomaly_id]
        anomaly.resolved = True
        anomaly.resolved_at = datetime.now(timezone.utc).isoformat()
        return True
    
    def add_feedback(self, anomaly_id: str, feedback: str) -> bool:
        """Add user feedback for an anomaly."""
        if anomaly_id not in self._anomalies:
            return False
        
        self._anomalies[anomaly_id].feedback = feedback
        
        # Learn from false positive feedback
        if feedback == "false_positive":
            self._learn_from_false_positive(anomaly_id)
        
        return True
    
    def _learn_from_false_positive(self, anomaly_id: str) -> None:
        """Learn from false positive feedback to reduce future false positives."""
        anomaly = self._anomalies[anomaly_id]
        
        # Adjust z-score threshold if this was a statistical anomaly
        if anomaly.anomaly_type in (AnomalyType.VALUE_SPIKE, AnomalyType.VALUE_DROP):
            # Increase threshold slightly to avoid similar false positives
            self._z_score_threshold = min(self._z_score_threshold + 0.1, 5.0)
            logger.info("Adjusted z-score threshold to %.2f after false positive", self._z_score_threshold)


def create_anomaly_detection_engine() -> AnomalyDetectionEngine:
    """Factory function to create anomaly detection engine."""
    return AnomalyDetectionEngine()
