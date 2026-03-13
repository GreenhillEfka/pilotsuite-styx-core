"""
Neuron Layer SVG Renderer.

Renders the 3-layer neural pipeline (Context → State → Mood) as an SVG image.
This module provides a layer-aware visualization that shows:
- All neurons grouped by layer with value-based coloring
- Synaptic connections with signal strength visualization
- Dominant mood highlighting
- Meta-module status overlays (Habitus, BrainGraph, Calendar)

Used by:
    GET /api/v1/neurons/layers/snapshot.svg
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# ── Color palette ──────────────────────────────────────────────────────────
_COLOR_INACTIVE = "#9CA3AF"   # gray-400
_COLOR_LOW = "#34D399"        # emerald-400
_COLOR_MID = "#FBBF24"        # amber-400
_COLOR_HIGH = "#F87171"       # red-400
_COLOR_DOMINANT = "#8B5CF6"   # violet-500
_BG_COLOR = "#1F2937"         # gray-800
_TEXT_COLOR = "#F9FAFB"       # gray-50
_LAYER_BG = "#374151"         # gray-700
_META_COLOR = "#6366F1"       # indigo-500
_FEEDBACK_COLOR = "#F59E0B"   # amber-500

# ── Default synapse topology ──────────────────────────────────────────────
# Imported from neuron_layers to stay DRY; can be called standalone too.
_DEFAULT_TOPOLOGY: List[tuple[str, str, float]] = []


def _ensure_topology() -> List[tuple[str, str, float]]:
    """Lazy-load topology from neuron_layers module."""
    global _DEFAULT_TOPOLOGY
    if not _DEFAULT_TOPOLOGY:
        try:
            from copilot_core.api.v1.neuron_layers import SYNAPSE_TOPOLOGY
            _DEFAULT_TOPOLOGY = list(SYNAPSE_TOPOLOGY)
        except ImportError:
            _DEFAULT_TOPOLOGY = []
    return _DEFAULT_TOPOLOGY


def value_color(value: float) -> str:
    """Map a 0..1 neuron value to a display color."""
    if value < 0.01:
        return _COLOR_INACTIVE
    if value < 0.4:
        return _COLOR_LOW
    if value < 0.7:
        return _COLOR_MID
    return _COLOR_HIGH


def render_neuron_layer_svg(
    all_neurons: dict,
    result: Any,
    *,
    topology: Optional[List[tuple[str, str, float]]] = None,
    meta_modules: Optional[List[Dict[str, Any]]] = None,
    width: int = 900,
    show_meta: bool = True,
) -> str:
    """
    Render the full neuron pipeline as an SVG.

    Args:
        all_neurons: dict[str, Neuron] keyed by full name (e.g. "context.presence").
        result: NeuronEvaluationResult (or None).
        topology: Optional synapse list; defaults to SYNAPSE_TOPOLOGY.
        meta_modules: Optional list of meta-module dicts
                      [{"id": ..., "state": ..., "layer": 3, ...}].
        width: SVG width in pixels.
        show_meta: Whether to render a Layer 3 meta-module row.

    Returns:
        Complete SVG string.
    """
    topo = topology or _ensure_topology()

    # ── Layout constants ──────────────────────────────────────────────
    SVG_W = width
    LAYER_H = 100
    LAYER_GAP = 80
    PADDING = 40
    NODE_R = 20

    # ── Group neurons by layer prefix ─────────────────────────────────
    layers: Dict[str, List[str]] = {"context": [], "state": [], "mood": []}
    for name in sorted(all_neurons.keys()):
        prefix = name.split(".")[0]
        if prefix in layers:
            layers[prefix].append(name)

    layer_order = ["context", "state", "mood"]

    # ── Optionally include meta-module layer ──────────────────────────
    has_meta = show_meta and meta_modules
    total_layers = len(layer_order) + (1 if has_meta else 0)

    # ── Y positions ───────────────────────────────────────────────────
    layer_y: Dict[str, int] = {}
    for i, ln in enumerate(layer_order):
        layer_y[ln] = PADDING + i * (LAYER_H + LAYER_GAP) + LAYER_H // 2

    if has_meta:
        layer_y["meta"] = PADDING + len(layer_order) * (LAYER_H + LAYER_GAP) + LAYER_H // 2

    SVG_H = PADDING * 2 + total_layers * LAYER_H + (total_layers - 1) * LAYER_GAP

    # ── X positions ───────────────────────────────────────────────────
    neuron_pos: Dict[str, tuple[int, int]] = {}
    for ln in layer_order:
        neurons = layers[ln]
        n = len(neurons)
        if n == 0:
            continue
        spacing = (SVG_W - 2 * PADDING) / max(n, 1)
        for j, name in enumerate(neurons):
            x = int(PADDING + spacing * (j + 0.5))
            neuron_pos[name] = (x, layer_y[ln])

    # ── Meta-module positions ─────────────────────────────────────────
    meta_pos: Dict[str, tuple[int, int]] = {}
    if has_meta and meta_modules:
        n = len(meta_modules)
        spacing = (SVG_W - 2 * PADDING) / max(n, 1)
        for j, mod in enumerate(meta_modules):
            x = int(PADDING + spacing * (j + 0.5))
            meta_pos[mod["id"]] = (x, layer_y["meta"])

    # ── Dominant mood ─────────────────────────────────────────────────
    dominant = result.dominant_mood if result else ""

    # ── Build SVG ─────────────────────────────────────────────────────
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" '
        f'viewBox="0 0 {SVG_W} {SVG_H}">',
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="{_BG_COLOR}" rx="8"/>',
    ]

    # Layer backgrounds
    labels = ["Layer 0: Context", "Layer 1: State", "Layer 2: Mood"]
    if has_meta:
        labels.append("Layer 3: Meta-Modules")

    for i, label in enumerate(labels):
        ly = PADDING + i * (LAYER_H + LAYER_GAP)
        parts.append(
            f'<rect x="{PADDING // 2}" y="{ly}" width="{SVG_W - PADDING}" '
            f'height="{LAYER_H}" fill="{_LAYER_BG}" rx="6" opacity="0.5"/>'
        )
        parts.append(
            f'<text x="{PADDING}" y="{ly + 16}" fill="{_TEXT_COLOR}" '
            f'font-size="11" font-family="monospace" opacity="0.6">{label}</text>'
        )

    # ── Draw connections ──────────────────────────────────────────────
    for from_n, to_n, weight in topo:
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

    # ── Draw feedback loops (dashed amber lines from mood back to meta) ──
    if has_meta and meta_modules:
        for mod in meta_modules:
            if mod["id"] in meta_pos:
                mx, my = meta_pos[mod["id"]]
                # Draw a subtle feedback arc from meta to mood layer
                for mood_name in layers.get("mood", []):
                    if mood_name in neuron_pos:
                        nx, ny = neuron_pos[mood_name]
                        parts.append(
                            f'<path d="M{mx},{my - 15} Q{(mx + nx) // 2},{my - 50} {nx},{ny + NODE_R + 5}" '
                            f'fill="none" stroke="{_FEEDBACK_COLOR}" stroke-width="0.8" '
                            f'opacity="0.15" stroke-dasharray="3,4"/>'
                        )
                        break  # One feedback arc per module is enough

    # ── Draw neurons ──────────────────────────────────────────────────
    for name, (x, y) in neuron_pos.items():
        neuron = all_neurons.get(name)
        value = neuron.value if neuron else 0.0
        short = name.split(".", 1)[1]
        is_dominant = (name == f"mood.{dominant}")

        fill = _COLOR_DOMINANT if is_dominant else value_color(value)
        stroke = "#FFFFFF" if is_dominant else fill
        stroke_w = 3 if is_dominant else 1.5
        r = NODE_R + 4 if is_dominant else NODE_R
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_w}" opacity="0.9"/>'
        )
        parts.append(
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" fill="{_BG_COLOR}" '
            f'font-size="10" font-family="monospace" font-weight="bold">'
            f'{value:.1f}</text>'
        )
        parts.append(
            f'<text x="{x}" y="{y + r + 14}" text-anchor="middle" fill="{_TEXT_COLOR}" '
            f'font-size="9" font-family="monospace">{short}</text>'
        )

    # ── Draw meta-module boxes ────────────────────────────────────────
    if has_meta and meta_modules:
        for mod in meta_modules:
            mid = mod["id"]
            if mid not in meta_pos:
                continue
            x, y = meta_pos[mid]
            state = mod.get("state", "unknown")
            is_active = state == "active"
            box_fill = _META_COLOR if is_active else _COLOR_INACTIVE
            box_opacity = 0.9 if is_active else 0.5

            # Rectangle instead of circle
            bw, bh = 80, 36
            parts.append(
                f'<rect x="{x - bw // 2}" y="{y - bh // 2}" width="{bw}" height="{bh}" '
                f'rx="6" fill="{box_fill}" opacity="{box_opacity}"/>'
            )
            # Module name
            short = mid.split(".")[-1] if "." in mid else mid
            parts.append(
                f'<text x="{x}" y="{y + 4}" text-anchor="middle" fill="{_TEXT_COLOR}" '
                f'font-size="9" font-family="monospace">{short}</text>'
            )
            # State indicator below
            parts.append(
                f'<text x="{x}" y="{y + bh // 2 + 12}" text-anchor="middle" '
                f'fill="{_TEXT_COLOR}" font-size="8" font-family="monospace" '
                f'opacity="0.6">{state}</text>'
            )

    # ── Title bar ─────────────────────────────────────────────────────
    mood_text = f"Mood: {dominant}" if dominant else "No evaluation"
    conf_text = f" ({result.mood_confidence:.0%})" if result else ""
    parts.append(
        f'<text x="{SVG_W // 2}" y="{SVG_H - 10}" text-anchor="middle" '
        f'fill="{_TEXT_COLOR}" font-size="12" font-family="monospace">'
        f'PilotSuite Styx Neural Pipeline — {mood_text}{conf_text}</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def render_placeholder_svg(message: str, width: int = 800, height: int = 200) -> str:
    """Render a placeholder/error SVG."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="{_BG_COLOR}"/>'
        f'<text x="{width // 2}" y="{height // 2}" text-anchor="middle" '
        f'fill="{_TEXT_COLOR}" font-size="16" font-family="monospace">{message}</text>'
        f'</svg>'
    )
