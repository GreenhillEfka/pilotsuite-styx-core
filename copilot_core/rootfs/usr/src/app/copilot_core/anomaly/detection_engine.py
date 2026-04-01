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
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(timestamp: str) -> datetime:
    normalized = str(timestamp or "").strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


_SEVERITY_RANK = {
    AnomalySeverity.LOW: 0,
    AnomalySeverity.MEDIUM: 1,
    AnomalySeverity.HIGH: 2,
    AnomalySeverity.CRITICAL: 3,
}

_NOTIFICATION_CHANNELS = {
    "push",
    "email",
    "sms",
    "webhook",
    "telegram",
    "whatsapp",
    "slack",
    "custom",
}


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
    timestamp: str = field(default_factory=_now_iso)
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
    last_updated: str = field(default_factory=_now_iso)

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

        self.last_updated = _now_iso()

    def z_score(self, value: float) -> float:
        """Calculate z-score for a value."""
        if self.stddev == 0:
            return 0.0
        return (value - self.mean) / self.stddev


@dataclass
class AlertRoute:
    """Alert routing definition for anomaly notifications."""

    route_id: str
    channel: str
    recipient: str = ""
    min_severity: AnomalySeverity = AnomalySeverity.MEDIUM
    throttle_seconds: int = 300
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    last_sent_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "channel": self.channel,
            "recipient": self.recipient,
            "min_severity": self.min_severity.value,
            "throttle_seconds": self.throttle_seconds,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_sent_at": self.last_sent_at,
        }


@dataclass
class AlertDispatch:
    """Recorded alert delivery attempt."""

    dispatch_id: str
    anomaly_id: str
    route_id: str
    channel: str
    recipient: str = ""
    status: str = "pending"
    sent_at: str = field(default_factory=_now_iso)
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "anomaly_id": self.anomaly_id,
            "route_id": self.route_id,
            "channel": self.channel,
            "recipient": self.recipient,
            "status": self.status,
            "sent_at": self.sent_at,
            "result": self.result,
            "error_message": self.error_message,
        }


AlertHandler = Callable[[Anomaly, AlertRoute], Dict[str, Any]]


