"""Live Metrics & KPI Service (Slice 168).

Tracks real-time performance indicators:
- API Latency Percentiles (p50, p95, p99)
- Event Processing Throughput
- System Resource Utilization
- Real-time Gauge Data for Dashboard
"""

from __future__ import annotations

import logging
import time
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

@dataclass
class MetricWindow:
    """Rolling window for metric samples."""
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    
    def add(self, value: float):
        self.samples.append(value)
        
    def get_stats(self) -> Dict[str, float]:
        if not self.samples:
            return {"p50": 0, "p95": 0, "p99": 0, "avg": 0}
        
        sorted_samples = sorted(list(self.samples))
        n = len(sorted_samples)
        return {
            "p50": sorted_samples[int(n * 0.5)],
            "p95": sorted_samples[int(n * 0.95)],
            "p99": sorted_samples[int(n * 0.99)],
            "avg": sum(sorted_samples) / n,
            "count": n
        }

class LiveMetricsProvider:
    """Background service for real-time dashboard metrics."""
    
    def __init__(self):
        self._latency_metrics: Dict[str, MetricWindow] = {}
        self._throughput: Dict[str, int] = {}
        self._start_time = time.monotonic()

    def record_latency(self, endpoint: str, duration_ms: float):
        """Records latency for a specific endpoint."""
        if endpoint not in self._latency_metrics:
            self._latency_metrics[endpoint] = MetricWindow()
        self._latency_metrics[endpoint].add(duration_ms)

    def record_event(self, event_type: str):
        """Increments throughput counter for an event type."""
        self._throughput[event_type] = self._throughput.get(event_type, 0) + 1

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Returns live data for the Dashboard Gauges."""
        total_latency = MetricWindow()
        for window in self._latency_metrics.values():
            for s in window.samples:
                total_latency.add(s)
        
        stats = total_latency.get_stats()
        uptime = time.monotonic() - self._start_time
        
        return {
            "gauges": {
                "avg_latency_ms": round(stats["avg"], 2),
                "p95_latency_ms": round(stats["p95"], 2),
                "events_per_sec": round(sum(self._throughput.values()) / max(1, uptime), 2),
                "error_rate_pct": 0.02 # Placeholder until circuit breaker integration
            },
            "system": {
                "cpu_usage_pct": 15.4, # Mock
                "mem_usage_mb": 245.0, # Mock
                "uptime_s": round(uptime, 0)
            },
            "ts": datetime.now(timezone.utc).isoformat()
        }

# Global Instance
_metrics_provider: Optional[LiveMetricsProvider] = None

def get_metrics_provider() -> LiveMetricsProvider:
    global _metrics_provider
    if _metrics_provider is None:
        _metrics_provider = LiveMetricsProvider()
    return _metrics_provider

# API Integration for Slice 168
def init_metrics_api(bp):
    @bp.route("/dashboard/live-metrics", methods=["GET"])
    def get_live_metrics():
        provider = get_metrics_provider()
        return {"ok": True, "metrics": provider.get_dashboard_metrics()}
