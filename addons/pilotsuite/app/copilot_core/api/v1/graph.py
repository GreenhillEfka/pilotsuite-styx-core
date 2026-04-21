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
        "edges": [{"from": e["from"], "to": e["to"]} for e in edges],
    })

@bp.get("/snapshot-legacy.svg")
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


# ---------------------------------------------------------------------------
# F4.4 — Brain Graph Export & Snapshots
# Full-state export + neuron summary + anomaly export
# ---------------------------------------------------------------------------

@bp.get("/export")
def graph_export():
    """Export the current brain graph state as JSON.

    Returns the full node + edge set with metadata, scores, and
    timestamps. Use this for backup, debugging, or downstream consumers.

    Query params:
        format: json (default, only json for now)
        nodes: max nodes to include (default 500, max 2000)
        edges: max edges to include (default 1000, max 4000)
    """
    try:
        limit_nodes = min(2000, max(1, int(request.args.get("nodes", 500))))
        limit_edges = min(4000, max(1, int(request.args.get("edges", 1000))))
    except (ValueError, TypeError):
        limit_nodes, limit_edges = 500, 1000

    state = _svc().get_graph_state(
        limit_nodes=limit_nodes,
        limit_edges=limit_edges,
    )

    return jsonify({
        "ok": True,
        "exported_at_ms": int(time.time() * 1000),
        "nodes": state.get("nodes", []),
        "edges": state.get("edges", []),
        "node_count": len(state.get("nodes", [])),
        "edge_count": len(state.get("edges", [])),
    })


@bp.get("/neuron-summary")
def graph_neuron_summary():
    """Compact neuron summary for dashboard consumption.

    Returns one entry per unique node kind + domain, with aggregated
    node count, average score, and last-updated timestamp.
    Used by the dashboard neuron panel.
    """
    state = _svc().get_graph_state(limit_nodes=2000, limit_edges=4000)
    nodes = state.get("nodes", [])

    summary: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        kind = node.get("kind", "unknown")
        domain = node.get("domain", "unknown")
        key = f"{kind}:{domain}"
        if key not in summary:
            summary[key] = {
                "kind": kind,
                "domain": domain,
                "count": 0,
                "score_sum": 0.0,
                "updated_at_ms_min": None,
                "updated_at_ms_max": None,
            }
        s = summary[key]
        s["count"] += 1
        s["score_sum"] += node.get("score", 0.0)
        ms = node.get("updated_at_ms", 0)
        if ms:
            if s["updated_at_ms_min"] is None or ms < s["updated_at_ms_min"]:
                s["updated_at_ms_min"] = ms
            if s["updated_at_ms_max"] is None or ms > s["updated_at_ms_max"]:
                s["updated_at_ms_max"] = ms

    result = []
    for key, s in summary.items():
        avg_score = s["score_sum"] / s["count"] if s["count"] else 0.0
        result.append({
            "kind": s["kind"],
            "domain": s["domain"],
            "count": s["count"],
            "avg_score": round(avg_score, 3),
            "last_updated_ms": s["updated_at_ms_max"],
            "oldest_node_ms": s["updated_at_ms_min"],
        })

    result.sort(key=lambda x: x["count"], reverse=True)
    return jsonify({
        "ok": True,
        "neuron_groups": result,
        "total_nodes": len(nodes),
    })


