"""RAG (Retrieval-Augmented Generation) module for PilotSuite.

Provides hybrid search combining BM25 and vector similarity search
with Reciprocal Rank Fusion (RRF) for optimal re-ranking.
"""

from .hybrid_search import (
    HybridSearchEngine,
    HybridSearchResult,
    HybridSearchConfig,
    rrf_fusion,
)

__all__ = [
    "HybridSearchEngine",
    "HybridSearchResult",
    "HybridSearchConfig",
    "rrf_fusion",
]
