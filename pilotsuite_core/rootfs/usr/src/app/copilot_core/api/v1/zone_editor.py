"""Zone Editor API - CRUD operations for PilotSuite Dashboard zones.

Endpunkte:
  GET    /api/v1/zone-editor/zones              - Alle Zonen auflisten
  GET    /api/v1/zone-editor/zones/<zone_id>    - Zone Details
  GET    /api/v1/zone-editor/zones/<zone_id>/state - Zone State
  GET    /api/v1/zone-editor/rooms              - Alle Rooms auflisten
  GET    /api/v1/zone-editor/rooms/<room_id>    - Room Details
  GET    /api/v1/zone-editor/overview           - Zone Übersicht
  GET    /api/v1/zone-editor/templates          - Verfügbare Templates
  POST   /api/v1/zone-editor/zones              - Neue Zone erstellen
  PUT    /api/v1/zone-editor/zones/<zone_id>    - Zone aktualisieren
  DELETE /api/v1/zone-editor/zones/<zone_id>    - Zone löschen
  POST   /api/v1/zone-editor/zones/<zone_id>/rooms - Room zu Zone hinzufügen
  DELETE /api/v1/zone-editor/zones/<zone_id>/rooms/<room_id> - Room aus Zone entfernen
  POST   /api/v1/zone/editor/create             - Neue Zone erstellen (legacy)
  GET    /api/v1/zone/editor/list               - Alle Zonen auflisten (legacy)
  GET    /api/v1/zone/editor/<zone_id>          - Zone Details (legacy)
  PUT    /api/v1/zone/editor/<zone_id>          - Zone aktualisieren (legacy)
  DELETE /api/v1/zone/editor/<zone_id>          - Zone löschen (legacy)
  POST   /api/v1/zone/editor/<zone_id>/rooms    - Room zu Zone hinzufügen (legacy)
  DELETE /api/v1/zone/editor/<zone_id>/rooms/<room_id> - Room aus Zone entfernen (legacy)

Author: Clawdya
Version: 2.0.0
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.hub.habitus_zones import HabitusZoneEngine
from copilot_core.homeassistant.habitus_zones import ZoneType
from copilot_core.homeassistant.zone_matcher import map_homeassistant_topology

_LOGGER = logging.getLogger(__name__)

# New API blueprint at /api/v1/zone-editor
zone_editor_bp = Blueprint("zone_editor", __name__, url_prefix="/api/v1/zone-editor")

# Legacy API blueprint at /api/v1/zone/editor (for backward compatibility)
zone_editor_legacy_bp = Blueprint("zone_editor_legacy", __name__, url_prefix="/api/v1/zone/editor")

# Global zone engine instance
_zone_engine: Optional[HabitusZoneEngine] = None


def init_zone_editor_api(engine: Optional[HabitusZoneEngine] = None) -> None:
    """Initialize the Zone Editor API.
    
    Args:
        engine: Optional HabitusZoneEngine instance to use (for testing).
                If not provided, a new engine is created.
    """
    global _zone_engine
    _zone_engine = engine if engine is not None else HabitusZoneEngine()
    _LOGGER.info("Zone Editor API initialized with HabitusZoneEngine")


def get_zone_engine() -> HabitusZoneEngine:
    """Get the zone engine instance."""
    global _zone_engine
    if _zone_engine is None:
        raise RuntimeError("Zone engine not initialized")
    return _zone_engine


def set_zone_engine(engine: HabitusZoneEngine) -> None:
    """Set the zone engine instance (for testing)."""
    global _zone_engine
    _zone_engine = engine


def reset_zone_engine() -> None:
    """Reset the zone engine instance (for testing)."""
    global _zone_engine
    _zone_engine = None


def _parse_json_body() -> dict[str, Any] | None:
    """Parse JSON request body and normalize to dict."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _normalize_enabled_modules(raw_modules: Any) -> set[str] | None:
    """Normalize modules list payload into a stable, stripped set."""
    if raw_modules is None:
        return set()
    if not isinstance(raw_modules, list):
        return None

    return {
        str(module_id).strip()
        for module_id in raw_modules
        if str(module_id).strip()
    }