@bp.get("/export/anomalies")
def graph_export_anomalies():
    """Export full anomaly history as JSON for external consumers.

    Query params:
        sensor_id: filter by sensor (optional)
        level: minimum level (low/medium/high/critical)
        format: json (default)
    """
    sensor_id = request.args.get("sensor_id")
    min_level = request.args.get("level", "low")
    level_map = {"normal": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    min_idx = level_map.get(min_level, 1)
    limit = min(200, max(1, int(request.args.get("limit", 100))))

    try:
        from copilot_core.ml.anomaly_detector import AnomalyDetector, AnomalyConfig
        detector = AnomalyDetector(config=AnomalyConfig())
        history = detector.get_anomaly_history(sensor_id=sensor_id, limit=limit)
    except Exception:
        history = []

    filtered = []
    for r in history:
        if level_map.get(r.level.value, 0) >= min_idx:
            filtered.append(r.to_dict())

    return jsonify({
        "ok": True,
        "exported_at_ms": int(time.time() * 1000),
        "anomaly_count": len(filtered),
        "filter": {"sensor_id": sensor_id, "level": min_level},
        "anomalies": filtered,
    })


@bp.get("/snapshot.svg")
def graph_snapshot_svg():
    """Enhanced SVG brain graph with anomaly overlay (F4.4).

    Renders nodes with color-coded anomaly scores and provides
    a visual summary layer for the dashboard.
    """
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

    W, H = 900, 640
    node_pos = {}
    cx, cy, r = W / 2, H / 2, min(W, H) / 2 - 60
    for i, node in enumerate(nodes):
        angle = 2 * math.pi * i / len(nodes)
        node_pos[node["id"]] = (cx + r * math.cos(angle), cy + r * math.sin(angle))

    kind_colors = {
        "entity": "#4fc3f7", "zone": "#81c784", "device": "#ffb74d",
        "service": "#ff8a65", "action": "#ce93d8", "concept": "#90a4ae",
        "person": "#f48fb1", "module": "#80cbc4", "event": "#ffd54f",
    }

    def _score_to_color(score: float) -> str:
        """Color-code by anomaly score."""
        if score <= -0.8:
            return "#ef5350"  # critical - red
        elif score <= -0.6:
            return "#ff7043"  # high - orange
        elif score <= -0.3:
            return "#ffca28"  # medium - yellow
        elif score <= 0.1:
            return "#66bb6a"  # low/normal - green
        else:
            return "#42a5f5"  # positive - blue

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
        f'  <rect width="100%" height="100%" fill="#0d1117"/>',
    ]

    # Draw edges
    for edge in edges:
        src = node_pos.get(edge.get("from") or edge.get("from_node"))
        tgt = node_pos.get(edge.get("to") or edge.get("to_node"))
        if src and tgt:
            parts.append(
                f'  <line x1="{src[0]:.0f}" y1="{src[1]:.0f}" '
                f'x2="{tgt[0]:.0f}" y2="{tgt[1]:.0f}" '
                f'stroke="#263850" stroke-width="1" opacity="0.7"/>'
            )

    # Count anomaly nodes for overlay badge
    anomaly_count = sum(
        1 for n in nodes if n.get("meta", {}).get("anomaly_score") is not None
    )

    # Draw nodes
    for node in nodes:
        pos = node_pos.get(node["id"])
        if not pos:
            continue
        meta = node.get("meta", {})
        anomaly_score = meta.get("anomaly_score")
        kind = node.get("kind", "entity")
        base_color = kind_colors.get(kind, "#78909c")
        label = node.get("label", node["id"])[:16]

        if anomaly_score is not None:
            node_color = _score_to_color(anomaly_score)
            glow_r = 10
            parts.append(
                f'  <circle cx="{pos[0]:.0f}" cy="{pos[1]:.0f}" r="{glow_r}" '
                f'fill="{node_color}" opacity="0.3"/>'
            )
        else:
            node_color = base_color

        parts.append(
            f'  <circle cx="{pos[0]:.0f}" cy="{pos[1]:.0f}" r="6" fill="{node_color}"/>'
        )
        parts.append(
            f'  <text x="{pos[0] + 8:.0f}" y="{pos[1] + 4:.0f}" fill="#ccc" '
            f'font-family="monospace" font-size="9">{label}</text>'
        )

    # Status bar
    parts.append(
        f'  <text x="10" y="{H - 30}" fill="#7f8c8d" font-family="monospace" font-size="10">'
        f'Neuronen: {len(nodes)} | Kanten: {len(edges)} | Anomalien: {anomaly_count}</text>'
    )
    parts.append(
        f'  <text x="10" y="{H - 10}" fill="#555" font-family="monospace" font-size="9">'
        f'PilotSuite Brain Graph {int(time.time())} | F4.4</text>'
    )
    parts.append('</svg>')

    resp = make_response("\n".join(parts), 200)
    resp.headers["Content-Type"] = "image/svg+xml; charset=utf-8"
    return resp


# ---------------------------------------------------------------------------
# F4.5 — Proactive Engine e2e Kabelung
# Anomaly → Proactive Context → Suggestion → Automation Trigger
# ---------------------------------------------------------------------------

