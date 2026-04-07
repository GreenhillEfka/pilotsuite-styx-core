"""State Consistency API endpoints.

Provides endpoints for state versioning, conflict management, and partition reconciliation.

Endpoints:
  GET  /api/v1/state/consistency/status       — Manager status
  GET  /api/v1/state/consistency/state/:key   — Get versioned state
  PUT  /api/v1/state/consistency/state/:key   — Update state with optimistic locking
  GET  /api/v1/state/consistency/conflicts    — List pending conflicts
  POST /api/v1/state/consistency/conflicts/:key/resolve — Resolve a conflict
  POST /api/v1/state/consistency/partition/start  — Start partition tracking
  POST /api/v1/state/consistency/partition/end    — End partition and reconcile
  POST /api/v1/state/consistency/verify       — Verify consistency across nodes
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token

bp = Blueprint("state_consistency", __name__, url_prefix="/api/v1/state/consistency")
_LOGGER = logging.getLogger(__name__)


def _error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _json_object_from_request(*, allow_missing: bool = True) -> tuple[dict[str, Any], tuple[Any, int] | None]:
    data = request.get_json(silent=True)
    if data is None:
        return ({}, None) if allow_missing else ({}, _error("JSON object required", 400))
    if not isinstance(data, dict):
        return {}, _error("JSON object required", 400)
    return data, None


def _get_manager():
    """Get StateConsistencyManager from app services."""
    services = current_app.config.get("COPILOT_SERVICES", {})
    return services.get("state_consistency_manager")


@bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@bp.route("/status", methods=["GET"])
def get_status():
    """Get consistency manager status."""
    manager = _get_manager()
    if not manager:
        return _error("state_consistency_manager not initialized", 503)
    
    try:
        return jsonify({"ok": True, **manager.get_status()})
    except Exception as exc:
        _LOGGER.exception("Status read failed")
        return _error(str(exc), 500)


@bp.route("/state/<path:key>", methods=["GET"])
def get_state(key: str):
    """Get versioned state for a key."""
    manager = _get_manager()
    if not manager:
        return _error("state_consistency_manager not initialized", 503)
    
    try:
        state = manager.get_state(key)
        if state is None:
            return jsonify({"ok": False, "error": "not_found", "key": key}), 404
        return jsonify({"ok": True, "state": state.to_dict()})
    except Exception as exc:
        _LOGGER.exception("State read failed for %s", key)
        return _error(str(exc), 500)


@bp.route("/state/<path:key>", methods=["PUT"])
def update_state(key: str):
    """Update state with optimistic locking.
    
    JSON body:
      - data: Dict[str, Any] (required)
      - expected_version: int (optional, for optimistic locking)
    """
    manager = _get_manager()
    if not manager:
        return _error("state_consistency_manager not initialized", 503)
    
    data, error = _json_object_from_request(allow_missing=False)
    if error:
        return error
    
    new_data = data.get("data")
    if new_data is None or not isinstance(new_data, dict):
        return _error("data (object) required", 400)
    
    expected_version = data.get("expected_version")
    if expected_version is not None and not isinstance(expected_version, int):
        return _error("expected_version must be an integer", 400)
    
    try:
        success, state, error_msg = manager.update_state(key, new_data, expected_version)
        if not success:
            return jsonify({
                "ok": False,
                "error": "optimistic_lock_failed",
                "message": error_msg,
            }), 409
        
        return jsonify({"ok": True, "state": state.to_dict()})
    except Exception as exc:
        _LOGGER.exception("State update failed for %s", key)
        return _error(str(exc), 500)


@bp.route("/conflicts", methods=["GET"])
def list_conflicts():
    """List all pending conflicts."""
    manager = _get_manager()
    if not manager:
        return _error("state_consistency_manager not initialized", 503)
    
    try:
        conflicts = manager.get_conflicts()
        return jsonify({"ok": True, "conflicts": conflicts, "count": len(conflicts)})
    except Exception as exc:
        _LOGGER.exception("Conflict list failed")
        return _error(str(exc), 500)


@bp.route("/conflicts/<path:key>/resolve", methods=["POST"])
def resolve_conflict(key: str):
    """Resolve a detected conflict.
    
    JSON body (optional):
      - strategy: "last_write_wins" | "first_write_wins" | "merge" | "custom"
    """
    manager = _get_manager()
    if not manager:
        return _error("state_consistency_manager not initialized", 503)
    
    data, error = _json_object_from_request(allow_missing=True)
    if error:
        return error
    
    strategy = data.get("strategy")
    
    try:
        from copilot_core.state.consistency import ConflictStrategy
        
        strategy_enum = None
        if strategy:
            try:
                strategy_enum = ConflictStrategy(strategy)
            except ValueError:
                return _error(f"Unknown strategy: {strategy}", 400)
        
        resolved = manager.resolve_conflict(key, strategy_enum)
        if resolved is None:
            return jsonify({"ok": False, "error": "no_conflict_found", "key": key}), 404
        
        return jsonify({"ok": True, "resolved_state": resolved.to_dict()})
    except Exception as exc:
        _LOGGER.exception("Conflict resolution failed for %s", key)
        return _error(str(exc), 500)


@bp.route("/partition/start", methods=["POST"])
def start_partition():
    """Start tracking a network partition.
    
    JSON body:
      - peers: List[str] (required) — list of peer node IDs
    """
    manager = _get_manager()
    if not manager:
        return _error("state_consistency_manager not initialized", 503)
    
    data, error = _json_object_from_request(allow_missing=False)
    if error:
        return error
    
    peers = data.get("peers")
    if not peers or not isinstance(peers, list):
        return _error("peers (list of node IDs) required", 400)
    
    try:
        manager.start_partition(peers)
        return jsonify({"ok": True, "partition_started": True, "peers": peers})
    except Exception as exc:
        _LOGGER.exception("Partition start failed")
        return _error(str(exc), 500)


@bp.route("/partition/end", methods=["POST"])
def end_partition():
    """End network partition and reconcile states.
    
    JSON body:
      - peer_states: Dict[str, Dict[str, VersionedState]] (required)
        — mapping of node_id -> {state_key -> state_dict}
    """
    manager = _get_manager()
    if not manager:
        return _error("state_consistency_manager not initialized", 503)
    
    data, error = _json_object_from_request(allow_missing=False)
    if error:
        return error
    
    peer_states_raw = data.get("peer_states")
    if not peer_states_raw or not isinstance(peer_states_raw, dict):
        return _error("peer_states (object) required", 400)
    
    try:
        from copilot_core.state.consistency import VersionedState
        
        # Deserialize peer states
        peer_states = {}
        for node_id, states in peer_states_raw.items():
            if not isinstance(states, dict):
                return _error(f"peer_states[{node_id}] must be an object", 400)
            peer_states[node_id] = {
                key: VersionedState.from_dict(state_dict)
                for key, state_dict in states.items()
            }
        
        result = manager.end_partition(peer_states)
        return jsonify({"ok": True, "reconciliation": result.to_dict()})
    except Exception as exc:
        _LOGGER.exception("Partition reconciliation failed")
        return _error(str(exc), 500)


@bp.route("/verify", methods=["POST"])
def verify_consistency():
    """Verify consistency across nodes.
    
    JSON body:
      - peer_states: Dict[str, Dict[str, VersionedState]] (required)
      - level: "eventual" | "sequential" | "linearizable" (optional)
    """
    manager = _get_manager()
    if not manager:
        return _error("state_consistency_manager not initialized", 503)
    
    data, error = _json_object_from_request(allow_missing=False)
    if error:
        return error
    
    peer_states_raw = data.get("peer_states")
    if not peer_states_raw or not isinstance(peer_states_raw, dict):
        return _error("peer_states (object) required", 400)
    
    level = data.get("level")
    
    try:
        from copilot_core.state.consistency import VersionedState, ConsistencyLevel
        
        # Deserialize peer states
        peer_states = {}
        for node_id, states in peer_states_raw.items():
            if not isinstance(states, dict):
                return _error(f"peer_states[{node_id}] must be an object", 400)
            peer_states[node_id] = {
                key: VersionedState.from_dict(state_dict)
                for key, state_dict in states.items()
            }
        
        level_enum = None
        if level:
            try:
                level_enum = ConsistencyLevel(level)
            except ValueError:
                return _error(f"Unknown consistency level: {level}", 400)
        
        report = manager.verify_consistency(peer_states, level_enum)
        return jsonify({"ok": True, "verification": report})
    except Exception as exc:
        _LOGGER.exception("Consistency verification failed")
        return _error(str(exc), 500)
