"""
Neuron Layer Visualization API.

Endpoints:
    GET /api/v1/neurons/layers/visualization  — Full layer data + connections
    GET /api/v1/neurons/layers/snapshot.svg    — SVG visualization
    GET /api/v1/neurons/connections/heatmap    — Connection weight matrix
"""

from __future__ import annotations

import logging
import time
from flask import Blueprint, jsonify, Response
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

neuron_layers_bp = Blueprint("neuron_layers", __name__, url_prefix="/api/v1/neurons/layers")

# Wired by init_neuron_layers_api()
_neuron_manager = None
_integration_bus = None

# Synapse topology: (from_neuron, to_neuron, weight)
# Derived from state.py and mood.py evaluate() methods
SYNAPSE_TOPOLOGY: List[tuple[str, str, float]] = [
    # Context → State
    ("context.time_of_day", "state.energy_level", 0.3),
    ("context.presence", "state.energy_level", 0.2),
    ("context.time_of_day", "state.stress_index", 0.25),
    ("context.presence", "state.routine_stability", 0.3),
    ("context.time_of_day", "state.routine_stability", 0.4),
    ("context.light_level", "state.comfort_index", 0.2),
    ("context.weather", "state.comfort_index", 0.15),
    ("context.time_of_day", "state.sleep_debt", 0.2),
    ("context.time_of_day", "state.attention_load", 0.3),
    # State → Mood
    ("state.energy_level", "mood.relax", -0.1),
    ("state.stress_index", "mood.relax", -0.4),
    ("state.comfort_index", "mood.relax", 0.3),
    ("state.attention_load", "mood.relax", -0.2),
    ("state.energy_level", "mood.focus", 0.3),
    ("state.stress_index", "mood.focus", -0.3),
    ("state.attention_load", "mood.focus", -0.2),
    ("state.routine_stability", "mood.focus", 0.2),
    ("state.energy_level", "mood.active", 0.4),
    ("state.comfort_index", "mood.active", 0.1),
    ("state.sleep_debt", "mood.active", -0.2),
    ("state.sleep_debt", "mood.sleep", 0.5),
    ("state.energy_level", "mood.sleep", -0.3),
    ("state.attention_load", "mood.sleep", -0.2),
    ("state.stress_index", "mood.alert", 0.5),
    ("state.routine_stability", "mood.alert", -0.3),
    ("state.attention_load", "mood.alert", 0.2),
    ("state.energy_level", "mood.social", 0.2),
    ("state.attention_load", "mood.social", 0.3),
    ("state.stress_index", "mood.recovery", -0.3),
    ("state.comfort_index", "mood.recovery", 0.4),
    ("state.routine_stability", "mood.recovery", 0.2),
    # Cross-layer (context directly to mood)
    ("context.presence", "mood.active", 0.3),
    ("context.presence", "mood.away", -0.7),
    ("context.presence", "mood.social", 0.3),
]


def init_neuron_layers_api(neuron_manager, integration_bus=None) -> None:
    """Wire the API with the NeuronManager instance."""
    global _neuron_manager, _integration_bus
    _neuron_manager = neuron_manager
    _integration_bus = integration_bus


@neuron_layers_bp.route("/visualization", methods=["GET"])
def get_layer_visualization():
    """Return full neuron layer data with values and connections."""
    if _neuron_manager is None:
        return jsonify({"error": "NeuronManager not initialized"}), 503

    all_neurons = _neuron_manager.get_all_neurons()
    result = _neuron_manager._last_result

    # Build layer structure
    layers = [
        _build_layer(0, "Context", "context", all_neurons, result),
        _build_layer(1, "State", "state", all_neurons, result),
        _build_layer(2, "Mood", "mood", all_neurons, result),
    ]

    # Build connections with signal strength
    connections = _build_connections(all_neurons, result)

    # Pipeline status
    pipeline_status = {
        "last_evaluation": result.timestamp if result else None,
        "dominant_mood": result.dominant_mood if result else None,
        "mood_confidence": result.mood_confidence if result else 0.0,
    }

    # Bus stats if available
    bus_stats = None
    if _integration_bus:
        bus_stats = _integration_bus.get_stats()

    return jsonify({
        "layers": layers,
        "connections": connections,
        "pipeline_status": pipeline_status,
        "bus_stats": bus_stats,
        "timestamp_ms": int(time.time() * 1000),
    })


