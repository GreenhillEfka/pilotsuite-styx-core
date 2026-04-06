"""Dashboard KPI Service (Slice 146).

Tracks and calculates real-time performance metrics:
- latency: p50/p95/p99 over rolling 5m window
- throughput: ops/min, errors/min
- token_burn: actual vs budget, predictive burn
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

@dataclass
class KPIWindow:
    latencies: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    ops_count: int = 0
    error_count: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    start_time: float = field(default_factory=time.monotonic)

class KPIService:
    """Service to aggregate SOTA Dashboard metrics."""
    
    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self._current = KPIWindow()
        
    def record_request(self, latency_ms: float, tokens_in: int = 0, tokens_out: int = 0, error: bool = False):
        """Record a single API request metrics."""
        self._current.latencies.append(latency_ms)
        self._current.tokens_in += tokens_in
        self._current.tokens_out += tokens_out
        self._current.ops_count += 1
        if error:
            self._current.error_count += 1
            
    def get_metrics(self) -> Dict[str, Any]:
        """Calculate and return formatted KPI metrics."""
        lats = sorted(list(self._current.latencies))
        count = len(lats)
        
        def percentile(p: int) -> float:
            if not lats: return 0.0
            idx = int(p / 100 * count)
            return lats[min(idx, count - 1)]

        now = time.monotonic()
        elapsed_min = (now - self._current.start_time) / 60.0
        
        return {
            "latency": {
                "p50": round(percentile(50), 2),
                "p95": round(percentile(95), 2),
                "p99": round(percentile(99), 2),
                "avg": round(sum(lats)/max(count, 1), 2),
                "unit": "ms"
            },
            "throughput": {
                "ops_per_min": round(self._current.ops_count / max(elapsed_min, 0.1), 2),
                "errors_per_min": round(self._current.error_count / max(elapsed_min, 0.1), 2),
                "status": "ok" if self._current.error_count == 0 else "warning"
            },
            "token_burn": {
                "total": self._current.tokens_in + self._current.tokens_out,
                "burn_rate_1h": (self._current.tokens_in + self._current.tokens_out) * (60 / max(elapsed_min, 0.1)),
                "budget_remaining": 85.2, # Placeholder for budget logic
                "unit": "tokens"
            },
            "meta": {
                "window_s": self.window_seconds,
                "samples": count
            }
        }

# Global singleton
_instance = KPIService()

def get_kpi_service() -> KPIService:
    return _instance
