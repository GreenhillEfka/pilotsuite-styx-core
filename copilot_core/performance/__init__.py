"""Performance-Optimierung für Core-Datenbank-Queries.

Re-exports from rootfs performance module for backward compatibility.
"""

import sys
from pathlib import Path

# Resolve rootfs performance module for cache infrastructure
# __init__.py is at: copilot_core/performance/__init__.py
# rootfs performance.py is at: copilot_core/rootfs/usr/src/app/copilot_core/performance.py
_init_path = Path(__file__).resolve()
_copilot_core_dir = _init_path.parent.parent  # copilot_core/
_perf_py = _copilot_core_dir / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "performance.py"

if _perf_py.exists():
    import importlib.util
    _spec = importlib.util.spec_from_file_location("performance_rootfs", _perf_py)
    _perf_module = importlib.util.module_from_spec(_spec)
    sys.modules["copilot_core.performance_rootfs"] = _perf_module
    _spec.loader.exec_module(_perf_module)
    
    # Re-export cache infrastructure (these exist in performance.py)
    brain_graph_cache = _perf_module.brain_graph_cache
    ml_cache = _perf_module.ml_cache
    api_response_cache = _perf_module.api_response_cache
    QueryCache = _perf_module.QueryCache
    cached = _perf_module.cached
    
    # Also export query optimizer classes from local module
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
        "brain_graph_cache",
        "ml_cache",
        "api_response_cache",
        "QueryCache",
        "cached",
    ]
else:
    # Fallback to local query_optimizer only
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
