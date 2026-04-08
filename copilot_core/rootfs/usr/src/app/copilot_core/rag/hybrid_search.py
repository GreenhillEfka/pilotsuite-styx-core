"""Hybrid Search with Reciprocal Rank Fusion.

Combines lexical (BM25) and semantic search results using RRF for optimal ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


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
