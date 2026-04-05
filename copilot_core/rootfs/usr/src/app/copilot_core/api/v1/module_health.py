"""
Module Health Dashboard API.

Provides a unified view of all module states, integration bus metrics,
cross-module patterns, and learning progress.

Endpoints:
    GET /api/v1/modules/health/dashboard — Full health dashboard
    GET /api/v1/modules/health/learning  — Learning engine status
    GET /api/v1/modules/health/patterns  — Cross-module patterns
"""

from __future__ import annotations

import logging
import time
from typing import Any

from flask import Blueprint, Response, jsonify

_LOGGER = logging.getLogger(__name__)

module_health_bp = Blueprint("module_health", __name__, url_prefix="/api/v1/modules/health")

# Wired by init_module_health_api()
_module_registry = None
_integration_bus = None
_hebbian_learning = None
_cross_module_analyzer = None
_feedback_loop = None


def init_module_health_api(
    module_registry=None,
    integration_bus=None,
    hebbian_learning=None,
    cross_module_analyzer=None,
    feedback_loop=None,
) -> None:
    """Wire the module health API with service instances."""
    global _module_registry, _integration_bus, _hebbian_learning
    global _cross_module_analyzer, _feedback_loop
    _module_registry = module_registry
    _integration_bus = integration_bus
    _hebbian_learning = hebbian_learning
    _cross_module_analyzer = cross_module_analyzer
    _feedback_loop = feedback_loop


def _timestamp_ms() -> int:
    return int(time.time() * 1000)


def _error(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status_code


def _ensure_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _ensure_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a list")
    return value


def _proposal_value(proposal: Any, key: str) -> Any:
    if isinstance(proposal, dict):
        return proposal.get(key)
    return getattr(proposal, key, None)


def _serialize_proposed_synapse(proposal: Any) -> dict[str, Any]:
    payload = {
        "from_neuron": _proposal_value(proposal, "from_neuron"),
        "to_neuron": _proposal_value(proposal, "to_neuron"),
        "proposed_weight": _proposal_value(proposal, "proposed_weight"),
        "reason": _proposal_value(proposal, "reason"),
        "confidence": _proposal_value(proposal, "confidence"),
    }
    if any(value is None for value in payload.values()):
        raise TypeError("Proposed synapse must expose from_neuron, to_neuron, proposed_weight, reason, confidence")
    return payload


@module_health_bp.route("/dashboard", methods=["GET"])
def get_health_dashboard():
    """Return the full module health dashboard."""
    try:
        result: dict[str, Any] = {
            "timestamp_ms": _timestamp_ms(),
            "modules": {},
            "bus": None,
            "learning": None,
            "cross_module": None,
            "feedback": None,
        }

        if _module_registry:
            result["modules"] = _ensure_dict(_module_registry.get_all_states(), "ModuleRegistry states")

        if _integration_bus:
            result["bus"] = _ensure_dict(_integration_bus.get_stats(), "IntegrationBus stats")

        if _hebbian_learning:
            learning_stats = _ensure_dict(_hebbian_learning.get_stats(), "HebbianLearning stats")
            learning_stats["weight_drift"] = _ensure_dict(
                _hebbian_learning.get_weight_drift(),
                "HebbianLearning weight drift",
            )
            result["learning"] = learning_stats

        if _cross_module_analyzer:
            cross_module_stats = _ensure_dict(
                _cross_module_analyzer.get_stats(),
                "CrossModuleAnalyzer stats",
            )
            cross_module_stats["patterns"] = _ensure_list(
                _cross_module_analyzer.get_patterns(),
                "CrossModuleAnalyzer patterns",
            )
            result["cross_module"] = cross_module_stats

        if _feedback_loop:
            result["feedback"] = _ensure_dict(_feedback_loop.get_stats(), "FeedbackLoop stats")

        return jsonify(result)
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.warning("Module health dashboard error: %s", exc)
        return _error(str(exc), 500)


@module_health_bp.route("/learning", methods=["GET"])
def get_learning_status():
    """Return detailed Hebbian learning status."""
    if _hebbian_learning is None:
        return _error("HebbianLearning not initialized", 503)

    try:
        return jsonify(
            {
                "stats": _ensure_dict(_hebbian_learning.get_stats(), "HebbianLearning stats"),
                "weights": _ensure_dict(_hebbian_learning.get_all_weights(), "HebbianLearning weights"),
                "drift": _ensure_dict(_hebbian_learning.get_weight_drift(), "HebbianLearning weight drift"),
                "timestamp_ms": _timestamp_ms(),
            }
        )
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.warning("Module health learning error: %s", exc)
        return _error(str(exc), 500)


@module_health_bp.route("/patterns", methods=["GET"])
def get_patterns():
    """Return discovered cross-module patterns."""
    if _cross_module_analyzer is None:
        return _error("CrossModuleAnalyzer not initialized", 503)

    try:
        patterns = _ensure_list(_cross_module_analyzer.get_patterns(), "CrossModuleAnalyzer patterns")
        proposed_synapses = _ensure_list(
            _cross_module_analyzer.suggest_new_connections(),
            "CrossModuleAnalyzer proposed synapses",
        )

        return jsonify(
            {
                "patterns": patterns,
                "proposed_synapses": [
                    _serialize_proposed_synapse(proposal)
                    for proposal in proposed_synapses
                ],
                "stats": _ensure_dict(_cross_module_analyzer.get_stats(), "CrossModuleAnalyzer stats"),
                "timestamp_ms": _timestamp_ms(),
            }
        )
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.warning("Module health patterns error: %s", exc)
        return _error(str(exc), 500)
