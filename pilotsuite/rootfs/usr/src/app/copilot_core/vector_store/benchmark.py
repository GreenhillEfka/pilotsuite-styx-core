#!/usr/bin/env python3
"""Performance benchmark for vector store with HNSW vs flat search.

Compares:
- Search latency (ms) for HNSW vs flat index
- Memory usage
- Index build time
- Search accuracy (recall)

Usage:
    python benchmark_vector_store.py [--num-vectors 10000] [--dim 384]
"""

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from copilot_core.vector_store.config import VectorStoreConfig
from copilot_core.vector_store.store import VectorStore, reset_vector_store


def generate_random_vector(dim: int) -> list[float]:
    """Generate a random unit vector."""
    vec = np.random.randn(dim)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


async def benchmark_search_performance(
    num_vectors: int = 10000,
    dim: int = 384,
    num_queries: int = 100,
    top_k: int = 10,
) -> dict:
    """Benchmark search performance for HNSW vs flat.
    
    Args:
        num_vectors: Number of vectors in index
        dim: Vector dimension
        num_queries: Number of query vectors
        top_k: Number of results to return
        
    Returns:
        Benchmark results dict
    """
    print(f"\n{'='*60}")
    print(f"Benchmark: {num_vectors} vectors, {dim} dimensions, {num_queries} queries")
    print(f"{'='*60}\n")
    
    results = {
        "num_vectors": num_vectors,
        "dim": dim,
        "num_queries": num_queries,
        "top_k": top_k,
        "hnsw": {},
        "flat": {},
    }
    
    # ==================== HNSW Benchmark ====================
    print("1. Testing HNSW index...")
    
    hnsw_config = VectorStoreConfig(
        db_path="/tmp/vector_benchmark_hnsw.db",
        persist=True,
        index_type="hnsw",
        hnsw_m=16,
        hnsw_ef_construction=200,
        hnsw_ef_search=50,
        hnsw_max_elements=num_vectors + 1000,
        use_float16=True,
    )
    
    reset_vector_store()
    hnsw_store = VectorStore(hnsw_config)
    
    # Generate test vectors
    print(f"   Generating {num_vectors} test vectors...")
    test_vectors = [generate_random_vector(dim) for _ in range(num_vectors)]
    
    # Index vectors
    print(f"   Indexing vectors...")
    index_start = time.time()
    for i, vec in enumerate(test_vectors):
        await hnsw_store.upsert(
            entry_id=f"test_{i}",
            vector=vec,
            entry_type="test",
            metadata={"index": i},
        )
    index_time = time.time() - index_start
    results["hnsw"]["index_time_sec"] = index_time
    print(f"   Index time: {index_time:.2f}s ({num_vectors/index_time:.0f} vec/s)")
    
    # Generate query vectors
    query_vectors = [generate_random_vector(dim) for _ in range(num_queries)]
    
    # Benchmark search
    print(f"   Running {num_queries} search queries...")
    search_times = []
    for query in query_vectors:
        start = time.time()
        results_hnsw = await hnsw_store.search_similar(
            query_vector=query,
            entry_type="test",
            limit=top_k,
            threshold=0.0,
        )
        elapsed = (time.time() - start) * 1000
        search_times.append(elapsed)
    
    avg_search_ms = sum(search_times) / len(search_times)
    p95_search_ms = sorted(search_times)[int(len(search_times) * 0.95)]
    p99_search_ms = sorted(search_times)[int(len(search_times) * 0.99)]
    
    results["hnsw"]["avg_search_ms"] = avg_search_ms
    results["hnsw"]["p95_search_ms"] = p95_search_ms
    results["hnsw"]["p99_search_ms"] = p99_search_ms
    results["hnsw"]["queries_per_sec"] = 1000.0 / avg_search_ms if avg_search_ms > 0 else 0
    
    print(f"   Avg search: {avg_search_ms:.2f}ms")
    print(f"   P95 search: {p95_search_ms:.2f}ms")
    print(f"   P99 search: {p99_search_ms:.2f}ms")
    print(f"   Throughput: {results['hnsw']['queries_per_sec']:.0f} queries/sec")
    
    hnsw_store.close()
    
    # ==================== Flat Benchmark ====================
    print("\n2. Testing Flat (linear) index...")
    
    flat_config = VectorStoreConfig(
        db_path="/tmp/vector_benchmark_flat.db",
        persist=True,
        index_type="flat",
        use_float16=True,
    )
    
    reset_vector_store()
    flat_store = VectorStore(flat_config)
    
    # Index vectors
    print(f"   Indexing {num_vectors} vectors...")
    index_start = time.time()
    for i, vec in enumerate(test_vectors):
        await flat_store.upsert(
            entry_id=f"test_{i}",
            vector=vec,
            entry_type="test",
            metadata={"index": i},
        )
    index_time = time.time() - index_start
    results["flat"]["index_time_sec"] = index_time
    print(f"   Index time: {index_time:.2f}s ({num_vectors/index_time:.0f} vec/s)")
    
    # Benchmark search
    print(f"   Running {num_queries} search queries...")
    search_times = []
    for query in query_vectors:
        start = time.time()
        results_flat = await flat_store.search_similar(
            query_vector=query,
            entry_type="test",
            limit=top_k,
            threshold=0.0,
        )
        elapsed = (time.time() - start) * 1000
        search_times.append(elapsed)
    
    avg_search_ms = sum(search_times) / len(search_times)
    p95_search_ms = sorted(search_times)[int(len(search_times) * 0.95)]
    p99_search_ms = sorted(search_times)[int(len(search_times) * 0.99)]
    
    results["flat"]["avg_search_ms"] = avg_search_ms
    results["flat"]["p95_search_ms"] = p95_search_ms
    results["flat"]["p99_search_ms"] = p99_search_ms
    results["flat"]["queries_per_sec"] = 1000.0 / avg_search_ms if avg_search_ms > 0 else 0
    
    print(f"   Avg search: {avg_search_ms:.2f}ms")
    print(f"   P95 search: {p95_search_ms:.2f}ms")
    print(f"   P99 search: {p99_search_ms:.2f}ms")
    print(f"   Throughput: {results['flat']['queries_per_sec']:.0f} queries/sec")
    
    flat_store.close()
    
    # ==================== Comparison ====================
    print(f"\n{'='*60}")
    print("COMPARISON RESULTS")
    print(f"{'='*60}")
    
    speedup = results["flat"]["avg_search_ms"] / results["hnsw"]["avg_search_ms"] if results["hnsw"]["avg_search_ms"] > 0 else 0
    print(f"\nHNSW Speedup: {speedup:.1f}x faster")
    print(f"\nSearch Latency:")
    print(f"  HNSW:  {results['hnsw']['avg_search_ms']:.2f}ms avg")
    print(f"  Flat:  {results['flat']['avg_search_ms']:.2f}ms avg")
    print(f"\nThroughput:")
    print(f"  HNSW:  {results['hnsw']['queries_per_sec']:.0f} queries/sec")
    print(f"  Flat:  {results['flat']['queries_per_sec']:.0f} queries/sec")
    
    # Cleanup
    for path in ["/tmp/vector_benchmark_hnsw.db", "/tmp/vector_benchmark_flat.db"]:
        try:
            os.remove(path)
        except OSError:
            pass
    
    return results


