"""
Styx Dashboard API — Unified endpoint for the SPA dashboard.

Aggregates data from all subsystems into a single response optimized
for frontend rendering: mood, neurons, brain graph, habitus zones,
module states, bus health, and suggestions.

Endpoints:
    GET  /api/v1/styx/dashboard          — Full dashboard payload
    GET  /api/v1/styx/dashboard/compact  — Lightweight polling payload
    GET  /api/v1/styx/config             — System configuration overview
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token

_LOGGER = logging.getLogger(__name__)

styx_dashboard_bp = Blueprint(
    "styx_dashboard", __name__, url_prefix="/api/v1/styx"
)

# Wired by init_styx_dashboard_api()
_services: Dict[str, Any] = {}


def init_styx_dashboard_api(services: Dict[str, Any]) -> None:
    """Wire services dict into the dashboard API."""
    global _services
    _services = services
    _LOGGER.info("Styx Dashboard API initialized with %d services", len(services))


@styx_dashboard_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


def _safe_call(fn, default=None):
    """Call fn, return default on any error."""
    try:
        return fn()
    except Exception:
        return default


# ═══════════════════════════════════════════════════════════════════════
# GET /api/v1/styx/dashboard — Full dashboard payload
# ═══════════════════════════════════════════════════════════════════════

@styx_dashboard_bp.route("/dashboard", methods=["GET"])
def full_dashboard():
    """Aggregated dashboard data for the Styx SPA.

    Returns all subsystem states in a single JSON response.
    """
    t0 = time.monotonic()

    # ── Mood ──
    neuron_mgr = _services.get("neuron_manager")
    mood_data = {}
    neuron_summary = {}
    if neuron_mgr:
        mood_data = _safe_call(neuron_mgr.get_mood_summary, {})
        neuron_summary = _safe_call(neuron_mgr.get_neuron_summary, {})

    # ── Brain Graph ──
    brain_svc = _services.get("brain_graph_service")
    graph_summary = {}
    if brain_svc:
        graph_state = _safe_call(
            lambda: brain_svc.get_graph_state(limit_nodes=30, limit_edges=60), {}
        )
        nodes = graph_state.get("nodes", [])
        edges = graph_state.get("edges", [])
        kind_counts = {}
        for n in nodes:
            k = n.get("kind", "unknown")
            kind_counts[k] = kind_counts.get(k, 0) + 1
        graph_summary = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "nodes_by_kind": kind_counts,
            "top_nodes": sorted(nodes, key=lambda n: n.get("score", 0), reverse=True)[:5],
        }

    # ── Integration Bus ──
    bus = _services.get("integration_bus")
    bus_stats = _safe_call(bus.get_stats, {}) if bus else {}
    dead_letters = _safe_call(bus.get_dead_letters, []) if bus else []

    # ── Module Registry ──
    registry = _services.get("module_registry")
    module_states = _safe_call(registry.get_all_states, {}) if registry else {}

    # ── Habitus ──
    habitus = _services.get("habitus_service")
    habitus_stats = _safe_call(habitus.get_pattern_stats, {}) if habitus else {}

    # ── Hebbian Learning ──
    hebbian = _services.get("hebbian_learning")
    learning_data = {}
    if hebbian:
        learning_data = _safe_call(lambda: {
            "total_synapses": len(hebbian.get_all_weights()),
            "top_drifts": sorted(
                [{"synapse": k, "drift": abs(v)} for k, v in hebbian.get_drift().items()],
                key=lambda x: x["drift"], reverse=True,
            )[:5],
        }, {})

    # ── Candidates ──
    candidates_store = _services.get("candidate_store")
    recent_candidates = []
    if candidates_store:
        recent_candidates = _safe_call(lambda: candidates_store.list(limit=5), [])

    # ── Habitus Zones (delegiert an zone_dashboard) ──
    zones_data = []
    try:
        from copilot_core.api.v1.zone_dashboard import build_zones_for_styx
        zones_data = build_zones_for_styx()
    except Exception:
        pass

    # ── Media / Musikwolke ──
    media_mgr = _services.get("media_zone_manager")
    media_data = {}
    if media_mgr:
        media_data = _safe_call(media_mgr.get_summary, {})

    # ── Suggestions ──
    suggestion_engine = _services.get("suggestion_engine")
    suggestions = []
    if suggestion_engine:
        suggestions = _safe_call(
            lambda: suggestion_engine.get_pending(limit=10), []
        )
    if not suggestions:
        try:
            from copilot_core.example_config import EXAMPLE_SUGGESTIONS
            suggestions = EXAMPLE_SUGGESTIONS
        except Exception:
            pass

    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    return jsonify({
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "render_ms": elapsed_ms,
        "mood": mood_data,
        "neurons": {
            "summary": neuron_summary,
            "total_count": neuron_summary.get("total_count", 0) if isinstance(neuron_summary, dict) else 0,
        },
        "graph": graph_summary,
        "bus": {
            **bus_stats,
            "dead_letter_count": len(dead_letters),
            "recent_dead_letters": dead_letters[:3],
        },
        "modules": module_states,
        "habitus": habitus_stats,
        "learning": learning_data,
        "candidates": recent_candidates,
        "zones": zones_data,
        "media": media_data,
        "suggestions": suggestions,
    })


# ═══════════════════════════════════════════════════════════════════════
# GET /api/v1/styx/dashboard/compact — Lightweight polling payload
# ═══════════════════════════════════════════════════════════════════════

@styx_dashboard_bp.route("/dashboard/compact", methods=["GET"])
def compact_dashboard():
    """Lightweight dashboard for frequent polling (5–10s intervals).

    Returns only frequently-changing data: mood, bus counters, module states.
    """
    neuron_mgr = _services.get("neuron_manager")
    mood = _safe_call(neuron_mgr.get_mood_summary, {}) if neuron_mgr else {}

    bus = _services.get("integration_bus")
    bus_stats = _safe_call(bus.get_stats, {}) if bus else {}

    registry = _services.get("module_registry")
    module_states = _safe_call(registry.get_all_states, {}) if registry else {}

    return jsonify({
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mood": mood,
        "bus": {
            "events_published": bus_stats.get("events_published", 0),
            "events_delivered": bus_stats.get("events_delivered", 0),
            "errors": bus_stats.get("errors", 0),
        },
        "modules": module_states,
    })


# ═══════════════════════════════════════════════════════════════════════
# GET /api/v1/styx/config — System configuration overview
# ═══════════════════════════════════════════════════════════════════════

@styx_dashboard_bp.route("/config", methods=["GET"])
def system_config():
    """Return current system configuration for the config panel.

    Exposes which modules are available, their states, and configurable
    parameters — without exposing secrets.
    """
    registry = _services.get("module_registry")
    module_states = _safe_call(registry.get_all_states, {}) if registry else {}

    # Discover known modules
    known_modules = [
        {"id": "mood_engine", "label": "Mood Engine", "icon": "mdi:emoticon", "description": "Stimmungserkennung aus Sensorwerten"},
        {"id": "habitus_miner", "label": "Habitus Miner", "icon": "mdi:pickaxe", "description": "Automatische Muster-Erkennung"},
        {"id": "brain_graph", "label": "Brain Graph", "icon": "mdi:brain", "description": "Wissens- und Beziehungsgraph"},
        {"id": "neuron_pipeline", "label": "Neuron Pipeline", "icon": "mdi:chart-timeline-variant-shimmer", "description": "Neuronale 3-Schicht-Pipeline"},
        {"id": "integration_bus", "label": "Integration Bus", "icon": "mdi:swap-horizontal", "description": "Event-basierte Modul-Kommunikation"},
        {"id": "hebbian_learning", "label": "Hebbian Learning", "icon": "mdi:school", "description": "Adaptive Synaptische Gewichte"},
        {"id": "proactive_engine", "label": "Proactive Engine", "icon": "mdi:lightbulb-on", "description": "Kontextbezogene Vorschläge"},
        {"id": "energy_service", "label": "Energy Service", "icon": "mdi:solar-power", "description": "PV-Prognose und Kostenoptimierung"},
        {"id": "voice_context", "label": "Voice Context", "icon": "mdi:microphone", "description": "Sprachassistent-Kontext"},
        {"id": "anomaly_detection", "label": "Anomaly Detection", "icon": "mdi:alert-circle", "description": "ML-basierte Anomalie-Erkennung"},
    ]

    for mod in known_modules:
        mod["state"] = module_states.get(mod["id"], "active")
        # Add autonomy helpers
        if registry:
            mod["collects_data"] = _safe_call(
                lambda mid=mod["id"]: registry.should_collect_data(mid), True
            )
            mod["generates_suggestions"] = _safe_call(
                lambda mid=mod["id"]: registry.should_suggest(mid), True
            )

    # Habitus zones
    habitus_zones = []
    try:
        from copilot_core.homeassistant.habitus_zones import get_all_zones
        for zone in get_all_zones():
            habitus_zones.append({
                "id": zone.zone_type.value,
                "name_de": zone.name_de,
                "name_en": zone.name_en,
                "priority": zone.priority,
            })
    except Exception:
        pass

    # Service availability summary
    service_health = {}
    for key in ("neuron_manager", "brain_graph_service", "integration_bus",
                "habitus_service", "hebbian_learning", "candidate_store",
                "module_registry", "proactive_engine"):
        service_health[key] = _services.get(key) is not None

    return jsonify({
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules": known_modules,
        "habitus_zones": habitus_zones,
        "valid_module_states": ["active", "learning", "off"],
        "service_health": service_health,
        "startup_time_ms": _services.get("startup_time_ms", 0),
    })
