"""Presence Entity Admin API — Vertical Slice Phase 2.
Full CRUD + state management for Presence Entities.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from typing import Dict, List

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("presence_entity_admin", __name__, url_prefix="/api/v1/entities")

# In-Memory Store
_entities: Dict[str, dict] = {}

@bp.route("/presence", methods=["GET"])
def list_presence_entities():
    """List all Presence Entities."""
    return jsonify({"ok": True, "entities": list(_entities.values()), "count": len(_entities)})

@bp.route("/presence", methods=["POST"])
def create_presence_entity():
    """Create or update a Presence Entity."""
    data = request.get_json() or {}
    entity_id = data.get("entity_id")
    if not entity_id:
        return jsonify({"ok": False, "error": "entity_id required"}), 400
    
    _entities[entity_id] = {
        "entity_id": entity_id,
        "ha_entity_id": data.get("ha_entity_id"),
        "name": data.get("name", entity_id),
        "presence_type": data.get("presence_type", "presence"),
        "zone_ref": data.get("zone_ref"),
        "current_state": data.get("current_state", False),
        "last_changed": data.get("last_changed")
    }
    _LOGGER.info(f"Created/updated Presence Entity: {entity_id}")
    return jsonify({"ok": True, "entity": _entities[entity_id]})

@bp.route("/presence/<entity_id>", methods=["GET"])
def get_presence_entity(entity_id):
    """Get single Presence Entity detail."""
    entity = _entities.get(entity_id)
    if not entity:
        return jsonify({"ok": False, "error": "Entity not found"}), 404
    return jsonify({"ok": True, "entity": entity})

@bp.route("/presence/<entity_id>", methods=["DELETE"])
def delete_presence_entity(entity_id):
    """Delete a Presence Entity."""
    if entity_id in _entities:
        del _entities[entity_id]
        _LOGGER.info(f"Deleted Presence Entity: {entity_id}")
        return jsonify({"ok": True, "deleted": entity_id})
    return jsonify({"ok": False, "error": "Entity not found"}), 404

@bp.route("/presence/<entity_id>/state", methods=["POST"])
def update_presence_state(entity_id):
    """Update presence state for an entity."""
    if entity_id not in _entities:
        return jsonify({"ok": False, "error": "Entity not found"}), 404
    
    data = request.get_json() or {}
    _entities[entity_id]["current_state"] = data.get("present", False)
    _entities[entity_id]["last_changed"] = "now"
    
    _LOGGER.info(f"Updated presence state for {entity_id}: {_entities[entity_id]['current_state']}")
    return jsonify({"ok": True, "entity_id": entity_id, "present": _entities[entity_id]["current_state"]})

@bp.route("/presence/active", methods=["GET"])
def get_active_presence():
    """Get all entities currently detecting presence."""
    active = [e for e in _entities.values() if e.get("current_state")]
    return jsonify({"ok": True, "active": active, "count": len(active)})

@bp.route("/presence/by_zone", methods=["GET"])
def get_presence_by_zone():
    """Get presence entities grouped by zone."""
    by_zone: Dict[str, List] = {}
    for entity in _entities.values():
        zone = entity.get("zone_ref") or "unassigned"
        if zone not in by_zone:
            by_zone[zone] = []
        by_zone[zone].append(entity)
    
    return jsonify({"ok": True, "by_zone": by_zone})

@bp.route("/presence/summary", methods=["GET"])
def presence_summary():
    """Get summary of all Presence Entities."""
    total = len(_entities)
    active = sum(1 for e in _entities.values() if e.get("current_state"))
    by_type: Dict[str, int] = {}
    
    for entity in _entities.values():
        ptype = entity.get("presence_type", "unknown")
        by_type[ptype] = by_type.get(ptype, 0) + 1
    
    return jsonify({
        "ok": True,
        "summary": {
            "total_entities": total,
            "active_entities": active,
            "by_type": by_type
        }
    })
