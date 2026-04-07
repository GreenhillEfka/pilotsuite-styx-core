"""Performance Benchmarks — Load testing and profiling for PilotSuite Core."""
from __future__ import annotations

import logging
import time
import statistics
from typing import Dict, Any, List, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Benchmark result."""
    test_name: str
    iterations: int
    total_time_seconds: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p50_time_ms: float
    p95_time_ms: float
    p99_time_ms: float
    requests_per_second: float
    errors: int = 0


@dataclass
class LoadTestResult:
    """Load test result."""
    concurrent_users: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: float
    p95_response_time_ms: float
    error_rate: float
    requests_per_second: float


class PerformanceBenchmark:
    """Performance benchmarking suite."""

    def __init__(self):
        self._results: List[BenchmarkResult] = []

    def benchmark_function(
        self,
        func: Callable,
        name: str,
        iterations: int = 100,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """
        Benchmark a function.
        
        Args:
            func: Function to benchmark
            name: Test name
            iterations: Number of iterations
            *args, **kwargs: Function arguments
        
        Returns:
            BenchmarkResult with statistics
        """
        times = []
        errors = 0
        
        for i in range(iterations):
            start = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(func):
                    asyncio.run(func(*args, **kwargs))
                else:
                    func(*args, **kwargs)
            except Exception as e:
                errors += 1
                logger.error(f"Benchmark error: {e}")
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms
        
        # Calculate statistics
        sorted_times = sorted(times)
        total_time = sum(times) / 1000  # Convert to seconds
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        p50 = sorted_times[int(len(sorted_times) * 0.50)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) >= 20 else max_time
        p99 = sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) >= 100 else max_time
        rps = iterations / total_time if total_time > 0 else 0
        
        result = BenchmarkResult(
            test_name=name,
            iterations=iterations,
            total_time_seconds=total_time,
            avg_time_ms=avg_time,
            min_time_ms=min_time,
            max_time_ms=max_time,
            p50_time_ms=p50,
            p95_time_ms=p95,
            p99_time_ms=p99,
            requests_per_second=rps,
            errors=errors,
        )
        
        self._results.append(result)
        logger.info(f"Benchmark {name}: {avg_time:.2f}ms avg, {rps:.2f} req/s")
        
        return result

    async def load_test(
        self,
        func: Callable,
        concurrent_users: int = 10,
        total_requests: int = 1000,
        *args,
        **kwargs
    ) -> LoadTestResult:
        """
        Run load test with concurrent users.
        
        Args:
            func: Function to test
            concurrent_users: Number of concurrent users
            total_requests: Total requests to make
            *args, **kwargs: Function arguments
        
        Returns:
            LoadTestResult with statistics
        """
        successful = 0
        failed = 0
        times = []
        
        async def make_request():
            nonlocal successful, failed
            start = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
                successful += 1
            except Exception as e:
                failed += 1
                logger.error(f"Load test error: {e}")
            end = time.perf_counter()
            times.append((end - start) * 1000)
        
        # Run concurrent requests
        semaphore = asyncio.Semaphore(concurrent_users)
        
        async def limited_request():
            async with semaphore:
                await make_request()
        
        tasks = [limited_request() for _ in range(total_requests)]
        start_time = time.perf_counter()
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time
        
        # Calculate statistics
        sorted_times = sorted(times)
        avg_time = statistics.mean(times) if times else 0
        p95 = sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) >= 20 else max(times) if times else 0
        error_rate = failed / total_requests if total_requests > 0 else 0
        rps = total_requests / total_time if total_time > 0 else 0
        
        return LoadTestResult(
            concurrent_users=concurrent_users,
            total_requests=total_requests,
            successful_requests=successful,
            failed_requests=failed,
            avg_response_time_ms=avg_time,
            p95_response_time_ms=p95,
            error_rate=error_rate,
            requests_per_second=rps,
        )

    def get_all_results(self) -> List[BenchmarkResult]:
        """Get all benchmark results."""
        return self._results

    def get_summary(self) -> Dict[str, Any]:
        """Get benchmark summary."""
        if not self._results:
            return {"tests_run": 0}
        
        return {
            "tests_run": len(self._results),
            "total_iterations": sum(r.iterations for r in self._results),
            "total_errors": sum(r.errors for r in self._results),
            "overall_avg_ms": statistics.mean(r.avg_time_ms for r in self._results),
            "overall_p95_ms": statistics.mean(r.p95_time_ms for r in self._results),
            "overall_rps": sum(r.requests_per_second for r in self._results) / len(self._results),
        }

    def print_report(self):
        """Print benchmark report."""
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARK REPORT")
        print("="*80)
        
        for result in self._results:
            print(f"\n{result.test_name}:")
            print(f"  Iterations: {result.iterations}")
            print(f"  Avg Time: {result.avg_time_ms:.2f}ms")
            print(f"  Min Time: {result.min_time_ms:.2f}ms")
            print(f"  Max Time: {result.max_time_ms:.2f}ms")
            print(f"  P50 Time: {result.p50_time_ms:.2f}ms")
            print(f"  P95 Time: {result.p95_time_ms:.2f}ms")
            print(f"  P99 Time: {result.p99_time_ms:.2f}ms")
            print(f"  Requests/sec: {result.requests_per_second:.2f}")
            print(f"  Errors: {result.errors}")
        
        print("\n" + "="*80)
        summary = self.get_summary()
        print(f"Tests Run: {summary['tests_run']}")
        print(f"Total Iterations: {summary['total_iterations']}")
        print(f"Overall Avg: {summary['overall_avg_ms']:.2f}ms")
        print(f"Overall P95: {summary['overall_p95_ms']:.2f}ms")
        print(f"Overall RPS: {summary['overall_rps']:.2f}")
        print("="*80 + "\n")


# =============================================================================
# BENCHMARK TESTS
# =============================================================================

def run_core_benchmarks():
    """Run core performance benchmarks."""
    benchmark = PerformanceBenchmark()
    
    # Benchmark 1: Vector Store Operations
    print("\n🔍 Running Vector Store Benchmarks...")
    try:
        from copilot_core.rag.vector_store import VectorStore
        import numpy as np
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        store = VectorStore(data_dir=temp_dir, dimension=384)
        
        # Add vectors benchmark
        def add_vectors():
            for i in range(100):
                vector = np.random.rand(384).astype(np.float32)
                store.add_vector(f"vec_{i}", vector, {"index": i})
        
        benchmark.benchmark_function(add_vectors, "Vector Store: Add 100 vectors", iterations=10)
        
        # Similarity search benchmark
        query_vector = np.random.rand(384).astype(np.float32)
        
        def similarity_search():
            store.similarity_search(query_vector, k=10)
        
        benchmark.benchmark_function(similarity_search, "Vector Store: Similarity Search (k=10)", iterations=100)
        
    except Exception as e:
        logger.error(f"Vector Store benchmark failed: {e}")
    
    # Benchmark 2: Presence Detection
    print("\n🔍 Running Presence Detection Benchmarks...")
    try:
        from copilot_core.presence.api import PresenceAPI
        
        api = PresenceAPI()
        
        def update_presence():
            api.update_sensor("pir", "pir_1", 0.9)
        
        benchmark.benchmark_function(update_presence, "Presence: Sensor Update", iterations=1000)
        
        def get_presence_state():
            api.get_current_state()
        
        benchmark.benchmark_function(get_presence_state, "Presence: Get State", iterations=1000)
        
    except Exception as e:
        logger.error(f"Presence benchmark failed: {e}")
    
    # Benchmark 3: Knowledge Graph
    print("\n🔍 Running Knowledge Graph Benchmarks...")
    try:
        from copilot_core.brain.graph_store import BrainGraphStore
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        graph = BrainGraphStore(storage_path=temp_dir)
        
        def add_entities():
            for i in range(50):
                graph.add_entity(f"entity_{i}", {"type": "test", "index": i})
        
        benchmark.benchmark_function(add_entities, "Graph: Add 50 entities", iterations=10)
        
        def query_entities():
            graph.query_by_type("test")
        
        benchmark.benchmark_function(query_entities, "Graph: Query by type", iterations=100)
        
    except Exception as e:
        logger.error(f"Graph benchmark failed: {e}")
    
    # Benchmark 4: Security Operations
    print("\n🔍 Running Security Benchmarks...")
    try:
        from copilot_core.security.hardening import SecureTokenGenerator, PasswordHasher
        
        token_gen = SecureTokenGenerator()
        
        def generate_token():
            token_gen.generate()
        
        benchmark.benchmark_function(generate_token, "Security: Token Generation", iterations=1000)
        
        hasher = PasswordHasher(iterations=1000)  # Low for benchmark
        
        def hash_password():
            hasher.hash("test_password")
        
        benchmark.benchmark_function(hash_password, "Security: Password Hashing", iterations=100)
        
    except Exception as e:
        logger.error(f"Security benchmark failed: {e}")
    
    # Print report
    benchmark.print_report()
    
    return benchmark.get_summary()


if __name__ == "__main__":
    run_core_benchmarks()
