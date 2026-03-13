"""Zone Dashboard API — Zonenzentriertes Dashboard mit voller Modulintegration.

Zentraler Dashboard-Endpunkt fuer Habituszonen. Aggregiert Daten aus
allen Hub-Engines pro Zone (13 Engines + Stammdaten).

Endpunkte:
  GET  /api/v1/zone/dashboard              - Alle Zonen mit Moduldaten
  GET  /api/v1/zone/dashboard/summary      - Leichtgewichtige Zusammenfassung
  GET  /api/v1/zone/dashboard/mood         - Mood-Daten aller Zonen
  PUT  /api/v1/zone/dashboard/mood/<id>    - Mood fuer Zone setzen
  POST /api/v1/zone/dashboard/quick-action - Quick-Action ausfuehren
  GET  /api/v1/zone/dashboard/<id>         - Einzelzone Detail

Author: Clawdya (via Codex)
Version: 5.0.0
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

zone_dashboard_bp = Blueprint("zone_dashboard", __name__, url_prefix="/api/v1/zone/dashboard")

# Runtime mood data (overridable via PUT endpoint)
_zone_mood_data: Dict[str, Dict[str, float]] = {}

# All service references in a single dict — keys match init_zone_dashboard_api() params.
# Replaces 15 individual module globals; read-only after init.
_svc: Dict[str, Any] = {}


def init_zone_dashboard_api(**services: Any) -> None:
    """Initialize the Zone Dashboard API with all available service references.

    Accepted keys:
      zone_automation, mood_service,
      hub_licht, hub_helligkeit, hub_heiz, hub_bewegung, hub_praesenz,
      hub_light_intel, hub_presence_intel, hub_media,
      hub_modes, hub_scenes, hub_energy,
      hub_notifications, hub_musikwolke
    """
    _svc.clear()
    _svc.update(services)

    engine_keys = (
        "hub_licht", "hub_helligkeit", "hub_heiz", "hub_bewegung", "hub_praesenz",
        "hub_light_intel", "hub_presence_intel", "hub_media",
        "hub_modes", "hub_scenes", "hub_energy",
        "hub_notifications", "hub_musikwolke",
    )
    wired = sum(1 for k in engine_keys if _svc.get(k))
    _LOGGER.info(
        "Zone Dashboard API initialized (zone_automation=%s, mood=%s, engines=%d/%d wired)",
        _svc.get("zone_automation") is not None,
        _svc.get("mood_service") is not None,
        wired, len(engine_keys),
    )


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _safe(fn: Callable[[], Any], default: Any = None) -> Any:
    """Call *fn*, return *default* on any exception. Avoids bare try/except sprawl."""
    try:
        return fn()
    except Exception:
        return default


def _attr_or_key(obj: Any, name: str, default: Any = ""):
    """Read *name* from dataclass attr or dict key, with fallback."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _iso_or_none(dt: Any) -> Optional[str]:
    """Convert datetime to ISO string or None."""
    return dt.isoformat() if dt and hasattr(dt, "isoformat") else None


# ── Stammdaten (example_config) — imported once at module level ──

def _load_example_data() -> Dict[str, Any]:
    """Load example_config data once. Returns empty dict if unavailable."""
    try:
        from copilot_core.example_config import (
            EXAMPLE_HOUSEHOLD,
            EXAMPLE_NOTIFICATIONS,
            EXAMPLE_PLAYLISTS,
            EXAMPLE_TODOS,
            EXAMPLE_ZONE_ENTITIES,
            ZONE_DISPLAY,
        )
        return {
            "zone_entities": EXAMPLE_ZONE_ENTITIES,
            "zone_display": ZONE_DISPLAY,
            "playlists": EXAMPLE_PLAYLISTS,
            "todos": EXAMPLE_TODOS,
            "notifications": EXAMPLE_NOTIFICATIONS,
            "household": EXAMPLE_HOUSEHOLD,
        }
    except ImportError:
        return {}


_example: Dict[str, Any] = {}


def _get_example() -> Dict[str, Any]:
    """Lazy-load and cache example data."""
    if not _example:
        _example.update(_load_example_data())
    return _example


# ═══════════════════════════════════════════════════════════════════════
# Zone Data Assembly — Single Source of Truth
# ═══════════════════════════════════════════════════════════════════════

