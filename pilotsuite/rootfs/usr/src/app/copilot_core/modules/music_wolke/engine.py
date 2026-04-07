"""MusicWolke Engine — Smart Audio Follow through Habitus Zones.

Eigenständiges Modul. Schnittstelle zu Sonnenwecker:
- accept_stop_request(zone_id): stoppt playback wenn Sonnenwecker Schlaf erkennt
- start_session() mit volume param

Keine automatische Kopplung. Kein Zwei-Wege-Import.
"""

from __future__ import annotations

import logging
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlaybackSession:
    """Aktive Wiedergabe-Session."""
    session_id: str
    source_entity: str
    zone_id: str
    media_type: str = "music"
    title: str = ""
    artist: str = ""
    album: str = ""
    state: str = "idle"
    started_at: str = ""
    volume_pct: int = 50
    follow_enabled: bool = False
    priority: int = 0
    person_id: Optional[str] = None

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "source_entity": self.source_entity,
            "zone_id": self.zone_id,
            "media_type": self.media_type,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "state": self.state,
            "started_at": self.started_at,
            "volume_pct": self.volume_pct,
            "follow_enabled": self.follow_enabled,
            "priority": self.priority,
            "person_id": self.person_id,
        }


@dataclass
class ZoneMediaState:
    """Medienzustand einer Zone."""
    zone_id: str
    active_sessions: int = 0
    primary_session: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)
    follow_enabled: bool = False
    volume_pct: int = 50
    current_source: str = ""
    favorites: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "active_sessions": self.active_sessions,
            "primary_session": self.primary_session,
            "sources": self.sources,
            "follow_enabled": self.follow_enabled,
            "volume_pct": self.volume_pct,
            "current_source": self.current_source,
            "favorites": self.favorites,
        }


@dataclass
class MediaTransfer:
    """Transfer-Ereignis (follow/handoff)."""
    session_id: str
    from_zone: str
    to_zone: str
    media_type: str
    title: str
    transferred_at: str = ""
    success: bool = True

    def __post_init__(self):
        if not self.transferred_at:
            self.transferred_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "from_zone": self.from_zone,
            "to_zone": self.to_zone,
            "media_type": self.media_type,
            "title": self.title,
            "transferred_at": self.transferred_at,
            "success": self.success,
        }


