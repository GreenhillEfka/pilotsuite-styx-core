"""Dashboard Live KPIs (Slice 146).

Provides real-time KPIs for Dashboard:
- latency: p50/p95/p99/max/avg over 5m window
- throughput: ops/min, errors/min, queue_depth
- token_burn: total/in/out/min, burn_1h, budget_24h, budget_remaining, predictive burn
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    avg_ms: float
    samples: int


@dataclass
class ThroughputMetrics:
    ops_per_min: float
    errors_per_min: float
    queue_depth: int


@dataclass
class TokenBurnMetrics:
    total: int
    in_per_min: float
    out_per_min: float
    burn_1h: int
    budget_24h: int
    budget_remaining: int
    predicted_burn_1h: int


class KPIService:
    """Service for calculating and tracking Dashboard KPIs."""
    
    def __init__(self, window_minutes: float = 5.0):
        self._window = timedelta(minutes=window_minutes)
        self._latency_samples: deque[tuple[float, float]] = deque()  # (timestamp_ms, latency_ms)
        self._ops_counter = 0
        self._error_counter = 0
        self._queue_depth = 0
        
        # Token tracking
        self._tokens_in = 0
        self._tokens_out = 0
        self._token_history: deque[tuple[float, int]] = deque()  # (timestamp, total_burned)
        self._budget_24h = 1_000_000  # Default budget
        
    def record_latency(self, latency_ms: float):
        """Record a latency sample."""
        now = time.time()
        self._latency_samples.append((now, latency_ms))
        self._cleanup_old_samples()
        
    def record_operation(self, success: bool = True):
        """Record an operation (success or error)."""
        self._ops_counter += 1
        if not success:
            self._error_counter += 1
    
    def set_queue_depth(self, depth: int):
        """Update current queue depth."""
        self._queue_depth = depth
    
    def record_tokens(self, tokens_in: int, tokens_out: int):
        """Record token usage."""
        self._tokens_in += tokens_in
        self._tokens_out += tokens_out
        total = self._tokens_in + self._tokens_out
        self._token_history.append((time.time(), total))
        self._cleanup_token_history()
    
    def _cleanup_old_samples(self):
        """Remove samples outside the time window."""
        cutoff = time.time() - self._window.total_seconds()
        while self._latency_samples and self._latency_samples[0][0] < cutoff:
            self._latency_samples.popleft()
    
    def _cleanup_token_history(self):
        """Remove token history outside 24h window."""
        cutoff = time.time() - 86400  # 24 hours
        while self._token_history and self._token_history[0][0] < cutoff:
            self._token_history.popleft()
    
    def get_latency_metrics(self) -> LatencyMetrics:
        """Calculate latency percentiles over window."""
        if not self._latency_samples:
            return LatencyMetrics(0, 0, 0, 0, 0, 0)
        
        latencies = [s[1] for s in self._latency_samples]
        latencies.sort()
        n = len(latencies)
        
        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            return latencies[min(idx, n-1)]
        
        return LatencyMetrics(
            p50_ms=percentile(50),
            p95_ms=percentile(95),
            p99_ms=percentile(99),
            max_ms=latencies[-1],
            avg_ms=sum(latencies) / n,
            samples=n,
        )
    
    def get_throughput_metrics(self) -> ThroughputMetrics:
        """Calculate throughput metrics."""
        # Calculate ops/min over the window
        window_minutes = self._window.total_seconds() / 60
        ops_per_min = self._ops_counter / max(window_minutes, 1)
        errors_per_min = self._error_counter / max(window_minutes, 1)
        
        return ThroughputMetrics(
            ops_per_min=round(ops_per_min, 2),
            errors_per_min=round(errors_per_min, 2),
            queue_depth=self._queue_depth,
        )
    
    def get_token_metrics(self) -> TokenBurnMetrics:
        """Calculate token burn metrics."""
        now = time.time()
        
        # Calculate per-minute rates
        window_minutes = self._window.total_seconds() / 60
        in_per_min = self._tokens_in / max(window_minutes, 1)
        out_per_min = self._tokens_out / max(window_minutes, 1)
        
        # Calculate 1h burn
        one_hour_ago = now - 3600
        recent_burn = sum(burn for ts, burn in self._token_history if ts >= one_hour_ago)
        burn_1h = self._tokens_in + self._tokens_out - recent_burn if self._token_history else 0
        
        # Predictive burn (linear extrapolation)
        if len(self._token_history) >= 2:
            timespan = self._token_history[-1][0] - self._token_history[0][0]
            if timespan > 0:
                rate = (self._token_history[-1][1] - self._token_history[0][1]) / timespan
                predicted_burn_1h = int(rate * 3600)
            else:
                predicted_burn_1h = burn_1h * 12  # Simple 12x extrapolation
        else:
            predicted_burn_1h = burn_1h * 12
        
        total = self._tokens_in + self._tokens_out
        budget_remaining = self._budget_24h - total
        
        return TokenBurnMetrics(
            total=total,
            in_per_min=round(in_per_min, 2),
            out_per_min=round(out_per_min, 2),
            burn_1h=burn_1h,
            budget_24h=self._budget_24h,
            budget_remaining=max(0, budget_remaining),
            predicted_burn_1h=predicted_burn_1h,
        )
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all KPIs as dictionary."""
        latency = self.get_latency_metrics()
        throughput = self.get_throughput_metrics()
        tokens = self.get_token_metrics()
        
        return {
            "latency": {
                "p50_ms": latency.p50_ms,
                "p95_ms": latency.p95_ms,
                "p99_ms": latency.p99_ms,
                "max_ms": latency.max_ms,
                "avg_ms": latency.avg_ms,
                "samples": latency.samples,
            },
            "throughput": {
                "ops_per_min": throughput.ops_per_min,
                "errors_per_min": throughput.errors_per_min,
                "queue_depth": throughput.queue_depth,
            },
            "token_burn": {
                "total": tokens.total,
                "in_per_min": tokens.in_per_min,
                "out_per_min": tokens.out_per_min,
                "burn_1h": tokens.burn_1h,
                "budget_24h": tokens.budget_24h,
                "budget_remaining": tokens.budget_remaining,
                "predicted_burn_1h": tokens.predicted_burn_1h,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Global instance
_kpi_service: Optional[KPIService] = None


def get_kpi_service() -> KPIService:
    """Get singleton KPI service."""
    global _kpi_service
    if _kpi_service is None:
        _kpi_service = KPIService()
    return _kpi_service
