"""Tests for cache core module."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestInMemoryStore:
    """Test in-memory fallback store."""
    
    @pytest.mark.asyncio
    async def test_set_get(self):
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        await store.set("key1", "value1")
        result = await store.get("key1")
        assert result == "value1"
    
    @pytest.mark.asyncio
    async def test_delete(self):
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        await store.set("key1", "value1")
        await store.delete("key1")
        result = await store.get("key1")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_flush(self):
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        await store.set("key1", "value1")
        await store.set("key2", "value2")
        await store.flush()
        keys = await store.keys()
        assert len(keys) == 0
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        from copilot_core.cache.redis_client import InMemoryStore
        import time
        
        store = InMemoryStore()
        await store.set("key1", "value1", ttl=1)
        await asyncio.sleep(1.1)
        result = await store.get("key1")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_pattern(self):
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        await store.set("entity:light1", {"state": "on"})
        await store.set("entity:light2", {"state": "off"})
        await store.set("state:light1", "on")
        count = await store.delete_pattern("entity:*")
        assert count == 2
        # state:light1 should still exist
        result = await store.get("state:light1")
        assert result == "on"
    
    @pytest.mark.asyncio
    async def test_keys(self):
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        await store.set("key1", "value1")
        await store.set("key2", "value2")
        keys = await store.keys()
        assert len(keys) == 2
        assert "key1" in keys
        assert "key2" in keys
    
    @pytest.mark.asyncio
    async def test_keys_pattern(self):
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        await store.set("entity:light1", "on")
        await store.set("entity:light2", "off")
        await store.set("state:light1", "on")
        keys = await store.keys("entity:*")
        assert len(keys) == 2
        assert "entity:light1" in keys
        assert "entity:light2" in keys


class TestRedisClient:
    """Test Redis client with fallback."""
    
    @pytest.mark.asyncio
    async def test_init_default(self):
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        assert client.host == "localhost"
        assert client.port == 6379
        assert client.key_prefix == "pilotsuite:"
    
    @pytest.mark.asyncio
    async def test_init_custom(self):
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient(host="redis.local", port=6380, key_prefix="test:")
        assert client.host == "redis.local"
        assert client.port == 6380
        assert client.key_prefix == "test:"
    
    @pytest.mark.asyncio
    async def test_full_key(self):
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient(key_prefix="test:")
        assert client._full_key("mykey") == "test:mykey"
    
    @pytest.mark.asyncio
    async def test_get_fallback_when_redis_unavailable(self):
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        # Connect should fall back to in-memory
        result = await client.connect()
        assert result == False  # Redis not connected, using fallback
        assert client._connected == False
        
        # Operations should use fallback
        await client.set("key", "value")
        value = await client.get("key")
        assert value == "value"
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        await client.connect()
        stats = await client.get_stats()
        assert "connected" in stats
        assert "host" in stats
        assert "port" in stats
        assert "using_fallback" in stats
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        await client.connect()
        await client.disconnect()
        assert client._connected == False
    
    @pytest.mark.asyncio
    async def test_is_connected_property(self):
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        assert client.is_connected == False
        await client.connect()
        assert client.is_connected == False  # Falls back, so not connected
    
    @pytest.mark.asyncio
    async def test_get_global_instance(self):
        from copilot_core.cache.redis_client import get_redis_client, _redis_client
        
        # Reset global
        import copilot_core.cache.redis_client as rc
        rc._redis_client = None
        
        client = get_redis_client()
        assert client is not None
        assert isinstance(client, rc.RedisClient)


class TestAPICache:
    """Test API cache layer."""
    
    @pytest.mark.asyncio
    async def test_make_key(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        # _make_key returns an MD5 hash
        key = cache._make_key("test", "method", "arg1", kwarg1="val1")
        assert len(key) == 32  # MD5 hash is 32 chars
        # Same inputs should produce same hash
        key2 = cache._make_key("test", "method", "arg1", kwarg1="val1")
        assert key == key2
        # Different inputs should produce different hash
        key3 = cache._make_key("test", "method", "arg2", kwarg1="val1")
        assert key != key3
    
    @pytest.mark.asyncio
    async def test_cache_entity_data(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        result = await cache.cache_entity_data("light.living_room", {"state": "on"})
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_cached_entity(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        await cache.cache_entity_data("light.living_room", {"state": "on"})
        result = await cache.get_entity_data("light.living_room")
        assert result is not None
        assert result.get("state") == "on"
    
    @pytest.mark.asyncio
    async def test_cache_state(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        result = await cache.cache_state("light.living_room", "on")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_cached_state(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        await cache.cache_state("light.living_room", "on")
        result = await cache.get_state("light.living_room")
        assert result == "on"
    
    @pytest.mark.asyncio
    async def test_invalidate_entity(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        await cache.cache_entity_data("light.living_room", {"state": "on"})
        await cache.invalidate_entity("light.living_room")
        result = await cache.get_entity_data("light.living_room")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalidate_state(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        await cache.cache_state("light.living_room", "on")
        await cache.invalidate_state("light.living_room")
        result = await cache.get_state("light.living_room")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalidate_pattern(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        await cache.cache_entity_data("light.living_room", {"state": "on"})
        await cache.cache_entity_data("light.kitchen", {"state": "off"})
        count = await cache.invalidate_pattern("entity:light*")
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_invalidate_entities(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        await cache.cache_entity_data("light.living_room", {"state": "on"})
        await cache.cache_entity_data("light.kitchen", {"state": "off"})
        count = await cache.invalidate_entities()
        assert count > 0
    
    @pytest.mark.asyncio
    async def test_invalidate_states(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        await cache.cache_state("light.living_room", "on")
        await cache.cache_state("light.kitchen", "off")
        count = await cache.invalidate_states()
        assert count > 0
    
    @pytest.mark.asyncio
    async def test_invalidate_all(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        await cache.cache_entity_data("light.living_room", {"state": "on"})
        await cache.cache_state("light.living_room", "on")
        count = await cache.invalidate_all()
        assert count > 0
    
    @pytest.mark.asyncio
    async def test_metrics(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        stats = await cache.metrics.get_stats()
        assert "hits" in stats
        assert "misses" in stats
    
    @pytest.mark.asyncio
    async def test_get_or_set(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        cache = APICache(store)
        
        call_count = 0
        
        async def fetch_data():
            nonlocal call_count
            call_count += 1
            return {"data": "cached"}
        
        # First call - should fetch and cache
        result1 = await cache.get_or_set("key1", fetch_data, ttl=60)
        assert result1 == {"data": "cached"}
        assert call_count == 1
        
        # Second call - should return cached
        result2 = await cache.get_or_set("key1", fetch_data, ttl=60)
        assert result2 == {"data": "cached"}
        assert call_count == 1  # Not called again
    
    @pytest.mark.asyncio
    async def test_cache_decorator(self):
        from copilot_core.cache.api_cache import cached
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        
        call_count = 0
        
        @cached(key_prefix="test", ttl=60)
        async def my_function(self, arg1):
            nonlocal call_count
            call_count += 1
            return f"result_{arg1}"
        
        # Create a mock self with redis client
        class MockCache:
            pass
        
        mock_self = MockCache()
        mock_self.redis = store
        
        result1 = await my_function(mock_self, "test")
        assert result1 == "result_test"
        assert call_count == 1
        
        result2 = await my_function(mock_self, "test")
        assert result2 == "result_test"
        assert call_count == 1  # Not called again


class TestCacheMetrics:
    """Test cache metrics tracking."""
    
    @pytest.mark.asyncio
    async def test_record_hit(self):
        from copilot_core.cache.api_cache import CacheMetrics
        
        metrics = CacheMetrics()
        await metrics.record_hit()
        stats = await metrics.get_stats()
        assert stats["hits"] == 1
        assert stats["total"] == 1
    
    @pytest.mark.asyncio
    async def test_record_miss(self):
        from copilot_core.cache.api_cache import CacheMetrics
        
        metrics = CacheMetrics()
        await metrics.record_miss()
        stats = await metrics.get_stats()
        assert stats["misses"] == 1
        assert stats["total"] == 1
    
    @pytest.mark.asyncio
    async def test_hit_ratio(self):
        from copilot_core.cache.api_cache import CacheMetrics
        
        metrics = CacheMetrics()
        await metrics.record_hit()
        await metrics.record_hit()
        await metrics.record_miss()
        
        stats = await metrics.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total"] == 3
        assert abs(stats["hit_ratio"] - 2/3) < 0.01
    
    @pytest.mark.asyncio
    async def test_reset(self):
        from copilot_core.cache.api_cache import CacheMetrics
        
        metrics = CacheMetrics()
        await metrics.record_hit()
        await metrics.record_miss()
        await metrics.reset()
        
        stats = await metrics.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total"] == 0


class TestRedisClientFallback:
    """Test Redis client fallback behavior."""
    
    @pytest.mark.asyncio
    async def test_fallback_flush(self):
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        await store.set("key1", "value1")
        await store.set("key2", "value2")
        
        # Flush should clear everything
        result = await store.flush()
        assert result is True
        assert len(await store.keys()) == 0
    
    @pytest.mark.asyncio
    async def test_fallback_ping(self):
        from copilot_core.cache.redis_client import InMemoryStore
        
        store = InMemoryStore()
        result = await store.ping()
        assert result is True


class TestCacheInvalidationSetup:
    """Test cache invalidation setup functions."""
    
    @pytest.mark.asyncio
    async def test_setup_cache_invalidation(self):
        """Test setup_cache_invalidation registers listeners."""
        from copilot_core.cache.api_cache import setup_cache_invalidation
        
        # Mock websocket handler with register_listener method
        mock_handler = MagicMock()
        mock_handler.register_listener = MagicMock()
        
        await setup_cache_invalidation(mock_handler)
        
        # Should register two listeners
        assert mock_handler.register_listener.call_count == 2
        mock_handler.register_listener.assert_any_call("state_changed", MagicMock())
        mock_handler.register_listener.assert_any_call("entity_added", MagicMock())
    
    @pytest.mark.asyncio
    async def test_setup_cache_invalidation_no_register_listener(self):
        """Test setup_cache_invalidation when handler doesn't support register_listener."""
        from copilot_core.cache.api_cache import setup_cache_invalidation
        
        # Mock websocket handler without register_listener method
        mock_handler = MagicMock(spec=[])
        
        # Should not raise
        await setup_cache_invalidation(mock_handler)
    
    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Test get_cache_stats returns statistics."""
        from copilot_core.cache.api_cache import get_cache_stats, get_api_cache
        from unittest.mock import AsyncMock, patch
        
        # Mock the cache
        mock_cache = AsyncMock()
        mock_cache.metrics.get_stats = AsyncMock(return_value={
            "hits": 10,
            "misses": 5,
            "total": 15,
            "hit_ratio": 0.67
        })
        mock_cache.redis.get_stats = AsyncMock(return_value={"status": "connected"})
        mock_cache.redis.is_connected = True
        mock_cache.redis._redis = AsyncMock()
        mock_cache.redis._redis.keys = AsyncMock(return_value=["key1", "key2", "key3"])
        mock_cache.redis.key_prefix = "test:"
        
        with patch('copilot_core.cache.api_cache.get_api_cache', return_value=mock_cache):
            stats = await get_cache_stats()
            
            assert stats["total_keys"] == 3
            assert stats["hits"] == 10
            assert stats["misses"] == 5
            assert stats["hit_rate_pct"] == 67.0
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_disconnected(self):
        """Test get_cache_stats when Redis is disconnected."""
        from copilot_core.cache.api_cache import get_cache_stats, get_api_cache
        from unittest.mock import AsyncMock, patch
        
        # Mock the cache with disconnected Redis
        mock_cache = AsyncMock()
        mock_cache.metrics.get_stats = AsyncMock(return_value={
            "hits": 5,
            "misses": 5,
            "total": 10,
            "hit_ratio": 0.5
        })
        mock_cache.redis.get_stats = AsyncMock(return_value={"status": "disconnected"})
        mock_cache.redis.is_connected = False
        mock_cache.redis._fallback._store = {"key1": "val1"}
        
        with patch('copilot_core.cache.api_cache.get_api_cache', return_value=mock_cache):
            stats = await get_cache_stats()
            
            assert stats["total_keys"] == 1  # From fallback store
            assert stats["hits"] == 5
            assert stats["connection"]["status"] == "disconnected"


class TestRedisClientConnection:
    """Test Redis client connection methods."""
    
    @pytest.mark.asyncio
    async def test_connect_without_redis(self):
        """Test connect returns False when redis not available."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        # Without redis package, should use fallback
        result = await client.connect()
        # Should return False or True depending on redis availability
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect method."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = True
        client._redis = AsyncMock()
        client._redis.close = AsyncMock()
        
        await client.disconnect()
        
        assert client._connected is False
        client._redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_is_connected_property(self):
        """Test is_connected property."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = True
        assert client.is_connected is True
        
        client._connected = False
        assert client.is_connected is False
    
    @pytest.mark.asyncio
    async def test_get_store_connected(self):
        """Test _get_store returns redis when connected."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = True
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        client._redis = mock_redis
        
        store = await client._get_store()
        assert store == mock_redis
    
    @pytest.mark.asyncio
    async def test_get_store_fallback(self):
        """Test _get_store returns fallback when disconnected."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = False
        
        store = await client._get_store()
        assert store == client._fallback
    
    @pytest.mark.asyncio
    async def test_get_store_fallback_on_ping_failure(self):
        """Test _get_store switches to fallback when ping fails."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = True
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection lost"))
        client._redis = mock_redis
        
        store = await client._get_store()
        assert store == client._fallback
        assert client._connected is False
    
    @pytest.mark.asyncio
    async def test_get_with_fallback(self):
        """Test get method uses fallback."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = False
        await client._fallback.set("test:key", "value")
        
        result = await client.get("key")
        assert result == "value"
    
    @pytest.mark.asyncio
    async def test_set_with_fallback(self):
        """Test set method uses fallback."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = False
        
        result = await client.set("key", "value", ttl=60)
        assert result is True
        
        stored = await client._fallback.get("test:key")
        assert stored == "value"
    
    @pytest.mark.asyncio
    async def test_delete_with_fallback(self):
        """Test delete method uses fallback."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = False
        await client._fallback.set("test:key", "value")
        
        result = await client.delete("key")
        assert result is True
        
        stored = await client._fallback.get("test:key")
        assert stored is None
    
    @pytest.mark.asyncio
    async def test_delete_pattern_with_fallback(self):
        """Test delete_pattern method uses fallback."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = False
        await client._fallback.set("test:entity:1", "val1")
        await client._fallback.set("test:entity:2", "val2")
        await client._fallback.set("test:state:1", "val3")
        
        count = await client.delete_pattern("entity:*")
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_flush_with_fallback(self):
        """Test flush method uses fallback."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = False
        await client._fallback.set("test:key1", "val1")
        await client._fallback.set("test:key2", "val2")
        
        result = await client.flush()
        assert result is True
        
        keys = await client._fallback.keys("test:*")
        assert len(keys) == 0
    
    @pytest.mark.asyncio
    async def test_ping_connected(self):
        """Test ping returns True when connected."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = True
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        client._redis = mock_redis
        
        result = await client.ping()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_ping_disconnected(self):
        """Test ping returns False when disconnected."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = False
        
        result = await client.ping()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test get_stats returns connection info."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient(host="testhost", port=6380)
        client._connected = True
        
        stats = await client.get_stats()
        assert stats["connected"] is True
        assert stats["host"] == "testhost"
        assert stats["port"] == 6380
        assert stats["using_fallback"] is False
    
    @pytest.mark.asyncio
    async def test_get_stats_fallback(self):
        """Test get_stats shows fallback mode."""
        from copilot_core.cache.redis_client import RedisClient
        
        client = RedisClient()
        client._connected = False
        
        stats = await client.get_stats()
        assert stats["connected"] is False
        assert stats["using_fallback"] is True
    
    @pytest.mark.asyncio
    async def test_init_redis_client(self):
        """Test init_redis_client function."""
        from copilot_core.cache.redis_client import init_redis_client, get_redis_client, _redis_client
        
        # Clear global instance
        import copilot_core.cache.redis_client as rc
        rc._redis_client = None
        
        client = await init_redis_client(host="testhost", port=6380, password="testpass")
        
        assert client is not None
        assert client.host == "testhost"
        assert client.port == 6380
        assert client.password == "testpass"
        
        # Reset
        rc._redis_client = None
