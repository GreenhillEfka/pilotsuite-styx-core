"""Habitus-Zonen — Room-to-Zone Grouping with Entity Adoption (v6.4.0).

Features:
- Group HA rooms into Habitus-Zonen (e.g. Bad + Toilette => Badbereich)
- Automatic entity adoption from rooms into zones
- Zone-level aggregation (temperature, humidity, occupancy)
- Zone states: active, idle, sleeping, party, away
- Quick zone mode switching (Party, Schlafmodus, etc.)
- Optional dashboard per zone
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class RoomConfig:
    """A HA room configuration."""

    room_id: str
    name: str
    area_id: str = ""  # HA area_id
    entities: list[str] = field(default_factory=list)
    floor: str = ""
    icon: str = "mdi:door"


@dataclass
class HabitusZone:
    """A Habitus Zone grouping multiple rooms."""

    zone_id: str
    name: str
    rooms: list[str] = field(default_factory=list)  # room_ids
    icon: str = "mdi:home-floor-1"
    mode: str = "active"  # active, idle, sleeping, party, away, custom
    entities: list[str] = field(default_factory=list)  # all entities from all rooms
    enabled: bool = True
    priority: int = 0  # higher = more important
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class ZoneState:
    """Current state of a zone."""

    zone_id: str
    name: str
    mode: str
    room_count: int
    entity_count: int
    enabled: bool
    avg_temperature: float | None = None
    avg_humidity: float | None = None
    occupancy: bool = False
    light_on_count: int = 0
    active_devices: int = 0
    last_activity: datetime | None = None


@dataclass
class ZoneOverview:
    """Overview of all zones."""

    total_zones: int = 0
    total_rooms: int = 0
    total_entities: int = 0
    active_zones: int = 0
    zones: list[dict[str, Any]] = field(default_factory=list)
    modes: dict[str, int] = field(default_factory=dict)
    unassigned_rooms: list[str] = field(default_factory=list)


# ── Predefined zone templates ──────────────────────────────────────────────

_ZONE_TEMPLATES = {
    "wohnbereich": {
        "name": "Wohnbereich",
        "icon": "mdi:sofa",
        "rooms": ["wohnzimmer", "esszimmer"],
    },
    "badbereich": {
        "name": "Badbereich",
        "icon": "mdi:shower-head",
        "rooms": ["bad", "badezimmer", "toilette", "gäste-wc", "gaeste_wc"],
    },
    "schlafbereich": {
        "name": "Schlafbereich",
        "icon": "mdi:bed",
        "rooms": ["schlafzimmer", "kinderzimmer", "gästezimmer"],
    },
    "küchenbereich": {
        "name": "Küchenbereich",
        "icon": "mdi:stove",
        "rooms": ["küche", "kueche", "speisekammer", "vorratskammer"],
    },
    "eingangsbereich": {
        "name": "Eingangsbereich",
        "icon": "mdi:door-open",
        "rooms": ["flur", "diele", "eingang", "garderobe"],
    },
    "außenbereich": {
        "name": "Außenbereich",
        "icon": "mdi:tree",
        "rooms": ["garten", "terrasse", "balkon", "garage", "carport"],
    },
    "büro": {
        "name": "Büro / Arbeitszimmer",
        "icon": "mdi:desk",
        "rooms": ["büro", "buero", "arbeitszimmer", "homeoffice"],
    },
}

# Zone modes with descriptions
_ZONE_MODES = {
    "active": {"name": "Aktiv", "icon": "mdi:play-circle", "automations": True},
    "idle": {"name": "Leerlauf", "icon": "mdi:pause-circle", "automations": True},
    "sleeping": {"name": "Schlafmodus", "icon": "mdi:sleep", "automations": False},
    "party": {"name": "Partymodus", "icon": "mdi:party-popper", "automations": False},
    "away": {"name": "Abwesend", "icon": "mdi:home-export-outline", "automations": True},
    "custom": {"name": "Benutzerdefiniert", "icon": "mdi:cog", "automations": True},
}


# ── Engine ──────────────────────────────────────────────────────────────────


class HabitusZoneEngine:
    """Engine for managing Habitus-Zonen."""

    def __init__(
        self,
        storage_path: str | None = None,
        *,
        enable_persistence: bool = True,
    ) -> None:
        self._rooms: dict[str, RoomConfig] = {}
        self._zones: dict[str, HabitusZone] = {}
        self._entity_values: dict[str, Any] = {}  # entity_id -> current value
        self._entity_types: dict[str, str] = {}  # entity_id -> domain (light, sensor, etc.)
        self._persistence_enabled = bool(enable_persistence)
        default_store = os.environ.get("HABITUS_ZONES_STORE", "/data/hub_habitus_zones.json")
        self._storage_path = Path(storage_path or default_store)
        if self._persistence_enabled:
            self._load_state()

    # ── Persistence ────────────────────────────────────────────────────

    def _resolve_writable_store(self) -> Path | None:
        if not self._persistence_enabled:
            return None
        path = self._storage_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.touch()
            return path
        except Exception:
            fallback_dir = os.environ.get("COPILOT_HABITUS_DIR", "").strip()
            if not fallback_dir:
                logger.warning("Habitus persistence disabled: store path not writable (%s)", path)
                self._persistence_enabled = False
                return None
            fallback = Path(fallback_dir) / path.name
            fallback.parent.mkdir(parents=True, exist_ok=True)
            self._storage_path = fallback
            return fallback

    def _persist_state(self) -> None:
        path = self._resolve_writable_store()
        if path is None:
            return
        payload = {
            "rooms": [
                {
                    "room_id": room.room_id,
                    "name": room.name,
                    "area_id": room.area_id,
                    "entities": list(room.entities),
                    "floor": room.floor,
                    "icon": room.icon,
                }
                for room in self._rooms.values()
            ],
            "zones": [
                {
                    "zone_id": zone.zone_id,
                    "name": zone.name,
                    "rooms": list(zone.rooms),
                    "icon": zone.icon,
                    "mode": zone.mode,
                    "entities": list(zone.entities),
                    "enabled": zone.enabled,
                    "priority": zone.priority,
                    "settings": dict(zone.settings or {}),
                }
                for zone in self._zones.values()
            ],
        }
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist habitus zones state: %s", exc)

    def _load_state(self) -> None:
        path = self._resolve_writable_store()
        if path is None:
            return
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return

        rooms = raw.get("rooms", [])
        zones = raw.get("zones", [])
        if isinstance(rooms, list):
            for room in rooms:
                if not isinstance(room, dict):
                    continue
                rid = str(room.get("room_id") or "").strip()
                if not rid:
                    continue
                cfg = RoomConfig(
                    room_id=rid,
                    name=str(room.get("name") or rid),
                    area_id=str(room.get("area_id") or ""),
                    entities=[str(e) for e in (room.get("entities") or []) if str(e)],
                    floor=str(room.get("floor") or ""),
                    icon=str(room.get("icon") or "mdi:door"),
                )
                self._rooms[rid] = cfg
                for entity_id in cfg.entities:
                    domain = entity_id.split(".", 1)[0] if "." in entity_id else "unknown"
                    self._entity_types[entity_id] = domain

        if isinstance(zones, list):
            for zone in zones:
                if not isinstance(zone, dict):
                    continue
                zid = str(zone.get("zone_id") or "").strip()
                if not zid:
                    continue
                self._zones[zid] = HabitusZone(
                    zone_id=zid,
                    name=str(zone.get("name") or zid),
                    rooms=[str(r) for r in (zone.get("rooms") or []) if str(r)],
                    icon=str(zone.get("icon") or "mdi:home-floor-1"),
                    mode=str(zone.get("mode") or "active"),
                    entities=[str(e) for e in (zone.get("entities") or []) if str(e)],
                    enabled=bool(zone.get("enabled", True)),
                    priority=int(zone.get("priority", 0)),
                    settings=dict(zone.get("settings") or {}),
                )
        logger.info(
            "HabitusZoneEngine state loaded: %d rooms, %d zones",
            len(self._rooms),
            len(self._zones),
        )

    # ── Room management ─────────────────────────────────────────────────

    def register_room(self, room_id: str, name: str, area_id: str = "",
                      entities: list[str] | None = None,
                      floor: str = "", icon: str = "mdi:door") -> RoomConfig:
        """Register a room (from HA area)."""
        room = RoomConfig(
            room_id=room_id,
            name=name,
            area_id=area_id,
            entities=entities or [],
            floor=floor,
            icon=icon,
        )
        self._rooms[room_id] = room

        # Classify entities by domain
        for entity_id in room.entities:
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            self._entity_types[entity_id] = domain

        logger.info("Raum '%s' registriert mit %d Entitäten", name, len(room.entities))
        self._persist_state()
        return room

    def update_room_entities(self, room_id: str, entities: list[str]) -> bool:
        """Update entities for a room (e.g. after HA discovery)."""
        room = self._rooms.get(room_id)
        if not room:
            return False
        room.entities = entities
        for eid in entities:
            domain = eid.split(".")[0] if "." in eid else "unknown"
            self._entity_types[eid] = domain

        # Update zones that contain this room
        for zone in self._zones.values():
            if room_id in zone.rooms:
                self._refresh_zone_entities(zone)
        self._persist_state()
        return True

    def get_room(self, room_id: str) -> dict[str, Any] | None:
        """Get room details."""
        room = self._rooms.get(room_id)
        if not room:
            return None
        return {
            "room_id": room.room_id,
            "name": room.name,
            "area_id": room.area_id,
            "entities": room.entities,
            "entity_count": len(room.entities),
            "floor": room.floor,
            "icon": room.icon,
            "zone": self._find_zone_for_room(room_id),
        }

    def get_rooms(self) -> list[dict[str, Any]]:
        """Get all rooms."""
        return [self.get_room(rid) for rid in self._rooms if self.get_room(rid)]

    # ── Zone management ─────────────────────────────────────────────────

    def create_zone(self, zone_id: str, name: str, room_ids: list[str] | None = None,
                    icon: str = "mdi:home-floor-1", priority: int = 0) -> HabitusZone:
        """Create a new Habitus Zone."""
        zone = HabitusZone(
            zone_id=zone_id,
            name=name,
            rooms=room_ids or [],
            icon=icon,
            priority=priority,
        )
        self._refresh_zone_entities(zone)
        self._zones[zone_id] = zone
        logger.info("Habitus-Zone '%s' erstellt mit %d Räumen, %d Entitäten",
                     name, len(zone.rooms), len(zone.entities))
        self._persist_state()
        return zone

    def create_zone_from_template(self, template_id: str) -> HabitusZone | None:
        """Create a zone from a predefined template, auto-matching rooms."""
        template = _ZONE_TEMPLATES.get(template_id)
        if not template:
            return None

        matched_rooms = []
        for room_id, room in self._rooms.items():
            room_name_lower = room.name.lower().replace(" ", "")
            for pattern in template["rooms"]:
                if pattern in room_name_lower or room_name_lower in pattern:
                    matched_rooms.append(room_id)
                    break

        zone = self.create_zone(
            zone_id=template_id,
            name=template["name"],
            room_ids=matched_rooms,
            icon=template["icon"],
        )
        return zone

    def add_room_to_zone(self, zone_id: str, room_id: str) -> bool:
        """Add a room to a zone (with entity adoption)."""
        zone = self._zones.get(zone_id)
        if not zone or room_id not in self._rooms:
            return False
        if room_id in zone.rooms:
            return True  # already assigned
        zone.rooms.append(room_id)
        self._refresh_zone_entities(zone)
        self._persist_state()
        return True

    def remove_room_from_zone(self, zone_id: str, room_id: str) -> bool:
        """Remove a room from a zone."""
        zone = self._zones.get(zone_id)
        if not zone or room_id not in zone.rooms:
            return False
        zone.rooms.remove(room_id)
        self._refresh_zone_entities(zone)
        self._persist_state()
        return True

    def delete_zone(self, zone_id: str) -> bool:
        """Delete a zone (rooms remain registered)."""
        if zone_id not in self._zones:
            return False
        del self._zones[zone_id]
        self._persist_state()
        return True

    def set_zone_mode(self, zone_id: str, mode: str) -> bool:
        """Set zone mode (active/idle/sleeping/party/away/custom)."""
        zone = self._zones.get(zone_id)
        if not zone or mode not in _ZONE_MODES:
            return False
        zone.mode = mode
        logger.info("Zone '%s' Modus → %s", zone.name, _ZONE_MODES[mode]["name"])
        self._persist_state()
        return True

    def set_zone_enabled(self, zone_id: str, enabled: bool) -> bool:
        """Enable or disable a zone."""
        zone = self._zones.get(zone_id)
        if not zone:
            return False
        zone.enabled = enabled
        self._persist_state()
        return True

    def set_zone_settings(self, zone_id: str, settings: dict[str, Any]) -> bool:
        """Update zone settings."""
        zone = self._zones.get(zone_id)
        if not zone:
            return False
        zone.settings.update(settings)
        # Settings may influence entity composition (e.g. extra_entities).
        self._refresh_zone_entities(zone)
        self._persist_state()
        return True

    # ── Entity state tracking ───────────────────────────────────────────

    def update_entity_state(self, entity_id: str, value: Any) -> None:
        """Update entity state (called from HA state changes)."""
        self._entity_values[entity_id] = value

    def update_entity_states_batch(self, states: dict[str, Any]) -> int:
        """Batch update entity states."""
        count = 0
        for eid, value in states.items():
            self._entity_values[eid] = value
            count += 1
        return count

    # ── Zone state queries ──────────────────────────────────────────────

    def get_zone_state(self, zone_id: str) -> ZoneState | None:
        """Get current state of a zone."""
        zone = self._zones.get(zone_id)
        if not zone:
            return None

        temps = []
        humids = []
        light_on = 0
        active = 0
        occupancy = False

        for eid in zone.entities:
            domain = self._entity_types.get(eid, "")
            value = self._entity_values.get(eid)

            if value is None:
                continue

            if domain == "sensor":
                if "temperature" in eid or "temp" in eid:
                    try:
                        temps.append(float(value))
                    except (ValueError, TypeError):
                        pass
                elif "humidity" in eid or "feucht" in eid:
                    try:
                        humids.append(float(value))
                    except (ValueError, TypeError):
                        pass

            elif domain == "light":
                if value in ("on", True, "True"):
                    light_on += 1
                    active += 1

            elif domain == "binary_sensor":
                if ("motion" in eid or "presence" in eid or "bewegung" in eid) \
                        and value in ("on", True, "True"):
                    occupancy = True

            if value not in (None, "off", False, "False", "unavailable", "unknown"):
                active += 1

        return ZoneState(
            zone_id=zone.zone_id,
            name=zone.name,
            mode=zone.mode,
            room_count=len(zone.rooms),
            entity_count=len(zone.entities),
            enabled=zone.enabled,
            avg_temperature=round(sum(temps) / len(temps), 1) if temps else None,
            avg_humidity=round(sum(humids) / len(humids), 1) if humids else None,
            occupancy=occupancy,
            light_on_count=light_on,
            active_devices=active,
            last_activity=datetime.now(tz=timezone.utc) if occupancy else None,
        )

    def get_zone(self, zone_id: str) -> dict[str, Any] | None:
        """Get zone details including rooms and entities."""
        zone = self._zones.get(zone_id)
        if not zone:
            return None

        state = self.get_zone_state(zone_id)
        rooms = []
        for rid in zone.rooms:
            room = self._rooms.get(rid)
            if room:
                rooms.append({"room_id": rid, "name": room.name, "entities": len(room.entities)})

        return {
            "zone_id": zone.zone_id,
            "name": zone.name,
            "icon": zone.icon,
            "mode": zone.mode,
            "mode_name": _ZONE_MODES.get(zone.mode, {}).get("name", zone.mode),
            "enabled": zone.enabled,
            "priority": zone.priority,
            "rooms": rooms,
            "room_count": len(zone.rooms),
            "entity_count": len(zone.entities),
            "entities": zone.entities,
            "settings": zone.settings,
            "state": {
                "avg_temperature": state.avg_temperature if state else None,
                "avg_humidity": state.avg_humidity if state else None,
                "occupancy": state.occupancy if state else False,
                "light_on_count": state.light_on_count if state else 0,
                "active_devices": state.active_devices if state else 0,
            },
        }

    def get_overview(self) -> ZoneOverview:
        """Get complete zone overview."""
        assigned_rooms = set()
        modes: dict[str, int] = defaultdict(int)
        zone_list = []

        for zone in self._zones.values():
            assigned_rooms.update(zone.rooms)
            modes[zone.mode] += 1
            zone_list.append({
                "zone_id": zone.zone_id,
                "name": zone.name,
                "icon": zone.icon,
                "mode": zone.mode,
                "enabled": zone.enabled,
                "room_count": len(zone.rooms),
                "entity_count": len(zone.entities),
                "entities": list(zone.entities),
            })

        unassigned = [rid for rid in self._rooms if rid not in assigned_rooms]

        return ZoneOverview(
            total_zones=len(self._zones),
            total_rooms=len(self._rooms),
            total_entities=sum(len(z.entities) for z in self._zones.values()),
            active_zones=sum(1 for z in self._zones.values() if z.enabled),
            zones=zone_list,
            modes=dict(modes),
            unassigned_rooms=unassigned,
        )

    def get_templates(self) -> list[dict[str, Any]]:
        """Get available zone templates."""
        return [
            {"template_id": tid, "name": t["name"], "icon": t["icon"],
             "room_patterns": t["rooms"]}
            for tid, t in _ZONE_TEMPLATES.items()
        ]

    def get_modes(self) -> list[dict[str, Any]]:
        """Get available zone modes."""
        return [
            {"mode_id": mid, "name": m["name"], "icon": m["icon"],
             "automations_enabled": m["automations"]}
            for mid, m in _ZONE_MODES.items()
        ]

    # ── Helpers ─────────────────────────────────────────────────────────

    def _refresh_zone_entities(self, zone: HabitusZone) -> None:
        """Rebuild zone entity list from assigned rooms."""
        entities = []
        for rid in zone.rooms:
            room = self._rooms.get(rid)
            if room:
                entities.extend(room.entities)
        # Optional explicit exclusions (e.g. when an entity is "moved" to another zone).
        exclude_set: set[str] = set()
        if isinstance(zone.settings, dict):
            raw_exclude = zone.settings.get("exclude_entities", [])
            if isinstance(raw_exclude, list):
                exclude_set = {str(e) for e in raw_exclude if str(e)}
            elif isinstance(raw_exclude, str) and raw_exclude.strip():
                exclude_set = {s.strip() for s in raw_exclude.split(",") if s.strip()}
        if exclude_set:
            entities = [e for e in entities if e not in exclude_set]
        # Optional explicit entities that are not tied to a room (zone UX assignments).
        extra = []
        if isinstance(zone.settings, dict):
            raw_extra = zone.settings.get("extra_entities", [])
            if isinstance(raw_extra, list):
                extra = [str(e) for e in raw_extra if str(e)]
            elif isinstance(raw_extra, str) and raw_extra.strip():
                extra = [s.strip() for s in raw_extra.split(",") if s.strip()]
        entities.extend(extra)
        zone.entities = list(dict.fromkeys(entities))  # deduplicate preserving order

    def _find_zone_for_room(self, room_id: str) -> str | None:
        """Find which zone a room belongs to."""
        for zone in self._zones.values():
            if room_id in zone.rooms:
                return zone.zone_id
        return None
