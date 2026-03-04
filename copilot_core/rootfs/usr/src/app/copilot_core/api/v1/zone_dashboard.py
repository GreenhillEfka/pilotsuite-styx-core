"""Zone Dashboard API - Real-time Zone Overview with Mood & Quick Actions.

Endpunkte:
  GET  /api/v1/zone/dashboard         - Dashboard-Daten (alle Zonen mit Status, Mood, Entities)
  GET  /api/v1/zone/dashboard/summary - Zusammenfassung (Counts, aktive Zonen)
  POST /api/v1/zone/dashboard/quick-action - Quick-Action ausführen (Zone ein/aus, Mood)
  GET  /api/v1/zone/dashboard/mood    - Mood-Daten aller Zonen
  PUT  /api/v1/zone/dashboard/mood/<zone_id> - Mood für Zone setzen

Integration:
  - Verwendet habitus_zones.py als Datenquelle
  - Aggregiert Entity-Status aus Home Assistant
  - Berechnet Mood-Scores (comfort, joy, frugality)
  - Bietet Quick-Actions für schnelle Steuerung

Author: Clawdya (via Codex)
Version: 1.0.0
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

zone_dashboard_bp = Blueprint("zone_dashboard", __name__, url_prefix="/api/v1/zone/dashboard")

# Mock-Daten für Demo (später durch HA-Integration ersetzen)
_MOCK_MOOD_DATA: Dict[str, Dict[str, float]] = {}
_MOCK_ENTITY_STATES: Dict[str, Dict[str, Any]] = {}


def init_zone_dashboard_api() -> None:
    """Initialize the Zone Dashboard API."""
    _LOGGER.info("Zone Dashboard API initialized")


def _get_habitus_zones() -> List[Dict[str, Any]]:
    """Get zones from habitus_zones module, enriched with example entities."""
    zones = []
    try:
        from copilot_core.api.v1.habitus_zones import get_all_zones
        zones = get_all_zones()
    except ImportError:
        _LOGGER.warning("habitus_zones module not available")

    # Enrich with example entity data
    try:
        from copilot_core.example_config import EXAMPLE_ZONE_ENTITIES, ZONE_DISPLAY
        enriched = []
        for zone in zones:
            # Handle both dict and dataclass objects
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
    """Get mood data for a zone (comfort, joy, frugality).
    
    In production, this would query:
    - Temperature/CO2 sensors → comfort
    - Media activity, lighting scenes → joy
    - Energy consumption → frugality
    """
    # Check mock data first
    if zone_id in _MOCK_MOOD_DATA:
        return _MOCK_MOOD_DATA[zone_id]
    
    # Default mood values
    return {
        "comfort": 0.7,
        "joy": 0.6,
        "frugality": 0.8,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _set_zone_mood(zone_id: str, mood_data: Dict[str, float]) -> Dict[str, Any]:
    """Set mood data for a zone (for testing/demo)."""
    _MOCK_MOOD_DATA[zone_id] = {
        "comfort": float(mood_data.get("comfort", 0.5)),
        "joy": float(mood_data.get("joy", 0.5)),
        "frugality": float(mood_data.get("frugality", 0.5)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _MOCK_MOOD_DATA[zone_id]


def _get_entity_count(zone: Dict[str, Any]) -> Dict[str, int]:
    """Count entities by domain for a zone."""
    entity_ids = zone.get("entity_ids", [])
    entities_by_role = zone.get("entities", {})
    
    counts: Dict[str, int] = {}
    
    # Count from entity_ids
    for entity_id in entity_ids:
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
        counts[domain] = counts.get(domain, 0) + 1
    
    # Count from entities by role
    for role, role_entities in entities_by_role.items():
        if isinstance(role_entities, list):
            for entity_id in role_entities:
                domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
                counts[domain] = counts.get(domain, 0) + 1
    
    return counts


def _get_zone_status(zone: Dict[str, Any]) -> str:
    """Determine zone status (active, idle, disabled).
    
    In production, this would check:
    - Motion sensors → active
    - Time of day + automation state
    - Manual override
    """
    zone_id = zone.get("zone_id", "")
    
    # Check mock state
    if zone_id in _MOCK_ENTITY_STATES:
        return _MOCK_ENTITY_STATES[zone_id].get("status", "idle")
    
    # Default: check if zone has motion entities
    entities = zone.get("entities", {})
    motion_entities = entities.get("motion", [])
    
    # For demo: random active state
    if motion_entities and len(motion_entities) > 0:
        return "active"
    
    return "idle"


def _get_person_count(zone: Dict[str, Any]) -> int:
    """Get number of people in zone (from device_tracker/person entities)."""
    entity_ids = zone.get("entity_ids", [])
    entities = zone.get("entities", {})
    
    person_count = 0
    
    # Check entity_ids
    for entity_id in entity_ids:
        if entity_id.startswith(("person.", "device_tracker.")):
            person_count += 1
    
    # Check entities by role
    for role_entities in entities.values():
        if isinstance(role_entities, list):
            for entity_id in role_entities:
                if entity_id.startswith(("person.", "device_tracker.")):
                    person_count += 1
    
    return person_count


def _generate_quick_actions(zone: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate quick actions for a zone based on its entities."""
    actions = []
    entities = zone.get("entities", {})
    entity_ids = zone.get("entity_ids", [])
    
    zone_id = zone.get("zone_id", "")
    zone_name = zone.get("name", zone_id)
    
    # Check for lights
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
    
    # Check for climate/heating
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
    
    # Check for media
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
    
    # Zone enable/disable
    actions.append({
        "action_id": f"{zone_id}_toggle",
        "name": "Zone " + ("deaktivieren" if zone.get("enabled", True) else "aktivieren"),
        "icon": "mdi:toggle-switch" if zone.get("enabled", True) else "mdi:toggle-switch-off",
        "service": "zone.toggle",
        "target": {"zone_id": zone_id},
    })
    
    return actions


