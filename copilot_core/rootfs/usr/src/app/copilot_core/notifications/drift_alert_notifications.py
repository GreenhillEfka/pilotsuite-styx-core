"""Drift Alert Notifications — converts drift detection alerts into PilotSuite notifications.

Subscribes to (or is called after) drift detection runs and fires notifications
through the existing NotificationEngine for any drifted/missing blueprints.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from copilot_core.notifications.engine import (
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationEngine,
)

_LOGGER = logging.getLogger(__name__)

# Severity → NotificationPriority mapping
_SEVERITY_TO_PRIORITY = {
    "info": NotificationPriority.NORMAL,
    "warning": NotificationPriority.HIGH,
    "critical": NotificationPriority.URGENT,
}

# Template ID for drift alerts
_DRIFT_TEMPLATE_ID = "drift_alert"


@dataclass
class DriftAlertNotification:
    """A drift alert packaged as a PilotSuite notification."""
    notification: Notification
    blueprint_id: str
    blueprint_name: str
    severity: str
    drift_count: int = 0
    message: str = ""


class DriftAlertNotifier:
    """Converts DriftAlert objects into NotificationEngine notifications.

    Usage::

        notifier = DriftAlertNotifier(notification_engine)
        alerts = detector.check_all()
        for alert in alerts:
            if alert.status != DriftStatus.CLEAN:
                notifier.notify(alert)
    """

    def __init__(
        self,
        engine: Optional[NotificationEngine] = None,
        channel: NotificationChannel = NotificationChannel.PUSH,
        recipient: str = "",
    ) -> None:
        self._engine = engine
        self._channel = channel
        self._recipient = recipient
        # Track recently notified blueprint_ids to avoid spam
        self._notified_recently: Dict[str, float] = {}
        # Suppress duplicate alerts within this window (seconds)
        self._dedup_window = 3600  # 1 hour

    def notify(self, alert, drift_count: int = 0) -> Optional[Notification]:
        """Convert a DriftAlert into a Notification and dispatch it.

        Returns the Notification object if dispatched, None if suppressed.
        """
        if self._engine is None:
            _LOGGER.debug("No notification engine set, skipping drift alert for %s", alert.blueprint_id)
            return None

        # Deduplicate: skip if we notified about this blueprint recently
        now = datetime.now(timezone.utc).timestamp()
        last = self._notified_recently.get(alert.blueprint_id, 0)
        if now - last < self._dedup_window and alert.severity != "critical":
            _LOGGER.debug(
                "Drift alert for %s suppressed (notified %.0f s ago)",
                alert.blueprint_id,
                now - last,
            )
            return None

        priority = _SEVERITY_TO_PRIORITY.get(
            alert.severity, NotificationPriority.NORMAL
        )

        title = self._build_title(alert)
        message = self._build_message(alert)

        notification = Notification(
            notification_id=f"drift_{alert.blueprint_id}_{int(now)}",
            title=title,
            message=message,
            channel=self._channel,
            priority=priority,
            recipient=self._recipient,
            template_id=_DRIFT_TEMPLATE_ID,
            template_data={
                "blueprint_id": alert.blueprint_id,
                "blueprint_name": alert.name,
                "status": alert.status.value,
                "severity": alert.severity,
                "drift_count": drift_count,
                "stored_hash": alert.stored_hash or "",
                "current_hash": alert.current_hash or "",
                "detected_at": alert.detected_at,
                "message": alert.message,
            },
            metadata={
                "alert_type": "blueprint_drift",
                "blueprint_id": alert.blueprint_id,
                "severity": alert.severity,
            },
        )

        try:
            self._engine.send(notification)
            self._notified_recently[alert.blueprint_id] = now
            _LOGGER.info(
                "Drift notification sent for %s (severity=%s, priority=%s)",
                alert.blueprint_id,
                alert.severity,
                priority.value,
            )
        except Exception as exc:
            _LOGGER.warning("Failed to send drift notification for %s: %s", alert.blueprint_id, exc)

        return notification

    def notify_batch(
        self,
        alerts: List[Any],
        drift_counts: Optional[Dict[str, int]] = None,
    ) -> List[Notification]:
        """Notify about a batch of drift alerts.

        Args:
            alerts: List of DriftAlert objects.
            drift_counts: Optional dict of blueprint_id → drift_count.

        Returns list of dispatched Notification objects.
        """
        notifications: List[Notification] = []
        counts = drift_counts or {}
        for alert in alerts:
            # Only notify for non-clean statuses
            if getattr(alert, "status", None) and alert.status.value == "clean":
                continue
            n = self.notify(alert, drift_count=counts.get(alert.blueprint_id, 0))
            if n:
                notifications.append(n)
        return notifications

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _build_title(self, alert) -> str:
        if alert.severity == "critical":
            return f"🔴 Kritisch: Blueprint geändert — {alert.name}"
        if alert.severity == "warning":
            return f"🟡 Blueprint-Drift erkannt — {alert.name}"
        if alert.status.value == "new":
            return f"🆕 Neuer Blueprint registriert — {alert.name}"
        if alert.status.value == "missing":
            return f"⚠️ Blueprint fehlt — {alert.name}"
        return f"ℹ️ Blueprint-Update — {alert.name}"

    def _build_message(self, alert) -> str:
        msg = alert.message or ""
        if alert.severity == "critical":
            return (
                f"'{alert.name}' wurde mehrfach geändert (Drift #{alert.severity}). "
                f"Bitte überprüfe die Automatisierung sofort. "
                f"{msg}"
            )
        if alert.severity == "warning":
            return (
                f"'{alert.name}' hat sich geändert. "
                f"Hash {alert.stored_hash[:8] if alert.stored_hash else '?'} → "
                f"{alert.current_hash[:8] if alert.current_hash else '?'}. "
                f"{msg}"
            )
        if alert.status.value == "missing":
            return f"'{alert.name}' wurde in der Registry gefunden, aber die Datei fehlt. {msg}"
        return msg


# ---------------------------------------------------------------------------
# Convenience function — get the notifier with the global notification engine
# ---------------------------------------------------------------------------

_notifier: Optional[DriftAlertNotifier] = None


def get_drift_alert_notifier(
    channel: NotificationChannel = NotificationChannel.PUSH,
    recipient: str = "",
) -> DriftAlertNotifier:
    global _notifier
    if _notifier is None:
        # Try to use the global notification engine
        try:
            from copilot_core.notifications.engine import get_notification_engine
            engine = get_notification_engine()
        except Exception:
            engine = None
        _notifier = DriftAlertNotifier(engine=engine, channel=channel, recipient=recipient)
    return _notifier


def notify_drift_alerts(alerts: List[Any]) -> List[Notification]:
    """Quick helper to notify about a list of drift alerts."""
    notifier = get_drift_alert_notifier()
    return notifier.notify_batch(alerts)
