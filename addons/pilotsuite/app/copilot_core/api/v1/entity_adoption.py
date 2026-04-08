"""Entity Adoption API Endpoints.

API für Auto-Vererbung von Entities (Raum → Zone).

Endpoints:
- GET /api/v1/adoption/zones/<zone_id>/entities — Alle geerbten Entities
- POST /api/v1/adoption/assign — Entity manuell zuordnen
- DELETE /api/v1/adoption/assign/<id> — Zuordnung entfernen
- GET /api/v1/adoption/stats — Adoption-Statistiken
- GET /api/v1/adoption/zones — Alle Zonen mit Adoption-Status
- POST /api/v1/adoption/refresh/<zone_id> — Zone neu berechnen
"""
from __future__ import annotations

import asyncio
import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, Optional

from copilot_core.api.security import validate_token
from copilot_core.homeassistant.entity_adoption import (
    get_adoption_service,
    AdoptionPriority,
)

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("entity_adoption", __name__, url_prefix="/adoption")


@bp.before_request
def _require_auth():
    """Require authentication for all adoption endpoints."""
    if not validate_token(request):
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required"
        }), 401


@bp.route("/zones/<zone_id>/entities", methods=["GET"])
def get_zone_entities(zone_id: str):
    """Get all inherited entities for a zone.
    
    Returns both auto-inherited entities from rooms and manual overrides.
    """
    try:
        service = get_adoption_service()
        result = asyncio.run(service.get_zone_entities(zone_id))
        
        return jsonify({
            "status": "ok",
            **result,
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get zone entities for %s: %s", zone_id, e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/zones", methods=["GET"])
def get_all_zones():
    """Get adoption status for all zones."""
    try:
        service = get_adoption_service()
        states = service.get_all_zone_states()
        
        return jsonify({
            "status": "ok",
            "zone_count": len(states),
            "zones": {
                zone_id: state.to_dict()
                for zone_id, state in states.items()
            },
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get all zones: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


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
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body required"
            }), 400
        
        entity_id = data.get("entity_id")
        zone_id = data.get("zone_id")
        
        if not entity_id or not zone_id:
            return jsonify({
                "status": "error",
                "message": "entity_id and zone_id are required"
            }), 400
        
        source_room_id = data.get("source_room_id")
        
        # Parse priority
        priority_str = data.get("priority", "override").lower()
        priority_map = {
            "override": AdoptionPriority.OVERRIDE,
            "specific": AdoptionPriority.SPECIFIC,
            "inherited": AdoptionPriority.INHERITED,
        }
        priority = priority_map.get(priority_str, AdoptionPriority.OVERRIDE)
        
        metadata = data.get("metadata", {})
        
        service = get_adoption_service()
        assignment = asyncio.run(service.assign_entity(
            entity_id=entity_id,
            zone_id=zone_id,
            source_room_id=source_room_id,
            priority=priority,
            metadata=metadata,
        ))
        
        return jsonify({
            "status": "ok",
            "message": f"Entity {entity_id} assigned to zone {zone_id}",
            "assignment": assignment.to_dict(),
        }), 201
    
    except Exception as e:
        _LOGGER.error("Failed to assign entity: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/assign/<assignment_id>", methods=["DELETE"])
def remove_assignment(assignment_id: str):
    """Remove an entity assignment.
    
    Assignment ID format: {entity_id}:{zone_id}
    """
    try:
        service = get_adoption_service()
        success = asyncio.run(service.remove_assignment(assignment_id))
        
        if not success:
            return jsonify({
                "status": "error",
                "message": f"Assignment not found: {assignment_id}"
            }), 404
        
        return jsonify({
            "status": "ok",
            "message": f"Assignment {assignment_id} removed",
        })
    
    except Exception as e:
        _LOGGER.error("Failed to remove assignment %s: %s", assignment_id, e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/stats", methods=["GET"])
def get_adoption_stats():
    """Get adoption statistics."""
    try:
        service = get_adoption_service()
        stats = service.get_stats()
        
        return jsonify({
            "status": "ok",
            **stats,
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get adoption stats: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/refresh/<zone_id>", methods=["POST"])
def refresh_zone(zone_id: str):
    """Force refresh of a zone's adoption state."""
    try:
        service = get_adoption_service()
        state = asyncio.run(service.refresh_zone(zone_id))
        
        return jsonify({
            "status": "ok",
            "message": f"Zone {zone_id} refreshed",
            "state": state.to_dict() if state else None,
        })
    
    except Exception as e:
        _LOGGER.error("Failed to refresh zone %s: %s", zone_id, e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/refresh", methods=["POST"])
def refresh_all_zones():
    """Force refresh of all zone adoption states."""
    try:
        service = get_adoption_service()
        states = asyncio.run(service.refresh_all_zones())
        
        return jsonify({
            "status": "ok",
            "message": f"Refreshed {len(states)} zones",
            "zones": {
                zone_id: state.to_dict()
                for zone_id, state in states.items()
            },
        })
    
    except Exception as e:
        _LOGGER.error("Failed to refresh all zones: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/mapping/room-zone", methods=["POST"])
def set_room_zone_mapping():
    """Map a room to a zone for inheritance.
    
    Request body:
    {
        "room_id": "room_living",
        "zone_id": "zone_og"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body required"
            }), 400
        
        room_id = data.get("room_id")
        zone_id = data.get("zone_id")
        
        if not room_id or not zone_id:
            return jsonify({
                "status": "error",
                "message": "room_id and zone_id are required"
            }), 400
        
        service = get_adoption_service()
        service.set_room_zone_mapping(room_id, zone_id)
        
        # Trigger zone update
        asyncio.run(service.refresh_zone(zone_id))
        
        return jsonify({
            "status": "ok",
            "message": f"Room {room_id} mapped to zone {zone_id}",
        })
    
    except Exception as e:
        _LOGGER.error("Failed to set room-zone mapping: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/mapping/entity-room", methods=["POST"])
def set_entity_room_mapping():
    """Map an entity to a room.
    
    Request body:
    {
        "entity_id": "sensor.living_room_temperature",
        "room_id": "room_living"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body required"
            }), 400
        
        entity_id = data.get("entity_id")
        room_id = data.get("room_id")
        
        if not entity_id or not room_id:
            return jsonify({
                "status": "error",
                "message": "entity_id and room_id are required"
            }), 400
        
        service = get_adoption_service()
        service.set_entity_room_mapping(entity_id, room_id)
        
        # Trigger zone update if room is mapped
        zone_id = service._room_zone_map.get(room_id)
        if zone_id:
            asyncio.run(service.refresh_zone(zone_id))
        
        return jsonify({
            "status": "ok",
            "message": f"Entity {entity_id} mapped to room {room_id}",
        })
    
    except Exception as e:
        _LOGGER.error("Failed to set entity-room mapping: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/assignments", methods=["GET"])
def get_all_assignments():
    """Get all entity assignments."""
    try:
        service = get_adoption_service()
        assignments = service.get_all_assignments()
        
        return jsonify({
            "status": "ok",
            "count": len(assignments),
            "assignments": [a.to_dict() for a in assignments],
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get all assignments: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/assignment/<assignment_id>", methods=["GET"])
def get_assignment(assignment_id: str):
    """Get specific assignment by ID."""
    try:
        service = get_adoption_service()
        assignment = service.get_assignment(assignment_id)
        
        if not assignment:
            return jsonify({
                "status": "error",
                "message": f"Assignment not found: {assignment_id}"
            }), 404
        
        return jsonify({
            "status": "ok",
            "assignment": assignment.to_dict(),
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get assignment %s: %s", assignment_id, e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


def init_adoption_api(app=None):
    """Initialize adoption API blueprint."""
    # The blueprint is already created, this is for future extensions
    _LOGGER.info("Entity Adoption API initialized")
    return bp
