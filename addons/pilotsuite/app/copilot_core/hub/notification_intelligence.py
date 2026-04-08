"""Notification Intelligence — Smart Benachrichtigungs-Steuerung (v7.2.0).

Features:
- Smart notification routing based on context (location, time, activity)
- Priority system (critical, high, normal, low, info) with escalation
- Do-Not-Disturb integration per person and zone mode
- Notification batching with configurable digest intervals
- Multi-channel delivery (push, tts, display, email, telegram)
- Notification history with read/unread tracking
- Quiet hours with critical override
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Enums ───────────────────────────────────────────────────────────────────


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    INFO = "info"


class Channel(str, Enum):
    PUSH = "push"
    TTS = "tts"
    DISPLAY = "display"
    EMAIL = "email"
    TELEGRAM = "telegram"


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class Notification:
    """A notification."""

    notification_id: str
    title: str
    message: str
    priority: Priority = Priority.NORMAL
    channel: Channel = Channel.PUSH
    category: str = "general"
    person_id: str = ""
    zone_id: str = ""
    icon: str = "mdi:bell"
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    delivered: bool = False
    read: bool = False
    batched: bool = False
    suppressed: bool = False
    suppression_reason: str = ""


@dataclass
class NotificationRule:
    """A routing rule for notifications."""

    rule_id: str
    name_de: str
    category: str = ""
    priority_min: Priority = Priority.LOW
    channel: Channel = Channel.PUSH
    person_id: str = ""
    zone_id: str = ""
    active: bool = True
    quiet_hours_start: int | None = None  # hour 0-23
    quiet_hours_end: int | None = None


@dataclass
class DndConfig:
    """Do-Not-Disturb configuration."""

    enabled: bool = False
    allow_critical: bool = True
    person_id: str = ""
    zone_mode: str = ""
    until: datetime | None = None


@dataclass
class BatchConfig:
    """Notification batching configuration."""

    enabled: bool = False
    interval_min: int = 15
    max_batch_size: int = 10
    categories: list[str] = field(default_factory=list)


@dataclass
class NotificationStats:
    """Notification statistics."""

    total_sent: int = 0
    total_suppressed: int = 0
    total_batched: int = 0
    unread_count: int = 0
    by_priority: dict[str, int] = field(default_factory=dict)
    by_channel: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)


@dataclass
class NotificationIntelligenceDashboard:
    """Notification intelligence dashboard."""

    total_notifications: int = 0
    unread_count: int = 0
    dnd_active: bool = False
    batch_pending: int = 0
    stats: dict[str, Any] = field(default_factory=dict)
    recent: list[dict[str, Any]] = field(default_factory=list)
    rules_count: int = 0
    channels_active: list[str] = field(default_factory=list)


# ── Priority order ──────────────────────────────────────────────────────────

_PRIORITY_ORDER = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.NORMAL: 2,
    Priority.LOW: 3,
    Priority.INFO: 4,
}


# ── Engine ──────────────────────────────────────────────────────────────────


class NotificationIntelligenceEngine:
    """Engine for intelligent notification routing and delivery."""

    def __init__(self) -> None:
        self._notifications: list[Notification] = []
        self._rules: dict[str, NotificationRule] = {}
        self._dnd_configs: list[DndConfig] = []
        self._batch_config = BatchConfig()
        self._batch_queue: list[Notification] = []
        self._id_counter = 0

    # ── Send / Create ─────────────────────────────────────────────────────

    def send(self, title: str, message: str, priority: str = "normal",
             channel: str = "push", category: str = "general",
             person_id: str = "", zone_id: str = "",
             icon: str = "mdi:bell") -> Notification:
        """Send a notification (or queue if batched/suppressed)."""
        self._id_counter += 1
        nid = f"notif_{self._id_counter}"

        notif = Notification(
            notification_id=nid,
            title=title,
            message=message,
            priority=Priority(priority),
            channel=Channel(channel),
            category=category,
            person_id=person_id,
            zone_id=zone_id,
            icon=icon,
        )

        # Check DND
        if self._is_dnd_active(person_id, notif.priority):
            notif.suppressed = True
            notif.suppression_reason = "DND aktiv"
            self._notifications.append(notif)
            self._notifications = self._notifications[-500:]
            return notif

        # Check quiet hours from rules
        if self._is_quiet_hours(category, notif.priority):
            notif.suppressed = True
            notif.suppression_reason = "Ruhezeit"
            self._notifications.append(notif)
            self._notifications = self._notifications[-500:]
            return notif

        # Apply routing rules
        notif = self._apply_rules(notif)

        # Check batching
        if self._should_batch(notif):
            notif.batched = True
            self._batch_queue.append(notif)
            self._notifications.append(notif)
            self._notifications = self._notifications[-500:]
            return notif

        # Deliver
        notif.delivered = True
        self._notifications.append(notif)
        self._notifications = self._notifications[-500:]
        logger.info("Notification delivered: %s [%s] via %s", nid, notif.priority.value, notif.channel.value)
        return notif

    def _apply_rules(self, notif: Notification) -> Notification:
        """Apply routing rules to determine channel."""
        for rule in self._rules.values():
            if not rule.active:
                continue
            if rule.category and rule.category != notif.category:
                continue
            if rule.person_id and rule.person_id != notif.person_id:
                continue
            if _PRIORITY_ORDER.get(notif.priority, 4) > _PRIORITY_ORDER.get(rule.priority_min, 4):
                continue
            notif.channel = rule.channel
            if rule.zone_id:
                notif.zone_id = rule.zone_id
            break
        return notif

    def _is_dnd_active(self, person_id: str, priority: Priority) -> bool:
        """Check if DND is active for person/globally."""
        now = datetime.now(tz=timezone.utc)
        for dnd in self._dnd_configs:
            if not dnd.enabled:
                continue
            if dnd.until and now > dnd.until:
                dnd.enabled = False
                continue
            if dnd.person_id and dnd.person_id != person_id:
                continue
            if dnd.allow_critical and priority == Priority.CRITICAL:
                continue
            return True
        return False

    def _is_quiet_hours(self, category: str, priority: Priority) -> bool:
        """Check quiet hours from rules."""
        if priority == Priority.CRITICAL:
            return False
        now = datetime.now(tz=timezone.utc)
        hour = now.hour
        for rule in self._rules.values():
            if not rule.active:
                continue
            if rule.category and rule.category != category:
                continue
            if rule.quiet_hours_start is not None and rule.quiet_hours_end is not None:
                start, end = rule.quiet_hours_start, rule.quiet_hours_end
                if start <= end:
                    if start <= hour < end:
                        return True
                else:  # wraps midnight
                    if hour >= start or hour < end:
                        return True
        return False

    def _should_batch(self, notif: Notification) -> bool:
        """Check if notification should be batched."""
        if not self._batch_config.enabled:
            return False
        if notif.priority in (Priority.CRITICAL, Priority.HIGH):
            return False
        if self._batch_config.categories and notif.category not in self._batch_config.categories:
            return False
        return True

    # ── Batch processing ──────────────────────────────────────────────────

    def flush_batch(self) -> list[Notification]:
        """Deliver all batched notifications."""
        delivered = []
        for notif in self._batch_queue:
            notif.delivered = True
            notif.batched = False
            delivered.append(notif)
        self._batch_queue.clear()
        return delivered

    def configure_batching(self, enabled: bool = False, interval_min: int = 15,
                           max_batch_size: int = 10,
                           categories: list[str] | None = None) -> BatchConfig:
        """Configure notification batching."""
        self._batch_config.enabled = enabled
        self._batch_config.interval_min = interval_min
        self._batch_config.max_batch_size = max_batch_size
        if categories is not None:
            self._batch_config.categories = categories
        return self._batch_config

    # ── DND ───────────────────────────────────────────────────────────────

    def set_dnd(self, enabled: bool = True, person_id: str = "",
                allow_critical: bool = True, duration_min: int = 0,
                zone_mode: str = "") -> DndConfig:
        """Set Do-Not-Disturb."""
        until = None
        if duration_min > 0:
            until = datetime.now(tz=timezone.utc) + timedelta(minutes=duration_min)

        # Update or create
        for dnd in self._dnd_configs:
            if dnd.person_id == person_id:
                dnd.enabled = enabled
                dnd.allow_critical = allow_critical
                dnd.until = until
                dnd.zone_mode = zone_mode
                return dnd

        dnd = DndConfig(
            enabled=enabled,
            allow_critical=allow_critical,
            person_id=person_id,
            zone_mode=zone_mode,
            until=until,
        )
        self._dnd_configs.append(dnd)
        return dnd

    def get_dnd_status(self) -> list[dict[str, Any]]:
        """Get current DND status."""
        return [
            {
                "enabled": d.enabled,
                "person_id": d.person_id,
                "allow_critical": d.allow_critical,
                "zone_mode": d.zone_mode,
                "until": d.until.isoformat() if d.until else None,
            }
            for d in self._dnd_configs
        ]

    # ── Rules ─────────────────────────────────────────────────────────────

    def add_rule(self, rule_id: str, name_de: str, category: str = "",
                 priority_min: str = "low", channel: str = "push",
                 person_id: str = "", zone_id: str = "",
                 quiet_hours_start: int | None = None,
                 quiet_hours_end: int | None = None) -> bool:
        """Add a notification routing rule."""
        if rule_id in self._rules:
            return False
        self._rules[rule_id] = NotificationRule(
            rule_id=rule_id,
            name_de=name_de,
            category=category,
            priority_min=Priority(priority_min),
            channel=Channel(channel),
            person_id=person_id,
            zone_id=zone_id,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
        )
        return True

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a routing rule."""
        if rule_id not in self._rules:
            return False
        del self._rules[rule_id]
        return True

    def get_rules(self) -> list[dict[str, Any]]:
        """Get all routing rules."""
        return [
            {
                "rule_id": r.rule_id,
                "name_de": r.name_de,
                "category": r.category,
                "priority_min": r.priority_min.value,
                "channel": r.channel.value,
                "active": r.active,
                "quiet_hours_start": r.quiet_hours_start,
                "quiet_hours_end": r.quiet_hours_end,
            }
            for r in self._rules.values()
        ]

    # ── Read / History ────────────────────────────────────────────────────

    def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        for n in self._notifications:
            if n.notification_id == notification_id:
                n.read = True
                return True
        return False

    def mark_all_read(self) -> int:
        """Mark all unread notifications as read."""
        count = 0
        for n in self._notifications:
            if not n.read:
                n.read = True
                count += 1
        return count

    def get_history(self, limit: int = 50, unread_only: bool = False,
                    category: str = "") -> list[dict[str, Any]]:
        """Get notification history."""
        notifs = list(reversed(self._notifications))
        if unread_only:
            notifs = [n for n in notifs if not n.read]
        if category:
            notifs = [n for n in notifs if n.category == category]
        return [
            {
                "notification_id": n.notification_id,
                "title": n.title,
                "message": n.message,
                "priority": n.priority.value,
                "channel": n.channel.value,
                "category": n.category,
                "icon": n.icon,
                "created_at": n.created_at.isoformat(),
                "delivered": n.delivered,
                "read": n.read,
                "suppressed": n.suppressed,
                "suppression_reason": n.suppression_reason,
            }
            for n in notifs[:limit]
        ]

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> NotificationStats:
        """Get notification statistics."""
        by_priority: dict[str, int] = defaultdict(int)
        by_channel: dict[str, int] = defaultdict(int)
        by_category: dict[str, int] = defaultdict(int)
        sent = suppressed = batched = unread = 0

        for n in self._notifications:
            by_priority[n.priority.value] += 1
            by_channel[n.channel.value] += 1
            by_category[n.category] += 1
            if n.delivered:
                sent += 1
            if n.suppressed:
                suppressed += 1
            if n.batched:
                batched += 1
            if not n.read:
                unread += 1

        return NotificationStats(
            total_sent=sent,
            total_suppressed=suppressed,
            total_batched=batched,
            unread_count=unread,
            by_priority=dict(by_priority),
            by_channel=dict(by_channel),
            by_category=dict(by_category),
        )

    # ── Dashboard ─────────────────────────────────────────────────────────

    def get_dashboard(self) -> NotificationIntelligenceDashboard:
        """Get notification intelligence dashboard."""
        stats = self.get_stats()
        dnd_active = any(d.enabled for d in self._dnd_configs)
        channels = list({r.channel.value for r in self._rules.values() if r.active})

        recent = self.get_history(limit=5)

        return NotificationIntelligenceDashboard(
            total_notifications=len(self._notifications),
            unread_count=stats.unread_count,
            dnd_active=dnd_active,
            batch_pending=len(self._batch_queue),
            stats={
                "total_sent": stats.total_sent,
                "total_suppressed": stats.total_suppressed,
                "by_priority": stats.by_priority,
                "by_channel": stats.by_channel,
            },
            recent=recent,
            rules_count=len(self._rules),
            channels_active=channels or ["push"],
        )