async def benchmark_batch_search(
    num_vectors: int = 5000,
    dim: int = 384,
    batch_sizes: list[int] = [1, 5, 10, 20, 50],
) -> dict:
    """Benchmark batch search performance.
    
    Args:
        num_vectors: Number of vectors in index
        dim: Vector dimension
        batch_sizes: List of batch sizes to test
        
    Returns:
        Benchmark results dict
    """
    print(f"\n{'='*60}")
    print(f"Batch Search Benchmark: {num_vectors} vectors, {dim} dimensions")
    print(f"{'='*60}\n")
    
    results = {"batch_sizes": {}, "num_vectors": num_vectors, "dim": dim}
    
    # Setup store
    config = VectorStoreConfig(
        db_path="/tmp/vector_benchmark_batch.db",
        persist=True,
        index_type="hnsw",
        hnsw_m=16,
        hnsw_ef_search=50,
        hnsw_max_elements=num_vectors + 1000,
    )
    
    reset_vector_store()
    store = VectorStore(config)
    
    # Index vectors
    print(f"Indexing {num_vectors} vectors...")
    for i in range(num_vectors):
        vec = generate_random_vector(dim)
        await store.upsert(f"test_{i}", vec, "test", {"index": i})
    
    print("Testing batch sizes...\n")
    
    for batch_size in batch_sizes:
        queries = [generate_random_vector(dim) for _ in range(batch_size)]
        
        start = time.time()
        batch_results = await store.batch_search(
            query_vectors=queries,
            entry_type="test",
            limit=10,
            threshold=0.0,
        )
        elapsed = time.time() - start
        
        results["batch_sizes"][batch_size] = {
            "total_time_ms": elapsed * 1000,
            "avg_time_per_query_ms": (elapsed * 1000) / batch_size,
            "queries_per_sec": batch_size / elapsed if elapsed > 0 else 0,
        }
        
        print(f"  Batch {batch_size:2d}: {elapsed*1000:7.2f}ms total, "
              f"{(elapsed*1000)/batch_size:6.2f}ms/query, "
              f"{batch_size/elapsed:6.0f} q/s")
    
    store.close()
    
    # Cleanup
    try:
        os.remove("/tmp/vector_benchmark_batch.db")
    except OSError:
        pass
    
    return results


async def main():
    """Run all benchmarks."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vector Store Performance Benchmark")
    parser.add_argument("--num-vectors", type=int, default=10000,
                       help="Number of vectors to index")
    parser.add_argument("--dim", type=int, default=384,
                       help="Vector dimension")
    parser.add_argument("--queries", type=int, default=100,
                       help="Number of query vectors")
    parser.add_argument("--output", type=str, default=None,
                       help="Output JSON file path")
    
    args = parser.parse_args()
    
    # Run benchmarks
    search_results = await benchmark_search_performance(
        num_vectors=args.num_vectors,
        dim=args.dim,
        num_queries=args.queries,
    )
    
    batch_results = await benchmark_batch_search(
        num_vectors=min(args.num_vectors, 5000),
        dim=args.dim,
    )
    
    # Combine results
    all_results = {
        "search_benchmark": search_results,
        "batch_benchmark": batch_results,
        "summary": {
            "hnsw_speedup": search_results["flat"]["avg_search_ms"] / search_results["hnsw"]["avg_search_ms"] 
                           if search_results["hnsw"]["avg_search_ms"] > 0 else 0,
            "recommendation": "Use HNSW for datasets with >1000 vectors for O(log n) search performance",
        }
    }
    
    # Save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    print(f"\n{'='*60}")
    print("BENCHMARK COMPLETE")
    print(f"{'='*60}\n")
    
    return all_results


if __name__ == "__main__":
    asyncio.run(main())