@bp.get("/suggestions")
def graph_suggestions():
    """Return current proactive suggestions driven by brain graph state.

    This endpoint combines:
    - Brain graph node state
    - Active anomaly alerts
    - Zone/presence context
    - Habit patterns

    Into actionable suggestions for the user.

    Query params:
        zone: filter by zone_id (optional)
        type: filter by suggestion type (optional)
        limit: max suggestions (default 10)
    """
    from copilot_core.proactive_engine import ProactiveContextEngine

    try:
        limit = min(50, max(1, int(request.args.get("limit", 10))))
    except (ValueError, TypeError):
        limit = 10

    zone_filter = request.args.get("zone")
    type_filter = request.args.get("type")

    # Build context from brain graph
    svc = _svc()
    state = svc.get_graph_state(limit_nodes=500, limit_edges=1000)
    nodes = state.get("nodes", [])

    # --- Inject anomalies into proactive context ---
    pe = ProactiveContextEngine()

    # Push anomaly context
    anomaly_nodes = [
        n for n in nodes
        if n.get("meta", {}).get("anomaly_score") is not None
    ]
    for n in anomaly_nodes:
        score = n["meta"].get("anomaly_score", 0.0)
        severity = "critical" if score < -0.8 else "high" if score < -0.6 else "warning"
        pe.add_context("anomaly", {
            "entity_id": n["id"],
            "kind": n.get("kind", "unknown"),
            "score": score,
            "severity": severity,
            "label": n.get("label", n["id"]),
            "zone_id": n.get("meta", {}).get("zone_id"),
        })

    # Push zone context
    zone_nodes = [n for n in nodes if n.get("kind") == "zone"]
    for z in zone_nodes:
        pe.add_context("zone", {
            "zone_id": z["id"],
            "label": z.get("label", z["id"]),
            "score": z.get("score", 0.0),
            "node_data": z,
        })

    # --- Build evaluation context ---
    ctx = {
        "zone_id": zone_filter or "unknown",
        "persons_home": _extract_persons(nodes),
        "total_home": len(_extract_persons(nodes)),
    }
    if zone_filter:
        ctx["zone_id"] = zone_filter

    # --- Get suggestions from proactive engine ---
    all_suggestions = []
    try:
        all_suggestions = pe.get_suggestions(ctx)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "suggestions": []}), 500

    # Apply filters
    if zone_filter:
        all_suggestions = [s for s in all_suggestions if s.get("zone_id") == zone_filter or not s.get("zone_id")]
    if type_filter:
        all_suggestions = [s for s in all_suggestions if s.get("type") == type_filter]

    return jsonify({
        "ok": True,
        "count": len(all_suggestions),
        "anomaly_context_injected": len(anomaly_nodes),
        "zone_context_injected": len(zone_nodes),
        "suggestions": all_suggestions[:limit],
    })


def _extract_persons(nodes: list) -> list:
    """Extract person node IDs from brain graph."""
    return [n["id"] for n in nodes if n.get("kind") == "person"]


@bp.post("/trigger/automation")
def graph_trigger_automation():
    """Manually trigger an automation action based on brain graph state.

    This endpoint allows testing automation triggers and supports
    manual invocation of habit-based automations.

    Request body:
    {
        "trigger_type": "zone_entry | anomaly_detected | pattern_match | manual",
        "entity_id": "sensor.xxx",
        "zone_id": "zone.wohnzimmer",
        "action": "notify | adjust | query",
        "params": {}
    }
    """
    from copilot_core.proactive_engine import ProactiveContextEngine

    data = request.get_json() or {}
    trigger_type = data.get("trigger_type", "manual")
    entity_id = data.get("entity_id", "")
    zone_id = data.get("zone_id", "")
    action = data.get("action", "query")
    params = data.get("params", {})

    pe = ProactiveContextEngine()

    if trigger_type == "anomaly_detected" and entity_id:
        pe.add_context("anomaly", {
            "entity_id": entity_id,
            "triggered_by": "manual_api",
            "zone_id": zone_id,
            "params": params,
        })
    elif trigger_type == "zone_entry" and entity_id and zone_id:
        pe.on_zone_entry(entity_id, zone_id)
    elif trigger_type == "pattern_match" and entity_id:
        pe.add_context("pattern", {
            "entity_id": entity_id,
            "params": params,
        })

    # Deliver the action
    if action == "notify":
        result = pe.deliver_suggestion({
            "type": trigger_type,
            "message": params.get("message", f"{trigger_type} triggered for {entity_id}"),
            "entity_id": entity_id,
        }, method="notification")
    elif action == "adjust":
        result = pe.deliver_suggestion({
            "type": trigger_type,
            "message": f"Automation triggered: {entity_id}",
            "action_taken": params,
        }, method="notification")
    else:
        result = {"delivered": True, "method": action}

    return jsonify({
        "ok": True,
        "trigger_type": trigger_type,
        "entity_id": entity_id,
        "action": action,
        "result": result,
    })


