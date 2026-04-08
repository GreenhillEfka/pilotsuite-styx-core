"""SonosIntelligence — Intelligenz-Schicht ueber dem SonosHTTPClient.

Features:
- Zeitabhaengige Lautstaerke-Profile (4 Tageszeiten)
- Fallback-Playlists pro Zone
- Praesenz → Auto-Play
- Preset-Management (persistiert als JSON)
- Zone Registry
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from copilot_core.sonos.client import SonosHTTPClient
from copilot_core.sonos.models import (
    FallbackConfig,
    SonosPreset,
    SonosZone,
    TimeVolumeProfile,
)

_LOGGER = logging.getLogger(__name__)

# Standard-Lautstaerke-Profile
_DEFAULT_PROFILES: list[TimeVolumeProfile] = [
    TimeVolumeProfile("morning", 6, 9, 20, 40, "Morgen \u2014 leise"),
    TimeVolumeProfile("day", 9, 18, 35, 70, "Tag \u2014 normal"),
    TimeVolumeProfile("evening", 18, 22, 25, 50, "Abend \u2014 gedimmt"),
    TimeVolumeProfile("night", 22, 6, 10, 25, "Nacht \u2014 sehr leise"),
]


class SonosIntelligence:
    """Intelligente Sonos-Steuerung mit zeitbasierter Lautstaerke und Presets."""

    def __init__(self, client: SonosHTTPClient, presets_dir: str = "/data/sonos_presets"):
        self._client = client
        self._presets_dir = presets_dir
        self._profiles = list(_DEFAULT_PROFILES)
        self._zones: dict[str, SonosZone] = {}
        self._fallbacks: dict[str, FallbackConfig] = {}
        os.makedirs(self._presets_dir, exist_ok=True)

    # -- Zeitabhaengige Lautstaerke --

    def get_current_volume_profile(self) -> TimeVolumeProfile:
        """Gibt das aktuelle Lautstaerke-Profil zurueck."""
        hour = datetime.now(timezone.utc).astimezone().hour
        for profile in self._profiles:
            if profile.start_hour < profile.end_hour:
                if profile.start_hour <= hour < profile.end_hour:
                    return profile
            else:
                # Ueber Mitternacht (z.B. 22-06)
                if hour >= profile.start_hour or hour < profile.end_hour:
                    return profile
        return self._profiles[1]  # Fallback: day

    def get_time_based_volume(self, zone_id: Optional[str] = None) -> int:
        """Gibt die empfohlene Lautstaerke fuer die aktuelle Tageszeit zurueck."""
        return self.get_current_volume_profile().volume_pct

    def apply_volume_ceiling(self, zone_id: str, requested_vol: int) -> int:
        """Begrenzt die Lautstaerke auf das Tageszeit-Maximum."""
        profile = self.get_current_volume_profile()
        return min(requested_vol, profile.max_volume_pct)

    def update_volume_profile(self, name: str, **kwargs) -> bool:
        """Aktualisiert ein Lautstaerke-Profil."""
        for i, profile in enumerate(self._profiles):
            if profile.name == name:
                for key, value in kwargs.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                self._profiles[i] = profile
                return True
        return False

    def get_all_volume_profiles(self) -> list[dict]:
        """Gibt alle Lautstaerke-Profile als dicts zurueck."""
        current = self.get_current_volume_profile()
        result = []
        for p in self._profiles:
            d = {
                "name": p.name,
                "start_hour": p.start_hour,
                "end_hour": p.end_hour,
                "volume_pct": p.volume_pct,
                "max_volume_pct": p.max_volume_pct,
                "label_de": p.label_de,
                "active": p.name == current.name,
            }
            result.append(d)
        return result

    # -- Fallback-Playlists --

    def set_fallback(self, zone_id: str, config: FallbackConfig) -> None:
        """Setzt die Fallback-Konfiguration fuer eine Zone."""
        self._fallbacks[zone_id] = config

    def get_fallback(self, zone_id: str) -> Optional[FallbackConfig]:
        """Gibt die Fallback-Konfiguration einer Zone zurueck."""
        return self._fallbacks.get(zone_id)

    def start_fallback(self, zone_id: str) -> dict:
        """Startet Fallback-Wiedergabe in einer Zone."""
        zone = self._zones.get(zone_id)
        if not zone:
            return {"action": "no_zone", "zone_id": zone_id}

        fb = self._fallbacks.get(zone_id)
        if not fb:
            return {"action": "no_fallback", "zone_id": zone_id}

        room = zone.primary_room
        vol = self.get_time_based_volume(zone_id)

        self._client.set_volume(room, vol)

        if fb.shuffle:
            self._client.set_shuffle(room, True)

        if fb.fallback_type == "favorite" and fb.favorite_name:
            self._client.play_favorite(room, fb.favorite_name)
        elif fb.fallback_type == "playlist" and fb.playlist_name:
            self._client.play_playlist(room, fb.playlist_name)
        elif fb.fallback_type == "uri" and fb.uri:
            # URI-Wiedergabe nicht direkt von node-sonos-http-api unterstuetzt,
            # Fallback auf play()
            self._client.play(room)
        else:
            return {"action": "invalid_fallback", "zone_id": zone_id}

        return {
            "action": "started_fallback",
            "zone_id": zone_id,
            "room": room,
            "volume": vol,
            "source": fb.favorite_name or fb.playlist_name or fb.uri,
        }

    # -- Praesenz → Auto-Play --

    def on_zone_presence(self, zone_id: str, person_id: str) -> dict:
        """Reagiert auf Praesenz in einer Zone.

        Prueft:
        1. Gibt es schon eine Wiedergabe? → skip
        2. Hat die Zone einen Sonos-Player?
        3. → Starte Fallback mit zeitbasierter Lautstaerke
        """
        zone = self._zones.get(zone_id)
        if not zone:
            return {"action": "no_player", "zone_id": zone_id, "person_id": person_id}

        # Pruefen ob schon etwas laeuft
        state = self._client.get_state(zone.primary_room)
        if state and isinstance(state, dict):
            playback = state.get("playbackState", state.get("currentState", ""))
            if playback.upper() in ("PLAYING", "TRANSITIONING"):
                return {
                    "action": "already_playing",
                    "zone_id": zone_id,
                    "person_id": person_id,
                }

        # Fallback starten
        if zone_id not in self._fallbacks:
            return {"action": "no_fallback", "zone_id": zone_id, "person_id": person_id}

        result = self.start_fallback(zone_id)
        result["person_id"] = person_id
        return result

    # -- Presets --

    def _preset_path(self, preset_id: str) -> str:
        """Pfad zur Preset-Datei."""
        safe_id = "".join(c for c in preset_id if c.isalnum() or c in "-_")
        return os.path.join(self._presets_dir, f"{safe_id}.json")

    def save_preset(self, preset: SonosPreset) -> bool:
        """Speichert ein Preset als JSON."""
        try:
            data = {
                "preset_id": preset.preset_id,
                "label": preset.label,
                "players": preset.players,
                "favorite": preset.favorite,
                "playlist": preset.playlist,
                "shuffle": preset.shuffle,
                "zone_id": preset.zone_id,
                "state": preset.state,
            }
            path = self._preset_path(preset.preset_id)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as exc:
            _LOGGER.warning("Preset save failed: %s", exc)
            return False

    def get_preset(self, preset_id: str) -> Optional[SonosPreset]:
        """Laedt ein Preset."""
        path = self._preset_path(preset_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return SonosPreset(**data)
        except Exception as exc:
            _LOGGER.warning("Preset load failed: %s", exc)
            return None

    def delete_preset(self, preset_id: str) -> bool:
        """Loescht ein Preset."""
        path = self._preset_path(preset_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def list_presets(self) -> list[dict]:
        """Listet alle gespeicherten Presets."""
        presets = []
        if not os.path.isdir(self._presets_dir):
            return presets
        for fname in sorted(os.listdir(self._presets_dir)):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(self._presets_dir, fname)) as f:
                    data = json.load(f)
                presets.append(data)
            except Exception:
                continue
        return presets

    def apply_preset(self, preset_id: str) -> bool:
        """Wendet ein gespeichertes Preset an."""
        preset = self.get_preset(preset_id)
        if not preset:
            return False

        result = self._client.apply_preset(preset.preset_id)
        if result is None:
            # Fallback: Manuell anwenden
            for player in preset.players:
                if preset.favorite:
                    self._client.play_favorite(player, preset.favorite)
                elif preset.playlist:
                    self._client.play_playlist(player, preset.playlist)
            if preset.shuffle:
                for player in preset.players:
                    self._client.set_shuffle(player, True)
        return True

    def create_zone_preset(self, zone_id: str, label: str,
                           favorite: str = "") -> Optional[SonosPreset]:
        """Erzeugt ein Preset aus Zone-Mapping mit zeitbasierter Lautstaerke."""
        zone = self._zones.get(zone_id)
        if not zone:
            return None

        players = [zone.primary_room] + zone.secondary_rooms
        preset = SonosPreset(
            preset_id=f"zone_{zone_id}_{label.lower().replace(' ', '_')}",
            label=label,
            players=players,
            favorite=favorite,
            zone_id=zone_id,
        )
        self.save_preset(preset)
        return preset

    # -- Zone Registry --

    def register_zone(self, zone: SonosZone) -> None:
        """Registriert eine Sonos-Zone."""
        self._zones[zone.zone_id] = zone

    def get_zone(self, zone_id: str) -> Optional[SonosZone]:
        """Gibt eine registrierte Zone zurueck."""
        return self._zones.get(zone_id)

    def get_all_zones(self) -> list[dict]:
        """Gibt alle registrierten Zonen als dicts zurueck."""
        return [
            {
                "zone_id": z.zone_id,
                "primary_room": z.primary_room,
                "secondary_rooms": z.secondary_rooms,
                "has_fallback": z.zone_id in self._fallbacks,
            }
            for z in self._zones.values()
        ]
