"""HNSW Vector Search Optimization (Slice 149).

Performance tuning for approximate nearest neighbor search.
"""

from __future__ import annotations

import logging
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


class HNSWOptimizer:
    """Optimizes HNSW index parameters for performance/accuracy tradeoff."""
    
    def __init__(
        self,
        dim: int = 384,
        target_recall: float = 0.95,
        target_latency_ms: float = 5.0,
    ):
        self.dim = dim
        self.target_recall = target_recall
        self.target_latency_ms = target_latency_ms
        self._optimal_params: Optional[Dict[str, Any]] = None
    
    def recommend_params(self, dataset_size: int) -> Dict[str, Any]:
        """Recommend HNSW parameters based on dataset size."""
        # M parameter: number of bi-directional links (higher = better recall, slower)
        if dataset_size < 1000:
            m = 8
        elif dataset_size < 10000:
            m = 16
        else:
            m = 32
        
        # ef_construction: size of dynamic candidate list during construction
        ef_construction = min(m * 10, 200)
        
        # ef_search: size of dynamic candidate list during search
        ef_search = min(m * 2, 50)
        
        self._optimal_params = {
            "M": m,
            "ef_construction": ef_construction,
            "ef_search": ef_search,
            "dim": self.dim,
            "max_elements": max(dataset_size * 2, 10000),
        }
        
        return self._optimal_params
    
    def benchmark_search(
        self,
        index,
        queries: np.ndarray,
        ground_truth: List[List[int]],
        k: int = 10,
    ) -> Dict[str, float]:
        """Benchmark search performance and recall."""
        import time
        
        recall_sum = 0.0
        latencies = []
        
        for i, query in enumerate(queries):
            start = time.monotonic()
            results = index.search(query, k=k)
            latency = (time.monotonic() - start) * 1000  # ms
            latencies.append(latency)
            
            # Calculate recall
            found_ids = {r[0] for r in results}
            expected_ids = set(ground_truth[i][:k])
            if expected_ids:
                recall = len(found_ids & expected_ids) / len(expected_ids)
                recall_sum += recall
        
        return {
            "avg_latency_ms": np.mean(latencies),
            "p99_latency_ms": np.percentile(latencies, 99),
            "avg_recall": recall_sum / len(queries) if queries else 0.0,
            "target_met": np.mean(latencies) <= self.target_latency_ms,
        }
    
    def auto_tune(
        self,
        index,
        queries: np.ndarray,
        ground_truth: List[List[int]],
    ) -> Dict[str, Any]:
        """Automatically tune parameters to meet targets."""
        current_params = self.recommend_params(len(ground_truth))
        
        # Benchmark current settings
        metrics = self.benchmark_search(index, queries, ground_truth)
        
        # Adjust ef_search if recall too low
        if metrics["avg_recall"] < self.target_recall:
            current_params["ef_search"] = min(current_params["ef_search"] * 2, 400)
            _LOGGER.info("Increased ef_search to %d for better recall", current_params["ef_search"])
        
        # Adjust ef_search if latency too high
        if metrics["avg_latency_ms"] > self.target_latency_ms * 1.5:
            current_params["ef_search"] = max(current_params["ef_search"] // 2, 10)
            _LOGGER.info("Decreased ef_search to %d for lower latency", current_params["ef_search"])
        
        return {
            "params": current_params,
            "metrics": metrics,
            "optimized": True,
        }
