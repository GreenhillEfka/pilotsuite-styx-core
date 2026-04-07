"""Presence Intelligence — Anwesenheits-Intelligence (v7.1.0).

Features:
- Real-time person presence tracking with room-level resolution
- Person transition detection (room → room) with timestamps
- Occupancy heatmap per zone/room over configurable time windows
- Presence-based automation triggers (arrival, departure, idle)
- Home/Away detection per person and household level
- Occupancy analytics: peak hours, average durations, patterns
- Presence zones with configurable sensor mapping
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class PersonState:
    """Tracked person state."""

    person_id: str
    name: str
    current_room: str = ""
    current_zone: str = ""
    is_home: bool = False
    last_seen: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_room_change: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    icon: str = "mdi:account"


@dataclass
class RoomTransition:
    """A person's room-to-room transition."""

    person_id: str
    from_room: str
    to_room: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class RoomOccupancy:
    """Occupancy stats for a room."""

    room_id: str
    room_name: str = ""
    current_count: int = 0
    persons: list[str] = field(default_factory=list)
    total_visits: int = 0
    avg_duration_min: float = 0.0
    peak_hour: int = 0


@dataclass
class PresenceTrigger:
    """A presence-based automation trigger."""

    trigger_id: str
    trigger_type: str  # arrival, departure, idle, room_enter, room_leave
    person_id: str = ""
    room_id: str = ""
    zone_id: str = ""
    idle_threshold_min: int = 30
    active: bool = True
    fired_count: int = 0
    last_fired: datetime | None = None


@dataclass
class HeatmapEntry:
    """Occupancy heatmap entry."""

    room_id: str
    hour: int
    occupancy_avg: float = 0.0
    visit_count: int = 0


@dataclass
class PresenceIntelligenceDashboard:
    """Presence intelligence dashboard."""

    total_persons: int = 0
    persons_home: int = 0
    persons_away: int = 0
    total_rooms: int = 0
    occupied_rooms: int = 0
    recent_transitions: list[dict[str, Any]] = field(default_factory=list)
    room_occupancy: list[dict[str, Any]] = field(default_factory=list)
    active_triggers: int = 0
    household_status: str = "away"  # home, away, partial


# ── Engine ──────────────────────────────────────────────────────────────────


