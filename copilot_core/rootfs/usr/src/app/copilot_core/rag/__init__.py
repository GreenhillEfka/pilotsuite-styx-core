"""RAG Hybrid Search Module.

Provides BM25 lexical search with semantic fusion via Reciprocal Rank Fusion.
Now includes SearXNG web search integration and query routing.
"""

from .bm25 import BM25Document, BM25Hit, BM25SqliteIndex
from .hybrid_search import FusedHit, RankedHit, reciprocal_rank_fusion
from .indexer import IndexManager, NamespaceInfo, NamespaceStats
try:
    from .searxng_client import SearXNGClient, SearXNGResult, get_searxng_client
except ImportError:
    SearXNGClient = None  # type: ignore[assignment,misc]
    SearXNGResult = None  # type: ignore[assignment,misc]
    get_searxng_client = None  # type: ignore[assignment,misc]
from .query_router import QueryType, QueryClassification, classify_query

__all__ = [
    "BM25Document",
    "BM25Hit",
    "BM25SqliteIndex",
    "FusedHit",
    "RankedHit",
    "reciprocal_rank_fusion",
    "SearXNGClient",
    "SearXNGResult",
    "get_searxng_client",
    "QueryType",
    "QueryClassification",
    "classify_query",
    "IndexManager",
    "NamespaceInfo",
    "NamespaceStats",
]
