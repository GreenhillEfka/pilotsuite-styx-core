"""
RAG Search API for PilotSuite Core

Provides semantic search endpoints:
- POST /api/v1/rag/search - Semantic search with embeddings
- GET /api/v1/rag/search/suggestions - Autocomplete suggestions
- GET /api/v1/rag/search/stats - Search analytics

Usage:
    from copilot_core.api.rag_search import setup_rag_search_routes
    
    app = web.Application()
    setup_rag_search_routes(app)
"""

import logging
import threading
import time
from typing import Optional
from collections import defaultdict

from aiohttp import web

from copilot_core.vector_store import get_vector_store, get_embedding_engine

logger = logging.getLogger(__name__)

# In-memory search analytics — guarded by _search_lock (Waitress is multi-threaded)
_search_lock = threading.Lock()
_search_analytics: dict[str, int] = defaultdict(int)
_search_history: list[dict] = []
_HISTORY_MAX_SIZE = 1000

# Query cache (simple LRU) — guarded by _search_lock
_query_cache: dict[str, dict] = {}
_CACHE_MAX_SIZE = 100
_CACHE_TTL = 300  # 5 minutes


def _add_to_cache(query: str, results: list) -> None:
    """Add query result to cache (caller must hold _search_lock)."""
    if len(_query_cache) >= _CACHE_MAX_SIZE:
        oldest_key = next(iter(_query_cache))
        del _query_cache[oldest_key]

    _query_cache[query] = {
        "results": results,
        "timestamp": time.time(),
    }


def _get_from_cache(query: str) -> Optional[list]:
    """Get cached query results if not expired (caller must hold _search_lock)."""
    if query in _query_cache:
        entry = _query_cache[query]
        if time.time() - entry["timestamp"] < _CACHE_TTL:
            return entry["results"]
        del _query_cache[query]

    return None


def _record_search(query: str, result_count: int, duration_ms: float) -> None:
    """Record search analytics (caller must hold _search_lock)."""
    _search_analytics[query] += 1
    _search_history.append({
        "query": query,
        "result_count": result_count,
        "duration_ms": duration_ms,
        "timestamp": time.time(),
    })

    # Rotate history
    if len(_search_history) > _HISTORY_MAX_SIZE:
        del _search_history[:-_HISTORY_MAX_SIZE]


async def handle_rag_search(request: web.Request) -> web.Response:
    """
    POST /api/v1/rag/search
    
    Semantic search with vector embeddings.
    
    Request body:
    {
        "query": "search text",
        "limit": 10,
        "filters": {
            "entry_type": "entity",  // optional: entity, user_preference, pattern
            "metadata": {...}  // optional metadata filters
        },
        "threshold": 0.7  // optional: similarity threshold
    }
    
    Response:
    {
        "query": "search text",
        "results": [
            {
                "id": "entity_123",
                "similarity": 0.95,
                "entry_type": "entity",
                "metadata": {...}
            }
        ],
        "duration_ms": 45,
        "cached": false
    }
    """
    start_time = time.time()
    
    try:
        body = await request.json()
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON body"},
            status=400,
        )
    
    query = body.get("query", "").strip()
    if not query:
        return web.json_response(
            {"error": "Query is required"},
            status=400,
        )
    
    limit = min(body.get("limit", 10), 100)  # Max 100 results
    filters = body.get("filters", {})
    threshold = body.get("threshold", 0.5)
    
    # Check cache first
    cache_key = f"{query}:{limit}:{str(filters)}:{threshold}"
    with _search_lock:
        cached_results = _get_from_cache(cache_key)

    if cached_results is not None:
        duration_ms = (time.time() - start_time) * 1000
        with _search_lock:
            _record_search(query, len(cached_results), duration_ms)

        return web.json_response({
            "query": query,
            "results": cached_results,
            "duration_ms": round(duration_ms, 2),
            "cached": True,
        })
    
    # Perform semantic search
    try:
        vector_store = get_vector_store()
        embedding_engine = get_embedding_engine()
        
        # Generate embedding for query
        embedding_result = await embedding_engine.embed_query(query)
        query_vector = embedding_result.embedding
        
        # Search vector store
        results = await vector_store.search(
            query_vector=query_vector,
            limit=limit,
            entry_type=filters.get("entry_type"),
            metadata_filter=filters.get("metadata"),
            threshold=threshold,
        )
        
        # Format results
        formatted_results = [
            {
                "id": r.id,
                "similarity": round(r.similarity, 4),
                "entry_type": r.entry_type,
                "metadata": r.metadata,
            }
            for r in results
        ]
        
        # Cache results
        duration_ms = (time.time() - start_time) * 1000
        with _search_lock:
            _add_to_cache(cache_key, formatted_results)
            _record_search(query, len(formatted_results), duration_ms)

        return web.json_response({
            "query": query,
            "results": formatted_results,
            "duration_ms": round(duration_ms, 2),
            "cached": False,
        })

    except Exception as e:
        logger.error("RAG search error: %s", e)
        return web.json_response(
            {"error": "Search failed", "details": str(e)},
            status=500,
        )