@neuron_layers_bp.route("/snapshot.svg", methods=["GET"])
def get_layer_svg():
    """Return SVG visualization of the neuron layers."""
    if _neuron_manager is None:
        return Response(
            _render_placeholder_svg("NeuronManager not initialized"),
            mimetype="image/svg+xml",
        )

    all_neurons = _neuron_manager.get_all_neurons()
    result = _neuron_manager._last_result
    svg = render_neuron_layer_svg(all_neurons, result)
    return Response(svg, mimetype="image/svg+xml")


@neuron_layers_bp.route("/heatmap", methods=["GET"])
def get_connection_heatmap():
    """Return connection weight matrix as a heatmap data structure."""
    if _neuron_manager is None:
        return jsonify({"error": "NeuronManager not initialized"}), 503

    all_neurons = _neuron_manager.get_all_neurons()
    labels = sorted(all_neurons.keys())
    n = len(labels)
    label_index = {name: i for i, name in enumerate(labels)}

    # Build matrix (n×n, default 0)
    matrix = [[0.0] * n for _ in range(n)]
    for from_n, to_n, weight in SYNAPSE_TOPOLOGY:
        i = label_index.get(from_n)
        j = label_index.get(to_n)
        if i is not None and j is not None:
            matrix[i][j] = weight

    # Layer boundaries
    context_count = sum(1 for k in labels if k.startswith("context."))
    state_count = sum(1 for k in labels if k.startswith("state."))
    layer_boundaries = [
        context_count,
        context_count + state_count,
        n,
    ]

    return jsonify({
        "matrix": matrix,
        "labels": labels,
        "layer_boundaries": layer_boundaries,
        "timestamp_ms": int(time.time() * 1000),
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_layer(
    layer_id: int,
    name: str,
    prefix: str,
    all_neurons: dict,
    result,
) -> Dict[str, Any]:
    """Build a layer dict with neuron details."""
    neurons = []
    for full_name, neuron in sorted(all_neurons.items()):
        if not full_name.startswith(f"{prefix}."):
            continue
        short_name = full_name.split(".", 1)[1]
        value = neuron.value
        neurons.append({
            "id": full_name,
            "name": short_name,
            "value": round(value, 3),
            "active": neuron.state.active,
            "confidence": round(neuron.confidence, 3),
        })
    return {"id": layer_id, "name": name, "neurons": neurons}


def _build_connections(all_neurons: dict, result) -> List[Dict[str, Any]]:
    """Build connection list with signal strength."""
    connections = []
    for from_n, to_n, weight in SYNAPSE_TOPOLOGY:
        from_neuron = all_neurons.get(from_n)
        source_value = from_neuron.value if from_neuron else 0.0
        signal_strength = round(abs(weight) * source_value, 3)
        connections.append({
            "from": from_n,
            "to": to_n,
            "weight": weight,
            "signal_strength": signal_strength,
            "excitatory": weight > 0,
        })
    return connections


# ---------------------------------------------------------------------------
# SVG Renderer
# ---------------------------------------------------------------------------

# Color palette
_COLOR_INACTIVE = "#9CA3AF"  # gray-400
_COLOR_LOW = "#34D399"       # emerald-400
_COLOR_MID = "#FBBF24"       # amber-400
_COLOR_HIGH = "#F87171"      # red-400
_COLOR_DOMINANT = "#8B5CF6"  # violet-500
_BG_COLOR = "#1F2937"        # gray-800
_TEXT_COLOR = "#F9FAFB"      # gray-50
_LAYER_BG = "#374151"        # gray-700


def _value_color(value: float) -> str:
    """Map a 0-1 value to a color."""
    if value < 0.01:
        return _COLOR_INACTIVE
    if value < 0.4:
        return _COLOR_LOW
    if value < 0.7:
        return _COLOR_MID
    return _COLOR_HIGH


def _render_placeholder_svg(message: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="200">'
        f'<rect width="800" height="200" fill="{_BG_COLOR}"/>'
        f'<text x="400" y="100" text-anchor="middle" fill="{_TEXT_COLOR}" '
        f'font-size="16" font-family="monospace">{message}</text>'
        '</svg>'
    )


def render_neuron_layer_svg(all_neurons: dict, result) -> str:
    """Render a layered SVG showing all neurons and connections."""
    # Layout constants
    SVG_W = 900
    LAYER_H = 100
    LAYER_GAP = 80
    PADDING = 40
    NODE_R = 20

    # Group neurons by layer
    layers = {"context": [], "state": [], "mood": []}
    for name in sorted(all_neurons.keys()):
        prefix = name.split(".")[0]
        if prefix in layers:
            layers[prefix].append(name)

    # Calculate layer Y positions
    layer_order = ["context", "state", "mood"]
    layer_y = {}
    for i, layer_name in enumerate(layer_order):
        layer_y[layer_name] = PADDING + i * (LAYER_H + LAYER_GAP) + LAYER_H // 2

    SVG_H = PADDING * 2 + len(layer_order) * LAYER_H + (len(layer_order) - 1) * LAYER_GAP

    # Calculate neuron X positions
    neuron_pos: Dict[str, tuple[int, int]] = {}
    for layer_name in layer_order:
        neurons = layers[layer_name]
        n = len(neurons)
        if n == 0:
            continue
        spacing = (SVG_W - 2 * PADDING) / max(n, 1)
        for j, name in enumerate(neurons):
            x = int(PADDING + spacing * (j + 0.5))
            y = layer_y[layer_name]
            neuron_pos[name] = (x, y)

    # Determine dominant mood
    dominant = result.dominant_mood if result else ""

    # Start SVG
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" '
        f'viewBox="0 0 {SVG_W} {SVG_H}">',
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="{_BG_COLOR}" rx="8"/>',
    ]

    # Layer backgrounds
    for i, layer_name in enumerate(layer_order):
        ly = PADDING + i * (LAYER_H + LAYER_GAP)
        label = ["Layer 0: Context", "Layer 1: State", "Layer 2: Mood"][i]
        parts.append(
            f'<rect x="{PADDING//2}" y="{ly}" width="{SVG_W - PADDING}" '
            f'height="{LAYER_H}" fill="{_LAYER_BG}" rx="6" opacity="0.5"/>'
        )
        parts.append(
            f'<text x="{PADDING}" y="{ly + 16}" fill="{_TEXT_COLOR}" '
            f'font-size="11" font-family="monospace" opacity="0.6">{label}</text>'
        )

    # Draw connections
    for from_n, to_n, weight in SYNAPSE_TOPOLOGY:
        if from_n not in neuron_pos or to_n not in neuron_pos:
            continue
        x1, y1 = neuron_pos[from_n]
        x2, y2 = neuron_pos[to_n]
        source_neuron = all_neurons.get(from_n)
        source_val = source_neuron.value if source_neuron else 0.0
        strength = abs(weight) * source_val
        opacity = max(0.08, min(0.6, strength))
        stroke_w = max(0.5, min(3.0, strength * 4))
        color = _COLOR_LOW if weight > 0 else _COLOR_HIGH
        dash = "" if weight > 0 else 'stroke-dasharray="4,3"'
        parts.append(
            f'<line x1="{x1}" y1="{y1 + NODE_R}" x2="{x2}" y2="{y2 - NODE_R}" '
            f'stroke="{color}" stroke-width="{stroke_w:.1f}" opacity="{opacity:.2f}" {dash}/>'
        )

    # Draw neurons
    for name, (x, y) in neuron_pos.items():
        neuron = all_neurons.get(name)
        value = neuron.value if neuron else 0.0
        short = name.split(".", 1)[1]
        is_dominant = (name == f"mood.{dominant}")

        # Node circle
        fill = _COLOR_DOMINANT if is_dominant else _value_color(value)
        stroke = "#FFFFFF" if is_dominant else fill
        stroke_w = 3 if is_dominant else 1.5
        r = NODE_R + 4 if is_dominant else NODE_R
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_w}" opacity="0.9"/>'
        )

        # Value text inside circle
        parts.append(
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" fill="{_BG_COLOR}" '
            f'font-size="10" font-family="monospace" font-weight="bold">'
            f'{value:.1f}</text>'
        )

        # Label below
        parts.append(
            f'<text x="{x}" y="{y + r + 14}" text-anchor="middle" fill="{_TEXT_COLOR}" '
            f'font-size="9" font-family="monospace">{short}</text>'
        )

    # Title
    mood_text = f"Mood: {dominant}" if dominant else "No evaluation"
    conf_text = f" ({result.mood_confidence:.0%})" if result else ""
    parts.append(
        f'<text x="{SVG_W // 2}" y="{SVG_H - 10}" text-anchor="middle" '
        f'fill="{_TEXT_COLOR}" font-size="12" font-family="monospace">'
        f'PilotSuite Styx Neural Pipeline — {mood_text}{conf_text}</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


# =============================================================================
# Synapse Configuration Endpoints (Iteration 2)
# =============================================================================

# Mutable synapse overrides (runtime adjustments persisted to JSON)
_synapse_overrides: Dict[str, float] = {}
_SYNAPSE_CONFIG_PATH = "/data/synapse_overrides.json"


def _load_synapse_overrides() -> None:
    """Load persisted synapse weight overrides."""
    global _synapse_overrides
    import json, os
    path = os.environ.get("SYNAPSE_CONFIG_PATH", _SYNAPSE_CONFIG_PATH)
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                _synapse_overrides = json.load(f)
            _LOGGER.info("Loaded %d synapse overrides from %s", len(_synapse_overrides), path)
    except Exception as e:
        _LOGGER.warning("Failed to load synapse overrides: %s", e)


def _save_synapse_overrides() -> None:
    """Persist synapse weight overrides to disk."""
    import json, os
    path = os.environ.get("SYNAPSE_CONFIG_PATH", _SYNAPSE_CONFIG_PATH)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(_synapse_overrides, f, indent=2)
    except Exception as e:
        _LOGGER.warning("Failed to save synapse overrides: %s", e)


def get_effective_synapse_weight(from_id: str, to_id: str) -> float:
    """Get effective synapse weight (override or default)."""
    key = f"{from_id}->{to_id}"
    if key in _synapse_overrides:
        return _synapse_overrides[key]
    for frm, to, w in SYNAPSE_TOPOLOGY:
        if frm == from_id and to == to_id:
            return w
    return 0.0


def get_all_synapses() -> List[Dict[str, Any]]:
    """Get all synapses with effective weights."""
    synapses = []
    for frm, to, default_w in SYNAPSE_TOPOLOGY:
        key = f"{frm}->{to}"
        effective = _synapse_overrides.get(key, default_w)
        synapses.append({
            "from": frm,
            "to": to,
            "default_weight": default_w,
            "weight": effective,
            "overridden": key in _synapse_overrides,
        })
    return synapses


@neuron_layers_bp.route("/synapses", methods=["GET"])
def list_synapses():
    """List all synapses with current and default weights."""
    return jsonify({
        "success": True,
        "data": get_all_synapses(),
        "count": len(SYNAPSE_TOPOLOGY),
    })


@neuron_layers_bp.route("/synapses/update", methods=["POST"])
def update_synapse_weight():
    """Update a synapse weight.

    JSON body:
        {"from": "context.presence", "to": "mood.active", "weight": 0.5}
    """
    from flask import request as req
    body = req.get_json(silent=True) or {}
    from_id = str(body.get("from", "")).strip()
    to_id = str(body.get("to", "")).strip()
    weight = body.get("weight")

    if not from_id or not to_id or weight is None:
        return jsonify({"success": False, "error": "Missing from, to, or weight"}), 400

    try:
        weight = float(weight)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "weight must be a number"}), 400

    if not -1.0 <= weight <= 1.0:
        return jsonify({"success": False, "error": "weight must be between -1.0 and 1.0"}), 400

    # Verify synapse exists in topology
    found = any(frm == from_id and to == to_id for frm, to, _ in SYNAPSE_TOPOLOGY)
    if not found:
        return jsonify({"success": False, "error": f"Synapse {from_id} -> {to_id} not found"}), 404

    key = f"{from_id}->{to_id}"
    _synapse_overrides[key] = weight
    _save_synapse_overrides()

    _LOGGER.info("Updated synapse %s -> %s weight to %.3f", from_id, to_id, weight)

    return jsonify({
        "success": True,
        "data": {
            "from": from_id,
            "to": to_id,
            "weight": weight,
            "default_weight": next(w for f, t, w in SYNAPSE_TOPOLOGY if f == from_id and t == to_id),
        },
    })


@neuron_layers_bp.route("/synapses/reset", methods=["POST"])
def reset_synapse_weight():
    """Reset a synapse weight to default.

    JSON body:
        {"from": "context.presence", "to": "mood.active"}
    Or reset all:
        {"all": true}
    """
    from flask import request as req
    body = req.get_json(silent=True) or {}

    if body.get("all"):
        count = len(_synapse_overrides)
        _synapse_overrides.clear()
        _save_synapse_overrides()
        return jsonify({"success": True, "data": {"reset_count": count}})

    from_id = str(body.get("from", "")).strip()
    to_id = str(body.get("to", "")).strip()
    if not from_id or not to_id:
        return jsonify({"success": False, "error": "Missing from or to"}), 400

    key = f"{from_id}->{to_id}"
    if key in _synapse_overrides:
        del _synapse_overrides[key]
        _save_synapse_overrides()

    return jsonify({"success": True, "data": {"from": from_id, "to": to_id, "reset": True}})


# Load overrides on module import
_load_synapse_overrides()
