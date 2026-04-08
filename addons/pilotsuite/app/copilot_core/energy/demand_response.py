"""Demand Response Manager — Grid signal response & load curtailment (v5.14.0).

Manages household energy consumption in response to grid operator signals,
dynamic tariff events, and self-defined peak rules.

Features:
- Register grid signals (peak warning, curtailment request, price spike)
- Automatic load shedding priority list
- Device curtailment with restore scheduling
- Event history and response metrics
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Optional


# ── Enums & Data ────────────────────────────────────────────────────────────

class SignalLevel(IntEnum):
    """Grid signal severity."""

    NORMAL = 0
    ADVISORY = 1  # informational — consider reducing
    MODERATE = 2  # reduce non-essential loads
    CRITICAL = 3  # shed all deferrable loads immediately


class DevicePriority(IntEnum):
    """Load shedding priority (lower = shed first)."""

    DEFERRABLE = 1  # pool pump, dryer, washer
    FLEXIBLE = 2    # EV charger, dishwasher
    COMFORT = 3     # AC, heat pump (reduce, don't cut)
    ESSENTIAL = 4   # fridge, lights, network — never shed


@dataclass
class ManagedDevice:
    """Device registered for demand response."""

    device_id: str
    device_name: str
    priority: int  # DevicePriority value
    max_watts: float
    current_watts: float = 0.0
    is_curtailed: bool = False
    curtailed_at: str = ""
    auto_restore_minutes: int = 60


@dataclass
class GridSignal:
    """Incoming grid signal event."""

    signal_id: str
    level: int  # SignalLevel value
    source: str  # "grid_operator", "tariff", "self"
    reason: str
    target_reduction_watts: float
    received_at: str
    expires_at: str
    active: bool = True


@dataclass
class CurtailmentAction:
    """Record of a curtailment action taken."""

    action_id: str
    signal_id: str
    device_id: str
    device_name: str
    action: str  # "curtail", "reduce", "restore"
    watts_affected: float
    timestamp: str
    auto_restore_at: str


@dataclass
class DemandResponseStatus:
    """Current demand response system status."""

    current_signal: int  # SignalLevel
    active_signals: int
    managed_devices: int
    curtailed_devices: int
    total_reduction_watts: float
    response_active: bool


# ── Constants ───────────────────────────────────────────────────────────────

MAX_HISTORY = 200
DEFAULT_RESTORE_MINUTES = 60


# ── Manager ─────────────────────────────────────────────────────────────────

class DemandResponseManager:
    """Manages demand response for the household."""

    def __init__(self) -> None:
        self._devices: dict[str, ManagedDevice] = {}
        self._signals: dict[str, GridSignal] = {}
        self._actions: deque[CurtailmentAction] = deque(maxlen=MAX_HISTORY)
        self._lock = threading.Lock()
        self._action_counter = 0

    # ── Device registration ─────────────────────────────────────────────

    def register_device(
        self,
        device_id: str,
        device_name: str,
        priority: int = DevicePriority.FLEXIBLE,
        max_watts: float = 1000.0,
        auto_restore_minutes: int = DEFAULT_RESTORE_MINUTES,
    ) -> ManagedDevice:
        """Register a device for demand response management."""
        with self._lock:
            dev = ManagedDevice(
                device_id=device_id,
                device_name=device_name,
                priority=priority,
                max_watts=max_watts,
                auto_restore_minutes=auto_restore_minutes,
            )
            self._devices[device_id] = dev
            return dev

    def unregister_device(self, device_id: str) -> bool:
        """Remove a device from demand response."""
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                return True
            return False

    def get_devices(self) -> list[dict]:
        """Get all managed devices."""
        with self._lock:
            return [asdict(d) for d in self._devices.values()]

    def update_device_power(self, device_id: str, current_watts: float) -> bool:
        """Update current power draw for a device."""
        with self._lock:
            dev = self._devices.get(device_id)
            if dev:
                dev.current_watts = current_watts
                return True
            return False

    # ── Signal handling ─────────────────────────────────────────────────

    def receive_signal(
        self,
        level: int,
        source: str = "grid_operator",
        reason: str = "",
        target_reduction_watts: float = 0.0,
        duration_minutes: int = 60,
    ) -> GridSignal:
        """Receive and process a grid signal.

        Automatically triggers load curtailment based on signal level.
        """
        now = datetime.now()
        signal_id = f"sig_{now.strftime('%Y%m%d_%H%M%S')}_{level}"

        signal = GridSignal(
            signal_id=signal_id,
            level=level,
            source=source,
            reason=reason,
            target_reduction_watts=target_reduction_watts,
            received_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=duration_minutes)).isoformat(),
        )

        with self._lock:
            self._signals[signal_id] = signal

        # Auto-respond based on level
        if level >= SignalLevel.MODERATE:
            self._auto_curtail(signal)

        return signal

    def cancel_signal(self, signal_id: str) -> bool:
        """Cancel an active signal and restore devices."""
        with self._lock:
            signal = self._signals.get(signal_id)
            if signal and signal.active:
                signal.active = False
                self._restore_all()
                return True
            return False

    def get_active_signals(self) -> list[dict]:
        """Get currently active signals."""
        now = datetime.now().isoformat()
        with self._lock:
            active = []
            for s in self._signals.values():
                if s.active and s.expires_at > now:
                    active.append(asdict(s))
                elif s.active and s.expires_at <= now:
                    s.active = False
            return active

    # ── Curtailment ─────────────────────────────────────────────────────

    def curtail_device(self, device_id: str, signal_id: str = "manual") -> Optional[CurtailmentAction]:
        """Manually curtail a specific device."""
        with self._lock:
            dev = self._devices.get(device_id)
            if not dev or dev.is_curtailed:
                return None

            now = datetime.now()
            restore_at = now + timedelta(minutes=dev.auto_restore_minutes)

            dev.is_curtailed = True
            dev.curtailed_at = now.isoformat()

            self._action_counter += 1
            action = CurtailmentAction(
                action_id=f"act_{self._action_counter}",
                signal_id=signal_id,
                device_id=device_id,
                device_name=dev.device_name,
                action="curtail",
                watts_affected=dev.current_watts or dev.max_watts,
                timestamp=now.isoformat(),
                auto_restore_at=restore_at.isoformat(),
            )
            self._actions.append(action)
            return action

    def restore_device(self, device_id: str) -> Optional[CurtailmentAction]:
        """Restore a curtailed device."""
        with self._lock:
            dev = self._devices.get(device_id)
            if not dev or not dev.is_curtailed:
                return None

            now = datetime.now()
            dev.is_curtailed = False
            dev.curtailed_at = ""

            self._action_counter += 1
            action = CurtailmentAction(
                action_id=f"act_{self._action_counter}",
                signal_id="restore",
                device_id=device_id,
                device_name=dev.device_name,
                action="restore",
                watts_affected=dev.max_watts,
                timestamp=now.isoformat(),
                auto_restore_at="",
            )
            self._actions.append(action)
            return action

    def get_curtailed_devices(self) -> list[dict]:
        """Get currently curtailed devices."""
        with self._lock:
            return [asdict(d) for d in self._devices.values() if d.is_curtailed]

    # ── Status & metrics ────────────────────────────────────────────────

    def get_status(self) -> DemandResponseStatus:
        """Get current demand response status."""
        now = datetime.now().isoformat()
        with self._lock:
            active_signals = [
                s for s in self._signals.values()
                if s.active and s.expires_at > now
            ]
            max_level = max((s.level for s in active_signals), default=0)
            curtailed = [d for d in self._devices.values() if d.is_curtailed]
            total_reduction = sum(
                d.current_watts or d.max_watts for d in curtailed
            )

            return DemandResponseStatus(
                current_signal=max_level,
                active_signals=len(active_signals),
                managed_devices=len(self._devices),
                curtailed_devices=len(curtailed),
                total_reduction_watts=round(total_reduction, 0),
                response_active=len(curtailed) > 0,
            )

    def get_action_history(self, limit: int = 50) -> list[dict]:
        """Get recent curtailment actions."""
        with self._lock:
            actions = list(self._actions)
            actions.reverse()
            return [asdict(a) for a in actions[:limit]]

    def get_metrics(self) -> dict:
        """Get demand response performance metrics."""
        with self._lock:
            total_actions = len(self._actions)
            curtail_actions = sum(1 for a in self._actions if a.action == "curtail")
            restore_actions = sum(1 for a in self._actions if a.action == "restore")
            total_watts_curtailed = sum(
                a.watts_affected for a in self._actions if a.action == "curtail"
            )
            signals_received = len(self._signals)

            return {
                "total_actions": total_actions,
                "curtail_actions": curtail_actions,
                "restore_actions": restore_actions,
                "total_watts_curtailed": round(total_watts_curtailed, 0),
                "signals_received": signals_received,
                "managed_devices": len(self._devices),
            }

    # ── Internal ────────────────────────────────────────────────────────

    def _auto_curtail(self, signal: GridSignal) -> None:
        """Automatically curtail devices based on signal level."""
        now = datetime.now()
        target = signal.target_reduction_watts
        reduced = 0.0

        # Sort devices by priority (lowest priority = shed first)
        with self._lock:
            devices_sorted = sorted(
                self._devices.values(),
                key=lambda d: d.priority,
            )

        for dev in devices_sorted:
            if dev.is_curtailed:
                continue
            if dev.priority >= DevicePriority.ESSENTIAL:
                continue  # Never shed essential devices

            # For CRITICAL signals, shed everything up to COMFORT
            if signal.level >= SignalLevel.CRITICAL:
                if dev.priority <= DevicePriority.COMFORT:
                    self.curtail_device(dev.device_id, signal.signal_id)
                    reduced += dev.current_watts or dev.max_watts
            # For MODERATE, shed DEFERRABLE and FLEXIBLE only
            elif signal.level >= SignalLevel.MODERATE:
                if dev.priority <= DevicePriority.FLEXIBLE:
                    self.curtail_device(dev.device_id, signal.signal_id)
                    reduced += dev.current_watts or dev.max_watts

            if target > 0 and reduced >= target:
                break

    def _restore_all(self) -> None:
        """Restore all curtailed devices (called when signal cancelled)."""
        for dev in list(self._devices.values()):
            if dev.is_curtailed:
                dev.is_curtailed = False
                dev.curtailed_at = ""
                self._action_counter += 1
                self._actions.append(CurtailmentAction(
                    action_id=f"act_{self._action_counter}",
                    signal_id="signal_cancelled",
                    device_id=dev.device_id,
                    device_name=dev.device_name,
                    action="restore",
                    watts_affected=dev.max_watts,
                    timestamp=datetime.now().isoformat(),
                    auto_restore_at="",
                ))