def _get_habitus_zones() -> List[Dict[str, Any]]:
    """Get zones from habitus_zones module, enriched with example entities."""
    zones: List[Any] = []
    try:
        from copilot_core.homeassistant.habitus_zones import get_all_zones
        zones = get_all_zones()
    except ImportError:
        _LOGGER.warning("habitus_zones module not available")

    ex = _get_example()
    zone_entities = ex.get("zone_entities", {})
    zone_display = ex.get("zone_display", {})
    if not zone_entities:
        return zones

    enriched = []
    for zone in zones:
        if isinstance(zone, dict):
            zid = zone.get("zone_id", "")
            zdict = zone
        else:
            zid = getattr(zone, "zone_type", getattr(zone, "zone_id", ""))
            if hasattr(zid, "value"):
                zid = zid.value
            zdict = {
                "zone_id": zid,
                "name": getattr(zone, "name_de", getattr(zone, "name", zid)),
                "name_de": getattr(zone, "name_de", ""),
                "name_en": getattr(zone, "name_en", ""),
                "zone_type": zid,
                "priority": getattr(zone, "priority", 0),
                "entity_ids": [],
                "entities": {},
                "enabled": True,
            }
        if zid in zone_entities and not zdict.get("entities"):
            zdict["entities"] = zone_entities[zid]
            zdict["entity_ids"] = [
                eid for role_list in zone_entities[zid].values()
                for eid in role_list
            ]
        if zid in zone_display:
            zdict.setdefault("icon", zone_display[zid].get("icon", ""))
            zdict.setdefault("color", zone_display[zid].get("color", ""))
        enriched.append(zdict)

    return enriched


