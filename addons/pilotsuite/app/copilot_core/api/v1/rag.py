"""RAG Hybrid Search API (Flask Blueprint).

Endpoints for hybrid search (BM25 + Semantic), document indexing,
reranking, and statistics. Mounted at /api/rag (absolute prefix).

Endpoints:
  POST /api/rag/search          – Hybrid Search (BM25 + Semantic + RRF)
  POST /api/rag/search/bm25     – BM25-only lexical search
  POST /api/rag/search/semantic  – Semantic-only search
  POST /api/rag/rerank          – RRF reranking of pre-existing hit lists
  GET  /api/rag/stats           – Index statistics
  POST /api/rag/index           – Upsert documents into index
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import re
from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.security.rate_limiter import get_rate_limiter, rate_limit
from copilot_core.rag.bm25 import BM25Config, BM25Document, BM25Hit, BM25SqliteIndex
from copilot_core.rag.hybrid_search import FusedHit, RankedHit, reciprocal_rank_fusion
from copilot_core.rag.searxng_client import SearXNGClient, SearXNGResult, get_searxng_client
from copilot_core.rag.query_router import classify_query, QueryType
from copilot_core.cache import get_rag_cache

# Rate limiting config for RAG endpoints: 15 req/min, burst 5
_RAG_RATE_LIMIT_CAPACITY = 5
_RAG_RATE_LIMIT_REFILL_RATE = 15.0 / 60.0  # 15 requests per minute

# Namespace validation regex: alphanumeric, underscore, hyphen only
_NAMESPACE_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_namespace(namespace: str) -> bool:
    """Validate namespace parameter against injection attacks.
    
    Args:
        namespace: Namespace string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not namespace:
        return False
    # Max length check (prevent DoS)
    if len(namespace) > 128:
        return False
    return bool(_NAMESPACE_PATTERN.match(namespace))


def _rate_limit_rag():
    """Apply rate limiting to RAG endpoints.
    
    Returns:
        None if allowed, or (response, status_code) tuple if rate limited
    """
    limiter = get_rate_limiter()
    client_key = limiter.get_client_key()
    endpoint = request.path
    
    # Set endpoint-specific limit if not already set
    if endpoint not in limiter._endpoint_limits:
        limiter.set_endpoint_limit(endpoint, 15)
    
    allowed, info = limiter.is_allowed(client_key, endpoint)
    
    if not allowed:
        from flask import g
        g.rate_limit_info = info
        
        # Log security event
        from copilot_core.security.security_logs import get_security_logger
        sec_logger = get_security_logger()
        sec_logger.log_rate_limit_exceeded(client_key, endpoint)
        
        response = jsonify({
            "ok": False,
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "rate_limit": info,
        })
        response.status_code = 429
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        response.headers["Retry-After"] = str(info["reset"] - int(time.time()))
        return response
    
    return None

logger = logging.getLogger(__name__)

bp = Blueprint("rag", __name__, url_prefix="/api/v1/rag")

_DEFAULT_DB_PATH = os.getenv("COPILOT_CORE_RAG_DB_PATH", "/data/copilot_core_rag.sqlite3")
_SEMANTIC_BACKEND_MODULE = os.getenv("COPILOT_CORE_RAG_SEMANTIC_BACKEND", "").strip()
_SEARXNG_BASE_URL = os.getenv("COPILOT_CORE_RAG_SEARXNG_URL", "http://localhost:8080")

# ── Limits ──────────────────────────────────────────────────────────────
_MAX_DOCUMENTS_PER_REQUEST = 2000
_MAX_TOP_K = 500
_MAX_RERANK_HITS = 1000
_MAX_MULTI_QUERY_VARIATIONS = 5


# ── Auth guard ──────────────────────────────────────────────────────────

@bp.before_request
def _require_auth() -> Any:
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


# ── Semantic backend abstraction ────────────────────────────────────────

@dataclass
class _SemanticBackend:
    index_fn: Callable[..., Any]
    search_fn: Callable[..., Any]
    module_path: str


@dataclass(frozen=True)
class _SemanticSearchOutcome:
    hits: List[RankedHit]
    degraded: bool = False
    degraded_reason: Optional[str] = None


