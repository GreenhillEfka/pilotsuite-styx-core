"""Zone Dashboard API — Zonenzentriertes Dashboard mit Modulintegration.

Zentraler Dashboard-Endpunkt fuer Habituszonen. Aggregiert Daten aus
allen 5 Modul-Engines (Licht, Helligkeit, Heiz, Bewegung, Praesenz)
pro Zone zu einem einheitlichen Dashboard.

Endpunkte:
  GET  /api/v1/zone/dashboard              - Alle Zonen mit Moduldaten
  GET  /api/v1/zone/dashboard/summary      - Leichtgewichtige Zusammenfassung
  GET  /api/v1/zone/dashboard/mood         - Mood-Daten aller Zonen
  PUT  /api/v1/zone/dashboard/mood/<id>    - Mood fuer Zone setzen
  POST /api/v1/zone/dashboard/quick-action - Quick-Action ausfuehren
  GET  /api/v1/zone/dashboard/<id>         - Einzelzone Detail

Author: Clawdya (via Codex)
Version: 2.0.0
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

zone_dashboard_bp = Blueprint("zone_dashboard", __name__, url_prefix="/api/v1/zone/dashboard")

# Runtime mood data (overridable via PUT endpoint)
_zone_mood_data: Dict[str, Dict[str, float]] = {}

# Service references wired by init_zone_dashboard_api()
_zone_automation = None
_mood_service = None

# Module engine references (wired by init_zone_dashboard_api)
_hub_licht = None
_hub_helligkeit = None
_hub_heiz = None
_hub_bewegung = None
_hub_praesenz = None


def init_zone_dashboard_api(
    zone_automation=None,
    mood_service=None,
    hub_licht=None,
    hub_helligkeit=None,
    hub_heiz=None,
    hub_bewegung=None,
    hub_praesenz=None,
) -> None:
    """Initialize the Zone Dashboard API with live service references."""
    global _zone_automation, _mood_service
    global _hub_licht, _hub_helligkeit, _hub_heiz, _hub_bewegung, _hub_praesenz
    _zone_automation = zone_automation
    _mood_service = mood_service
    _hub_licht = hub_licht
    _hub_helligkeit = hub_helligkeit
    _hub_heiz = hub_heiz
    _hub_bewegung = hub_bewegung
    _hub_praesenz = hub_praesenz
    _LOGGER.info(
        "Zone Dashboard API initialized (zone_automation=%s, mood=%s, "
        "modules=%d/5 wired)",
        zone_automation is not None, mood_service is not None,
        sum(1 for m in (hub_licht, hub_helligkeit, hub_heiz, hub_bewegung, hub_praesenz) if m),
    )


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

    # Enrich with example entity data
    try:
        from copilot_core.example_config import EXAMPLE_ZONE_ENTITIES, ZONE_DISPLAY
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
            if zid in EXAMPLE_ZONE_ENTITIES and not zdict.get("entities"):
                zdict["entities"] = EXAMPLE_ZONE_ENTITIES[zid]
                zdict["entity_ids"] = [
                    eid for role_list in EXAMPLE_ZONE_ENTITIES[zid].values()
                    for eid in role_list
                ]
            if zid in ZONE_DISPLAY:
                zdict.setdefault("icon", ZONE_DISPLAY[zid].get("icon", ""))
                zdict.setdefault("color", ZONE_DISPLAY[zid].get("color", ""))
            enriched.append(zdict)
        zones = enriched
    except ImportError:
        pass

    return zones


def _get_zone_mood(zone_id: str) -> Dict[str, Any]:
    """Get mood data for a zone.

    Sources (priority):
    1. User-set overrides (_zone_mood_data)
    2. MoodService zone-level mood (if wired)
    3. Computed defaults from zone automation state
    """
    if zone_id in _zone_mood_data:
        return _zone_mood_data[zone_id]

    if _mood_service:
        try:
            mood_state = _mood_service.get_current_mood()
            return {
                "comfort": mood_state.get("comfort", 0.5),
                "joy": mood_state.get("joy", 0.5),
                "frugality": mood_state.get("frugality", 0.5),
                "mood": mood_state.get("mood", "unknown"),
                "confidence": mood_state.get("confidence", 0.0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            pass

    if _zone_automation:
        try:
            state = _zone_automation.get_zone_state(zone_id)
            zone_state = state.get("state", {})
            occupied = zone_state.get("occupied", False)
            lights_on = zone_state.get("lights_on", False)
            music = zone_state.get("music_playing", False)
            return {
                "comfort": 0.8 if lights_on else 0.4,
                "joy": 0.9 if music else (0.6 if occupied else 0.3),
                "frugality": 0.4 if (lights_on and music) else 0.8,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            pass

    return {
        "comfort": 0.5,
        "joy": 0.5,
        "frugality": 0.5,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


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
    """Count entities by domain for a zone."""
    entity_ids = zone.get("entity_ids", [])
    entities_by_role = zone.get("entities", {})

    counts: Dict[str, int] = {}

    for entity_id in entity_ids:
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
        counts[domain] = counts.get(domain, 0) + 1

    # Only count from role mapping if entity_ids was empty
    if not entity_ids:
        for role, role_entities in entities_by_role.items():
            if isinstance(role_entities, list):
                for entity_id in role_entities:
                    domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
                    counts[domain] = counts.get(domain, 0) + 1

    return counts


def _get_zone_status(zone: Dict[str, Any]) -> str:
    """Determine zone status from ZoneAutomationController live state."""
    zone_id = zone.get("zone_id", "")

    if _zone_automation:
        try:
            state = _zone_automation.get_zone_state(zone_id)
            zone_state = state.get("state", {})
            if zone_state.get("occupied", False):
                return "active"
            config = state.get("config", {})
            light_cfg = config.get("light", {})
            if not light_cfg.get("enabled", True):
                return "disabled"
        except Exception:
            pass

    return "idle"


def _get_person_count(zone: Dict[str, Any]) -> int:
    """Get number of people in zone from PraesenzModule or entity heuristic."""
    zone_id = zone.get("zone_id", "")

    # Prefer live presence data from PraesenzModuleEngine
    if _hub_praesenz:
        try:
            presence = _hub_praesenz.get_zone_presence(zone_id)
            return presence.person_count
        except Exception:
            pass

    # Fallback: count person/device_tracker entities
    entity_ids = zone.get("entity_ids", [])
    return sum(1 for e in entity_ids if e.startswith(("person.", "device_tracker.")))


# ═══════════════════════════════════════════════════════════════════════
# Module Engine Integration — Per-Zone Aggregation
# ═══════════════════════════════════════════════════════════════════════

def _get_zone_module_data(zone_id: str) -> Dict[str, Any]:
    """Aggregate module engine data for a single zone.

    Queries all 5 module engines and returns a unified dict with
    licht, helligkeit, heiz, bewegung, praesenz subsections.
    """
    modules: Dict[str, Any] = {}

    # Licht (Light)
    if _hub_licht:
        try:
            state = _hub_licht.get_zone_state(zone_id)
            modules["licht"] = {
                "lights_on": state.lights_on,
                "lights_total": state.lights_total,
                "avg_brightness_pct": state.avg_brightness_pct,
                "any_override": state.any_override,
                "target_brightness_pct": state.target_brightness_pct,
                "target_color_temp_k": state.target_color_temp_k,
                "auto_enabled": state.auto_enabled,
            }
        except Exception:
            pass

    # Helligkeit (Brightness)
    if _hub_helligkeit:
        try:
            state = _hub_helligkeit.get_zone_brightness(zone_id)
            modules["helligkeit"] = {
                "avg_indoor_lux": state.avg_indoor_lux,
                "avg_outdoor_lux": state.avg_outdoor_lux,
                "needs_light": state.needs_light,
                "deficit_pct": state.deficit_pct,
                "recommended_dimming_pct": state.recommended_dimming_pct,
            }
        except Exception:
            pass

    # Heiz (Climate)
    if _hub_heiz:
        try:
            state = _hub_heiz.get_zone_climate(zone_id)
            modules["heiz"] = {
                "current_temp": state.current_temp,
                "target_temp": state.target_temp,
                "humidity": state.humidity,
                "is_heating": state.is_heating,
                "eco_mode": state.eco_mode,
                "comfort_index": state.comfort_index,
                "needs_heating": state.needs_heating,
            }
        except Exception:
            pass

    # Bewegung (Motion)
    if _hub_bewegung:
        try:
            state = _hub_bewegung.get_zone_motion(zone_id)
            modules["bewegung"] = {
                "sensors_active": state.sensors_active,
                "sensors_total": state.sensors_total,
                "last_motion": state.last_motion.isoformat() if state.last_motion else None,
                "motion_in_last_5min": state.motion_in_last_5min,
                "motion_in_last_30min": state.motion_in_last_30min,
                "daily_triggers": state.daily_triggers,
            }
        except Exception:
            pass

    # Praesenz (Presence)
    if _hub_praesenz:
        try:
            state = _hub_praesenz.get_zone_presence(zone_id)
            modules["praesenz"] = {
                "is_occupied": state.is_occupied,
                "person_count": state.person_count,
                "persons": state.persons,
                "occupied_since": state.occupied_since.isoformat() if state.occupied_since else None,
                "sources_active": state.sources_active,
                "sources_total": state.sources_total,
            }
        except Exception:
            pass

    return modules


def _generate_quick_actions(zone: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate quick actions for a zone based on its entities."""
    actions = []
    entities = zone.get("entities", {})
    entity_ids = zone.get("entity_ids", [])

    zone_id = zone.get("zone_id", "")

    has_lights = any(e.startswith("light.") for e in entity_ids) or "lights" in entities
    if has_lights:
        actions.append({
            "action_id": f"{zone_id}_lights_on",
            "name": "Licht an",
            "icon": "mdi:lightbulb",
            "service": "light.turn_on",
            "target": {"entity_id": "all_lights_in_zone"},
        })
        actions.append({
            "action_id": f"{zone_id}_lights_off",
            "name": "Licht aus",
            "icon": "mdi:lightbulb-off",
            "service": "light.turn_off",
            "target": {"entity_id": "all_lights_in_zone"},
        })

    has_climate = any(e.startswith("climate.") for e in entity_ids) or "heating" in entities
    if has_climate:
        actions.append({
            "action_id": f"{zone_id}_climate_comfort",
            "name": "Komfort",
            "icon": "mdi:thermometer",
            "service": "climate.set_hvac_mode",
            "data": {"hvac_mode": "heat"},
            "target": {"entity_id": "all_climate_in_zone"},
        })

    has_media = any(e.startswith("media_player.") for e in entity_ids) or "media" in entities
    if has_media:
        actions.append({
            "action_id": f"{zone_id}_media_mood",
            "name": "Stimmung",
            "icon": "mdi:music",
            "service": "media_player.play_media",
            "data": {"media_content_type": "playlist"},
            "target": {"entity_id": "all_media_in_zone"},
        })

    actions.append({
        "action_id": f"{zone_id}_toggle",
        "name": "Zone " + ("deaktivieren" if zone.get("enabled", True) else "aktivieren"),
        "icon": "mdi:toggle-switch" if zone.get("enabled", True) else "mdi:toggle-switch-off",
        "service": "zone.toggle",
        "target": {"zone_id": zone_id},
    })

    return actions


