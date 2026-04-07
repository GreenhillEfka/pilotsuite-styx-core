"""Alarm/Wecker Datenmodelle.

Enums fuer Modus, Zustand und Kurventyp.
Dataclasses fuer Schedule, Licht-, Musik- und Alarm-Konfiguration.
CCT-zu-RGB Lookup-Tabelle fuer Lampen ohne native Farbtemperatur.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class AlarmMode(str, Enum):
    """Wecker-Modus."""

    WAKE = "wake"    # Aufwachen — Sunrise
    SLEEP = "sleep"  # Einschlafen — Sunset


class AlarmState(str, Enum):
    """Zustand eines Alarm-Laufs."""

    IDLE = "idle"
    ARMED = "armed"
    RUNNING = "running"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CurveType(str, Enum):
    """Verfuegbare Helligkeits-/Lautstärke-Kurventypen."""

    LINEAR = "linear"
    QUADRATIC = "quadratic"        # Weber-Fechner (t^2)
    SIGMOID = "sigmoid"            # S-Kurve (logistisch)
    PHILIPS_HUE = "philips_hue"    # 3-Phasen (Philips-Referenz)
    EXPONENTIAL = "exponential"    # Exponentielle Kurve (base=10)


# --- CCT-zu-RGB Lookup-Tabelle (Kelvin → RGB) ---
# Fuer Lampen ohne color_temp_kelvin Unterstuetzung.
# Werte basieren auf CIE 1931 Approximation (Tanner Helland).

CCT_RGB_TABLE: Dict[int, tuple[int, int, int]] = {
    1800: (255, 130, 46),
    2000: (255, 141, 60),
    2200: (255, 152, 75),
    2400: (255, 163, 90),
    2700: (255, 180, 114),
    3000: (255, 194, 133),
    3500: (255, 209, 163),
    4000: (255, 224, 189),
    4500: (255, 236, 211),
    5000: (255, 244, 229),
    5500: (255, 250, 244),
    6000: (255, 255, 255),
    6500: (248, 251, 255),
}

# Sortierte Kelvin-Werte fuer Interpolation
_CCT_KEYS = sorted(CCT_RGB_TABLE.keys())


def cct_to_rgb(kelvin: int) -> tuple[int, int, int]:
    """Konvertiert Farbtemperatur (Kelvin) zu RGB.

    Interpoliert linear zwischen den Stuetzstellen der Lookup-Tabelle.
    """
    kelvin = max(_CCT_KEYS[0], min(kelvin, _CCT_KEYS[-1]))

    if kelvin in CCT_RGB_TABLE:
        return CCT_RGB_TABLE[kelvin]

    # Stuetzstellen finden
    lower_k = _CCT_KEYS[0]
    upper_k = _CCT_KEYS[-1]
    for i, k in enumerate(_CCT_KEYS):
        if k > kelvin:
            upper_k = k
            lower_k = _CCT_KEYS[i - 1]
            break

    # Linear interpolieren
    t = (kelvin - lower_k) / (upper_k - lower_k) if upper_k != lower_k else 0.0
    r1, g1, b1 = CCT_RGB_TABLE[lower_k]
    r2, g2, b2 = CCT_RGB_TABLE[upper_k]
    return (
        int(r1 + t * (r2 - r1)),
        int(g1 + t * (g2 - g1)),
        int(b1 + t * (b2 - b1)),
    )


# --- Dataclasses ---


@dataclass
class AlarmSchedule:
    """Zeitplan fuer einen Alarm."""

    time: str = "07:00"  # HH:MM
    days: List[str] = field(default_factory=lambda: [
        "mon", "tue", "wed", "thu", "fri",
    ])
    enabled: bool = True
    one_shot: bool = False
    timezone: str = "Europe/Berlin"


@dataclass
class LightConfig:
    """Lichtwecker-Konfiguration."""

    entity_ids: List[str] = field(default_factory=list)
    curve_type: str = "quadratic"      # CurveType value
    duration_minutes: int = 30         # Sunrise: 30, Sunset: 45
    brightness_start_pct: int = 0      # Wake: 0→100, Sleep: 100→0
    brightness_end_pct: int = 100
    cct_start_k: int = 1800            # Warm-Start (Kelvin)
    cct_end_k: int = 5000              # Tageslicht-End (Kelvin)
    step_interval_s: float = 10.0      # Sekunden zwischen Steps
    use_rgb_fallback: bool = False     # CCT-RGB Tabelle nutzen
    transition_s: int = 2              # HA light.turn_on Transition

    @property
    def total_steps(self) -> int:
        """Anzahl der Steps fuer den gesamten Verlauf."""
        if self.step_interval_s <= 0:
            return 1
        return max(1, int((self.duration_minutes * 60) / self.step_interval_s))


@dataclass
class MusicConfig:
    """Musik-Konfiguration fuer Alarm."""

    source_type: str = "favorite"   # favorite | playlist | uri
    source_name: str = ""           # Sonos Favorite/Playlist Name
    sonos_room: str = ""            # Sonos-Raum
    media_player_entity: str = ""   # Alternativ: HA media_player Entity
    volume_start_pct: int = 5       # Wake: 5→40, Sleep: 40→5
    volume_end_pct: int = 40
    shuffle: bool = True
    sleep_timer_s: int = 0          # Auto-Stop nach X Sekunden (0=aus)
    enabled: bool = True


@dataclass
class AlarmConfig:
    """Vollstaendige Alarm-Konfiguration."""

    alarm_id: str = ""
    name: str = "Wecker"
    person_id: str = ""          # Person.id
    mode: str = "wake"           # AlarmMode value
    zone_id: str = ""            # Habitus-Zone
    schedule: AlarmSchedule = field(default_factory=AlarmSchedule)
    light: LightConfig = field(default_factory=LightConfig)
    music: MusicConfig = field(default_factory=MusicConfig)
    snooze_minutes: int = 9      # Standard-Snooze: 9 Minuten

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert die Konfiguration."""
        return {
            "alarm_id": self.alarm_id,
            "name": self.name,
            "person_id": self.person_id,
            "mode": self.mode,
            "zone_id": self.zone_id,
            "schedule": {
                "time": self.schedule.time,
                "days": self.schedule.days,
                "enabled": self.schedule.enabled,
                "one_shot": self.schedule.one_shot,
                "timezone": self.schedule.timezone,
            },
            "light": {
                "entity_ids": self.light.entity_ids,
                "curve_type": self.light.curve_type,
                "duration_minutes": self.light.duration_minutes,
                "brightness_start_pct": self.light.brightness_start_pct,
                "brightness_end_pct": self.light.brightness_end_pct,
                "cct_start_k": self.light.cct_start_k,
                "cct_end_k": self.light.cct_end_k,
                "step_interval_s": self.light.step_interval_s,
                "use_rgb_fallback": self.light.use_rgb_fallback,
                "transition_s": self.light.transition_s,
            },
            "music": {
                "source_type": self.music.source_type,
                "source_name": self.music.source_name,
                "sonos_room": self.music.sonos_room,
                "media_player_entity": self.music.media_player_entity,
                "volume_start_pct": self.music.volume_start_pct,
                "volume_end_pct": self.music.volume_end_pct,
                "shuffle": self.music.shuffle,
                "sleep_timer_s": self.music.sleep_timer_s,
                "enabled": self.music.enabled,
            },
            "snooze_minutes": self.snooze_minutes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlarmConfig":
        """Deserialisiert die Konfiguration."""
        sched_data = data.get("schedule", {})
        light_data = data.get("light", {})
        music_data = data.get("music", {})
        return cls(
            alarm_id=data.get("alarm_id", ""),
            name=data.get("name", "Wecker"),
            person_id=data.get("person_id", ""),
            mode=data.get("mode", "wake"),
            zone_id=data.get("zone_id", ""),
            schedule=AlarmSchedule(
                time=sched_data.get("time", "07:00"),
                days=sched_data.get("days", ["mon", "tue", "wed", "thu", "fri"]),
                enabled=sched_data.get("enabled", True),
                one_shot=sched_data.get("one_shot", False),
                timezone=sched_data.get("timezone", "Europe/Berlin"),
            ),
            light=LightConfig(
                entity_ids=light_data.get("entity_ids", []),
                curve_type=light_data.get("curve_type", "quadratic"),
                duration_minutes=light_data.get("duration_minutes", 30),
                brightness_start_pct=light_data.get("brightness_start_pct", 0),
                brightness_end_pct=light_data.get("brightness_end_pct", 100),
                cct_start_k=light_data.get("cct_start_k", 1800),
                cct_end_k=light_data.get("cct_end_k", 5000),
                step_interval_s=light_data.get("step_interval_s", 10.0),
                use_rgb_fallback=light_data.get("use_rgb_fallback", False),
                transition_s=light_data.get("transition_s", 2),
            ),
            music=MusicConfig(
                source_type=music_data.get("source_type", "favorite"),
                source_name=music_data.get("source_name", ""),
                sonos_room=music_data.get("sonos_room", ""),
                media_player_entity=music_data.get("media_player_entity", ""),
                volume_start_pct=music_data.get("volume_start_pct", 5),
                volume_end_pct=music_data.get("volume_end_pct", 40),
                shuffle=music_data.get("shuffle", True),
                sleep_timer_s=music_data.get("sleep_timer_s", 0),
                enabled=music_data.get("enabled", True),
            ),
            snooze_minutes=data.get("snooze_minutes", 9),
        )


@dataclass
class AlarmRuntime:
    """Laufzeit-Zustand eines aktiven Alarms."""

    state: str = "idle"          # AlarmState value
    progress_pct: float = 0.0
    current_brightness: int = 0
    current_volume: int = 0
    current_cct: int = 1800
    step_count: int = 0
    total_steps: int = 0
    snooze_count: int = 0
    started_at: str = ""
    next_trigger: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert den Laufzeit-Zustand."""
        return {
            "state": self.state,
            "progress_pct": round(self.progress_pct, 1),
            "current_brightness": self.current_brightness,
            "current_volume": self.current_volume,
            "current_cct": self.current_cct,
            "step_count": self.step_count,
            "total_steps": self.total_steps,
            "snooze_count": self.snooze_count,
            "started_at": self.started_at,
            "next_trigger": self.next_trigger,
        }


@dataclass
class AlarmPreset:
    """Vordefiniertes Alarm-Preset."""

    preset_id: str
    label: str
    description: str = ""
    mode: str = "wake"
    light: LightConfig = field(default_factory=LightConfig)
    music: MusicConfig = field(default_factory=MusicConfig)
    snooze_minutes: int = 9
