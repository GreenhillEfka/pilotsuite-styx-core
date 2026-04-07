"""Brain Activity — Pulse, Sleep & Chat History (v7.5.0).

Tracks the brain's activity state for dashboard visualisation:
- **Active / Pulsing** — processing a request, dispatching events, chatting
- **Idle** — awake but no current work
- **Sleeping** — low-power mode, no polling, minimal resource usage
- **Chat History** — conversation log for the dashboard chat widget

The frontend reads the activity state to animate the brain:
- pulse animation when active
- gentle glow when idle
- dimmed / closed-eyes when sleeping
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────


class BrainState(str, Enum):
    """Activity state of the brain."""

    ACTIVE = "active"      # processing / pulsing
    IDLE = "idle"          # awake, no work
    SLEEPING = "sleeping"  # low-power / resource saving


# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class ChatMessage:
    """A single message in the chat history."""

    message_id: str
    role: str            # "user" or "assistant"
    content: str
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActivityPulse:
    """A recorded activity pulse (brain was active for a reason)."""

    pulse_id: str
    reason: str          # e.g. "chat", "event_dispatch", "api_request", "automation"
    started: str = ""
    ended: str = ""
    duration_ms: int = 0


@dataclass
class BrainActivityStatus:
    """Current brain activity status."""

    state: str = BrainState.IDLE.value
    last_active: str = ""
    last_sleep: str = ""
    total_pulses: int = 0
    total_chat_messages: int = 0
    uptime_seconds: int = 0
    sleep_seconds: int = 0
    idle_timeout_seconds: int = 300
    sleep_timeout_seconds: int = 1800
    recent_pulses: list[dict[str, Any]] = field(default_factory=list)
    recent_chat: list[dict[str, Any]] = field(default_factory=list)


# ── Engine ───────────────────────────────────────────────────────────────────


class BrainActivityEngine:
    """Tracks brain activity state, pulses, and chat history."""

    def __init__(self, idle_timeout: int = 300, sleep_timeout: int = 1800) -> None:
        self._state = BrainState.IDLE
        self._boot_time = datetime.now(tz=timezone.utc)
        self._last_active: datetime | None = None
        self._last_sleep: datetime | None = None
        self._sleep_start: datetime | None = None
        self._total_sleep_seconds = 0

        self._idle_timeout = idle_timeout      # seconds before idle → sleeping
        self._sleep_timeout = sleep_timeout    # max sleep before forced wake

        self._pulses: list[ActivityPulse] = []
        self._pulse_counter = 0
        self._active_pulse: ActivityPulse | None = None

        self._chat_history: list[ChatMessage] = []
        self._chat_counter = 0

    # ── State management ──────────────────────────────────────────────────

    @property
    def state(self) -> BrainState:
        return self._state

    def wake(self) -> str:
        """Wake the brain from sleeping or idle."""
        if self._state == BrainState.SLEEPING and self._sleep_start:
            elapsed = (datetime.now(tz=timezone.utc) - self._sleep_start).total_seconds()
            self._total_sleep_seconds += int(elapsed)
            self._sleep_start = None
        self._state = BrainState.IDLE
        self._last_active = datetime.now(tz=timezone.utc)
        logger.info("Brain: woke up → idle")
        return self._state.value

    def sleep(self) -> str:
        """Put the brain to sleep (resource saving mode)."""
        if self._active_pulse:
            self.end_pulse()
        self._state = BrainState.SLEEPING
        self._last_sleep = datetime.now(tz=timezone.utc)
        self._sleep_start = datetime.now(tz=timezone.utc)
        logger.info("Brain: going to sleep 💤")
        return self._state.value

    def check_idle(self) -> str:
        """Check if brain should transition to sleeping based on idle timeout.

        Returns the current state after check.
        """
        if self._state != BrainState.IDLE:
            return self._state.value

        if self._last_active:
            elapsed = (datetime.now(tz=timezone.utc) - self._last_active).total_seconds()
            if elapsed >= self._idle_timeout:
                self.sleep()
        return self._state.value

    # ── Pulse tracking ────────────────────────────────────────────────────

    def start_pulse(self, reason: str = "api_request") -> ActivityPulse:
        """Start a new activity pulse — brain becomes active."""
        if self._state == BrainState.SLEEPING:
            self.wake()

        self._state = BrainState.ACTIVE
        self._last_active = datetime.now(tz=timezone.utc)
        self._pulse_counter += 1

        pulse = ActivityPulse(
            pulse_id=f"pulse_{self._pulse_counter:05d}",
            reason=reason,
            started=datetime.now(tz=timezone.utc).isoformat(),
        )
        self._active_pulse = pulse
        return pulse

    def end_pulse(self) -> ActivityPulse | None:
        """End the current pulse — brain returns to idle."""
        if not self._active_pulse:
            return None

        pulse = self._active_pulse
        now = datetime.now(tz=timezone.utc)
        pulse.ended = now.isoformat()

        start_dt = datetime.fromisoformat(pulse.started)
        pulse.duration_ms = int((now - start_dt).total_seconds() * 1000)

        self._pulses.append(pulse)
        self._pulses = self._pulses[-500:]  # cap history
        self._active_pulse = None
        self._state = BrainState.IDLE
        self._last_active = now
        return pulse

    def get_recent_pulses(self, limit: int = 10) -> list[ActivityPulse]:
        return list(reversed(self._pulses[-limit:]))

    # ── Chat history ──────────────────────────────────────────────────────

    def add_chat_message(self, role: str, content: str,
                         metadata: dict[str, Any] | None = None) -> ChatMessage:
        """Add a message to the chat history. Auto-pulses when assistant responds."""
        self._chat_counter += 1
        msg = ChatMessage(
            message_id=f"msg_{self._chat_counter:05d}",
            role=role,
            content=content,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        self._chat_history.append(msg)
        self._chat_history = self._chat_history[-200:]  # cap

        # Auto-pulse on assistant message
        if role == "assistant":
            pulse = self.start_pulse(reason="chat")
            self.end_pulse()

        # Keep brain awake on any chat activity
        if self._state == BrainState.SLEEPING:
            self.wake()
        self._last_active = datetime.now(tz=timezone.utc)

        return msg

    def get_chat_history(self, limit: int = 50) -> list[ChatMessage]:
        return list(reversed(self._chat_history[-limit:]))

    def clear_chat_history(self) -> int:
        count = len(self._chat_history)
        self._chat_history.clear()
        return count

    # ── Configuration ─────────────────────────────────────────────────────

    def set_idle_timeout(self, seconds: int) -> int:
        self._idle_timeout = max(30, min(3600, seconds))
        return self._idle_timeout

    def set_sleep_timeout(self, seconds: int) -> int:
        self._sleep_timeout = max(60, min(86400, seconds))
        return self._sleep_timeout

    # ── Status ────────────────────────────────────────────────────────────

    def get_status(self) -> BrainActivityStatus:
        now = datetime.now(tz=timezone.utc)
        uptime = int((now - self._boot_time).total_seconds())

        sleep_secs = self._total_sleep_seconds
        if self._state == BrainState.SLEEPING and self._sleep_start:
            sleep_secs += int((now - self._sleep_start).total_seconds())

        recent_pulses = [
            {
                "pulse_id": p.pulse_id,
                "reason": p.reason,
                "started": p.started,
                "duration_ms": p.duration_ms,
            }
            for p in self.get_recent_pulses(5)
        ]

        recent_chat = [
            {
                "message_id": m.message_id,
                "role": m.role,
                "content": m.content[:200],
                "timestamp": m.timestamp,
            }
            for m in self.get_chat_history(5)
        ]

        return BrainActivityStatus(
            state=self._state.value,
            last_active=self._last_active.isoformat() if self._last_active else "",
            last_sleep=self._last_sleep.isoformat() if self._last_sleep else "",
            total_pulses=len(self._pulses),
            total_chat_messages=len(self._chat_history),
            uptime_seconds=uptime,
            sleep_seconds=sleep_secs,
            idle_timeout_seconds=self._idle_timeout,
            sleep_timeout_seconds=self._sleep_timeout,
            recent_pulses=recent_pulses,
            recent_chat=recent_chat,
        )

    def get_dashboard(self) -> dict[str, Any]:
        """Full activity dashboard for API."""
        status = self.get_status()
        return {
            "ok": True,
            "state": status.state,
            "last_active": status.last_active,
            "last_sleep": status.last_sleep,
            "total_pulses": status.total_pulses,
            "total_chat_messages": status.total_chat_messages,
            "uptime_seconds": status.uptime_seconds,
            "sleep_seconds": status.sleep_seconds,
            "idle_timeout_seconds": status.idle_timeout_seconds,
            "sleep_timeout_seconds": status.sleep_timeout_seconds,
            "recent_pulses": status.recent_pulses,
            "recent_chat": status.recent_chat,
        }