@bp.get("/context/buckets")
def graph_context_buckets():
    """Show what context buckets are currently active in the proactive engine.

    Returns the live context store showing which signals are currently
    influencing suggestions. Useful for debugging the e2e chain.
    """
    from copilot_core.proactive_engine import ProactiveContextEngine

    pe = ProactiveContextEngine()
    buckets = {}
    try:
        for key, entries in pe._context_store.items():
            buckets[key] = {
                "count": len(entries),
                "latest_ts": max((e.get("ts", 0) for e in entries), default=0),
                "sample": entries[-1] if entries else None,
            }
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({
        "ok": True,
        "buckets": buckets,
        "ttl_seconds": pe.CONTEXT_TTL_SECONDS,
    })


# ---------------------------------------------------------------------------
# F4.5 — Proactive Engine e2e Kabelung
# Anomaly → Proactive Context → Suggestion → Automation Trigger
# ---------------------------------------------------------------------------

@bp.get("/suggestions")
def graph_suggestions():
    """Return current proactive suggestions driven by brain graph state.

    Combines brain graph node state, active anomaly alerts, zone/presence
    context, and habit patterns into actionable suggestions.
    """
    from copilot_core.proactive_engine import ProactiveContextEngine

    try:
        limit = min(50, max(1, int(request.args.get("limit", 10))))
    except (ValueError, TypeError):
        limit = 10

    zone_filter = request.args.get("zone")
    type_filter = request.args.get("type")

    svc = _svc()
    state = svc.get_graph_state(limit_nodes=500, limit_edges=1000)
    nodes = state.get("nodes", [])

    pe = ProactiveContextEngine()

    # Push anomaly context from brain graph nodes
    anomaly_nodes = [n for n in nodes if n.get("meta", {}).get("anomaly_score") is not None]
    for n in anomaly_nodes:
        score = n["meta"].get("anomaly_score", 0.0)
        severity = "critical" if score < -0.8 else "high" if score < -0.6 else "warning"
        pe.add_context("anomaly", {
            "entity_id": n["id"],
            "kind": n.get("kind", "unknown"),
            "score": score,
            "severity": severity,
            "label": n.get("label", n["id"]),
            "zone_id": n.get("meta", {}).get("zone_id"),
        })

    # Push zone context
    for z in nodes:
        if z.get("kind") == "zone":
            pe.add_context("zone", {
                "zone_id": z["id"],
                "label": z.get("label", z["id"]),
                "score": z.get("score", 0.0),
            })

    ctx = {"zone_id": zone_filter or "unknown", "persons_home": _ep(nodes), "total_home": 0}
    if zone_filter:
        ctx["zone_id"] = zone_filter

    try:
        suggestions = pe.get_suggestions(ctx)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "suggestions": []}), 500

    if zone_filter:
        suggestions = [s for s in suggestions if not s.get("zone_id") or s.get("zone_id") == zone_filter]
    if type_filter:
        suggestions = [s for s in suggestions if s.get("type") == type_filter]

    return jsonify({
        "ok": True,
        "count": len(suggestions),
        "anomaly_context_injected": len(anomaly_nodes),
        "zone_context_injected": sum(1 for n in nodes if n.get("kind") == "zone"),
        "suggestions": suggestions[:limit],
    })


def _ep(nodes):
    """Extract person node IDs from brain graph."""
    return [n["id"] for n in nodes if n.get("kind") == "person"]