class _Metrics:
    """Thread-safe request metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.search_requests: int = 0
        self.index_requests: int = 0
        self.rerank_requests: int = 0
        self.errors: int = 0
        self._avg_search_ms: float = 0.0
        self._avg_search_n: int = 0
        self.last_search_ms: Optional[float] = None
        self.last_error: Optional[str] = None

    def record_search(self, took_ms: float, *, ok: bool) -> None:
        with self._lock:
            self.search_requests += 1
            if ok:
                self._avg_search_n += 1
                self._avg_search_ms += (took_ms - self._avg_search_ms) / float(self._avg_search_n)
                self.last_search_ms = took_ms
            else:
                self.errors += 1

    def record_index(self, *, ok: bool) -> None:
        with self._lock:
            self.index_requests += 1
            if not ok:
                self.errors += 1

    def record_rerank(self, *, ok: bool) -> None:
        with self._lock:
            self.rerank_requests += 1
            if not ok:
                self.errors += 1

    def record_error(self, message: str) -> None:
        with self._lock:
            self.errors += 1
            self.last_error = message

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "search_requests": self.search_requests,
                "index_requests": self.index_requests,
                "rerank_requests": self.rerank_requests,
                "errors": self.errors,
                "avg_search_ms": round(self._avg_search_ms, 3) if self._avg_search_n else 0.0,
                "last_search_ms": round(self.last_search_ms, 3) if self.last_search_ms is not None else None,
                "last_error": self.last_error,
            }


_metrics = _Metrics()

# ── Cache Integration ─────────────────────────────────────────────────

_rag_cache = None


def _get_rag_cache():
    """Get or create RAG cache instance (lazy initialization)."""
    global _rag_cache
    if _rag_cache is None:
        _rag_cache = get_rag_cache()
        logger.info("RAG cache initialized (TTL=600s, local_size=1000)")
    return _rag_cache


def _generate_cache_key(
    namespace: str, query: str, top_k: int, mode: str = "hybrid",
    include_text: bool = True, include_metadata: bool = True,
) -> str:
    """Generate cache key for RAG search results.

    Args:
        namespace: Document namespace
        query: Search query
        top_k: Number of results
        mode: Search mode (hybrid, bm25, semantic)
        include_text: Whether text is included in results
        include_metadata: Whether metadata is included in results

    Returns:
        Cache key string
    """
    import hashlib
    key_base = f"{mode}:{namespace}:{query}:{top_k}:t{int(include_text)}:m{int(include_metadata)}"
    key_hash = hashlib.md5(key_base.encode()).hexdigest()[:12]
    return f"rag:{mode}:{namespace}:{key_hash}"


# ── Singletons (double-checked locking) ────────────────────────────────

_bm25_lock = threading.Lock()
_bm25_index: Optional[BM25SqliteIndex] = None

_semantic_lock = threading.Lock()
_semantic_backend: Optional[_SemanticBackend] = None


def init_rag_api() -> None:
    """Reset RAG API state for test isolation.
    
    Call this before each test to ensure clean state.
    Resets metrics, BM25 index, and semantic backend singletons.
    """
    global _metrics, _bm25_index, _semantic_backend
    _metrics = _Metrics()
    _bm25_index = None
    _semantic_backend = None
    logger.debug("RAG API state reset for test isolation")


def _get_bm25() -> BM25SqliteIndex:
    global _bm25_index
    if _bm25_index is not None:
        return _bm25_index
    with _bm25_lock:
        if _bm25_index is None:
            _bm25_index = BM25SqliteIndex(BM25Config(db_path=_DEFAULT_DB_PATH))
            logger.info("RAG BM25 index initialized (db_path=%s)", _DEFAULT_DB_PATH)
    return _bm25_index


def _load_semantic_backend() -> Optional[_SemanticBackend]:
    global _semantic_backend
    if _semantic_backend is not None:
        return _semantic_backend

    with _semantic_lock:
        if _semantic_backend is not None:
            return _semantic_backend

        # Priority 1: External backend from env var
        backend_module = _SEMANTIC_BACKEND_MODULE
        # Priority 2: Built-in VectorStore-based backend
        if not backend_module:
            backend_module = "copilot_core.rag.semantic_backend"

        try:
            mod = importlib.import_module(backend_module)
        except Exception:
            logger.exception("Failed to import semantic backend: %s", backend_module)
            return None

        index_fn = getattr(mod, "rag_semantic_index", None) or getattr(mod, "semantic_index", None)
        search_fn = getattr(mod, "rag_semantic_search", None) or getattr(mod, "semantic_search", None)

        if callable(index_fn) and callable(search_fn):
            _semantic_backend = _SemanticBackend(
                index_fn=index_fn,
                search_fn=search_fn,
                module_path=backend_module,
            )
            logger.info("Semantic backend loaded: %s", backend_module)
            return _semantic_backend

    return None


# ── SearXNG Client (Web Search) ─────────────────────────────────────────

_searxng_lock = threading.Lock()
_searxng_client: Optional[SearXNGClient] = None


def _get_searxng_client() -> SearXNGClient:
    """Get or create global SearXNG client instance."""
    global _searxng_client
    if _searxng_client is None:
        with _searxng_lock:
            if _searxng_client is None:
                _searxng_client = SearXNGClient(base_url=_SEARXNG_BASE_URL, timeout=10)
                logger.info("SearXNG client initialized (base_url=%s)", _SEARXNG_BASE_URL)
    return _searxng_client


async def _searxng_search(
    query: str,
    categories: Optional[List[str]] = None,
    top_k: int = 10,
    warnings: Optional[List[str]] = None,
) -> List[SearXNGResult]:
    """Search SearXNG for web results.
    
    Args:
        query: Search query
        categories: SearXNG categories (e.g., ['general', 'news', 'weather'])
        top_k: Maximum results to return
        warnings: List to append warnings to
    
    Returns:
        List of SearXNGResult objects
    """
    if warnings is None:
        warnings = []
    
    client = _get_searxng_client()
    
    try:
        results = await client.search(query=query, categories=categories, top_k=top_k)
        return results
    
    except Exception as exc:
        logger.warning("SearXNG search failed for query '%s': %s", query, exc)
        warnings.append(f"Web search (SearXNG) failed: {exc}")
        return []


# ── Internal helpers ────────────────────────────────────────────────────

def _semantic_index(
    *,
    namespace: str,
    documents: Sequence[Dict[str, Any]],
    warnings: List[str],
) -> int:
    backend = _load_semantic_backend()
    if backend is None:
        warnings.append("semantic backend not configured; BM25-only indexing performed")
        return 0

    try:
        result = backend.index_fn(namespace=namespace, documents=documents)
    except TypeError:
        result = backend.index_fn(documents=documents, namespace=namespace)
    except Exception as exc:
        logger.exception("Semantic index failed (namespace=%s)", namespace)
        warnings.append("semantic index failed; BM25-only index is still updated")
        _metrics.record_error(f"semantic index failed: {exc}")
        return 0

    if isinstance(result, int):
        return result
    if isinstance(result, list):
        return len(result)
    return 0


def _semantic_search(
    *,
    namespace: str,
    query: str,
    top_k: int,
    warnings: List[str],
) -> _SemanticSearchOutcome:
    backend = _load_semantic_backend()
    if backend is None:
        warnings.append("semantic backend not configured; returning BM25-only results")
        return _SemanticSearchOutcome(
            hits=[],
            degraded=True,
            degraded_reason="semantic_backend_unavailable",
        )

    try:
        raw = backend.search_fn(namespace=namespace, query=query, top_k=top_k)
    except TypeError:
        raw = backend.search_fn(query=query, top_k=top_k, namespace=namespace)
    except Exception as exc:
        logger.exception("Semantic search failed (namespace=%s)", namespace)
        warnings.append("semantic search failed; returning BM25-only results")
        _metrics.record_error(f"semantic search failed: {exc}")
        return _SemanticSearchOutcome(
            hits=[],
            degraded=True,
            degraded_reason="semantic_backend_failed",
        )

    hits: List[RankedHit] = []
    if not raw:
        return _SemanticSearchOutcome(hits=hits)

    for i, item in enumerate(raw, start=1):
        doc_id: Optional[str] = None
        score: float = 0.0

        if isinstance(item, dict):
            doc_id = item.get("id") or item.get("doc_id") or item.get("document_id")
            try:
                score = float(item.get("score", 0.0))
            except Exception:
                score = 0.0
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            doc_id = str(item[0]) if item[0] is not None else None
            try:
                score = float(item[1])
            except Exception:
                score = 0.0
        else:
            doc_id = getattr(item, "id", None) or getattr(item, "doc_id", None)
            try:
                score = float(getattr(item, "score", 0.0))
            except Exception:
                score = 0.0

        if not doc_id:
            continue
        hits.append(RankedHit(doc_id=str(doc_id), score=float(score), rank=int(i)))

    return _SemanticSearchOutcome(hits=hits)


def _clamp_top_k(raw: Any, default: int = 10) -> int:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(v, _MAX_TOP_K))


def _enrich_results(
    bm25: BM25SqliteIndex,
    namespace: str,
    doc_ids: List[str],
    include_text: bool,
    include_metadata: bool,
) -> Dict[str, Dict[str, Any]]:
    if not doc_ids or (not include_text and not include_metadata):
        return {}
    return bm25.get_documents(namespace=namespace, doc_ids=doc_ids)


def _build_result_entry(
    doc_id: str,
    score: float,
    docs: Dict[str, Dict[str, Any]],
    include_text: bool,
    include_metadata: bool,
    **extra: Any,
) -> Dict[str, Any]:
    doc = docs.get(doc_id, {})
    entry: Dict[str, Any] = {"id": doc_id, "score": round(score, 6)}
    entry.update(extra)
    if include_text:
        entry["text"] = doc.get("text")
    if include_metadata:
        entry["metadata"] = doc.get("metadata")
    return entry


def _dedupe_preserve_order(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _normalize_multi_queries(raw_queries: Any) -> List[str]:
    if not isinstance(raw_queries, list):
        raise ValueError("queries must be a list")

    queries: List[str] = []
    for raw_query in raw_queries:
        if not isinstance(raw_query, str):
            raise ValueError("queries must contain only strings")
        query = raw_query.strip()
        if not query:
            raise ValueError("queries must not contain blank values")
        queries.append(query)

    queries = _dedupe_preserve_order(queries)
    if not queries:
        raise ValueError("queries required")
    if len(queries) > _MAX_MULTI_QUERY_VARIATIONS:
        raise ValueError(
            f"queries must contain between 1 and {_MAX_MULTI_QUERY_VARIATIONS} items"
        )
    return queries


def _accumulate_multi_query_hits(
    aggregate: Dict[str, Dict[str, Any]],
    hits: Sequence[Any],
    *,
    query: str,
    source: str,
    weight: float,
    rrf_k: int,
) -> None:
    for hit in hits:
        doc_id = getattr(hit, "doc_id", None)
        if not doc_id:
            continue

        try:
            rank = int(getattr(hit, "rank", 1) or 1)
        except (TypeError, ValueError):
            rank = 1
        if rank <= 0:
            rank = 1

        try:
            score = float(getattr(hit, "score", 0.0))
        except (TypeError, ValueError):
            score = 0.0

        item = aggregate.setdefault(str(doc_id), {
            "score": 0.0,
            "lexical_rank": None,
            "semantic_rank": None,
            "lexical_score": None,
            "semantic_score": None,
            "matched_queries": [],
        })

        item["score"] += float(weight) / float(rrf_k + rank)
        item["matched_queries"] = _dedupe_preserve_order([*item["matched_queries"], query])

        rank_key = f"{source}_rank"
        score_key = f"{source}_score"

        previous_rank = item.get(rank_key)
        if previous_rank is None or rank < previous_rank:
            item[rank_key] = rank
            item[score_key] = score
        elif item.get(score_key) is None or score > item[score_key]:
            item[score_key] = score


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: POST /api/rag/search  –  Hybrid Search (BM25 + Semantic + RRF)
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/search", methods=["POST"])
def rag_search() -> Tuple[Any, int] | Any:
    """Hybrid search combining BM25 lexical and semantic results via RRF.
    
    Results are cached with TTL=600s (10 min) for improved performance.
    Cache hit rate target: >80% for frequently accessed queries.
    """
    # Rate limiting check
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response
    
    started = time.monotonic()
    warnings: List[str] = []
    ok = False
    cache_hit = False

    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        namespace = str(data.get("namespace", "default") or "default")
        
        # Namespace validation
        if not _validate_namespace(namespace):
            return jsonify({"error": "invalid namespace format"}), 400
        
        query = str(data.get("query", "")).strip()

        if not query:
            return jsonify({"error": "query required"}), 400

        top_k = _clamp_top_k(data.get("top_k", 10))

        # Auto-classify query if no explicit use_lexical/use_semantic flags
        auto_classify = data.get("auto_classify", False)
        if auto_classify:
            try:
                from copilot_core.rag.query_router import classify_query
                classification = classify_query(query)
                # Map classification to search mode
                qt = classification.query_type.value if hasattr(classification.query_type, 'value') else str(classification.query_type)
                if qt in ("factual", "entity_lookup"):
                    data.setdefault("use_lexical", True)
                    data.setdefault("use_semantic", False)
                elif qt in ("conceptual", "how_to"):
                    data.setdefault("use_lexical", True)
                    data.setdefault("use_semantic", True)
                    data.setdefault("semantic_weight", 1.5)
                warnings.append(f"auto_classified: {qt} (confidence={classification.confidence:.2f})")
            except Exception as exc:
                logger.debug("Query auto-classification failed: %s", exc)

        use_lexical = bool(data.get("use_lexical", True))
        use_semantic = bool(data.get("use_semantic", True))
        rrf_k = max(1, int(data.get("rrf_k", 60)))
        lexical_weight = max(0.0, float(data.get("lexical_weight", 1.0)))
        semantic_weight = max(0.0, float(data.get("semantic_weight", 1.0)))
        include_text = bool(data.get("include_text", True))
        include_metadata = bool(data.get("include_metadata", True))

        if not use_lexical and not use_semantic:
            return jsonify({"error": "at least one of use_lexical/use_semantic must be true"}), 400

        # Determine search mode for cache key
        if use_lexical and use_semantic:
            mode = "hybrid_rrf"
        elif use_lexical:
            mode = "bm25"
        else:
            mode = "semantic"
        
        # Generate cache key
        cache_key = _generate_cache_key(namespace, query, top_k, mode, include_text, include_metadata)
        
        # Try cache first (only for hybrid and bm25 modes with default weights)
        use_cache = (
            mode in ("hybrid_rrf", "bm25") and
            rrf_k == 60 and
            lexical_weight == 1.0 and
            semantic_weight == 1.0
        )
        
        if use_cache:
            cache = _get_rag_cache()
            cached_result = asyncio.run(cache.get(cache_key))
            if cached_result is not None:
                cache_hit = True
                logger.debug("RAG cache HIT: %s", cache_key)
                took_ms = (time.monotonic() - started) * 1000.0
                cached_payload = dict(cached_result)
                cached_payload.setdefault("effective_mode", cached_payload.get("mode"))
                cached_payload.setdefault("degraded", False)
                cached_payload.setdefault("degraded_reason", None)
                return jsonify({
                    **cached_payload,
                    "cache_hit": True,
                    "took_ms": round(took_ms, 3),
                })

        bm25 = _get_bm25()

        lexical_hits: List[BM25Hit] = []
        semantic_hits: List[RankedHit] = []
        semantic_outcome = _SemanticSearchOutcome(hits=[])

        if use_lexical:
            lexical_hits = bm25.search(
                namespace=namespace, query=query, top_k=top_k,
                include_text=False, include_metadata=False,
            )

        if use_semantic:
            semantic_outcome = _semantic_search(
                namespace=namespace, query=query, top_k=top_k, warnings=warnings,
            )
            semantic_hits = semantic_outcome.hits

        mode: str
        effective_mode: str
        results: List[Dict[str, Any]] = []

        if use_lexical and use_semantic:
            fused = reciprocal_rank_fusion(
                lexical_hits=[
                    RankedHit(doc_id=h.doc_id, score=h.score, rank=h.rank) for h in lexical_hits
                ],
                semantic_hits=semantic_hits,
                top_k=top_k, k=rrf_k,
                lexical_weight=lexical_weight, semantic_weight=semantic_weight,
            )
            mode = "hybrid_rrf"
            doc_ids = [f.doc_id for f in fused]
            docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)

            for f in fused:
                results.append(_build_result_entry(
                    f.doc_id, f.fused_score, docs, include_text, include_metadata,
                    fused_score=round(f.fused_score, 6),
                    lexical_rank=f.lexical_rank, semantic_rank=f.semantic_rank,
                    lexical_score=f.lexical_score, semantic_score=f.semantic_score,
                ))

        elif use_lexical:
            mode = "bm25"
            trimmed = lexical_hits[:top_k]
            doc_ids = [h.doc_id for h in trimmed]
            docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)
            for h in trimmed:
                results.append(_build_result_entry(
                    h.doc_id, h.score, docs, include_text, include_metadata,
                    lexical_score=round(h.score, 6), lexical_rank=h.rank,
                ))
        else:
            mode = "semantic"
            trimmed = semantic_hits[:top_k]
            doc_ids = [h.doc_id for h in trimmed]
            docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)
            for h in trimmed:
                results.append(_build_result_entry(
                    h.doc_id, h.score, docs, include_text, include_metadata,
                    semantic_score=round(h.score, 6), semantic_rank=h.rank,
                ))

        degraded = bool(use_semantic and semantic_outcome.degraded)
        degraded_reason = semantic_outcome.degraded_reason if degraded else None
        effective_mode = mode
        if degraded:
            effective_mode = "bm25" if use_lexical else "semantic"

        ok = True
        took_ms = (time.monotonic() - started) * 1000.0

        response_data = {
            "namespace": namespace,
            "query": query,
            "mode": mode,
            "effective_mode": effective_mode,
            "degraded": degraded,
            "degraded_reason": degraded_reason,
            "results": results,
            "result_count": len(results),
            "warnings": warnings,
            "took_ms": round(took_ms, 3),
            "cache_hit": cache_hit,
        }
        
        # Cache result (only for cacheable queries, not on cache hit)
        if use_cache and not cache_hit:
            try:
                cache = _get_rag_cache()
                # Store cacheable subset of data (exclude took_ms which varies)
                cache_data = {
                    "namespace": namespace,
                    "query": query,
                    "mode": mode,
                    "effective_mode": effective_mode,
                    "degraded": degraded,
                    "degraded_reason": degraded_reason,
                    "results": results,
                    "result_count": len(results),
                    "warnings": warnings,
                }
                # Use TTL from cache config (default 600s)
                asyncio.run(cache.set(cache_key, cache_data))
                logger.debug("RAG cache SET: %s", cache_key)
            except Exception as e:
                logger.warning("Failed to cache RAG result: %s", e)
        
        return jsonify(response_data)

    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("RAG hybrid search failed")
        return jsonify({"error": "RAG search failed"}), 500
    finally:
        took_ms = (time.monotonic() - started) * 1000.0
        _metrics.record_search(took_ms, ok=ok)


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 1B: POST /api/rag/search/multi  –  Bounded Multi-Query Hybrid Search
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/search/multi", methods=["POST"])
def rag_search_multi() -> Tuple[Any, int] | Any:
    """Bounded multi-query hybrid search on the existing RAG family."""
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response

    started = time.monotonic()
    warnings: List[str] = []
    degraded_reasons: List[str] = []
    ok = False

    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        namespace = str(data.get("namespace", "default") or "default")

        if not _validate_namespace(namespace):
            return jsonify({"error": "invalid namespace format"}), 400

        queries = _normalize_multi_queries(data.get("queries"))
        top_k = _clamp_top_k(data.get("top_k", 10))
        include_text = bool(data.get("include_text", True))
        include_metadata = bool(data.get("include_metadata", True))
        use_lexical = bool(data.get("use_lexical", True))
        use_semantic = bool(data.get("use_semantic", True))
        rrf_k = max(1, int(data.get("rrf_k", 60)))
        lexical_weight = max(0.0, float(data.get("lexical_weight", 1.0)))
        semantic_weight = max(0.0, float(data.get("semantic_weight", 1.0)))

        if not use_lexical and not use_semantic:
            return jsonify({"error": "at least one of use_lexical/use_semantic must be true"}), 400

        bm25 = _get_bm25()
        aggregate: Dict[str, Dict[str, Any]] = {}

        for query in queries:
            if use_lexical:
                lexical_hits = bm25.search(
                    namespace=namespace,
                    query=query,
                    top_k=top_k,
                    include_text=False,
                    include_metadata=False,
                )
                _accumulate_multi_query_hits(
                    aggregate,
                    lexical_hits,
                    query=query,
                    source="lexical",
                    weight=lexical_weight,
                    rrf_k=rrf_k,
                )

            if use_semantic:
                semantic_outcome = _semantic_search(
                    namespace=namespace,
                    query=query,
                    top_k=top_k,
                    warnings=warnings,
                )
                if semantic_outcome.degraded and semantic_outcome.degraded_reason:
                    degraded_reasons.append(semantic_outcome.degraded_reason)

                _accumulate_multi_query_hits(
                    aggregate,
                    semantic_outcome.hits,
                    query=query,
                    source="semantic",
                    weight=semantic_weight,
                    rrf_k=rrf_k,
                )

        ranked = sorted(
            aggregate.items(),
            key=lambda item: (-float(item[1]["score"]), item[0]),
        )[:top_k]
        doc_ids = [doc_id for doc_id, _ in ranked]
        docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)

        results: List[Dict[str, Any]] = []
        for doc_id, item in ranked:
            lexical_score = item.get("lexical_score")
            semantic_score = item.get("semantic_score")
            matched_queries = item.get("matched_queries", [])
            results.append(_build_result_entry(
                doc_id,
                float(item["score"]),
                docs,
                include_text,
                include_metadata,
                fused_score=round(float(item["score"]), 6),
                lexical_rank=item.get("lexical_rank"),
                semantic_rank=item.get("semantic_rank"),
                lexical_score=round(float(lexical_score), 6) if lexical_score is not None else None,
                semantic_score=round(float(semantic_score), 6) if semantic_score is not None else None,
                matched_queries=matched_queries,
                query_match_count=len(matched_queries),
            ))

        if use_lexical and use_semantic:
            mode = "multi_hybrid_rrf"
        elif use_lexical:
            mode = "multi_bm25"
        else:
            mode = "multi_semantic"

        degraded = bool(degraded_reasons)
        unique_degraded_reasons = _dedupe_preserve_order(degraded_reasons)
        degraded_reason = None
        if degraded:
            degraded_reason = (
                unique_degraded_reasons[0]
                if len(unique_degraded_reasons) == 1
                else "semantic_backend_partially_degraded"
            )

        effective_mode = mode
        if degraded:
            effective_mode = "multi_bm25" if use_lexical else "multi_semantic"

        ok = True
        took_ms = (time.monotonic() - started) * 1000.0
        return jsonify({
            "namespace": namespace,
            "queries": queries,
            "query_count": len(queries),
            "mode": mode,
            "effective_mode": effective_mode,
            "degraded": degraded,
            "degraded_reason": degraded_reason,
            "results": results,
            "result_count": len(results),
            "warnings": _dedupe_preserve_order(warnings),
            "took_ms": round(took_ms, 3),
        })

    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("RAG multi-query search failed")
        return jsonify({"error": "RAG multi-query search failed"}), 500
    finally:
        took_ms = (time.monotonic() - started) * 1000.0
        _metrics.record_search(took_ms, ok=ok)


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: POST /api/rag/search/bm25  –  BM25-only lexical search
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/search/bm25", methods=["POST"])
def rag_search_bm25() -> Tuple[Any, int] | Any:
    """BM25 lexical search only."""
    # Rate limiting check
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response
    
    started = time.monotonic()
    ok = False

    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        namespace = str(data.get("namespace", "default") or "default")
        
        # Namespace validation
        if not _validate_namespace(namespace):
            return jsonify({"error": "invalid namespace format"}), 400
        
        query = str(data.get("query", "")).strip()

        if not query:
            return jsonify({"error": "query required"}), 400

        top_k = _clamp_top_k(data.get("top_k", 10))
        include_text = bool(data.get("include_text", True))
        include_metadata = bool(data.get("include_metadata", True))

        bm25 = _get_bm25()
        hits = bm25.search(
            namespace=namespace, query=query, top_k=top_k,
            include_text=include_text, include_metadata=include_metadata,
        )

        results: List[Dict[str, Any]] = []
        for h in hits:
            entry: Dict[str, Any] = {
                "id": h.doc_id,
                "score": round(h.score, 6),
                "rank": h.rank,
            }
            if include_text:
                entry["text"] = h.text
            if include_metadata:
                entry["metadata"] = h.metadata
            results.append(entry)

        ok = True
        took_ms = (time.monotonic() - started) * 1000.0
        return jsonify({
            "namespace": namespace,
            "query": query,
            "mode": "bm25",
            "results": results,
            "result_count": len(results),
            "took_ms": round(took_ms, 3),
        })

    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("RAG BM25 search failed")
        return jsonify({"error": "RAG BM25 search failed"}), 500
    finally:
        took_ms = (time.monotonic() - started) * 1000.0
        _metrics.record_search(took_ms, ok=ok)


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 3: POST /api/rag/search/semantic  –  Semantic-only search
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/search/semantic", methods=["POST"])
def rag_search_semantic() -> Tuple[Any, int] | Any:
    """Semantic (embedding-based) search only."""
    # Rate limiting check
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response
    
    started = time.monotonic()
    warnings: List[str] = []
    ok = False

    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        namespace = str(data.get("namespace", "default") or "default")
        
        # Namespace validation
        if not _validate_namespace(namespace):
            return jsonify({"error": "invalid namespace format"}), 400
        
        query = str(data.get("query", "")).strip()

        if not query:
            return jsonify({"error": "query required"}), 400

        top_k = _clamp_top_k(data.get("top_k", 10))
        include_text = bool(data.get("include_text", True))
        include_metadata = bool(data.get("include_metadata", True))

        semantic_outcome = _semantic_search(
            namespace=namespace, query=query, top_k=top_k, warnings=warnings,
        )
        hits = semantic_outcome.hits

        bm25 = _get_bm25()
        doc_ids = [h.doc_id for h in hits[:top_k]]
        docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)

        results: List[Dict[str, Any]] = []
        for h in hits[:top_k]:
            results.append(_build_result_entry(
                h.doc_id, h.score, docs, include_text, include_metadata,
                semantic_score=round(h.score, 6), semantic_rank=h.rank,
            ))

        ok = True
        took_ms = (time.monotonic() - started) * 1000.0
        return jsonify({
            "namespace": namespace,
            "query": query,
            "mode": "semantic",
            "results": results,
            "result_count": len(results),
            "warnings": warnings,
            "took_ms": round(took_ms, 3),
        })

    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("RAG semantic search failed")
        return jsonify({"error": "RAG semantic search failed"}), 500
    finally:
        took_ms = (time.monotonic() - started) * 1000.0
        _metrics.record_search(took_ms, ok=ok)


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 4: POST /api/rag/rerank  –  RRF Reranking
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/rerank", methods=["POST"])
def rag_rerank() -> Tuple[Any, int] | Any:
    """Rerank pre-existing hit lists using Reciprocal Rank Fusion."""
    # Rate limiting check
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response
    
    started = time.monotonic()
    ok = False

    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}

        lexical_raw = data.get("lexical_hits", [])
        semantic_raw = data.get("semantic_hits", [])

        if not lexical_raw and not semantic_raw:
            return jsonify({"error": "at least one of lexical_hits/semantic_hits required"}), 400

        if len(lexical_raw) > _MAX_RERANK_HITS or len(semantic_raw) > _MAX_RERANK_HITS:
            return jsonify({"error": f"max {_MAX_RERANK_HITS} hits per list"}), 400

        top_k = _clamp_top_k(data.get("top_k", 10))
        rrf_k = max(1, int(data.get("rrf_k", 60)))
        lexical_weight = max(0.0, float(data.get("lexical_weight", 1.0)))
        semantic_weight = max(0.0, float(data.get("semantic_weight", 1.0)))

        def _parse_hits(raw: List[Dict[str, Any]]) -> List[RankedHit]:
            hits: List[RankedHit] = []
            for i, item in enumerate(raw, start=1):
                doc_id = str(item.get("id") or item.get("doc_id", "")).strip()
                if not doc_id:
                    continue
                score = float(item.get("score", 0.0))
                rank = int(item.get("rank", i))
                hits.append(RankedHit(doc_id=doc_id, score=score, rank=rank))
            return hits

        lexical_hits = _parse_hits(lexical_raw)
        semantic_hits = _parse_hits(semantic_raw)

        fused = reciprocal_rank_fusion(
            lexical_hits=lexical_hits,
            semantic_hits=semantic_hits,
            top_k=top_k, k=rrf_k,
            lexical_weight=lexical_weight, semantic_weight=semantic_weight,
        )

        results: List[Dict[str, Any]] = []
        for f in fused:
            results.append({
                "id": f.doc_id,
                "fused_score": round(f.fused_score, 6),
                "lexical_rank": f.lexical_rank,
                "semantic_rank": f.semantic_rank,
                "lexical_score": f.lexical_score,
                "semantic_score": f.semantic_score,
            })

        ok = True
        took_ms = (time.monotonic() - started) * 1000.0
        return jsonify({
            "results": results,
            "result_count": len(results),
            "rrf_k": rrf_k,
            "took_ms": round(took_ms, 3),
        })

    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("RAG rerank failed")
        return jsonify({"error": "RAG rerank failed"}), 500
    finally:
        _metrics.record_rerank(ok=ok)


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 5: GET /api/rag/stats  –  Index Statistics
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/stats", methods=["GET"])
def rag_stats() -> Tuple[Any, int] | Any:
    """Return BM25 index statistics, request metrics, and cache stats."""
    # Rate limiting check
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response
    
    namespace = request.args.get("namespace", "default")
    
    # Namespace validation
    if not _validate_namespace(namespace):
        return jsonify({"error": "invalid namespace format"}), 400

    try:
        bm25 = _get_bm25()
        s = bm25.stats(namespace=namespace)
        
        # Get cache stats
        cache_stats = None
        try:
            cache = _get_rag_cache()
            cache_stats = asyncio.run(cache.get_stats())
        except Exception as e:
            logger.debug("Failed to get cache stats: %s", e)
        
        metrics = _metrics.snapshot()
        
        # Add cache metrics to response
        if cache_stats:
            metrics["cache"] = {
                "enabled": cache_stats.get("hybrid", {}).get("enabled", False),
                "hit_rate": cache_stats.get("hybrid", {}).get("metrics", {}).get("hit_rate", 0.0),
                "local_size": cache_stats.get("local", {}).get("size", 0),
                "local_max_size": cache_stats.get("local", {}).get("max_size", 0),
                "redis_connected": cache_stats.get("redis", {}).get("connected", False),
            }
        
        return jsonify({
            "namespace": s.namespace,
            "doc_count": s.doc_count,
            "term_count": s.term_count,
            "posting_count": s.posting_count,
            "avg_doc_len": round(s.avg_doc_len, 3),
            "total_doc_len": s.total_doc_len,
            "updated_at": s.updated_at,
            "db_path": s.db_path,
            "db_size_bytes": s.db_size_bytes,
            "schema_version": s.schema_version,
            "semantic_backend": _SEMANTIC_BACKEND_MODULE or None,
            "metrics": metrics,
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("RAG stats failed")
        return jsonify({"error": "RAG stats failed"}), 500


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 6: GET /api/rag/health  –  RAG Operational Readiness
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/health", methods=["GET"])
def rag_health() -> Tuple[Any, int] | Any:
    """Return machine-checkable RAG operational readiness truth.

    Returns BM25 readiness, semantic backend availability, and cache status.
    No auth required — this is a read-only operational surface.
    """
    try:
        bm25_ready = False
        bm25_stats = {"available": False}
        try:
            bm25 = _get_bm25()
            s = bm25.stats(namespace="default")
            bm25_ready = True
            bm25_stats = {
                "available": True,
                "doc_count": s.doc_count,
                "term_count": s.term_count,
            }
        except Exception as e:
            bm25_stats = {"available": False, "reason": str(e)}

        semantic_available = False
        semantic_reason = "semantic_backend_unavailable"
        semantic_module = None
        try:
            backend = _load_semantic_backend()
            if backend is not None:
                semantic_available = True
                semantic_reason = None
                semantic_module = backend.module_path
            else:
                semantic_reason = "semantic_backend_unavailable"
        except Exception:
            semantic_reason = "semantic_backend_failed"

        cache_status = {"available": False}
        try:
            cache = _get_rag_cache()
            cache_status = {"available": True, "type": "redis" if hasattr(cache, 'redis') else "local"}
        except Exception:
            pass

        healthy = bm25_ready and semantic_reason in (None, "semantic_backend_unavailable")
        return jsonify({
            "healthy": healthy,
            "bm25": bm25_stats,
            "semantic": {
                "available": semantic_available,
                "reason": semantic_reason,
                "module": semantic_module,
            },
            "cache": cache_status,
        })
    except Exception as e:
        logger.exception("RAG health check failed")
        return jsonify({"healthy": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 6a: POST /api/rag/index  –  Document Indexing
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/index", methods=["POST"])
def rag_index() -> Tuple[Any, int] | Any:
    """Upsert documents into the BM25 (and optionally semantic) index."""
    # Rate limiting check
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response
    
    started = time.monotonic()
    warnings: List[str] = []
    ok = False

    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        namespace = str(data.get("namespace", "default") or "default")
        
        # Namespace validation
        if not _validate_namespace(namespace):
            return jsonify({"error": "invalid namespace format"}), 400
        
        documents_data = data.get("documents", [])
        index_semantic = bool(data.get("index_semantic", True))

        if not documents_data:
            return jsonify({"error": "documents required"}), 400
        if len(documents_data) > _MAX_DOCUMENTS_PER_REQUEST:
            return jsonify({"error": f"max {_MAX_DOCUMENTS_PER_REQUEST} documents per request"}), 400

        docs: List[BM25Document] = []
        for d in documents_data:
            doc_id = str(d.get("id", "")).strip()
            text = str(d.get("text", "")).strip()
            metadata = d.get("metadata")

            if not doc_id:
                return jsonify({"error": "document id required"}), 400
            if not text:
                return jsonify({"error": "document text required"}), 400

            docs.append(BM25Document(doc_id=doc_id, text=text, metadata=metadata))

        bm25 = _get_bm25()
        bm25_indexed, bm25_errors = bm25.upsert_documents(namespace=namespace, documents=docs)

        semantic_indexed = 0
        if index_semantic:
            semantic_indexed = _semantic_index(
                namespace=namespace, documents=documents_data, warnings=warnings,
            )

        # Auto-invalidate cache for the indexed namespace
        try:
            cache = _get_rag_cache()
            if cache and bm25_indexed > 0:
                cache.invalidate_pattern(f"rag:*:{namespace}:*")
                logger.debug("RAG cache invalidated for namespace '%s'", namespace)
        except Exception:
            logger.debug("RAG cache invalidation failed (non-critical)")

        ok = True
        took_ms = (time.monotonic() - started) * 1000.0
        return jsonify({
            "namespace": namespace,
            "bm25_indexed": bm25_indexed,
            "semantic_indexed": semantic_indexed,
            "errors": bm25_errors,
            "warnings": warnings,
            "took_ms": round(took_ms, 3),
            "cache_invalidated": bm25_indexed > 0,
        })

    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("RAG index failed")
        return jsonify({"error": "RAG index failed"}), 500
    finally:
        _metrics.record_index(ok=ok)


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 6a: POST /api/rag/documents  –  Single Document Create
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/documents", methods=["POST"])
def rag_documents_create() -> Tuple[Any, int] | Any:
    """Create or update one document on the documented RAG document seam."""
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response

    warnings: List[str] = []
    ok = False
    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        namespace = str(data.get("namespace", "default") or "default")
        if not _validate_namespace(namespace):
            return jsonify({"error": "invalid namespace format"}), 400

        doc_id = str(data.get("doc_id", "") or "").strip()
        content = str(data.get("content", "") or "").strip()
        metadata = data.get("metadata")

        if not doc_id:
            return jsonify({"error": "doc_id required"}), 400
        if not content:
            return jsonify({"error": "content required"}), 400

        bm25 = _get_bm25()
        indexed, errors = bm25.upsert_documents(
            namespace=namespace,
            documents=[BM25Document(doc_id=doc_id, text=content, metadata=metadata)],
        )

        semantic_indexed = 0
        semantic_degraded = False
        semantic_reason = None
        semantic_payload = [{"id": doc_id, "text": content, "metadata": metadata}]
        semantic_indexed = _semantic_index(namespace=namespace, documents=semantic_payload, warnings=warnings)
        if semantic_indexed == 0:
            semantic_degraded = True
            semantic_reason = "semantic_backend_unavailable_or_failed"

        try:
            cache = _get_rag_cache()
            cache.invalidate_pattern(f"rag:*:{namespace}:*")
        except Exception:
            logger.debug("RAG cache invalidation failed after document create (non-critical)")

        ok = True
        return jsonify({
            "namespace": namespace,
            "doc_id": doc_id,
            "created": indexed > 0,
            "bm25_indexed": indexed > 0,
            "semantic_indexed": semantic_indexed > 0,
            "degraded": semantic_degraded,
            "degraded_reason": semantic_reason,
            "errors": errors,
            "warnings": warnings,
            "cache_invalidated": indexed > 0,
        })
    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("RAG document create failed")
        return jsonify({"error": "RAG document create failed"}), 500
    finally:
        _metrics.record_index(ok=ok)


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 6aa: DELETE /api/rag/documents/<doc_id>  –  Single Document Delete
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/documents/<doc_id>", methods=["DELETE"])
def rag_documents_delete(doc_id: str) -> Tuple[Any, int] | Any:
    """Delete one document on the documented RAG document seam."""
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response

    warnings: List[str] = []
    ok = False
    try:
        namespace = str(request.args.get("namespace", "default") or "default")
        if not _validate_namespace(namespace):
            return jsonify({"error": "invalid namespace format"}), 400

        cleaned_doc_id = str(doc_id or "").strip()
        if not cleaned_doc_id:
            return jsonify({"error": "doc_id required"}), 400

        bm25 = _get_bm25()
        deleted = bm25.delete_document(namespace=namespace, doc_id=cleaned_doc_id)
        if not deleted:
            return jsonify({
                "error": "document not found",
                "namespace": namespace,
                "doc_id": cleaned_doc_id,
                "deleted": False,
            }), 404

        warnings.append("semantic delete unavailable; BM25 document deleted")
        try:
            cache = _get_rag_cache()
            cache.invalidate_pattern(f"rag:*:{namespace}:*")
        except Exception:
            logger.debug("RAG cache invalidation failed after document delete (non-critical)")

        ok = True
        return jsonify({
            "namespace": namespace,
            "doc_id": cleaned_doc_id,
            "deleted": True,
            "semantic_deleted": False,
            "degraded": True,
            "degraded_reason": "semantic_delete_unavailable",
            "warnings": warnings,
            "cache_invalidated": True,
        })
    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("RAG document delete failed")
        return jsonify({"error": "RAG document delete failed"}), 500
    finally:
        _metrics.record_index(ok=ok)


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 6b: POST /api/rag/cache/clear  –  Clear RAG Cache
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/cache/clear", methods=["POST"])
def rag_cache_clear() -> Tuple[Any, int] | Any:
    """Clear RAG search result cache.
    
    Useful for:
    - Forcing fresh results after document updates
    - Debugging cache issues
    - Performance testing (cold vs warm cache)
    
    Request body (optional):
        - namespace: Clear only specific namespace (default: all)
        - pattern: Cache key pattern to clear (default: all)
    
    Returns:
        Status and number of entries cleared
    """
    # Rate limiting check
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response
    
    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        namespace = data.get("namespace")
        pattern = data.get("pattern")
        
        cache = _get_rag_cache()
        
        # Clear all or filter by namespace/pattern
        if namespace:
            # Clear only keys matching the namespace prefix
            prefix = f"rag:{namespace}:"
            count = asyncio.run(cache.clear_by_prefix(prefix))
            cleared = f"namespace '{namespace}' ({count} entries)"
        elif pattern:
            # Clear keys matching a glob pattern
            count = asyncio.run(cache.clear_by_pattern(f"*{pattern}*"))
            cleared = f"pattern '{pattern}' ({count} entries)"
        else:
            asyncio.run(cache.clear())
            cleared = "all"
        
        logger.info("RAG cache cleared: %s", cleared)
        
        return jsonify({
            "status": "ok",
            "cleared": cleared,
            "message": f"RAG cache cleared ({cleared})",
        })
    except Exception as e:
        logger.exception("Failed to clear RAG cache")
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 7: POST /api/rag/search/enhanced  –  Hybrid Search with SearXNG
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/search/enhanced", methods=["POST"])
def rag_search_enhanced() -> Tuple[Any, int] | Any:
    """Enhanced hybrid search with SearXNG web integration.
    
    This endpoint implements the full RAG pipeline with query routing:
    1. Classify query as local, web, or hybrid
    2. Search local sources (BM25 + Semantic)
    3. Search web (SearXNG) if needed
    4. Fuse results with weighted RRF
    
    Request body:
        - query: Search query string (required)
        - namespace: Index namespace (default: "default")
        - use_web: Force web search (default: auto-detect via query router)
        - top_k: Max results (default: 10)
        - searxng_categories: SearXNG categories (default: ["general", "news"])
        - weights: Fusion weights (default: {"local": 1.0, "semantic": 0.8, "web": 0.5})
    
    Returns:
        Enhanced search results with query classification and multi-source fusion
    """
    # Rate limiting check
    rate_limit_response = _rate_limit_rag()
    if rate_limit_response is not None:
        return rate_limit_response
    
    started = time.monotonic()
    warnings: List[str] = []
    ok = False
    
    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        namespace = str(data.get("namespace", "default") or "default")
        
        # Namespace validation
        if not _validate_namespace(namespace):
            return jsonify({"error": "invalid namespace format"}), 400
        
        query = str(data.get("query", "")).strip()
        
        if not query:
            return jsonify({"error": "query required"}), 400
        
        top_k = _clamp_top_k(data.get("top_k", 10))
        use_web = data.get("use_web")  # None = auto-detect
        searxng_categories = data.get("searxng_categories", ["general", "news"])
        
        # Fusion weights
        weights_config = data.get("weights", {})
        local_weight = float(weights_config.get("local", 1.0))
        semantic_weight = float(weights_config.get("semantic", 0.8))
        web_weight = float(weights_config.get("web", 0.5))
        
        include_text = bool(data.get("include_text", True))
        include_metadata = bool(data.get("include_metadata", True))
        
        # Step 1: Query Classification
        classification = classify_query(query)
        query_type = classification.query_type
        
        # Determine if web search is needed
        perform_web_search = False
        if use_web is True:
            perform_web_search = True
        elif use_web is False:
            perform_web_search = False
        else:
            # Auto-detect based on query classification
            perform_web_search = classification.use_web_search
        
        logger.info(
            "Enhanced RAG search: query='%s', type=%s, web=%s",
            query,
            query_type.value,
            perform_web_search,
        )
        
        bm25 = _get_bm25()
        
        # Step 2: Local Search (BM25 + Semantic)
        lexical_hits: List[BM25Hit] = []
        semantic_hits: List[RankedHit] = []
        
        # Always do BM25 for local context
        lexical_hits = bm25.search(
            namespace=namespace,
            query=query,
            top_k=top_k,
            include_text=False,
            include_metadata=False,
        )
        
        # Semantic search (if backend configured)
        semantic_outcome = _semantic_search(
            namespace=namespace,
            query=query,
            top_k=top_k,
            warnings=warnings,
        )
        semantic_hits = semantic_outcome.hits
        
        # Step 3: Web Search (SearXNG) if needed
        web_results: List[SearXNGResult] = []
        
        if perform_web_search:
            web_results = _searxng_search_sync(
                query=query,
                categories=searxng_categories,
                top_k=top_k,
                warnings=warnings,
            )
        
        # Step 4: Result Fusion
        mode: str
        results: List[Dict[str, Any]] = []
        
        if query_type == QueryType.LOCAL and not perform_web_search:
            # Local-only mode
            mode = "local"
            
            # Fuse BM25 + Semantic
            if lexical_hits and semantic_hits:
                fused = reciprocal_rank_fusion(
                    lexical_hits=[
                        RankedHit(doc_id=h.doc_id, score=h.score, rank=h.rank)
                        for h in lexical_hits
                    ],
                    semantic_hits=semantic_hits,
                    top_k=top_k,
                    k=60,
                    lexical_weight=local_weight,
                    semantic_weight=semantic_weight,
                )
                doc_ids = [f.doc_id for f in fused]
                docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)
                
                for f in fused:
                    results.append(_build_result_entry(
                        f.doc_id,
                        f.fused_score,
                        docs,
                        include_text,
                        include_metadata,
                        fused_score=round(f.fused_score, 6),
                        lexical_rank=f.lexical_rank,
                        semantic_rank=f.semantic_rank,
                    ))
            elif lexical_hits:
                # BM25 only
                trimmed = lexical_hits[:top_k]
                doc_ids = [h.doc_id for h in trimmed]
                docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)
                for h in trimmed:
                    results.append(_build_result_entry(
                        h.doc_id,
                        h.score,
                        docs,
                        include_text,
                        include_metadata,
                        lexical_score=round(h.score, 6),
                        lexical_rank=h.rank,
                    ))
            else:
                # Semantic only
                trimmed = semantic_hits[:top_k]
                doc_ids = [h.doc_id for h in trimmed]
                docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)
                for h in trimmed:
                    results.append(_build_result_entry(
                        h.doc_id,
                        h.score,
                        docs,
                        include_text,
                        include_metadata,
                        semantic_score=round(h.score, 6),
                        semantic_rank=h.rank,
                    ))
        
        elif query_type == QueryType.WEB and perform_web_search:
            # Web-only mode
            mode = "web"
            
            for i, web_result in enumerate(web_results[:top_k]):
                results.append({
                    "id": web_result.url,
                    "title": web_result.title,
                    "url": web_result.url,
                    "content": web_result.content,
                    "score": round(web_result.score, 6),
                    "rank": i + 1,
                    "source": "searxng",
                    "category": web_result.category,
                    "engine": web_result.engine,
                })
        
        else:
            # Hybrid mode (local + web)
            mode = "hybrid"
            
            # First, fuse local results
            local_results: List[Dict[str, Any]] = []
            
            if lexical_hits and semantic_hits:
                fused = reciprocal_rank_fusion(
                    lexical_hits=[
                        RankedHit(doc_id=h.doc_id, score=h.score, rank=h.rank)
                        for h in lexical_hits
                    ],
                    semantic_hits=semantic_hits,
                    top_k=top_k,
                    k=60,
                    lexical_weight=local_weight,
                    semantic_weight=semantic_weight,
                )
                doc_ids = [f.doc_id for f in fused]
                docs = _enrich_results(bm25, namespace, doc_ids, include_text, include_metadata)
                
                for f in fused:
                    local_results.append(_build_result_entry(
                        f.doc_id,
                        f.fused_score,
                        docs,
                        include_text,
                        include_metadata,
                        fused_score=round(f.fused_score, 6),
                        source="local",
                    ))
            elif lexical_hits:
                for h in lexical_hits[:top_k]:
                    local_results.append({
                        "id": h.doc_id,
                        "score": round(h.score, 6),
                        "rank": h.rank,
                        "source": "local_bm25",
                    })
            
            # Add web results
            web_result_dicts = [
                {
                    "id": web_result.url,
                    "title": web_result.title,
                    "url": web_result.url,
                    "content": web_result.content,
                    "score": round(web_result.score * web_weight, 6),
                    "source": "searxng",
                    "category": web_result.category,
                    "engine": web_result.engine,
                }
                for web_result in web_results[:top_k]
            ]
            
            # Combine and re-rank (simple approach: local first, then web)
            # For more sophisticated fusion, implement cross-source RRF
            results = local_results + web_result_dicts
            results = results[:top_k]

        degraded = False
        degraded_reason: Optional[str] = None
        effective_mode = mode

        if mode == "local":
            degraded = semantic_outcome.degraded
            degraded_reason = semantic_outcome.degraded_reason if degraded else None
            if lexical_hits and semantic_hits:
                effective_mode = "local_hybrid"
            elif lexical_hits:
                effective_mode = "local_bm25"
            elif semantic_hits:
                effective_mode = "local_semantic"
            else:
                effective_mode = "local_bm25" if degraded else "local"
        elif mode == "hybrid":
            degraded = semantic_outcome.degraded
            degraded_reason = semantic_outcome.degraded_reason if degraded else None
            effective_mode = "hybrid_bm25_web" if degraded else "hybrid_local_web"

        ok = True
        took_ms = (time.monotonic() - started) * 1000.0

        return jsonify({
            "namespace": namespace,
            "query": query,
            "mode": mode,
            "effective_mode": effective_mode,
            "degraded": degraded,
            "degraded_reason": degraded_reason,
            "query_classification": {
                "type": query_type.value,
                "confidence": classification.confidence,
                "web_keywords": classification.web_keywords_found,
                "local_keywords": classification.local_keywords_found,
                "reasoning": classification.reasoning,
            },
            "results": results,
            "result_count": len(results),
            "sources_used": {
                "local_bm25": len(lexical_hits) > 0,
                "semantic": len(semantic_hits) > 0,
                "web_searxng": len(web_results) > 0,
            },
            "warnings": warnings,
            "took_ms": round(took_ms, 3),
        })
    
    except ValueError as exc:
        _metrics.record_error(str(exc))
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        _metrics.record_error(str(exc))
        logger.exception("Enhanced RAG search failed")
        return jsonify({"error": "Enhanced RAG search failed"}), 500
    finally:
        took_ms = (time.monotonic() - started) * 1000.0
        _metrics.record_search(took_ms, ok=ok)


def _searxng_search_sync(
    query: str,
    categories: Optional[List[str]] = None,
    top_k: int = 10,
    warnings: Optional[List[str]] = None,
) -> List[SearXNGResult]:
    """Synchronous wrapper for SearXNG search.

    Flask is synchronous, but our SearXNG client is async.
    This wrapper handles the async call properly.
    """
    client = _get_searxng_client()

    try:
        coro = client.search(query=query, categories=categories, top_k=top_k)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, asyncio.wait_for(coro, timeout=10))
                return future.result(timeout=12)

        return asyncio.run(asyncio.wait_for(coro, timeout=10))

    except Exception as exc:
        logger.warning("SearXNG sync search failed for query '%s': %s", query, exc)
        if warnings is not None:
            warnings.append(f"Web search failed: {exc}")
        return []
