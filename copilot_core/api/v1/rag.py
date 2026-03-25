"""RAG Search API (Flask Blueprint) — PilotSuite Styx Core.

Hybrid Search: BM25 + Semantic (Reciprocal Rank Fusion)
Query Routing: automatic detection of query type
SearXNG Fallback: external web context
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.rag.indexer import NamespaceIndex
from copilot_core.rag.hybrid_search import HybridSearch
from copilot_core.rag.query_router import QueryRouter, classify_query
from copilot_core.rag.searxng_client import get_searxng_client

logger = logging.getLogger(__name__)

bp = Blueprint("rag", __name__, url_prefix="/rag")

# Lazy-initialized singletons
_hybrid_search = None
_query_router = None
_searxng_client = None


def _hs() -> HybridSearch:
    global _hybrid_search
    if _hybrid_search is None:
        _hybrid_search = HybridSearch()
    return _hybrid_search


def _qr():
    global _query_router
    if _query_router is None:
        _query_router = QueryRouter()
    return _query_router


def _sx():
    global _searxng_client
    if _searxng_client is None:
        _searxng_client = get_searxng_client()
    return _searxng_client


# === GET /api/v1/rag/search ===

@bp.route("/search", methods=["GET"])
def rag_search_get():
    """
    GET /api/v1/rag/search?q=<query>&namespace=<ns>&top_k=<k>&use_searxng=1
    """
    query = request.args.get("q", "")
    namespace = request.args.get("namespace", "default")
    top_k = int(request.args.get("top_k", 5))
    use_searxng = request.args.get("use_searxng", "1") in ("1", "true", "yes")

    return _do_search(query, namespace, top_k, use_searxng)


# === POST /api/v1/rag/search ===

@bp.route("/search", methods=["POST"])
def rag_search_post():
    """
    POST /api/v1/rag/search
    Body: {"query": "...", "namespace": "...", "top_k": 5, "use_searxng_fallback": true}
    """
    body = request.get_json(force=True) or {}
    query = body.get("query", "")
    namespace = body.get("namespace", "default")
    top_k = int(body.get("top_k", 5))
    use_searxng = body.get("use_searxng_fallback", True)

    return _do_search(query, namespace, top_k, use_searxng)


def _do_search(query: str, namespace: str, top_k: int, use_searxng: bool):
    """Shared search implementation for GET and POST."""
    try:
        # 1. Route query
        query_type = classify_query(query)
        logger.debug(f"RAG routed: {query_type} | query: {query}")

        # 2. Hybrid search
        hs = _hs()
        results = hs.search(query, namespace=namespace, top_k=top_k)

        searxng_used = False
        searxng_results = None

        # 3. SearXNG fallback
        if use_searxng and (not results or query_type == "searxng"):
            try:
                sx = _sx()
                searxng_results = sx.search(query, top_k=top_k)
                searxng_used = True
                if not results:
                    query_type = "searxng"
            except Exception as e:
                logger.warning(f"SearXNG fallback failed: {e}")

        # 4. Build response
        rag_docs = []
        for i, (doc, score) in enumerate(results):
            rag_docs.append({
                "content": doc.page_content if hasattr(doc, "page_content") else str(doc),
                "score": float(score),
                "metadata": doc.metadata if hasattr(doc, "metadata") else {},
                "rank": i + 1,
            })

        return jsonify({
            "results": rag_docs,
            "query_type": query_type,
            "query": query,
            "namespace": namespace,
            "total_results": len(rag_docs),
            "searxng_used": searxng_used,
            "searxng_results": searxng_results or [],
        })

    except Exception as e:
        logger.error(f"RAG search error: {e}")
        return jsonify({"error": str(e)}), 500


# === POST /api/v1/rag/index ===

@bp.route("/index", methods=["POST"])
def rag_index():
    """
    POST /api/v1/rag/index
    Body: {"namespace": "default", "documents": [{id, content, metadata}], "rebuild": false}
    """
    try:
        body = request.get_json(force=True) or {}
        namespace = body.get("namespace", "default")
        documents = body.get("documents", [])
        rebuild = body.get("rebuild", False)

        indexer = NamespaceIndex()
        count = indexer.add_documents(namespace=namespace, documents=documents, rebuild=rebuild)
        hs = _hs()
        hs.rebuild_index(namespace=namespace)

        return jsonify({
            "namespace": namespace,
            "indexed_count": count,
            "total_docs": len(documents),
            "message": f"Indexed {count} documents",
        })

    except Exception as e:
        logger.error(f"RAG index error: {e}")
        return jsonify({"error": str(e)}), 500


# === GET /api/v1/rag/namespaces ===

@bp.route("/namespaces", methods=["GET"])
def rag_namespaces():
    """List all available RAG namespaces."""
    try:
        indexer = NamespaceIndex()
        namespaces = indexer.list_namespaces()
        return jsonify({"namespaces": namespaces})
    except Exception as e:
        logger.error(f"RAG namespaces error: {e}")
        return jsonify({"error": str(e)}), 500


# === DELETE /api/v1/rag/namespace/<namespace> ===

@bp.route("/namespace/<namespace>", methods=["DELETE"])
def rag_delete_namespace(namespace: str):
    """Delete all documents in a namespace."""
    try:
        indexer = NamespaceIndex()
        indexer.delete_namespace(namespace)
        hs = _hs()
        hs.rebuild_index(namespace=namespace)
        return jsonify({"message": f"Namespace '{namespace}' deleted", "namespace": namespace})
    except Exception as e:
        logger.error(f"RAG delete namespace error: {e}")
        return jsonify({"error": str(e)}), 500