def _is_valid_zone_type(zone_type: str) -> bool:
    """Validate zone type against the canonical enum values."""
    normalized = (zone_type or "").strip().lower()
    if not normalized:
        return False
    return normalized in {value.value for value in ZoneType}


def _zone_engine_unavailable_response():
    """Return a consistent 503 response when the zone engine is unavailable."""
    return jsonify({"ok": False, "error": "Zone engine not initialized"}), 503


def _get_zone_engine_or_unavailable():
    """Return the zone engine instance or a consistent 503 response tuple."""
    try:
        return get_zone_engine()
    except RuntimeError:
        return _zone_engine_unavailable_response()


def _require_zone(engine: HabitusZoneEngine, zone_id: str):
    """Return zone or a 404 response tuple."""
    zone = engine.get_zone(zone_id)
    if zone:
        return zone
    return jsonify({"ok": False, "error": f"Zone {zone_id} not found"}), 404


def _zone_payload_response(engine: HabitusZoneEngine, zone_id: str, status: int = 200):
    zone = engine.get_zone(zone_id)
    if not zone:
        return jsonify({"ok": False, "error": f"Zone {zone_id} not found"}), 404
    return jsonify({"ok": True, "zone": zone}), status


# =============================================================================
# NEW API ENDPOINTS (/api/v1/zone-editor)
# =============================================================================

@zone_editor_bp.route("/zones", methods=["GET"])
def list_zones():
    """List all zones.

    Supports optional filtering by canonical ``zone_type`` via query parameter.
    """
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine

    requested_zone_type = (request.args.get("zone_type") or "").strip().lower()
    if requested_zone_type and not _is_valid_zone_type(requested_zone_type):
        return jsonify({"ok": False, "error": f"Invalid zone_type: {requested_zone_type}"}), 400

    overview = engine.get_overview()

    if not overview:
        return _zone_engine_unavailable_response()

    zones_data = []
    for zone in overview.zones:
        zone_details = engine.get_zone(zone["zone_id"])
        if not zone_details:
            continue
        if requested_zone_type and zone_details.get("zone_type") != requested_zone_type:
            continue
        zones_data.append(zone_details)

    return jsonify({
        "ok": True,
        "zones": zones_data,
        "total": len(zones_data),
    })


@zone_editor_bp.route("/zones/<zone_id>", methods=["GET"])
def get_zone(zone_id: str):
    """Get details for a specific zone."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine

    zone = engine.get_zone(zone_id)

    if not zone:
        return jsonify({"ok": False, "error": f"Zone {zone_id} not found"}), 404

    return jsonify({
        "ok": True,
        "zone": zone,
    })


@zone_editor_bp.route("/zones/<zone_id>/state", methods=["GET"])
def get_zone_state(zone_id: str):
    """Get current state of a zone."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    state = engine.get_zone_state(zone_id)
    
    if not state:
        return jsonify({"ok": False, "error": f"Zone {zone_id} not found"}), 404
    
    return jsonify({
        "ok": True,
        "state": {
            "zone_id": state.zone_id,
            "name": state.name,
            "mode": state.mode,
            "room_count": state.room_count,
            "entity_count": state.entity_count,
            "enabled": state.enabled,
            "avg_temperature": state.avg_temperature,
            "avg_humidity": state.avg_humidity,
            "occupancy": state.occupancy,
            "light_on_count": state.light_on_count,
            "active_devices": state.active_devices,
        },
    })


