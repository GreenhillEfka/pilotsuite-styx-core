"""Sonnenwecker — Sunlight Wake-Up Engine.

Autonomes Modul: plant und steuert Lichtweck-Sequenzen pro Zone.
Schnittstelle zu Musikwolke: minimal — Deaktivierung bei Schlafbeginn.

Verhalten:
- Aufwachsequenz: Ramp brightness + color_temp über duration_min
- Optional: startet Musikwolke am Ende der Sequenz (wenn konfiguriert)
- Bei Schlaf (Presence gone + Sonnenwecker aktiv): deaktiviert sich, kann Musikwolke stoppen
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, time as dt_time
from typing import Any, Dict, List, Optional, Callable
import uuid

_LOGGER = logging.getLogger(__name__)


@dataclass
class SunlightAlarmConfig:
    """Konfiguration pro Zone."""
    enabled: bool = False
    wake_time: str = "07:00"          # HH:MM
    duration_min: int = 30            # Aufwachdauer in Minuten
    max_brightness: float = 1.0       # 0.0–1.0
    color_temp_start: int = 2000      # Kelvin — warm (Start)
    color_temp_end: int = 5000        # Kelvin — kalt (Ende)
    zone_id: str = ""
    sound_enabled: bool = False       # Musik nach Aufwachsequenz
    sound_source: str = ""            # entity_id für TTS/Musik
    music_on_wake: bool = False       # Musikwolke nach Aufwachsequenz starten
    music_volume_start: float = 0.15  #sanft starten


@dataclass
class AlarmStep:
    """Ein Schritt der Aufwachsequenz."""
    step_ts: str
    brightness: float
    color_temp: int
    elapsed_min: int
    is_complete: bool = False


@dataclass
class AlarmRun:
    """Laufende oder vergangene Aufwachsequenz."""
    run_id: str
    zone_id: str
    config: SunlightAlarmConfig
    started_at: str
    steps: List[AlarmStep] = field(default_factory=list)
    state: str = "pending"  # pending | running | complete | cancelled
    current_step: int = 0
    triggered_callbacks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "zone_id": self.zone_id,
            "config": asdict(self.config),
            "started_at": self.started_at,
            "steps": [asdict(s) for s in self.steps],
            "state": self.state,
            "current_step": self.current_step,
        }


class SonnenweckerEngine:
    """Eigenständiger Sonnenwecker pro Zone."""

    def __init__(self):
        self._configs: Dict[str, SunlightAlarmConfig] = {}
        self._runs: Dict[str, AlarmRun] = {}
        self._callbacks: Dict[str, Callable] = {}  # event → callback
        self._lock_callbacks: List[Callable] = []  # called on sleep/presence gone
        self._wake_callbacks: List[Callable] = []   # called on alarm complete

    # ─── Konfiguration ───────────────────────────────────────────────────────

    def configure(self, zone_id: str, config: SunlightAlarmConfig) -> bool:
        """Konfiguration für eine Zone setzen."""
        config.zone_id = zone_id
        self._configs[zone_id] = config
        _LOGGER.info("Sonnenwecker konfiguriert für %s: %s → %s (%dm)",
                     zone_id, config.wake_time, config.enabled)
        return True

    def get_config(self, zone_id: str) -> Optional[SunlightAlarmConfig]:
        return self._configs.get(zone_id)

    def list_configs(self) -> Dict[str, Dict[str, Any]]:
        return {zid: asdict(cfg) for zid, cfg in self._configs.items()}

    # ─── Sequenz-Steuerung ───────────────────────────────────────────────────

    def start_alarm(self, zone_id: str) -> Optional[str]:
        """Aufwachsequenz für Zone starten. Gibt run_id zurück."""
        config = self._configs.get(zone_id)
        if not config or not config.enabled:
            _LOGGER.debug("Sonnenwecker nicht aktiv für %s", zone_id)
            return None

        run_id = f"sw_{uuid.uuid4().hex[:8]}"
        run = AlarmRun(
            run_id=run_id,
            zone_id=zone_id,
            config=config,
            started_at=datetime.now(timezone.utc).isoformat(),
            state="running",
        )

        # Alle Steps vorberechnen
        self._calculate_steps(run)
        self._runs[run_id] = run

        _LOGGER.info("Sonnenwecker %s gestartet für %s (%d Steps)",
                     run_id, zone_id, len(run.steps))

        # Step 0 sofort ausführen
        self._apply_step(run, 0)

        # Wake-Complete-Callbacks registrieren
        if config.music_on_wake:
            self._trigger_wake_callbacks(run)

        return run_id

    def _calculate_steps(self, run: AlarmRun) -> None:
        """Steps für linearen Ramp berechnen."""
        cfg = run.config
        interval_min = 1  # alle 1 Minute ein Step
        steps_count = min(cfg.duration_min, 30)  # max 30 Steps

        for i in range(steps_count + 1):
            elapsed = i * interval_min
            progress = elapsed / cfg.duration_min if cfg.duration_min > 0 else 1.0

            brightness = cfg.max_brightness * progress
            color_temp = int(cfg.color_temp_start +
                             (cfg.color_temp_end - cfg.color_temp_start) * progress)

            is_complete = (i == steps_count)

            run.steps.append(AlarmStep(
                step_ts=datetime.now(timezone.utc).isoformat(),
                brightness=round(brightness, 3),
                color_temp=color_temp,
                elapsed_min=elapsed,
                is_complete=is_complete,
            ))

    def _apply_step(self, run: AlarmRun, step_idx: int) -> None:
        """Step auf Licht-Entity anwenden."""
        if step_idx >= len(run.steps):
            return

        step = run.steps[step_idx]
        run.current_step = step_idx

        # Callback: Licht-Engine steuern
        on_light = self._callbacks.get("light_step")
        if on_light:
            on_light(run.zone_id, step.brightness, step.color_temp)

        if step.is_complete:
            run.state = "complete"
            _LOGGER.info("Sonnenwecker %s abgeschlossen für %s",
                         run.run_id, run.zone_id)
            # Musikwolke starten wenn konfiguriert
            if run.config.music_on_wake:
                self._trigger_music_wake(run.zone_id, run.config.music_volume_start)

    def tick_step(self, run_id: str) -> Optional[AlarmStep]:
        """Einen Step weiter (wird von Cron/Scheduler aufgerufen)."""
        run = self._runs.get(run_id)
        if not run or run.state != "running":
            return None

        next_idx = run.current_step + 1
        if next_idx >= len(run.steps):
            run.state = "complete"
            return None

        self._apply_step(run, next_idx)
        return run.steps[next_idx]

    def cancel_alarm(self, run_id: str) -> bool:
        """Aktive Sequenz abbrechen."""
        run = self._runs.get(run_id)
        if not run:
            return False

        run.state = "cancelled"
        _LOGGER.info("Sonnenwecker %s abgebrochen für %s", run_id, run.zone_id)

        # Licht aus / Ruhezustand
        on_light = self._callbacks.get("light_step")
        if on_light:
            on_light(run.zone_id, 0.0, run.config.color_temp_start)

        return True

    # ─── Schlaf-Signal (von Presence/Zone) ────────────────────────────────

    def on_sleep_detected(self, zone_id: str) -> List[str]:
        """Wird aufgerufen wenn Schlaf erkannt wird.
        Deaktiviert aktive Alarme, stoppt Musikwolke.

        Returns: List of triggered callback names.
        """
        triggered = []
        config = self._configs.get(zone_id)
        if not config:
            return triggered

        # Alle laufenden Alarme für diese Zone canceln
        for run_id, run in list(self._runs.items()):
            if run.zone_id == zone_id and run.state == "running":
                self.cancel_alarm(run_id)
                triggered.append(f"alarm_cancelled:{run_id}")

        # Musikwolke stoppen wenn aktiv
        if config.sound_enabled or config.music_on_wake:
            self._trigger_sleep_lock_callbacks(zone_id)
            triggered.append("music_stopped")

        _LOGGER.info("Sleep detected for %s: %s", zone_id, triggered)
        return triggered

    def on_wake_up(self, zone_id: str) -> Optional[str]:
        """Wird aufgerufen wenn Aufstehen erkannt wird.
        Startet Musikwolke wenn konfiguriert.

        Returns: run_id oder None.
        """
        config = self._configs.get(zone_id)
        if not config:
            return None

        # Sanfte Musik starten wenn enabled
        if config.music_on_wake:
            return self._start_music_wolke(zone_id, config.music_volume_start)

        return None

    # ─── Callbacks ──────────────────────────────────────────────────────────

    def on_light_step(self, callback: Callable) -> None:
        """Callback für Licht-Step (zone_id, brightness, color_temp)."""
        self._callbacks["light_step"] = callback

    def on_sleep_lock(self, callback: Callable) -> None:
        """Callback wenn Schlaf → soll Musikwolke stoppen."""
        self._lock_callbacks.append(callback)

    def on_wake_complete(self, callback: Callable) -> None:
        """Callback wenn Aufwachsequenz fertig."""
        self._wake_callbacks.append(callback)

    def _trigger_sleep_lock_callbacks(self, zone_id: str) -> None:
        for cb in self._lock_callbacks:
            try:
                cb(zone_id)
            except Exception as e:
                _LOGGER.warning("Sleep lock callback failed: %s", e)

    def _trigger_wake_callbacks(self, run: AlarmRun) -> None:
        for cb in self._wake_callbacks:
            try:
                cb(run)
            except Exception as e:
                _LOGGER.warning("Wake complete callback failed: %s", e)

    def _trigger_music_wake(self, zone_id: str, volume: float) -> None:
        """Musikwolke bei Aufwachsequenz-Ende starten."""
        self._start_music_wolke(zone_id, volume)

    def _start_music_wolke(self, zone_id: str, volume: float) -> str:
        """Wrapper: startet Musikwolke (ruft MusicWolke-Engine oder API auf)."""
        # Direkter Import um zirkuläre Abhängigkeit zu vermeiden
        try:
            from copilot_core.modules.music_wolke.engine import MusicWolkeEngine
            engine = MusicWolkeEngine.get_instance()
            session_id = engine.start_session(
                zone_id=zone_id,
                source_entity="sonnenwecker",
                media_type="music",
                follow_enabled=False,
            )
            if session_id:
                # Sanfte Lautstärke setzen
                _LOGGER.info("Musikwolke gestartet für %s (Vol: %.0f%%)", zone_id, volume * 100)
            return session_id or ""
        except Exception as e:
            _LOGGER.warning("Musikwolke nicht verfügbar: %s", e)
            return ""

    # ─── Status ─────────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = self._runs.get(run_id)
        return run.to_dict() if run else None

    def get_active_runs(self, zone_id: Optional[str] = None) -> List[Dict[str, Any]]:
        runs = [r for r in self._runs.values() if r.state == "running"]
        if zone_id:
            runs = [r for r in runs if r.zone_id == zone_id]
        return [r.to_dict() for r in runs]

    def get_dashboard(self) -> Dict[str, Any]:
        return {
            "configured_zones": list(self._configs.keys()),
            "active_runs": self.get_active_runs(),
            "pending_count": len([r for r in self._runs.values() if r.state == "pending"]),
            "complete_count": len([r for r in self._runs.values() if r.state == "complete"]),
        }


# Singleton
_engine: Optional[SonnenweckerEngine] = None


def get_sonnenwecker_engine() -> SonnenweckerEngine:
    global _engine
    if _engine is None:
        _engine = SonnenweckerEngine()
    return _engine
