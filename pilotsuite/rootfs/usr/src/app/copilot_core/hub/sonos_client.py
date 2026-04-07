"""Sonos HTTP API Client — via jishi/node-sonos-http-api (Port 5005).

Steuert Sonos-Lautsprecher ueber die lokal installierte
node-sonos-http-api (https://github.com/jishi/node-sonos-http-api).

REST-Endpunkte:  GET http://{host}:5005/{Room}/{action}[/{param}]
Zonen-Topologie: GET http://{host}:5005/zones

Architektur:
  PilotSuite Core --> node-sonos-http-api:5005 --> Sonos Speaker (LAN)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_JISHI_HOST = "localhost"
DEFAULT_JISHI_PORT = 5005
DEFAULT_TIMEOUT = 8.0


@dataclass
class SonosSpeaker:
    """Repraesentiert einen Sonos-Lautsprecher aus der jishi-Topologie."""
    room_name: str
    uuid: str = ""
    coordinator_uuid: str = ""
    state: str = "STOPPED"
    volume: int = 0
    muted: bool = False
    track_title: str = ""
    track_artist: str = ""
    track_album: str = ""
    track_uri: str = ""
    elapsed_seconds: int = 0
    duration_seconds: int = 0
    group_members: list[str] = field(default_factory=list)
    is_coordinator: bool = False
    last_seen: float = field(default_factory=time.time)


class SonosCloudClient:
    """Client fuer jishi/node-sonos-http-api.

    Alle Sonos-Steuerung laeuft ueber simple HTTP GET/POST Requests
    an die lokal laufende node-sonos-http-api Instanz.

    API-Pattern:
      GET  /{Room}/play
      GET  /{Room}/pause
      GET  /{Room}/volume/{level}
      GET  /{Room}/favorite/{name}
      GET  /{Room}/say/{text}/{lang}
      GET  /{Room}/join/{OtherRoom}
      GET  /{Room}/leave
      GET  /zones
      GET  /favorites
      GET  /playlists
    """

    def __init__(
        self,
        host: str = DEFAULT_JISHI_HOST,
        port: int = DEFAULT_JISHI_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._base_url = f"http://{host}:{port}"
        self._speakers: dict[str, SonosSpeaker] = {}
        self._lock = threading.Lock()

        # Requests session mit retry
        self._session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[502, 503])
        self._session.mount("http://", HTTPAdapter(max_retries=retry))

    # ── HTTP Helpers ───────────────────────────────────────────────

    def _get(self, path: str) -> dict[str, Any] | list | None:
        """GET-Request an jishi API, gibt JSON oder None zurueck."""
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.get(url, timeout=self._timeout)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if "json" in ct or resp.text.strip().startswith(("{", "[")):
                return resp.json()
            return {"status": "ok", "response": resp.text.strip()}
        except requests.Timeout:
            logger.warning("Sonos API Timeout: %s", path)
            return None
        except requests.RequestException as exc:
            logger.error("Sonos API Fehler %s: %s", path, exc)
            return None

    def _room_cmd(self, room: str, action: str) -> dict[str, Any] | None:
        """Room-basierter Befehl: GET /{Room}/{action}."""
        encoded_room = quote(room, safe="")
        result = self._get(f"/{encoded_room}/{action}")
        if isinstance(result, dict):
            return result
        return {"status": "ok"} if result is not None else None

    # ── Zone Discovery ─────────────────────────────────────────────

    def discover_zones(self) -> list[dict[str, Any]]:
        """Hole komplette Sonos-Topologie via GET /zones.

        Aktualisiert den internen Speaker-Cache.
        Gibt die rohe Zone-Liste zurueck.
        """
        data = self._get("/zones")
        if not isinstance(data, list):
            logger.warning("Zone-Discovery fehlgeschlagen oder leere Antwort")
            return []

        with self._lock:
            self._speakers.clear()
            for zone in data:
                coordinator = zone.get("coordinator", {})
                coord_name = coordinator.get("roomName", "Unknown")
                coord_uuid = coordinator.get("uuid", "")
                coord_state = coordinator.get("state", {})

                members = zone.get("members", [])
                member_names = [m.get("roomName", "") for m in members]

                for member in members:
                    room_name = member.get("roomName", "")
                    if not room_name:
                        continue

                    current_track = coord_state.get("currentTrack", {})
                    playback = coord_state.get("playbackState", "STOPPED")

                    speaker = SonosSpeaker(
                        room_name=room_name,
                        uuid=member.get("uuid", ""),
                        coordinator_uuid=coord_uuid,
                        state=playback,
                        volume=member.get("state", {}).get("volume", 0),
                        muted=member.get("state", {}).get("mute", False),
                        track_title=current_track.get("title", ""),
                        track_artist=current_track.get("artist", ""),
                        track_album=current_track.get("album", ""),
                        track_uri=current_track.get("uri", ""),
                        elapsed_seconds=current_track.get("elapsedTime", 0),
                        duration_seconds=current_track.get("duration", 0),
                        group_members=member_names,
                        is_coordinator=(room_name == coord_name),
                    )
                    self._speakers[room_name] = speaker

        logger.info("Sonos Discovery: %d Speaker gefunden", len(self._speakers))
        return data

    def get_speakers(self) -> list[SonosSpeaker]:
        """Alle bekannten Speaker (aus letzter Discovery)."""
        with self._lock:
            return list(self._speakers.values())

    def get_speaker(self, room_name: str) -> Optional[SonosSpeaker]:
        """Speaker nach Room-Name."""
        return self._speakers.get(room_name)

    # ── Playback Control ───────────────────────────────────────────

    def play(self, room: str) -> bool:
        """Starte Wiedergabe."""
        return self._room_cmd(room, "play") is not None

    def pause(self, room: str) -> bool:
        """Pausiere Wiedergabe."""
        return self._room_cmd(room, "pause") is not None

    def stop(self, room: str) -> bool:
        """Stoppe Wiedergabe (= Pause bei Sonos)."""
        return self._room_cmd(room, "pause") is not None

    def next_track(self, room: str) -> bool:
        """Naechster Track."""
        return self._room_cmd(room, "next") is not None

    def previous_track(self, room: str) -> bool:
        """Vorheriger Track."""
        return self._room_cmd(room, "previous") is not None

    def toggle(self, room: str) -> bool:
        """Toggle Play/Pause."""
        return self._room_cmd(room, "toggle") is not None

    # ── Volume Control ─────────────────────────────────────────────

    def set_volume(self, room: str, volume: int) -> bool:
        """Setze Lautstaerke (0-100)."""
        volume = max(0, min(100, volume))
        return self._room_cmd(room, f"volume/{volume}") is not None

    def get_volume(self, room: str) -> int:
        """Hole aktuelle Lautstaerke aus Cache."""
        speaker = self._speakers.get(room)
        return speaker.volume if speaker else 0

    def volume_up(self, room: str, step: int = 5) -> bool:
        """Lautstaerke erhoehen."""
        current = self.get_volume(room)
        return self.set_volume(room, min(100, current + step))

    def volume_down(self, room: str, step: int = 5) -> bool:
        """Lautstaerke verringern."""
        current = self.get_volume(room)
        return self.set_volume(room, max(0, current - step))

    def set_mute(self, room: str, muted: bool) -> bool:
        """Mute/Unmute."""
        action = "mute" if muted else "unmute"
        return self._room_cmd(room, action) is not None

    def group_volume(self, room: str, volume: int) -> bool:
        """Setze Gruppen-Lautstaerke (alle Speaker der Gruppe)."""
        volume = max(0, min(100, volume))
        return self._room_cmd(room, f"groupVolume/{volume}") is not None

    # ── Favorites / Playlists ──────────────────────────────────────

    def get_favorites(self) -> list[dict[str, Any]]:
        """Hole Sonos-Favoriten."""
        data = self._get("/favorites")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("favorites", [])
        return []

    def play_favorite(self, room: str, favorite_name: str) -> bool:
        """Spiele einen Favoriten ab."""
        encoded = quote(favorite_name, safe="")
        return self._room_cmd(room, f"favorite/{encoded}") is not None

    def get_playlists(self) -> list[dict[str, Any]]:
        """Hole Sonos-Playlists."""
        data = self._get("/playlists")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("playlists", [])
        return []

    def play_playlist(self, room: str, playlist_name: str) -> bool:
        """Spiele eine Playlist ab."""
        encoded = quote(playlist_name, safe="")
        return self._room_cmd(room, f"playlist/{encoded}") is not None

    # ── URI / Stream Playback ──────────────────────────────────────

    def play_uri(self, room: str, uri: str) -> bool:
        """Spiele URI direkt ab (Radio-Stream, einzelner Track)."""
        encoded = quote(uri, safe="")
        return self._room_cmd(room, f"setavtransporturi/{encoded}") is not None

    def play_clip(self, room: str, uri: str, volume: int | None = None) -> bool:
        """Spiele Audio-Clip ab (ueberlagert aktuelle Wiedergabe, setzt danach fort)."""
        encoded = quote(uri, safe="")
        action = f"clip/{encoded}"
        if volume is not None:
            action += f"/{max(0, min(100, volume))}"
        return self._room_cmd(room, action) is not None

    # ── TTS / Say ──────────────────────────────────────────────────

    def say(
        self,
        room: str,
        text: str,
        language: str = "de-de",
        volume: int | None = None,
    ) -> bool:
        """Text-to-Speech Ansage in einem Raum.

        Nutzt die integrierte TTS-Engine von node-sonos-http-api.
        """
        encoded_text = quote(text, safe="")
        action = f"say/{encoded_text}/{language}"
        if volume is not None:
            action += f"/{max(0, min(100, volume))}"
        return self._room_cmd(room, action) is not None

    def say_all(self, text: str, language: str = "de-de", volume: int | None = None) -> bool:
        """TTS Ansage auf allen Speakern."""
        encoded_text = quote(text, safe="")
        action = f"sayall/{encoded_text}/{language}"
        if volume is not None:
            action += f"/{max(0, min(100, volume))}"
        return self._get(f"/{action}") is not None

    # ── Speaker Grouping (Musikwolke) ──────────────────────────────

    def join(self, room: str, target_room: str) -> bool:
        """Fuege Room einer bestehenden Gruppe hinzu.

        Der Room uebernimmt die Wiedergabe von target_room.
        """
        encoded_target = quote(target_room, safe="")
        return self._room_cmd(room, f"join/{encoded_target}") is not None

    def leave(self, room: str) -> bool:
        """Entferne Room aus seiner Gruppe (wird wieder eigenstaendig)."""
        return self._room_cmd(room, "leave") is not None

    def create_musikwolke(self, rooms: list[str]) -> bool:
        """Erstelle Musikwolke — gruppiere alle Raeume.

        Der erste Raum wird Coordinator, alle anderen joinen.
        """
        if len(rooms) < 2:
            logger.warning("Musikwolke braucht mindestens 2 Raeume")
            return False

        coordinator = rooms[0]
        success = True
        for room in rooms[1:]:
            if not self.join(room, coordinator):
                logger.error("Musikwolke: %s konnte %s nicht joinen", room, coordinator)
                success = False

        if success:
            logger.info("Musikwolke erstellt: %s (Coordinator: %s)", rooms, coordinator)
        return success

    def dissolve_musikwolke(self, rooms: list[str]) -> bool:
        """Loese Musikwolke auf — alle Speaker werden eigenstaendig."""
        success = True
        for room in rooms:
            if not self.leave(room):
                success = False

        if success:
            logger.info("Musikwolke aufgeloest: %s", rooms)
        return success

    def follow_user(
        self,
        user_room: str,
        previous_room: str | None = None,
        musikwolke_rooms: list[str] | None = None,
    ) -> bool:
        """Musikwolke folgt dem User in einen neuen Raum.

        1. Neuer Raum joint die Gruppe
        2. Optional: Alter Raum verlaesst die Gruppe (wenn kein anderer User dort)

        Args:
            user_room: Raum, in den der User gewechselt hat
            previous_room: Raum, den der User verlassen hat (optional)
            musikwolke_rooms: Aktuelle Musikwolke-Mitglieder (optional)
        """
        if musikwolke_rooms and len(musikwolke_rooms) > 0:
            # Join zum Coordinator (erster Raum der Wolke)
            coordinator = musikwolke_rooms[0]
            if user_room != coordinator:
                if not self.join(user_room, coordinator):
                    return False
        else:
            # Keine bestehende Wolke — nichts zu joinen
            logger.debug("Keine aktive Musikwolke fuer follow_user")
            return True

        # Alten Raum optional entfernen
        if previous_room and previous_room != user_room:
            if musikwolke_rooms and previous_room in musikwolke_rooms:
                self.leave(previous_room)
                logger.info(
                    "Musikwolke: %s → %s (verlassen: %s)",
                    previous_room, user_room, previous_room,
                )

        return True

    # ── Queue Management ───────────────────────────────────────────

    def clear_queue(self, room: str) -> bool:
        """Loesche die Wiedergabe-Queue."""
        return self._room_cmd(room, "clearqueue") is not None

    def shuffle(self, room: str, enabled: bool) -> bool:
        """Shuffle an/aus."""
        action = "shuffle/on" if enabled else "shuffle/off"
        return self._room_cmd(room, action) is not None

    def repeat(self, room: str, mode: str = "all") -> bool:
        """Repeat-Modus (all, one, none)."""
        return self._room_cmd(room, f"repeat/{mode}") is not None

    def crossfade(self, room: str, enabled: bool) -> bool:
        """Crossfade an/aus."""
        action = "crossfade/on" if enabled else "crossfade/off"
        return self._room_cmd(room, action) is not None

    # ── Sleep Timer ────────────────────────────────────────────────

    def sleep(self, room: str, seconds: int) -> bool:
        """Setze Sleep-Timer (Sekunden). 0 = deaktivieren."""
        if seconds <= 0:
            # Disable sleep timer
            return self._room_cmd(room, "sleep/off") is not None
        # Convert to HH:MM:SS
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return self._room_cmd(room, f"sleep/{h:02d}:{m:02d}:{s:02d}") is not None

    # ── Transport Info (cached from discover_zones) ────────────────

    def get_state(self, room: str) -> dict[str, Any]:
        """Hole aktuellen State eines Raums via GET /{room}/state."""
        result = self._room_cmd(room, "state")
        if result:
            # Update lokalen Cache
            with self._lock:
                speaker = self._speakers.get(room)
                if speaker:
                    speaker.state = result.get("playbackState", speaker.state)
                    speaker.volume = result.get("volume", speaker.volume)
                    speaker.muted = result.get("mute", speaker.muted)
                    track = result.get("currentTrack", {})
                    speaker.track_title = track.get("title", "")
                    speaker.track_artist = track.get("artist", "")
                    speaker.track_album = track.get("album", "")
                    speaker.track_uri = track.get("uri", "")
                    speaker.elapsed_seconds = track.get("elapsedTime", 0)
                    speaker.duration_seconds = track.get("duration", 0)
                    speaker.last_seen = time.time()
            return result
        return {"playbackState": "UNKNOWN", "room": room}

    # ── Summary / Dashboard ────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Dashboard-Daten fuer alle bekannten Speaker."""
        # Frische Discovery
        self.discover_zones()

        speakers_data = []
        for sp in self._speakers.values():
            speakers_data.append({
                "room_name": sp.room_name,
                "uuid": sp.uuid,
                "state": sp.state,
                "volume": sp.volume,
                "muted": sp.muted,
                "track": {
                    "title": sp.track_title,
                    "artist": sp.track_artist,
                    "album": sp.track_album,
                    "uri": sp.track_uri,
                    "elapsed": sp.elapsed_seconds,
                    "duration": sp.duration_seconds,
                },
                "group_members": sp.group_members,
                "is_coordinator": sp.is_coordinator,
            })

        groups: dict[str, list[str]] = {}
        for sp in self._speakers.values():
            key = sp.coordinator_uuid or sp.uuid
            if key:
                groups.setdefault(key, []).append(sp.room_name)

        return {
            "total_speakers": len(speakers_data),
            "speakers": speakers_data,
            "playing": sum(1 for s in self._speakers.values() if s.state == "PLAYING"),
            "groups": len(groups),
            "musikwolke_active": any(len(g) > 1 for g in groups.values()),
        }

    # ── Lifecycle ──────────────────────────────────────────────────

    def close(self) -> None:
        """Schliesse HTTP-Session."""
        self._session.close()

    def health_check(self) -> bool:
        """Pruefe ob jishi API erreichbar ist."""
        try:
            resp = self._session.get(
                f"{self._base_url}/zones",
                timeout=3.0,
            )
            return resp.status_code == 200
        except Exception:
            return False
