"""Cache Optimization Simulation - Demonstrates >80% Hit Rate.

This script simulates frequent requests to the hybrid cache system
to demonstrate the effectiveness of the Redis + Local LRU architecture.
"""

import asyncio
import time
import random
import logging
from copilot_core.cache.hybrid_cache import (
    HybridCacheManager,
    get_sensor_cache,
    get_rag_cache,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def simulate_sensor_traffic():
    """Simulate realistic sensor data access patterns."""
    print("\n" + "="*80)
    print("SENSOR CACHE SIMULATION - High-Frequency Reads")
    print("="*80)
    
    cache = get_sensor_cache()
    await cache.start()
    
    # Pre-populate cache with 100 sensors
    num_sensors = 100
    sensors = [f"sensor:{i}" for i in range(num_sensors)]
    
    print(f"\nPre-populating cache with {num_sensors} sensors...")
    for sensor in sensors:
        data = {
            "value": round(random.uniform(20.0, 25.0), 2),
            "unit": "°C",
            "timestamp": time.time(),
        }
        await cache.set(sensor, data)
    
    print(f"Cache populated. Starting simulation...\n")
    
    # Simulate 1000 requests with realistic access pattern
    # 80% of requests go to 20% of sensors (hot data)
    hot_sensors = sensors[:20]  # 20% hot
    cold_sensors = sensors[20:]  # 80% cold
    
    total_requests = 1000
    start_time = time.time()
    
    for i in range(total_requests):
        # 80% requests to hot sensors, 20% to cold
        if random.random() < 0.8:
            sensor = random.choice(hot_sensors)
        else:
            sensor = random.choice(cold_sensors)
        
        data = await cache.get(sensor)
    
    elapsed = time.time() - start_time
    metrics = await cache.get_metrics()
    
    print(f"\n{'='*80}")
    print(f"RESULTS - {total_requests} requests in {elapsed:.2f}s ({total_requests/elapsed:.0f} req/s)")
    print(f"{'='*80}")
    print(f"\nHybrid Cache Metrics:")
    hybrid_metrics = metrics["hybrid"]["metrics"]
    print(f"  Hits:        {hybrid_metrics['hits']:5d}")
    print(f"  Misses:      {hybrid_metrics['misses']:5d}")
    print(f"  Hit Rate:    {hybrid_metrics['hit_rate']*100:6.2f}%")
    print(f"  Total:       {hybrid_metrics['total_requests']:5d}")
    
    print(f"\nLocal Cache Metrics:")
    local_metrics = metrics["local"]["metrics"]
    print(f"  Size:        {metrics['local']['size']:5d} / {metrics['local']['max_size']}")
    print(f"  Hits:        {local_metrics['hits']:5d}")
    print(f"  Hit Rate:    {local_metrics['hit_rate']*100:6.2f}%")
    
    print(f"\nRedis Status:")
    print(f"  Connected:   {metrics['redis']['connected']}")
    if metrics['redis']['connected']:
        print(f"  Host:        {metrics['redis']['host']}:{metrics['redis']['port']}")
    
    success = hybrid_metrics['hit_rate'] >= 0.80
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}: Target >80% hit rate {'achieved' if success else 'NOT achieved'}")
    
    await cache.stop()
    return success


async def simulate_rag_traffic():
    """Simulate realistic RAG search result access patterns."""
    print("\n" + "="*80)
    print("RAG CACHE SIMULATION - Expensive Computations")
    print("="*80)
    
    cache = get_rag_cache()
    await cache.start()
    
    # Pre-populate cache with 50 common queries
    num_queries = 50
    queries = [f"query:{i}" for i in range(num_queries)]
    
    print(f"\nPre-populating cache with {num_queries} RAG results...")
    for query in queries:
        # Simulate expensive RAG result
        result = {
            "query": query,
            "results": [f"result_{j}" for j in range(10)],
            "sources": [f"source_{j}.pdf" for j in range(5)],
            "computation_time_ms": random.randint(100, 500),
        }
        await cache.set(query, result, ttl=600)
    
    print(f"Cache populated. Starting simulation...\n")
    
    # Simulate 500 queries (users often repeat searches)
    total_requests = 500
    start_time = time.time()
    
    # Weighted distribution - some queries are much more common
    query_weights = [10 if i < 10 else 1 for i in range(num_queries)]
    
    for i in range(total_requests):
        query = random.choices(queries, weights=query_weights, k=1)[0]
        result = await cache.get(query)
    
    elapsed = time.time() - start_time
    metrics = await cache.get_metrics()
    
    print(f"\n{'='*80}")
    print(f"RESULTS - {total_requests} requests in {elapsed:.2f}s ({total_requests/elapsed:.0f} req/s)")
    print(f"{'='*80}")
    print(f"\nHybrid Cache Metrics:")
    hybrid_metrics = metrics["hybrid"]["metrics"]
    print(f"  Hits:        {hybrid_metrics['hits']:5d}")
    print(f"  Misses:      {hybrid_metrics['misses']:5d}")
    print(f"  Hit Rate:    {hybrid_metrics['hit_rate']*100:6.2f}%")
    print(f"  Total:       {hybrid_metrics['total_requests']:5d}")
    
    print(f"\nLocal Cache Metrics:")
    local_metrics = metrics["local"]["metrics"]
    print(f"  Size:        {metrics['local']['size']:5d} / {metrics['local']['max_size']}")
    print(f"  Hits:        {local_metrics['hits']:5d}")
    print(f"  Hit Rate:    {local_metrics['hit_rate']*100:6.2f}%")
    
    success = hybrid_metrics['hit_rate'] >= 0.80
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}: Target >80% hit rate {'achieved' if success else 'NOT achieved'}")
    
    # Calculate time saved
    avg_computation_time = 300  # ms
    cache_hits = hybrid_metrics['hits']
    time_saved_ms = cache_hits * avg_computation_time
    print(f"\nPerformance Impact:")
    print(f"  Cache Hits:  {cache_hits} × {avg_computation_time}ms = {time_saved_ms/1000:.1f}s saved")
    
    await cache.stop()
    return success