@bp.post("/trigger/automation")
def graph_trigger_automation():
    """Manually trigger an automation action."""
    from copilot_core.proactive_engine import ProactiveContextEngine

    data = request.get_json() or {}
    trigger_type = data.get("trigger_type", "manual")
    entity_id = data.get("entity_id", "")
    zone_id = data.get("zone_id", "")
    action = data.get("action", "query")
    params = data.get("params", {})

    pe = ProactiveContextEngine()

    if trigger_type == "anomaly_detected" and entity_id:
        pe.add_context("anomaly", {
            "entity_id": entity_id, "triggered_by": "manual_api",
            "zone_id": zone_id, "params": params,
        })
    elif trigger_type == "zone_entry" and entity_id and zone_id:
        pe.on_zone_entry(entity_id, zone_id)
    elif trigger_type == "pattern_match" and entity_id:
        pe.add_context("pattern", {"entity_id": entity_id, "params": params})

    if action == "notify":
        result = pe.deliver_suggestion({
            "type": trigger_type,
            "message": params.get("message", f"{trigger_type} for {entity_id}"),
            "entity_id": entity_id,
        }, method="notification")
    elif action == "adjust":
        result = pe.deliver_suggestion({
            "type": trigger_type, "message": f"Automation: {entity_id}",
            "action_taken": params,
        }, method="notification")
    else:
        result = {"delivered": True, "method": action}

    return jsonify({"ok": True, "trigger_type": trigger_type,
                    "entity_id": entity_id, "action": action, "result": result})


@bp.get("/context/buckets")
def graph_context_buckets():
    """Show live context buckets in the proactive engine."""
    from copilot_core.proactive_engine import ProactiveContextEngine

    pe = ProactiveContextEngine()
    buckets = {}
    try:
        for key, entries in pe._context_store.items():
            buckets[key] = {
                "count": len(entries),
                "latest_ts": max((e.get("ts", 0) for e in entries), default=0),
                "sample": entries[-1] if entries else None,
            }
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "buckets": buckets, "ttl_seconds": pe.CONTEXT_TTL_SECONDS})


# ---------------------------------------------------------------------------
# F4.6 — Automation Rule Engine API
# CRUD for rules + matcher evaluation endpoint
# ---------------------------------------------------------------------------

_rule_matcher: Optional["RuleMatcher"] = None
_rule_executor: Optional["RuleExecutor"] = None

def _get_rule_matcher() -> "RuleMatcher":
    global _rule_matcher
    if _rule_matcher is None:
        from copilot_core.autonomy.rule_engine import RuleMatcher
        _rule_matcher = RuleMatcher()
        _rule_matcher.load_defaults()
    return _rule_matcher

def _get_rule_executor() -> "RuleExecutor":
    global _rule_executor
    if _rule_executor is None:
        from copilot_core.autonomy.rule_engine import RuleExecutor
        _rule_executor = RuleExecutor()
    return _rule_executor


@bp.get("/automation/rules")
def list_automation_rules():
    """List all automation rules (F4.6)."""
    matcher = _get_rule_matcher()
    tag = request.args.get("tag")
    status = request.args.get("status")
    rules = matcher.list_rules(tag=tag, status=status)
    return jsonify({
        "ok": True,
        "count": len(rules),
        "rules": [r.to_dict() for r in rules],
    })


@bp.post("/automation/rules")
def create_automation_rule():
    """Create a new automation rule (F4.6)."""
    from copilot_core.autonomy.rule_engine import AutomationRule, RuleCondition, RuleAction, ConditionOp

    data = request.get_json() or {}
    rule_id = data.get("rule_id")
    if not rule_id:
        return jsonify({"ok": False, "error": "rule_id required"}), 400

    matcher = _get_rule_matcher()
    if rule_id in matcher._rules:
        return jsonify({"ok": False, "error": "rule_id already exists"}), 409

    conditions = []
    for c in data.get("conditions", []):
        op = ConditionOp(c.get("operator", "eq"))
        conditions.append(RuleCondition(field=c.get("field", ""), operator=op, value=c.get("value")))

    actions = []
    for a in data.get("actions", []):
        actions.append(RuleAction(
            action_type=a.get("action_type", "notify"),
            entity_id=a.get("entity_id", ""),
            params=a.get("params", {}),
        ))

    rule = AutomationRule(
        rule_id=rule_id,
        name=data.get("name", rule_id),
        description=data.get("description", ""),
        conditions=conditions,
        actions=actions,
        cooldown_seconds=data.get("cooldown_seconds", 60),
        require_all_conditions=data.get("require_all_conditions", True),
        tags=data.get("tags", []),
        priority=data.get("priority", 0),
    )
    matcher.add_rule(rule)
    return jsonify({"ok": True, "rule": rule.to_dict()})