# --- REST Endpoints ---


@zone_dashboard_bp.route("", methods=["GET"])
@require_token
def get_dashboard():
    """Get complete dashboard data with all zones, status, mood, and quick actions.
    
    Query params:
      - include_entities: bool (default: true) - Include entity details
      - include_mood: bool (default: true) - Include mood scores
      - include_actions: bool (default: true) - Include quick actions
    """
    include_entities = request.args.get("include_entities", "true").lower() == "true"
    include_mood = request.args.get("include_mood", "true").lower() == "true"
    include_actions = request.args.get("include_actions", "true").lower() == "true"
    
    zones = _get_habitus_zones()
    
    dashboard_zones = []
    for zone in zones:
        zone_data = {
            "zone_id": zone.get("zone_id"),
            "name": zone.get("name"),
            "zone_type": zone.get("zone_type", "room"),
            "status": _get_zone_status(zone),
            "person_count": _get_person_count(zone),
            "entity_count": len(zone.get("entity_ids", [])),
            "entity_counts_by_domain": _get_entity_count(zone),
            "enabled": zone.get("enabled", True),
            "updated_at": zone.get("updated_at"),
        }
        
        if include_mood:
            zone_data["mood"] = _get_zone_mood(zone.get("zone_id", ""))
        
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
    """Get dashboard summary (lightweight overview without details)."""
    zones = _get_habitus_zones()
    
    total_entities = 0
    active_zones = 0
    total_persons = 0
    zone_types: Dict[str, int] = {}
    
    for zone in zones:
        total_entities += len(zone.get("entity_ids", []))
        if _get_zone_status(zone) == "active":
            active_zones += 1
        total_persons += _get_person_count(zone)
        
        zone_type = zone.get("zone_type", "room")
        zone_types[zone_type] = zone_types.get(zone_type, 0) + 1
    
    return jsonify({
        "ok": True,
        "summary": {
            "total_zones": len(zones),
            "active_zones": active_zones,
            "idle_zones": len(zones) - active_zones,
            "total_entities": total_entities,
            "total_persons": total_persons,
            "zone_types": zone_types,
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
        "data": {}  # optional
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
    
    # In production, this would call Home Assistant service
    # For now, return success mock
    _LOGGER.info("Quick action executed: %s for zone %s", action_id, zone_id)
    
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
    """Get detailed data for a single zone including scenes and aggregates."""
    zones = _get_habitus_zones()

    # Try matching with and without zone: prefix
    bare_id = zone_id.removeprefix("zone:")
    prefixed_id = f"zone:{bare_id}"
    zone = next(
        (z for z in zones if z.get("zone_id") in (bare_id, prefixed_id, zone_id)),
        None,
    )

    if zone is None:
        return jsonify({"ok": False, "error": "Zone not found"}), 404

    zid = zone.get("zone_id", bare_id)
    entities_by_role = zone.get("entities", {})
    entity_ids = zone.get("entity_ids", [])

    # Build domain aggregates
    domain_agg: Dict[str, List[str]] = {}
    for eid in entity_ids:
        domain = eid.split(".")[0] if "." in eid else "other"
        domain_agg.setdefault(domain, []).append(eid)
    for role_entities in entities_by_role.values():
        if isinstance(role_entities, list):
            for eid in role_entities:
                domain = eid.split(".")[0] if "." in eid else "other"
                if eid not in domain_agg.get(domain, []):
                    domain_agg.setdefault(domain, []).append(eid)

    # Fetch scenes for this zone
    scenes_data = []
    try:
        from copilot_core.api.v1.scenes import _scene_cache
        scenes_data = [
            s for s in _scene_cache.values()
            if s.get("zone_id") in (zid, prefixed_id, bare_id)
        ]
    except ImportError:
        pass

    zone_data = {
        "zone_id": zid,
        "name": zone.get("name"),
        "zone_type": zone.get("zone_type", "room"),
        "status": _get_zone_status(zone),
        "person_count": _get_person_count(zone),
        "entity_count": len(entity_ids),
        "entity_counts_by_domain": _get_entity_count(zone),
        "domain_entities": domain_agg,
        "mood": _get_zone_mood(zid),
        "quick_actions": _generate_quick_actions(zone),
        "entity_ids": entity_ids,
        "entities": entities_by_role,
        "scenes": scenes_data,
        "metadata": zone.get("metadata", {}),
        "enabled": zone.get("enabled", True),
        "updated_at": zone.get("updated_at"),
    }

    return jsonify({
        "ok": True,
        "zone": zone_data,
    })
