"""Musikwolke ↔ Sonnenwecker Integration Service.

Automatically pauses Musikwolke when sleep mode activates,
and resumes playback after wake-up.

Integration Points:
- Listens to alarm events (sleep/wake triggers)
- Controls Musikwolke playback per zone
- Maintains playback state for resume
- Exposes status entities for Lovelace
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from copilot_core.alarm.models import AlarmMode

_LOGGER = logging.getLogger(__name__)


class SleepIntegrationService:
    """Service for Musikwolke ↔ Sonnenwecker integration.
    
    Responsibilities:
    1. Auto-Pause: Pause Musikwolke when sleep mode activates
    2. Auto-Resume: Resume Musikwolke after wake-up alarm
    3. Track playback state per zone
    4. Expose status for Lovelace indicators
    """

    def __init__(
        self,
        musikwolke_service=None,
        alarm_service=None,
        config: Optional[Dict] = None,
    ):
        """Initialize.
        
        Args:
            musikwolke_service: Musikwolke/ZoneMediaManager instance
            alarm_service: WeckerService or AlarmEngine instance
            config: Global config dict
        """
        self._musikwolke = musikwolke_service
        self._alarm = alarm_service
        self._config = config or {}
        
        # Zone integration config: zone_id → config dict
        self._zone_configs: Dict[str, Dict[str, Any]] = {}
        
        # Playback state before pause: zone_id → state dict
        self._paused_state: Dict[str, Dict[str, Any]] = {}
        
        # Sleep mode status: zone_id → is_sleeping
        self._sleep_status: Dict[str, bool] = {}
        
        # Active resume timers: zone_id → timer thread
        self._resume_timers: Dict[str, threading.Thread] = {}
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        _LOGGER.info("SleepIntegrationService initialized")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure_zone(self, zone_id: str, config: Dict[str, Any]) -> None:
        """Configure integration for a specific zone.
        
        Config keys:
        - enabled: bool — Enable/disable integration for this zone
        - auto_pause_on_sleep: bool — Auto-pause on sleep mode
        - auto_resume_on_wake: bool — Auto-resume on wake-up
        - pause_delay_s: int — Delay before pausing (seconds)
        - resume_delay_s: int — Delay before resuming (seconds)
        - volume_restore_pct: int — Volume after resume (0-100)
        - show_status_indicator: bool — Show status in Lovelace
        """
        with self._lock:
            self._zone_configs[zone_id] = {
                "enabled": config.get("enabled", False),
                "auto_pause_on_sleep": config.get("auto_pause_on_sleep", True),
                "auto_resume_on_wake": config.get("auto_resume_on_wake", True),
                "pause_delay_s": config.get("pause_delay_s", 0),
                "resume_delay_s": config.get("resume_delay_s", 60),
                "volume_restore_pct": config.get("volume_restore_pct", 100),
                "show_status_indicator": config.get("show_status_indicator", True),
            }
            _LOGGER.debug("Zone %s configured: %s", zone_id, self._zone_configs[zone_id])

    def get_zone_config(self, zone_id: str) -> Dict[str, Any]:
        """Get config for a zone."""
        with self._lock:
            return self._zone_configs.get(zone_id, {
                "enabled": False,
                "auto_pause_on_sleep": True,
                "auto_resume_on_wake": True,
                "pause_delay_s": 0,
                "resume_delay_s": 60,
                "volume_restore_pct": 100,
                "show_status_indicator": True,
            })

    def is_enabled_for_zone(self, zone_id: str) -> bool:
        """Check if integration is enabled for a zone."""
        config = self.get_zone_config(zone_id)
        return config.get("enabled", False)

    # ------------------------------------------------------------------
    # Sleep Mode Activation (Auto-Pause)
    # ------------------------------------------------------------------

    def on_sleep_mode_activated(self, zone_id: str, alarm_id: Optional[str] = None) -> None:
        """Called when sleep mode (sunset alarm) is activated for a zone.
        
        Triggers auto-pause of Musikwolke if configured.
        """
        config = self.get_zone_config(zone_id)
        if not config.get("enabled") or not config.get("auto_pause_on_sleep"):
            _LOGGER.debug("Sleep mode activated for %s but integration disabled", zone_id)
            return

        with self._lock:
            self._sleep_status[zone_id] = True

        _LOGGER.info("Sleep mode activated for zone %s — pausing Musikwolke", zone_id)

        # Apply pause delay if configured
        pause_delay = config.get("pause_delay_s", 0)
        if pause_delay > 0:
            _LOGGER.debug("Pause delayed by %ds for zone %s", pause_delay, zone_id)
            timer = threading.Thread(
                target=self._delayed_pause,
                args=(zone_id, pause_delay),
                daemon=True,
                name=f"sleep-pause-{zone_id}",
            )
            timer.start()
        else:
            self._execute_pause(zone_id)

    def _delayed_pause(self, zone_id: str, delay_s: int) -> None:
        """Execute pause after delay."""
        time.sleep(delay_s)
        
        # Check if still in sleep mode
        with self._lock:
            if not self._sleep_status.get(zone_id):
                _LOGGER.debug("Sleep mode ended before pause delay completed for %s", zone_id)
                return
        
        self._execute_pause(zone_id)

    def _execute_pause(self, zone_id: str) -> None:
        """Execute Musikwolke pause for a zone."""
        if not self._musikwolke:
            _LOGGER.warning("No Musikwolke service available — cannot pause")
            return

        try:
            # Capture current playback state for resume
            state = self._musikwolke.get_zone_state(zone_id)
            if state:
                with self._lock:
                    self._paused_state[zone_id] = {
                        "is_playing": state.get("is_playing", False),
                        "volume_pct": state.get("volume_pct", 30),
                        "source": state.get("source"),
                        "track": state.get("track"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                _LOGGER.debug("Captured state for %s: %s", zone_id, self._paused_state[zone_id])

            # Pause Musikwolke
            self._musikwolke.pause_zone(zone_id)
            _LOGGER.info("Musikwolke paused for zone %s (sleep mode)", zone_id)

        except Exception as exc:
            _LOGGER.warning("Failed to pause Musikwolke for %s: %s", zone_id, exc)

    # ------------------------------------------------------------------
    # Wake-Up Activation (Auto-Resume)
    # ------------------------------------------------------------------

    def on_wake_mode_activated(self, zone_id: str, alarm_id: Optional[str] = None) -> None:
        """Called when wake-up mode (sunrise alarm) is activated for a zone.
        
        Triggers auto-resume of Musikwolke if configured.
        """
        config = self.get_zone_config(zone_id)
        if not config.get("enabled") or not config.get("auto_resume_on_wake"):
            _LOGGER.debug("Wake mode activated for %s but integration disabled", zone_id)
            return

        with self._lock:
            self._sleep_status[zone_id] = False

        _LOGGER.info("Wake mode activated for zone %s — scheduling Musikwolke resume", zone_id)

        # Cancel any pending resume timer
        if zone_id in self._resume_timers:
            del self._resume_timers[zone_id]

        # Apply resume delay if configured
        resume_delay = config.get("resume_delay_s", 60)
        if resume_delay > 0:
            _LOGGER.debug("Resume delayed by %ds for zone %s", resume_delay, zone_id)
            timer = threading.Thread(
                target=self._delayed_resume,
                args=(zone_id, resume_delay),
                daemon=True,
                name=f"sleep-resume-{zone_id}",
            )
            self._resume_timers[zone_id] = timer
            timer.start()
        else:
            self._execute_resume(zone_id)

    def _delayed_resume(self, zone_id: str, delay_s: int) -> None:
        """Execute resume after delay."""
        time.sleep(delay_s)
        
        # Check if still awake (not back to sleep)
        with self._lock:
            if self._sleep_status.get(zone_id):
                _LOGGER.debug("Still in sleep mode — skipping resume for %s", zone_id)
                return
        
        self._execute_resume(zone_id)

    def _execute_resume(self, zone_id: str) -> None:
        """Execute Musikwolke resume for a zone."""
        if not self._musikwolke:
            _LOGGER.warning("No Musikwolke service available — cannot resume")
            return

        with self._lock:
            saved_state = self._paused_state.pop(zone_id, None)
        
        if not saved_state:
            _LOGGER.debug("No saved state for %s — skipping resume", zone_id)
            return

        try:
            # Restore volume if configured
            config = self.get_zone_config(zone_id)
            volume_pct = config.get("volume_restore_pct", 100)
            if volume_pct != 100:
                self._musikwolke.set_volume(zone_id, volume_pct)
            elif saved_state.get("volume_pct"):
                self._musikwolke.set_volume(zone_id, saved_state["volume_pct"])

            # Resume playback
            self._musikwolke.play_zone(zone_id)
            _LOGGER.info("Musikwolke resumed for zone %s (wake mode)", zone_id)

        except Exception as exc:
            _LOGGER.warning("Failed to resume Musikwolke for %s: %s", zone_id, exc)

    # ------------------------------------------------------------------
    # Status & Lovelace Integration
    # ------------------------------------------------------------------

    def get_sleep_status(self, zone_id: str) -> Dict[str, Any]:
        """Get sleep mode status for a zone (for Lovelace indicator).
        
        Returns:
            Dict with:
            - is_sleeping: bool
            - musikwolke_paused: bool
            - pause_reason: str (e.g., "sleep_mode")
            - paused_since: str (ISO timestamp)
        """
        with self._lock:
            is_sleeping = self._sleep_status.get(zone_id, False)
            has_saved_state = zone_id in self._paused_state

        return {
            "is_sleeping": is_sleeping,
            "musikwolke_paused": has_saved_state,
            "pause_reason": "sleep_mode" if is_sleeping else None,
            "paused_since": self._paused_state.get(zone_id, {}).get("timestamp"),
            "integration_enabled": self.is_enabled_for_zone(zone_id),
        }

    def get_all_zones_status(self) -> Dict[str, Dict[str, Any]]:
        """Get sleep status for all configured zones."""
        with self._lock:
            result = {}
            for zone_id in self._zone_configs:
                result[zone_id] = self.get_sleep_status(zone_id)
            return result

    def get_lovelace_status_text(self, zone_id: str) -> str:
        """Get human-readable status text for Lovelace display.
        
        Returns:
            German status text like "Schlaf-Modus aktiv" or "Musik aktiv"
        """
        status = self.get_sleep_status(zone_id)
        
        if not status["integration_enabled"]:
            return "Integration deaktiviert"
        
        if status["is_sleeping"]:
            return "Schlaf-Modus aktiv"
        
        if status["musikwolke_paused"]:
            return "Pause (Schlaf-Modus war aktiv)"
        
        return "Musik aktiv"

    # ------------------------------------------------------------------
    # Manual Controls
    # ------------------------------------------------------------------

    def force_pause(self, zone_id: str) -> bool:
        """Manually pause Musikwolke for a zone (e.g., from Lovelace button)."""
        if not self.is_enabled_for_zone(zone_id):
            return False
        
        with self._lock:
            self._sleep_status[zone_id] = True
        
        self._execute_pause(zone_id)
        return True

    def force_resume(self, zone_id: str) -> bool:
        """Manually resume Musikwolke for a zone (e.g., from Lovelace button)."""
        if not self.is_enabled_for_zone(zone_id):
            return False
        
        with self._lock:
            self._sleep_status[zone_id] = False
        
        self._execute_resume(zone_id)
        return True

    # ------------------------------------------------------------------
    # Event Hooks (for HA Integration)
    # ------------------------------------------------------------------

    def handle_alarm_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle alarm events from HA event bus.
        
        Event types:
        - alarm_sleep_activated: Sleep mode started
        - alarm_wake_activated: Wake-up alarm triggered
        - alarm_completed: Alarm sequence completed
        """
        zone_id = data.get("zone_id")
        alarm_id = data.get("alarm_id")
        alarm_mode = data.get("mode")  # "wake" or "sleep"
        
        if not zone_id:
            return

        if event_type in ("alarm_sleep_activated", "alarm_completed") and alarm_mode == "sleep":
            self.on_sleep_mode_activated(zone_id, alarm_id)
        
        elif event_type in ("alarm_wake_activated", "alarm_completed") and alarm_mode == "wake":
            self.on_wake_mode_activated(zone_id, alarm_id)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Clean up on shutdown."""
        with self._lock:
            self._resume_timers.clear()
            self._paused_state.clear()
            self._sleep_status.clear()
        
        _LOGGER.info("SleepIntegrationService shut down")
