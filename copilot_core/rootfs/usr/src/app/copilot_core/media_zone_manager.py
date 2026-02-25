"""
Media Zone Manager -- Zone-aware media player orchestration.

Assigns media_player entities to habitus zones, enables smart grouping
("Musikwolke") that follows users through zones, and provides dashboard
controls for play/pause/volume/source per zone.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

import requests

_LOGGER = logging.getLogger(__name__)

SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
DB_PATH = os.environ.get("MEDIA_ZONES_DB", "/data/media_zones.db")


class MediaZoneManager:
    """Manage media players by habitus zone with smart grouping.

    Each zone can have one or more media_player entities assigned.
    The "Musikwolke" feature groups/ungroups players as users move
    between zones, creating a seamless audio experience.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        # Active Musikwolke sessions: {session_id: {person, zones, source, ...}}
        self._musikwolke_sessions: Dict[str, Dict[str, Any]] = {}
        _LOGGER.info("MediaZoneManager initialized at %s", self._db_path)

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS zone_players (
                        zone_id       TEXT NOT NULL,
                        entity_id     TEXT NOT NULL,
                        role          TEXT NOT NULL DEFAULT 'primary',
                        assigned_at   TEXT NOT NULL,
                        PRIMARY KEY (zone_id, entity_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_zp_zone
                        ON zone_players(zone_id);

                    CREATE TABLE IF NOT EXISTS media_events (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        zone_id    TEXT NOT NULL,
                        entity_id  TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        data       TEXT,
                        timestamp  TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_me_zone
                        ON media_events(zone_id, timestamp DESC);
                """)
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Zone ↔ Player Assignment
    # ------------------------------------------------------------------

    def assign_player(self, zone_id: str, entity_id: str,
                      role: str = "primary") -> dict:
        """Assign a media_player entity to a zone."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO zone_players "
                    "(zone_id, entity_id, role, assigned_at) VALUES (?,?,?,?)",
                    (zone_id, entity_id, role, now),
                )
                conn.commit()
            finally:
                conn.close()
        _LOGGER.info("Assigned %s to zone %s (role=%s)", entity_id, zone_id, role)
        return {"ok": True, "zone_id": zone_id, "entity_id": entity_id, "role": role}

    def unassign_player(self, zone_id: str, entity_id: str) -> dict:
        """Remove a media_player from a zone."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "DELETE FROM zone_players WHERE zone_id=? AND entity_id=?",
                    (zone_id, entity_id),
                )
                conn.commit()
            finally:
                conn.close()
        return {"ok": True}

    def get_zone_players(self, zone_id: str) -> List[Dict[str, Any]]:
        """Get all media players assigned to a zone."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT zone_id, entity_id, role, assigned_at "
                    "FROM zone_players WHERE zone_id=?", (zone_id,),
                ).fetchall()
            finally:
                conn.close()
        return [{"zone_id": r[0], "entity_id": r[1], "role": r[2],
                 "assigned_at": r[3]} for r in rows]

    def get_all_assignments(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all zone→player assignments grouped by zone."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT zone_id, entity_id, role, assigned_at "
                    "FROM zone_players ORDER BY zone_id",
                ).fetchall()
            finally:
                conn.close()
        zones: Dict[str, list] = {}
        for r in rows:
            zones.setdefault(r[0], []).append(
                {"entity_id": r[1], "role": r[2], "assigned_at": r[3]}
            )
        return zones

    # ------------------------------------------------------------------
    # Media Control (via Supervisor API)
    # ------------------------------------------------------------------

    def _ha_headers(self) -> Dict[str, str]:
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        return {"Authorization": f"Bearer {token}",
                "Content-Type": "application/json"}

    @staticmethod
    def _normalize_entity_ids(players: List[Dict[str, Any]]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in players:
            entity_id = str(item.get("entity_id", "")).strip()
            if not entity_id or entity_id in seen:
                continue
            seen.add(entity_id)
            out.append(entity_id)
        return out

    def _call_service(self, domain: str, service: str,
                      data: dict,
                      timeout: int = 10) -> dict:
        """Call a HA service via Supervisor API."""
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            return {"ok": False, "error": "No SUPERVISOR_TOKEN"}
        try:
            resp = requests.post(
                f"{SUPERVISOR_API}/services/{domain}/{service}",
                json=data, headers=self._ha_headers(), timeout=timeout,
            )
            return {"ok": resp.ok, "status": resp.status_code}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _get_entity_state(self, entity_id: str) -> dict:
        """Best-effort state fetch for one HA entity."""
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            return {}
        try:
            resp = requests.get(
                f"{SUPERVISOR_API}/states/{entity_id}",
                headers=self._ha_headers(),
                timeout=5,
            )
            if resp.ok:
                payload = resp.json()
                if isinstance(payload, dict):
                    return payload
        except Exception:
            pass
        return {}

    def _pick_zone_leader(self, zone_id: str, preferred_entity_id: str | None = None) -> str | None:
        players = self._normalize_entity_ids(self.get_zone_players(zone_id))
        if not players:
            return None
        if preferred_entity_id and preferred_entity_id in players:
            return preferred_entity_id
        return players[0]

    def _join_players(self, leader_entity_id: str, members: list[str]) -> dict:
        """Join members to a leader (Sonos and compatible media_player integrations)."""
        clean_members = [m for m in members if m and m != leader_entity_id]
        if not clean_members:
            return {"ok": True, "joined": [], "leader": leader_entity_id}
        result = self._call_service(
            "media_player",
            "join",
            {"entity_id": leader_entity_id, "group_members": clean_members},
        )
        return {"ok": bool(result.get("ok")), "joined": clean_members, "leader": leader_entity_id, "result": result}

    def _unjoin_players(self, members: list[str]) -> dict:
        """Unjoin members from current groups."""
        clean_members = [m for m in members if m]
        if not clean_members:
            return {"ok": True, "ungrouped": []}
        result = self._call_service(
            "media_player",
            "unjoin",
            {"entity_id": clean_members},
        )
        return {"ok": bool(result.get("ok")), "ungrouped": clean_members, "result": result}

    def play_zone(self, zone_id: str) -> dict:
        """Resume playback on all players in a zone."""
        players = self.get_zone_players(zone_id)
        results = []
        for p in players:
            r = self._call_service("media_player", "media_play",
                                   {"entity_id": p["entity_id"]})
            results.append({**r, "entity_id": p["entity_id"]})
        return {"ok": True, "zone_id": zone_id, "results": results}

    def pause_zone(self, zone_id: str) -> dict:
        """Pause playback on all players in a zone."""
        players = self.get_zone_players(zone_id)
        results = []
        for p in players:
            r = self._call_service("media_player", "media_pause",
                                   {"entity_id": p["entity_id"]})
            results.append({**r, "entity_id": p["entity_id"]})
        return {"ok": True, "zone_id": zone_id, "results": results}

    def set_zone_volume(self, zone_id: str, volume: float) -> dict:
        """Set volume (0.0-1.0) on all players in a zone."""
        players = self.get_zone_players(zone_id)
        results = []
        for p in players:
            r = self._call_service("media_player", "volume_set",
                                   {"entity_id": p["entity_id"],
                                    "volume_level": max(0.0, min(1.0, volume))})
            results.append({**r, "entity_id": p["entity_id"]})
        return {"ok": True, "zone_id": zone_id, "volume": volume, "results": results}

    def play_media_in_zone(self, zone_id: str, media_content_id: str,
                           media_content_type: str = "music") -> dict:
        """Start playing specific media in a zone."""
        players = self.get_zone_players(zone_id)
        results = []
        for p in players:
            r = self._call_service("media_player", "play_media", {
                "entity_id": p["entity_id"],
                "media_content_id": media_content_id,
                "media_content_type": media_content_type,
            })
            results.append({**r, "entity_id": p["entity_id"]})
        return {"ok": True, "zone_id": zone_id, "results": results}

    # ------------------------------------------------------------------
    # Musikwolke (Smart Audio Follow)
    # ------------------------------------------------------------------

    def start_musikwolke(self, person_id: str,
                         source_zone: str,
                         mode: str = "group",
                         degroup_on_leave: bool = True,
                         leader_entity_id: str | None = None) -> dict:
        """Start a Musikwolke session: audio follows person through zones.

        The media currently playing in source_zone will follow person_id
        as they move between zones.
        """
        import uuid
        session_id = uuid.uuid4().hex[:10]
        players = self._normalize_entity_ids(self.get_zone_players(source_zone))
        if not players:
            return {"ok": False, "error": f"No players in zone {source_zone}"}

        leader = self._pick_zone_leader(source_zone, leader_entity_id)
        if not leader:
            return {"ok": False, "error": "No leader player available"}

        mode_clean = str(mode or "group").strip().lower()
        if mode_clean not in {"group", "follow"}:
            mode_clean = "group"

        grouped_entities: set[str] = set()
        if mode_clean == "group":
            group_result = self._join_players(leader, players)
            if group_result.get("ok"):
                grouped_entities.update(group_result.get("joined", []))

        self._musikwolke_sessions[session_id] = {
            "person_id": person_id,
            "active_zones": [source_zone],
            "source_zone": source_zone,
            "current_zone": source_zone,
            "started_at": time.time(),
            "last_updated": time.time(),
            "mode": mode_clean,
            "degroup_on_leave": bool(degroup_on_leave),
            "leader_entity_id": leader,
            "grouped_entities": sorted(grouped_entities),
        }
        _LOGGER.info(
            "Musikwolke started: session=%s, person=%s, zone=%s, mode=%s, leader=%s",
            session_id,
            person_id,
            source_zone,
            mode_clean,
            leader,
        )
        return {
            "ok": True,
            "session_id": session_id,
            "source_zone": source_zone,
            "leader_entity_id": leader,
            "mode": mode_clean,
        }

    def update_musikwolke(self, session_id: str,
                          entered_zone: str) -> dict:
        """Person entered a new zone -- extend Musikwolke there.

        Joins the new zone's players to the group and optionally
        pauses/reduces volume in the previous zone.
        """
        session = self._musikwolke_sessions.get(session_id)
        if not session:
            return {"ok": False, "error": "Session not found"}

        new_players = self._normalize_entity_ids(self.get_zone_players(entered_zone))
        if not new_players:
            return {"ok": False, "error": f"No players in zone {entered_zone}"}

        leader = str(session.get("leader_entity_id") or "").strip()
        mode = str(session.get("mode") or "group")
        previous_zone = str(session.get("current_zone") or session.get("source_zone") or "")
        previously_grouped = set(session.get("grouped_entities", []))

        if mode == "group" and leader:
            join_result = self._join_players(leader, new_players)
            if join_result.get("ok"):
                previously_grouped.update(join_result.get("joined", []))
        else:
            # Fallback mode: start playback in new zone and fade previous zones.
            for entity_id in new_players:
                self._call_service("media_player", "media_play", {"entity_id": entity_id})
            for prev_zone in session.get("active_zones", []):
                if prev_zone == entered_zone:
                    continue
                prev_players = self._normalize_entity_ids(self.get_zone_players(prev_zone))
                for entity_id in prev_players:
                    self._call_service(
                        "media_player",
                        "volume_set",
                        {"entity_id": entity_id, "volume_level": 0.15},
                    )

        if session.get("degroup_on_leave", True) and previous_zone and previous_zone != entered_zone:
            leaving_entities = self._normalize_entity_ids(self.get_zone_players(previous_zone))
            leaving_members = [entity_id for entity_id in leaving_entities if entity_id != leader]
            self._unjoin_players(leaving_members)
            for entity_id in leaving_members:
                previously_grouped.discard(entity_id)

        if entered_zone not in session["active_zones"]:
            session["active_zones"].append(entered_zone)
        session["current_zone"] = entered_zone
        session["last_updated"] = time.time()
        session["grouped_entities"] = sorted(previously_grouped)
        _LOGGER.info("Musikwolke extended to zone %s (session=%s)",
                      entered_zone, session_id)
        return {
            "ok": True,
            "session_id": session_id,
            "active_zones": session["active_zones"],
            "leader_entity_id": leader,
            "mode": mode,
            "current_zone": entered_zone,
            "grouped_entities": session["grouped_entities"],
        }

    def stop_musikwolke(self, session_id: str) -> dict:
        """Stop a Musikwolke session."""
        session = self._musikwolke_sessions.pop(session_id, None)
        if not session:
            return {"ok": False, "error": "Session not found"}

        leader = str(session.get("leader_entity_id") or "").strip()
        grouped = [entity_id for entity_id in session.get("grouped_entities", []) if entity_id != leader]

        if session.get("mode") == "group" and session.get("degroup_on_leave", True):
            self._unjoin_players(grouped)
        else:
            # Fallback behavior: pause all zones except source.
            for zone in session["active_zones"]:
                if zone != session["source_zone"]:
                    self.pause_zone(zone)

        _LOGGER.info("Musikwolke stopped: session=%s", session_id)
        return {
            "ok": True,
            "session_id": session_id,
            "leader_entity_id": leader or None,
            "ungrouped_entities": grouped,
        }

    def get_musikwolke_sessions(self) -> List[Dict[str, Any]]:
        """List active Musikwolke sessions."""
        sessions: list[dict[str, Any]] = []
        for sid, raw in self._musikwolke_sessions.items():
            payload = dict(raw)
            payload["session_id"] = sid
            payload["grouped_entities"] = list(payload.get("grouped_entities", []))
            sessions.append(payload)
        return sessions

    def get_zone_favorites(self, zone_id: str) -> dict:
        """Return best-effort favorite/source list for a zone's primary player."""
        leader = self._pick_zone_leader(zone_id)
        if not leader:
            return {"ok": False, "error": f"No players in zone {zone_id}", "favorites": []}

        state = self._get_entity_state(leader)
        attrs = state.get("attributes", {}) if isinstance(state, dict) else {}
        source_list = attrs.get("source_list") if isinstance(attrs.get("source_list"), list) else []
        sonos_favs = attrs.get("sonos_favorites") if isinstance(attrs.get("sonos_favorites"), list) else []

        favorites: list[str] = []
        seen: set[str] = set()
        for item in source_list + sonos_favs:
            name = str(item).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            favorites.append(name)

        return {"ok": True, "zone_id": zone_id, "leader_entity_id": leader, "favorites": favorites}

    def play_zone_favorite(self, zone_id: str, favorite_name: str,
                           media_content_type: str = "favorite_item") -> dict:
        """Play a Sonos/source favorite in a zone."""
        favorite = str(favorite_name or "").strip()
        if not favorite:
            return {"ok": False, "error": "Missing favorite_name"}

        leader = self._pick_zone_leader(zone_id)
        if not leader:
            return {"ok": False, "error": f"No players in zone {zone_id}"}

        result = self._call_service(
            "media_player",
            "play_media",
            {
                "entity_id": leader,
                "media_content_id": favorite,
                "media_content_type": media_content_type or "favorite_item",
            },
        )
        return {
            "ok": bool(result.get("ok")),
            "zone_id": zone_id,
            "leader_entity_id": leader,
            "favorite_name": favorite,
            "result": result,
        }

    def search_and_play(self, zone_id: str, query: str,
                        media_content_type: str = "music") -> dict:
        """Play content by manual search query on the zone leader."""
        search_query = str(query or "").strip()
        if not search_query:
            return {"ok": False, "error": "Missing query"}

        leader = self._pick_zone_leader(zone_id)
        if not leader:
            return {"ok": False, "error": f"No players in zone {zone_id}"}

        result = self._call_service(
            "media_player",
            "play_media",
            {
                "entity_id": leader,
                "media_content_id": search_query,
                "media_content_type": media_content_type or "music",
            },
        )
        return {
            "ok": bool(result.get("ok")),
            "zone_id": zone_id,
            "leader_entity_id": leader,
            "query": search_query,
            "result": result,
        }

    # ------------------------------------------------------------------
    # Zone media state
    # ------------------------------------------------------------------

    def get_zone_media_state(self, zone_id: str) -> dict:
        """Get current media state for a zone by querying HA entities."""
        players = self.get_zone_players(zone_id)
        if not players:
            return {"zone_id": zone_id, "players": [], "state": "idle"}

        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            return {"zone_id": zone_id, "players": players, "state": "unknown"}

        states = []
        for p in players:
            try:
                resp = requests.get(
                    f"{SUPERVISOR_API}/states/{p['entity_id']}",
                    headers=self._ha_headers(), timeout=5,
                )
                if resp.ok:
                    s = resp.json()
                    states.append({
                        "entity_id": p["entity_id"],
                        "state": s.get("state", "unknown"),
                        "media_title": s.get("attributes", {}).get("media_title"),
                        "media_artist": s.get("attributes", {}).get("media_artist"),
                        "volume": s.get("attributes", {}).get("volume_level"),
                        "source": s.get("attributes", {}).get("source"),
                        "app_name": s.get("attributes", {}).get("app_name"),
                    })
            except Exception:
                states.append({"entity_id": p["entity_id"], "state": "error"})

        # Zone-level state: playing if any player is playing
        zone_state = "idle"
        for s in states:
            if s["state"] == "playing":
                zone_state = "playing"
                break
            elif s["state"] == "paused":
                zone_state = "paused"

        return {"zone_id": zone_id, "state": zone_state, "players": states}
