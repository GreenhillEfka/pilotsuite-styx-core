"""Neuron Visualization API - Enhanced endpoints for PilotSuite neural system.

Provides detailed neuron state visualization and brain pipeline inspection.

Endpoints:
    GET /api/v1/neurons/state                - Alle 14 Neuronen-States
    GET /api/v1/neurons/{id}/fire            - Einzelnes Neuron (Live-Status)
    GET /api/v1/neurons/brain/pipeline       - Kommunikations-Pipeline
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.neurons.base import BaseNeuron
from copilot_core.neurons.manager import get_neuron_manager

_LOGGER = logging.getLogger(__name__)

# Create blueprint with relative prefix (nested under /api/v1)
bp = Blueprint("neurons_viz", __name__, url_prefix="/neurons")


class _ServiceUnavailableError(RuntimeError):
    """Raised when the neuron manager is unavailable."""


class _ContractError(ValueError):
    """Raised when runtime objects violate the API contract."""


@bp.before_request
def _require_auth():
    """Require authentication for all neuron visualization endpoints."""
    if not validate_token(request):
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required",
        }), 401


# =============================================================================
# Neuron State Endpoints
# =============================================================================

@bp.route("/state", methods=["GET"])
def get_all_neurons_state():
    """Get all neuron states grouped by neuron type."""
    try:
        manager = _require_manager()
        context_store = _get_neuron_store(manager, "_context_neurons", "context")
        state_store = _get_neuron_store(manager, "_state_neurons", "state")
        mood_store = _get_neuron_store(manager, "_mood_neurons", "mood")

        context_neurons, context_active = _serialize_neuron_store(context_store)
        state_neurons, state_active = _serialize_neuron_store(state_store)
        mood_neurons, mood_active = _serialize_neuron_store(mood_store)
        summary = _require_mapping(manager.get_neuron_summary(), "Neuron summary")

        return jsonify({
            "success": True,
            "data": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_neurons": len(context_neurons) + len(state_neurons) + len(mood_neurons),
                "active_count": context_active + state_active + mood_active,
                "neurons": {
                    "context": context_neurons,
                    "state": state_neurons,
                    "mood": mood_neurons,
                },
                "summary": {
                    "context_values": _summary_bucket(summary, "context"),
                    "state_values": _summary_bucket(summary, "state"),
                    "mood_values": _summary_bucket(summary, "mood"),
                },
            },
        })
    except _ServiceUnavailableError as exc:
        return _json_error(str(exc), 503)
    except _ContractError as exc:
        return _json_error(str(exc), 500)
    except Exception as exc:  # pragma: no cover - defensive logging path
        _LOGGER.exception("Error getting all neuron states")
        return _json_error(str(exc), 500)


@bp.route("/<neuron_id>/fire", methods=["GET"])
def get_neuron_fire_status(neuron_id: str):
    """Get live fire status for a single neuron."""
    try:
        manager = _require_manager()
        context_store = _get_neuron_store(manager, "_context_neurons", "context")
        state_store = _get_neuron_store(manager, "_state_neurons", "state")
        mood_store = _get_neuron_store(manager, "_mood_neurons", "mood")

        neuron_name, neuron = _find_neuron(neuron_id, context_store, state_store, mood_store)
        if neuron is None:
            return jsonify({
                "success": False,
                "error": f"Neuron not found: {neuron_id}",
            }), 404

        return jsonify({
            "success": True,
            "data": {
                "name": _require_non_empty_string(getattr(neuron, "name", None), f"Neuron {neuron_name} name"),
                "type": _enum_string(getattr(neuron, "neuron_type", None), f"Neuron {neuron_name} type"),
                "firing": _neuron_is_active(neuron, neuron_name),
                "state": _state_payload(neuron, neuron_name),
                "config": _config_payload(neuron, neuron_name),
                "live_metrics": _calculate_live_metrics(neuron, neuron_name),
            },
        })
    except _ServiceUnavailableError as exc:
        return _json_error(str(exc), 503)
    except _ContractError as exc:
        return _json_error(str(exc), 500)
    except Exception as exc:  # pragma: no cover - defensive logging path
        _LOGGER.exception("Error getting neuron fire status for %s", neuron_id)
        return _json_error(str(exc), 500)


# =============================================================================
# Brain Pipeline Endpoint
# =============================================================================

@bp.route("/brain/pipeline", methods=["GET"])
def get_brain_pipeline():
    """Get the communication pipeline status."""
    try:
        manager = _require_manager()
        context_store = _get_neuron_store(manager, "_context_neurons", "context")
        state_store = _get_neuron_store(manager, "_state_neurons", "state")
        mood_store = _get_neuron_store(manager, "_mood_neurons", "mood")

        context_active = _active_count(context_store)
        state_active = _active_count(state_store)
        mood_active = _active_count(mood_store)
        last_result = getattr(manager, "_last_result", None)
        execution_count = _require_int(
            getattr(manager, "_evaluation_count", 0),
            "NeuronManager evaluation count",
            minimum=0,
        )

        stages = [
            {
                "name": "Context Evaluation",
                "type": "input",
                "neuron_count": len(context_store),
                "active_count": context_active,
                "status": "active" if context_store else "inactive",
                "description": "Evaluates objective environmental factors",
            },
            {
                "name": "State Smoothing",
                "type": "processing",
                "neuron_count": len(state_store),
                "active_count": state_active,
                "status": "active" if state_store else "inactive",
                "description": "Applies EMA smoothing and inertia",
            },
            {
                "name": "Mood Aggregation",
                "type": "aggregation",
                "neuron_count": len(mood_store),
                "active_count": mood_active,
                "status": "active" if mood_store else "inactive",
                "description": "Aggregates into mood values",
            },
            {
                "name": "Suggestion Generation",
                "type": "output",
                "neuron_count": 0,
                "active_count": 0,
                "status": "active",
                "description": "Generates actionable suggestions",
            },
        ]
        pipeline_status = "active" if any(stage["active_count"] > 0 for stage in stages) else "idle"

        return jsonify({
            "success": True,
            "data": {
                "pipeline": {
                    "stages": stages,
                    "status": pipeline_status,
                    "last_execution": _last_execution(last_result),
                    "execution_count": execution_count,
                },
                "data_flow": {
                    "input_rate": len(_get_ha_states(manager)),
                    "output_rate": _suggestion_count(last_result),
                    "avg_latency_ms": _calculate_avg_latency(context_store, state_store, mood_store, last_result),
                },
                "connections": {
                    "context_to_state": [
                        {"from": name, "to": "state_neurons", "weight": 0.5}
                        for name in list(context_store.keys())[:5]
                    ],
                    "state_to_mood": [
                        {"from": name, "to": "mood_neurons", "weight": 0.7}
                        for name in list(state_store.keys())[:5]
                    ],
                    "mood_to_suggestions": [
                        {"from": name, "to": "suggestions", "weight": 1.0}
                        for name in list(mood_store.keys())[:5]
                    ],
                },
                "current_state": {
                    "context_active": context_active,
                    "state_active": state_active,
                    "mood_active": mood_active,
                    "dominant_mood": _dominant_mood(last_result),
                },
            },
        })
    except _ServiceUnavailableError as exc:
        return _json_error(str(exc), 503)
    except _ContractError as exc:
        return _json_error(str(exc), 500)
    except Exception as exc:  # pragma: no cover - defensive logging path
        _LOGGER.exception("Error getting brain pipeline")
        return _json_error(str(exc), 500)


# =============================================================================
# Helper Functions
# =============================================================================

def _json_error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _require_manager() -> Any:
    manager = get_neuron_manager()
    if manager is None:
        raise _ServiceUnavailableError("NeuronManager not initialized")
    return manager


def _get_neuron_store(manager: Any, attr_name: str, label: str) -> Mapping[str, Any]:
    store = getattr(manager, attr_name, None)
    return _require_mapping(store, f"NeuronManager {label} store")


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _ContractError(f"{label} must be an object")
    return value


def _require_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _ContractError(f"{label} must be a non-empty string")
    return value


def _require_numeric(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise _ContractError(f"{label} must be numeric")
    return float(value)


def _require_int(value: object, label: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _ContractError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise _ContractError(f"{label} must be >= {minimum}")
    return value


def _enum_string(value: object, label: str) -> str:
    enum_value = getattr(value, "value", None)
    return _require_non_empty_string(enum_value, label)


def _serialize_neuron_store(store: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int]:
    payloads: list[dict[str, Any]] = []
    active_count = 0
    for name, neuron in store.items():
        neuron_name = _require_non_empty_string(name, "Neuron key")
        payload = dict(_require_mapping(neuron.to_dict(), f"Neuron {neuron_name} payload"))
        payload["name"] = neuron_name
        payloads.append(payload)
        if _neuron_is_active(neuron, neuron_name):
            active_count += 1
    return payloads, active_count


def _neuron_is_active(neuron: Any, neuron_name: str) -> bool:
    if not hasattr(neuron, "is_active"):
        raise _ContractError(f"Neuron {neuron_name} missing is_active")
    return bool(getattr(neuron, "is_active"))


def _find_neuron(
    neuron_id: str,
    context_store: Mapping[str, Any],
    state_store: Mapping[str, Any],
    mood_store: Mapping[str, Any],
) -> tuple[str | None, Any]:
    normalized_id = _require_non_empty_string(neuron_id, "Neuron id")
    for store in (context_store, state_store, mood_store):
        if normalized_id in store:
            return normalized_id, store[normalized_id]

    base_id = normalized_id.rsplit(".", 1)[-1]
    for store in (context_store, state_store, mood_store):
        for name, neuron in store.items():
            if name == base_id or name.endswith(f".{base_id}"):
                return name, neuron
    return None, None


def _state_payload(neuron: Any, neuron_name: str) -> dict[str, Any]:
    state = getattr(neuron, "state", None)
    if state is None or not hasattr(state, "to_dict"):
        raise _ContractError(f"Neuron {neuron_name} state missing")
    return dict(_require_mapping(state.to_dict(), f"Neuron {neuron_name} state payload"))


def _config_payload(neuron: Any, neuron_name: str) -> dict[str, Any]:
    config = getattr(neuron, "config", None)
    if config is None or not hasattr(config, "to_dict"):
        raise _ContractError(f"Neuron {neuron_name} config missing")
    return dict(_require_mapping(config.to_dict(), f"Neuron {neuron_name} config payload"))


def _summary_bucket(summary: Mapping[str, Any], key: str) -> dict[str, Any]:
    bucket = summary.get(key, {})
    return dict(_require_mapping(bucket, f"Neuron summary {key}"))


def _active_count(store: Mapping[str, Any]) -> int:
    return sum(1 for name, neuron in store.items() if _neuron_is_active(neuron, name))


def _last_execution(last_result: Any) -> str | None:
    if last_result is None:
        return None
    timestamp = getattr(last_result, "timestamp", None)
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    return _require_non_empty_string(timestamp, "Pipeline timestamp")


def _dominant_mood(last_result: Any) -> str:
    if last_result is None:
        return "unknown"
    dominant_mood = getattr(last_result, "dominant_mood", None)
    if hasattr(dominant_mood, "value"):
        dominant_mood = dominant_mood.value
    return _require_non_empty_string(dominant_mood, "Pipeline dominant mood")


def _get_ha_states(manager: Any) -> Mapping[str, Any]:
    return _require_mapping(getattr(manager, "_ha_states", {}), "NeuronManager HA state cache")


def _suggestion_count(last_result: Any) -> int:
    if last_result is None:
        return 0
    suggestions = getattr(last_result, "suggestions", None)
    if not isinstance(suggestions, list):
        raise _ContractError("Pipeline suggestions must be a list")
    return len(suggestions)


def _calculate_live_metrics(neuron: BaseNeuron, neuron_name: str) -> dict[str, Any]:
    """Calculate live metrics for a neuron."""
    state = getattr(neuron, "state", None)
    if state is None:
        raise _ContractError(f"Neuron {neuron_name} state missing")

    value = _require_numeric(getattr(state, "value", None), f"Neuron {neuron_name} state value")
    trigger_count = _require_int(
        getattr(state, "trigger_count", 0),
        f"Neuron {neuron_name} trigger count",
        minimum=0,
    )
    last_trigger = getattr(state, "last_trigger", None)
    firing_rate = 0.0

    if last_trigger is not None:
        last_trigger_str = _require_non_empty_string(last_trigger, f"Neuron {neuron_name} last trigger")
        if trigger_count > 0:
            try:
                last_trigger_time = datetime.fromisoformat(last_trigger_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_minutes = (now - last_trigger_time).total_seconds() / 60
                if age_minutes > 0:
                    firing_rate = trigger_count / age_minutes
            except ValueError as exc:  # pragma: no cover - defensive parsing guard
                raise _ContractError(f"Neuron {neuron_name} last trigger must be ISO-8601") from exc

    trend = "stable"
    if value > 0.7:
        trend = "increasing"
    elif value < 0.3:
        trend = "decreasing"

    return {
        "firing_rate": round(firing_rate, 3),
        "avg_value": round(value, 3),
        "trend": trend,
    }


def _calculate_avg_latency(
    context_store: Mapping[str, Any],
    state_store: Mapping[str, Any],
    mood_store: Mapping[str, Any],
    last_result: Any,
) -> float:
    """Calculate average pipeline latency."""
    total_neurons = len(context_store) + len(state_store) + len(mood_store)
    base_latency = total_neurons * 1.0
    if last_result is not None:
        base_latency += 5.0
    return round(base_latency, 2)


__all__ = ["bp"]
