"""SonosHTTPClient — Python-Wrapper um node-sonos-http-api (Port 5005).

Alle Methoden nutzen HTTP GET (so funktioniert die node-sonos-http-api).
Bei Fehlern wird None zurueckgegeben, nie eine Exception geworfen.
"""

import logging
from typing import Optional
from urllib.parse import quote

import requests

_LOGGER = logging.getLogger(__name__)


class SonosHTTPClient:
    """Thread-safe HTTP-Client fuer node-sonos-http-api."""

    def __init__(self, base_url: str = "http://127.0.0.1:5005", timeout: int = 10):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()

    def _get(self, path: str, timeout: Optional[int] = None) -> Optional[dict | list | str]:
        """HTTP GET an node-sonos-http-api. Gibt parsed JSON oder None zurueck."""
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.get(url, timeout=timeout or self._timeout)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if "json" in ct:
                return resp.json()
            return resp.text
        except Exception as exc:
            _LOGGER.debug("Sonos HTTP GET %s failed: %s", path, exc)
            return None

    @staticmethod
    def _encode(value: str) -> str:
        """URL-encode einen Wert fuer Pfad-Segmente."""
        return quote(str(value), safe="")

    # -- System --

    def is_healthy(self) -> bool:
        """Prueft ob node-sonos-http-api erreichbar ist."""
        result = self._get("/zones", timeout=2)
        return result is not None

    def get_zones(self) -> Optional[list]:
        """Gibt Sonos-Topologie (Zone-Groups) zurueck."""
        return self._get("/zones")

    def get_rooms(self) -> list[str]:
        """Extrahiert alle Raum-Namen aus der Topologie."""
        zones = self.get_zones()
        if not zones or not isinstance(zones, list):
            return []
        rooms = []
        for zone in zones:
            members = zone.get("members", [])
            for member in members:
                name = member.get("roomName", "")
                if name:
                    rooms.append(name)
        return sorted(set(rooms))

    # -- Per-Room State --

    def get_state(self, room: str) -> Optional[dict]:
        """Aktueller Wiedergabestatus eines Raums."""
        return self._get(f"/{self._encode(room)}/state")

    # -- Playback Control --

    def play(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/play")

    def pause(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/pause")

    def playpause(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/playpause")

    def stop(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/stop")

    def next(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/next")

    def previous(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/previous")

    # -- Volume --

    def set_volume(self, room: str, vol: int) -> Optional[str]:
        """Setzt absolute Lautstaerke (0-100)."""
        vol = max(0, min(100, int(vol)))
        return self._get(f"/{self._encode(room)}/volume/{vol}")

    def adjust_volume(self, room: str, delta: int) -> Optional[str]:
        """Relative Lautstaerke-Aenderung (+/- delta)."""
        delta = int(delta)
        sign = f"+{delta}" if delta >= 0 else str(delta)
        return self._get(f"/{self._encode(room)}/volume/{sign}")

    def set_group_volume(self, room: str, vol: int) -> Optional[str]:
        """Setzt Gruppen-Lautstaerke."""
        vol = max(0, min(100, int(vol)))
        return self._get(f"/{self._encode(room)}/groupVolume/{vol}")

    def mute(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/mute")

    def unmute(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/unmute")

    def toggle_mute(self, room: str) -> Optional[str]:
        return self._get(f"/{self._encode(room)}/togglemute")

    # -- Favorites / Playlists --

    def get_favorites(self, room: str) -> Optional[list]:
        """Gibt Sonos-Favoriten zurueck (detailed)."""
        result = self._get(f"/{self._encode(room)}/favorites/detailed")
        if isinstance(result, dict):
            return result.get("favorites", [])
        return result if isinstance(result, list) else None

    def play_favorite(self, room: str, name: str) -> Optional[str]:
        """Spielt einen Sonos-Favoriten ab."""
        return self._get(f"/{self._encode(room)}/favorite/{self._encode(name)}")

    def play_playlist(self, room: str, name: str) -> Optional[str]:
        """Spielt eine Sonos-Playlist ab."""
        return self._get(f"/{self._encode(room)}/playlist/{self._encode(name)}")

    # -- Queue --

    def get_queue(self, room: str) -> Optional[list]:
        """Gibt die aktuelle Wiedergabeliste zurueck."""
        return self._get(f"/{self._encode(room)}/queue")

    def clear_queue(self, room: str) -> Optional[str]:
        """Leert die Wiedergabeliste."""
        return self._get(f"/{self._encode(room)}/clearqueue")

    # -- Grouping --

    def join(self, room: str, coordinator: str) -> Optional[str]:
        """Fuegt Raum einer Gruppe hinzu."""
        return self._get(f"/{self._encode(room)}/join/{self._encode(coordinator)}")

    def leave(self, room: str) -> Optional[str]:
        """Entfernt Raum aus Gruppe."""
        return self._get(f"/{self._encode(room)}/leave")

    # -- TTS --

    def say(self, room: str, text: str, volume: Optional[int] = None,
            language: str = "de-de") -> Optional[str]:
        """Text-to-Speech Durchsage in einem Raum."""
        encoded_text = self._encode(text)
        lang = self._encode(language)
        if volume is not None:
            vol = max(0, min(100, int(volume)))
            return self._get(f"/{self._encode(room)}/say/{encoded_text}/{lang}/{vol}")
        return self._get(f"/{self._encode(room)}/say/{encoded_text}/{lang}")

    def say_all(self, text: str, volume: Optional[int] = None,
                language: str = "de-de") -> Optional[str]:
        """Text-to-Speech Durchsage auf allen Playern."""
        encoded_text = self._encode(text)
        lang = self._encode(language)
        if volume is not None:
            vol = max(0, min(100, int(volume)))
            return self._get(f"/sayall/{encoded_text}/{lang}/{vol}")
        return self._get(f"/sayall/{encoded_text}/{lang}")

    # -- Presets --

    def apply_preset(self, name: str) -> Optional[str]:
        """Wendet ein Preset an (definiert in presets.json)."""
        return self._get(f"/preset/{self._encode(name)}")

    def list_presets(self) -> Optional[list]:
        """Listet verfuegbare Presets."""
        return self._get("/presets")

    # -- Sleep / Play Mode --

    def set_sleep(self, room: str, seconds: int) -> Optional[str]:
        """Setzt Sleep-Timer."""
        return self._get(f"/{self._encode(room)}/sleep/{int(seconds)}")

    def set_shuffle(self, room: str, on: bool) -> Optional[str]:
        """Setzt Shuffle-Modus."""
        state = "on" if on else "off"
        return self._get(f"/{self._encode(room)}/shuffle/{state}")

    def set_repeat(self, room: str, mode: str) -> Optional[str]:
        """Setzt Repeat-Modus (all|one|none)."""
        return self._get(f"/{self._encode(room)}/repeat/{self._encode(mode)}")

    # -- Global --

    def pause_all(self) -> Optional[str]:
        """Pausiert alle Player."""
        return self._get("/pauseall")

    def resume_all(self) -> Optional[str]:
        """Setzt alle Player fort."""
        return self._get("/resumeall")
