"""State Bridge Admin API — Vertical Slice Phase 2.
Full CRUD + history management for State Bridges.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from typing import Dict, List
from datetime import datetime

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("state_bridge_admin", __name__, url_prefix="/api/v1")

# In-Memory Store
_states: Dict[str, dict] = {}

@bp.route("/states", methods=["GET"])
def list_states():
    """List all State Bridges."""
    return jsonify({"ok": True, "states": list(_states.values()), "count": len(_states)})

@bp.route("/states", methods=["POST"])
def create_state():
    """Create or update a State Bridge."""
    data = request.get_json() or {}
    state_id = data.get("state_id")
    if not state_id:
        return jsonify({"ok": False, "error": "state_id required"}), 400
    
    _states[state_id] = {
        "state_id": state_id,
        "ha_entity_id": data.get("ha_entity_id"),
        "name": data.get("name", state_id),
        "current_state": data.get("current_state", {}),
        "history": data.get("history", []),
        "subscribers": data.get("subscribers", []),
        "last_sync": data.get("last_sync")
    }
    _LOGGER.info(f"Created/updated State Bridge: {state_id}")
    return jsonify({"ok": True, "state": _states[state_id]})

@bp.route("/states/<state_id>", methods=["GET"])
def get_state(state_id):
    """Get single State Bridge detail."""
    state = _states.get(state_id)
    if not state:
        return jsonify({"ok": False, "error": "State not found"}), 404
    return jsonify({"ok": True, "state": state})

@bp.route("/states/<state_id>", methods=["DELETE"])
def delete_state(state_id):
    """Delete a State Bridge."""
    if state_id in _states:
        del _states[state_id]
        _LOGGER.info(f"Deleted State Bridge: {state_id}")
        return jsonify({"ok": True, "deleted": state_id})
    return jsonify({"ok": False, "error": "State not found"}), 404

@bp.route("/states/<state_id>/history", methods=["GET"])
def get_state_history(state_id):
    """Get history for a State Bridge."""
    if state_id not in _states:
        return jsonify({"ok": False, "error": "State not found"}), 404
    
    limit = int(request.args.get("limit", 50))
    history = _states[state_id].get("history", [])[-limit:]
    return jsonify({"ok": True, "state_id": state_id, "history": history, "count": len(history)})

@bp.route("/states/<state_id>/history", methods=["POST"])
def add_state_history(state_id):
    """Add history entry for a State Bridge."""
    if state_id not in _states:
        return jsonify({"ok": False, "error": "State not found"}), 404
    
    data = request.get_json() or {}
    history_entry = {
        "at": datetime.utcnow().isoformat(),
        "state": data.get("state"),
        "attributes": data.get("attributes", {})
    }
    
    if "history" not in _states[state_id]:
        _states[state_id]["history"] = []
    
    _states[state_id]["history"].append(history_entry)
    # Keep only last 100 entries
    _states[state_id]["history"] = _states[state_id]["history"][-100:]
    
    return jsonify({"ok": True, "state_id": state_id, "history_count": len(_states[state_id]["history"])})

@bp.route("/states/<state_id>/subscribe", methods=["POST"])
def subscribe_to_state(state_id):
    """Subscribe to state changes."""
    if state_id not in _states:
        return jsonify({"ok": False, "error": "State not found"}), 404
    
    data = request.get_json() or {}
    subscriber = data.get("subscriber")
    
    if subscriber and subscriber not in _states[state_id].get("subscribers", []):
        _states[state_id].setdefault("subscribers", []).append(subscriber)
    
    return jsonify({"ok": True, "state_id": state_id, "subscribers": _states[state_id].get("subscribers", [])})

@bp.route("/states/summary", methods=["GET"])
def states_summary():
    """Get summary of all State Bridges."""
    total = len(_states)
    with_history = sum(1 for s in _states.values() if s.get("history") and len(s["history"]) > 0)
    with_subscribers = sum(1 for s in _states.values() if s.get("subscribers") and len(s["subscribers"]) > 0)
    total_history_entries = sum(len(s.get("history", [])) for s in _states.values())
    
    return jsonify({
        "ok": True,
        "summary": {
            "total_states": total,
            "states_with_history": with_history,
            "states_with_subscribers": with_subscribers,
            "total_history_entries": total_history_entries
        }
    })
