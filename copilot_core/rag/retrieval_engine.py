"""P2-004: Context Retrieval Engine — Multi-Stage Retrieval, Re-Ranking."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import time

logger = logging.getLogger(__name__)


class RetrievalStage(Enum):
    """Stages in multi-stage retrieval."""
    INITIAL = "initial"  # First pass retrieval
    RE_RANK = "re_rank"  # Re-ranking stage
    FILTER = "filter"  # Filtering stage
    FINAL = "final"  # Final selection


@dataclass
class RetrievalResult:
    """Result from retrieval stage."""
    stage: RetrievalStage
    documents: List[Any]
    scores: List[float]
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalConfig:
    """Configuration for retrieval engine."""
    initial_k: int = 50  # Initial retrieval count
    final_k: int = 10  # Final result count
    re_rank_enabled: bool = True
    filter_enabled: bool = True
    diversity_enabled: bool = False
    min_score_threshold: float = 0.3
    max_latency_ms: float = 500.0


class ContextRetrievalEngine:
    """Multi-stage context retrieval with re-ranking."""

    def __init__(
        self,
        vector_search_fn: Callable[[str, int], List[Tuple[Any, float]]],
        re_rank_fn: Optional[Callable[[str, List[Any]], List[Tuple[Any, float]]]] = None,
        config: Optional[RetrievalConfig] = None,
    ):
        self.vector_search_fn = vector_search_fn
        self.re_rank_fn = re_rank_fn
        self.config = config or RetrievalConfig()
        self._stats = {
            "total_queries": 0,
            "avg_latency_ms": 0.0,
            "cache_hits": 0,
            "re_rank_applied": 0,
        }

    def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        k: Optional[int] = None,
    ) -> RetrievalResult:
        """Retrieve context with multi-stage pipeline."""
        start = time.time()
        self._stats["total_queries"] += 1
        
        k = k or self.config.final_k
        
        # Stage 1: Initial retrieval
        initial_result = self._initial_retrieval(query, self.config.initial_k)
        
        # Stage 2: Re-ranking (optional)
        if self.config.re_rank_enabled and self.re_rank_fn:
            rerank_result = self._re_rank(query, initial_result.documents)
        else:
            rerank_result = initial_result
        
        # Stage 3: Filtering (optional)
        if self.config.filter_enabled and filters:
            filtered_result = self._filter(rerank_result, filters)
        else:
            filtered_result = rerank_result
        
        # Stage 4: Final selection
        final_result = self._select_top_k(filtered_result, k)
        
        # Update stats
        total_latency = (time.time() - start) * 1000
        self._stats["avg_latency_ms"] = (
            self._stats["avg_latency_ms"] * (self._stats["total_queries"] - 1) + total_latency
        ) / self._stats["total_queries"]
        
        final_result.metadata["total_latency_ms"] = total_latency
        final_result.metadata["query"] = query
        
        return final_result

    def _initial_retrieval(self, query: str, k: int) -> RetrievalResult:
        """Initial vector-based retrieval."""
        start = time.time()
        
        try:
            results = self.vector_search_fn(query, k)
            documents = [r[0] for r in results]
            scores = [r[1] for r in results]
        except Exception as e:
            logger.warning(f"Initial retrieval failed: {e}")
            documents, scores = [], []
        
        latency = (time.time() - start) * 1000
        
        return RetrievalResult(
            stage=RetrievalStage.INITIAL,
            documents=documents,
            scores=scores,
            latency_ms=latency
        )

    def _re_rank(self, query: str, documents: List[Any]) -> RetrievalResult:
        """Re-rank documents using cross-encoder."""
        start = time.time()
        
        if not self.re_rank_fn or not documents:
            return RetrievalResult(
                stage=RetrievalStage.RE_RANK,
                documents=documents,
                scores=[],
                latency_ms=(time.time() - start) * 1000
            )
        
        try:
            reranked = self.re_rank_fn(query, documents)
            documents = [r[0] for r in reranked]
            scores = [r[1] for r in reranked]
            self._stats["re_rank_applied"] += 1
        except Exception as e:
            logger.warning(f"Re-ranking failed: {e}")
        
        return RetrievalResult(
            stage=RetrievalStage.RE_RANK,
            documents=documents,
            scores=scores,
            latency_ms=(time.time() - start) * 1000
        )

    def _filter(
        self,
        result: RetrievalResult,
        filters: Dict[str, Any]
    ) -> RetrievalResult:
        """Filter documents based on metadata."""
        start = time.time()
        
        filtered_docs = []
        filtered_scores = []
        
        for i, doc in enumerate(result.documents):
            if self._matches_filters(doc, filters):
                filtered_docs.append(doc)
                if i < len(result.scores):
                    filtered_scores.append(result.scores[i])
        
        return RetrievalResult(
            stage=RetrievalStage.FILTER,
            documents=filtered_docs,
            scores=filtered_scores,
            latency_ms=(time.time() - start) * 1000
        )

    def _matches_filters(self, document: Any, filters: Dict[str, Any]) -> bool:
        """Check if document matches all filters."""
        # Simplified filter matching
        for key, value in filters.items():
            if hasattr(document, 'metadata'):
                if document.metadata.get(key) != value:
                    return False
        return True

    def _select_top_k(self, result: RetrievalResult, k: int) -> RetrievalResult:
        """Select top-k documents."""
        start = time.time()
        
        # Sort by score
        if result.scores:
            indexed = list(enumerate(result.documents))
            indexed.sort(key=lambda x: result.scores[x[0]] if x[0] < len(result.scores) else 0, reverse=True)
            
            top_indices = [i for i, _ in indexed[:k]]
            documents = [result.documents[i] for i in top_indices]
            scores = [result.scores[i] for i in top_indices if i < len(result.scores)]
        else:
            documents = result.documents[:k]
            scores = []
        
        # Apply score threshold
        if self.config.min_score_threshold and scores:
            thresholded = []
            for i, doc in enumerate(documents):
                if i < len(scores) and scores[i] >= self.config.min_score_threshold:
                    thresholded.append(doc)
            documents = thresholded
        
        return RetrievalResult(
            stage=RetrievalStage.FINAL,
            documents=documents,
            scores=scores[:k],
            latency_ms=(time.time() - start) * 1000
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        return self._stats.copy()


# Global default retrieval engine
default_retrieval_engine: Optional[ContextRetrievalEngine] = None


def init_retrieval_engine(
    vector_search_fn: Callable,
    re_rank_fn: Optional[Callable] = None,
    config: Optional[RetrievalConfig] = None,
) -> ContextRetrievalEngine:
    """Initialize global retrieval engine."""
    global default_retrieval_engine
    default_retrieval_engine = ContextRetrievalEngine(vector_search_fn, re_rank_fn, config)
    return default_retrieval_engine


def retrieve_context(query: str, **kwargs) -> RetrievalResult:
    """Convenience function for context retrieval."""
    if default_retrieval_engine:
        return default_retrieval_engine.retrieve(query, **kwargs)
    return RetrievalResult(
        stage=RetrievalStage.FINAL,
        documents=[],
        scores=[],
        latency_ms=0.0
    )
