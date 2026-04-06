"""Music Cloud & Sunlight Alarm — Konsolidierte Referenz (Slice 165 v2).

Verwendet die eigenständigen Module:
- copilot_core.modules.music_wolke.engine.MusicWolkeEngine
- copilot_core.modules.sonnenwecker.engine.SonnenweckerEngine

Kein direkter HA/API-Code. Nur Integration-Logik.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .sonnenwecker.engine import (
    SonnenweckerEngine,
    SunlightAlarmConfig,
    get_sonnenwecker_engine,
)
from .music_wolke.engine import MusicWolkeEngine

_LOGGER = logging.getLogger(__name__)


class HabitusMediaService:
    """Verbindet Musikwolke + Sonnenwecker für Habitus-Zonen."""

    def __init__(self):
        self._sonnenwecker = get_sonnenwecker_engine()
        self._music_wolke = MusicWolkeEngine.get_instance()
        self._wire_callbacks()

    def _wire_callbacks(self) -> None:
        """Sonnenwecker → Musikwolke verdrahten."""

        def on_sleep_lock(zone_id: str) -> None:
            stopped = self._music_wolke.stop_zone(zone_id)
            _LOGGER.info(
                "Sleep lock on %s: stopped %d MusicWolke sessions",
                zone_id, stopped,
            )

        self._sonnenwecker.on_sleep_lock(on_sleep_lock)

    # ─── Sonnenwecker ────────────────────────────────────────────────────

    def configure_sonnenwecker(self, zone_id: str, **kwargs) -> bool:
        """Sonnenwecker für Zone konfigurieren."""
        config = SunlightAlarmConfig(
            enabled=kwargs.get("enabled", False),
            wake_time=kwargs.get("wake_time", "07:00"),
            duration_min=kwargs.get("duration_min", 30),
            max_brightness=kwargs.get("max_brightness", 1.0),
            color_temp_start=kwargs.get("color_temp_start", 2000),
            color_temp_end=kwargs.get("color_temp_end", 5000),
            music_on_wake=kwargs.get("music_on_wake", False),
            music_volume_start=kwargs.get("music_volume_start", 0.15),
        )
        return self._sonnenwecker.configure(zone_id, config)

    def start_sonnenwecker(self, zone_id: str) -> str:
        """Aufwachsequenz starten."""
        return self._sonnenwecker.start_alarm(zone_id) or ""

    def tick_sonnenwecker(self, run_id: str) -> Dict[str, Any]:
        """Einen Minute-Step weiter (Cron-Callback)."""
        step = self._sonnenwecker.tick_step(run_id)
        return {"run_id": run_id, "step": step}

    def get_sonnenwecker_status(self, zone_id: str) -> Dict[str, Any]:
        """Aktueller Stand."""
        runs = self._sonnenwecker.get_active_runs(zone_id)
        config = self._sonnenwecker.get_config(zone_id)
        return {
            "zone_id": zone_id,
            "configured": config is not None,
            "config": config.__dict__ if config else None,
            "active_runs": runs,
        }

    # ─── Musikwolke ─────────────────────────────────────────────────────

    def register_speaker(self, entity_id: str, name: str, zone_id: str) -> bool:
        """Sonos-Speaker registrieren."""
        return self._music_wolke.register_source(
            entity_id=entity_id, name=name, zone_id=zone_id, media_type="music",
        )

    def play_in_zone(
        self, zone_id: str, source: str = "favorite",
        volume: int = 50, follow: bool = False,
    ) -> str:
        """Musik in Zone starten."""
        return self._music_wolke.start_session(
            zone_id=zone_id,
            source_entity=source,
            media_type="music",
            follow_enabled=follow,
            volume_pct=volume,
        ) or ""

    def stop_zone(self, zone_id: str) -> int:
        """Musik in Zone stoppen."""
        return self._music_wolke.stop_zone(zone_id)

    def get_music_status(self) -> Dict[str, Any]:
        """Musikwolke-Status."""
        return self._music_wolke.get_dashboard()

    # ─── Presence-Integration ───────────────────────────────────────────

    def on_presence_enter(self, person_id: str, zone_id: str) -> None:
        """Person betritt Zone."""
        transfers = self._music_wolke.on_zone_entry(person_id, zone_id)
        _LOGGER.debug("Presence enter %s in %s: %d transfers", person_id, zone_id, len(transfers))

    def on_presence_leave(self, person_id: str, zone_id: str) -> None:
        """Person verlässt Zone."""
        # Nur stoppen wenn keine follow-Sessions aktiv
        _LOGGER.debug("Presence leave %s from %s", person_id, zone_id)


# Singleton
_habitus_media: HabitusMediaService | None = None


def get_habitus_media_service() -> HabitusMediaService:
    global _habitus_media
    if _habitus_media is None:
        _habitus_media = HabitusMediaService()
    return _habitus_media