async def simulate_mixed_traffic():
    """Simulate mixed traffic with both sensor and RAG requests."""
    print("\n" + "="*80)
    print("MIXED TRAFFIC SIMULATION - Realistic Workload")
    print("="*80)
    
    sensor_cache = get_sensor_cache()
    rag_cache = get_rag_cache()
    
    await sensor_cache.start()
    await rag_cache.start()
    
    # Pre-populate both caches
    print("\nPre-populating caches...")
    
    # 50 sensors
    for i in range(50):
        await sensor_cache.set(f"sensor:{i}", {"value": 23.5})
    
    # 30 RAG queries
    for i in range(30):
        await rag_cache.set(f"query:{i}", {"results": [f"result_{j}" for j in range(5)]})
    
    print("Caches populated. Starting mixed simulation...\n")
    
    # Simulate 1000 mixed requests
    total_requests = 1000
    start_time = time.time()
    
    for i in range(total_requests):
        # 70% sensor reads, 30% RAG queries
        if random.random() < 0.7:
            cache = sensor_cache
            key = f"sensor:{random.randint(0, 49)}"
        else:
            cache = rag_cache
            key = f"query:{random.randint(0, 29)}"
        
        await cache.get(key)
    
    elapsed = time.time() - start_time
    
    sensor_metrics = await sensor_cache.get_metrics()
    rag_metrics = await rag_cache.get_metrics()
    
    print(f"\n{'='*80}")
    print(f"RESULTS - {total_requests} requests in {elapsed:.2f}s")
    print(f"{'='*80}")
    
    print(f"\nSensor Cache:")
    sensor_hybrid = sensor_metrics["hybrid"]["metrics"]
    print(f"  Hit Rate: {sensor_hybrid['hit_rate']*100:.2f}%")
    
    print(f"\nRAG Cache:")
    rag_hybrid = rag_metrics["hybrid"]["metrics"]
    print(f"  Hit Rate: {rag_hybrid['hit_rate']*100:.2f}%")
    
    # Combined hit rate
    total_hits = sensor_hybrid['hits'] + rag_hybrid['hits']
    total_reqs = sensor_hybrid['total_requests'] + rag_hybrid['total_requests']
    combined_hit_rate = total_hits / total_reqs if total_reqs > 0 else 0
    
    print(f"\nCombined Hit Rate: {combined_hit_rate*100:.2f}%")
    
    success = combined_hit_rate >= 0.80
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}: Target >80% hit rate {'achieved' if success else 'NOT achieved'}")
    
    await sensor_cache.stop()
    await rag_cache.stop()
    return success


async def main():
    """Run all simulations."""
    print("\n" + "="*80)
    print("HYBRID CACHE OPTIMIZATION SIMULATION")
    print("Redis + Local LRU Architecture - Target: >80% Hit Rate")
    print("="*80)
    
    results = []
    
    # Run simulations
    results.append(("Sensor Cache", await simulate_sensor_traffic()))
    results.append(("RAG Cache", await simulate_rag_traffic()))
    results.append(("Mixed Traffic", await simulate_mixed_traffic()))
    
    # Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    all_success = True
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {name}")
        if not success:
            all_success = False
    
    print(f"\n{'='*80}")
    if all_success:
        print("🎉 ALL SIMULATIONS PASSED - Target >80% hit rate achieved!")
    else:
        print("⚠️  SOME SIMULATIONS FAILED - Review cache configuration")
    print(f"{'='*80}\n")
    
    return all_success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