class PresenceIntelligenceEngine:
    """Engine for presence intelligence and occupancy analytics."""

    def __init__(self) -> None:
        self._persons: dict[str, PersonState] = {}
        self._rooms: dict[str, str] = {}  # room_id → room_name
        self._transitions: list[RoomTransition] = []
        self._triggers: dict[str, PresenceTrigger] = {}
        self._visit_log: list[tuple[str, str, datetime, datetime | None]] = []  # person, room, enter, leave

    # ── Person management ─────────────────────────────────────────────────

    def register_person(self, person_id: str, name: str,
                        icon: str = "mdi:account") -> PersonState:
        """Register a person for presence tracking."""
        if person_id in self._persons:
            p = self._persons[person_id]
            p.name = name
            p.icon = icon
            return p
        person = PersonState(person_id=person_id, name=name, icon=icon)
        self._persons[person_id] = person
        logger.info("Person registered: %s (%s)", person_id, name)
        return person

    def unregister_person(self, person_id: str) -> bool:
        """Remove a person from tracking."""
        if person_id not in self._persons:
            return False
        del self._persons[person_id]
        return True

    def get_person(self, person_id: str) -> dict[str, Any] | None:
        """Get person details."""
        p = self._persons.get(person_id)
        if not p:
            return None
        return {
            "person_id": p.person_id,
            "name": p.name,
            "current_room": p.current_room,
            "current_zone": p.current_zone,
            "is_home": p.is_home,
            "last_seen": p.last_seen.isoformat(),
            "last_room_change": p.last_room_change.isoformat(),
            "icon": p.icon,
        }

    # ── Room management ───────────────────────────────────────────────────

    def register_room(self, room_id: str, room_name: str = "") -> bool:
        """Register a room for occupancy tracking."""
        self._rooms[room_id] = room_name or room_id
        return True

    def get_rooms(self) -> list[dict[str, Any]]:
        """Get all registered rooms with occupancy."""
        result = []
        for room_id, room_name in self._rooms.items():
            persons_in_room = [
                p.person_id for p in self._persons.values()
                if p.current_room == room_id and p.is_home
            ]
            result.append({
                "room_id": room_id,
                "room_name": room_name,
                "current_count": len(persons_in_room),
                "persons": persons_in_room,
            })
        return result

    # ── State updates ─────────────────────────────────────────────────────

    def update_presence(self, person_id: str, room_id: str = "",
                        zone_id: str = "", is_home: bool = True) -> bool:
        """Update a person's presence state."""
        person = self._persons.get(person_id)
        if not person:
            return False

        now = datetime.now(tz=timezone.utc)
        old_room = person.current_room
        was_home = person.is_home

        person.is_home = is_home
        person.last_seen = now

        if not is_home:
            # Person left home
            if old_room:
                self._log_room_leave(person_id, old_room, now)
            person.current_room = ""
            person.current_zone = ""
            if was_home:
                self._fire_triggers("departure", person_id, old_room)
            return True

        if not was_home and is_home:
            # Person arrived home
            self._fire_triggers("arrival", person_id, room_id)

        if room_id and room_id != old_room:
            # Room transition
            if old_room:
                self._transitions.append(RoomTransition(
                    person_id=person_id,
                    from_room=old_room,
                    to_room=room_id,
                    timestamp=now,
                ))
                self._transitions = self._transitions[-500:]
                self._log_room_leave(person_id, old_room, now)
                self._fire_triggers("room_leave", person_id, old_room)

            self._log_room_enter(person_id, room_id, now)
            self._fire_triggers("room_enter", person_id, room_id)
            person.current_room = room_id
            person.last_room_change = now

        if zone_id:
            person.current_zone = zone_id

        return True

    def _log_room_enter(self, person_id: str, room_id: str, ts: datetime) -> None:
        self._visit_log.append((person_id, room_id, ts, None))
        self._visit_log = self._visit_log[-1000:]

    def _log_room_leave(self, person_id: str, room_id: str, ts: datetime) -> None:
        for i in range(len(self._visit_log) - 1, -1, -1):
            pid, rid, enter, leave = self._visit_log[i]
            if pid == person_id and rid == room_id and leave is None:
                self._visit_log[i] = (pid, rid, enter, ts)
                break

    # ── Triggers ──────────────────────────────────────────────────────────

    def register_trigger(self, trigger_id: str, trigger_type: str,
                         person_id: str = "", room_id: str = "",
                         zone_id: str = "",
                         idle_threshold_min: int = 30) -> bool:
        """Register a presence-based automation trigger."""
        valid_types = {"arrival", "departure", "idle", "room_enter", "room_leave"}
        if trigger_type not in valid_types:
            return False
        if trigger_id in self._triggers:
            return False
        self._triggers[trigger_id] = PresenceTrigger(
            trigger_id=trigger_id,
            trigger_type=trigger_type,
            person_id=person_id,
            room_id=room_id,
            zone_id=zone_id,
            idle_threshold_min=idle_threshold_min,
        )
        return True

    def unregister_trigger(self, trigger_id: str) -> bool:
        """Remove a trigger."""
        if trigger_id not in self._triggers:
            return False
        del self._triggers[trigger_id]
        return True

    def _fire_triggers(self, event_type: str, person_id: str, room_id: str = "") -> list[str]:
        """Check and fire matching triggers."""
        fired = []
        now = datetime.now(tz=timezone.utc)
        for t in self._triggers.values():
            if not t.active or t.trigger_type != event_type:
                continue
            if t.person_id and t.person_id != person_id:
                continue
            if t.room_id and t.room_id != room_id:
                continue
            t.fired_count += 1
            t.last_fired = now
            fired.append(t.trigger_id)
        return fired

    def check_idle_triggers(self) -> list[str]:
        """Check idle triggers — call periodically."""
        now = datetime.now(tz=timezone.utc)
        fired = []
        for t in self._triggers.values():
            if not t.active or t.trigger_type != "idle":
                continue
            for p in self._persons.values():
                if t.person_id and t.person_id != p.person_id:
                    continue
                if not p.is_home:
                    continue
                idle_minutes = (now - p.last_seen).total_seconds() / 60
                if idle_minutes >= t.idle_threshold_min:
                    t.fired_count += 1
                    t.last_fired = now
                    fired.append(t.trigger_id)
        return fired

    def get_triggers(self) -> list[dict[str, Any]]:
        """Get all registered triggers."""
        return [
            {
                "trigger_id": t.trigger_id,
                "trigger_type": t.trigger_type,
                "person_id": t.person_id,
                "room_id": t.room_id,
                "active": t.active,
                "fired_count": t.fired_count,
                "last_fired": t.last_fired.isoformat() if t.last_fired else None,
            }
            for t in self._triggers.values()
        ]

    # ── Analytics ─────────────────────────────────────────────────────────

    def get_room_occupancy(self, room_id: str) -> RoomOccupancy:
        """Get occupancy stats for a room."""
        persons = [
            p.person_id for p in self._persons.values()
            if p.current_room == room_id and p.is_home
        ]
        visits = [v for v in self._visit_log if v[1] == room_id]
        completed = [v for v in visits if v[3] is not None]
        durations = [(v[3] - v[2]).total_seconds() / 60 for v in completed]
        avg_dur = sum(durations) / len(durations) if durations else 0.0

        # Peak hour
        hour_counts: dict[int, int] = defaultdict(int)
        for v in visits:
            hour_counts[v[2].hour] += 1
        peak = max(hour_counts, key=hour_counts.get) if hour_counts else 0

        return RoomOccupancy(
            room_id=room_id,
            room_name=self._rooms.get(room_id, room_id),
            current_count=len(persons),
            persons=persons,
            total_visits=len(visits),
            avg_duration_min=round(avg_dur, 1),
            peak_hour=peak,
        )

    def get_heatmap(self, hours: int = 24) -> list[HeatmapEntry]:
        """Get occupancy heatmap for last N hours."""
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(hours=hours)
        recent = [v for v in self._visit_log if v[2] >= cutoff]

        # Group by room and hour
        room_hour: dict[tuple[str, int], int] = defaultdict(int)
        for _, room_id, enter, _ in recent:
            room_hour[(room_id, enter.hour)] += 1

        entries = []
        for (room_id, hour), count in sorted(room_hour.items()):
            entries.append(HeatmapEntry(
                room_id=room_id,
                hour=hour,
                visit_count=count,
                occupancy_avg=count / max(1, hours / 24),
            ))
        return entries

    def get_transitions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent room transitions."""
        return [
            {
                "person_id": t.person_id,
                "from_room": t.from_room,
                "to_room": t.to_room,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in reversed(self._transitions[-limit:])
        ]

    # ── Household status ──────────────────────────────────────────────────

    def get_household_status(self) -> dict[str, Any]:
        """Get household-level presence status."""
        if not self._persons:
            return {"status": "unknown", "persons_home": 0, "persons_away": 0, "total": 0}

        home = [p for p in self._persons.values() if p.is_home]
        away = [p for p in self._persons.values() if not p.is_home]

        if len(home) == 0:
            status = "away"
        elif len(away) == 0:
            status = "home"
        else:
            status = "partial"

        return {
            "status": status,
            "persons_home": len(home),
            "persons_away": len(away),
            "total": len(self._persons),
            "home_names": [p.name for p in home],
            "away_names": [p.name for p in away],
        }

    # ── Dashboard ─────────────────────────────────────────────────────────

    def get_dashboard(self) -> PresenceIntelligenceDashboard:
        """Get presence intelligence dashboard."""
        home = [p for p in self._persons.values() if p.is_home]
        away = [p for p in self._persons.values() if not p.is_home]
        occupied = set()
        for p in home:
            if p.current_room:
                occupied.add(p.current_room)

        household = self.get_household_status()
        active_triggers = sum(1 for t in self._triggers.values() if t.active)

        return PresenceIntelligenceDashboard(
            total_persons=len(self._persons),
            persons_home=len(home),
            persons_away=len(away),
            total_rooms=len(self._rooms),
            occupied_rooms=len(occupied),
            recent_transitions=self.get_transitions(5),
            room_occupancy=self.get_rooms(),
            active_triggers=active_triggers,
            household_status=household["status"],
        )
