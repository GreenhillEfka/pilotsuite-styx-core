"""AlarmEngine — Scheduler, Lichtwecker und Musik-Steuerung.

Features:
- Daemon-Thread Scheduler (10s Check-Intervall)
- CRUD fuer Alarm-Konfigurationen (persistiert als JSON)
- Sunrise/Sunset Licht-Simulation via HA Supervisor API
- Musik-Steuerung via SonosHTTPClient
- Snooze, Cancel, Presets
- Laufzeit-Status pro Alarm
- Zone-basierte Alarme (pro Schlafzimmer)
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any

import requests

from copilot_core.modules.sunrise_alarm.curves import (
    get_curve,
    interpolate_value,
    interpolate_cct,
    philips_hue_phase_cct,
    reverse,
)
from copilot_core.modules.sunrise_alarm.models import (
    AlarmConfig,
    AlarmMode,
    AlarmPreset,
    AlarmRuntime,
    AlarmState,
    CurveType,
    LightConfig,
    MusicConfig,
    cct_to_rgb,
)

_LOGGER = logging.getLogger(__name__)

_SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
_SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


def _ha_headers() -> dict:
    """HTTP-Header fuer HA Supervisor API."""
    return {
        "Authorization": f"Bearer {_SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }


class AlarmEngine:
    """Wecker-Engine mit Scheduler, Licht- und Musiksteuerung."""

    def __init__(
        self,
        sonos_client=None,
        configs_dir: str = "/data/sunrise_alarm_configs",
        presets_dir: str = "/data/sunrise_alarm_presets",
    ):
        self._sonos = sonos_client
        self._configs_dir = configs_dir
        self._presets_dir = presets_dir

        # Alarm-Configs (alarm_id → AlarmConfig)
        self._alarms: dict[str, AlarmConfig] = {}
        # Laufzeit-Zustaende (alarm_id → AlarmRuntime)
        self._runtimes: dict[str, AlarmRuntime] = {}

        # Scheduler Thread
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Execution Threads (alarm_id → Thread)
        self._exec_threads: dict[str, threading.Thread] = {}
        self._exec_stops: dict[str, threading.Event] = {}

        # Directories erstellen + Config laden
        os.makedirs(self._configs_dir, exist_ok=True)
        os.makedirs(self._presets_dir, exist_ok=True)
        self._load_configs()
        self._install_default_presets()

    # ------------------------------------------------------------------ #
    # Scheduler
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Startet den Scheduler-Thread."""
        if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
            return
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="alarm-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        _LOGGER.info("AlarmEngine scheduler started")

    def stop(self) -> None:
        """Stoppt den Scheduler und alle laufenden Alarme."""
        self._stop_event.set()
        # Alle Execution-Threads stoppen
        for alarm_id in list(self._exec_stops):
            self._exec_stops[alarm_id].set()
        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=5)
            self._scheduler_thread = None
        _LOGGER.info("AlarmEngine scheduler stopped")

    def _scheduler_loop(self) -> None:
        """Hauptschleife: prueft alle 10s ob ein Alarm ausgeloest werden muss."""
        while not self._stop_event.wait(timeout=10):
            try:
                self._check_alarms()
            except Exception as exc:
                _LOGGER.warning("Scheduler check failed: %s", exc)

    def _check_alarms(self) -> None:
        """Prueft alle aktivierten Alarme gegen die aktuelle Zeit."""
        now = datetime.now(timezone.utc).astimezone()
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%a").lower()

        with self._lock:
            for alarm_id, config in self._alarms.items():
                if not config.schedule.enabled:
                    continue

                runtime = self._runtimes.get(alarm_id)
                if runtime and runtime.state in (
                    AlarmState.RUNNING.value,
                    AlarmState.SNOOZED.value,
                ):
                    continue

                # Zeitabgleich (auf Minute genau)
                if config.schedule.time != current_time:
                    continue

                # Tagesabgleich
                if current_day not in config.schedule.days:
                    continue

                # Doppelte Ausloesung verhindern (bereits completed in dieser Minute)
                if runtime and runtime.state == AlarmState.COMPLETED.value:
                    if runtime.started_at:
                        started = runtime.started_at[:16]  # YYYY-MM-DDTHH:MM
                        if started == now.isoformat()[:16]:
                            continue

                self._trigger_alarm(alarm_id)

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def create_alarm(self, data: dict) -> AlarmConfig:
        """Erstellt einen neuen Alarm."""
        alarm_id = data.get("alarm_id", "") or str(uuid.uuid4())[:8]
        data["alarm_id"] = alarm_id
        config = AlarmConfig.from_dict(data)
        config.alarm_id = alarm_id

        with self._lock:
            self._alarms[alarm_id] = config
            self._runtimes[alarm_id] = AlarmRuntime(
                state=AlarmState.ARMED.value,
                next_trigger=self._compute_next_trigger(config),
            )

        self._save_config(config)
        _LOGGER.info("Alarm created: %s (%s)", alarm_id, config.name)
        return config

    def update_alarm(self, alarm_id: str, data: dict) -> Optional[AlarmConfig]:
        """Aktualisiert einen bestehenden Alarm."""
        with self._lock:
            if alarm_id not in self._alarms:
                return None
            data["alarm_id"] = alarm_id
            config = AlarmConfig.from_dict(data)
            self._alarms[alarm_id] = config

            # Runtime zuruecksetzen wenn nicht laufend
            runtime = self._runtimes.get(alarm_id)
            if not runtime or runtime.state not in (
                AlarmState.RUNNING.value,
                AlarmState.SNOOZED.value,
            ):
                self._runtimes[alarm_id] = AlarmRuntime(
                    state=AlarmState.ARMED.value,
                    next_trigger=self._compute_next_trigger(config),
                )

        self._save_config(config)
        return config

    def delete_alarm(self, alarm_id: str) -> bool:
        """Loescht einen Alarm."""
        with self._lock:
            if alarm_id not in self._alarms:
                return False
            # Laufenden Alarm stoppen
            if alarm_id in self._exec_stops:
                self._exec_stops[alarm_id].set()
            del self._alarms[alarm_id]
            self._runtimes.pop(alarm_id, None)

        path = self._config_path(alarm_id)
        if os.path.exists(path):
            os.remove(path)
        return True

    def get_alarm(self, alarm_id: str) -> Optional[dict]:
        """Gibt Alarm-Config + Runtime zurueck."""
        with self._lock:
            config = self._alarms.get(alarm_id)
            if not config:
                return None
            runtime = self._runtimes.get(alarm_id, AlarmRuntime())
            return {
                **config.to_dict(),
                "runtime": runtime.to_dict(),
            }

    def list_alarms(self) -> list[dict]:
        """Listet alle Alarme."""
        with self._lock:
            result = []
            for alarm_id, config in self._alarms.items():
                runtime = self._runtimes.get(alarm_id, AlarmRuntime())
                result.append({
                    **config.to_dict(),
                    "runtime": runtime.to_dict(),
                })
            return result

    def get_alarms_for_zone(self, zone_id: str) -> list[dict]:
        """Gibt alle Alarme fuer eine Zone zurueck."""
        return [a for a in self.list_alarms() if a.get("zone_id") == zone_id]

    def get_alarms_for_person(self, person_id: str) -> list[dict]:
        """Gibt alle Alarme fuer eine Person zurueck."""
        return [a for a in self.list_alarms() if a.get("person_id") == person_id]

    # ------------------------------------------------------------------ #
    # Trigger / Snooze / Cancel
    # ------------------------------------------------------------------ #

    def trigger_alarm(self, alarm_id: str) -> Optional[dict]:
        """Manuelles Ausloesen eines Alarms."""
        with self._lock:
            if alarm_id not in self._alarms:
                return None
        return self._trigger_alarm(alarm_id)

    def _trigger_alarm(self, alarm_id: str) -> dict:
        """Interne Alarm-Ausloesung — startet Execution-Thread."""
        config = self._alarms[alarm_id]
        now_iso = datetime.now(timezone.utc).isoformat()

        runtime = AlarmRuntime(
            state=AlarmState.RUNNING.value,
            started_at=now_iso,
            total_steps=config.light.total_steps,
        )
        self._runtimes[alarm_id] = runtime

        # Execution Thread starten
        stop_event = threading.Event()
        self._exec_stops[alarm_id] = stop_event

        thread = threading.Thread(
            target=self._execute_alarm,
            args=(alarm_id, config, runtime, stop_event),
            name=f"alarm-exec-{alarm_id}",
            daemon=True,
        )
        self._exec_threads[alarm_id] = thread
        thread.start()

        _LOGGER.info("Alarm triggered: %s (%s, mode=%s)", alarm_id, config.name, config.mode)
        return {
            "alarm_id": alarm_id,
            "action": "triggered",
            "mode": config.mode,
            "name": config.name,
        }

    def snooze_alarm(self, alarm_id: str) -> Optional[dict]:
        """Snooze — pausiert und startet nach snooze_minutes neu."""
        with self._lock:
            if alarm_id not in self._alarms:
                return None
            runtime = self._runtimes.get(alarm_id)
            if not runtime or runtime.state not in (
                AlarmState.RUNNING.value,
                AlarmState.SNOOZED.value,
            ):
                return {"alarm_id": alarm_id, "action": "not_running"}

            # Execution stoppen
            if alarm_id in self._exec_stops:
                self._exec_stops[alarm_id].set()

            config = self._alarms[alarm_id]
            runtime.state = AlarmState.SNOOZED.value
            runtime.snooze_count += 1

        # Lichter ausschalten
        self._lights_off(config.light.entity_ids)
        # Musik pausieren
        self._music_stop(config)

        # Nach snooze_minutes erneut ausloesen
        snooze_s = config.snooze_minutes * 60

        def _snooze_resume():
            time.sleep(snooze_s)
            with self._lock:
                rt = self._runtimes.get(alarm_id)
                if rt and rt.state == AlarmState.SNOOZED.value:
                    pass  # Weiter unten triggern
                else:
                    return
            self._trigger_alarm(alarm_id)

        t = threading.Thread(target=_snooze_resume, daemon=True, name=f"alarm-snooze-{alarm_id}")
        t.start()

        _LOGGER.info("Alarm snoozed: %s (%d min, count=%d)",
                      alarm_id, config.snooze_minutes, runtime.snooze_count)
        return {
            "alarm_id": alarm_id,
            "action": "snoozed",
            "snooze_minutes": config.snooze_minutes,
            "snooze_count": runtime.snooze_count,
        }

    def cancel_alarm(self, alarm_id: str) -> Optional[dict]:
        """Bricht einen laufenden/gesnoozten Alarm ab."""
        with self._lock:
            if alarm_id not in self._alarms:
                return None
            runtime = self._runtimes.get(alarm_id)
            if not runtime:
                return {"alarm_id": alarm_id, "action": "not_active"}

            if alarm_id in self._exec_stops:
                self._exec_stops[alarm_id].set()

            config = self._alarms[alarm_id]
            runtime.state = AlarmState.CANCELLED.value

        # Aufraumen
        self._lights_off(config.light.entity_ids)
        self._music_stop(config)

        _LOGGER.info("Alarm cancelled: %s", alarm_id)
        return {"alarm_id": alarm_id, "action": "cancelled"}

    # ------------------------------------------------------------------ #
    # Alarm Execution (laeuft im Thread)
    # ------------------------------------------------------------------ #

    def _execute_alarm(self, alarm_id: str, config: AlarmConfig,
                       runtime: AlarmRuntime, stop_event: threading.Event) -> None:
        """Fuehrt den Alarm-Verlauf aus (Licht + Musik)."""
        try:
            is_wake = config.mode == AlarmMode.WAKE.value
            light = config.light
            music = config.music
            curve_fn = get_curve(light.curve_type)

            # Fuer Sunset die Kurve umkehren
            if not is_wake:
                curve_fn = reverse(curve_fn)

            total_steps = light.total_steps
            use_philips_cct = light.curve_type == CurveType.PHILIPS_HUE.value

            # Musik starten (am Anfang bei Wake, am Anfang bei Sleep)
            if music.enabled and music.source_name:
                self._music_start(config)

            # Licht-Verlauf
            for step in range(total_steps + 1):
                if stop_event.is_set():
                    return

                t = step / total_steps if total_steps > 0 else 1.0

                # Helligkeit
                brightness = int(interpolate_value(
                    light.brightness_start_pct,
                    light.brightness_end_pct,
                    t,
                    curve_fn,
                ))
                brightness = max(0, min(100, brightness))

                # Farbtemperatur
                if use_philips_cct:
                    cct = philips_hue_phase_cct(t, light.cct_start_k, light.cct_end_k)
                else:
                    cct = interpolate_cct(light.cct_start_k, light.cct_end_k, t, curve_fn)

                # Lautstaerke (linearer Verlauf)
                if music.enabled:
                    volume = int(interpolate_value(
                        music.volume_start_pct,
                        music.volume_end_pct,
                        t,
                        linear_fn,
                    ))
                    volume = max(0, min(100, volume))
                    self._set_music_volume(config, volume)
                    runtime.current_volume = volume

                # Licht setzen
                if light.entity_ids and brightness > 0:
                    self._set_lights(
                        light.entity_ids,
                        brightness,
                        cct,
                        light.use_rgb_fallback,
                        light.transition_s,
                    )
                elif light.entity_ids and brightness == 0 and step > 0:
                    # Bei Sunset am Ende ausschalten
                    self._lights_off(light.entity_ids)

                # Runtime aktualisieren
                runtime.step_count = step
                runtime.progress_pct = (step / total_steps * 100) if total_steps > 0 else 100
                runtime.current_brightness = brightness
                runtime.current_cct = cct

                # Warten
                if step < total_steps:
                    if stop_event.wait(timeout=light.step_interval_s):
                        return

            # Abschluss
            with self._lock:
                rt = self._runtimes.get(alarm_id)
                if rt and rt.state == AlarmState.RUNNING.value:
                    rt.state = AlarmState.COMPLETED.value
                    rt.progress_pct = 100.0

            # Sleep Timer fuer Musik
            if music.enabled and music.sleep_timer_s > 0 and self._sonos and music.sonos_room:
                self._sonos.set_sleep(music.sonos_room, music.sleep_timer_s)

            # One-Shot deaktivieren
            if config.schedule.one_shot:
                config.schedule.enabled = False
                self._save_config(config)

            _LOGGER.info("Alarm completed: %s", alarm_id)

        except Exception as exc:
            _LOGGER.error("Alarm execution failed: %s — %s", alarm_id, exc)
            with self._lock:
                rt = self._runtimes.get(alarm_id)
                if rt:
                    rt.state = AlarmState.CANCELLED.value
        finally:
            self._exec_stops.pop(alarm_id, None)
            self._exec_threads.pop(alarm_id, None)

    # ------------------------------------------------------------------ #
    # HA Light Control
    # ------------------------------------------------------------------ #

    def _set_lights(self, entity_ids: list[str], brightness_pct: int,
                    cct_k: int, use_rgb_fallback: bool, transition_s: int) -> None:
        """Setzt Helligkeit und Farbtemperatur via HA Supervisor API."""
        service_data: dict = {
            "entity_id": entity_ids,
            "brightness_pct": brightness_pct,
            "transition": transition_s,
        }

        if use_rgb_fallback:
            rgb = cct_to_rgb(cct_k)
            service_data["rgb_color"] = list(rgb)
        else:
            service_data["color_temp_kelvin"] = cct_k

        self._call_ha_service("light", "turn_on", service_data)

    def _lights_off(self, entity_ids: list[str]) -> None:
        """Schaltet Lichter aus."""
        if not entity_ids:
            return
        self._call_ha_service("light", "turn_off", {"entity_id": entity_ids})

    def _call_ha_service(self, domain: str, service: str, data: dict) -> bool:
        """Ruft einen HA-Service via Supervisor API auf."""
        url = f"{_SUPERVISOR_API}/services/{domain}/{service}"
        try:
            resp = requests.post(url, json=data, headers=_ha_headers(), timeout=10)
            if resp.status_code >= 400:
                _LOGGER.warning("HA service call failed: %s/%s → %d", domain, service, resp.status_code)
                return False
            return True
        except Exception as exc:
            _LOGGER.warning("HA service call error: %s/%s → %s", domain, service, exc)
            return False

    # ------------------------------------------------------------------ #
    # Music Control
    # ------------------------------------------------------------------ #

    def _music_start(self, config: AlarmConfig) -> None:
        """Startet Musik-Wiedergabe."""
        music = config.music
        if not music.enabled:
            return

        if self._sonos and music.sonos_room:
            # Sonos: Lautstaerke setzen, Shuffle, Favorite/Playlist starten
            self._sonos.set_volume(music.sonos_room, music.volume_start_pct)
            if music.shuffle:
                self._sonos.set_shuffle(music.sonos_room, True)
            if music.source_type == "favorite" and music.source_name:
                self._sonos.play_favorite(music.sonos_room, music.source_name)
            elif music.source_type == "playlist" and music.source_name:
                self._sonos.play_playlist(music.sonos_room, music.source_name)
            else:
                self._sonos.play(music.sonos_room)
        elif music.media_player_entity:
            # HA media_player Fallback
            self._call_ha_service("media_player", "volume_set", {
                "entity_id": music.media_player_entity,
                "volume_level": music.volume_start_pct / 100.0,
            })
            self._call_ha_service("media_player", "media_play", {
                "entity_id": music.media_player_entity,
            })

    def _music_stop(self, config: AlarmConfig) -> None:
        """Stoppt Musik-Wiedergabe."""
        music = config.music
        if not music.enabled:
            return

        if self._sonos and music.sonos_room:
            self._sonos.pause(music.sonos_room)
        elif music.media_player_entity:
            self._call_ha_service("media_player", "media_pause", {
                "entity_id": music.media_player_entity,
            })

    def _set_music_volume(self, config: AlarmConfig, volume_pct: int) -> None:
        """Setzt die Musik-Lautstaerke."""
        music = config.music
        if not music.enabled:
            return

        if self._sonos and music.sonos_room:
            self._sonos.set_volume(music.sonos_room, volume_pct)
        elif music.media_player_entity:
            self._call_ha_service("media_player", "volume_set", {
                "entity_id": music.media_player_entity,
                "volume_level": volume_pct / 100.0,
            })

    # ------------------------------------------------------------------ #
    # Presets
    # ------------------------------------------------------------------ #

    def _install_default_presets(self) -> None:
        """Installiert Standard-Presets falls noch keine vorhanden."""
        if self.list_presets():
            return

        defaults = [
            AlarmPreset(
                preset_id="sunrise_gentle",
                label="Sanfter Sonnenaufgang",
                description="30 Min Quadratic-Kurve, 1800K→5000K, leise Musik",
                mode=AlarmMode.WAKE.value,
                light=LightConfig(
                    curve_type=CurveType.QUADRATIC.value,
                    duration_minutes=30,
                    brightness_start_pct=0,
                    brightness_end_pct=100,
                    cct_start_k=1800,
                    cct_end_k=5000,
                ),
                music=MusicConfig(volume_start_pct=5, volume_end_pct=30),
                snooze_minutes=9,
            ),
            AlarmPreset(
                preset_id="sunrise_philips",
                label="Philips Wake-up",
                description="30 Min 3-Phasen Philips-Kurve, warmrot bis Tageslicht",
                mode=AlarmMode.WAKE.value,
                light=LightConfig(
                    curve_type=CurveType.PHILIPS_HUE.value,
                    duration_minutes=30,
                    brightness_start_pct=0,
                    brightness_end_pct=100,
                    cct_start_k=1800,
                    cct_end_k=5000,
                ),
                music=MusicConfig(volume_start_pct=5, volume_end_pct=40),
                snooze_minutes=9,
            ),
            AlarmPreset(
                preset_id="sunrise_sigmoid",
                label="Sigmoid Sanft",
                description="30 Min S-Kurve, sehr sanfter Start und Ende",
                mode=AlarmMode.WAKE.value,
                light=LightConfig(
                    curve_type=CurveType.SIGMOID.value,
                    duration_minutes=30,
                    brightness_start_pct=0,
                    brightness_end_pct=100,
                    cct_start_k=1800,
                    cct_end_k=4500,
                ),
                music=MusicConfig(volume_start_pct=3, volume_end_pct=25),
                snooze_minutes=9,
            ),
            AlarmPreset(
                preset_id="sunset_gentle",
                label="Sanfter Sonnenuntergang",
                description="45 Min Quadratic-Kurve, 3000K→1800K, Musik leiser",
                mode=AlarmMode.SLEEP.value,
                light=LightConfig(
                    curve_type=CurveType.QUADRATIC.value,
                    duration_minutes=45,
                    brightness_start_pct=80,
                    brightness_end_pct=0,
                    cct_start_k=3000,
                    cct_end_k=1800,
                ),
                music=MusicConfig(
                    volume_start_pct=30,
                    volume_end_pct=5,
                    sleep_timer_s=2700,
                ),
                snooze_minutes=5,
            ),
            AlarmPreset(
                preset_id="sunset_exponential",
                label="Exponentielles Dimmen",
                description="60 Min Exponential, lange sanft dann schneller aus",
                mode=AlarmMode.SLEEP.value,
                light=LightConfig(
                    curve_type=CurveType.EXPONENTIAL.value,
                    duration_minutes=60,
                    brightness_start_pct=70,
                    brightness_end_pct=0,
                    cct_start_k=2700,
                    cct_end_k=1800,
                ),
                music=MusicConfig(
                    volume_start_pct=25,
                    volume_end_pct=3,
                    sleep_timer_s=3600,
                ),
                snooze_minutes=5,
            ),
        ]
        for preset in defaults:
            self.save_preset(preset)

    def save_preset(self, preset: AlarmPreset) -> bool:
        """Speichert ein Preset als JSON."""
        try:
            data = {
                "preset_id": preset.preset_id,
                "label": preset.label,
                "description": preset.description,
                "mode": preset.mode,
                "light": {
                    "curve_type": preset.light.curve_type,
                    "duration_minutes": preset.light.duration_minutes,
                    "brightness_start_pct": preset.light.brightness_start_pct,
                    "brightness_end_pct": preset.light.brightness_end_pct,
                    "cct_start_k": preset.light.cct_start_k,
                    "cct_end_k": preset.light.cct_end_k,
                    "step_interval_s": preset.light.step_interval_s,
                    "use_rgb_fallback": preset.light.use_rgb_fallback,
                    "transition_s": preset.light.transition_s,
                },
                "music": {
                    "source_type": preset.music.source_type,
                    "source_name": preset.music.source_name,
                    "volume_start_pct": preset.music.volume_start_pct,
                    "volume_end_pct": preset.music.volume_end_pct,
                    "shuffle": preset.music.shuffle,
                    "sleep_timer_s": preset.music.sleep_timer_s,
                    "enabled": preset.music.enabled,
                },
                "snooze_minutes": preset.snooze_minutes,
            }
            path = self._preset_path(preset.preset_id)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as exc:
            _LOGGER.warning("Preset save failed: %s", exc)
            return False

    def get_preset(self, preset_id: str) -> Optional[dict]:
        """Laedt ein Preset."""
        path = self._preset_path(preset_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return None

    def delete_preset(self, preset_id: str) -> bool:
        """Loescht ein Preset."""
        path = self._preset_path(preset_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def list_presets(self) -> list[dict]:
        """Listet alle Presets."""
        presets = []
        if not os.path.isdir(self._presets_dir):
            return presets
        for fname in sorted(os.listdir(self._presets_dir)):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(self._presets_dir, fname)) as f:
                    presets.append(json.load(f))
            except Exception:
                continue
        return presets

    def create_from_preset(self, preset_id: str, overrides: dict = None) -> Optional[AlarmConfig]:
        """Erstellt einen Alarm aus einem Preset."""
        preset_data = self.get_preset(preset_id)
        if not preset_data:
            return None

        alarm_data = {
            "name": preset_data.get("label", "Wecker"),
            "mode": preset_data.get("mode", "wake"),
            "light": preset_data.get("light", {}),
            "music": preset_data.get("music", {}),
            "snooze_minutes": preset_data.get("snooze_minutes", 9),
        }
        if overrides:
            alarm_data.update(overrides)

        return self.create_alarm(alarm_data)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _config_path(self, alarm_id: str) -> str:
        safe_id = "".join(c for c in alarm_id if c.isalnum() or c in "-_")
        return os.path.join(self._configs_dir, f"{safe_id}.json")

    def _preset_path(self, preset_id: str) -> str:
        safe_id = "".join(c for c in preset_id if c.isalnum() or c in "-_")
        return os.path.join(self._presets_dir, f"{safe_id}.json")

    def _save_config(self, config: AlarmConfig) -> None:
        try:
            path = self._config_path(config.alarm_id)
            with open(path, "w") as f:
                json.dump(config.to_dict(), f, indent=2)
        except Exception as exc:
            _LOGGER.warning("Config save failed: %s", exc)

    def _load_configs(self) -> None:
        """Laedt alle gespeicherten Alarm-Configs."""
        if not os.path.isdir(self._configs_dir):
            return
        for fname in os.listdir(self._configs_dir):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(self._configs_dir, fname)) as f:
                    data = json.load(f)
                config = AlarmConfig.from_dict(data)
                self._alarms[config.alarm_id] = config
                self._runtimes[config.alarm_id] = AlarmRuntime(
                    state=AlarmState.ARMED.value if config.schedule.enabled else AlarmState.IDLE.value,
                    next_trigger=self._compute_next_trigger(config),
                )
            except Exception as exc:
                _LOGGER.warning("Config load failed for %s: %s", fname, exc)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _compute_next_trigger(self, config: AlarmConfig) -> str:
        """Berechnet den naechsten Ausloesezeitpunkt."""
        if not config.schedule.enabled:
            return ""
        try:
            now = datetime.now(timezone.utc).astimezone()
            hour, minute = map(int, config.schedule.time.split(":"))

            # Naechsten passenden Tag finden
            for day_offset in range(8):
                candidate = now + timedelta(days=day_offset)
                trigger = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if trigger <= now:
                    continue
                day_name = trigger.strftime("%a").lower()
                if day_name in config.schedule.days:
                    return trigger.isoformat()
            return ""
        except Exception:
            return ""

    def get_dashboard(self) -> dict:
        """Dashboard-Daten: alle Alarme + Presets + Kurventypen."""
        from copilot_core.modules.sunrise_alarm.curves import get_all_curves

        alarms = self.list_alarms()
        active = [a for a in alarms if a.get("runtime", {}).get("state") in (
            AlarmState.RUNNING.value, AlarmState.SNOOZED.value,
        )]
        return {
            "alarms": alarms,
            "active_count": len(active),
            "total_count": len(alarms),
            "presets": self.list_presets(),
            "curves": get_all_curves(),
        }

    def status(self) -> Dict[str, Any]:
        """Get service status."""
        with self._lock:
            alarms = list(self._alarms.values())
        return {
            "total_alarms": len(alarms),
            "enabled": sum(1 for a in alarms if a.schedule.enabled),
            "running": sum(1 for a in alarms if self._runtimes.get(a.alarm_id, AlarmRuntime()).state == AlarmState.RUNNING.value),
            "snoozed": sum(1 for a in alarms if self._runtimes.get(a.alarm_id, AlarmRuntime()).state == AlarmState.SNOOZED.value),
            "sonos_available": self._sonos is not None,
        }


# Lineare Hilfsfunktion fuer Lautstaerke-Rampe
def _linear_fn(t: float) -> float:
    return max(0.0, min(1.0, t))


linear_fn = _linear_fn
