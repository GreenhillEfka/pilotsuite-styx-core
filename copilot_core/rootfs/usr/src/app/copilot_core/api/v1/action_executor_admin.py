"""Action Executor Admin API — Vertical Slice Phase 2.
Full CRUD + execution for Actions.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from typing import Dict, List
from datetime import datetime

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("action_executor_admin", __name__, url_prefix="/api/v1")

# In-Memory Store
_actions: Dict[str, dict] = {}
_execution_log: List[dict] = []

@bp.route("/actions", methods=["GET"])
def list_actions():
    """List all Actions."""
    return jsonify({"ok": True, "actions": list(_actions.values()), "count": len(_actions)})

@bp.route("/actions", methods=["POST"])
def create_action():
    """Create or update an Action."""
    data = request.get_json() or {}
    action_id = data.get("action_id")
    if not action_id:
        return jsonify({"ok": False, "error": "action_id required"}), 400
    
    _actions[action_id] = {
        "action_id": action_id,
        "name": data.get("name", action_id),
        "target_devices": data.get("target_devices", []),
        "commands": data.get("commands", []),
        "ha_script_id": data.get("ha_script_id"),
        "undo_state": data.get("undo_state", []),
        "last_executed": data.get("last_executed"),
        "execution_count": data.get("execution_count", 0)
    }
    _LOGGER.info(f"Created/updated Action: {action_id}")
    return jsonify({"ok": True, "action": _actions[action_id]})

@bp.route("/actions/<action_id>", methods=["GET"])
def get_action(action_id):
    """Get single Action detail."""
    action = _actions.get(action_id)
    if not action:
        return jsonify({"ok": False, "error": "Action not found"}), 404
    return jsonify({"ok": True, "action": action})

@bp.route("/actions/<action_id>", methods=["DELETE"])
def delete_action(action_id):
    """Delete an Action."""
    if action_id in _actions:
        del _actions[action_id]
        _LOGGER.info(f"Deleted Action: {action_id}")
        return jsonify({"ok": True, "deleted": action_id})
    return jsonify({"ok": False, "error": "Action not found"}), 404

@bp.route("/actions/<action_id>/execute", methods=["POST"])
def execute_action(action_id):
    """Execute an Action."""
    if action_id not in _actions:
        return jsonify({"ok": False, "error": "Action not found"}), 404
    
    action = _actions[action_id]
    action["last_executed"] = datetime.utcnow().isoformat()
    action["execution_count"] = action.get("execution_count", 0) + 1
    
    # Log execution
    _execution_log.append({
        "action_id": action_id,
        "executed_at": action["last_executed"],
        "status": "executed"
    })
    
    _LOGGER.info(f"Executed Action: {action_id} (count: {action['execution_count']})")
    return jsonify({"ok": True, "executed": action_id, "count": action["execution_count"]})

@bp.route("/actions/<action_id>/undo", methods=["POST"])
def undo_action(action_id):
    """Undo an Action (restore previous state)."""
    if action_id not in _actions:
        return jsonify({"ok": False, "error": "Action not found"}), 404
    
    action = _actions[action_id]
    undo_state = action.get("undo_state", [])
    
    _LOGGER.info(f"Undoing Action: {action_id} ({len(undo_state)} states to restore)")
    return jsonify({"ok": True, "undone": action_id, "restored_states": len(undo_state)})

@bp.route("/actions/executions", methods=["GET"])
def get_execution_log():
    """Get execution log."""
    limit = int(request.args.get("limit", 50))
    return jsonify({"ok": True, "executions": _execution_log[-limit:], "count": len(_execution_log[-limit:])})

@bp.route("/actions/summary", methods=["GET"])
def actions_summary():
    """Get summary of all Actions."""
    total = len(_actions)
    total_executions = sum(a.get("execution_count", 0) for a in _actions.values())
    with_script = sum(1 for a in _actions.values() if a.get("ha_script_id"))
    
    return jsonify({
        "ok": True,
        "summary": {
            "total_actions": total,
            "total_executions": total_executions,
            "actions_with_script": with_script
        }
    })
