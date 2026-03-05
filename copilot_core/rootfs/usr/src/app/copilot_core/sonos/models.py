"""Sonos Datenmodelle."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SonosPlayer:
    """Ein Sonos-Lautsprecher."""

    room_name: str
    entity_id: str = ""
    zone_id: str = ""
    uuid: str = ""


@dataclass
class SonosZone:
    """Eine Sonos-Zone (1+ Raeume)."""

    zone_id: str
    primary_room: str
    secondary_rooms: list[str] = field(default_factory=list)
    fallback_config: Optional["FallbackConfig"] = None


@dataclass
class SonosPreset:
    """Gespeichertes Sonos-Preset."""

    preset_id: str
    label: str
    players: list[str] = field(default_factory=list)
    favorite: str = ""
    playlist: str = ""
    shuffle: bool = False
    zone_id: str = ""
    state: str = "stopped"


@dataclass
class SonosState:
    """Aktueller Wiedergabestatus eines Sonos-Players."""

    playback_state: str = "stopped"
    volume: int = 0
    current_track: dict = field(default_factory=lambda: {
        "title": "",
        "artist": "",
        "album": "",
        "art_uri": "",
        "duration": 0,
    })
    mute: bool = False
    play_mode: str = "NORMAL"
    equalizer: dict = field(default_factory=dict)


@dataclass
class TimeVolumeProfile:
    """Zeitabhaengiges Lautstaerke-Profil."""

    name: str
    start_hour: int
    end_hour: int
    volume_pct: int
    max_volume_pct: int
    label_de: str


@dataclass
class FallbackConfig:
    """Fallback-Wiedergabe-Konfiguration fuer eine Zone."""

    zone_id: str
    fallback_type: str = "favorite"  # favorite | playlist | uri
    favorite_name: str = ""
    playlist_name: str = ""
    uri: str = ""
    volume_pct: int = 25
    shuffle: bool = True
