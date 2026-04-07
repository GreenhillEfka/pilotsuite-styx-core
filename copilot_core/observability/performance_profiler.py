"""Performance Profiler — CPU, Memory, Latency, Optimization."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict
import functools

logger = logging.getLogger(__name__)


@dataclass
class ProfilerResult:
    """Profiler measurement result."""
    function_name: str
    calls: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p95_time_ms: float


class PerformanceProfiler:
    """Profiles function execution time and resource usage."""

    def __init__(self):
        self._measurements: Dict[str, List[float]] = defaultdict(list)
        self._call_counts: Dict[str, int] = defaultdict(int)
        self._enabled: bool = True

    def profile(self, func: Callable) -> Callable:
        """Decorator to profile a function."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self._enabled:
                return func(*args, **kwargs)

            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                self._record(func.__name__, elapsed)

        return wrapper

    def _record(self, func_name: str, elapsed_ms: float):
        """Record a measurement."""
        self._measurements[func_name].append(elapsed_ms)
        self._call_counts[func_name] += 1

    def get_results(self) -> List[ProfilerResult]:
        """Get profiling results."""
        results = []
        for func_name, times in self._measurements.items():
            if not times:
                continue
            sorted_times = sorted(times)
            p95_idx = int(len(sorted_times) * 0.95)
            results.append(ProfilerResult(
                function_name=func_name,
                calls=self._call_counts[func_name],
                total_time_ms=sum(times),
                avg_time_ms=sum(times) / len(times),
                min_time_ms=min(times),
                max_time_ms=max(times),
                p95_time_ms=sorted_times[p95_idx] if p95_idx < len(sorted_times) else max(times),
            ))
        return sorted(results, key=lambda r: r.total_time_ms, reverse=True)

    def enable(self):
        """Enable profiling."""
        self._enabled = True

    def disable(self):
        """Disable profiling."""
        self._enabled = False

    def reset(self):
        """Clear all measurements."""
        self._measurements.clear()
        self._call_counts.clear()

    def get_slow_functions(self, threshold_ms: float = 100) -> List[str]:
        """Get functions that exceed threshold."""
        return [r.function_name for r in self.get_results() if r.avg_time_ms > threshold_ms]

    def get_stats(self) -> Dict[str, Any]:
        """Get profiler statistics."""
        results = self.get_results()
        return {
            "tracked_functions": len(results),
            "total_calls": sum(r.calls for r in results),
            "slow_functions": len(self.get_slow_functions()),
            "top_3_slowest": [r.function_name for r in results[:3]],
        }


# Global default profiler
default_profiler: Optional[PerformanceProfiler] = None


def init_profiler() -> PerformanceProfiler:
    global default_profiler
    default_profiler = PerformanceProfiler()
    return default_profiler
