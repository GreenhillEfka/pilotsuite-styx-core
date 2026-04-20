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
    except (ValueError, TypeError):
        hops = 1

    try:
        limit_nodes = int(request.args.get("limitNodes", request.args.get("limit_nodes", "200")))
    except (ValueError, TypeError):
        limit_nodes = 200

    try:
        limit_edges = int(request.args.get("limitEdges", request.args.get("limit_edges", "400")))
    except (ValueError, TypeError):
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


@bp.get("/topology")
def graph_topology():
    """Return simplified brain graph topology for dashboard visibility.

    Returns: nodes with kind/domain/label, edge pairs, node counts by kind.
    Lightweight — uses get_graph_state with capped limits.
    """
    state = _svc().get_graph_state(limit_nodes=100, limit_edges=200)
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])

    kind_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    for node in nodes:
        kind = node.get("kind", "unknown")
        domain = node.get("domain", "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    return jsonify({
        "ok": True,
        "version": 1,
        "generated_at_ms": int(time.time() * 1000),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes_by_kind": kind_counts,
        "nodes_by_domain": domain_counts,
        "nodes": [
            {"id": n["id"], "kind": n.get("kind"), "domain": n.get("domain"), "label": n.get("label", n["id"])}
            for n in nodes
        ],
        "edges": [{"from": e["from_node"], "to": e["to_node"]} for e in edges],
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
        src = node_pos.get(edge.get("from") or edge.get("from_node"))
        tgt = node_pos.get(edge.get("to") or edge.get("to_node"))
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


@bp.get("/sequences")
def graph_sequences():
    """Detect recurring temporal event sequences in the brain graph."""
    try:
        time_window = float(request.args.get("time_window_s", "30.0"))
    except (ValueError, TypeError):
        time_window = 30.0

    try:
        min_occ = int(request.args.get("min_occurrences", "3"))
    except (ValueError, TypeError):
        min_occ = 3

    # Clamp parameters to safe ranges
    time_window = max(1.0, min(time_window, 300.0))
    min_occ = max(1, min(min_occ, 50))

    try:
        sequences = _svc().detect_sequences(
            time_window_s=time_window,
            min_occurrences=min_occ,
        )
    except Exception:
        return jsonify({"ok": False, "error": "sequence detection failed"}), 500

    return jsonify({
        "ok": True,
        "generated_at_ms": int(time.time() * 1000),
        "params": {"time_window_s": time_window, "min_occurrences": min_occ},
        "sequences": sequences,
        "count": len(sequences),
    })


@bp.post("/cache/clear")
def clear_cache():
    """Clear graph cache."""
    brain_graph_cache.clear()
    return jsonify({
        "ok": True,
        "message": "Cache cleared",
        "timestamp_ms": int(time.time() * 1000)
    })


# ---------------------------------------------------------------------------
# F4.3 — Brain Graph Anomaly Detection
# Bridge: brain_graph service + anomaly_detector + proactive_engine
# ---------------------------------------------------------------------------

@bp.get("/anomalies")
def graph_anomalies():
    """Current anomalies from the ML anomaly detector.

    Returns active anomaly entries with level, score, sensor_id, and
    contributing features. Each can be acknowledged via
    POST /graph/anomalies/{idx}/acknowledge.

    Query params:
        level: minimum AnomalyLevel (normal/low/medium/high/critical)
        limit: max results (default 50)
    """
    try:
        from copilot_core.ml.anomaly_detector import AnomalyDetector, AnomalyConfig
    except Exception as e:
        return jsonify({"ok": False, "error": f"anomaly module unavailable: {e}"}), 503

    level_map = {"normal": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    min_level = level_map.get(request.args.get("level", "low"), 1)
    try:
        limit = min(200, max(1, int(request.args.get("limit", 50))))
    except (ValueError, TypeError):
        limit = 50

    detector = AnomalyDetector(config=AnomalyConfig())
    history = detector.get_anomaly_history(limit=limit * 2)

    filtered = []
    for r in history:
        if level_map.get(r.level.value, 0) >= min_level:
            filtered.append(r)
            if len(filtered) >= limit:
                break

    # Also pull anomaly-tagged nodes from brain graph
    svc = _svc()
    state = svc.get_graph_state(limit_nodes=300, limit_edges=600)
    nodes = state.get("nodes", [])
    anomaly_nodes = [
        n for n in nodes
        if n.get("meta", {}).get("anomaly_score") is not None
    ]
    for n in anomaly_nodes:
        score = n["meta"].get("anomaly_score", 0.0)
        level_str = "normal"
        if score < -0.9:
            level_str = "critical"
        elif score < -0.7:
            level_str = "high"
        elif score < -0.5:
            level_str = "medium"
        elif score < -0.3:
            level_str = "low"
        filtered.append(_bg_anomaly_from_node(score, level_str, n["id"], n.get("updated_at_ms", 0)))

    return jsonify({
        "ok": True,
        "count": len(filtered),
        "anomalies": [r.to_dict() for r in filtered[:limit]],
    })


def _bg_anomaly_from_node(score: float, level_str: str, sensor_id: str, updated_at_ms: int):
    """Build a lightweight anomaly-like object from a brain graph node."""
    iso = ""
    try:
        from datetime import datetime, timezone
        iso = datetime.fromtimestamp(updated_at_ms / 1000, tz=timezone.utc).isoformat()
    except Exception:
        iso = str(updated_at_ms)

    class _Obj:
        pass
    obj = _Obj()
    obj.score = score
    obj.level = type("_Lvl", (), {"value": level_str})()
    obj.sensor_id = sensor_id
    obj.timestamp = type("_Ts", (), {"isoformat": lambda s: iso})()
    obj.features = {}
    obj.contributing_features = []
    obj.is_anomaly = score < -0.3
    obj.to_dict = lambda self: {
        "score": self.score,
        "level": self.level.value,
        "sensor_id": self.sensor_id,
        "timestamp": self.timestamp.isoformat(),
        "features": self.features,
        "contributing_features": self.contributing_features,
        "is_anomaly": self.is_anomaly,
    }
    return obj


@bp.get("/anomalies/history")
def graph_anomalies_history():
    """Full anomaly history with optional sensor filter."""
    sensor_id = request.args.get("sensor_id")
    limit = min(200, max(1, int(request.args.get("limit", 100))))

    try:
        from copilot_core.ml.anomaly_detector import AnomalyDetector, AnomalyConfig
    except Exception:
        return jsonify({"ok": False, "anomalies": [], "count": 0})

    detector = AnomalyDetector(config=AnomalyConfig())
    history = detector.get_anomaly_history(sensor_id=sensor_id, limit=limit)

    seen = set()
    unique = []
    for r in history:
        key = (r.sensor_id, int(r.timestamp.timestamp()))
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return jsonify({
        "ok": True,
        "count": len(unique),
        "anomalies": [u.to_dict() for u in unique],
        "sensor_id": sensor_id,
    })


@bp.post("/anomalies/<int:anomaly_idx>/acknowledge")
def graph_anomalies_acknowledge(anomaly_idx: int):
    """Acknowledge and dismiss an anomaly entry (F4.3)."""
    svc = _svc()
    state = svc.get_graph_state(limit_nodes=500, limit_edges=1000)
    nodes = state.get("nodes", [])
    anomaly_nodes = [
        n for n in nodes
        if n.get("meta", {}).get("anomaly_score") is not None
    ]
    if anomaly_idx < 0 or anomaly_idx >= len(anomaly_nodes):
        return jsonify({"ok": False, "error": "anomaly index out of range"}), 404

    target = anomaly_nodes[anomaly_idx]
    node_id = target["id"]

    try:
        svc.update_node(
            node_id=node_id,
            meta_update={"anomaly_acknowledged": True, "acknowledged_at_ms": int(time.time() * 1000)},
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    try:
        from copilot_core.proactive_engine import ProactiveContextEngine
        pe = ProactiveContextEngine()
        pe.add_context("anomaly_acknowledged", {
            "entity_id": node_id,
            "idx": anomaly_idx,
            "ts": int(time.time()),
        })
    except Exception:
        pass

    return jsonify({"ok": True, "node_id": node_id, "acknowledged": True})


@bp.get("/e2e/status")
def graph_e2e_status():
    """End-to-end system status: brain graph + anomaly + proactive."""
    svc = _svc()
    state = svc.get_graph_state(limit_nodes=1000, limit_edges=2000)
    node_count = len(state.get("nodes", []))
    edge_count = len(state.get("edges", []))
    zone_nodes = [n for n in state.get("nodes", []) if n.get("kind") == "zone"]
    device_nodes = [n for n in state.get("nodes", []) if n.get("kind") == "device"]

    try:
        from copilot_core.ml.anomaly_detector import AnomalyDetector, AnomalyConfig
        detector = AnomalyDetector(config=AnomalyConfig())
        history = detector.get_anomaly_history(limit=100)
        anomaly_count = sum(1 for r in history if r.is_anomaly)
        last_anomaly = history[-1].to_dict() if history else None
    except Exception:
        anomaly_count = -1
        last_anomaly = None

    try:
        from copilot_core.proactive_engine import ProactiveContextEngine
        pe = ProactiveContextEngine()
        context_keys = list(pe._context_store.keys()) if hasattr(pe, "_context_store") else []
    except Exception:
        context_keys = []

    return jsonify({
        "ok": True,
        "brain_graph": {
            "nodes": node_count,
            "edges": edge_count,
            "zones": len(zone_nodes),
            "devices": len(device_nodes),
        },
        "anomaly_detector": {
            "active_anomalies": anomaly_count,
            "last_anomaly": last_anomaly,
        },
        "proactive_engine": {
            "context_buckets": context_keys,
        },
    })