@zone_editor_bp.route("/rooms", methods=["GET"])
def list_rooms():
    """List all rooms."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    rooms = engine.get_rooms()
    unassigned_only = request.args.get("unassigned", "false").lower() == "true"
    
    if unassigned_only:
        # Filter to only unassigned rooms
        unassigned = []
        for room in rooms:
            if room and room.get("zone") is None:
                unassigned.append(room)
        return jsonify({
            "ok": True,
            "rooms": unassigned,
            "total": len(unassigned),
            "unassigned_count": len(unassigned),
        })
    
    return jsonify({
        "ok": True,
        "rooms": [r for r in rooms if r],
        "total": len([r for r in rooms if r]),
    })


@zone_editor_bp.route("/rooms/<room_id>", methods=["GET"])
def get_room(room_id: str):
    """Get details for a specific room."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    room = engine.get_room(room_id)
    
    if not room:
        return jsonify({"ok": False, "error": f"Room {room_id} not found"}), 404
    
    return jsonify({
        "ok": True,
        "room": room,
    })


@zone_editor_bp.route("/overview", methods=["GET"])
def get_overview():
    """Get zone overview.

    Supports optional filtering by canonical ``zone_type`` via query parameter.
    """
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine

    requested_zone_type = (request.args.get("zone_type") or "").strip().lower()
    if requested_zone_type and not _is_valid_zone_type(requested_zone_type):
        return jsonify({"ok": False, "error": f"Invalid zone_type: {requested_zone_type}"}), 400

    overview = engine.get_overview()

    if not overview:
        return _zone_engine_unavailable_response()

    zones = overview.zones
    if requested_zone_type:
        zones = [zone for zone in zones if zone.get("zone_type") == requested_zone_type]

    active_zones = sum(1 for zone in zones if zone.get("enabled") is True)

    return jsonify({
        "ok": True,
        "overview": {
            "total_zones": len(zones),
            "total_rooms": overview.total_rooms,
            "total_entities": overview.total_entities,
            "active_zones": active_zones,
            "zones": zones,
            "modes": overview.modes,
            "unassigned_rooms": overview.unassigned_rooms,
        },
    })



@zone_editor_bp.route("/ha/review", methods=["POST"])
@require_token
def review_homeassistant_topology():
    """Review Home Assistant room/entity topology against Habitus templates.

    Returns the same shape as zone-matcher mapping with zone buckets and review queue,
    but framed for the Zone-Editor workstream as a dedicated UI surface.
    """
    payload = _parse_json_body()
    if payload is None:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    areas = payload.get("areas")
    entities = payload.get("entities")
    if not isinstance(areas, list) or not isinstance(entities, list):
        return jsonify({
            "ok": False,
            "error": "invalid_format",
            "message": "'areas' und 'entities' must be arrays"
        }), 400

    review = map_homeassistant_topology(areas, entities)
    zone_defs = []

    for zone in review.get("zones", []):
        zone_defs.append({
            "zone_type": zone.get("zone_type"),
            "zone_name_de": zone.get("zone_name_de"),
            "zone_name_en": zone.get("zone_name_en"),
            "avg_confidence": zone.get("avg_confidence", 0.0),
            "area_count": zone.get("area_count", 0),
            "entity_count": zone.get("entity_count", 0),
        })

    return jsonify({
        "ok": True,
        "source": "homeassistant",
        "summary": review.get("summary", {}),
        "zones": zone_defs,
        "raw": review,
        "unassigned": review.get("ungeordnet", {}),
    })



@zone_editor_bp.route("/templates", methods=["GET"])
def list_templates():
    """List available zone templates."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    templates = engine.get_templates()
    
    return jsonify({
        "ok": True,
        "templates": templates,
    })


@zone_editor_bp.route("/modes", methods=["GET"])
def list_modes():
    """List available zone modes."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    modes = engine.get_modes()
    
    return jsonify({
        "ok": True,
        "modes": modes,
    })


