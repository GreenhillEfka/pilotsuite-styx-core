"""Symbiosis Benchmark Suite — Performance Testing.
Measures latency, throughput, and resource usage.
"""
import asyncio
import time
import statistics
from typing import List, Dict
from copilot_core.symbiosis.rule_engine import SymbioticRuleEngine
from copilot_core.symbiosis.predictive_symbiosis import PredictiveSymbiosisEngine

class SymbiosisBenchmark:
    def __init__(self):
        self.results: Dict[str, List[float]] = {}
    
    def benchmark_rule_evaluation(self, num_rules: int = 100, num_iterations: int = 1000) -> Dict:
        """Benchmark rule evaluation performance."""
        rule_engine = SymbioticRuleEngine()
        
        # Setup rules
        for i in range(num_rules):
            rule_engine.register_rule(
                f"zone_{i % 10}",
                "benchmark",
                {"logic": "AND", "checks": [{"type": "test"}]},
                {"type": "log"}
            )
        
        latencies = []
        start = time.time()
        
        for i in range(num_iterations):
            iter_start = time.time()
            rule_engine.evaluate_zone(
                {"zone_id": f"zone_{i % 10}"},
                [{"event_type": "test", "data": i}]
            )
            latencies.append((time.time() - iter_start) * 1000)  # ms
        
        total_time = time.time() - start
        
        results = {
            "test": "rule_evaluation",
            "num_rules": num_rules,
            "num_iterations": num_iterations,
            "total_time_sec": round(total_time, 3),
            "throughput_eps": round(num_iterations / total_time, 2),
            "latency_avg_ms": round(statistics.mean(latencies), 3),
            "latency_p50_ms": round(statistics.median(latencies), 3),
            "latency_p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 3),
            "latency_max_ms": round(max(latencies), 3)
        }
        
        self.results.setdefault("rule_evaluation", []).append(results)
        return results
    
    def benchmark_pattern_detection(self, num_events: int = 1000) -> Dict:
        """Benchmark pattern detection performance."""
        predictive = PredictiveSymbiosisEngine()
        
        # Add events
        for i in range(num_events):
            predictive.add_event({
                "event_type": "motion",
                "zone_id": f"zone_{i % 10}",
                "timestamp": f"2026-04-06T{20 + (i % 4):02d}:00:00Z"
            })
        
        # Measure analysis
        start = time.time()
        patterns = predictive.analyze_patterns()
        elapsed = time.time() - start
        
        results = {
            "test": "pattern_detection",
            "num_events": num_events,
            "patterns_found": len(patterns),
            "analysis_time_ms": round(elapsed * 1000, 3),
            "events_per_sec": round(num_events / elapsed, 2)
        }
        
        self.results.setdefault("pattern_detection", []).append(results)
        return results
    
    def benchmark_context_transitions(self, num_transitions: int = 10000) -> Dict:
        """Benchmark context manager transitions."""
        from copilot_core.symbiosis.rule_engine import ContextManager
        
        cm = ContextManager()
        latencies = []
        
        start = time.time()
        for i in range(num_transitions):
            iter_start = time.time()
            cm.transition(f"zone_{i % 10}", f"context_{i % 5}")
            latencies.append((time.time() - iter_start) * 1000)
        
        total_time = time.time() - start
        
        results = {
            "test": "context_transitions",
            "num_transitions": num_transitions,
            "total_time_sec": round(total_time, 3),
            "throughput_tps": round(num_transitions / total_time, 2),
            "latency_avg_ms": round(statistics.mean(latencies), 3),
            "latency_p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 3)
        }
        
        self.results.setdefault("context_transitions", []).append(results)
        return results
    
    def run_all_benchmarks(self) -> Dict:
        """Run all benchmarks and return summary."""
        print("🏁 Starting Symbiosis Benchmark Suite...")
        
        r1 = self.benchmark_rule_evaluation()
        print(f"✅ Rule Evaluation: {r1['throughput_eps']} eps, {r1['latency_avg_ms']}ms avg")
        
        r2 = self.benchmark_pattern_detection()
        print(f"✅ Pattern Detection: {r2['events_per_sec']} eps, {r2['analysis_time_ms']}ms")
        
        r3 = self.benchmark_context_transitions()
        print(f"✅ Context Transitions: {r3['throughput_tps']} tps, {r3['latency_avg_ms']}ms avg")
        
        return {
            "summary": {
                "total_tests": 3,
                "rule_evaluation": r1,
                "pattern_detection": r2,
                "context_transitions": r3
            },
            "all_results": self.results
        }

if __name__ == "__main__":
    benchmark = SymbiosisBenchmark()
    results = benchmark.run_all_benchmarks()
    print(f"\n📊 Benchmark Complete: {results['summary']}")