async def handle_rag_suggestions(request: web.Request) -> web.Response:
    """
    GET /api/v1/rag/search/suggestions
    
    Autocomplete suggestions based on search history.
    
    Query params:
    - q: Partial query string
    - limit: Max suggestions (default: 5)
    
    Response:
    {
        "query": "par",
        "suggestions": ["party", "parking", "pattern"],
        "count": 3
    }
    """
    query = request.query.get("q", "").strip().lower()
    limit = min(int(request.query.get("limit", 5)), 10)
    
    if not query:
        return web.json_response({
            "query": "",
            "suggestions": [],
            "count": 0,
        })
    
    # Get suggestions from search history
    with _search_lock:
        suggestions = set()
        for past_query in list(_search_analytics.keys()):
            if past_query.lower().startswith(query) and past_query.lower() != query:
                suggestions.add(past_query)
            if len(suggestions) >= limit * 2:  # Get extra to sort by popularity
                break

        # Sort by popularity and take top N
        sorted_suggestions = sorted(
            suggestions,
            key=lambda q: _search_analytics.get(q, 0),
            reverse=True,
        )[:limit]
    
    return web.json_response({
        "query": query,
        "suggestions": sorted_suggestions,
        "count": len(sorted_suggestions),
    })


async def handle_rag_stats(request: web.Request) -> web.Response:
    """
    GET /api/v1/rag/search/stats
    
    Search analytics and statistics.
    
    Query params:
    - limit: Top N queries (default: 10)
    
    Response:
    {
        "total_searches": 1234,
        "unique_queries": 567,
        "top_queries": [
            {"query": "lighting", "count": 45},
            {"query": "temperature", "count": 32}
        ],
        "recent_searches": [...],
        "cache_stats": {
            "size": 23,
            "max_size": 100
        }
    }
    """
    limit = min(int(request.query.get("limit", 10)), 50)
    
    with _search_lock:
        top_queries = sorted(
            _search_analytics.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]
        recent = list(_search_history[-20:])
        total = sum(_search_analytics.values())
        unique = len(_search_analytics)
        cache_size = len(_query_cache)
        history_size = len(_search_history)

    return web.json_response({
        "total_searches": total,
        "unique_queries": unique,
        "top_queries": [
            {"query": q, "count": c} for q, c in top_queries
        ],
        "recent_searches": recent,
        "cache_stats": {
            "size": cache_size,
            "max_size": _CACHE_MAX_SIZE,
            "ttl_seconds": _CACHE_TTL,
        },
        "history_stats": {
            "size": history_size,
            "max_size": _HISTORY_MAX_SIZE,
        },
    })


