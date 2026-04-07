"""Entity Adoption API Endpoints.

API für Auto-Vererbung von Entities (Raum → Zone).

Endpoints:
- GET /api/v1/entity-adoption/zones/<zone_id>/entities — Alle geerbten Entities
- POST /api/v1/entity-adoption/assign — Entity manuell zuordnen
- DELETE /api/v1/entity-adoption/assign/<id> — Zuordnung entfernen
- GET /api/v1/entity-adoption/stats — Adoption-Statistiken
- GET /api/v1/entity-adoption/zones — Alle Zonen mit Adoption-Status
- POST /api/v1/entity-adoption/refresh/<zone_id> — Zone neu berechnen
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.homeassistant.entity_adoption import AdoptionPriority, get_adoption_service

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("entity_adoption", __name__, url_prefix="/api/v1/entity-adoption")


def _error_response(message: str, status_code: int = 400):
    return jsonify({"status": "error", "message": message}), status_code


def _handle_exception(action: str, exc: Exception):
    _LOGGER.exception("Entity adoption API action failed: %s", action)
    return _error_response(str(exc), 500)


def _require_json_object():
    data = request.get_json(silent=True)
    if data is None:
        return None, _error_response("Request body required", 400)
    if not isinstance(data, dict):
        return None, _error_response("JSON body must be an object", 400)
    return data, None


def _run_async(action: str, coroutine):
    try:
        return asyncio.run(coroutine), None
    except Exception as exc:  # pragma: no cover - exercised through contract tests
        return None, _handle_exception(action, exc)


def _call(action: str, func, *args, **kwargs):
    try:
        return func(*args, **kwargs), None
    except Exception as exc:  # pragma: no cover - exercised through contract tests
        return None, _handle_exception(action, exc)


@bp.before_request
def _require_auth():
    """Require authentication for all adoption endpoints."""
    if not validate_token(request):
        return jsonify(
            {
                "error": "unauthorized",
                "message": "Valid X-Auth-Token or Bearer token required",
            }
        ), 401


@bp.route("/zones/<zone_id>/entities", methods=["GET"])
def get_zone_entities(zone_id: str):
    """Get all inherited entities for a zone.

    Returns both auto-inherited entities from rooms and manual overrides.
    """
    service = get_adoption_service()
    result, err = _run_async("get_zone_entities", service.get_zone_entities(zone_id))
    if err:
        return err

    return jsonify({"status": "ok", **result})


@bp.route("/zones", methods=["GET"])
def get_all_zones():
    """Get adoption status for all zones."""
    service = get_adoption_service()
    states, err = _call("get_all_zone_states", service.get_all_zone_states)
    if err:
        return err

    return jsonify(
        {
            "status": "ok",
            "zone_count": len(states),
            "zones": {zone_id: state.to_dict() for zone_id, state in states.items()},
        }
    )


@bp.route("/assign", methods=["POST"])
def assign_entity():
    """Manually assign an entity to a zone.

    Request body:
    {
        "entity_id": "sensor.living_room_temperature",
        "zone_id": "zone_og",
        "source_room_id": "room_living",  # optional
        "priority": "override",  # "override" | "specific" | "inherited"
        "metadata": {}  # optional
    }
    """
    data, err = _require_json_object()
    if err:
        return err

    entity_id = data.get("entity_id")
    zone_id = data.get("zone_id")
    if not entity_id or not zone_id:
        return _error_response("entity_id and zone_id are required", 400)

    source_room_id = data.get("source_room_id")
    priority_str = str(data.get("priority", "override")).lower()
    priority_map = {
        "override": AdoptionPriority.OVERRIDE,
        "specific": AdoptionPriority.SPECIFIC,
        "inherited": AdoptionPriority.INHERITED,
    }
    priority = priority_map.get(priority_str, AdoptionPriority.OVERRIDE)

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        return _error_response("metadata must be an object", 400)

    service = get_adoption_service()
    assignment, err = _run_async(
        "assign_entity",
        service.assign_entity(
            entity_id=entity_id,
            zone_id=zone_id,
            source_room_id=source_room_id,
            priority=priority,
            metadata=metadata,
        ),
    )
    if err:
        return err

    return (
        jsonify(
            {
                "status": "ok",
                "message": f"Entity {entity_id} assigned to zone {zone_id}",
                "assignment": assignment.to_dict(),
            }
        ),
        201,
    )


@bp.route("/assign/<assignment_id>", methods=["DELETE"])
def remove_assignment(assignment_id: str):
    """Remove an entity assignment.

    Assignment ID format: {entity_id}:{zone_id}
    """
    service = get_adoption_service()
    success, err = _run_async("remove_assignment", service.remove_assignment(assignment_id))
    if err:
        return err
    if not success:
        return _error_response(f"Assignment not found: {assignment_id}", 404)

    return jsonify({"status": "ok", "message": f"Assignment {assignment_id} removed"})


@bp.route("/stats", methods=["GET"])
def get_adoption_stats():
    """Get adoption statistics."""
    service = get_adoption_service()
    stats, err = _call("get_stats", service.get_stats)
    if err:
        return err

    return jsonify({"status": "ok", **stats})


@bp.route("/refresh/<zone_id>", methods=["POST"])
def refresh_zone(zone_id: str):
    """Force refresh of a zone's adoption state."""
    service = get_adoption_service()
    state, err = _run_async("refresh_zone", service.refresh_zone(zone_id))
    if err:
        return err

    return jsonify(
        {
            "status": "ok",
            "message": f"Zone {zone_id} refreshed",
            "state": state.to_dict() if state else None,
        }
    )


@bp.route("/refresh", methods=["POST"])
def refresh_all_zones():
    """Force refresh of all zone adoption states."""
    service = get_adoption_service()
    states, err = _run_async("refresh_all_zones", service.refresh_all_zones())
    if err:
        return err

    return jsonify(
        {
            "status": "ok",
            "message": f"Refreshed {len(states)} zones",
            "zones": {zone_id: state.to_dict() for zone_id, state in states.items()},
        }
    )


@bp.route("/mapping/room-zone", methods=["POST"])
def set_room_zone_mapping():
    """Map a room to a zone for inheritance.

    Request body:
    {
        "room_id": "room_living",
        "zone_id": "zone_og"
    }
    """
    data, err = _require_json_object()
    if err:
        return err

    room_id = data.get("room_id")
    zone_id = data.get("zone_id")
    if not room_id or not zone_id:
        return _error_response("room_id and zone_id are required", 400)

    service = get_adoption_service()
    _result, err = _call("set_room_zone_mapping", service.set_room_zone_mapping, room_id, zone_id)
    if err:
        return err

    _state, err = _run_async("refresh_zone_after_room_zone_mapping", service.refresh_zone(zone_id))
    if err:
        return err

    return jsonify({"status": "ok", "message": f"Room {room_id} mapped to zone {zone_id}"})


@bp.route("/mapping/entity-room", methods=["POST"])
def set_entity_room_mapping():
    """Map an entity to a room.

    Request body:
    {
        "entity_id": "sensor.living_room_temperature",
        "room_id": "room_living"
    }
    """
    data, err = _require_json_object()
    if err:
        return err

    entity_id = data.get("entity_id")
    room_id = data.get("room_id")
    if not entity_id or not room_id:
        return _error_response("entity_id and room_id are required", 400)

    service = get_adoption_service()
    _result, err = _call("set_entity_room_mapping", service.set_entity_room_mapping, entity_id, room_id)
    if err:
        return err

    zone_id = getattr(service, "_room_zone_map", {}).get(room_id)
    if zone_id:
        _state, err = _run_async("refresh_zone_after_entity_room_mapping", service.refresh_zone(zone_id))
        if err:
            return err

    return jsonify({"status": "ok", "message": f"Entity {entity_id} mapped to room {room_id}"})


@bp.route("/assignments", methods=["GET"])
def get_all_assignments():
    """Get all entity assignments."""
    service = get_adoption_service()
    assignments, err = _call("get_all_assignments", service.get_all_assignments)
    if err:
        return err

    return jsonify(
        {
            "status": "ok",
            "count": len(assignments),
            "assignments": [assignment.to_dict() for assignment in assignments],
        }
    )


@bp.route("/assignment/<assignment_id>", methods=["GET"])
def get_assignment(assignment_id: str):
    """Get specific assignment by ID."""
    service = get_adoption_service()
    assignment, err = _call("get_assignment", service.get_assignment, assignment_id)
    if err:
        return err
    if not assignment:
        return _error_response(f"Assignment not found: {assignment_id}", 404)

    return jsonify({"status": "ok", "assignment": assignment.to_dict()})


def init_adoption_api(app=None):
    """Initialize adoption API blueprint."""
    _LOGGER.info("Entity Adoption API initialized")
    return bp