@bp.get("/automation/rules/<rule_id>")
def get_automation_rule(rule_id: str):
    """Get a single rule by ID."""
    matcher = _get_rule_matcher()
    rule = matcher.get_rule(rule_id)
    if not rule:
        return jsonify({"ok": False, "error": "rule not found"}), 404
    return jsonify({"ok": True, "rule": rule.to_dict()})


@bp.delete("/automation/rules/<rule_id>")
def delete_automation_rule(rule_id: str):
    """Delete a rule."""
    matcher = _get_rule_matcher()
    removed = matcher.remove_rule(rule_id)
    if not removed:
        return jsonify({"ok": False, "error": "rule not found"}), 404
    return jsonify({"ok": True, "deleted": rule_id})


@bp.post("/automation/rules/<rule_id>/pause")
def pause_automation_rule(rule_id: str):
    """Pause a rule (F4.6)."""
    from copilot_core.autonomy.rule_engine import RuleStatus
    matcher = _get_rule_matcher()
    rule = matcher.get_rule(rule_id)
    if not rule:
        return jsonify({"ok": False, "error": "rule not found"}), 404
    rule.status = RuleStatus.PAUSED
    return jsonify({"ok": True, "rule_id": rule_id, "status": "paused"})


@bp.post("/automation/rules/<rule_id>/resume")
def resume_automation_rule(rule_id: str):
    """Resume a paused rule (F4.6)."""
    from copilot_core.autonomy.rule_engine import RuleStatus
    matcher = _get_rule_matcher()
    rule = matcher.get_rule(rule_id)
    if not rule:
        return jsonify({"ok": False, "error": "rule not found"}), 404
    rule.status = RuleStatus.ACTIVE
    return jsonify({"ok": True, "rule_id": rule_id, "status": "active"})


@bp.post("/automation/evaluate")
def evaluate_automation():
    """Evaluate all active rules against current context (F4.6).

    Builds context from brain graph + anomaly detector + proactive engine,
    runs the matcher, executes matched rules.
    """
    data = request.get_json() or {}
    override_ctx = data.get("context", {})

    svc = _svc()
    state = svc.get_graph_state(limit_nodes=500, limit_edges=1000)
    nodes = state.get("nodes", [])

    # Build context from brain graph
    ctx = dict(override_ctx)
    ctx["nodes"] = nodes
    ctx["node_count"] = len(nodes)
    ctx["evaluated_at_ms"] = int(time.time() * 1000)

    # Inject anomaly scores
    anomaly_nodes = [n for n in nodes if n.get("meta", {}).get("anomaly_score") is not None]
    if anomaly_nodes:
        ctx["anomaly"] = {
            "count": len(anomaly_nodes),
            "score": min((n["meta"]["anomaly_score"] for n in anomaly_nodes), default=0.0),
            "top_entity": anomaly_nodes[0]["id"] if anomaly_nodes else None,
        }

    # Inject zone context
    zones = {n["id"]: n for n in nodes if n.get("kind") == "zone"}
    ctx["zones"] = zones

    # Inject presence
    ctx["presence"] = {"persons_home": [n["id"] for n in nodes if n.get("kind") == "person"]}

    matcher = _get_rule_matcher()
    matched = matcher.match_all(ctx)

    executor = _get_rule_executor()
    results = []
    for rule in matched:
        result = executor.execute(rule, ctx)
        results.append(result)

    return jsonify({
        "ok": True,
        "context_keys": list(ctx.keys()),
        "rules_evaluated": len(matcher._rules),
        "rules_matched": len(matched),
        "executions": results,
    })


@bp.get("/automation/execution-log")
def get_execution_log():
    """Get the rule execution log (F4.6)."""
    executor = _get_rule_executor()
    limit = min(100, max(1, int(request.args.get("limit", 50))))
    return jsonify({
        "ok": True,
        "count": len(executor._execution_log),
        "log": executor.get_execution_log(limit=limit),
    })


# ---------------------------------------------------------------------------
# F6.1 — Habit/Zone Configuration API
# Zone-specific automation configuration + habitat settings
# ---------------------------------------------------------------------------

