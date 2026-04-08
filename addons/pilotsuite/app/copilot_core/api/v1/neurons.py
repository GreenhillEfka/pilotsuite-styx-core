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
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from copilot_core.neurons.manager import get_neuron_manager, NeuronManager, NeuralPipelineResult

_LOGGER = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("neurons", __name__, url_prefix="/neurons")

from copilot_core.api.security import validate_token as _validate_token


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
        
        # Apply state overrides
        if "states" in body:
            manager.update_states(body["states"])
        
        # Apply context overrides
        if "context" in body:
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
    
    JSON body:
        {
            "states": {...}  # Entity ID -> state dict
        }
    
    Returns:
        {"success": true, "data": {"updated": int}}
    """
    try:
        body = request.get_json()
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
        body = request.get_json()
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
    
    Returns:
        Full evaluation result with dominant mood
    """
    try:
        manager = get_neuron_manager()
        
        body = request.get_json(silent=True) or {}
        
        if "states" in body:
            manager.update_states(body["states"])
        if "context" in body:
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
    """Get mood history.
    
    Query params:
        limit: Number of entries (default 10)
    
    Returns:
        {
            "success": true,
            "data": {
                "history": [...],
                "count": int
            }
        }
    """
    try:
        manager = get_neuron_manager()
        limit = int(request.args.get("limit", "10"))
        
        history = manager._mood_history[-limit:]
        
        return jsonify({
            "success": True,
            "data": {
                "history": history,
                "count": len(history)
            }
        })
    except Exception as e:
        _LOGGER.error("Error getting mood history: %s", e)
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


__all__ = ["bp"]