class MusicWolkeEngine:
    """Eigenständiges Musikwolke-Modul. Singleton."""

    _instance: Optional["MusicWolkeEngine"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._sessions: Dict[str, PlaybackSession] = {}
        self._zone_states: Dict[str, ZoneMediaState] = {}
        self._transfers: List[MediaTransfer] = []
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "MusicWolkeEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ─── Source-Management ───────────────────────────────────────────────────

    def register_source(self, entity_id: str, name: str, zone_id: str,
                       media_type: str = "music") -> bool:
        """Medienquelle (Player/Lautsprecher) registrieren."""
        with self._lock:
            if zone_id not in self._zone_states:
                self._zone_states[zone_id] = ZoneMediaState(zone_id=zone_id)

            zone = self._zone_states[zone_id]
            existing = [s for s in zone.sources if s["entity_id"] == entity_id]
            if not existing:
                zone.sources.append({
                    "entity_id": entity_id,
                    "name": name,
                    "media_type": media_type,
                    "state": "idle",
                })
                _LOGGER.debug("MusicWolke: Registered source %s in zone %s", entity_id, zone_id)
            else:
                existing[0].update({"name": name, "media_type": media_type, "state": "idle"})
            return True

    def unregister_source(self, entity_id: str) -> bool:
        """Quelle entfernen."""
        with self._lock:
            for zone in self._zone_states.values():
                zone.sources = [s for s in zone.sources if s["entity_id"] != entity_id]
            _LOGGER.debug("MusicWolke: Unregistered source %s", entity_id)
            return True

    # ─── Session-Management ───────────────────────────────────────────────────

    def start_session(self, zone_id: str, source_entity: str,
                     media_type: str = "music", person_id: Optional[str] = None,
                     follow_enabled: bool = True,
                     volume_pct: int = 50) -> Optional[str]:
        """Neue Wiedergabe-Session starten."""
        with self._lock:
            if zone_id not in self._zone_states:
                self._zone_states[zone_id] = ZoneMediaState(zone_id=zone_id)

            session_id = f"mw_{uuid.uuid4().hex[:8]}"
            session = PlaybackSession(
                session_id=session_id,
                source_entity=source_entity,
                zone_id=zone_id,
                media_type=media_type,
                follow_enabled=follow_enabled,
                person_id=person_id,
                volume_pct=volume_pct,
                state="playing",
            )

            self._sessions[session_id] = session
            zone = self._zone_states[zone_id]
            zone.active_sessions += 1
            zone.primary_session = session.to_dict()
            zone.volume_pct = volume_pct

            _LOGGER.info("MusicWolke: Session %s gestartet in %s (person: %s, vol: %d%%)",
                         session_id, zone_id, person_id, volume_pct)
            return session_id

    def transfer_session(self, session_id: str, to_zone_id: str,
                        to_source_entity: Optional[str] = None) -> bool:
        """Playback auf neue Zone übertragen (follow mode)."""
        with self._lock:
            if session_id not in self._sessions:
                _LOGGER.warning("MusicWolke: Session %s nicht gefunden", session_id)
                return False

            session = self._sessions[session_id]
            from_zone = session.zone_id

            # Zone wechseln
            session.zone_id = to_zone_id
            if to_source_entity:
                session.source_entity = to_source_entity

            # Alte Zone: sessions abziehen
            if from_zone in self._zone_states:
                self._zone_states[from_zone].active_sessions = max(
                    0, self._zone_states[from_zone].active_sessions - 1)

            # Neue Zone: sessions erhöhen
            if to_zone_id not in self._zone_states:
                self._zone_states[to_zone_id] = ZoneMediaState(zone_id=to_zone_id)
            self._zone_states[to_zone_id].active_sessions += 1
            self._zone_states[to_zone_id].primary_session = session.to_dict()

            # Transfer loggen
            self._transfers.append(MediaTransfer(
                session_id=session_id,
                from_zone=from_zone,
                to_zone=to_zone_id,
                media_type=session.media_type,
                title=session.title,
            ))

            _LOGGER.info("MusicWolke: Session %s transferiert %s → %s",
                         session_id, from_zone, to_zone_id)
            return True

    def stop_session(self, session_id: str) -> bool:
        """Session stoppen."""
        with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]
            zone_id = session.zone_id

            if zone_id in self._zone_states:
                self._zone_states[zone_id].active_sessions = max(
                    0, self._zone_states[zone_id].active_sessions - 1)
                if self._zone_states[zone_id].active_sessions == 0:
                    self._zone_states[zone_id].primary_session = None

            del self._sessions[session_id]
            _LOGGER.info("MusicWolke: Session %s gestoppt", session_id)
            return True

    def stop_zone(self, zone_id: str) -> int:
        """Alle Sessions in einer Zone stoppen. Rückgabe: Anzahl gestoppte Sessions."""
        with self._lock:
            to_stop = [
                sid for sid, s in self._sessions.items()
                if s.zone_id == zone_id
            ]
            for sid in to_stop:
                self.stop_session(sid)
            return len(to_stop)

    def set_volume(self, session_id: str, volume_pct: int) -> bool:
        """Lautstärke einer Session ändern."""
        with self._lock:
            if session_id not in self._sessions:
                return False
            session = self._sessions[session_id]
            session.volume_pct = max(0, min(100, volume_pct))
            return True

    # ─── Presence-Integration ────────────────────────────────────────────────

    def on_zone_entry(self, person_id: str, zone_id: str) -> List[Dict[str, Any]]:
        """Person betritt Zone → follow wenn aktiv."""
        transfers = []
        with self._lock:
            for session in list(self._sessions.values()):
                if session.person_id == person_id and session.follow_enabled:
                    if zone_id in self._zone_states:
                        sources = self._zone_states[zone_id].sources
                        if sources:
                            target = sources[0]["entity_id"]
                            if self.transfer_session(session.session_id, zone_id, target):
                                transfers.append(self._transfers[-1].to_dict())
        return transfers

    # ─── Status ─────────────────────────────────────────────────────────────

    def get_zone_state(self, zone_id: str) -> Dict[str, Any]:
        """Medienzustand einer Zone."""
        with self._lock:
            if zone_id not in self._zone_states:
                return ZoneMediaState(zone_id=zone_id).to_dict()
            return self._zone_states[zone_id].to_dict()

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Alle aktiven Sessions."""
        with self._lock:
            return [s.to_dict() for s in self._sessions.values()]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.get(session_id)
        return session.to_dict() if session else None

    def get_transfers(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Letzte Transfers."""
        with self._lock:
            return [t.to_dict() for t in self._transfers[-limit:]]

    def get_dashboard(self) -> Dict[str, Any]:
        """Dashboard-Überblick."""
        with self._lock:
            return {
                "active_sessions": len(self._sessions),
                "zones": {zid: zs.to_dict() for zid, zs in self._zone_states.items()},
                "recent_transfers": self.get_transfers(10),
            }
