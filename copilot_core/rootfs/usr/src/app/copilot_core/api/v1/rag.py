"""RAG (Retrieval-Augmented Generation) API endpoints.

Provides hybrid search API combining BM25 and vector search with RRF re-ranking.

Endpoints:
- POST /api/v1/rag/search - Hybrid search (BM25 + Vector)
- POST /api/v1/rag/search/multi - Multi-query hybrid search
- POST /api/v1/rag/documents - Add document to index
- DELETE /api/v1/rag/documents/<doc_id> - Remove document
- GET /api/v1/rag/stats - Search engine statistics
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.validation import validate_json
from copilot_core.rag.hybrid_search import (
    get_hybrid_search_engine,
    HybridSearchConfig,
    HybridSearchResult,
)

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("rag", __name__, url_prefix="/rag")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    """Require authentication for all RAG endpoints."""
    if not _validate_token(request):
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required",
        }), 401


def _get_engine():
    """Get hybrid search engine with vector store integration."""
    from copilot_core.vector_store.store import get_vector_store
    
    vector_store = get_vector_store()
    config = HybridSearchConfig(
        rrf_k=60,
        bm25_weight=0.5,
        vector_weight=0.5,
        top_k=10,
        bm25_k1=1.5,
        bm25_b=0.75,
        vector_threshold=0.5,
        multi_query_enabled=True,
        multi_query_count=3,
        use_cache=True,
        cache_ttl_seconds=300,
    )
    
    return get_hybrid_search_engine(config=config, vector_store=vector_store)


# ==================== Schemas ====================

class SearchRequest:
    """Search request schema."""
    
    def __init__(self, data: Dict[str, Any]):
        self.query = data.get("query", "")
        self.top_k = min(data.get("top_k", 10), 100)
        self.filters = data.get("filters")
        self.use_multi_query = data.get("use_multi_query", False)
        
    @classmethod
    def from_request(cls) -> "SearchRequest":
        """Create from Flask request."""
        data = request.get_json() or {}
        return cls(data)


class MultiQueryRequest:
    """Multi-query search request schema."""
    
    def __init__(self, data: Dict[str, Any]):
        self.queries = data.get("queries", [])
        self.top_k = min(data.get("top_k", 10), 100)
        
    @classmethod
    def from_request(cls) -> "MultiQueryRequest":
        """Create from Flask request."""
        data = request.get_json() or {}
        return cls(data)


class DocumentRequest:
    """Document add/update request schema."""
    
    def __init__(self, data: Dict[str, Any]):
        self.doc_id = data.get("doc_id", "")
        self.content = data.get("content", "")
        self.metadata = data.get("metadata", {})
        
    @classmethod
    def from_request(cls) -> "DocumentRequest":
        """Create from Flask request."""
        data = request.get_json() or {}
        return cls(data)


# ==================== Search Endpoints ====================

@bp.post("/search")
def hybrid_search():
    """Perform hybrid search (BM25 + Vector with RRF fusion).
    
    Request body:
    - query: Search query string (required)
    - top_k: Number of results (default 10, max 100)
    - filters: Optional filters for vector search
    - use_multi_query: Enable multi-query mode (default False)
    
    Response:
    - results: List of search results with scores
    - execution_time_ms: Query execution time
    - query_type: "single" or "multi"
    """
    start_time = time.time()
    
    try:
        req = SearchRequest.from_request()
        
        if not req.query:
            return jsonify({
                "ok": False,
                "error": "Missing required field: query",
            }), 400
        
        engine = _get_engine()
        
        # Run async search
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if req.use_multi_query:
                # Generate query variations for multi-query
                query_variations = _generate_query_variations(req.query)
                results = loop.run_until_complete(
                    engine.search_multi_query(query_variations, req.top_k)
                )
                query_type = "multi"
            else:
                results = loop.run_until_complete(
                    engine.search(req.query, req.top_k, req.filters)
                )
                query_type = "single"
        finally:
            loop.close()
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        return jsonify({
            "ok": True,
            "results": [
                {
                    "id": r.id,
                    "score": round(r.score, 4),
                    "bm25_score": round(r.bm25_score, 4) if r.bm25_score else 0,
                    "vector_score": round(r.vector_score, 4) if r.vector_score else 0,
                    "rrf_score": round(r.rrf_score, 6) if r.rrf_score else 0,
                    "content": r.content[:500],  # Truncate for response
                    "metadata": r.metadata,
                    "rank_bm25": r.rank_bm25,
                    "rank_vector": r.rank_vector,
                    "final_rank": r.final_rank,
                }
                for r in results
            ],
            "count": len(results),
            "query": req.query,
            "query_type": query_type,
            "execution_time_ms": round(execution_time_ms, 2),
        })
        
    except Exception as e:
        _LOGGER.exception("Hybrid search failed")
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


def _generate_query_variations(base_query: str) -> List[str]:
    """Generate query variations for multi-query search.
    
    Creates semantically similar queries to improve recall.
    
    Args:
        base_query: Original search query
        
    Returns:
        List of query variations
    """
    variations = [base_query]
    
    # Add simplified version (remove stop words)
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being"}
    words = base_query.split()
    simplified = " ".join(w for w in words if w.lower() not in stop_words)
    if simplified and simplified != base_query:
        variations.append(simplified)
    
    # Add expanded version (add related terms)
    # Simple expansion - in production, use LLM or thesaurus
    if "light" in base_query.lower():
        variations.append(base_query + " lamp illumination")
    elif "temperature" in base_query.lower():
        variations.append(base_query + " climate thermostat")
    elif "security" in base_query.lower():
        variations.append(base_query + " alarm lock camera")
    
    return variations[:5]  # Limit to 5 variations


@bp.post("/search/multi")
def multi_query_search():
    """Perform multi-query hybrid search.
    
    Request body:
    - queries: List of query strings (required)
    - top_k: Number of results (default 10, max 100)
    
    Response:
    - results: Fused search results from all queries
    - execution_time_ms: Query execution time
    """
    start_time = time.time()
    
    try:
        req = MultiQueryRequest.from_request()
        
        if not req.queries:
            return jsonify({
                "ok": False,
                "error": "Missing required field: queries",
            }), 400
        
        engine = _get_engine()
        
        # Run async multi-query search
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                engine.search_multi_query(req.queries, req.top_k)
            )
        finally:
            loop.close()
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        return jsonify({
            "ok": True,
            "results": [
                {
                    "id": r.id,
                    "score": round(r.score, 4),
                    "bm25_score": round(r.bm25_score, 4) if r.bm25_score else 0,
                    "vector_score": round(r.vector_score, 4) if r.vector_score else 0,
                    "rrf_score": round(r.rrf_score, 6) if r.rrf_score else 0,
                    "content": r.content[:500],
                    "metadata": r.metadata,
                    "final_rank": r.final_rank,
                }
                for r in results
            ],
            "count": len(results),
            "queries": req.queries,
            "execution_time_ms": round(execution_time_ms, 2),
        })
        
    except Exception as e:
        _LOGGER.exception("Multi-query search failed")
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


# ==================== Document Management ====================

@bp.post("/documents")
def add_document():
    """Add a document to the RAG index.
    
    Request body:
    - doc_id: Unique document identifier (required)
    - content: Document text content (required)
    - metadata: Optional metadata dict
    
    Response:
    - ok: Success status
    - doc_id: Added document ID
    """
    try:
        req = DocumentRequest.from_request()
        
        if not req.doc_id or not req.content:
            return jsonify({
                "ok": False,
                "error": "Missing required fields: doc_id, content",
            }), 400
        
        engine = _get_engine()
        
        # Generate embedding for vector search
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from copilot_core.vector_store.embeddings import get_embedding_engine
            
            embedding_engine = get_embedding_engine()
            embedding_result = loop.run_in_executor(
                None,
                lambda: embedding_engine.generate_embedding(req.content[:2000]),  # Limit content for embedding
            )
            vector = embedding_result.result.embedding
            
            # Add to index
            engine.add_document(req.doc_id, req.content, vector)
        finally:
            loop.close()
        
        return jsonify({
            "ok": True,
            "doc_id": req.doc_id,
            "content_length": len(req.content),
        }), 201
        
    except Exception as e:
        _LOGGER.exception("Failed to add document")
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@bp.delete("/documents/<path:doc_id>")
def remove_document(doc_id: str):
    """Remove a document from the RAG index.
    
    Args:
        doc_id: Document identifier to remove
        
    Response:
    - ok: Success status
    - deleted: Removed document ID
    """
    try:
        engine = _get_engine()
        
        removed = engine.remove_document(doc_id)
        
        if not removed:
            return jsonify({
                "ok": False,
                "error": f"Document not found: {doc_id}",
            }), 404
        
        return jsonify({
            "ok": True,
            "deleted": doc_id,
        })
        
    except Exception as e:
        _LOGGER.exception("Failed to remove document")
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


# ==================== Stats & Health ====================

@bp.get("/stats")
def rag_stats():
    """Get RAG search engine statistics.
    
    Response:
    - num_documents: Total indexed documents
    - avg_doc_length: Average document length
    - cache_size: Number of cached queries
    - config: Current configuration
    """
    try:
        engine = _get_engine()
        stats = engine.get_stats()
        
        return jsonify({
            "ok": True,
            "stats": stats,
        })
        
    except Exception as e:
        _LOGGER.exception("Failed to get stats")
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@bp.get("/health")
def rag_health():
    """Health check for RAG service.
    
    Response:
    - status: "healthy" or "degraded"
    - components: Component health status
    """
    try:
        engine = _get_engine()
        stats = engine.get_stats()
        
        # Check if we have documents indexed
        has_documents = stats["num_documents"] > 0
        
        return jsonify({
            "ok": True,
            "status": "healthy" if has_documents else "degraded",
            "components": {
                "bm25_index": "healthy",
                "vector_store": "healthy" if engine._vector_store else "not_configured",
                "cache": "active" if stats["cache_size"] > 0 else "empty",
            },
            "num_documents": stats["num_documents"],
        })
        
    except Exception as e:
        _LOGGER.exception("RAG health check failed")
        return jsonify({
            "ok": False,
            "status": "unhealthy",
            "error": str(e),
        }), 500
