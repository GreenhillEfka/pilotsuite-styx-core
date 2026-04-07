"""Room Context Admin API — Vertical Slice Phase 2.
Full CRUD + activation for Room Contexts.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from typing import Dict, List

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("room_context_admin", __name__, url_prefix="/api/v1/contexts")

# In-Memory Store
_contexts: Dict[str, dict] = {}

@bp.route("/rooms", methods=["GET"])
def list_room_contexts():
    """List all Room Contexts."""
    return jsonify({"ok": True, "contexts": list(_contexts.values()), "count": len(_contexts)})

@bp.route("/rooms", methods=["POST"])
def create_room_context():
    """Create or update a Room Context."""
    data = request.get_json() or {}
    context_id = data.get("context_id")
    if not context_id:
        return jsonify({"ok": False, "error": "context_id required"}), 400
    
    _contexts[context_id] = {
        "context_id": context_id,
        "name": data.get("name", context_id),
        "zone_ref": data.get("zone_ref"),
        "trigger_time": data.get("trigger_time"),
        "trigger_presence": data.get("trigger_presence"),
        "ha_scene_id": data.get("ha_scene_id"),
        "ha_automation_ids": data.get("ha_automation_ids", []),
        "active": data.get("active", False),
        "learned": data.get("learned", False)
    }
    _LOGGER.info(f"Created/updated Room Context: {context_id}")
    return jsonify({"ok": True, "context": _contexts[context_id]})

@bp.route("/rooms/<context_id>", methods=["GET"])
def get_room_context(context_id):
    """Get single Room Context detail."""
    ctx = _contexts.get(context_id)
    if not ctx:
        return jsonify({"ok": False, "error": "Context not found"}), 404
    return jsonify({"ok": True, "context": ctx})

@bp.route("/rooms/<context_id>", methods=["DELETE"])
def delete_room_context(context_id):
    """Delete a Room Context."""
    if context_id in _contexts:
        del _contexts[context_id]
        _LOGGER.info(f"Deleted Room Context: {context_id}")
        return jsonify({"ok": True, "deleted": context_id})
    return jsonify({"ok": False, "error": "Context not found"}), 404

@bp.route("/rooms/<context_id>/activate", methods=["POST"])
def activate_room_context(context_id):
    """Activate a Room Context (triggers HA scene)."""
    if context_id not in _contexts:
        return jsonify({"ok": False, "error": "Context not found"}), 404
    
    _contexts[context_id]["active"] = True
    
    # Trigger HA scene if linked
    ha_scene_id = _contexts[context_id].get("ha_scene_id")
    if ha_scene_id:
        # TODO: Call HA API to activate scene
        _LOGGER.info(f"Would trigger HA scene: {ha_scene_id}")
    
    _LOGGER.info(f"Activated Room Context: {context_id}")
    return jsonify({"ok": True, "activated": context_id})

@bp.route("/rooms/<context_id>/deactivate", methods=["POST"])
def deactivate_room_context(context_id):
    """Deactivate a Room Context."""
    if context_id in _contexts:
        _contexts[context_id]["active"] = False
        _LOGGER.info(f"Deactivated Room Context: {context_id}")
        return jsonify({"ok": True, "deactivated": context_id})
    return jsonify({"ok": False, "error": "Context not found"}), 404

@bp.route("/rooms/active", methods=["GET"])
def get_active_contexts():
    """Get all active Room Contexts."""
    active = [ctx for ctx in _contexts.values() if ctx.get("active")]
    return jsonify({"ok": True, "active_contexts": active, "count": len(active)})

@bp.route("/rooms/summary", methods=["GET"])
def room_contexts_summary():
    """Get summary of all Room Contexts."""
    total = len(_contexts)
    active = sum(1 for c in _contexts.values() if c.get("active"))
    with_scene = sum(1 for c in _contexts.values() if c.get("ha_scene_id"))
    learned = sum(1 for c in _contexts.values() if c.get("learned"))
    
    return jsonify({
        "ok": True,
        "summary": {
            "total_contexts": total,
            "active_contexts": active,
            "contexts_with_scene": with_scene,
            "learned_contexts": learned
        }
    })
