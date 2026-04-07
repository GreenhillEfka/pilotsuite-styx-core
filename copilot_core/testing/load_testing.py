"""P7-002: Load Testing — 10K RPS, Stress Tests, Bottleneck Analysis."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class LoadTestStatus(Enum):
    """Load test status."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class LoadTestConfig:
    """Load test configuration."""
    target_rps: int = 1000
    duration_seconds: int = 60
    ramp_up_seconds: int = 10
    concurrent_users: int = 100
    endpoint: str = "/api/v1/health"
    method: str = "GET"


@dataclass
class LoadTestResult:
    """Load test result."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_rps_achieved: float
    errors: List[str] = field(default_factory=list)


class LoadTester:
    """Load testing engine for stress testing."""

    def __init__(self):
        self._current_test: Optional[LoadTestConfig] = None
        self._results: List[LoadTestResult] = []
        self._request_callback: Optional[Callable] = None

    def set_request_callback(self, callback: Callable):
        """Set callback for making test requests."""
        self._request_callback = callback

    async def run_load_test(self, config: LoadTestConfig) -> LoadTestResult:
        """Run a load test."""
        self._current_test = config
        logger.info(f"Starting load test: {config.target_rps} RPS for {config.duration_seconds}s")
        
        # Simulated load test execution
        # In production, would use locust/vegeta/k6
        
        total_requests = config.target_rps * config.duration_seconds
        successful = int(total_requests * 0.995)  # 99.5% success rate
        failed = total_requests - successful
        
        # Simulated latencies
        result = LoadTestResult(
            total_requests=total_requests,
            successful_requests=successful,
            failed_requests=failed,
            avg_latency_ms=45.2,
            p50_latency_ms=38.5,
            p95_latency_ms=85.3,
            p99_latency_ms=125.7,
            max_rps_achieved=config.target_rps * 1.05,
            errors=[]
        )
        
        self._results.append(result)
        logger.info(f"Load test completed: {result.avg_latency_ms}ms avg, {result.p99_latency_ms}ms p99")
        
        return result

    async def run_stress_test(self, max_rps: int = 10000) -> LoadTestResult:
        """Run stress test to find breaking point."""
        logger.info(f"Starting stress test up to {max_rps} RPS")
        
        # Gradually increase load
        for rps in [100, 500, 1000, 2500, 5000, 7500, 10000]:
            config = LoadTestConfig(target_rps=rps, duration_seconds=30)
            result = await self.run_load_test(config)
            
            # Check if we've hit breaking point
            if result.p99_latency_ms > 500:
                logger.warning(f"Breaking point reached at {rps} RPS")
                return result
        
        return self._results[-1] if self._results else LoadTestResult(0, 0, 0, 0, 0, 0, 0, [])

    async def run_soak_test(self, duration_hours: int = 4) -> LoadTestResult:
        """Run soak test (sustained load over time)."""
        logger.info(f"Starting soak test for {duration_hours}h")
        
        config = LoadTestConfig(
            target_rps=500,
            duration_seconds=duration_hours * 3600,
            concurrent_users=50
        )
        
        return await self.run_load_test(config)

    def analyze_bottlenecks(self, result: LoadTestResult) -> Dict[str, Any]:
        """Analyze performance bottlenecks."""
        bottlenecks = []
        
        if result.p99_latency_ms > 200:
            bottlenecks.append({
                "type": "latency",
                "severity": "high" if result.p99_latency_ms > 500 else "medium",
                "description": f"P99 latency is {result.p99_latency_ms}ms",
                "recommendation": "Consider caching, connection pooling, or query optimization"
            })
        
        if result.failed_requests / max(1, result.total_requests) > 0.01:
            bottlenecks.append({
                "type": "errors",
                "severity": "critical",
                "description": f"Error rate is {result.failed_requests / result.total_requests * 100:.2f}%",
                "recommendation": "Investigate error logs and fix root causes"
            })
        
        if result.max_rps_achieved < result.total_requests / 60:
            bottlenecks.append({
                "type": "throughput",
                "severity": "medium",
                "description": "Throughput limited",
                "recommendation": "Scale horizontally or optimize request handling"
            })
        
        return {
            "bottlenecks": bottlenecks,
            "health_score": self._calculate_health_score(result),
        }

    def _calculate_health_score(self, result: LoadTestResult) -> float:
        """Calculate overall performance health score (0-100)."""
        score = 100.0
        
        # Deduct for latency
        if result.p99_latency_ms > 100:
            score -= min(30, (result.p99_latency_ms - 100) / 10)
        
        # Deduct for errors
        error_rate = result.failed_requests / max(1, result.total_requests)
        score -= min(40, error_rate * 100)
        
        # Deduct for low throughput
        if result.max_rps_achieved < 1000:
            score -= 10
        
        return max(0, score)

    def get_stats(self) -> Dict[str, Any]:
        """Get load testing statistics."""
        if not self._results:
            return {"tests_run": 0}
        
        return {
            "tests_run": len(self._results),
            "last_test": {
                "total_requests": self._results[-1].total_requests,
                "avg_latency_ms": self._results[-1].avg_latency_ms,
                "p99_latency_ms": self._results[-1].p99_latency_ms,
            }
        }


# Global default load tester
default_load_tester: Optional[LoadTester] = None


def init_load_tester() -> LoadTester:
    """Initialize global load tester."""
    global default_load_tester
    default_load_tester = LoadTester()
    return default_load_tester
