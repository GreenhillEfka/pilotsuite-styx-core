"""Hybrid Search with Reciprocal Rank Fusion.

Combines lexical (BM25) and semantic search results using RRF for optimal ranking.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class RankedHit:
    """Ranked search result."""
    
    doc_id: str
    score: float
    rank: int


@dataclass(frozen=True)
class FusedHit:
    """Fused search result from RRF."""
    
    doc_id: str
    fused_score: float
    lexical_rank: Optional[int] = None
    semantic_rank: Optional[int] = None
    lexical_score: Optional[float] = None
    semantic_score: Optional[float] = None


def reciprocal_rank_fusion(
    *,
    lexical_hits: Sequence[RankedHit],
    semantic_hits: Sequence[RankedHit],
    top_k: int,
    k: int = 60,
    lexical_weight: float = 1.0,
    semantic_weight: float = 1.0,
) -> List[FusedHit]:
    """Reciprocal Rank Fusion for hybrid search.
    
    RRF formula: score = sum(1 / (k + rank_i)) for each result i
    
    Args:
        lexical_hits: Results from lexical (BM25) search
        semantic_hits: Results from semantic (embedding) search
        top_k: Number of top results to return
        k: RRF constant (default 60)
        lexical_weight: Weight for lexical scores
        semantic_weight: Weight for semantic scores
    
    Returns:
        Fused and ranked results
    """
    if top_k <= 0:
        return []
    if k <= 0:
        k = 60
    
    fused: Dict[str, float] = {}
    meta: Dict[str, Dict[str, Optional[float]]] = {}
    
    def add(source: str, hits: Sequence[RankedHit], weight: float) -> None:
        for h in hits:
            if not h.doc_id:
                continue
            r = int(h.rank) if h.rank and h.rank > 0 else 1
            fused[h.doc_id] = fused.get(h.doc_id, 0.0) + (float(weight) / float(k + r))
            
            m = meta.get(h.doc_id)
            if m is None:
                m = {
                    "lexical_rank": None,
                    "semantic_rank": None,
                    "lexical_score": None,
                    "semantic_score": None,
                }
                meta[h.doc_id] = m
            
            if source == "lexical":
                m["lexical_rank"] = float(r)
                m["lexical_score"] = float(h.score)
            elif source == "semantic":
                m["semantic_rank"] = float(r)
                m["semantic_score"] = float(h.score)
    
    add("lexical", lexical_hits, lexical_weight)
    add("semantic", semantic_hits, semantic_weight)
    
    ranked: List[Tuple[str, float]] = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]
    out: List[FusedHit] = []
    for doc_id, fused_score in ranked:
        m = meta.get(doc_id) or {}
        out.append(
            FusedHit(
                doc_id=doc_id,
                fused_score=float(fused_score),
                lexical_rank=int(m["lexical_rank"]) if m.get("lexical_rank") is not None else None,
                semantic_rank=int(m["semantic_rank"]) if m.get("semantic_rank") is not None else None,
                lexical_score=float(m["lexical_score"]) if m.get("lexical_score") is not None else None,
                semantic_score=float(m["semantic_score"]) if m.get("semantic_score") is not None else None,
            )
        )
    return out


# ── Hybrid Search Engine ────────────────────────────────────────────────

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .bm25 import BM25SqliteIndex
from .semantic_backend import SemanticBackend


@dataclass
class HybridSearchEngine:
    """Orchestrates lexical (BM25) + semantic search with RRF fusion.
    
    Combines BM25 keyword search with embedding-based semantic search
    using Reciprocal Rank Fusion for optimal ranking.
    
    Args:
        bm25_index: BM25 index for lexical search (BM25SqliteIndex instance)
        semantic_backend: Semantic backend callable (rag_semantic_search style)
        namespace: Default document namespace to search
        cache_ttl_seconds: TTL for cached results (default: 60s)
        rrf_k: RRF constant k (default: 60)
    """
    
    bm25_index: BM25SqliteIndex
    semantic_backend: Any  # Callable matching rag_semantic_search signature
    namespace: str = "default"
    cache_ttl_seconds: float = 60.0
    rrf_k: int = 60
    _cache: Dict[str, tuple] = field(default_factory=dict, repr=False)
    _cache_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    def search(
        self,
        query: str,
        namespace: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.0,
        include_debug: bool = False,
    ) -> Dict[str, Any]:
        """Execute hybrid search combining BM25 + semantic results via RRF.
        
        Args:
            query: Search query string
            namespace: Document namespace to search in (uses default if None)
            top_k: Maximum results to return
            min_score: Minimum fused score threshold (0.0 = no filter)
            include_debug: Include per-source scores in response
        
        Returns:
            Dict with:
            - items: List of result dicts with doc_id, fused_score, rank
            - count: Number of results
            - query: Original query
            - timing_ms: Time taken for search
            - bm25_count, semantic_count: Per-source result counts
            - debug (optional): BM25 and semantic scores per result
        """
        start = time.monotonic()
        ns = namespace or self.namespace
        
        if not query or not query.strip():
            return {
                "items": [],
                "count": 0,
                "query": query,
                "timing_ms": 0,
            }
        
        # Check cache
        cache_key = self._make_cache_key(query, ns, top_k, min_score)
        cached, cached_at = self._get_cached(cache_key)
        if cached is not None:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = dict(cached)
            result["timing_ms"] = round(elapsed_ms, 2)
            result["_cached"] = True
            result["_cached_at"] = cached_at
            return result
        
        # Execute both searches
        bm25_results = self._search_bm25(query, ns, top_k * 2)
        semantic_results = self._search_semantic(query, ns, top_k * 2)
        
        # Fuse with RRF
        fused = reciprocal_rank_fusion(
            lexical_hits=bm25_results,
            semantic_hits=semantic_results,
            top_k=top_k,
            k=self.rrf_k,
        )
        
        # Build response items
        items: List[Dict[str, Any]] = []
        for rank, hit in enumerate(fused, start=1):
            if hit.fused_score < min_score:
                continue
            item: Dict[str, Any] = {
                "doc_id": hit.doc_id,
                "fused_score": round(hit.fused_score, 6),
                "rank": rank,
            }
            if include_debug:
                item["_debug"] = {
                    "lexical_rank": hit.lexical_rank,
                    "semantic_rank": hit.semantic_rank,
                    "lexical_score": hit.lexical_score,
                    "semantic_score": hit.semantic_score,
                }
            items.append(item)
        
        elapsed_ms = (time.monotonic() - start) * 1000
        result = {
            "items": items,
            "count": len(items),
            "query": query,
            "namespace": ns,
            "timing_ms": round(elapsed_ms, 2),
            "bm25_count": len(bm25_results),
            "semantic_count": len(semantic_results),
        }
        
        self._set_cache(cache_key, result)
        return result
    
    def _search_bm25(
        self,
        query: str,
        namespace: str,
        top_k: int,
    ) -> Sequence[RankedHit]:
        """Execute BM25 search against the configured index."""
        try:
            hits = self.bm25_index.search(namespace=namespace, query=query, top_k=top_k)
            return [
                RankedHit(doc_id=hit.doc_id, score=hit.score, rank=hit.rank)
                for hit in hits
            ]
        except Exception:
            return []
    
    def _search_semantic(
        self,
        query: str,
        namespace: str,
        top_k: int,
    ) -> Sequence[RankedHit]:
        """Execute semantic search via the configured backend."""
        try:
            raw = self.semantic_backend(namespace=namespace, query=query, top_k=top_k)
            return [
                RankedHit(doc_id=str(h["id"]), score=float(h.get("score", 0.0)), rank=i + 1)
                for i, h in enumerate(raw)
            ]
        except Exception:
            return []
    
    def _make_cache_key(self, query: str, namespace: str, top_k: int, min_score: float) -> str:
        """Build a deterministic cache key."""
        content = f"{query}|{namespace}|{top_k}|{min_score}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _get_cached(self, key: str) -> tuple:
        """Get cached result if still valid."""
        with self._cache_lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.monotonic() - timestamp < self.cache_ttl_seconds:
                    return value, timestamp
                del self._cache[key]
        return None, None
    
    def _set_cache(self, key: str, value: Dict[str, Any]) -> None:
        """Cache a result, evicting oldest on overflow."""
        with self._cache_lock:
            if len(self._cache) >= 500:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            self._cache[key] = (dict(value), time.monotonic())
    
    def clear_cache(self) -> None:
        """Clear all cached search results."""
        with self._cache_lock:
            self._cache.clear()


# ── Convenience factory ─────────────────────────────────────────────────


def get_hybrid_search_engine(
    namespace: str = "default",
    cache_ttl_seconds: float = 60.0,
    rrf_k: int = 60,
) -> HybridSearchEngine:
    """Create a HybridSearchEngine from default backends.
    
    Returns a fully wired engine using the installed BM25 index
    and rag_semantic_search function.
    """
    try:
        bm25 = BM25SqliteIndex()
    except Exception:
        bm25 = BM25SqliteIndex()
    
    # Use the module-level rag_semantic_search as the semantic backend
    from . import semantic_backend as _sb
    sem_backend = _sb.rag_semantic_search
    
    return HybridSearchEngine(
        bm25_index=bm25,
        semantic_backend=sem_backend,
        namespace=namespace,
        cache_ttl_seconds=cache_ttl_seconds,
        rrf_k=rrf_k,
    )