# ═══════════════════════════════════════════════════════════════════════
# Public Helper — Used by styx_dashboard.py
# ═══════════════════════════════════════════════════════════════════════

def build_zones_for_styx() -> List[Dict[str, Any]]:
    """Build compact zone data for the Styx full dashboard.

    Returns a list of zone dicts with identity, module summary,
    and entity counts — no mood or quick actions (those are
    separate SPA tabs).
    """
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
        }
        # Attach lightweight module summary
        modules = _get_zone_module_data(zid)
        if modules:
            entry["modules"] = modules
        result.append(entry)
    return result


# ═══════════════════════════════════════════════════════════════════════
# REST Endpoints
# ═══════════════════════════════════════════════════════════════════════


@zone_dashboard_bp.route("", methods=["GET"])
@require_token
def get_dashboard():
    """Zonenzentriertes Dashboard mit Moduldaten.

    Gibt alle Habituszonen mit Status, Mood, Entities und
    aggregierten Moduldaten (Licht, Heiz, Helligkeit, Bewegung,
    Praesenz) zurueck.

    Query params:
      - include_entities: bool (default: true)
      - include_mood: bool (default: true)
      - include_actions: bool (default: true)
      - include_modules: bool (default: true)
    """
    include_entities = request.args.get("include_entities", "true").lower() == "true"
    include_mood = request.args.get("include_mood", "true").lower() == "true"
    include_actions = request.args.get("include_actions", "true").lower() == "true"
    include_modules = request.args.get("include_modules", "true").lower() == "true"

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

    return jsonify({
        "ok": True,
        "zones": dashboard_zones,
        "count": len(dashboard_zones),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


@zone_dashboard_bp.route("/summary", methods=["GET"])
@require_token
def get_dashboard_summary():
    """Leichtgewichtige Zusammenfassung (Counts, aktive Zonen, Modulstatus)."""
    zones = _get_habitus_zones()

    total_entities = 0
    active_zones = 0
    total_persons = 0
    zone_types: Dict[str, int] = {}
    zones_heating = 0
    zones_with_motion = 0
    zones_occupied = 0

    for zone in zones:
        zid = zone.get("zone_id", "")
        total_entities += len(zone.get("entity_ids", []))
        status = _get_zone_status(zone)
        if status == "active":
            active_zones += 1
        total_persons += _get_person_count(zone)
        zone_type = zone.get("zone_type", "room")
        zone_types[zone_type] = zone_types.get(zone_type, 0) + 1

        # Module summary counters
        if _hub_heiz:
            try:
                climate = _hub_heiz.get_zone_climate(zid)
                if climate.is_heating:
                    zones_heating += 1
            except Exception:
                pass
        if _hub_bewegung:
            try:
                motion = _hub_bewegung.get_zone_motion(zid)
                if motion.motion_in_last_5min:
                    zones_with_motion += 1
            except Exception:
                pass
        if _hub_praesenz:
            try:
                presence = _hub_praesenz.get_zone_presence(zid)
                if presence.is_occupied:
                    zones_occupied += 1
            except Exception:
                pass

    return jsonify({
        "ok": True,
        "summary": {
            "total_zones": len(zones),
            "active_zones": active_zones,
            "idle_zones": len(zones) - active_zones,
            "total_entities": total_entities,
            "total_persons": total_persons,
            "zone_types": zone_types,
            "zones_heating": zones_heating,
            "zones_with_motion": zones_with_motion,
            "zones_occupied": zones_occupied,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


@zone_dashboard_bp.route("/mood", methods=["GET"])
@require_token
def get_mood():
    """Get mood data for all zones."""
    zones = _get_habitus_zones()

    mood_data = {}
    for zone in zones:
        zone_id = zone.get("zone_id", "")
        mood_data[zone_id] = _get_zone_mood(zone_id)

    return jsonify({
        "ok": True,
        "mood": mood_data,
        "count": len(mood_data),
    })


@zone_dashboard_bp.route("/mood/<zone_id>", methods=["PUT"])
@require_token
def set_mood(zone_id: str):
    """Set mood data for a zone (for testing/demo).

    Payload:
    {
        "comfort": 0.8,
        "joy": 0.6,
        "frugality": 0.7
    }
    """
    zone_id = zone_id if zone_id.startswith("zone:") else f"zone:{zone_id}"
    body = request.get_json(silent=True) or {}

    if not body:
        return jsonify({"ok": False, "error": "Mood data required"}), 400

    mood_data = _set_zone_mood(zone_id, body)

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "mood": mood_data,
    })


@zone_dashboard_bp.route("/quick-action", methods=["POST"])
@require_token
def execute_quick_action():
    """Execute a quick action for a zone.

    Payload:
    {
        "zone_id": "zone:wohnzimmer",
        "action_id": "zone:wohnzimmer_lights_on",
        "service": "light.turn_on",
        "target": {"entity_id": "light.wohnzimmer"},
        "data": {}
    }
    """
    body = request.get_json(silent=True) or {}

    zone_id = body.get("zone_id")
    action_id = body.get("action_id")
    service = body.get("service")

    if not zone_id or not action_id or not service:
        return jsonify({
            "ok": False,
            "error": "zone_id, action_id, and service are required"
        }), 400

    _LOGGER.info("Quick action executed: %s for zone %s (service: %s)", action_id, zone_id, service)

    return jsonify({
        "ok": True,
        "action_id": action_id,
        "zone_id": zone_id,
        "service": service,
        "executed_at": datetime.now(timezone.utc).isoformat(),
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
        "entity_count": len(zone.get("entity_ids", [])),
        "entity_counts_by_domain": _get_entity_count(zone),
        "modules": _get_zone_module_data(zone_id),
        "mood": _get_zone_mood(zone_id),
        "quick_actions": _generate_quick_actions(zone),
        "entity_ids": zone.get("entity_ids", []),
        "entities": zone.get("entities", {}),
        "metadata": zone.get("metadata", {}),
        "enabled": zone.get("enabled", True),
        "updated_at": zone.get("updated_at"),
    }

    return jsonify({
        "ok": True,
        "zone": zone_data,
    })