@zone_editor_bp.route("/zones", methods=["POST"])
@require_token
def create_zone():
    """Create a new zone on the modern /zone-editor API."""
    data = _parse_json_body()
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400
    if not data:
        return jsonify({"ok": False, "error": "Missing request body"}), 400

    zone_id = str(data.get("zone_id") or "").strip()
    name = str(data.get("name") or "").strip()
    if not zone_id:
        return jsonify({"ok": False, "error": "Missing required field: zone_id"}), 400
    if not name:
        return jsonify({"ok": False, "error": "Missing required field: name"}), 400

    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    if engine.get_zone(zone_id):
        return jsonify({"ok": False, "error": f"Zone {zone_id} already exists"}), 409

    room_ids = data.get("rooms") if isinstance(data.get("rooms"), list) else []
    icon = str(data.get("icon") or "mdi:home-floor-1").strip() or "mdi:home-floor-1"
    priority = int(data.get("priority") or 0)

    zone_type = str(data.get("zone_type") or "living").strip().lower()
    if not _is_valid_zone_type(zone_type):
        return jsonify({"ok": False, "error": f"Invalid zone_type: {data.get('zone_type', 'living')}"}), 400

    enabled_modules = None
    if "enabled_modules" in data:
        normalized_modules = _normalize_enabled_modules(data.get("enabled_modules"))
        if normalized_modules is None:
            return jsonify({"ok": False, "error": "Invalid field: enabled_modules"}), 400
        enabled_modules = normalized_modules

    engine.create_zone(
        zone_id,
        name,
        room_ids,
        icon,
        priority,
        zone_type=zone_type,
        enabled_modules=enabled_modules,
    )
    _LOGGER.info("Created zone via modern API: %s", zone_id)
    return _zone_payload_response(engine, zone_id, status=201)


@zone_editor_bp.route("/zones/<zone_id>", methods=["PUT", "PATCH"])
@require_token
def update_zone(zone_id: str):
    """Update an existing zone on the modern /zone-editor API."""
    data = _parse_json_body()
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400
    if not data:
        return jsonify({"ok": False, "error": "Missing request body"}), 400

    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    existing = _require_zone(engine, zone_id)
    if not isinstance(existing, dict):
        return existing

    if "name" in data and not engine.set_zone_name(zone_id, str(data.get("name") or "")):
        return jsonify({"ok": False, "error": "Invalid field: name"}), 400
    if "icon" in data and not engine.set_zone_icon(zone_id, str(data.get("icon") or "")):
        return jsonify({"ok": False, "error": "Invalid field: icon"}), 400
    if "zone_type" in data:
        zone_type = str(data.get("zone_type") or "").strip().lower()
        if not _is_valid_zone_type(zone_type):
            return jsonify({"ok": False, "error": f"Invalid zone_type: {data.get('zone_type')}"}), 400
        if not engine.set_zone_type(zone_id, zone_type):
            return jsonify({"ok": False, "error": "Failed to update zone_type"}), 400
    if "mode" in data and not engine.set_zone_mode(zone_id, str(data.get("mode") or "")):
        return jsonify({"ok": False, "error": f"Invalid mode: {data.get('mode')}"}), 400
    if "enabled" in data:
        engine.set_zone_enabled(zone_id, bool(data.get("enabled")))
    if "enabled_modules" in data:
        normalized_modules = _normalize_enabled_modules(data.get("enabled_modules"))
        if normalized_modules is None:
            return jsonify({"ok": False, "error": "Invalid field: enabled_modules"}), 400
        if not engine.set_zone_enabled_modules(zone_id, normalized_modules):
            return jsonify({"ok": False, "error": "Failed to update enabled_modules"}), 400
    if "priority" in data:
        engine.set_zone_priority(zone_id, int(data.get("priority") or 0))

    rooms = data.get("rooms")
    if isinstance(rooms, list):
        current_rooms = [room.get("room_id") for room in existing.get("rooms", []) if isinstance(room, dict)]
        target_rooms = [str(room_id).strip() for room_id in rooms if str(room_id).strip()]
        for room_id in current_rooms:
            if room_id not in target_rooms:
                engine.remove_room_from_zone(zone_id, room_id)
        for room_id in target_rooms:
            if room_id not in current_rooms:
                engine.add_room_to_zone(zone_id, room_id)

    _LOGGER.info("Updated zone via modern API: %s", zone_id)
    return _zone_payload_response(engine, zone_id)


