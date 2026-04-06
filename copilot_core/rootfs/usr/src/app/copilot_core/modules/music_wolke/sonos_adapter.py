"""Sonos Adapter — HTTP client for node-sonos-http-api."""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
import requests
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)


class SonosAdapter:
    """Adapter for node-sonos-http-api (port 5005)."""

    def __init__(self, base_url: str = "http://127.0.0.1:5005", timeout: int = 10):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()

    def _get(self, path: str) -> Optional[Any]:
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.get(url, timeout=self._timeout)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            return resp.json() if "json" in ct else resp.text
        except Exception as e:
            _LOGGER.debug("Sonos HTTP GET %s failed: %s", path, e)
            return None

    def is_healthy(self) -> bool:
        return self._get("/zones") is not None

    def get_zones(self) -> List[Dict[str, Any]]:
        result = self._get("/zones")
        return result if isinstance(result, list) else []

    def get_rooms(self) -> List[str]:
        zones = self.get_zones()
        rooms = []
        for zone in zones:
            for member in zone.get("members", []):
                name = member.get("roomName", "")
                if name and name not in rooms:
                    rooms.append(name)
        return sorted(rooms)

    def get_state(self, room: str) -> Optional[Dict[str, Any]]:
        return self._get(f"/{quote(room, safe='')}/state")

    def play(self, room: str) -> bool:
        return self._get(f"/{quote(room, safe='')}/play") is not None

    def pause(self, room: str) -> bool:
        return self._get(f"/{quote(room, safe='')}/pause") is not None

    def set_volume(self, room: str, volume: int) -> bool:
        return self._get(f"/{quote(room, safe='')}/volume/{volume}") is not None

    def play_favorite(self, room: str, favorite: str) -> bool:
        return self._get(f"/{quote(room, safe='')}/favorite/{quote(favorite, safe='')}") is not None

    def get_favorites(self, room: str) -> List[str]:
        state = self.get_state(room)
        if not state:
            return []
        return state.get("favorite", "") or []

    def transfer_to(self, from_room: str, to_room: str) -> bool:
        state = self.get_state(from_room)
        if not state:
            return False
        if state.get("state") == "PLAYING":
            self.pause(from_room)
            favorite = state.get("favorite")
            if favorite:
                return self.play_favorite(to_room, favorite)
            self.play(to_room)
            return True
        return False
