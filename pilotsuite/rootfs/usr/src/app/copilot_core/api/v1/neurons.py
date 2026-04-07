"""Neuron API endpoints for PilotSuite.

Exposes the neural system via REST API for Home Assistant integration.

Endpoints:
- GET /api/v1/neurons - List all neurons
- GET /api/v1/neurons/<id> - Get neuron state
- POST /api/v1/neurons/evaluate - Run full evaluation
- GET /api/v1/mood - Get current mood
- POST /api/v1/mood/evaluate - Force mood evaluation
- GET /api/v1/suggestions - Get current suggestions
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from copilot_core.neurons.manager import get_neuron_manager, NeuronManager, NeuralPipelineResult
from copilot_core.neurons.mood_history import get_mood_history_store

_LOGGER = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("neurons", __name__, url_prefix="/neurons")
neurons_bp = bp

from copilot_core.api.security import validate_token as _validate_token, require_admin_token
from copilot_core.api.v1 import neuron_graph as neuron_graph_module
from copilot_core.api.v1.websocket_neuron import get_neuron_ws_handler
from copilot_core.api.v1.neuron_graph import get_neuron_connections, find_paths

# Neuron ID validation: lowercase letters, underscores, dots only
# Format: prefix.name (e.g., "context.presence", "mood.focus")
NEURON_ID_PATTERN = re.compile(r'^[a-z_]+(\.[a-z_]+)?$')
NEURON_ID_MAX_LENGTH = 100

# Server-side cap for mood history queries
MOOD_HISTORY_MAX_LIMIT = 100


def _require_admin_mutation(action: str, error_message: str):
    """Require admin authentication for state/config mutations."""
    _LOGGER.info("%s attempted from %s", action, request.remote_addr)
    if require_admin_token(request):
        return None

    _LOGGER.warning("Unauthorized %s attempt from %s", action, request.remote_addr)
    return jsonify({
        "success": False,
        "error": error_message,
    }), 403


def _resolve_neuron(manager: NeuronManager, neuron_id: str):
    """Resolve a neuron by full ID or short name fallback."""
    return manager.get_neuron(neuron_id) or manager.get_neuron(
        neuron_id.split(".")[-1] if "." in neuron_id else neuron_id
    )


def _normalize_neuron_config_patch(patch: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Validate and normalize a neuron config patch before mutating state."""
    normalized: dict[str, Any] = {}
    changed: list[str] = []

    for key in ("threshold", "decay_rate", "smoothing_factor"):
        if key in patch:
            val = float(patch[key])
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{key} must be between 0.0 and 1.0")
            normalized[key] = val
            changed.append(key)

    if "weights" in patch:
        weights = patch["weights"]
        if not isinstance(weights, dict):
            raise ValueError("weights must be an object")
        normalized["weights"] = {str(k): float(v) for k, v in weights.items()}
        changed.append("weights")

    if "enabled" in patch:
        normalized["enabled"] = bool(patch["enabled"])
        changed.append("enabled")

    return normalized, changed


def _apply_neuron_config_patch(config: Any, patch: dict[str, Any]) -> list[str]:
    """Apply a validated neuron config patch."""
    normalized, changed = _normalize_neuron_config_patch(patch)

    for key, value in normalized.items():
        if key == "weights":
            config.weights.update(value)
        else:
            setattr(config, key, value)

    return changed


