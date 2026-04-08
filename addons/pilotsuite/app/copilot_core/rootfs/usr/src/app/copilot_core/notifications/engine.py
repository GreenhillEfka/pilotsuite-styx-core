"""Notification Engine — Smart alert aggregation and routing (v5.8.0).

Centralizes notifications from all PilotSuite modules (energy anomalies,
schedule reminders, comfort alerts, weather warnings) with:
- Priority levels (critical, high, normal, low)
- Deduplication within configurable time windows
- Rate limiting per channel
- Digest mode: batch low-priority alerts into periodic summaries
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Notification priority levels."""

    CRITICAL = 1  # Immediate — safety issues, very high anomalies
    HIGH = 2  # Soon — significant anomalies, schedule conflicts
    NORMAL = 3  # Standard — schedule reminders, comfort suggestions
    LOW = 4  # Digest — informational, tips, minor improvements


@dataclass
class Notification:
    """Single notification."""

    id: str
    source: str  # Module: energy, comfort, schedule, weather, system
    title: str
    message: str
    priority: Priority
    created_at: str
    dedup_key: str | None = None  # For deduplication
    data: dict[str, Any] = field(default_factory=dict)
    delivered: bool = False
    delivered_at: str | None = None
    channel: str = "default"  # Routing target


@dataclass
class NotificationDigest:
    """Batched notification summary."""

    period_start: str
    period_end: str
    count: int
    by_source: dict[str, int]
    by_priority: dict[str, int]
    items: list[dict[str, Any]]


# Default configuration
DEFAULT_DEDUP_WINDOW_SECONDS = 600  # 10 minutes
DEFAULT_RATE_LIMIT_PER_HOUR = 20
DEFAULT_DIGEST_INTERVAL_MINUTES = 60
MAX_HISTORY_SIZE = 500


