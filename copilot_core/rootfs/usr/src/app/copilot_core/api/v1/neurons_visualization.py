"""Neuron Visualization API - Enhanced endpoints for PilotSuite neural system.

Provides detailed neuron state visualization and brain pipeline inspection.

Endpoints:
    GET /api/v1/neurons/state       - Alle 14 Neuronen-States
    GET /api/v1/neurons/{id}/fire   - Einzelnes Neuron (Live-Status)
    GET /api/v1/brain/pipeline      - Kommunikations-Pipeline
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.neurons.manager import get_neuron_manager
from copilot_core.neurons.base import NeuronType, MoodType, BaseNeuron
from copilot_core.api.security import validate_token

_LOGGER = logging.getLogger(__name__)

# Create blueprint with relative prefix (nested under /api/v1)
bp = Blueprint("neurons_viz", __name__, url_prefix="/neurons")


@bp.before_request
def _require_auth():
    """Require authentication for all neuron visualization endpoints."""
    if not validate_token(request):
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required"
        }), 401


# =============================================================================
# Neuron State Endpoints
# =============================================================================

@bp.route("/state", methods=["GET"])
def get_all_neurons_state():
    """Get all 14 neuron states.
    
    Returns comprehensive state information for all neurons in the system.
    
    Returns:
        {
            "success": true,
            "data": {
                "timestamp": str,
                "total_neurons": int,
                "active_count": int,
                "neurons": {
                    "context": [...],
                    "state": [...],
                    "mood": [...]
                },
                "summary": {
                    "context_values": {...},
                    "state_values": {...},
                    "mood_values": {...}
                }
            }
        }
    """
    try:
        manager = get_neuron_manager()
        now = datetime.now(timezone.utc).isoformat()
        
        # Get all neurons grouped by type
        all_neurons = []
        active_count = 0
        
        # Collect context neurons
        context_neurons = []
        for name, neuron in manager._context_neurons.items():
            neuron_data = neuron.to_dict()
            neuron_data["name"] = name
            context_neurons.append(neuron_data)
            if neuron.is_active:
                active_count += 1
        
        # Collect state neurons
        state_neurons = []
        for name, neuron in manager._state_neurons.items():
            neuron_data = neuron.to_dict()
            neuron_data["name"] = name
            state_neurons.append(neuron_data)
            if neuron.is_active:
                active_count += 1
        
        # Collect mood neurons
        mood_neurons = []
        for name, neuron in manager._mood_neurons.items():
            neuron_data = neuron.to_dict()
            neuron_data["name"] = name
            mood_neurons.append(neuron_data)
            if neuron.is_active:
                active_count += 1
        
        all_neurons = context_neurons + state_neurons + mood_neurons
        
        # Get current values summary
        summary = manager.get_neuron_summary()
        
        return jsonify({
            "success": True,
            "data": {
                "timestamp": now,
                "total_neurons": len(all_neurons),
                "active_count": active_count,
                "neurons": {
                    "context": context_neurons,
                    "state": state_neurons,
                    "mood": mood_neurons
                },
                "summary": {
                    "context_values": summary.get("context", {}),
                    "state_values": summary.get("state", {}),
                    "mood_values": summary.get("mood", {})
                }
            }
        })
    
    except Exception as e:
        _LOGGER.error("Error getting all neuron states: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/<neuron_id>/fire", methods=["GET"])
def get_neuron_fire_status(neuron_id: str):
    """Get live fire status for a single neuron.
    
    Args:
        neuron_id: Neuron name or ID (e.g., "presence", "context.presence", "mood.relax")
    
    Returns:
        {
            "success": true,
            "data": {
                "name": str,
                "type": str,
                "firing": bool,
                "state": {
                    "active": bool,
                    "value": float,
                    "confidence": float,
                    "last_update": str,
                    "last_trigger": str,
                    "trigger_count": int
                },
                "config": {
                    "threshold": float,
                    "decay_rate": float,
                    "smoothing_factor": float,
                    "entity_ids": [...]
                },
                "live_metrics": {
                    "firing_rate": float,
                    "avg_value": float,
                    "trend": str  # "increasing", "decreasing", "stable"
                }
            }
        }
    """
    try:
        manager = get_neuron_manager()
        
        # Try to find neuron by various ID formats
        neuron = None
        
        # Direct lookup
        if neuron_id in manager._context_neurons:
            neuron = manager._context_neurons[neuron_id]
        elif neuron_id in manager._state_neurons:
            neuron = manager._state_neurons[neuron_id]
        elif neuron_id in manager._mood_neurons:
            neuron = manager._mood_neurons[neuron_id]
        else:
            # Try without prefix
            base_id = neuron_id.split(".")[-1] if "." in neuron_id else neuron_id
            
            # Search in all neuron types
            for neuron_dict in [manager._context_neurons, manager._state_neurons, manager._mood_neurons]:
                for name, n in neuron_dict.items():
                    if name == base_id or name.endswith(f".{base_id}"):
                        neuron = n
                        break
                if neuron:
                    break
        
        if not neuron:
            return jsonify({
                "success": False,
                "error": f"Neuron not found: {neuron_id}"
            }), 404
        
        # Calculate live metrics
        live_metrics = _calculate_live_metrics(neuron)
        
        return jsonify({
            "success": True,
            "data": {
                "name": neuron.name,
                "type": neuron.neuron_type.value,
                "firing": neuron.is_active,
                "state": neuron.state.to_dict(),
                "config": neuron.config.to_dict(),
                "live_metrics": live_metrics
            }
        })
    
    except Exception as e:
        _LOGGER.error("Error getting neuron fire status for %s: %s", neuron_id, e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Brain Pipeline Endpoint
# =============================================================================

@bp.route("/brain/pipeline", methods=["GET"])
def get_brain_pipeline():
    """Get the communication pipeline status.
    
    Returns the current state of the neural pipeline including:
    - Pipeline stages and their status
    - Data flow between stages
    - Current throughput and latency
    - Active connections
    
    Returns:
        {
            "success": true,
            "data": {
                "pipeline": {
                    "stages": [...],
                    "status": str,
                    "last_execution": str,
                    "execution_count": int
                },
                "data_flow": {
                    "input_rate": float,
                    "output_rate": float,
                    "avg_latency_ms": float
                },
                "connections": {
                    "context_to_state": [...],
                    "state_to_mood": [...],
                    "mood_to_suggestions": [...]
                },
                "current_state": {
                    "context_active": int,
                    "state_active": int,
                    "mood_active": int,
                    "dominant_mood": str
                }
            }
        }
    """
    try:
        manager = get_neuron_manager()
        now = datetime.now(timezone.utc)
        
        # Build pipeline stages
        stages = [
            {
                "name": "Context Evaluation",
                "type": "input",
                "neuron_count": len(manager._context_neurons),
                "active_count": sum(1 for n in manager._context_neurons.values() if n.is_active),
                "status": "active" if manager._context_neurons else "inactive",
                "description": "Evaluates objective environmental factors"
            },
            {
                "name": "State Smoothing",
                "type": "processing",
                "neuron_count": len(manager._state_neurons),
                "active_count": sum(1 for n in manager._state_neurons.values() if n.is_active),
                "status": "active" if manager._state_neurons else "inactive",
                "description": "Applies EMA smoothing and inertia"
            },
            {
                "name": "Mood Aggregation",
                "type": "aggregation",
                "neuron_count": len(manager._mood_neurons),
                "active_count": sum(1 for n in manager._mood_neurons.values() if n.is_active),
                "status": "active" if manager._mood_neurons else "inactive",
                "description": "Aggregates into mood values"
            },
            {
                "name": "Suggestion Generation",
                "type": "output",
                "neuron_count": 0,
                "active_count": 0,
                "status": "active",
                "description": "Generates actionable suggestions"
            }
        ]
        
        # Determine overall pipeline status
        pipeline_status = "active" if any(s["active_count"] > 0 for s in stages) else "idle"
        
        # Get last result info
        last_result = manager._last_result
        last_execution = last_result.timestamp if last_result else None
        execution_count = manager._evaluation_count
        
        # Build connection map (simplified synapse representation)
        connections = {
            "context_to_state": [
                {"from": name, "to": "state_neurons", "weight": 0.5}
                for name in list(manager._context_neurons.keys())[:5]
            ],
            "state_to_mood": [
                {"from": name, "to": "mood_neurons", "weight": 0.7}
                for name in list(manager._state_neurons.keys())[:5]
            ],
            "mood_to_suggestions": [
                {"from": name, "to": "suggestions", "weight": 1.0}
                for name in list(manager._mood_neurons.keys())[:5]
            ]
        }
        
        # Current state summary
        current_state = {
            "context_active": sum(1 for n in manager._context_neurons.values() if n.is_active),
            "state_active": sum(1 for n in manager._state_neurons.values() if n.is_active),
            "mood_active": sum(1 for n in manager._mood_neurons.values() if n.is_active),
            "dominant_mood": last_result.dominant_mood if last_result else "unknown"
        }
        
        # Data flow metrics (simulated based on evaluation history)
        data_flow = {
            "input_rate": len(manager._ha_states),
            "output_rate": len(last_result.suggestions) if last_result else 0,
            "avg_latency_ms": _calculate_avg_latency(manager)
        }
        
        return jsonify({
            "success": True,
            "data": {
                "pipeline": {
                    "stages": stages,
                    "status": pipeline_status,
                    "last_execution": last_execution,
                    "execution_count": execution_count
                },
                "data_flow": data_flow,
                "connections": connections,
                "current_state": current_state
            }
        })
    
    except Exception as e:
        _LOGGER.error("Error getting brain pipeline: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Helper Functions
# =============================================================================

def _calculate_live_metrics(neuron: BaseNeuron) -> Dict[str, Any]:
    """Calculate live metrics for a neuron.
    
    Args:
        neuron: The neuron instance
    
    Returns:
        Dictionary with live metrics
    """
    # Firing rate: triggers per minute (based on trigger count and age)
    state = neuron.state
    firing_rate = 0.0
    
    if state.last_trigger and state.trigger_count > 0:
        try:
            last_trigger_time = datetime.fromisoformat(state.last_trigger.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            age_minutes = (now - last_trigger_time).total_seconds() / 60
            
            if age_minutes > 0:
                firing_rate = state.trigger_count / age_minutes
        except Exception:
            pass
    
    # Trend calculation (simplified - would need history for real trend)
    trend = "stable"
    if state.value > 0.7:
        trend = "increasing"
    elif state.value < 0.3:
        trend = "decreasing"
    
    return {
        "firing_rate": round(firing_rate, 3),
        "avg_value": round(state.value, 3),
        "trend": trend
    }


def _calculate_avg_latency(manager: Any) -> float:
    """Calculate average pipeline latency.
    
    Args:
        manager: NeuronManager instance
    
    Returns:
        Average latency in milliseconds
    """
    # Simplified: would need actual timing data for real latency
    # Estimate based on neuron count and typical processing time
    total_neurons = (
        len(manager._context_neurons) +
        len(manager._state_neurons) +
        len(manager._mood_neurons)
    )
    
    # Rough estimate: ~1ms per neuron
    base_latency = total_neurons * 1.0
    
    # Add some variance based on recent evaluations
    if manager._last_result:
        base_latency += 5.0  # Base overhead
    
    return round(base_latency, 2)


# Import datetime at module level
from datetime import datetime, timezone


__all__ = ["bp"]