@bp.get("/zones/config")
def graph_zones_config():
    """Return all zone configurations with habitat settings (F6.1).

    Aggregates zone state from brain graph + habitus_zones.
    Each zone includes: id, kind, label, score, activity config, lighting prefs.
    """
    svc = _svc()
    state = svc.get_graph_state(limit_nodes=2000, limit_edges=4000)
    nodes = state.get("nodes", [])

    # Get zone nodes from brain graph
    zone_nodes = [n for n in nodes if n.get("kind") == "zone"]

    # Also pull from habitus_zones
    try:
        from copilot_core.homeassistant.habitus_zones import get_all_zones, HABITUS_ZONES
        habit_zones = get_all_zones()
    except Exception:
        habit_zones = {}

    result = []
    for z in zone_nodes:
        zone_id = z.get("id", "")
        zone_type = zone_id.split(".")[-1] if zone_id else zone_id
        # Look up habitus config
        habit = {}
        for hz_key, hz_val in habit_zones.items():
            if hz_key in zone_id or zone_id in hz_key:
                habit = {
                    "name_de": getattr(hz_val, "name_de", zone_id),
                    "name_en": getattr(hz_val, "name_en", zone_id),
                    "module_overrides": getattr(hz_val, "module_overrides", {}),
                }
                break

        # Extract activity + lighting config from meta
        meta = z.get("meta", {})
        habitat_config = meta.get("habitat_config", {})
        if not habitat_config:
            habitat_config = {
                "lighting": meta.get("preferred_lighting", "auto"),
                "temperature": meta.get("preferred_temp", 21.0),
                "activities": meta.get("activities", []),
            }

        result.append({
            "zone_id": zone_id,
            "label": z.get("label", zone_id),
            "kind": z.get("kind", "zone"),
            "score": z.get("score", 0.0),
            "updated_at_ms": z.get("updated_at_ms", 0),
            "habitus_type": zone_type,
            "habitat_config": habitat_config,
            "habitus_info": habit,
        })

    # Sort by label
    result.sort(key=lambda x: x.get("label", ""))
    return jsonify({
        "ok": True,
        "count": len(result),
        "zones": result,
    })


