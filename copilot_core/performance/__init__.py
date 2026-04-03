"""Performance-Optimierung für Core-Datenbank-Queries."""

from .query_optimizer import (
    CacheEntry,
    IndexRecommendation,
    QueryMetrics,
    QueryOptimizer,
    QueryOptimizerSummary,
    QueryPattern,
    get_query_optimizer,
)

__all__ = [
    "CacheEntry",
    "IndexRecommendation",
    "QueryMetrics",
    "QueryOptimizer",
    "QueryOptimizerSummary",
    "QueryPattern",
    "get_query_optimizer",
]
