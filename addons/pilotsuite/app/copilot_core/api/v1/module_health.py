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
from flask import Blueprint, jsonify
from typing import Any, Dict, Optional

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


@module_health_bp.route("/dashboard", methods=["GET"])
def get_health_dashboard():
    """Return the full module health dashboard."""
    result: Dict[str, Any] = {
        "timestamp_ms": int(time.time() * 1000),
    }

    # Module states
    if _module_registry:
        result["modules"] = _module_registry.get_all_states()
    else:
        result["modules"] = {}

    # Integration bus metrics
    if _integration_bus:
        result["bus"] = _integration_bus.get_stats()
    else:
        result["bus"] = None

    # Hebbian learning stats
    if _hebbian_learning:
        result["learning"] = _hebbian_learning.get_stats()
        result["learning"]["weight_drift"] = _hebbian_learning.get_weight_drift()
    else:
        result["learning"] = None

    # Cross-module patterns
    if _cross_module_analyzer:
        result["cross_module"] = _cross_module_analyzer.get_stats()
        result["cross_module"]["patterns"] = _cross_module_analyzer.get_patterns()
    else:
        result["cross_module"] = None

    # Feedback loop
    if _feedback_loop:
        result["feedback"] = _feedback_loop.get_stats()
    else:
        result["feedback"] = None

    return jsonify(result)


@module_health_bp.route("/learning", methods=["GET"])
def get_learning_status():
    """Return detailed Hebbian learning status."""
    if _hebbian_learning is None:
        return jsonify({"error": "HebbianLearning not initialized"}), 503

    return jsonify({
        "stats": _hebbian_learning.get_stats(),
        "weights": _hebbian_learning.get_all_weights(),
        "drift": _hebbian_learning.get_weight_drift(),
        "timestamp_ms": int(time.time() * 1000),
    })


@module_health_bp.route("/patterns", methods=["GET"])
def get_patterns():
    """Return discovered cross-module patterns."""
    if _cross_module_analyzer is None:
        return jsonify({"error": "CrossModuleAnalyzer not initialized"}), 503

    patterns = _cross_module_analyzer.get_patterns()
    proposals = [
        {
            "from_neuron": p.from_neuron,
            "to_neuron": p.to_neuron,
            "proposed_weight": p.proposed_weight,
            "reason": p.reason,
            "confidence": p.confidence,
        }
        for p in _cross_module_analyzer.suggest_new_connections()
    ]

    return jsonify({
        "patterns": patterns,
        "proposed_synapses": proposals,
        "stats": _cross_module_analyzer.get_stats(),
        "timestamp_ms": int(time.time() * 1000),
    })