@zone_editor_bp.route("/zones/<zone_id>", methods=["DELETE"])
@require_token
def delete_zone(zone_id: str):
    """Delete a zone on the modern /zone-editor API."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    existing = _require_zone(engine, zone_id)
    if not isinstance(existing, dict):
        return existing

    if not engine.delete_zone(zone_id):
        return jsonify({"ok": False, "error": "Failed to delete zone"}), 500

    _LOGGER.info("Deleted zone via modern API: %s", zone_id)
    return jsonify({"ok": True, "deleted_zone_id": zone_id})


@zone_editor_bp.route("/zones/<zone_id>/rooms", methods=["POST"])
@require_token
def add_room(zone_id: str):
    """Add a room to a zone on the modern /zone-editor API."""
    data = _parse_json_body()
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400
    room_id = str(data.get("room_id") or "").strip()
    if not room_id:
        return jsonify({"ok": False, "error": "Missing required field: room_id"}), 400

    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    existing = _require_zone(engine, zone_id)
    if not isinstance(existing, dict):
        return existing

    if not engine.add_room_to_zone(zone_id, room_id):
        return jsonify({"ok": False, "error": f"Failed to add room {room_id} to zone {zone_id}"}), 500

    _LOGGER.info("Added room %s to zone %s via modern API", room_id, zone_id)
    return _zone_payload_response(engine, zone_id)


@zone_editor_bp.route("/zones/<zone_id>/rooms/<room_id>", methods=["DELETE"])
@require_token
def remove_room(zone_id: str, room_id: str):
    """Remove a room from a zone on the modern /zone-editor API."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return engine
    existing = _require_zone(engine, zone_id)
    if not isinstance(existing, dict):
        return existing

    if not engine.remove_room_from_zone(zone_id, room_id):
        return jsonify({"ok": False, "error": f"Room {room_id} not found in zone {zone_id}"}), 404

    _LOGGER.info("Removed room %s from zone %s via modern API", room_id, zone_id)
    return _zone_payload_response(engine, zone_id)


# =============================================================================
# LEGACY API ENDPOINTS (/api/v1/zone/editor) - Backward Compatibility
# =============================================================================

