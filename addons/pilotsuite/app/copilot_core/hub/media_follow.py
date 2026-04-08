"""Media Follow — Musikwolke & Wiedergabe-Folgen (v6.7.0).

Features:
- Track active media playback across zones (music, TV, radio)
- Follow mode: playback follows user between Habitus zones
- Media cloud: centralized playback state overview
- Per-zone media routing with priority management
- Dashboard with current playback info per zone
- Quick-toggle follow mode per zone or global
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class MediaSource:
    """A media source (player/speaker/TV)."""

    entity_id: str
    name: str
    zone_id: str
    media_type: str  # music, tv, radio, podcast, video
    state: str = "idle"  # idle, playing, paused, buffering
    title: str = ""
    artist: str = ""
    album: str = ""
    media_image_url: str = ""
    volume_pct: int = 50
    is_muted: bool = False
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class PlaybackSession:
    """An active playback session."""

    session_id: str
    source_entity: str
    zone_id: str
    media_type: str
    title: str
    artist: str = ""
    album: str = ""
    state: str = "playing"
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    volume_pct: int = 50
    follow_enabled: bool = False
    priority: int = 0


@dataclass
class ZoneMediaState:
    """Media state for a zone."""

    zone_id: str
    active_sessions: int = 0
    primary_session: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    follow_enabled: bool = False
    volume_pct: int = 50


@dataclass
class MediaTransfer:
    """A media transfer event (follow/handoff)."""

    session_id: str
    from_zone: str
    to_zone: str
    media_type: str
    title: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    trigger: str = "presence"  # presence, manual, schedule


@dataclass
class MediaDashboard:
    """Media cloud dashboard overview."""

    total_sources: int = 0
    active_sessions: int = 0
    zones_with_playback: int = 0
    follow_enabled_zones: int = 0
    sessions: list[dict[str, Any]] = field(default_factory=list)
    zone_states: list[dict[str, Any]] = field(default_factory=list)
    recent_transfers: list[dict[str, Any]] = field(default_factory=list)


# ── Engine ──────────────────────────────────────────────────────────────────


class MediaFollowEngine:
    """Engine for media follow / Musikwolke playback tracking."""

    def __init__(self) -> None:
        self._sources: dict[str, MediaSource] = {}  # entity_id -> MediaSource
        self._sessions: dict[str, PlaybackSession] = {}  # session_id -> PlaybackSession
        self._follow_zones: set[str] = set()  # zones with follow enabled
        self._global_follow: bool = False
        self._transfers: list[MediaTransfer] = []
        self._session_counter: int = 0

    # ── Source management ────────────────────────────────────────────────

    def register_source(self, entity_id: str, name: str, zone_id: str,
                        media_type: str = "music") -> MediaSource:
        """Register a media source (speaker, TV, etc.)."""
        source = MediaSource(
            entity_id=entity_id,
            name=name,
            zone_id=zone_id,
            media_type=media_type,
        )
        self._sources[entity_id] = source
        logger.info("Media source registered: %s (%s) in zone '%s'", name, media_type, zone_id)
        return source

    def unregister_source(self, entity_id: str) -> bool:
        """Remove a media source."""
        if entity_id in self._sources:
            del self._sources[entity_id]
            # Remove any sessions for this source
            to_remove = [
                sid for sid, s in self._sessions.items()
                if s.source_entity == entity_id
            ]
            for sid in to_remove:
                del self._sessions[sid]
            return True
        return False

    # ── Playback tracking ────────────────────────────────────────────────

    def update_playback(self, entity_id: str, state: str,
                        title: str = "", artist: str = "",
                        album: str = "", volume_pct: int | None = None,
                        media_image_url: str = "") -> PlaybackSession | None:
        """Update playback state for a media source.

        Creates a session when playing starts, removes when stopped.
        """
        source = self._sources.get(entity_id)
        if not source:
            return None

        now = datetime.now(tz=timezone.utc)
        source.state = state
        source.title = title
        source.artist = artist
        source.album = album
        source.last_updated = now
        if media_image_url:
            source.media_image_url = media_image_url
        if volume_pct is not None:
            source.volume_pct = volume_pct

        # Find existing session for this source
        existing = next(
            (s for s in self._sessions.values() if s.source_entity == entity_id),
            None,
        )

        if state in ("playing", "paused", "buffering"):
            if existing:
                existing.state = state
                existing.title = title
                existing.artist = artist
                existing.album = album
                if volume_pct is not None:
                    existing.volume_pct = volume_pct
                return existing
            else:
                # Create new session
                self._session_counter += 1
                session_id = f"session_{self._session_counter}"
                follow = self._global_follow or source.zone_id in self._follow_zones
                session = PlaybackSession(
                    session_id=session_id,
                    source_entity=entity_id,
                    zone_id=source.zone_id,
                    media_type=source.media_type,
                    title=title,
                    artist=artist,
                    album=album,
                    state=state,
                    started_at=now,
                    volume_pct=volume_pct or source.volume_pct,
                    follow_enabled=follow,
                )
                self._sessions[session_id] = session
                return session
        elif state in ("idle", "off", "unavailable"):
            if existing:
                del self._sessions[existing.session_id]
        return None

    # ── Follow mode ──────────────────────────────────────────────────────

    def set_follow_zone(self, zone_id: str, enabled: bool) -> bool:
        """Enable/disable follow mode for a zone."""
        if enabled:
            self._follow_zones.add(zone_id)
        else:
            self._follow_zones.discard(zone_id)

        # Update active sessions
        for session in self._sessions.values():
            if session.zone_id == zone_id:
                session.follow_enabled = enabled or self._global_follow
        return True

    def set_global_follow(self, enabled: bool) -> bool:
        """Enable/disable global follow mode."""
        self._global_follow = enabled
        for session in self._sessions.values():
            session.follow_enabled = enabled or session.zone_id in self._follow_zones
        return True

    def transfer_playback(self, session_id: str, to_zone_id: str,
                          trigger: str = "presence") -> MediaTransfer | None:
        """Transfer a playback session to another zone.

        This simulates the media follow behavior — when a user enters a new zone,
        playback transfers from the source zone to the target zone.
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        if session.zone_id == to_zone_id:
            return None  # Already in target zone

        from_zone = session.zone_id
        transfer = MediaTransfer(
            session_id=session_id,
            from_zone=from_zone,
            to_zone=to_zone_id,
            media_type=session.media_type,
            title=session.title,
            trigger=trigger,
        )
        self._transfers.append(transfer)

        session.zone_id = to_zone_id
        logger.info(
            "Media transferred: '%s' from '%s' → '%s' (trigger: %s)",
            session.title, from_zone, to_zone_id, trigger,
        )
        return transfer

    def on_zone_enter(self, zone_id: str) -> list[MediaTransfer]:
        """Handle user entering a zone — transfer follow-enabled sessions.

        Returns list of transfers that occurred.
        """
        transfers = []
        for session in list(self._sessions.values()):
            if session.follow_enabled and session.zone_id != zone_id:
                t = self.transfer_playback(session.session_id, zone_id, "presence")
                if t:
                    transfers.append(t)
        return transfers

    # ── Query ────────────────────────────────────────────────────────────

    def get_zone_media(self, zone_id: str) -> ZoneMediaState:
        """Get media state for a zone."""
        zone_sessions = [
            s for s in self._sessions.values()
            if s.zone_id == zone_id
        ]
        zone_sources = [
            s for s in self._sources.values()
            if s.zone_id == zone_id
        ]

        primary = None
        if zone_sessions:
            # Pick highest priority playing session
            playing = [s for s in zone_sessions if s.state == "playing"]
            if playing:
                primary_session = max(playing, key=lambda s: s.priority)
            else:
                primary_session = zone_sessions[0]
            primary = {
                "session_id": primary_session.session_id,
                "title": primary_session.title,
                "artist": primary_session.artist,
                "album": primary_session.album,
                "media_type": primary_session.media_type,
                "state": primary_session.state,
                "volume_pct": primary_session.volume_pct,
                "follow_enabled": primary_session.follow_enabled,
            }

        return ZoneMediaState(
            zone_id=zone_id,
            active_sessions=len(zone_sessions),
            primary_session=primary,
            sources=[
                {
                    "entity_id": s.entity_id,
                    "name": s.name,
                    "media_type": s.media_type,
                    "state": s.state,
                    "title": s.title,
                    "artist": s.artist,
                }
                for s in zone_sources
            ],
            follow_enabled=zone_id in self._follow_zones or self._global_follow,
            volume_pct=primary["volume_pct"] if primary else 50,
        )

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get all active playback sessions."""
        return [
            {
                "session_id": s.session_id,
                "source_entity": s.source_entity,
                "zone_id": s.zone_id,
                "media_type": s.media_type,
                "title": s.title,
                "artist": s.artist,
                "album": s.album,
                "state": s.state,
                "volume_pct": s.volume_pct,
                "follow_enabled": s.follow_enabled,
                "started_at": s.started_at.isoformat(),
            }
            for s in self._sessions.values()
        ]

    def get_dashboard(self) -> MediaDashboard:
        """Get media cloud dashboard overview."""
        zones_with_playback = set()
        for s in self._sessions.values():
            if s.state == "playing":
                zones_with_playback.add(s.zone_id)

        sessions = self.get_active_sessions()

        zone_ids = set(s.zone_id for s in self._sources.values())
        zone_states = []
        for zid in zone_ids:
            zm = self.get_zone_media(zid)
            zone_states.append({
                "zone_id": zm.zone_id,
                "active_sessions": zm.active_sessions,
                "primary_title": zm.primary_session["title"] if zm.primary_session else None,
                "primary_artist": zm.primary_session["artist"] if zm.primary_session else None,
                "primary_state": zm.primary_session["state"] if zm.primary_session else "idle",
                "follow_enabled": zm.follow_enabled,
            })

        recent = [
            {
                "session_id": t.session_id,
                "from_zone": t.from_zone,
                "to_zone": t.to_zone,
                "title": t.title,
                "media_type": t.media_type,
                "trigger": t.trigger,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in self._transfers[-20:]
        ]

        return MediaDashboard(
            total_sources=len(self._sources),
            active_sessions=len(self._sessions),
            zones_with_playback=len(zones_with_playback),
            follow_enabled_zones=len(self._follow_zones) + (len(zone_ids) if self._global_follow else 0),
            sessions=sessions,
            zone_states=zone_states,
            recent_transfers=list(reversed(recent)),
        )

    def get_sources(self) -> list[dict[str, Any]]:
        """Get all registered media sources."""
        return [
            {
                "entity_id": s.entity_id,
                "name": s.name,
                "zone_id": s.zone_id,
                "media_type": s.media_type,
                "state": s.state,
                "title": s.title,
                "artist": s.artist,
                "volume_pct": s.volume_pct,
            }
            for s in self._sources.values()
        ]
