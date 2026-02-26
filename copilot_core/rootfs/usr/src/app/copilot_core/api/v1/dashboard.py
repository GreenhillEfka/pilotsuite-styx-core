"""Dashboard API endpoints.

Provides data for Home Assistant dashboard displays.
"""

from flask import Blueprint, jsonify, request

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


def _now_iso() -> str:
    """Return current timestamp in ISO format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _get_brain_graph_service():
    """Get Brain Graph service instance."""
    try:
        from copilot_core.brain_graph.provider import get_graph_service
        return get_graph_service()
    except Exception:
        return None


@bp.get("/brain-summary")
def brain_summary():
    """Get brain graph summary for dashboard display.
    
    Returns:
    - Node counts by kind (concept, entity, zone, etc.)
    - Edge counts by type (controls, observed_with, etc.)
    - Top nodes by score
    - Top edges by weight
    - Last update timestamp
    """
    brain_service = _get_brain_graph_service()
    
    if not brain_service:
        return jsonify({
            "ok": False,
            "error": "Brain Graph service not available",
            "time": _now_iso(),
        }), 503
    
    try:
        # Export state to get current graph data
        state = brain_service.export_state(
            limit_nodes=50,
            limit_edges=100,
        )
        
        nodes = state.get("nodes", [])
        edges = state.get("edges", [])
        
        # Count nodes by kind
        kind_counts = {}
        for node in nodes:
            kind = node.get("kind", "unknown")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        
        # Count edges by type
        type_counts = {}
        for edge in edges:
            edge_type = edge.get("type", "unknown")
            type_counts[edge_type] = type_counts.get(edge_type, 0) + 1
        
        # Top nodes by score
        sorted_nodes = sorted(nodes, key=lambda n: n.get("score", 0), reverse=True)
        top_nodes = sorted_nodes[:10]
        
        # Top edges by weight
        sorted_edges = sorted(edges, key=lambda e: e.get("weight", 0), reverse=True)
        top_edges = sorted_edges[:10]
        
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "summary": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "nodes_by_kind": kind_counts,
                "edges_by_type": type_counts,
                "node_limits": state.get("limits", {}),
            },
            "top_nodes": [
                {
                    "id": n.get("id"),
                    "label": n.get("label"),
                    "kind": n.get("kind"),
                    "domain": n.get("domain"),
                    "score": round(n.get("score", 0), 6),
                    "updated_at_ms": n.get("updated_at_ms"),
                }
                for n in top_nodes
            ],
            "top_edges": [
                {
                    "id": e.get("id"),
                    "from": e.get("from"),
                    "to": e.get("to"),
                    "type": e.get("type"),
                    "weight": round(e.get("weight", 0), 6),
                    "updated_at_ms": e.get("updated_at_ms"),
                }
                for e in top_edges
            ],
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


@bp.get("/brain-graph-data")
def brain_graph_data():
    """Return full brain graph structure for frontend visualization.

    Returns d3.js / vis.js compatible nodes + edges arrays
    suitable for rendering an interactive force-directed graph.

    Query params:
        limit_nodes: Max nodes to return (default 200)
        limit_edges: Max edges to return (default 500)
    """
    brain_service = _get_brain_graph_service()

    if not brain_service:
        return jsonify({
            "ok": False,
            "error": "Brain Graph service not available",
            "time": _now_iso(),
        }), 503

    try:
        limit_nodes = int(request.args.get("limit_nodes", "200"))
        limit_edges = int(request.args.get("limit_edges", "500"))

        state = brain_service.export_state(
            limit_nodes=limit_nodes,
            limit_edges=limit_edges,
        )

        raw_nodes = state.get("nodes", [])
        raw_edges = state.get("edges", [])

        # Kind → color/shape mapping for frontend rendering
        _KIND_COLORS = {
            "concept": "#60a5fa", "entity": "#34d399", "zone": "#fb923c",
            "person": "#f472b6", "automation": "#a78bfa", "device": "#fbbf24",
            "action": "#f87171", "scene": "#c084fc",
        }
        _KIND_SHAPES = {
            "concept": "dot", "entity": "diamond", "zone": "box",
            "person": "star", "automation": "triangle", "device": "square",
        }

        vis_nodes = []
        for n in raw_nodes:
            kind = n.get("kind", "unknown")
            vis_nodes.append({
                "id": n.get("id"),
                "label": n.get("label", n.get("id", "")),
                "group": kind,
                "domain": n.get("domain"),
                "value": round(n.get("score", 0), 6),
                "title": f"{n.get('label', '')} ({kind})",
                "color": _KIND_COLORS.get(kind, "#94a3b8"),
                "shape": _KIND_SHAPES.get(kind, "dot"),
            })

        vis_edges = []
        for e in raw_edges:
            vis_edges.append({
                "from": e.get("from"),
                "to": e.get("to"),
                "label": e.get("type", ""),
                "value": round(e.get("weight", 0), 6),
                "arrows": "to",
            })

        kind_groups = {}
        for n in vis_nodes:
            group = n["group"]
            if group not in kind_groups:
                kind_groups[group] = {
                    "color": _KIND_COLORS.get(group, "#94a3b8"),
                    "shape": _KIND_SHAPES.get(group, "dot"),
                }

        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "nodes": vis_nodes,
            "edges": vis_edges,
            "groups": kind_groups,
            "total_nodes": len(vis_nodes),
            "total_edges": len(vis_edges),
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


@bp.get("/neuron-layers")
def neuron_layers():
    """Return neuron layer data for visualization.

    Structured as context -> state -> mood pipeline with per-neuron values.
    """
    try:
        from copilot_core.neurons.manager import get_neuron_manager
        manager = get_neuron_manager()
        summary = manager.get_neuron_summary()

        layers = {}
        for layer_name in ("context", "state", "mood"):
            layer_data = summary.get(layer_name, {})
            neurons_in_layer = []
            for n_name, n_state in layer_data.items():
                neurons_in_layer.append({
                    "name": n_name,
                    "value": n_state.get("value", 0),
                    "confidence": n_state.get("confidence", 0),
                    "trend": n_state.get("trend", "stable"),
                    "last_update": n_state.get("last_update"),
                })
            layers[layer_name] = {
                "count": len(neurons_in_layer),
                "neurons": sorted(
                    neurons_in_layer,
                    key=lambda n: n.get("value", 0),
                    reverse=True,
                ),
            }

        mood_summary = manager.get_mood_summary()

        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "layers": layers,
            "dominant_mood": mood_summary.get("mood", "unknown"),
            "mood_confidence": mood_summary.get("confidence", 0.0),
            "total_neurons": summary.get("total_count", 0),
            "pipeline": ["context", "state", "mood", "suggestions"],
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


@bp.get("/health")
def health():
    """Health check for dashboard module."""
    brain_ok = _get_brain_graph_service() is not None

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "module": "dashboard",
        "version": "0.2.0",
        "features": [
            "brain_graph_summary",
            "brain_graph_data",
            "neuron_layers",
            "node_statistics",
            "edge_statistics",
        ],
        "integrations": {
            "brain_graph": "ok" if brain_ok else "unavailable",
        },
        "status": "active",
        "endpoints": [
            "/api/v1/dashboard/brain-summary",
            "/api/v1/dashboard/brain-graph-data",
            "/api/v1/dashboard/neuron-layers",
            "/api/v1/dashboard/health",
        ],
    })