class NotificationEngine:
    """Central notification hub for PilotSuite.

    Features:
    - Deduplication: identical alerts within a time window are merged
    - Rate limiting: max N notifications per hour per channel
    - Priority routing: CRITICAL bypasses rate limits
    - Digest mode: LOW priority batched into periodic summaries
    - History: recent notifications stored for API queries
    """

    def __init__(
        self,
        dedup_window_seconds: int = DEFAULT_DEDUP_WINDOW_SECONDS,
        rate_limit_per_hour: int = DEFAULT_RATE_LIMIT_PER_HOUR,
        digest_interval_minutes: int = DEFAULT_DIGEST_INTERVAL_MINUTES,
    ):
        self._lock = threading.Lock()
        self._dedup_window = timedelta(seconds=dedup_window_seconds)
        self._rate_limit = rate_limit_per_hour
        self._digest_interval = timedelta(minutes=digest_interval_minutes)

        # State
        self._history: deque[Notification] = deque(maxlen=MAX_HISTORY_SIZE)
        self._dedup_cache: dict[str, datetime] = {}  # dedup_key -> last_sent
        self._rate_counters: dict[str, list[datetime]] = {}  # channel -> timestamps
        self._digest_buffer: list[Notification] = []
        self._last_digest: datetime = datetime.now(timezone.utc)
        self._pending: deque[Notification] = deque(maxlen=100)

        # Callbacks for delivery
        self._handlers: dict[str, Any] = {}  # channel -> callable

        self._counter = 0
        logger.info("NotificationEngine initialized (dedup=%ds, rate=%d/h)",
                     dedup_window_seconds, rate_limit_per_hour)

    def register_handler(self, channel: str, handler) -> None:
        """Register a delivery handler for a channel."""
        self._handlers[channel] = handler
        logger.info("Registered notification handler for channel: %s", channel)

    def notify(
        self,
        source: str,
        title: str,
        message: str,
        priority: Priority | int = Priority.NORMAL,
        dedup_key: str | None = None,
        data: dict[str, Any] | None = None,
        channel: str = "default",
    ) -> Notification | None:
        """Submit a notification.

        Returns the Notification if accepted, None if deduplicated/rate-limited.
        """
        if isinstance(priority, int) and not isinstance(priority, Priority):
            try:
                priority = Priority(priority)
            except ValueError:
                priority = Priority.NORMAL

        now = datetime.now(timezone.utc)

        # Generate dedup key if not provided
        if dedup_key is None:
            dedup_key = self._make_dedup_key(source, title, message)

        with self._lock:
            # Dedup check (CRITICAL bypasses)
            if priority != Priority.CRITICAL and self._is_duplicate(dedup_key, now):
                logger.debug("Deduplicated notification: %s", dedup_key[:20])
                return None

            # Rate limit check (CRITICAL bypasses)
            if priority != Priority.CRITICAL and self._is_rate_limited(channel, now):
                logger.debug("Rate limited notification on channel: %s", channel)
                return None

            # Create notification
            self._counter += 1
            notif = Notification(
                id=f"n-{now.strftime('%Y%m%d%H%M%S')}-{self._counter:04d}",
                source=source,
                title=title,
                message=message,
                priority=priority,
                created_at=now.isoformat(timespec="seconds"),
                dedup_key=dedup_key,
                data=data or {},
                channel=channel,
            )

            # Update dedup cache
            self._dedup_cache[dedup_key] = now

            # Update rate counter
            if channel not in self._rate_counters:
                self._rate_counters[channel] = []
            self._rate_counters[channel].append(now)

            # Route by priority
            if priority == Priority.LOW:
                self._digest_buffer.append(notif)
            else:
                self._pending.append(notif)

            self._history.append(notif)

        return notif

    def flush_pending(self) -> list[Notification]:
        """Get and clear pending notifications for delivery."""
        with self._lock:
            pending = list(self._pending)
            self._pending.clear()

            # Check if digest is due
            now = datetime.now(timezone.utc)
            if now - self._last_digest >= self._digest_interval and self._digest_buffer:
                digest_notif = self._create_digest_notification(now)
                if digest_notif:
                    pending.append(digest_notif)
                self._digest_buffer.clear()
                self._last_digest = now

        return pending

    def get_digest(self, hours: float = 24.0) -> NotificationDigest:
        """Get notification digest for the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        with self._lock:
            recent = [
                n for n in self._history
                if datetime.fromisoformat(n.created_at) >= cutoff
            ]

        by_source: dict[str, int] = {}
        by_priority: dict[str, int] = {}

        for n in recent:
            by_source[n.source] = by_source.get(n.source, 0) + 1
            pname = n.priority.name if isinstance(n.priority, Priority) else str(n.priority)
            by_priority[pname] = by_priority.get(pname, 0) + 1

        now = datetime.now(timezone.utc)
        return NotificationDigest(
            period_start=(now - timedelta(hours=hours)).isoformat(timespec="seconds"),
            period_end=now.isoformat(timespec="seconds"),
            count=len(recent),
            by_source=by_source,
            by_priority=by_priority,
            items=[
                {
                    "id": n.id,
                    "source": n.source,
                    "title": n.title,
                    "message": n.message,
                    "priority": n.priority.name if isinstance(n.priority, Priority) else str(n.priority),
                    "created_at": n.created_at,
                    "channel": n.channel,
                }
                for n in recent
            ],
        )

    def get_history(self, limit: int = 50, source: str | None = None) -> list[dict[str, Any]]:
        """Get recent notification history."""
        with self._lock:
            items = list(self._history)

        if source:
            items = [n for n in items if n.source == source]

        items = items[-limit:]
        items.reverse()

        return [
            {
                "id": n.id,
                "source": n.source,
                "title": n.title,
                "message": n.message,
                "priority": n.priority.name if isinstance(n.priority, Priority) else str(n.priority),
                "created_at": n.created_at,
                "channel": n.channel,
                "delivered": n.delivered,
            }
            for n in items
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        with self._lock:
            return {
                "total_notifications": len(self._history),
                "pending_count": len(self._pending),
                "digest_buffer_count": len(self._digest_buffer),
                "dedup_cache_size": len(self._dedup_cache),
                "channels": list(self._handlers.keys()),
                "rate_limit_per_hour": self._rate_limit,
                "dedup_window_seconds": int(self._dedup_window.total_seconds()),
            }

    def clear_history(self) -> None:
        """Clear all notification history."""
        with self._lock:
            self._history.clear()
            self._dedup_cache.clear()
            self._rate_counters.clear()
            self._digest_buffer.clear()
            self._pending.clear()
            self._counter = 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_duplicate(self, dedup_key: str, now: datetime) -> bool:
        """Check if notification was recently sent."""
        last = self._dedup_cache.get(dedup_key)
        if last and (now - last) < self._dedup_window:
            return True
        # Clean expired entries
        expired = [k for k, v in self._dedup_cache.items() if (now - v) > self._dedup_window]
        for k in expired:
            del self._dedup_cache[k]
        return False

    def _is_rate_limited(self, channel: str, now: datetime) -> bool:
        """Check if channel is rate limited."""
        timestamps = self._rate_counters.get(channel, [])
        cutoff = now - timedelta(hours=1)
        # Clean old entries
        timestamps = [t for t in timestamps if t > cutoff]
        self._rate_counters[channel] = timestamps
        return len(timestamps) >= self._rate_limit

    @staticmethod
    def _make_dedup_key(source: str, title: str, message: str) -> str:
        """Generate dedup key from content."""
        raw = f"{source}:{title}:{message}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _create_digest_notification(self, now: datetime) -> Notification | None:
        """Create a digest summary notification from buffered low-priority items."""
        if not self._digest_buffer:
            return None

        count = len(self._digest_buffer)
        sources = {}
        for n in self._digest_buffer:
            sources[n.source] = sources.get(n.source, 0) + 1

        source_summary = ", ".join(f"{s}: {c}" for s, c in sources.items())

        self._counter += 1
        return Notification(
            id=f"digest-{now.strftime('%Y%m%d%H%M%S')}-{self._counter:04d}",
            source="system",
            title=f"Zusammenfassung: {count} Hinweise",
            message=f"In der letzten Stunde: {source_summary}",
            priority=Priority.LOW,
            created_at=now.isoformat(timespec="seconds"),
            dedup_key=f"digest-{now.strftime('%Y%m%d%H')}",
            data={"digest_count": count, "by_source": sources},
            channel="default",
        )
