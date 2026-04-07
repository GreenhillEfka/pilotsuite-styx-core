"""Integration tests for cache with API endpoints."""

import pytest
from unittest.mock import MagicMock, patch
import asyncio


class TestSensorCacheIntegration:
    """Test sensor API with caching."""

    def test_sensor_service_creation(self):
        """Test that sensor service can be created."""
        from copilot_core.api.v1.sensors import SensorService

        service = SensorService()
        assert service is not None
        assert service._cache is not None

    @pytest.mark.asyncio
    async def test_sensor_cache_flow(self):
        """Test sensor data caching flow."""
        from copilot_core.api.v1.sensors import SensorService

        service = SensorService()

        # First call - should populate cache (miss)
        sensors1 = await service.get_all_sensors(use_cache=True)
        assert len(sensors1) > 0

        # Second call - should use cache (hit)
        sensors2 = await service.get_all_sensors(use_cache=True)
        assert len(sensors2) == len(sensors1)

        # Verify cache has data (check metrics)
        stats = await service._cache.get_stats()
        assert stats["total"] > 0 or stats["hits"] > 0

    @pytest.mark.asyncio
    async def test_sensor_get_single(self):
        """Test getting single sensor with caching."""
        from copilot_core.api.v1.sensors import SensorService

        service = SensorService()

        # Get all sensors first to know valid entity_id
        all_sensors = await service.get_all_sensors()
        if all_sensors:
            entity_id = all_sensors[0]["entity_id"]

            # Get specific sensor
            sensor = await service.get_sensor(entity_id)
            assert sensor is not None
            assert sensor["entity_id"] == entity_id


class TestHabitusCacheIntegration:
    """Test habitus API with caching."""

    def test_habitus_cache_import(self):
        """Test that habitus cache can be imported."""
        from copilot_core.cache import get_habitus_cache

        cache = get_habitus_cache()
        assert cache is not None
        assert cache._config.default_ttl == 900  # 15 minutes


class TestRAGCacheIntegration:
    """Test RAG BM25 with caching."""

    def test_bm25_search_method_exists(self, tmp_path):
        """Test that BM25 has search method."""
        from copilot_core.rag.bm25 import BM25SqliteIndex, BM25Config

        config = BM25Config(db_path=str(tmp_path / "test_rag.sqlite3"))
        bm25 = BM25SqliteIndex(config=config)

        # Check search method exists
        assert hasattr(bm25, 'search')
        assert hasattr(bm25, 'upsert_documents')

    def test_bm25_search_signature(self, tmp_path):
        """Test that search method signature."""
        from copilot_core.rag.bm25 import BM25SqliteIndex, BM25Config
        import inspect

        config = BM25Config(db_path=str(tmp_path / "test_rag.sqlite3"))
        bm25 = BM25SqliteIndex(config=config)

        # Check signature
        sig = inspect.signature(bm25.search)
        params = list(sig.parameters.keys())
        assert 'query' in params


class TestCacheMetricsIntegration:
    """Test cache metrics across all caches."""
    
    @pytest.mark.asyncio
    async def test_hybrid_caches_have_metrics(self):
        """Test that hybrid cache instances track metrics."""
        from copilot_core.cache import (
            get_habitus_cache,
            get_rag_cache,
        )
        
        caches = [
            ("habitus", get_habitus_cache()),
            ("rag", get_rag_cache()),
        ]
        
        for name, cache in caches:
            metrics = await cache.get_metrics()
            # Check hybrid metrics structure
            assert 'local' in metrics
            assert 'metrics' in metrics['local']
            assert 'hits' in metrics['local']['metrics']
            
            stats = await cache.get_stats()
            # Stats should have hybrid/local/redis structure
            assert 'hybrid' in stats or 'local' in stats
    
    @pytest.mark.asyncio
    async def test_sensor_cache_has_stats(self):
        """Test that sensor cache has stats."""
        from copilot_core.cache import get_sensor_cache
        
        cache = get_sensor_cache()
        stats = await cache.get_stats()
        assert 'total' in stats or 'hits' in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