@bp.put("/zones/<zone_id>/habitat")
def graph_update_zone_habitat(zone_id: str):
    """Update the habitat configuration for a zone (F6.1).

    Request body:
    {
        "lighting": "bright" | "normal" | "dim" | "auto",
        "temperature": float,
        "activities": ["reading", "cooking", ...],
        "module_overrides": {"light": {...}}
    }
    """
    data = request.get_json() or {}
    habitat_config = {
        "lighting": data.get("lighting", "auto"),
        "temperature": data.get("temperature", 21.0),
        "activities": data.get("activities", []),
        "module_overrides": data.get("module_overrides", {}),
        "updated_at_ms": int(time.time() * 1000),
    }

    # Update in brain graph
    svc = _svc()
    try:
        svc.update_node(
            node_id=zone_id,
            meta_update={"habitat_config": habitat_config},
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    # Also inject into proactive engine
    try:
        from copilot_core.proactive_engine import ProactiveContextEngine
        pe = ProactiveContextEngine()
        pe.add_context("zone_habitat_update", {
            "zone_id": zone_id,
            "habitat_config": habitat_config,
        })
    except Exception:
        pass

    return jsonify({"ok": True, "zone_id": zone_id, "habitat_config": habitat_config})


@bp.get("/zones/<zone_id>/status")
def graph_zone_status(zone_id: str):
    """Get current status of a zone including devices, mood, and activity (F6.1)."""
    svc = _svc()
    state = svc.get_graph_state(limit_nodes=2000, limit_edges=4000)
    nodes = state.get("nodes", [])

    # Find the zone node
    zone_node = None
    for n in nodes:
        if n["id"] == zone_id:
            zone_node = n
            break

    if not zone_node:
        return jsonify({"ok": False, "error": "zone not found"}), 404

    # Find connected devices and entities
    edges = state.get("edges", [])
    connected_nodes = set()
    for e in edges:
        if e.get("from_node") == zone_id:
            connected_nodes.add(e.get("to_node"))
        if e.get("to_node") == zone_id:
            connected_nodes.add(e.get("from_node"))

    device_nodes = [n for n in nodes if n["id"] in connected_nodes and n.get("kind") == "device"]
    entity_nodes = [n for n in nodes if n["id"] in connected_nodes and n.get("kind") == "entity"]
    person_nodes = [n for n in nodes if n["id"] in connected_nodes and n.get("kind") == "person"]

    # Count anomalies in this zone
    zone_anomalies = [
        n for n in nodes
        if n.get("meta", {}).get("anomaly_score") is not None
        and n.get("meta", {}).get("zone_id") == zone_id
    ]

    return jsonify({
        "ok": True,
        "zone": {
            "zone_id": zone_node["id"],
            "label": zone_node.get("label", ""),
            "kind": zone_node.get("kind", "zone"),
            "score": zone_node.get("score", 0.0),
            "habitat_config": zone_node.get("meta", {}).get("habitat_config", {}),
            "updated_at_ms": zone_node.get("updated_at_ms", 0),
        },
        "devices": [{"id": d["id"], "label": d.get("label", ""), "score": d.get("score", 0.0)} for d in device_nodes],
        "entities": [{"id": e["id"], "label": e.get("label", ""), "kind": e.get("kind", "entity")} for e in entity_nodes],
        "persons": [{"id": p["id"], "label": p.get("label", "")} for p in person_nodes],
        "anomaly_count": len(zone_anomalies),
        "connected_count": len(connected_nodes),
    })


# ---------------------------------------------------------------------------
# F6.2 — Dashboard Widget Bundle
# Aggregated summary: PV + Anomalies + Automation + Brain Graph
# ---------------------------------------------------------------------------

@bp.get("/dashboard/summary")
def graph_dashboard_summary():
    """Aggregated dashboard summary for widget bundle (F6.2).

    Returns:
    - Brain graph state (nodes, edges, zones, devices)
    - Active anomalies (count + latest)
    - Active automation rules (count + triggered recently)
    - PV forecast summary (if available)
    - Proactive engine context buckets
    """
    svc = _svc()

    # --- Brain graph ---
    state = svc.get_graph_state(limit_nodes=1000, limit_edges=2000)
    nodes = state.get("nodes", [])
    edges = state.get("edges", [])
    zone_nodes = [n for n in nodes if n.get("kind") == "zone"]
    device_nodes = [n for n in nodes if n.get("kind") == "device"]

    # --- Anomalies ---
    try:
        from copilot_core.ml.anomaly_detector import AnomalyDetector, AnomalyConfig
        detector = AnomalyDetector(config=AnomalyConfig())
        history = detector.get_anomaly_history(limit=20)
        anomaly_entries = [r.to_dict() for r in history if r.is_anomaly]
    except Exception:
        anomaly_entries = []
        history = []

    # --- Automation rules ---
    matcher = _get_rule_matcher()
    active_rules = matcher.list_rules(status=None)
    triggered_recent = [
        r.to_dict() for r in active_rules
        if r.last_triggered_ms and (int(time.time() * 1000) - r.last_triggered_ms) < 3600000
    ]

    # --- PV forecast (best effort) ---
    pv_status = {}
    try:
        from copilot_core.energy.pv_prediction import PVPredictionEngine
        pv_engine = PVPredictionEngine()
        pv_state = pv_engine.get_current_state()
        if pv_state:
            pv_status = {
                "current_power_kw": pv_state.get("current_power_kw", 0),
                "peak_today_kw": pv_state.get("peak_today_kw", 0),
                "today_energy_wh": pv_state.get("today_energy_wh", 0),
            }
    except Exception:
        pv_status = {"available": False}

    # --- Proactive context ---
    try:
        from copilot_core.proactive_engine import ProactiveContextEngine
        pe = ProactiveContextEngine()
        context_keys = list(pe._context_store.keys()) if hasattr(pe, "_context_store") else []
        context_counts = {k: len(v) for k, v in pe._context_store.items()} if hasattr(pe, "_context_store") else {}
    except Exception:
        context_keys = []
        context_counts = {}

    # --- Execution log ---
    executor = _get_rule_executor()
    recent_executions = executor.get_execution_log(limit=5)

    return jsonify({
        "ok": True,
        "generated_at_ms": int(time.time() * 1000),
        "brain_graph": {
            "nodes": len(nodes),
            "edges": len(edges),
            "zones": len(zone_nodes),
            "devices": len(device_nodes),
        },
        "anomalies": {
            "active_count": len(anomaly_entries),
            "recent": anomaly_entries[:5],
        },
        "automation": {
            "total_rules": len(active_rules),
            "triggered_last_hour": len(triggered_recent),
            "recent_executions": recent_executions,
        },
        "pv": pv_status,
        "proactive_engine": {
            "context_buckets": context_keys,
            "context_counts": context_counts,
        },
    })
