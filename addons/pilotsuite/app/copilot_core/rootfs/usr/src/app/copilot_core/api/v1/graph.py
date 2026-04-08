from __future__ import annotations

import time
import hashlib
import json
from flask import Blueprint, jsonify, make_response, request

from copilot_core.brain_graph.provider import get_graph_service
from copilot_core.performance import brain_graph_cache

bp = Blueprint("graph", __name__, url_prefix="/graph")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


def _svc():
    return get_graph_service()


def _compute_cache_key(prefix: str, **params) -> str:
    """Compute a deterministic cache key from parameters."""
    sorted_params = json.dumps(params, sort_keys=True, default=str)
    content = f"{prefix}:{sorted_params}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@bp.get("/state")
def graph_state():
    # Multi-value query params: kind=...&kind=...
    kinds = request.args.getlist("kind")
    domains = request.args.getlist("domain")
    center = request.args.get("center")

    try:
        hops = int(request.args.get("hops", "1"))
    except Exception:
        hops = 1

    try:
        limit_nodes = int(request.args.get("limitNodes", request.args.get("limit_nodes", "200")))
    except Exception:
        limit_nodes = 200

    try:
        limit_edges = int(request.args.get("limitEdges", request.args.get("limit_edges", "400")))
    except Exception:
        limit_edges = 400

    # Server-side caps: tighter than storage maxima by default.
    limit_nodes = max(1, min(limit_nodes, 500))
    limit_edges = max(1, min(limit_edges, 1500))
    hops = max(0, min(hops, 2))

    # Check cache bypass
    nocache = request.args.get('nocache', '0') == '1'
    
    # Compute cache key
    cache_key = _compute_cache_key(
        "graph_state",
        kinds=kinds,
        domains=domains,
        center=center,
        hops=hops,
        limit_nodes=limit_nodes,
        limit_edges=limit_edges
    )
    
    # Try cache first (unless nocache)
    if not nocache:
        cached_result = brain_graph_cache.get(cache_key)
        if cached_result is not None:
            # Copy to avoid mutating shared cached dict across threads
            result = {**cached_result, "_cached": True}
            return jsonify(result)

    # Convert query params to match BrainGraphService.get_graph_state signature
    kinds = [k for k in kinds if isinstance(k, str)]
    domains = [d for d in domains if isinstance(d, str)]
    
    state = _svc().get_graph_state(
        kinds=kinds if kinds else None,
        domains=domains if domains else None,
        center_node=center if center else None,
        hops=hops,
        limit_nodes=limit_nodes,
        limit_edges=limit_edges,
    )
    
    # Cache the result
    brain_graph_cache.set(cache_key, state, ttl=30.0)
    state["_cached"] = False
    
    return jsonify(state)


@bp.get("/stats")
def graph_stats():
    """Graph statistics for health checks."""
    # Get cache stats
    cache_stats = brain_graph_cache.get_stats()
    
    state = _svc().get_graph_state(limit_nodes=1, limit_edges=1)
    return jsonify({
        "version": 1,
        "ok": True,
        "nodes": len(state.get("nodes", [])),
        "edges": len(state.get("edges", [])),
        "updated_at_ms": state.get("generated_at_ms", 0),
        "limits": state.get("limits", {}),
        "cache": {
            "enabled": brain_graph_cache.enabled,
            "size": cache_stats["size"],
            "max_size": cache_stats["max_size"],
            "hits": cache_stats["hits"],
            "misses": cache_stats["misses"],
            "hit_rate": round(cache_stats["hit_rate"], 3),
        }
    })


@bp.get("/patterns")
def graph_patterns():
    """Pattern summary for health checks."""
    patterns = _svc().infer_patterns()
    return jsonify({
        "version": 1,
        "ok": True,
        "generated_at_ms": int(time.time() * 1000),
        "patterns": patterns
    })


@bp.get("/snapshot.svg")
def graph_snapshot_svg():
    """Generate a live SVG visualization of the brain graph."""
    import math

    state = _svc().get_graph_state(limit_nodes=60, limit_edges=120)
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])

    if not nodes:
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="120">\n'
            '  <rect width="100%" height="100%" fill="#111"/>\n'
            '  <text x="20" y="60" fill="#aaa" font-family="monospace" font-size="14">'
            'Brain Graph: no nodes yet</text>\n'
            '</svg>\n'
        )
        resp = make_response(svg, 200)
        resp.headers["Content-Type"] = "image/svg+xml; charset=utf-8"
        return resp

    W, H = 800, 600
    # Assign positions in a circle layout
    node_pos = {}
    cx, cy, r = W / 2, H / 2, min(W, H) / 2 - 60
    for i, node in enumerate(nodes):
        angle = 2 * math.pi * i / len(nodes)
        node_pos[node["id"]] = (cx + r * math.cos(angle), cy + r * math.sin(angle))

    kind_colors = {
        "entity": "#4fc3f7", "zone": "#81c784", "service": "#ffb74d",
        "action": "#ff8a65", "state": "#ce93d8",
    }

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
        f'  <rect width="100%" height="100%" fill="#1a1a2e"/>',
    ]

    # Draw edges
    for edge in edges:
        src = node_pos.get(edge.get("from"))
        tgt = node_pos.get(edge.get("to"))
        if src and tgt:
            parts.append(
                f'  <line x1="{src[0]:.0f}" y1="{src[1]:.0f}" '
                f'x2="{tgt[0]:.0f}" y2="{tgt[1]:.0f}" '
                f'stroke="#334" stroke-width="1" opacity="0.6"/>'
            )

    # Draw nodes
    for node in nodes:
        pos = node_pos.get(node["id"])
        if not pos:
            continue
        kind = node.get("kind", "entity")
        color = kind_colors.get(kind, "#888")
        label = node.get("label", node["id"])[:16]
        parts.append(
            f'  <circle cx="{pos[0]:.0f}" cy="{pos[1]:.0f}" r="6" fill="{color}"/>'
        )
        parts.append(
            f'  <text x="{pos[0] + 8:.0f}" y="{pos[1] + 4:.0f}" fill="#ccc" '
            f'font-family="monospace" font-size="9">{label}</text>'
        )

    # Legend
    parts.append(f'  <text x="10" y="{H - 10}" fill="#555" font-family="monospace" font-size="10">'
                 f'Nodes: {len(nodes)} | Edges: {len(edges)}</text>')
    parts.append('</svg>')

    resp = make_response("\n".join(parts), 200)
    resp.headers["Content-Type"] = "image/svg+xml; charset=utf-8"
    return resp


@bp.post("/cache/clear")
def clear_cache():
    """Clear graph cache."""
    brain_graph_cache.clear()
    return jsonify({
        "ok": True,
        "message": "Cache cleared",
        "timestamp_ms": int(time.time() * 1000)
    })
