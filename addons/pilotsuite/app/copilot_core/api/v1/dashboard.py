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


@bp.get("/health")
def health():
    """Health check for dashboard module."""
    brain_ok = _get_brain_graph_service() is not None
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "module": "dashboard",
        "version": "0.1.0",
        "features": [
            "brain_graph_summary",
            "node_statistics",
            "edge_statistics",
        ],
        "integrations": {
            "brain_graph": "ok" if brain_ok else "unavailable",
        },
        "status": "active",
        "endpoints": [
            "/api/v1/dashboard/brain-summary",
            "/api/v1/dashboard/health",
        ],
    })