async def handle_rag_search_benchmark(request: web.Request) -> web.Response:
    """
    POST /api/v1/rag/search/benchmark
    
    Benchmark search performance.
    
    Request body:
    {
        "query": "test query",
        "iterations": 10
    }
    
    Response:
    {
        "iterations": 10,
        "avg_duration_ms": 45.2,
        "min_duration_ms": 38.1,
        "max_duration_ms": 52.3,
        "p95_duration_ms": 50.1
    }
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON body"},
            status=400,
        )
    
    query = body.get("query", "benchmark test")
    iterations = min(body.get("iterations", 10), 100)
    
    durations = []
    
    for _ in range(iterations):
        start = time.time()
        
        try:
            vector_store = get_vector_store()
            embedding_engine = get_embedding_engine()
            
            embedding_result = await embedding_engine.embed_query(query)
            await vector_store.search(
                query_vector=embedding_result.embedding,
                limit=10,
            )
        except Exception:
            logger.debug("Benchmark iteration failed", exc_info=True)

        duration_ms = (time.time() - start) * 1000
        durations.append(duration_ms)

    if not durations:
        return web.json_response({"error": "No successful iterations"}, status=500)
    
    durations.sort()
    avg = sum(durations) / len(durations)
    p95_idx = int(len(durations) * 0.95)
    
    return web.json_response({
        "query": query,
        "iterations": iterations,
        "avg_duration_ms": round(avg, 2),
        "min_duration_ms": round(min(durations), 2),
        "max_duration_ms": round(max(durations), 2),
        "p95_duration_ms": round(durations[p95_idx] if p95_idx < len(durations) else durations[-1], 2),
        "success_rate": len(durations) / iterations * 100,
    })


def setup_rag_search_routes(app: web.Application):
    """Register RAG search routes with the application."""
    # Create a blueprint-like structure for Flask
    # For aiohttp, we add routes directly
    
    # For Flask compatibility (api_v1 is a Flask Blueprint)
    # We'll register these routes with the Flask app instead
    
    logger.info("RAG search routes configured (call register_rag_search_flask for Flask)")


def register_rag_search_flask(app):
    """Register RAG search routes with Flask app."""
    from flask import Blueprint
    
    rag_bp = Blueprint('rag_search', __name__, url_prefix='/api/v1/rag')
    
    # We need to convert aiohttp handlers to Flask handlers
    # For now, we'll create Flask-compatible wrappers
    
    @app.route('/api/v1/rag/search', methods=['POST'])
    def rag_search_flask():
        from flask import request, jsonify
        import asyncio
        
        # Get request data
        data = request.get_json() or {}
        query = data.get('query', '')
        limit = min(data.get('limit', 10), 100)
        filters = data.get('filters', {})
        threshold = data.get('threshold', 0.5)
        
        start_time = time.time()
        
        # Check cache
        cache_key = f"{query}:{limit}:{str(filters)}:{threshold}"
        with _search_lock:
            cached_results = _get_from_cache(cache_key)

        if cached_results is not None:
            duration_ms = (time.time() - start_time) * 1000
            with _search_lock:
                _record_search(query, len(cached_results), duration_ms)

            return jsonify({
                "query": query,
                "results": cached_results,
                "duration_ms": round(duration_ms, 2),
                "cached": True,
            })
        
        # Perform search
        try:
            vector_store = get_vector_store()
            embedding_engine = get_embedding_engine()
            
            # Generate embedding
            embedding_result = asyncio.run(
                embedding_engine.embed_query(query)
            )
            results = asyncio.run(
                vector_store.search(
                    query_vector=embedding_result.embedding,
                    limit=limit,
                    entry_type=filters.get("entry_type"),
                    metadata_filter=filters.get("metadata"),
                    threshold=threshold,
                )
            )
            
            formatted_results = [
                {
                    "id": r.id,
                    "similarity": round(r.similarity, 4),
                    "entry_type": r.entry_type,
                    "metadata": r.metadata,
                }
                for r in results
            ]
            
            duration_ms = (time.time() - start_time) * 1000
            with _search_lock:
                _add_to_cache(cache_key, formatted_results)
                _record_search(query, len(formatted_results), duration_ms)

            return jsonify({
                "query": query,
                "results": formatted_results,
                "duration_ms": round(duration_ms, 2),
                "cached": False,
            })

        except Exception as e:
            logger.error("RAG search error: %s", e)
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/v1/rag/search/suggestions', methods=['GET'])
    def rag_suggestions_flask():
        from flask import request, jsonify
        
        query = request.args.get('q', '').strip().lower()
        limit = min(int(request.args.get('limit', 5)), 10)
        
        if not query:
            return jsonify({
                "query": "",
                "suggestions": [],
                "count": 0,
            })
        
        with _search_lock:
            suggestions = set()
            for past_query in list(_search_analytics.keys()):
                if past_query.lower().startswith(query) and past_query.lower() != query:
                    suggestions.add(past_query)
                if len(suggestions) >= limit * 2:
                    break

            sorted_suggestions = sorted(
                suggestions,
                key=lambda q: _search_analytics.get(q, 0),
                reverse=True,
            )[:limit]

        return jsonify({
            "query": query,
            "suggestions": sorted_suggestions,
            "count": len(sorted_suggestions),
        })
    
    @app.route('/api/v1/rag/search/stats', methods=['GET'])
    def rag_stats_flask():
        from flask import request, jsonify
        
        limit = min(int(request.args.get('limit', 10)), 50)
        
        with _search_lock:
            top_queries = sorted(
                _search_analytics.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:limit]
            recent = list(_search_history[-20:])
            total = sum(_search_analytics.values())
            unique = len(_search_analytics)
            cache_size = len(_query_cache)
            history_size = len(_search_history)

        return jsonify({
            "total_searches": total,
            "unique_queries": unique,
            "top_queries": [
                {"query": q, "count": c} for q, c in top_queries
            ],
            "recent_searches": recent,
            "cache_stats": {
                "size": cache_size,
                "max_size": _CACHE_MAX_SIZE,
                "ttl_seconds": _CACHE_TTL,
            },
            "history_stats": {
                "size": history_size,
                "max_size": _HISTORY_MAX_SIZE,
            },
        })
    
    @app.route('/api/v1/rag/search/benchmark', methods=['POST'])
    def rag_benchmark_flask():
        from flask import request, jsonify
        import asyncio
        
        data = request.get_json() or {}
        query = data.get('query', 'benchmark test')
        iterations = min(data.get('iterations', 10), 100)
        
        durations = []
        
        for _ in range(iterations):
            start = time.time()
            
            try:
                vector_store = get_vector_store()
                embedding_engine = get_embedding_engine()
                
                embedding_result = asyncio.run(
                    embedding_engine.embed_query(query)
                )
                asyncio.run(
                    vector_store.search(
                        query_vector=embedding_result.embedding,
                        limit=10,
                    )
                )
            except Exception:
                logger.debug("Flask benchmark iteration failed", exc_info=True)
            
            duration_ms = (time.time() - start) * 1000
            durations.append(duration_ms)
        
        if not durations:
            return jsonify({"error": "No successful iterations"}), 500
        
        durations.sort()
        avg = sum(durations) / len(durations)
        p95_idx = int(len(durations) * 0.95)
        
        return jsonify({
            "query": query,
            "iterations": iterations,
            "avg_duration_ms": round(avg, 2),
            "min_duration_ms": round(min(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "p95_duration_ms": round(durations[p95_idx] if p95_idx < len(durations) else durations[-1], 2),
            "success_rate": len(durations) / iterations * 100,
        })
    
    logger.info("RAG search routes registered with Flask app")
