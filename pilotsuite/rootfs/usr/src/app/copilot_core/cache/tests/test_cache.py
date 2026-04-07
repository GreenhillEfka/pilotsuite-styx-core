"""Tests for cache module."""
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


class TestCacheMetrics:
    """Test cache metrics tracking."""
    
    @pytest.mark.asyncio
    async def test_hit_miss_ratio(self):
        from copilot_core.cache.api_cache import CacheMetrics
        
        metrics = CacheMetrics()
        await metrics.record_hit()
        await metrics.record_hit()
        await metrics.record_miss()
        
        stats = await metrics.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total"] == 3
        assert stats["hit_ratio"] == pytest.approx(0.667, rel=0.01)
    
    @pytest.mark.asyncio
    async def test_reset(self):
        from copilot_core.cache.api_cache import CacheMetrics
        
        metrics = CacheMetrics()
        await metrics.record_hit()
        await metrics.reset()
        
        stats = await metrics.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestAPICache:
    """Test API cache layer."""
    
    @pytest.mark.asyncio
    async def test_cache_entity_data(self):
        from copilot_core.cache.api_cache import APICache
        from copilot_core.cache.redis_client import InMemoryStore
        
        # Mock redis client to use in-memory
        with patch('copilot_core.cache.api_cache.get_redis_client') as mock_get:
            mock_redis = MagicMock()
            mock_redis.get = AsyncMock(side_effect=lambda k: None)
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock(return_value=True)
            mock_redis.delete_pattern = AsyncMock(return_value=0)
            mock_redis.flush = AsyncMock(return_value=True)
            mock_redis.get_stats = AsyncMock(return_value={"connected": False, "using_fallback": True})
            mock_get.return_value = mock_redis
            
            cache = APICache(mock_redis)
            result = await cache.cache_entity_data("light.living_room", {"state": "on"})
            assert result is True
    
    @pytest.mark.asyncio
    async def test_invalidate_pattern(self):
        from copilot_core.cache.api_cache import APICache
        
        with patch('copilot_core.cache.api_cache.get_redis_client') as mock_get:
            mock_redis = MagicMock()
            mock_redis.delete_pattern = AsyncMock(return_value=5)
            mock_get.return_value = mock_redis
            
            cache = APICache(mock_redis)
            count = await cache.invalidate_entities()
            assert count == 5


class TestCacheEndpoints:
    """Test cache control API endpoints."""
    
    def test_cache_status_endpoint(self):
        """Test /api/v1/cache/status endpoint."""
        from copilot_core.api.v1.cache_control import cache_control_bp
        from flask import Flask
        
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(cache_control_bp, url_prefix="/api/v1/cache")
        
        with app.test_client() as client:
            # Without auth token
            response = client.get("/api/v1/cache/status")
            assert response.status_code in [401, 403]
    
    def test_cache_stats_endpoint(self):
        """Test /api/v1/cache/stats endpoint."""
        from copilot_core.api.v1.cache_control import cache_control_bp
        from flask import Flask
        
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(cache_control_bp, url_prefix="/api/v1/cache")
        
        with app.test_client() as client:
            response = client.get("/api/v1/cache/stats")
            assert response.status_code in [401, 403]
    
    def test_cache_invalidate_endpoint(self):
        """Test /api/v1/cache/invalidate endpoint."""
        from copilot_core.api.v1.cache_control import cache_control_bp
        from flask import Flask
        
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(cache_control_bp, url_prefix="/api/v1/cache")
        
        with app.test_client() as client:
            response = client.post("/api/v1/cache/invalidate", json={"all": True})
            assert response.status_code in [401, 403]