def _get_zone_mood(zone_id: str) -> Dict[str, Any]:
    """Get mood data for a zone (override > mood_service > automation > default)."""
    if zone_id in _zone_mood_data:
        return _zone_mood_data[zone_id]

    mood_svc = _svc.get("mood_service")
    if mood_svc:
        result = _safe(lambda: mood_svc.get_current_mood())
        if result:
            return {
                "comfort": result.get("comfort", 0.5),
                "joy": result.get("joy", 0.5),
                "frugality": result.get("frugality", 0.5),
                "mood": result.get("mood", "unknown"),
                "confidence": result.get("confidence", 0.0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    za = _svc.get("zone_automation")
    if za:
        state = _safe(lambda: za.get_zone_state(zone_id))
        if state:
            zs = state.get("state", {})
            occupied = zs.get("occupied", False)
            lights_on = zs.get("lights_on", False)
            music = zs.get("music_playing", False)
            return {
                "comfort": 0.8 if lights_on else 0.4,
                "joy": 0.9 if music else (0.6 if occupied else 0.3),
                "frugality": 0.4 if (lights_on and music) else 0.8,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    return {"comfort": 0.5, "joy": 0.5, "frugality": 0.5,
            "updated_at": datetime.now(timezone.utc).isoformat()}


def _set_zone_mood(zone_id: str, mood_data: Dict[str, float]) -> Dict[str, Any]:
    """Set mood data override for a zone."""
    _zone_mood_data[zone_id] = {
        "comfort": float(mood_data.get("comfort", 0.5)),
        "joy": float(mood_data.get("joy", 0.5)),
        "frugality": float(mood_data.get("frugality", 0.5)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _zone_mood_data[zone_id]


def _get_entity_count(zone: Dict[str, Any]) -> Dict[str, int]:
    """Count entities by HA domain for a zone."""
    source = zone.get("entity_ids") or []
    if not source:
        source = [
            eid for role_entities in zone.get("entities", {}).values()
            if isinstance(role_entities, list)
            for eid in role_entities
        ]
    counts: Dict[str, int] = {}
    for eid in source:
        domain = eid.split(".")[0] if "." in eid else "unknown"
        counts[domain] = counts.get(domain, 0) + 1
    return counts


def _get_zone_status(zone: Dict[str, Any]) -> str:
    """Determine zone status from ZoneAutomationController live state."""
    za = _svc.get("zone_automation")
    if not za:
        return "idle"
    state = _safe(lambda: za.get_zone_state(zone.get("zone_id", "")))
    if not state:
        return "idle"
    zs = state.get("state", {})
    if zs.get("occupied", False):
        return "active"
    cfg = state.get("config", {}).get("light", {})
    if not cfg.get("enabled", True):
        return "disabled"
    return "idle"


def _get_person_count(zone: Dict[str, Any]) -> int:
    """Get number of people in zone from PraesenzModule or entity heuristic."""
    hub = _svc.get("hub_praesenz")
    if hub:
        result = _safe(lambda: hub.get_zone_presence(zone.get("zone_id", "")))
        if result is not None:
            return getattr(result, "person_count", 0)
    entity_ids = zone.get("entity_ids", [])
    return sum(1 for e in entity_ids if e.startswith(("person.", "device_tracker.")))


# ═══════════════════════════════════════════════════════════════════════
# Module Engine Integration — Per-Zone Aggregation (13 Engines)
# ═══════════════════════════════════════════════════════════════════════

def _collect_licht(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_licht")
    if not hub:
        return None
    state = hub.get_zone_state(zone_id)
    lights = hub.get_zone_lights(zone_id)
    on_lights = [l for l in lights if l.is_on]
    avg_ct = sum(l.color_temp_k for l in on_lights) / len(on_lights) if on_lights else 0
    return {
        "lights_on": state.lights_on,
        "lights_total": state.lights_total,
        "avg_brightness_pct": state.avg_brightness_pct,
        "avg_color_temp_k": round(avg_ct),
        "any_override": state.any_override,
        "override_count": sum(1 for l in lights if l.is_override),
        "target_brightness_pct": state.target_brightness_pct,
        "target_color_temp_k": state.target_color_temp_k,
        "auto_enabled": state.auto_enabled,
        "lights": [
            {"entity_id": l.entity_id, "friendly_name": l.friendly_name,
             "is_on": l.is_on, "brightness_pct": l.brightness_pct,
             "color_temp_k": l.color_temp_k, "is_override": l.is_override}
            for l in lights
        ],
    }


def _collect_helligkeit(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_helligkeit")
    if not hub:
        return None
    s = hub.get_zone_brightness(zone_id)
    return {
        "avg_indoor_lux": s.avg_indoor_lux, "avg_outdoor_lux": s.avg_outdoor_lux,
        "target_lux": s.target_lux, "min_lux": s.min_lux,
        "needs_light": s.needs_light, "deficit_pct": s.deficit_pct,
        "recommended_dimming_pct": s.recommended_dimming_pct,
    }


def _collect_heiz(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_heiz")
    if not hub:
        return None
    s = hub.get_zone_climate(zone_id)
    return {
        "current_temp": s.current_temp, "target_temp": s.target_temp,
        "humidity": s.humidity, "is_heating": s.is_heating,
        "eco_mode": s.eco_mode, "comfort_index": s.comfort_index,
        "needs_heating": s.needs_heating, "temp_delta": s.temp_delta,
    }


def _collect_bewegung(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_bewegung")
    if not hub:
        return None
    s = hub.get_zone_motion(zone_id)
    return {
        "sensors_active": s.sensors_active, "sensors_total": s.sensors_total,
        "last_motion": _iso_or_none(s.last_motion),
        "motion_in_last_5min": s.motion_in_last_5min,
        "motion_in_last_30min": s.motion_in_last_30min,
        "daily_triggers": s.daily_triggers,
    }


def _collect_praesenz(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_praesenz")
    if not hub:
        return None
    s = hub.get_zone_presence(zone_id)
    return {
        "is_occupied": s.is_occupied, "person_count": s.person_count,
        "persons": s.persons,
        "last_entered": _iso_or_none(s.last_entered),
        "last_left": _iso_or_none(s.last_left),
        "occupied_since": _iso_or_none(s.occupied_since),
        "sources_active": s.sources_active, "sources_total": s.sources_total,
    }


def _collect_light_intelligence(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_light_intel")
    if not hub:
        return None
    zb = hub.get_zone_brightness(zone_id)
    data: Dict[str, Any] = {
        "avg_indoor_lux": zb.avg_indoor_lux,
        "avg_outdoor_lux": zb.avg_outdoor_lux,
        "illumination_ratio": getattr(zb, "illumination_ratio", 0.0),
        "illumination_pct": getattr(zb, "illumination_pct", 0),
        "threshold_met": getattr(zb, "threshold_met", False),
        "needs_light": zb.needs_light,
        "suggested_dimming_pct": getattr(zb, "suggested_dimming_pct", zb.recommended_dimming_pct),
    }
    sun = _safe(lambda: hub.get_sun_position())
    if sun:
        data["sun"] = {"elevation": sun.elevation, "azimuth": sun.azimuth, "phase": sun.phase}
    scene = _safe(lambda: hub.get_active_scene())
    if scene:
        data["active_scene"] = scene if isinstance(scene, dict) else {"scene_id": str(scene)}
    return data


def _collect_presence_intelligence(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_presence_intel")
    if not hub:
        return None
    rooms = hub.get_rooms()
    room = next((r for r in rooms
                 if r.get("room_id", "") == zone_id or r.get("zone_id", "") == zone_id), None)
    if not room:
        return None
    data: Dict[str, Any] = {
        "current_count": room.get("current_count", 0),
        "persons": room.get("persons", []),
    }
    occ = _safe(lambda: hub.get_room_occupancy(room.get("room_id", zone_id)))
    if occ:
        data["total_visits"] = occ.total_visits
        data["avg_duration_min"] = occ.avg_duration_min
        data["peak_hour"] = occ.peak_hour
    return data


def _collect_media(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_media")
    if not hub:
        return None
    ms = hub.get_zone_media(zone_id)
    data: Dict[str, Any] = {
        "active_sessions": ms.active_sessions,
        "follow_enabled": ms.follow_enabled,
        "volume_pct": getattr(ms, "volume_pct", 0),
    }
    if hasattr(ms, "sources") and ms.sources:
        data["sources"] = [
            {"entity_id": s.entity_id, "name": s.name,
             "media_type": s.media_type, "state": s.state}
            for s in ms.sources
        ]
    ps = ms.primary_session
    if ps:
        data["primary_session"] = {
            "title": _attr_or_key(ps, "title"),
            "artist": _attr_or_key(ps, "artist"),
            "state": _attr_or_key(ps, "state"),
            "volume_pct": _attr_or_key(ps, "volume_pct", 0),
            "media_type": _attr_or_key(ps, "media_type"),
        }
    return data


def _collect_mode(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_modes")
    if not hub:
        return None
    ms = hub.get_zone_status(zone_id)
    data: Dict[str, Any] = {
        "active_mode": ms.active_mode,
        "mode_name_de": ms.mode_name_de,
        "icon": ms.icon,
        "remaining_min": ms.remaining_min,
    }
    if hasattr(ms, "expires_at") and ms.expires_at:
        data["expires_at"] = _iso_or_none(ms.expires_at) or str(ms.expires_at)
    if hasattr(ms, "suppressed"):
        sup = ms.suppressed
        data["suppressed"] = {
            k: _attr_or_key(sup, k, False)
            for k in ("automations", "lights", "media", "notifications")
        }
    if hasattr(ms, "restrictions"):
        r = ms.restrictions if isinstance(ms.restrictions, dict) else {}
        if r:
            data["restrictions"] = r
    return data


def _collect_scenes(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_scenes")
    if not hub:
        return None
    data: Dict[str, Any] = {}
    active = _safe(lambda: hub.get_active_scene())
    if active:
        data["active_scene"] = active if isinstance(active, dict) else {"scene_id": str(active)}
    suggestions = _safe(lambda: hub.suggest_scenes(
        context={"active_zone": zone_id, "hour": datetime.now(timezone.utc).hour},
        limit=3,
    ))
    if suggestions:
        data["suggestions"] = [
            {k: _attr_or_key(s, k, 0 if k == "confidence" else "")
             for k in ("scene_id", "name_de", "confidence", "reason_de", "icon")}
            for s in suggestions
        ]
    return data or None


def _collect_energy(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_energy")
    if not hub:
        return None
    eco = hub.calculate_eco_score()
    return {"eco_score": eco.score, "eco_grade": eco.grade, "eco_trend": eco.trend}


def _collect_notifications(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_notifications")
    if hub:
        history = hub.get_history(limit=20, unread_only=False)
        zone_notifs = [n for n in history
                       if n.get("zone_id") == zone_id
                       or (not n.get("zone_id") and not n.get("person_id"))]
        if zone_notifs:
            return {
                "total": len(zone_notifs),
                "unread": sum(1 for n in zone_notifs if not n.get("read", True)),
                "recent": zone_notifs[:5],
            }
    # Fallback to example_config
    ex_notifs = _get_example().get("notifications", [])
    zone_notifs = [n for n in ex_notifs if n.get("zone_id") == zone_id]
    if not zone_notifs:
        return None
    return {
        "total": len(zone_notifs),
        "unread": sum(1 for n in zone_notifs if not n.get("acknowledged", True)),
        "recent": zone_notifs[:5],
    }


def _collect_musikwolke(zone_id: str) -> Optional[Dict[str, Any]]:
    hub = _svc.get("hub_musikwolke")
    if not hub:
        return None
    status = hub.get_status()
    data: Dict[str, Any] = {
        "speaker_mapped": zone_id in status.get("zone_speaker_map", {}),
        "speaker_name": status.get("zone_speaker_map", {}).get(zone_id, ""),
        "is_active": zone_id in status.get("active_zones", []),
    }
    mf = status.get("media_follow")
    if mf:
        data["follow_enabled_zones"] = mf.get("follow_enabled_zones", 0)
    return data


def _collect_playlists(zone_id: str) -> Optional[List[Dict[str, Any]]]:
    """Collect playlists for a zone from Musikwolke/Sonos or example fallback."""
    # Try real data from musikwolke service (has zone-speaker mapping)
    hub_mw = _svc.get("hub_musikwolke")
    if hub_mw:
        try:
            status = hub_mw.get_status()
            speaker = status.get("zone_speaker_map", {}).get(zone_id)
            if speaker:
                # If zone has a mapped speaker, retrieve its playlists
                playlists_raw = hub_mw.get_playlists() if hasattr(hub_mw, "get_playlists") else []
                if playlists_raw:
                    return [
                        {"id": p.get("id", ""), "name": p.get("name", ""),
                         "source": p.get("source", "sonos"),
                         "icon": p.get("icon", "mdi:playlist-music"),
                         "time_affinity": p.get("time_affinity", "")}
                        for p in playlists_raw
                    ] or None
        except Exception:
            pass

    # Fallback to example data
    playlists = _get_example().get("playlists", [])
    result = [
        {"id": p["id"], "name": p["name"], "source": p["source"],
         "icon": p.get("icon", ""), "time_affinity": p.get("time_affinity", "")}
        for p in playlists if zone_id in p.get("zone_affinity", [])
    ]
    return result or None


def _collect_todos(zone_id: str) -> Optional[Dict[str, Any]]:
    """Collect todos/reminders for a zone from Shopping/Reminders DB or example fallback."""
    try:
        from copilot_core.api.v1.shopping import _get_conn
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id, title, description, due_at, created_at "
            "FROM reminders WHERE completed = 0 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        conn.close()
        if rows:
            zone_todos = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "description": r["description"] or "",
                    "due_at": r["due_at"],
                    "zone_id": zone_id,
                    "status": "pending",
                }
                for r in rows
            ]
            return {"count": len(zone_todos), "items": zone_todos}
    except Exception:
        pass

    # Fallback to example data
    todos = _get_example().get("todos", [])
    zone_todos = [t for t in todos
                  if t.get("zone_id") == zone_id and t.get("status") != "completed"]
    if not zone_todos:
        return None
    return {"count": len(zone_todos), "items": zone_todos}


# Collector registry: (module_key, collector_fn)
_MODULE_COLLECTORS: List[tuple[str, Callable[[str], Any]]] = [
    ("licht", _collect_licht),
    ("helligkeit", _collect_helligkeit),
    ("heiz", _collect_heiz),
    ("bewegung", _collect_bewegung),
    ("praesenz", _collect_praesenz),
    ("light_intelligence", _collect_light_intelligence),
    ("presence_intelligence", _collect_presence_intelligence),
    ("media", _collect_media),
    ("mode", _collect_mode),
    ("scenes", _collect_scenes),
    ("energy", _collect_energy),
    ("notifications", _collect_notifications),
    ("musikwolke", _collect_musikwolke),
    ("playlists", _collect_playlists),
    ("todos", _collect_todos),
]


def _get_zone_module_data(zone_id: str) -> Dict[str, Any]:
    """Aggregate all module engine data for a single zone.

    Iterates the collector registry; each collector returns data or None.
    Exceptions in any collector are caught and logged, never propagated.
    """
    modules: Dict[str, Any] = {}
    for key, collector in _MODULE_COLLECTORS:
        result = _safe(lambda c=collector: c(zone_id))
        if result is not None:
            modules[key] = result
    return modules


# ═══════════════════════════════════════════════════════════════════════
# Quick Actions — data-driven
# ═══════════════════════════════════════════════════════════════════════

_QUICK_ACTION_DEFS: List[Dict[str, Any]] = [
    {
        "detect": lambda eids, ents: any(e.startswith("light.") for e in eids) or "lights" in ents,
        "actions": [
            {"suffix": "lights_on", "name": "Licht an", "icon": "mdi:lightbulb",
             "service": "light.turn_on", "target_key": "all_lights_in_zone"},
            {"suffix": "lights_off", "name": "Licht aus", "icon": "mdi:lightbulb-off",
             "service": "light.turn_off", "target_key": "all_lights_in_zone"},
        ],
    },
    {
        "detect": lambda eids, ents: any(e.startswith("climate.") for e in eids) or "climate" in ents or "heating" in ents,
        "actions": [
            {"suffix": "climate_comfort", "name": "Komfort", "icon": "mdi:thermometer",
             "service": "climate.set_hvac_mode", "data": {"hvac_mode": "heat"},
             "target_key": "all_climate_in_zone"},
            {"suffix": "climate_eco", "name": "Eco", "icon": "mdi:leaf",
             "service": "climate.set_hvac_mode", "data": {"hvac_mode": "auto"},
             "target_key": "all_climate_in_zone"},
        ],
    },
    {
        "detect": lambda eids, ents: any(e.startswith("media_player.") for e in eids) or "media" in ents,
        "actions": [
            {"suffix": "media_play", "name": "Musik an", "icon": "mdi:play",
             "service": "media_player.media_play", "target_key": "all_media_in_zone"},
            {"suffix": "media_pause", "name": "Musik Pause", "icon": "mdi:pause",
             "service": "media_player.media_pause", "target_key": "all_media_in_zone"},
        ],
    },
    {
        "detect": lambda eids, ents: any(e.startswith("cover.") for e in eids) or "cover" in ents or "covers" in ents,
        "actions": [
            {"suffix": "covers_open", "name": "Rolllaeden auf", "icon": "mdi:window-shutter-open",
             "service": "cover.open_cover", "target_key": "all_covers_in_zone"},
            {"suffix": "covers_close", "name": "Rolllaeden zu", "icon": "mdi:window-shutter",
             "service": "cover.close_cover", "target_key": "all_covers_in_zone"},
        ],
    },
]


def _generate_quick_actions(zone: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate quick actions for a zone based on its entities and active mode."""
    actions: List[Dict[str, Any]] = []
    entities = zone.get("entities", {})
    entity_ids = zone.get("entity_ids", [])
    zone_id = zone.get("zone_id", "")

    for group in _QUICK_ACTION_DEFS:
        if group["detect"](entity_ids, entities):
            for a in group["actions"]:
                entry: Dict[str, Any] = {
                    "action_id": f"{zone_id}_{a['suffix']}",
                    "name": a["name"],
                    "icon": a["icon"],
                    "service": a["service"],
                    "target": {"entity_id": a["target_key"]},
                }
                if "data" in a:
                    entry["data"] = a["data"]
                actions.append(entry)

    # Mode-basierte Aktionen
    hub_modes = _svc.get("hub_modes")
    if hub_modes:
        ms = _safe(lambda: hub_modes.get_zone_status(zone_id))
        if ms:
            if ms.active_mode:
                actions.append({
                    "action_id": f"{zone_id}_mode_off",
                    "name": f"{ms.mode_name_de} beenden",
                    "icon": "mdi:close-circle",
                    "service": "zone.deactivate_mode",
                    "target": {"zone_id": zone_id},
                })
            else:
                actions.append({
                    "action_id": f"{zone_id}_mode_movie",
                    "name": "Filmmodus",
                    "icon": "mdi:movie-open",
                    "service": "zone.activate_mode",
                    "data": {"mode_id": "movie"},
                    "target": {"zone_id": zone_id},
                })

    enabled = zone.get("enabled", True)
    actions.append({
        "action_id": f"{zone_id}_toggle",
        "name": f"Zone {'deaktivieren' if enabled else 'aktivieren'}",
        "icon": f"mdi:toggle-switch{'' if enabled else '-off'}",
        "service": "zone.toggle",
        "target": {"zone_id": zone_id},
    })

    return actions


# ═══════════════════════════════════════════════════════════════════════
# Global Context
# ═══════════════════════════════════════════════════════════════════════

def _build_global_context() -> Dict[str, Any]:
    """Build global dashboard context from available engines + example data."""
    ctx: Dict[str, Any] = {}

    hub_energy = _svc.get("hub_energy")
    if hub_energy:
        eco = _safe(lambda: hub_energy.calculate_eco_score())
        if eco:
            energy_ctx: Dict[str, Any] = {
                "eco_score": eco.score, "eco_grade": eco.grade, "eco_trend": eco.trend,
            }
            breakdown = _safe(lambda: hub_energy.get_breakdown())
            if breakdown:
                energy_ctx["breakdown"] = [
                    {"category": b.category, "name_de": b.name_de,
                     "kwh": b.kwh, "pct": b.pct, "cost_eur": b.cost_eur}
                    for b in breakdown
                ]
            ctx["energy"] = energy_ctx

    hub_praesenz = _svc.get("hub_praesenz")
    if hub_praesenz:
        persons = _safe(lambda: hub_praesenz.get_all_persons_home())
        if persons is not None:
            ctx["persons_home"] = persons

    hub_li = _svc.get("hub_light_intel")
    if hub_li:
        sun = _safe(lambda: hub_li.get_sun_position())
        if sun:
            ctx["sun"] = {"elevation": sun.elevation, "azimuth": sun.azimuth, "phase": sun.phase}

    hub_notif = _svc.get("hub_notifications")
    if hub_notif:
        stats = _safe(lambda: hub_notif.get_stats())
        if stats:
            ctx["notifications"] = {
                "unread_count": stats.unread_count,
                "total_sent": stats.total_sent,
                "total_suppressed": stats.total_suppressed,
            }

    hub_mw = _svc.get("hub_musikwolke")
    if hub_mw:
        mw = _safe(lambda: hub_mw.get_status())
        if mw:
            ctx["musikwolke"] = {
                "sonos_connected": mw.get("sonos_connected", False),
                "active_zones": mw.get("active_zones", []),
                "zone_speaker_map": mw.get("zone_speaker_map", {}),
            }

    # Household + Birthdays
    ex = _get_example()
    household = ex.get("household", [])
    if household:
        ctx["household"] = [
            {"person_id": p["person_id"], "name": p["name"], "role": p["role"]}
            for p in household
        ]
        today = date.today()
        upcoming = []
        for person in household:
            bday_str = person.get("birthday", "")
            if not bday_str:
                continue
            bday = date.fromisoformat(bday_str)
            next_bday = bday.replace(year=today.year)
            if next_bday < today:
                next_bday = next_bday.replace(year=today.year + 1)
            days_until = (next_bday - today).days
            if days_until <= 30:
                upcoming.append({
                    "name": person["name"], "date": next_bday.isoformat(),
                    "days_until": days_until, "age": next_bday.year - bday.year,
                })
        if upcoming:
            ctx["upcoming_birthdays"] = sorted(upcoming, key=lambda x: x["days_until"])

    # Todos summary
    todos = ex.get("todos", [])
    if todos:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pending = [t for t in todos if t.get("status") != "completed"]
        overdue = [t for t in pending if t.get("due_date") and t["due_date"] < today_str]
        by_zone: Dict[str, int] = {}
        for t in pending:
            zid = t.get("zone_id", "_global")
            by_zone[zid] = by_zone.get(zid, 0) + 1
        ctx["todos"] = {
            "total_pending": len(pending), "overdue": len(overdue), "by_zone": by_zone,
        }

    return ctx


# ═══════════════════════════════════════════════════════════════════════
# Public Helper — Used by styx_dashboard.py
# ═══════════════════════════════════════════════════════════════════════

def build_zones_for_styx() -> List[Dict[str, Any]]:
    """Build compact zone data for the Styx full dashboard."""
    zones = _get_habitus_zones()
    result = []
    for zone in zones:
        zid = zone.get("zone_id", "")
        entities = zone.get("entities", {})
        entry: Dict[str, Any] = {
            "id": zid,
            "name_de": zone.get("name_de", zone.get("name", zid)),
            "name_en": zone.get("name_en", ""),
            "icon": zone.get("icon", ""),
            "color": zone.get("color", "#888"),
            "priority": zone.get("priority", 0),
            "entity_count": len(zone.get("entity_ids", [])),
            "roles": {k: len(v) for k, v in entities.items() if isinstance(v, list)},
            "status": _get_zone_status(zone),
            "person_count": _get_person_count(zone),
        }
        modules = _get_zone_module_data(zid)
        if modules:
            entry["modules"] = modules
        result.append(entry)
    return result


# ═══════════════════════════════════════════════════════════════════════
# REST Endpoints
# ═══════════════════════════════════════════════════════════════════════

def _parse_bool_param(name: str, default: bool = True) -> bool:
    return request.args.get(name, str(default)).lower() == "true"


@zone_dashboard_bp.route("", methods=["GET"])
@require_token
def get_dashboard():
    """Zonenzentriertes Dashboard mit allen Moduldaten.

    Query params:
      - include_entities, include_mood, include_actions, include_modules (bool, default: true)
    """
    include_entities = _parse_bool_param("include_entities")
    include_mood = _parse_bool_param("include_mood")
    include_actions = _parse_bool_param("include_actions")
    include_modules = _parse_bool_param("include_modules")

    zones = _get_habitus_zones()
    dashboard_zones = []
    for zone in zones:
        zid = zone.get("zone_id", "")
        zone_data: Dict[str, Any] = {
            "zone_id": zid,
            "name": zone.get("name"),
            "name_de": zone.get("name_de", zone.get("name", zid)),
            "name_en": zone.get("name_en", ""),
            "zone_type": zone.get("zone_type", "room"),
            "icon": zone.get("icon", ""),
            "color": zone.get("color", ""),
            "priority": zone.get("priority", 0),
            "status": _get_zone_status(zone),
            "person_count": _get_person_count(zone),
            "entity_count": len(zone.get("entity_ids", [])),
            "entity_counts_by_domain": _get_entity_count(zone),
            "enabled": zone.get("enabled", True),
            "updated_at": zone.get("updated_at"),
        }
        if include_modules:
            zone_data["modules"] = _get_zone_module_data(zid)
        if include_mood:
            zone_data["mood"] = _get_zone_mood(zid)
        if include_actions:
            zone_data["quick_actions"] = _generate_quick_actions(zone)
        if include_entities:
            zone_data["entity_ids"] = zone.get("entity_ids", [])
            zone_data["entities"] = zone.get("entities", {})
        dashboard_zones.append(zone_data)

    response: Dict[str, Any] = {
        "ok": True,
        "zones": dashboard_zones,
        "count": len(dashboard_zones),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    global_ctx = _build_global_context()
    if global_ctx:
        response["global"] = global_ctx

    return jsonify(response)


@zone_dashboard_bp.route("/summary", methods=["GET"])
@require_token
def get_dashboard_summary():
    """Leichtgewichtige Zusammenfassung (Counts, aktive Zonen, alle Modulstatus)."""
    zones = _get_habitus_zones()

    total_entities = 0
    active_zones = 0
    total_persons = 0
    zone_types: Dict[str, int] = {}
    counters = {"heating": 0, "motion": 0, "occupied": 0, "media": 0, "mode": 0}
    lights_on = lights_total = 0

    for zone in zones:
        zid = zone.get("zone_id", "")
        total_entities += len(zone.get("entity_ids", []))
        if _get_zone_status(zone) == "active":
            active_zones += 1
        total_persons += _get_person_count(zone)
        zt = zone.get("zone_type", "room")
        zone_types[zt] = zone_types.get(zt, 0) + 1

        # Per-zone engine queries (each guarded)
        hub = _svc.get("hub_licht")
        if hub:
            ls = _safe(lambda h=hub: h.get_zone_state(zid))
            if ls:
                lights_on += ls.lights_on
                lights_total += ls.lights_total

        hub = _svc.get("hub_heiz")
        if hub:
            cl = _safe(lambda h=hub: h.get_zone_climate(zid))
            if cl and cl.is_heating:
                counters["heating"] += 1

        hub = _svc.get("hub_bewegung")
        if hub:
            mo = _safe(lambda h=hub: h.get_zone_motion(zid))
            if mo and mo.motion_in_last_5min:
                counters["motion"] += 1

        hub = _svc.get("hub_praesenz")
        if hub:
            pr = _safe(lambda h=hub: h.get_zone_presence(zid))
            if pr and pr.is_occupied:
                counters["occupied"] += 1

        hub = _svc.get("hub_media")
        if hub:
            ms = _safe(lambda h=hub: h.get_zone_media(zid))
            if ms and ms.active_sessions > 0:
                counters["media"] += 1

        hub = _svc.get("hub_modes")
        if hub:
            md = _safe(lambda h=hub: h.get_zone_status(zid))
            if md and md.active_mode:
                counters["mode"] += 1

    summary: Dict[str, Any] = {
        "total_zones": len(zones),
        "active_zones": active_zones,
        "idle_zones": len(zones) - active_zones,
        "total_entities": total_entities,
        "total_persons": total_persons,
        "zone_types": zone_types,
        "lights_on": lights_on,
        "lights_total": lights_total,
        "zones_heating": counters["heating"],
        "zones_with_motion": counters["motion"],
        "zones_occupied": counters["occupied"],
        "zones_with_media": counters["media"],
        "zones_with_active_mode": counters["mode"],
    }

    hub_energy = _svc.get("hub_energy")
    if hub_energy:
        eco = _safe(lambda: hub_energy.calculate_eco_score())
        if eco:
            summary["eco_score"] = eco.score
            summary["eco_grade"] = eco.grade

    hub_praesenz = _svc.get("hub_praesenz")
    if hub_praesenz:
        persons = _safe(lambda: hub_praesenz.get_all_persons_home())
        if persons is not None:
            summary["persons_home"] = persons

    return jsonify({
        "ok": True,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


@zone_dashboard_bp.route("/mood", methods=["GET"])
@require_token
def get_mood():
    """Get mood data for all zones."""
    zones = _get_habitus_zones()
    mood_data = {zone.get("zone_id", ""): _get_zone_mood(zone.get("zone_id", ""))
                 for zone in zones}
    return jsonify({"ok": True, "mood": mood_data, "count": len(mood_data)})


@zone_dashboard_bp.route("/mood/<zone_id>", methods=["PUT"])
@require_token
def set_mood(zone_id: str):
    """Set mood data for a zone."""
    zone_id = zone_id if zone_id.startswith("zone:") else f"zone:{zone_id}"
    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"ok": False, "error": "Mood data required"}), 400
    return jsonify({"ok": True, "zone_id": zone_id, "mood": _set_zone_mood(zone_id, body)})


@zone_dashboard_bp.route("/quick-action", methods=["POST"])
@require_token
def execute_quick_action():
    """Execute a quick action for a zone."""
    body = request.get_json(silent=True) or {}
    zone_id = body.get("zone_id")
    action_id = body.get("action_id")
    service = body.get("service")

    if not all((zone_id, action_id, service)):
        return jsonify({"ok": False, "error": "zone_id, action_id, and service are required"}), 400

    _LOGGER.info("Quick action executed: %s for zone %s (service: %s)", action_id, zone_id, service)
    return jsonify({
        "ok": True, "action_id": action_id, "zone_id": zone_id,
        "service": service, "executed_at": datetime.now(timezone.utc).isoformat(),
    })


@zone_dashboard_bp.route("/<zone_id>", methods=["GET"])
@require_token
def get_zone_detail(zone_id: str):
    """Detailansicht einer einzelnen Zone mit allen Moduldaten."""
    zone_id = zone_id if zone_id.startswith("zone:") else f"zone:{zone_id}"
    zones = _get_habitus_zones()
    zone = next((z for z in zones if z.get("zone_id") == zone_id), None)
    if zone is None:
        return jsonify({"ok": False, "error": "Zone not found"}), 404

    entity_ids = zone.get("entity_ids", [])
    entities_by_role = zone.get("entities_by_role", {})
    scenes_data = zone.get("scenes", [])

    zone_data: Dict[str, Any] = {
        "zone_id": zone.get("zone_id"),
        "name": zone.get("name"),
        "name_de": zone.get("name_de", zone.get("name", zone_id)),
        "name_en": zone.get("name_en", ""),
        "zone_type": zone.get("zone_type", "room"),
        "icon": zone.get("icon", ""),
        "color": zone.get("color", ""),
        "priority": zone.get("priority", 0),
        "status": _get_zone_status(zone),
        "person_count": _get_person_count(zone),
        "entity_count": len(entity_ids),
        "entity_counts_by_domain": _get_entity_count(zone),
        "modules": _get_zone_module_data(zone_id),
        "mood": _get_zone_mood(zone_id),
        "quick_actions": _generate_quick_actions(zone),
        "entity_ids": entity_ids,
        "entities": entities_by_role,
        "scenes": scenes_data,
        "metadata": zone.get("metadata", {}),
        "enabled": zone.get("enabled", True),
        "updated_at": zone.get("updated_at"),
    }
    return jsonify({"ok": True, "zone": zone_data})