def validate_neuron_id(neuron_id: str) -> bool:
    """Validate neuron ID format.
    
    Args:
        neuron_id: Neuron identifier to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not neuron_id or len(neuron_id) > NEURON_ID_MAX_LENGTH:
        return False
    return bool(NEURON_ID_PATTERN.match(neuron_id))


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


# =============================================================================
# Neuron Endpoints
# =============================================================================

@bp.route("", methods=["GET"])
def list_neurons():
    """List all neurons.
    
    Returns:
        {
            "success": true,
            "data": {
                "context": {...},
                "state": {...},
                "mood": {...},
                "total_count": int
            }
        }
    """
    try:
        manager = get_neuron_manager()
        summary = manager.get_neuron_summary()
        
        return jsonify({
            "success": True,
            "data": summary
        })
    except Exception as e:
        _LOGGER.error("Error listing neurons: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/<neuron_id>", methods=["GET"])
def get_neuron(neuron_id: str):
    """Get a specific neuron's state.
    
    Args:
        neuron_id: Neuron name (e.g., "context.presence", "state.energy_level")
    
    Returns:
        {
            "success": true,
            "data": {
                "name": str,
                "type": str,
                "state": {...},
                "config": {...}
            }
        }
    """
    # Validate neuron ID format
    if not validate_neuron_id(neuron_id):
        return jsonify({
            "success": False,
            "error": "Invalid neuron_id format. Must be lowercase letters, underscores, or dots."
        }), 400
    
    try:
        manager = get_neuron_manager()
        
        neuron = manager.get_neuron(neuron_id)
        if not neuron:
            # Try without prefix
            neuron = manager.get_neuron(neuron_id.split(".")[-1] if "." in neuron_id else neuron_id)
        
        if not neuron:
            return jsonify({
                "success": False,
                "error": f"Neuron not found: {neuron_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": neuron.to_dict()
        })
    except Exception as e:
        _LOGGER.error("Error getting neuron %s: %s", neuron_id, e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/evaluate", methods=["POST"])
def evaluate_neurons():
    """Run full neural pipeline evaluation.
    
    Optional JSON body:
        {
            "states": {...},        # Override HA states
            "context": {...},       # Additional context
            "trigger": "manual"     # Trigger source
        }
    
    State/context overrides require admin-level authentication.
    
    Returns:
        {
            "success": true,
            "data": {
                "timestamp": str,
                "context_values": {...},
                "state_values": {...},
                "mood_values": {...},
                "dominant_mood": str,
                "mood_confidence": float,
                "suggestions": [...]
            }
        }
    """
    try:
        manager = get_neuron_manager()
        
        # Get optional overrides from request body
        body = request.get_json(silent=True) or {}
        
        # Apply state overrides - requires admin token for state manipulation
        if "states" in body:
            _LOGGER.info("Evaluate state override attempted from %s", request.remote_addr)
            if not require_admin_token(request):
                _LOGGER.warning("Unauthorized evaluate state override attempt from %s", request.remote_addr)
                return jsonify({
                    "success": False,
                    "error": "Admin token required for state overrides"
                }), 403
            manager.update_states(body["states"])

        # Apply context overrides - requires admin token
        if "context" in body:
            _LOGGER.info("Evaluate context override attempted from %s", request.remote_addr)
            if not require_admin_token(request):
                _LOGGER.warning("Unauthorized evaluate context override attempt from %s", request.remote_addr)
                return jsonify({
                    "success": False,
                    "error": "Admin token required for context overrides"
                }), 403
            manager.set_context(body["context"])
        
        # Run evaluation
        result = manager.evaluate()
        
        return jsonify({
            "success": True,
            "data": {
                "timestamp": result.timestamp,
                "context_values": result.context_values,
                "state_values": result.state_values,
                "mood_values": result.mood_values,
                "dominant_mood": result.dominant_mood,
                "mood_confidence": result.mood_confidence,
                "suggestions": result.suggestions,
                "neuron_count": len(result.neuron_states),
            }
        })
    except Exception as e:
        _LOGGER.error("Error evaluating neurons: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/update", methods=["POST"])
def update_neuron_states():
    """Update HA states without full evaluation.
    
    Requires admin-level authentication for state manipulation.
    
    JSON body:
        {
            "states": {...}  # Entity ID -> state dict
        }
    
    Returns:
        {"success": true, "data": {"updated": int}}
    """
    try:
        admin_error = _require_admin_mutation(
            "neuron state update",
            "Admin token required for state updates",
        )
        if admin_error:
            return admin_error

        body = request.get_json(silent=True)
        if not body:
            return jsonify({
                "success": False,
                "error": "No JSON body provided"
            }), 400
        
        states = body.get("states", {})
        
        if not states:
            return jsonify({
                "success": False,
                "error": "No states provided"
            }), 400
        
        manager = get_neuron_manager()
        manager.update_states(states)
        
        return jsonify({
            "success": True,
            "data": {
                "updated": len(states),
                "total_states": len(manager._ha_states)
            }
        })
    except Exception as e:
        _LOGGER.error("Error updating states: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/configure", methods=["POST"])
def configure_neurons():
    """Configure neurons from HA.
    
    JSON body:
        {
            "states": {...},      # HA states
            "config": {...}       # Neuron configuration
        }
    
    Returns:
        {"success": true, "data": {...}}
    """
    try:
        admin_error = _require_admin_mutation(
            "neuron configure",
            "Admin token required for neuron configuration",
        )
        if admin_error:
            return admin_error

        body = request.get_json(silent=True)
        if not body:
            return jsonify({
                "success": False,
                "error": "No JSON body provided"
            }), 400
        
        states = body.get("states", {})
        config = body.get("config", {})
        
        manager = get_neuron_manager()
        manager.configure_from_ha(states, config)
        
        return jsonify({
            "success": True,
            "data": manager.to_dict()
        })
    except Exception as e:
        _LOGGER.error("Error configuring neurons: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Mood Endpoints (under /neurons/mood)
# =============================================================================

@bp.route("/mood", methods=["GET"])
def get_mood():
    """Get current mood state.
    
    Returns:
        {
            "success": true,
            "data": {
                "mood": str,
                "confidence": float,
                "mood_values": {...},
                "timestamp": str
            }
        }
    """
    try:
        manager = get_neuron_manager()
        summary = manager.get_mood_summary()
        
        return jsonify({
            "success": True,
            "data": summary
        })
    except Exception as e:
        _LOGGER.error("Error getting mood: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/mood/evaluate", methods=["POST"])
def evaluate_mood():
    """Force mood evaluation.

    Optional JSON body:
        {
            "states": {...},
            "context": {...}
        }

    State/context overrides require admin-level authentication.

    Returns:
        Full evaluation result with dominant mood
    """
    try:
        manager = get_neuron_manager()

        body = request.get_json(silent=True) or {}

        # Apply state overrides - requires admin token for state manipulation
        if "states" in body:
            _LOGGER.info("Mood evaluate state override attempted from %s", request.remote_addr)
            if not require_admin_token(request):
                _LOGGER.warning("Unauthorized mood state override attempt from %s", request.remote_addr)
                return jsonify({
                    "success": False,
                    "error": "Admin token required for state overrides"
                }), 403
            manager.update_states(body["states"])

        # Apply context overrides - requires admin token
        if "context" in body:
            _LOGGER.info("Mood evaluate context override attempted from %s", request.remote_addr)
            if not require_admin_token(request):
                _LOGGER.warning("Unauthorized mood context override attempt from %s", request.remote_addr)
                return jsonify({
                    "success": False,
                    "error": "Admin token required for context overrides"
                }), 403
            manager.set_context(body["context"])
        
        result = manager.evaluate()
        
        return jsonify({
            "success": True,
            "data": {
                "mood": result.dominant_mood,
                "confidence": result.mood_confidence,
                "mood_values": result.mood_values,
                "timestamp": result.timestamp,
                "suggestions": result.suggestions,
            }
        })
    except Exception as e:
        _LOGGER.error("Error evaluating mood: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/mood/history", methods=["GET"])
def get_mood_history():
    """Get mood history from persistent SQLite store.

    Query params:
        hours: Look-back window in hours (default 24, max 168 = 7 days)

    Returns:
        {
            "success": true,
            "data": {
                "history": [...],
                "count": int,
                "hours": int
            }
        }
    """
    try:
        try:
            hours = int(request.args.get("hours", "24"))
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Invalid 'hours' parameter. Must be a positive integer."
            }), 400
        if hours < 1:
            hours = 1
        hours = min(hours, 168)  # Cap at 7 days

        store = get_mood_history_store()
        history = store.get_recent(hours=hours)

        return jsonify({
            "success": True,
            "data": {
                "history": history,
                "count": len(history),
                "hours": hours,
            }
        })
    except Exception as e:
        _LOGGER.error("Error getting mood history: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/mood/trend", methods=["GET"])
def get_mood_trend():
    """Get mood distribution/trend over a time period.

    Query params:
        hours: Look-back window in hours (default 24, max 168 = 7 days)

    Returns:
        {
            "success": true,
            "data": {
                "count": int,
                "distribution": {"relax": 5, "focus": 3, ...},
                "dominant_mood": str,
                "avg_confidence": float,
                "period_hours": int
            }
        }
    """
    try:
        try:
            hours = int(request.args.get("hours", "24"))
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Invalid 'hours' parameter. Must be a positive integer."
            }), 400
        if hours < 1:
            hours = 1
        hours = min(hours, 168)

        store = get_mood_history_store()
        trend = store.get_trend(hours=hours)

        return jsonify({
            "success": True,
            "data": trend,
        })
    except Exception as e:
        _LOGGER.error("Error getting mood trend: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/suggestions", methods=["GET"])
def get_suggestions():
    """Get current suggestions.
    
    Returns suggestions from last evaluation.
    """
    try:
        manager = get_neuron_manager()
        
        if not manager._last_result:
            result = manager.evaluate()
        else:
            result = manager._last_result
        
        return jsonify({
            "success": True,
            "data": {
                "suggestions": result.suggestions,
                "mood": result.dominant_mood,
                "timestamp": result.timestamp,
            }
        })
    except Exception as e:
        _LOGGER.error("Error getting suggestions: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Neuron Graph Endpoints (NEW)
# =============================================================================

@bp.route("/graph", methods=["GET"])
def get_neuron_graph_endpoint():
    """Get complete neuron graph (nodes + edges).
    
    Returns:
        {
            "success": true,
            "data": {
                "nodes": [...],
                "edges": [...],
                "metadata": {...}
            }
        }
    """
    try:
        graph = neuron_graph_module.get_neuron_graph()
        
        return jsonify({
            "success": True,
            "data": graph.to_dict()
        })
    except Exception as e:
        _LOGGER.error("Error getting neuron graph: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/<neuron_id>/stats", methods=["GET"])
def get_neuron_stats(neuron_id: str):
    """Get neuron statistics (fire-rate, confidence, metrics).
    
    Args:
        neuron_id: Neuron ID (e.g., "context.presence", "mood.focus")
    
    Returns:
        {
            "success": true,
            "data": {
                "neuron_id": str,
                "name": str,
                "type": str,
                "layer": int,
                "active": bool,
                "value": float,
                "metrics": {
                    "fire_rate": float,
                    "confidence": float,
                    "avg_value": float,
                    "trend": str,
                    "last_fire_time": str
                },
                "connections": {
                    "incoming": int,
                    "outgoing": int
                }
            }
        }
    """
    # Validate neuron ID format
    if not validate_neuron_id(neuron_id):
        return jsonify({
            "success": False,
            "error": "Invalid neuron_id format. Must be lowercase letters, underscores, or dots."
        }), 400
    
    try:
        graph = neuron_graph_module.get_neuron_graph()
        node = graph.get_node(neuron_id)
        
        if not node:
            # Try without prefix
            for prefix in ["context", "state", "mood"]:
                full_id = f"{prefix}.{neuron_id}"
                node = graph.get_node(full_id)
                if node:
                    neuron_id = full_id
                    break
        
        if not node:
            return jsonify({
                "success": False,
                "error": f"Neuron not found: {neuron_id}"
            }), 404
        
        # Get connection counts
        incoming = len(graph.get_incoming_edges(neuron_id))
        outgoing = len(graph.get_outgoing_edges(neuron_id))
        
        return jsonify({
            "success": True,
            "data": {
                "neuron_id": neuron_id,
                "name": node.name,
                "type": node.neuron_type,
                "layer": node.layer,
                "active": node.active,
                "value": round(node.value, 3),
                "metrics": node.metrics.to_dict(),
                "connections": {
                    "incoming": incoming,
                    "outgoing": outgoing
                }
            }
        })
    except Exception as e:
        _LOGGER.error("Error getting neuron stats for %s: %s", neuron_id, e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/graph/stats", methods=["GET"])
def get_graph_stats():
    """Get overall graph statistics.
    
    Returns:
        {
            "success": true,
            "data": {
                "total_nodes": int,
                "active_nodes": int,
                "total_edges": int,
                "avg_fire_rate": float,
                "avg_confidence": float,
                "layers": {...}
            }
        }
    """
    try:
        graph = neuron_graph_module.get_neuron_graph()
        
        return jsonify({
            "success": True,
            "data": graph.get_stats()
        })
    except Exception as e:
        _LOGGER.error("Error getting graph stats: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/connections", methods=["GET"])
def get_connections():
    """Get connections between neurons.
    
    Query params:
        node_id: Optional node ID to filter connections for a specific node
    
    Returns:
        {
            "success": true,
            "data": {
                "node_id": str (if filtered),
                "node_name": str (if filtered),
                "incoming": [...],
                "outgoing": [...],
                "total_connections": int
            }
        }
    """
    try:
        node_id = request.args.get("node_id")
        
        result = get_neuron_connections(node_id)
        
        if "error" in result:
            return jsonify({
                "success": False,
                "error": result["error"]
            }), 404
        
        return jsonify({
            "success": True,
            "data": result
        })
    except Exception as e:
        _LOGGER.error("Error getting connections: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/paths", methods=["GET"])
def get_paths():
    """Find paths between two neurons.
    
    Query params:
        from: Starting node ID (required)
        to: Ending node ID (required)
        max_depth: Maximum path length (default: 5, max: 10)
    
    Returns:
        {
            "success": true,
            "data": {
                "from": str,
                "to": str,
                "paths": [
                    {
                        "path": [...],
                        "length": int,
                        "nodes": [...]
                    }
                ],
                "path_count": int
            }
        }
    """
    try:
        from_id = request.args.get("from")
        to_id = request.args.get("to")
        
        if not from_id or not to_id:
            return jsonify({
                "success": False,
                "error": "Missing required parameters: 'from' and 'to'"
            }), 400
        
        try:
            max_depth = int(request.args.get("max_depth", "5"))
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Invalid 'max_depth' parameter. Must be a positive integer."
            }), 400
        
        # Cap max_depth to prevent excessive computation
        max_depth = max(1, min(max_depth, 10))
        
        paths = find_paths(from_id, to_id, max_depth)
        
        return jsonify({
            "success": True,
            "data": {
                "from": from_id,
                "to": to_id,
                "paths": paths,
                "path_count": len(paths),
                "max_depth": max_depth
            }
        })
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
    except Exception as e:
        _LOGGER.error("Error finding paths: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Neuron Configuration Editing Endpoints (Iteration 2)
# =============================================================================

@bp.route("/<neuron_id>/config", methods=["PATCH"])
def update_neuron_config(neuron_id: str):
    """Update a neuron's configuration parameters.

    JSON body (all fields optional):
        {
            "threshold": 0.6,          # 0.0-1.0
            "decay_rate": 0.15,        # 0.0-1.0
            "smoothing_factor": 0.25,  # 0.0-1.0
            "weights": {"energy": 0.5},
            "enabled": true
        }
    """
    if not validate_neuron_id(neuron_id):
        return jsonify({"success": False, "error": "Invalid neuron_id format"}), 400

    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"success": False, "error": "Empty body"}), 400

    admin_error = _require_admin_mutation(
        "neuron config update",
        "Admin token required for neuron configuration updates",
    )
    if admin_error:
        return admin_error

    try:
        manager = get_neuron_manager()
        neuron = _resolve_neuron(manager, neuron_id)
        if not neuron:
            return jsonify({"success": False, "error": f"Neuron not found: {neuron_id}"}), 404

        config = neuron.config
        changed = _apply_neuron_config_patch(config, body)

        # Persist if manager supports it
        if hasattr(manager, "persist_neuron_config"):
            manager.persist_neuron_config(neuron_id)

        _LOGGER.info("Updated neuron %s config: %s", neuron_id, changed)

        return jsonify({
            "success": True,
            "data": {
                "neuron_id": neuron_id,
                "changed": changed,
                "config": config.to_dict(),
            },
        })
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Invalid value: {e}"}), 400
    except Exception as e:
        _LOGGER.error("Error updating neuron %s config: %s", neuron_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/<neuron_id>/enable", methods=["POST"])
def enable_neuron(neuron_id: str):
    """Enable a neuron."""
    if not validate_neuron_id(neuron_id):
        return jsonify({"success": False, "error": "Invalid neuron_id format"}), 400

    admin_error = _require_admin_mutation(
        "neuron enable",
        "Admin token required for neuron enable",
    )
    if admin_error:
        return admin_error

    try:
        manager = get_neuron_manager()
        neuron = _resolve_neuron(manager, neuron_id)
        if not neuron:
            return jsonify({"success": False, "error": f"Neuron not found: {neuron_id}"}), 404

        neuron.config.enabled = True
        if hasattr(manager, "persist_neuron_config"):
            manager.persist_neuron_config(neuron_id)

        return jsonify({"success": True, "data": {"neuron_id": neuron_id, "enabled": True}})
    except Exception as e:
        _LOGGER.error("Error enabling neuron %s: %s", neuron_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/<neuron_id>/disable", methods=["POST"])
def disable_neuron(neuron_id: str):
    """Disable a neuron."""
    if not validate_neuron_id(neuron_id):
        return jsonify({"success": False, "error": "Invalid neuron_id format"}), 400

    admin_error = _require_admin_mutation(
        "neuron disable",
        "Admin token required for neuron disable",
    )
    if admin_error:
        return admin_error

    try:
        manager = get_neuron_manager()
        neuron = _resolve_neuron(manager, neuron_id)
        if not neuron:
            return jsonify({"success": False, "error": f"Neuron not found: {neuron_id}"}), 404

        neuron.config.enabled = False
        if hasattr(manager, "persist_neuron_config"):
            manager.persist_neuron_config(neuron_id)

        return jsonify({"success": True, "data": {"neuron_id": neuron_id, "enabled": False}})
    except Exception as e:
        _LOGGER.error("Error disabling neuron %s: %s", neuron_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/batch-configure", methods=["POST"])
def batch_configure_neurons():
    """Configure multiple neurons in one request.

    JSON body:
        {
            "neurons": {
                "context.presence": {"threshold": 0.7},
                "mood.focus": {"enabled": false, "decay_rate": 0.2}
            }
        }
    """
    body = request.get_json(silent=True) or {}
    configs = body.get("neurons", {})
    if not configs or not isinstance(configs, dict):
        return jsonify({"success": False, "error": "Missing 'neurons' dict"}), 400

    admin_error = _require_admin_mutation(
        "neuron batch configure",
        "Admin token required for neuron batch configuration",
    )
    if admin_error:
        return admin_error

    manager = get_neuron_manager()
    results = {}
    errors = {}

    for nid, patch in configs.items():
        if not validate_neuron_id(nid):
            errors[nid] = "Invalid neuron_id format"
            continue

        neuron = _resolve_neuron(manager, nid)
        if not neuron:
            errors[nid] = "Neuron not found"
            continue

        try:
            cfg = neuron.config
            _apply_neuron_config_patch(cfg, patch)
            results[nid] = cfg.to_dict()
        except (ValueError, TypeError) as e:
            errors[nid] = str(e)

    if results and hasattr(manager, "persist_all_neuron_configs"):
        manager.persist_all_neuron_configs()

    return jsonify({
        "success": len(errors) == 0,
        "data": {"updated": results, "errors": errors},
    })


__all__ = ["bp"]

# ── SLICE 131: Neuron-View Expansion ─────────────────────────────────

@bp.get("/activity-stream")
def neuron_activity_stream():
    """Real-time neuron firing activity.
    
    Query params:
    - limit: Max recent activations (default 50)
    - neuron_id: Filter by specific neuron
    - timeframe: Minutes to look back (default 5)
    """
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    neuron_id = request.args.get("neuron_id")
    
    try:
        timeframe = int(request.args.get("timeframe", "5"))
    except (ValueError, TypeError):
        timeframe = 5
    
    limit = max(1, min(limit, 500))
    timeframe = max(1, min(timeframe, 60))
    
    manager = get_neuron_manager()
    activity = manager.get_recent_activations(
        limit=limit,
        neuron_id=neuron_id,
        timeframe_minutes=timeframe
    )
    
    return jsonify({
        "ok": True,
        "activity": activity,
        "count": len(activity),
        "timeframe_minutes": timeframe
    })


@bp.get("/clusters")
def neuron_clusters():
    """Get neuron clusters by function/context.
    
    Query params:
    - group_by: domain|category|activation_rate (default: domain)
    - min_size: Minimum cluster size (default: 1)
    """
    group_by = request.args.get("group_by", "domain")
    
    try:
        min_size = int(request.args.get("min_size", "1"))
    except (ValueError, TypeError):
        min_size = 1
    
    manager = get_neuron_manager()
    clusters = manager.get_neuron_clusters(group_by=group_by, min_size=min_size)
    
    return jsonify({
        "ok": True,
        "group_by": group_by,
        "clusters": clusters,
        "cluster_count": len(clusters),
        "total_neurons": sum(len(c.get("neurons", [])) for c in clusters)
    })


@bp.get("/health")
def neuron_health():
    """Neuron health metrics: activation rates, latency, errors.
    
    Query params:
    - neuron_id: Specific neuron (optional)
    - timeframe: Hours to analyze (default 24)
    """
    neuron_id = request.args.get("neuron_id")
    
    try:
        timeframe = int(request.args.get("timeframe", "24"))
    except (ValueError, TypeError):
        timeframe = 24
    
    timeframe = max(1, min(timeframe, 168))
    
    manager = get_neuron_manager()
    health = manager.get_neuron_health(
        neuron_id=neuron_id,
        timeframe_hours=timeframe
    )
    
    return jsonify({
        "ok": True,
        "timeframe_hours": timeframe,
        "health": health
    })
