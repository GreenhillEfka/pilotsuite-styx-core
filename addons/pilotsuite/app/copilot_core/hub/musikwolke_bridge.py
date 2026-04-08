"""Musikwolke Bridge — Wires ZoneAutomationController to SonosCloudClient + MediaFollowEngine.

Listens to zone automation action dicts (music_start, music_pause, music_follow)
and executes them via the Sonos HTTP API client and the MediaFollowEngine.

Architecture:
  ZoneAutomationController.on_presence_detected()
    → actions = {"music_start": True, "music_volume_pct": 30, "music_follow": True}
    → MusikwolkeBridge.execute_actions(actions)
      → SonosCloudClient.play(room) / .set_volume(room, vol) / .follow_user(...)
      → MediaFollowEngine.on_zone_enter(zone_id)
"""

from __future__ import annotations

import logging
from typing import Any

from copilot_core.hub.sonos_client import SonosCloudClient
from copilot_core.hub.media_follow import MediaFollowEngine

logger = logging.getLogger(__name__)


class MusikwolkeBridge:
    """Bridges zone automation music actions to Sonos hardware + media follow engine."""

    def __init__(
        self,
        sonos: SonosCloudClient | None = None,
        media_follow: MediaFollowEngine | None = None,
        zone_speaker_map: dict[str, str] | None = None,
    ) -> None:
        self._sonos = sonos
        self._media_follow = media_follow
        # zone_id -> Sonos room name (e.g., "wohnzimmer" -> "Wohnzimmer")
        self._zone_speaker_map: dict[str, str] = zone_speaker_map or {}
        self._active_zones: set[str] = set()
        self._last_occupied_zone: str | None = None

    # ── Configuration ─────────────────────────────────────────────────────

    def set_zone_speaker(self, zone_id: str, sonos_room: str) -> None:
        """Map a zone to a Sonos room name."""
        self._zone_speaker_map[zone_id] = sonos_room

    def remove_zone_speaker(self, zone_id: str) -> None:
        """Remove a zone-to-speaker mapping."""
        self._zone_speaker_map.pop(zone_id, None)

    def get_zone_speaker_map(self) -> dict[str, str]:
        """Get current zone-to-speaker mapping."""
        return dict(self._zone_speaker_map)

    def auto_discover_mappings(self) -> int:
        """Try to auto-map zones to Sonos rooms by name similarity.

        Returns the number of mappings created.
        """
        if not self._sonos:
            return 0

        speakers = self._sonos.get_speakers()
        if not speakers:
            self._sonos.discover_zones()
            speakers = self._sonos.get_speakers()

        mapped = 0
        for speaker in speakers:
            room_lower = speaker.room_name.lower().replace(" ", "").replace("-", "").replace("_", "")
            # Try to match against existing zone IDs
            for zone_id in list(self._zone_speaker_map.keys()) + self._get_known_zone_ids():
                zone_lower = zone_id.lower().replace("zone:", "").replace(" ", "").replace("-", "").replace("_", "")
                if room_lower == zone_lower or room_lower in zone_lower or zone_lower in room_lower:
                    if zone_id not in self._zone_speaker_map:
                        self._zone_speaker_map[zone_id] = speaker.room_name
                        mapped += 1
                        logger.info("Auto-mapped zone '%s' → Sonos '%s'", zone_id, speaker.room_name)

        return mapped

    def _get_known_zone_ids(self) -> list[str]:
        """Get zone IDs from media follow engine sources."""
        if not self._media_follow:
            return []
        return [s["zone_id"] for s in self._media_follow.get_sources()]

    # ── Action Execution ──────────────────────────────────────────────────

    def execute_actions(self, actions: dict[str, Any]) -> dict[str, Any]:
        """Execute zone automation music actions.

        Receives action dicts from ZoneAutomationController and translates them
        to concrete Sonos/MediaFollow commands.

        Returns a result dict with what was executed.
        """
        zone_id = actions.get("zone_id", "")
        result: dict[str, Any] = {"zone_id": zone_id, "executed": []}

        sonos_room = self._zone_speaker_map.get(zone_id)

        if actions.get("music_start"):
            try:
                self._handle_music_start(zone_id, sonos_room, actions, result)
            except Exception:
                logger.exception("music_start failed for zone '%s'", zone_id)

        if actions.get("music_pause"):
            try:
                self._handle_music_pause(zone_id, sonos_room, actions, result)
            except Exception:
                logger.exception("music_pause failed for zone '%s'", zone_id)

        if actions.get("music_follow"):
            try:
                self._handle_music_follow(zone_id, result)
            except Exception:
                logger.exception("music_follow failed for zone '%s'", zone_id)

        return result

    def _handle_music_start(
        self, zone_id: str, sonos_room: str | None,
        actions: dict[str, Any], result: dict[str, Any],
    ) -> None:
        """Start music playback in a zone."""
        volume = actions.get("music_volume_pct", 30)

        if self._sonos and sonos_room:
            # Set volume first, then play
            self._sonos.set_volume(sonos_room, volume)
            self._sonos.play(sonos_room)
            result["executed"].append(f"sonos_play:{sonos_room}@{volume}%")
            logger.info("Musikwolke: play '%s' @ %d%%", sonos_room, volume)
        else:
            logger.debug("No Sonos room mapped for zone '%s'", zone_id)

        # Track in media follow engine
        if self._media_follow:
            transfers = self._media_follow.on_zone_enter(zone_id)
            if transfers:
                result["executed"].append(f"media_follow_transfers:{len(transfers)}")

        self._active_zones.add(zone_id)
        self._last_occupied_zone = zone_id

    def _handle_music_pause(
        self, zone_id: str, sonos_room: str | None,
        actions: dict[str, Any], result: dict[str, Any],
    ) -> None:
        """Pause music in a zone after absence with optional volume fade-out."""
        fade_s = actions.get("music_fade_s", 3)

        if self._sonos and sonos_room:
            if fade_s > 0:
                self._fade_and_pause(sonos_room, fade_s)
                result["executed"].append(f"sonos_fade_pause:{sonos_room}:{fade_s}s")
            else:
                self._sonos.pause(sonos_room)
                result["executed"].append(f"sonos_pause:{sonos_room}")
            logger.info("Musikwolke: pause '%s' (fade=%ds)", sonos_room, fade_s)

        self._active_zones.discard(zone_id)

    def _fade_and_pause(self, room: str, fade_s: int) -> None:
        """Gradually reduce volume over fade_s seconds, then pause.

        Runs in a background daemon thread so it doesn't block the caller.
        After fade completes, restores original volume level for next play.
        """
        import threading

        original_vol = self._sonos.get_volume(room)
        if original_vol <= 0:
            self._sonos.pause(room)
            return

        def _do_fade():
            import time
            steps = min(fade_s * 2, 20)  # 2 steps/second, max 20 steps
            interval = fade_s / steps if steps > 0 else 0
            vol_step = original_vol / steps if steps > 0 else original_vol

            for i in range(1, steps + 1):
                target_vol = max(0, int(original_vol - (vol_step * i)))
                try:
                    self._sonos.set_volume(room, target_vol)
                except Exception:
                    break
                time.sleep(interval)

            # Pause and restore original volume for next play
            try:
                self._sonos.pause(room)
                self._sonos.set_volume(room, original_vol)
            except Exception as exc:
                logger.warning("Fade cleanup failed for '%s': %s", room, exc)

        t = threading.Thread(target=_do_fade, daemon=True)
        t.start()

    def _handle_music_follow(self, zone_id: str, result: dict[str, Any]) -> None:
        """Handle music follow (Musikwolke) when user moves between zones."""
        if not self._sonos:
            return

        previous_zone = self._last_occupied_zone
        current_room = self._zone_speaker_map.get(zone_id)
        previous_room = self._zone_speaker_map.get(previous_zone) if previous_zone else None

        if current_room and previous_room and current_room != previous_room:
            # Get current musikwolke members
            musikwolke_rooms = [
                self._zone_speaker_map[z]
                for z in self._active_zones
                if z in self._zone_speaker_map
            ]

            success = self._sonos.follow_user(
                user_room=current_room,
                previous_room=previous_room,
                musikwolke_rooms=musikwolke_rooms,
            )
            if success:
                result["executed"].append(
                    f"follow:{previous_room}→{current_room}"
                )
                logger.info(
                    "Musikwolke follow: %s → %s", previous_room, current_room
                )

        self._last_occupied_zone = zone_id

    # ── Direct Control ────────────────────────────────────────────────────

    def play_in_zone(self, zone_id: str, volume_pct: int | None = None) -> bool:
        """Directly play music in a zone."""
        room = self._zone_speaker_map.get(zone_id)
        if not room or not self._sonos:
            return False
        if volume_pct is not None:
            self._sonos.set_volume(room, volume_pct)
        return self._sonos.play(room)

    def pause_in_zone(self, zone_id: str) -> bool:
        """Directly pause music in a zone."""
        room = self._zone_speaker_map.get(zone_id)
        if not room or not self._sonos:
            return False
        return self._sonos.pause(room)

    def set_zone_volume(self, zone_id: str, volume_pct: int) -> bool:
        """Set volume for a zone's Sonos speaker."""
        room = self._zone_speaker_map.get(zone_id)
        if not room or not self._sonos:
            return False
        return self._sonos.set_volume(room, volume_pct)

    def create_musikwolke(self, zone_ids: list[str]) -> bool:
        """Create a Musikwolke across multiple zones."""
        if not self._sonos:
            return False
        rooms = [
            self._zone_speaker_map[z]
            for z in zone_ids
            if z in self._zone_speaker_map
        ]
        if len(rooms) < 2:
            return False
        return self._sonos.create_musikwolke(rooms)

    def dissolve_musikwolke(self, zone_ids: list[str]) -> bool:
        """Dissolve a Musikwolke."""
        if not self._sonos:
            return False
        rooms = [
            self._zone_speaker_map[z]
            for z in zone_ids
            if z in self._zone_speaker_map
        ]
        return self._sonos.dissolve_musikwolke(rooms)

    # ── Status ────────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Get Musikwolke bridge status."""
        sonos_summary = self._sonos.get_summary() if self._sonos else {}
        media_dashboard = None
        if self._media_follow:
            db = self._media_follow.get_dashboard()
            if db is not None:
                media_dashboard = {
                    "total_sources": db.total_sources,
                    "active_sessions": db.active_sessions,
                    "zones_with_playback": db.zones_with_playback,
                    "follow_enabled_zones": db.follow_enabled_zones,
                }

        return {
            "sonos_connected": (self._sonos.health_check() if self._sonos else False),
            "media_follow_active": self._media_follow is not None,
            "zone_speaker_map": dict(self._zone_speaker_map),
            "active_zones": list(self._active_zones),
            "last_occupied_zone": self._last_occupied_zone,
            "sonos": sonos_summary,
            "media_follow": media_dashboard,
        }
