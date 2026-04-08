"""
Brain Graph API endpoints with performance optimization.
"""

import time
import hashlib
import json
from flask import Blueprint, request, jsonify, Response
from typing import Dict, Any, Optional

from .service import BrainGraphService
from .render import GraphRenderer
from ..api.security import require_api_key
from ..performance import brain_graph_cache, api_response_cache, QueryCache

# Create blueprint
brain_graph_bp = Blueprint('brain_graph', __name__, url_prefix='/api/v1/graph')

# Global service instance (will be initialized in main.py)
_brain_graph_service: BrainGraphService = None
_graph_renderer: GraphRenderer = None


def _compute_cache_key(prefix: str, **params) -> str:
    """Compute a deterministic cache key from parameters."""
    # Sort keys for consistent hashing
    sorted_params = json.dumps(params, sort_keys=True, default=str)
    content = f"{prefix}:{sorted_params}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def init_brain_graph_api(service: BrainGraphService, renderer: GraphRenderer = None):
    """Initialize the brain graph API with service instances."""
    global _brain_graph_service, _graph_renderer
    _brain_graph_service = service
    _graph_renderer = renderer or GraphRenderer()

@brain_graph_bp.route('/state', methods=['GET'])
@require_api_key
def get_graph_state() -> Response:
    """
    Get current graph state as JSON.
    
    Query parameters:
    - kind: filter by node kind (repeatable)
    - domain: filter by domain (repeatable)  
    - center: center node for neighborhood query
    - hops: number of hops for neighborhood (default 1)
    - limitNodes: max nodes to return
    - limitEdges: max edges to return
    - nocache: set to 1 to bypass cache
    
    Caching: Results are cached for 30 seconds (TTL).
    """
    if not _brain_graph_service:
        return jsonify({"error": "Brain graph service not initialized"}), 503
    
    try:
        # Check cache bypass flag
        nocache = request.args.get('nocache', '0') == '1'
        
        # Parse query parameters
        kinds = request.args.getlist('kind')
        domains = request.args.getlist('domain')
        center = request.args.get('center')
        hops = int(request.args.get('hops', 1))
        limit_nodes = _parse_int_param('limitNodes', default=None, max_value=500)
        limit_edges = _parse_int_param('limitEdges', default=None, max_value=1500)
        
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
                cached_result["_cached"] = True
                return jsonify(cached_result)
        
        # Validate parameters
        if hops < 1 or hops > 3:
            return jsonify({"error": "hops must be between 1 and 3"}), 400
        
        valid_kinds = ['entity', 'zone', 'device', 'person', 'concept', 'module', 'event']
        for kind in kinds:
            if kind not in valid_kinds:
                return jsonify({"error": f"Invalid kind: {kind}"}), 400
        
        # Get graph state
        state = _brain_graph_service.get_graph_state(
            kinds=kinds or None,
            domains=domains or None,
            center_node=center,
            hops=hops,
            limit_nodes=limit_nodes,
            limit_edges=limit_edges
        )
        
        # Cache the result (30 second TTL for graph state)
        brain_graph_cache.set(cache_key, state, ttl=30.0)
        state["_cached"] = False
        
        return jsonify(state)
        
    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {str(e)}"}), 400
    except Exception as e:
        # Security: Don't leak internal error details
        import logging
        logging.getLogger(__name__).error(f"Graph state error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@brain_graph_bp.route('/snapshot.svg', methods=['GET'])
@require_api_key
def get_graph_snapshot() -> Response:
    """
    Get graph visualization as SVG.
    
    Query parameters:
    - Same as /state plus:
    - layout: dot, neato, fdp (default dot)
    - theme: light, dark (default light)
    - label: short, full (default short)
    """
    if not _brain_graph_service or not _graph_renderer:
        error_svg = '''<?xml version="1.0"?>
<svg width="400" height="200" xmlns="http://www.w3.org/2000/svg">
    <text x="200" y="100" text-anchor="middle" fill="red">Service unavailable</text>
</svg>'''
        return Response(error_svg, mimetype='image/svg+xml'), 503
    
    try:
        # Parse visualization parameters
        layout = request.args.get('layout', 'dot')
        theme = request.args.get('theme', 'light') 
        label_style = request.args.get('label', 'short')
        
        # Parse same filter parameters as /state
        kinds = request.args.getlist('kind')
        domains = request.args.getlist('domain')
        center = request.args.get('center')
        hops = int(request.args.get('hops', 1))
        limit_nodes = _parse_int_param('limitNodes', default=120, max_value=120)  # Enforce render limits
        limit_edges = _parse_int_param('limitEdges', default=300, max_value=300)
        
        # Validate parameters
        if layout not in ['dot', 'neato', 'fdp', 'circo', 'twopi']:
            layout = 'dot'
        if theme not in ['light', 'dark']:
            theme = 'light'
        if label_style not in ['short', 'full']:
            label_style = 'short'
        if hops < 1 or hops > 3:
            hops = 1
        
        # Get graph state
        state = _brain_graph_service.get_graph_state(
            kinds=kinds or None,
            domains=domains or None,
            center_node=center,
            hops=hops,
            limit_nodes=limit_nodes,
            limit_edges=limit_edges
        )
        
        # Render as SVG
        svg_bytes = _graph_renderer.render_svg(
            graph_state=state,
            layout=layout,
            theme=theme,
            label_style=label_style
        )
        
        return Response(svg_bytes, mimetype='image/svg+xml')
        
    except Exception as e:
        # Security: Don't leak internal error details
        import logging
        logging.getLogger(__name__).error(f"Graph snapshot error: {e}")
        error_svg = '''<?xml version="1.0"?>
<svg width="400" height="200" xmlns="http://www.w3.org/2000/svg">
    <text x="200" y="100" text-anchor="middle" fill="red">Render Error</text>
</svg>'''
        return Response(error_svg, mimetype='image/svg+xml'), 500

@brain_graph_bp.route('/stats', methods=['GET'])
@require_api_key 
def get_graph_stats() -> Response:
    """
    Get brain graph statistics.
    
    Returns:
    - Graph statistics (node/edge counts)
    - Cache statistics (hits, misses, hit rate)
    - Performance metrics
    """
    if not _brain_graph_service:
        return jsonify({"error": "Brain graph service not initialized"}), 503
    
    try:
        # Get graph stats
        stats = _brain_graph_service.get_stats()
        
        # Add cache stats
        cache_stats = brain_graph_cache.get_stats()
        
        return jsonify({
            "version": 1,
            "ok": True,
            **stats,
            "cache": {
                "enabled": brain_graph_cache.enabled,
                "size": cache_stats["size"],
                "max_size": cache_stats["max_size"],
                "hits": cache_stats["hits"],
                "misses": cache_stats["misses"],
                "hit_rate": round(cache_stats["hit_rate"], 3),
                "evictions": cache_stats["evictions"],
            }
        })
    except Exception as e:
        # Security: Don't leak internal error details
        import logging
        logging.getLogger(__name__).error(f"Graph stats error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@brain_graph_bp.route('/cache', methods=['POST'])
@require_api_key
def clear_graph_cache() -> Response:
    """
    Clear the graph cache.
    
    Useful after major graph changes or for testing.
    """
    if not _brain_graph_service:
        return jsonify({"error": "Brain graph service not initialized"}), 503
    
    try:
        brain_graph_cache.clear()
        return jsonify({
            "message": "Graph cache cleared successfully",
            "timestamp_ms": int(time.time() * 1000)
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Cache clear error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@brain_graph_bp.route('/nodes', methods=['GET'])
@require_api_key
def get_nodes_paginated() -> Response:
    """
    Get nodes with pagination.
    
    Query parameters:
    - kind: filter by node kind (repeatable)
    - domain: filter by domain (repeatable)
    - page: page number (1-indexed, default 1)
    - per_page: items per page (default 50, max 100)
    - sort: sort field (score, label, updated_at)
    - order: sort order (asc, desc)
    """
    if not _brain_graph_service:
        return jsonify({"error": "Brain graph service not initialized"}), 503
    
    try:
        # Parse pagination parameters
        page = _parse_int_param('page', default=1)
        per_page = _parse_int_param('per_page', default=50, max_value=100)
        
        # Parse filter parameters
        kinds = request.args.getlist('kind')
        domains = request.args.getlist('domain')
        
        # Parse sort parameters
        sort = request.args.get('sort', 'score')
        order = request.args.get('order', 'desc')
        
        if sort not in ['score', 'label', 'updated_at']:
            sort = 'score'
        if order not in ['asc', 'desc']:
            order = 'desc'
        
        # Get all nodes (filtered)
        all_nodes = _brain_graph_service.store.get_nodes(
            kinds=kinds or None,
            domains=domains or None,
            limit=None
        )
        
        now_ms = int(time.time() * 1000)
        
        # Convert to serializable format with scores
        node_list = []
        for node in all_nodes:
            node_list.append({
                "id": node.id,
                "kind": node.kind,
                "label": node.label,
                "domain": node.domain,
                "score": node.effective_score(now_ms, _brain_graph_service.node_half_life_hours),
                "updated_at_ms": node.updated_at_ms,
                "source": node.source,
                "tags": node.tags,
            })
        
        # Sort
        if sort == 'score':
            node_list.sort(key=lambda x: x["score"], reverse=(order == 'desc'))
        elif sort == 'label':
            node_list.sort(key=lambda x: x.get("label", ""), reverse=(order == 'desc'))
        elif sort == 'updated_at':
            node_list.sort(key=lambda x: x.get("updated_at_ms", 0), reverse=(order == 'desc'))
        
        # Paginate
        total = len(node_list)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_nodes = node_list[start:end]
        
        return jsonify({
            "version": 1,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
            "nodes": paginated_nodes,
        })
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Nodes pagination error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@brain_graph_bp.route('/prune', methods=['POST'])
@require_api_key
def prune_graph() -> Response:
    """Manually trigger graph pruning."""
    if not _brain_graph_service:
        return jsonify({"error": "Brain graph service not initialized"}), 503
    
    try:
        stats = _brain_graph_service.prune_now()
        return jsonify({
            "message": "Graph pruned successfully",
            "stats": stats
        })
    except Exception as e:
        # Security: Don't leak internal error details
        import logging
        logging.getLogger(__name__).error(f"Graph prune error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@brain_graph_bp.route('/patterns', methods=['GET'])
@require_api_key
def get_patterns() -> Response:
    """
    Get inferred patterns from the graph.
    
    Query parameters:
    - limit: max items per pattern type (default 5, max 20)
    """
    if not _brain_graph_service:
        return jsonify({"error": "Brain graph service not initialized"}), 503
    
    try:
        limit = _parse_int_param('limit', default=5, max_value=20)
        
        patterns = _brain_graph_service.infer_patterns()
        
        # Limit results
        for key in patterns:
            if isinstance(patterns[key], list):
                patterns[key] = patterns[key][:limit]
        
        return jsonify({
            "version": 1,
            "ok": True,
            "generated_at_ms": int(time.time() * 1000),
            "patterns": patterns
        })
    except Exception as e:
        # Security: Don't leak internal error details
        import logging
        logging.getLogger(__name__).error(f"Graph patterns error: {e}")
        return jsonify({"error": "Internal server error"}), 500

def _parse_int_param(param_name: str, default: int = None, max_value: int = None) -> int:
    """Parse integer parameter with validation."""
    value = request.args.get(param_name)

    if value is None:
        return default

    try:
        parsed = int(value)
        if parsed < 1:
            raise ValueError(f"{param_name} must be positive")
        if max_value and parsed > max_value:
            parsed = max_value
        return parsed
    except ValueError:
        raise ValueError(f"{param_name} must be a valid positive integer")


# ═══════════════════════════════════════════════════════════════════════════
# v5.0.0 — SSE Real-Time Brain Graph Stream
# ═══════════════════════════════════════════════════════════════════════════

@brain_graph_bp.route('/stream', methods=['GET'])
@require_api_key
def stream_graph_updates() -> Response:
    """SSE endpoint for real-time brain graph updates.

    Streams node_updated, edge_updated, and graph_pruned events.
    Client connects with: ``new EventSource('/api/v1/graph/stream')``.
    """
    if not _brain_graph_service:
        return jsonify({"error": "Brain graph service not initialized"}), 503

    import queue as _queue

    subscriber = _brain_graph_service.subscribe_sse()

    def generate():
        try:
            # Send initial connected event
            yield f"data: {json.dumps({'event': 'connected', 'timestamp_ms': int(time.time() * 1000)})}\n\n"
            while True:
                try:
                    msg = subscriber.get(timeout=30.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except _queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            _brain_graph_service.unsubscribe_sse(subscriber)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )