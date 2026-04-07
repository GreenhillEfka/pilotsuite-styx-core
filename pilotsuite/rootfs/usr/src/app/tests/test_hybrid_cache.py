"""Hybrid Cache Manager Tests - Redis + Local LRU.

Tests for HybridCacheManager with two-tier caching:
- Local LRU cache (ultra-fast)
- Redis cache (shared, persistent)
- Target: >80% cache hit rate
"""

import pytest
import asyncio
import time
import logging

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

from copilot_core.cache.hybrid_cache import (
    HybridCacheManager,
    CacheMetrics,
    get_sensor_cache,
    get_habitus_cache,
    get_rag_cache,
    init_all_caches,
    shutdown_all_caches,
)


class TestHybridCacheManager:
    """Tests for HybridCacheManager class."""
    
    @pytest.fixture
    def hybrid_cache(self):
        """Create hybrid cache instance with Redis disabled for unit tests."""
        cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,
            local_cache_size=500,
            redis_enabled=False,  # Disable Redis for unit tests
            write_through=True,
        )
        return cache
    
    @pytest.fixture
    async def started_cache(self, hybrid_cache):
        """Create and start hybrid cache instance."""
        await hybrid_cache.start()
        yield hybrid_cache
        await hybrid_cache.stop()
    
    @pytest.mark.asyncio
    async def test_init_local_only(self, hybrid_cache):
        """Test hybrid cache initialization with local cache only."""
        assert hybrid_cache._config.local_cache_size == 500
        assert hybrid_cache._config.default_ttl == 300
        assert hybrid_cache._config.redis_enabled is False
        assert len(hybrid_cache._local_cache) == 0
    
    @pytest.mark.asyncio
    async def test_set_get_local(self, started_cache):
        """Test set and get operations with local cache."""
        cache = started_cache
        
        # Set a value
        key = "test_key"
        value = {"data": "test_value", "count": 42}
        await cache.set(key, value)
        
        # Get the value
        retrieved = await cache.get(key)
        assert retrieved == value
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, hybrid_cache):
        """Test cache expiration."""
        await hybrid_cache.start()
        
        key = "expire_test"
        value = {"test": "data"}
        
        await hybrid_cache.set(key, value, ttl=1)
        retrieved = await hybrid_cache.get(key)
        assert retrieved == value
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # Should be expired
        retrieved = await hybrid_cache.get(key)
        assert retrieved is None
        
        await hybrid_cache.stop()
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self, hybrid_cache):
        """Test LRU eviction when local cache exceeds max_size."""
        # Create cache with small size
        small_cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,
            local_cache_size=5,
            redis_enabled=False,
        )
        await small_cache.start()
        
        # Add 7 items (should evict 2)
        for i in range(7):
            await small_cache.set(f"key_{i}", f"value_{i}")
        
        # First 2 keys should be evicted
        assert await small_cache.get("key_0") is None
        assert await small_cache.get("key_1") is None
        
        # Last 5 keys should exist
        assert await small_cache.get("key_2") == "value_2"
        assert await small_cache.get("key_3") == "value_3"
        assert await small_cache.get("key_4") == "value_4"
        assert await small_cache.get("key_5") == "value_5"
        assert await small_cache.get("key_6") == "value_6"
        
        await small_cache.stop()
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, started_cache):
        """Test cache deletion."""
        cache = started_cache
        
        key = "delete_test"
        value = {"test": "data"}
        
        await cache.set(key, value)
        assert await cache.get(key) == value
        
        await cache.delete(key)
        assert await cache.get(key) is None
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, started_cache):
        """Test clearing all cache entries."""
        cache = started_cache
        
        # Add multiple entries
        for i in range(10):
            await cache.set(f"key_{i}", f"value_{i}")
        
        # Clear all
        await cache.clear()
        
        # All should be gone
        for i in range(10):
            assert await cache.get(f"key_{i}") is None
    
    @pytest.mark.asyncio
    async def test_exists(self, started_cache):
        """Test key existence check."""
        cache = started_cache
        
        key = "exists_test"
        value = {"test": "data"}
        
        # Should not exist initially
        assert await cache.exists(key) is False
        
        # Set and check
        await cache.set(key, value)
        assert await cache.exists(key) is True
        
        # Delete and check
        await cache.delete(key)
        assert await cache.exists(key) is False
    
    @pytest.mark.asyncio
    async def test_get_or_set(self, started_cache):
        """Test get_or_set with factory function."""
        cache = started_cache
        call_count = 0
        
        def factory():
            nonlocal call_count
            call_count += 1
            return {"computed": True, "count": call_count}
        
        # First call - should compute
        result1 = await cache.get_or_set("compute_key", factory, ttl=300)
        assert result1["computed"] is True
        assert result1["count"] == 1
        assert call_count == 1
        
        # Second call - should use cache
        result2 = await cache.get_or_set("compute_key", factory, ttl=300)
        assert result2["computed"] is True
        assert result2["count"] == 1  # Still 1, cached
        assert call_count == 1  # Factory not called again
    
    @pytest.mark.asyncio
    async def test_get_or_set_async(self, started_cache):
        """Test get_or_set with async factory function."""
        cache = started_cache
        call_count = 0
        
        async def async_factory():
            nonlocal call_count
            await asyncio.sleep(0.01)  # Simulate async work
            call_count += 1
            return {"async": True, "count": call_count}
        
        # First call - should compute
        result1 = await cache.get_or_set("async_key", async_factory, ttl=300)
        assert result1["async"] is True
        assert result1["count"] == 1
        assert call_count == 1
        
        # Second call - should use cache
        result2 = await cache.get_or_set("async_key", async_factory, ttl=300)
        assert result2["async"] is True
        assert result2["count"] == 1  # Still 1, cached
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, started_cache):
        """Test cache metrics tracking."""
        cache = started_cache
        
        # Perform some operations
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss (returns None/default)
        await cache.get("key3")  # Miss (returns None/default)
        
        metrics = await cache.get_metrics()
        
        assert "local" in metrics
        assert "redis" in metrics
        assert "hybrid" in metrics
        
        local_metrics = metrics["local"]["metrics"]
        # We should have at least 2 hits
        assert local_metrics["hits"] >= 2
        # Total requests should include hits and misses
        assert local_metrics["total_requests"] >= 2
        
        hybrid_metrics = metrics["hybrid"]["metrics"]
        assert hybrid_metrics["hits"] >= 2
        # Verify hit rate is calculated
        assert "hit_rate" in hybrid_metrics
    
    @pytest.mark.asyncio
    async def test_get_stats(self, started_cache):
        """Test cache statistics."""
        cache = started_cache
        
        # Add some data
        await cache.set("stats_test", {"data": "test"})
        
        stats = await cache.get_stats()
        
        assert "local" in stats
        assert stats["local"]["size"] >= 1
        assert "hybrid" in stats
        assert stats["hybrid"]["enabled"] is True


class TestHybridCacheHitRate:
    """Tests for cache hit rate optimization."""
    
    @pytest.mark.asyncio
    async def test_high_hit_rate_simulation(self):
        """Simulate frequent requests to verify >80% hit rate."""
        cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,
            local_cache_size=500,
            redis_enabled=False,
        )
        await cache.start()
        
        # Pre-populate cache with sensor data (simulating warm cache)
        sensor_keys = [f"sensor:temp:{i}" for i in range(100)]
        for key in sensor_keys:
            await cache.set(key, {"value": 23.5, "unit": "°C"})
        
        # Simulate 1000 requests with Zipfian distribution (realistic access pattern)
        # 80% of requests go to 20% of keys (hot data)
        hot_keys = sensor_keys[:20]  # 20% hot keys
        cold_keys = sensor_keys[20:]  # 80% cold keys
        
        total_requests = 1000
        for i in range(total_requests):
            if i % 5 < 4:  # 80% requests to hot keys
                key = hot_keys[i % len(hot_keys)]
            else:  # 20% requests to cold keys
                key = cold_keys[i % len(cold_keys)]
            
            await cache.get(key)
        
        metrics = await cache.get_metrics()
        hybrid_metrics = metrics["hybrid"]["metrics"]
        
        hit_rate = hybrid_metrics["hit_rate"]
        _LOGGER.info(f"Hit rate: {hit_rate:.2%} (target: >80%)")
        
        # Verify hit rate meets target
        assert hit_rate >= 0.80, f"Hit rate {hit_rate:.2%} below target 80%"
        
        await cache.stop()
    
    @pytest.mark.asyncio
    async def test_rag_cache_hit_rate(self):
        """Test RAG cache with expensive computations."""
        cache = get_rag_cache()
        await cache.start()
        
        # Pre-populate RAG cache with search results
        queries = [f"query_{i}" for i in range(50)]
        for query in queries:
            result = {"results": [f"result_{j}" for j in range(10)], "query": query}
            await cache.set(f"rag:{query}", result, ttl=600)
        
        # Simulate repeated queries (users often repeat searches)
        total_requests = 500
        for i in range(total_requests):
            query = queries[i % len(queries)]
            await cache.get(f"rag:{query}")
        
        metrics = await cache.get_metrics()
        hit_rate = metrics["hybrid"]["metrics"]["hit_rate"]
        
        _LOGGER.info(f"RAG cache hit rate: {hit_rate:.2%}")
        assert hit_rate >= 0.80, f"RAG hit rate {hit_rate:.2%} below target"
        
        await cache.stop()
    
    @pytest.mark.asyncio
    async def test_sensor_cache_hit_rate(self):
        """Test sensor cache with high-frequency reads."""
        cache = get_sensor_cache()
        await cache.start()
        
        # Pre-populate sensor cache
        sensors = [f"sensor:{i}" for i in range(50)]
        for sensor in sensors:
            await cache.set(sensor, {"value": 23.5, "timestamp": time.time()})
        
        # Simulate high-frequency sensor reads (every 100ms)
        total_requests = 1000
        for i in range(total_requests):
            sensor = sensors[i % len(sensors)]
            await cache.get(sensor)
        
        metrics = await cache.get_metrics()
        hit_rate = metrics["hybrid"]["metrics"]["hit_rate"]
        
        _LOGGER.info(f"Sensor cache hit rate: {hit_rate:.2%}")
        assert hit_rate >= 0.80, f"Sensor hit rate {hit_rate:.2%} below target"
        
        await cache.stop()


class TestHybridCacheGlobalInstances:
    """Tests for global cache instances."""
    
    @pytest.mark.asyncio
    async def test_get_sensor_cache(self):
        """Test sensor cache singleton."""
        cache1 = get_sensor_cache()
        cache2 = get_sensor_cache()
        
        assert cache1 is cache2  # Same instance
        assert cache1._config.default_ttl == 300
        assert cache1._config.local_cache_size == 500
    
    @pytest.mark.asyncio
    async def test_get_habitus_cache(self):
        """Test habitus cache singleton."""
        cache1 = get_habitus_cache()
        cache2 = get_habitus_cache()
        
        assert cache1 is cache2  # Same instance
        assert cache1._config.default_ttl == 900
        assert cache1._config.local_cache_size == 200
    
    @pytest.mark.asyncio
    async def test_get_rag_cache(self):
        """Test RAG cache singleton."""
        cache1 = get_rag_cache()
        cache2 = get_rag_cache()
        
        assert cache1 is cache2  # Same instance
        assert cache1._config.default_ttl == 600
        assert cache1._config.local_cache_size == 1000
    
    @pytest.mark.asyncio
    async def test_init_all_caches(self):
        """Test initializing all caches."""
        await init_all_caches()
        
        # Verify all caches are started
        sensor = get_sensor_cache()
        habitus = get_habitus_cache()
        rag = get_rag_cache()
        
        assert sensor._running is True
        assert habitus._running is True
        assert rag._running is True
        
        await shutdown_all_caches()
        
        # Verify all caches are stopped
        assert sensor._running is False
        assert habitus._running is False
        assert rag._running is False


class TestHybridCacheWarmup:
    """Tests for cache warming functionality."""
    
    @pytest.mark.asyncio
    async def test_warm_cache(self):
        """Test cache warming with pre-computed values."""
        cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,
            local_cache_size=500,
            redis_enabled=False,
        )
        await cache.start()
        
        keys = [f"warm_key_{i}" for i in range(10)]
        
        async def loader(key):
            return {"warmed": True, "key": key}
        
        result = await cache.warm_cache(keys, loader)
        
        assert result["warmed"] == 10
        assert result["failed"] == 0
        
        # Verify all keys are cached
        for key in keys:
            value = await cache.get(key)
            assert value is not None
            assert value["warmed"] is True
        
        await cache.stop()
    
    @pytest.mark.asyncio
    async def test_warm_cache_with_failures(self):
        """Test cache warming with some failures."""
        cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,
            local_cache_size=500,
            redis_enabled=False,
        )
        await cache.start()
        
        keys = [f"warm_key_{i}" for i in range(10)]
        
        async def flaky_loader(key):
            if "5" in key:
                raise ValueError("Simulated failure")
            return {"warmed": True, "key": key}
        
        result = await cache.warm_cache(keys, flaky_loader)
        
        assert result["warmed"] == 9  # All except key_5
        assert result["failed"] == 1
        
        await cache.stop()


class TestHybridCacheConcurrency:
    """Tests for concurrent cache access."""
    
    @pytest.mark.asyncio
    async def test_concurrent_reads(self):
        """Test concurrent read operations."""
        cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,
            local_cache_size=1000,
            redis_enabled=False,
        )
        await cache.start()
        
        # Pre-populate
        for i in range(100):
            await cache.set(f"key_{i}", f"value_{i}")
        
        # Concurrent reads
        async def reader(key):
            return await cache.get(key)
        
        tasks = [reader(f"key_{i}") for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 100
        for i, result in enumerate(results):
            assert result == f"value_{i}"
        
        await cache.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_writes(self):
        """Test concurrent write operations."""
        cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,
            local_cache_size=1000,
            redis_enabled=False,
        )
        await cache.start()
        
        # Concurrent writes
        async def writer(key, value):
            await cache.set(key, value)
        
        tasks = [writer(f"key_{i}", f"value_{i}") for i in range(100)]
        await asyncio.gather(*tasks)
        
        # Verify all writes succeeded
        for i in range(100):
            value = await cache.get(f"key_{i}")
            assert value == f"value_{i}"
        
        await cache.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self):
        """Test concurrent read/write operations."""
        cache = HybridCacheManager(
            cache_enabled=True,
            default_ttl=300,
            local_cache_size=1000,
            redis_enabled=False,
        )
        await cache.start()
        
        async def worker(worker_id):
            for i in range(50):
                key = f"key_{worker_id}_{i}"
                await cache.set(key, f"value_{i}")
                await cache.get(key)
        
        # Run 10 concurrent workers
        tasks = [worker(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify operations succeeded
        metrics = await cache.get_metrics()
        total_requests = metrics["hybrid"]["metrics"]["total_requests"]
        
        assert total_requests >= 500  # 10 workers * 50 reads
        
        await cache.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