class AnomalyDetectionEngine:
    """Main anomaly detection engine."""

    def __init__(self, notification_engine: Any = None):
        self._history: Dict[str, AnomalyHistory] = {}
        self._anomalies: Dict[str, Anomaly] = {}
        self._rules: List[Dict[str, Any]] = []
        self._anomaly_counter = 0
        self._route_counter = 0
        self._dispatch_counter = 0
        self._alert_routes: Dict[str, AlertRoute] = {}
        self._alert_history: List[AlertDispatch] = []
        self._alert_handlers: Dict[str, AlertHandler] = {"log": self._handle_log_alert}
        self._last_alert_by_signature: Dict[tuple[str, str, str], str] = {}
        self._notification_engine = notification_engine

        # Default thresholds
        self._z_score_threshold = 3.0  # Values beyond 3 stddev are anomalous
        self._spike_threshold = 0.5  # 50% change is a spike
        self._flap_count_threshold = 5  # 5 state changes in window
        self._flap_window_seconds = 60

    def add_history(self, entity_id: str, value: float, timestamp: Optional[str] = None) -> None:
        """Add value to history for anomaly detection."""
        if timestamp is None:
            timestamp = _now_iso()

        if entity_id not in self._history:
            self._history[entity_id] = AnomalyHistory(entity_id=entity_id)

        self._history[entity_id].update(value, timestamp)

    def add_rule(self, rule: Dict[str, Any]) -> None:
        """Add a detection rule."""
        self._rules.append(rule)

    def register_alert_handler(self, channel: str, handler: AlertHandler) -> None:
        """Register a custom alert delivery handler."""
        self._alert_handlers[channel] = handler

    def set_notification_engine(self, notification_engine: Any) -> None:
        """Attach a notification engine used for built-in channels."""
        self._notification_engine = notification_engine

    def register_alert_route(
        self,
        channel: str,
        recipient: str = "",
        *,
        min_severity: str | AnomalySeverity = AnomalySeverity.MEDIUM,
        throttle_seconds: int = 300,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        route_id: Optional[str] = None,
    ) -> str:
        """Register a route for alert delivery."""
        self._route_counter += 1
        resolved_route_id = route_id or f"route_{self._route_counter}"
        route = AlertRoute(
            route_id=resolved_route_id,
            channel=channel,
            recipient=recipient,
            min_severity=self._coerce_severity(min_severity),
            throttle_seconds=max(int(throttle_seconds), 0),
            enabled=enabled,
            metadata=metadata or {},
        )
        self._alert_routes[resolved_route_id] = route
        return resolved_route_id

    def get_alert_routes(self) -> List[Dict[str, Any]]:
        """Return registered alert routes."""
        return [route.to_dict() for route in self._alert_routes.values()]

    def get_alert_history(
        self,
        *,
        anomaly_id: Optional[str] = None,
        channel: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return recorded alert delivery attempts."""
        history = list(self._alert_history)
        if anomaly_id:
            history = [dispatch for dispatch in history if dispatch.anomaly_id == anomaly_id]
        if channel:
            history = [dispatch for dispatch in history if dispatch.channel == channel]
        history.sort(key=lambda item: _parse_iso(item.sent_at), reverse=True)
        if limit is not None:
            history = history[: max(int(limit), 0)]
        return [dispatch.to_dict() for dispatch in history]

    def detect_anomalies(
        self,
        entity_id: str,
        current_value: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Anomaly]:
        """Detect anomalies for a given entity value."""
        anomalies: List[Anomaly] = []

        # Rule-based detection must work even without statistical history.
        for rule in self._rules:
            if rule.get("entity_id") == entity_id or rule.get("entity_pattern", "*") == "*":
                rule_anomaly = self._check_rule(rule, entity_id, current_value, context)
                if rule_anomaly:
                    anomalies.append(rule_anomaly)

        # Check if we have history
        if entity_id not in self._history or not self._history[entity_id].values:
            return anomalies

        history = self._history[entity_id]

        # Early spike/drop detection should work with limited history using the
        # latest known value as baseline. Full z-score detection still waits for
        # a broader sample window.
        if isinstance(current_value, (int, float)) and len(history.values) == 1:
            baseline = history.values[-1]
            if isinstance(baseline, (int, float)) and baseline != 0:
                relative_change = abs(current_value - baseline) / abs(baseline)
                if relative_change >= self._spike_threshold:
                    anomaly = self._create_anomaly(
                        anomaly_type=(
                            AnomalyType.VALUE_SPIKE
                            if current_value > baseline
                            else AnomalyType.VALUE_DROP
                        ),
                        entity_id=entity_id,
                        current_value=current_value,
                        expected_value=baseline,
                        deviation_score=relative_change,
                        severity=self._severity_for_relative_change(relative_change),
                        description=(
                            f"Value {current_value} changed {relative_change:.2f} relative to baseline {baseline}"
                        ),
                        context=context or {},
                    )
                    anomalies.append(anomaly)

        if len(history.values) < 10:
            # Not enough history for statistical detection
            return anomalies

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
                    severity=self._severity_for_deviation(abs(z_score)),
                    description=(
                        f"Value {current_value} deviates {abs(z_score):.2f} stddev from mean {history.mean:.2f}"
                    ),
                    context=context or {},
                )
                anomalies.append(anomaly)

        return anomalies

    def _check_rule(
        self,
        rule: Dict[str, Any],
        entity_id: str,
        current_value: Any,
        context: Optional[Dict[str, Any]],
    ) -> Optional[Anomaly]:
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
                        severity=self._coerce_severity(rule.get("severity", AnomalySeverity.HIGH)),
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

        self._anomalies[anomaly.anomaly_id] = anomaly
        self._route_anomaly(anomaly)
        return anomaly

    def _route_anomaly(self, anomaly: Anomaly) -> None:
        """Route anomaly through registered alert channels."""
        if not self._alert_routes:
            return

        for route in self._alert_routes.values():
            if not route.enabled:
                continue
            if _SEVERITY_RANK[anomaly.severity] < _SEVERITY_RANK[route.min_severity]:
                continue
            if self._is_route_throttled(route, anomaly):
                continue
            self._dispatch_alert(route, anomaly)

    def _is_route_throttled(self, route: AlertRoute, anomaly: Anomaly) -> bool:
        """Check if an alert should be suppressed by route throttling."""
        if route.throttle_seconds <= 0:
            return False

        signature = (route.route_id, anomaly.entity_id, anomaly.anomaly_type.value)
        last_sent = self._last_alert_by_signature.get(signature)
        if not last_sent:
            return False

        elapsed = (_parse_iso(anomaly.timestamp) - _parse_iso(last_sent)).total_seconds()
        return elapsed < route.throttle_seconds

    def _dispatch_alert(self, route: AlertRoute, anomaly: Anomaly) -> None:
        """Dispatch one anomaly alert through a route."""
        self._dispatch_counter += 1
        dispatch = AlertDispatch(
            dispatch_id=f"dispatch_{self._dispatch_counter}",
            anomaly_id=anomaly.anomaly_id,
            route_id=route.route_id,
            channel=route.channel,
            recipient=route.recipient,
        )

        try:
            if route.channel in self._alert_handlers:
                result = self._alert_handlers[route.channel](anomaly, route)
            elif self._notification_engine is not None and route.channel in _NOTIFICATION_CHANNELS:
                result = self._send_via_notification_engine(anomaly, route)
            else:
                result = self._handle_log_alert(anomaly, route)

            dispatch.status = "sent"
            dispatch.result = result or {}
            route.last_sent_at = dispatch.sent_at
            self._last_alert_by_signature[(route.route_id, anomaly.entity_id, anomaly.anomaly_type.value)] = dispatch.sent_at
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception("Alert dispatch failed: %s", exc)
            dispatch.status = "failed"
            dispatch.error_message = str(exc)

        self._alert_history.append(dispatch)
        if len(self._alert_history) > 1000:
            self._alert_history = self._alert_history[-1000:]

    def _handle_log_alert(self, anomaly: Anomaly, route: AlertRoute) -> Dict[str, Any]:
        """Default alert handler when no channel integration is configured."""
        message = self._build_alert_message(anomaly)
        logger.warning("Anomaly alert [%s] %s", route.channel, message)
        return {
            "channel": route.channel,
            "recipient": route.recipient,
            "message": message,
            "handler": "log",
        }

    def _send_via_notification_engine(self, anomaly: Anomaly, route: AlertRoute) -> Dict[str, Any]:
        """Deliver anomaly alert through NotificationEngine-compatible API."""
        if self._notification_engine is None:
            return self._handle_log_alert(anomaly, route)

        notification_id = self._notification_engine.send_notification(
            title=self._build_alert_title(anomaly),
            message=self._build_alert_message(anomaly),
            channel=route.channel,
            recipient=route.recipient,
            priority=self._notification_priority(anomaly.severity),
            metadata={
                "anomaly": anomaly.to_dict(),
                "route": route.to_dict(),
            },
        )
        return {
            "channel": route.channel,
            "recipient": route.recipient,
            "notification_id": notification_id,
            "handler": "notification_engine",
        }

    def _build_alert_title(self, anomaly: Anomaly) -> str:
        entity_label = anomaly.entity_id or anomaly.module_id or anomaly.zone_id or "unknown"
        return f"Anomaly {anomaly.severity.value.upper()}: {entity_label}"

    def _build_alert_message(self, anomaly: Anomaly) -> str:
        zone_part = f" zone={anomaly.zone_id}" if anomaly.zone_id and anomaly.zone_id != "unknown" else ""
        module_part = f" module={anomaly.module_id}" if anomaly.module_id and anomaly.module_id != "unknown" else ""
        return (
            f"{anomaly.description or anomaly.anomaly_type.value}"
            f" (entity={anomaly.entity_id}{zone_part}{module_part}, "
            f"current={anomaly.current_value}, expected={anomaly.expected_value})"
        )

    def _notification_priority(self, severity: AnomalySeverity) -> str:
        if severity == AnomalySeverity.CRITICAL:
            return "urgent"
        if severity == AnomalySeverity.HIGH:
            return "high"
        if severity == AnomalySeverity.LOW:
            return "low"
        return "normal"

    def get_anomalies(
        self,
        entity_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        unresolved_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get anomalies, optionally filtered."""
        anomalies = list(self._anomalies.values())

        if unresolved_only:
            anomalies = [a for a in anomalies if not a.resolved]

        if entity_id:
            anomalies = [a for a in anomalies if a.entity_id == entity_id]

        if zone_id:
            anomalies = [a for a in anomalies if a.zone_id == zone_id]

        anomalies.sort(
            key=lambda a: (
                _SEVERITY_RANK.get(a.severity, -1),
                _parse_iso(a.timestamp).timestamp(),
            ),
            reverse=True,
        )

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
        anomaly.resolved_at = _now_iso()
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

    def get_anomaly_summary(
        self,
        *,
        entity_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        since_hours: Optional[int] = 24,
    ) -> Dict[str, Any]:
        """Build a compact anomaly/read-model summary for dashboards and alerts."""
        anomalies = list(self._anomalies.values())
        if entity_id:
            anomalies = [a for a in anomalies if a.entity_id == entity_id]
        if zone_id:
            anomalies = [a for a in anomalies if a.zone_id == zone_id]

        if since_hours is not None:
            window_start = datetime.now(timezone.utc) - timedelta(hours=max(int(since_hours), 0))
            anomalies = [a for a in anomalies if _parse_iso(a.timestamp) >= window_start]

        by_severity = {severity.value: 0 for severity in AnomalySeverity}
        by_type: Dict[str, int] = {}
        by_entity: Dict[str, int] = {}

        for anomaly in anomalies:
            by_severity[anomaly.severity.value] += 1
            by_type[anomaly.anomaly_type.value] = by_type.get(anomaly.anomaly_type.value, 0) + 1
            by_entity[anomaly.entity_id] = by_entity.get(anomaly.entity_id, 0) + 1

        unresolved = [a for a in anomalies if not a.resolved]
        acknowledged = [a for a in anomalies if a.acknowledged]
        false_positives = [a for a in anomalies if a.feedback == "false_positive"]
        alert_history = self.get_alert_history(limit=1000)
        if entity_id:
            entity_anomaly_ids = {a.anomaly_id for a in anomalies}
            alert_history = [item for item in alert_history if item.get("anomaly_id") in entity_anomaly_ids]

        hottest_entities = [
            {"entity_id": key, "count": value}
            for key, value in sorted(by_entity.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]

        top_anomalies = [
            anomaly.to_dict()
            for anomaly in sorted(
                anomalies,
                key=lambda item: (_SEVERITY_RANK[item.severity], item.deviation_score),
                reverse=True,
            )[:5]
        ]

        return {
            "generated_at": _now_iso(),
            "window_hours": since_hours,
            "entity_id": entity_id,
            "zone_id": zone_id,
            "total": len(anomalies),
            "unresolved": len(unresolved),
            "resolved": len(anomalies) - len(unresolved),
            "acknowledged": len(acknowledged),
            "false_positive_count": len(false_positives),
            "false_positive_rate": (len(false_positives) / len(anomalies)) if anomalies else 0.0,
            "alerts_sent": len([item for item in alert_history if item.get("status") == "sent"]),
            "by_severity": by_severity,
            "by_type": by_type,
            "hottest_entities": hottest_entities,
            "top_anomalies": top_anomalies,
        }

    def _coerce_severity(self, value: str | AnomalySeverity) -> AnomalySeverity:
        if isinstance(value, AnomalySeverity):
            return value
        normalized = str(value or "").strip().lower()
        for severity in AnomalySeverity:
            if severity.value == normalized:
                return severity
        return AnomalySeverity.MEDIUM

    def _severity_for_deviation(self, deviation_score: float) -> AnomalySeverity:
        if deviation_score >= max(self._z_score_threshold + 2.0, 5.0):
            return AnomalySeverity.CRITICAL
        if deviation_score >= max(self._z_score_threshold + 1.0, 4.0):
            return AnomalySeverity.HIGH
        return AnomalySeverity.MEDIUM

    def _severity_for_relative_change(self, relative_change: float) -> AnomalySeverity:
        if relative_change >= 2.0:
            return AnomalySeverity.CRITICAL
        if relative_change >= 1.0:
            return AnomalySeverity.HIGH
        return AnomalySeverity.MEDIUM


def create_anomaly_detection_engine() -> AnomalyDetectionEngine:
    """Factory function to create anomaly detection engine."""
    return AnomalyDetectionEngine()