@zone_editor_legacy_bp.route("/create", methods=["POST"])
@require_token
def create_zone_legacy():
    """Create a new zone (legacy endpoint)."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400
    
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    
    if "zone_id" not in data:
        return jsonify({"error": "Missing required field: zone_id"}), 400
    
    if "name" not in data:
        return jsonify({"error": "Missing required field: name"}), 400
    
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return jsonify({"error": engine[0]["error"]}), engine[1]
    zone_id = data["zone_id"]
    
    # Check for duplicate
    existing = engine.get_zone(zone_id)
    if existing:
        return jsonify({"error": f"Zone {zone_id} already exists"}), 409
    
    room_ids = data.get("rooms", [])
    icon = data.get("icon", "mdi:home-floor-1")
    priority = int(data.get("priority") or 0)
    zone_type = str(data.get("zone_type") or "").strip().lower() or None
    if zone_type is not None and not _is_valid_zone_type(zone_type):
        return jsonify({"error": f"Invalid zone_type: {data.get('zone_type')}"}), 400

    if "enabled_modules" in data:
        normalized_modules = _normalize_enabled_modules(data.get("enabled_modules"))
        if normalized_modules is None:
            return jsonify({"error": "Invalid field: enabled_modules"}), 400
    else:
        normalized_modules = None
    
    kwargs = {}
    if zone_type is not None:
        kwargs["zone_type"] = zone_type
    if normalized_modules is not None:
        kwargs["enabled_modules"] = normalized_modules
    if priority:
        kwargs["priority"] = priority

    engine.create_zone(zone_id, data["name"], room_ids, icon, **kwargs)
    created = engine.get_zone(zone_id)
    
    _LOGGER.info(f"Created zone: {zone_id}")
    
    return jsonify({
        "ok": True,
        "zone": created,
    })


@zone_editor_legacy_bp.route("/list", methods=["GET"])
@require_token
def list_zones_legacy():
    """List all zones (legacy endpoint)."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return jsonify({"error": engine[0]["error"]}), engine[1]

    requested_zone_type = (request.args.get("zone_type") or "").strip().lower()
    if requested_zone_type and not _is_valid_zone_type(requested_zone_type):
        return jsonify({"error": f"Invalid zone_type: {requested_zone_type}"}), 400

    overview = engine.get_overview()
    
    zones_data = []
    for zone in overview.zones:
        zone_details = engine.get_zone(zone["zone_id"])
        if not zone_details:
            continue
        if requested_zone_type and zone_details.get("zone_type") != requested_zone_type:
            continue
        zones_data.append(zone_details)
    
    return jsonify({
        "zones": zones_data,
        "count": len(zones_data),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


@zone_editor_legacy_bp.route("/<zone_id>", methods=["GET"])
@require_token
def get_zone_legacy(zone_id: str):
    """Get details for a specific zone (legacy endpoint)."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return jsonify({"error": engine[0]["error"]}), engine[1]
    zone = engine.get_zone(zone_id)
    
    if not zone:
        return jsonify({"error": f"Zone {zone_id} not found"}), 404
    
    return jsonify({
        "ok": True,
        "zone": zone,
    })


@zone_editor_legacy_bp.route("/<zone_id>", methods=["PUT"])
@require_token
def update_zone_legacy(zone_id: str):
    """Update an existing zone (legacy endpoint)."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400
    
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return jsonify({"error": engine[0]["error"]}), engine[1]
    existing = engine.get_zone(zone_id)
    
    if not existing:
        return jsonify({"error": f"Zone {zone_id} not found"}), 404
    
    # Update zone settings
    if "name" in data:
        engine.set_zone_name(zone_id, data["name"])
    if "icon" in data:
        engine.set_zone_icon(zone_id, data["icon"])
    if "mode" in data:
        engine.set_zone_mode(zone_id, data["mode"])
    if "enabled" in data:
        engine.set_zone_enabled(zone_id, data["enabled"])
    if "priority" in data:
        engine.set_zone_priority(zone_id, int(data["priority"]) if data.get("priority") is not None else 0)
    if "zone_type" in data:
        zone_type = str(data["zone_type"] or "").strip().lower()
        if not _is_valid_zone_type(zone_type):
            return jsonify({"error": f"Invalid zone_type: {data.get('zone_type')}"}), 400
        if not engine.set_zone_type(zone_id, zone_type):
            return jsonify({"error": "Failed to update zone_type"}), 400
    if "enabled_modules" in data:
        normalized_modules = _normalize_enabled_modules(data["enabled_modules"])
        if normalized_modules is None:
            return jsonify({"error": "Invalid field: enabled_modules"}), 400
        if not engine.set_zone_enabled_modules(zone_id, normalized_modules):
            return jsonify({"error": "Failed to update enabled_modules"}), 400
    
    _LOGGER.info(f"Updated zone: {zone_id}")
    
    return jsonify({
        "ok": True,
        "zone": engine.get_zone(zone_id),
    })


@zone_editor_legacy_bp.route("/<zone_id>", methods=["DELETE"])
@require_token
def delete_zone_legacy(zone_id: str):
    """Delete a zone (legacy endpoint)."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return jsonify({"error": engine[0]["error"]}), engine[1]
    existing = engine.get_zone(zone_id)
    
    if not existing:
        return jsonify({"error": f"Zone {zone_id} not found"}), 404
    
    success = engine.delete_zone(zone_id)
    
    if not success:
        return jsonify({"error": "Failed to delete zone"}), 500
    
    _LOGGER.info(f"Deleted zone: {zone_id}")
    
    return jsonify({
        "ok": True,
    })


@zone_editor_legacy_bp.route("/<zone_id>/rooms", methods=["POST"])
@require_token
def add_room_legacy(zone_id: str):
    """Add a room to a zone (legacy endpoint)."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400
    
    if not data or "room_id" not in data:
        return jsonify({"error": "Missing required field: room_id"}), 400
    
    room_id = data["room_id"]
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return jsonify({"error": engine[0]["error"]}), engine[1]
    
    existing = engine.get_zone(zone_id)
    if not existing:
        return jsonify({"error": f"Zone {zone_id} not found"}), 404
    
    success = engine.add_room_to_zone(zone_id, room_id)
    
    if not success:
        return jsonify({"error": "Failed to add room to zone"}), 500
    
    _LOGGER.info(f"Added room {room_id} to zone {zone_id}")
    
    return jsonify({
        "ok": True,
        "zone": engine.get_zone(zone_id),
    })


@zone_editor_legacy_bp.route("/<zone_id>/rooms/<room_id>", methods=["DELETE"])
@require_token
def remove_room_legacy(zone_id: str, room_id: str):
    """Remove a room from a zone (legacy endpoint)."""
    engine = _get_zone_engine_or_unavailable()
    if isinstance(engine, tuple):
        return jsonify({"error": engine[0]["error"]}), engine[1]
    
    existing = engine.get_zone(zone_id)
    if not existing:
        return jsonify({"error": f"Zone {zone_id} not found"}), 404
    
    success = engine.remove_room_from_zone(zone_id, room_id)
    
    if not success:
        return jsonify({"error": f"Room {room_id} not found in zone {zone_id}"}), 404
    
    _LOGGER.info(f"Removed room {room_id} from zone {zone_id}")
    
    return jsonify({
        "ok": True,
        "zone": engine.get_zone(zone_id),
    })


# ============================================================================
# HA Test Compatibility Aliases
# These routes provide backward compatibility for HA integration tests
# ============================================================================

# Additional blueprint for /api/v1/zone/* legacy paths (HA test compatibility)
zone_legacy_alias_bp = Blueprint("zone_legacy_alias", __name__, url_prefix="/api/v1/zone")

# Export all blueprints for registration
__all__ = ["zone_editor_bp", "zone_editor_legacy_bp", "zone_legacy_alias_bp"]


@zone_legacy_alias_bp.route("/create", methods=["POST"])
@require_token
def create_zone_alias():
    """Create zone alias for HA test compatibility.
    
    Redirects to /api/v1/zone/editor/create
    """
    from flask import redirect, url_for
    return redirect(url_for("zone_editor_legacy.create_zone_legacy"))


@zone_legacy_alias_bp.route("/update", methods=["POST"])
@zone_legacy_alias_bp.route("/<zone_id>", methods=["PUT"])
@require_token
def update_zone_alias(zone_id=None):
    """Update zone alias for HA test compatibility.
    
    Redirects to /api/v1/zone/editor/<zone_id>
    """
    from flask import redirect, url_for
    if zone_id:
        return redirect(url_for("zone_editor_legacy.update_zone_legacy", zone_id=zone_id))
    # For /api/v1/zone/update without zone_id, expect zone_id in body
    data = request.get_json(force=True) if request.is_json else {}
    zone_id = data.get("zone_id")
    if not zone_id:
        return jsonify({"error": "Missing zone_id"}), 400
    return redirect(url_for("zone_editor_legacy.update_zone_legacy", zone_id=zone_id))


@zone_legacy_alias_bp.route("/delete/<zone_id>", methods=["DELETE"])
@require_token
def delete_zone_alias(zone_id: str):
    """Delete zone alias for HA test compatibility.
    
    Redirects to /api/v1/zone/editor/<zone_id> (DELETE)
    """
    from flask import redirect, url_for
    return redirect(url_for("zone_editor_legacy.delete_zone_legacy", zone_id=zone_id))
