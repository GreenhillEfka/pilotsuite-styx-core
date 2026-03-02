"""
Tests for Metrics API endpoints

Tests:
- GET /api/v1/metrics/connection-pool
- GET /api/v1/metrics/cache
- GET /api/v1/metrics/all
- GET /api/v1/metrics/history
- GET /api/v1/metrics/health
"""

import pytest
from copilot_core.api.metrics import (
    _collect_current_metrics,
    _add_to_history,
    get_metrics_history,
    handle_connection_pool_metrics,
    handle_cache_metrics,
    handle_all_metrics,
    handle_metrics_history,
    handle_health,
)
from aiohttp import web


@pytest.fixture
def app():
    """Create test application with metrics routes."""
    app = web.Application()
    from copilot_core.api.metrics import setup_metrics_routes
    setup_metrics_routes(app)
    return app


@pytest.fixture
def client(aiohttp_client, app):
    """Create test client."""
    return aiohttp_client(app)


class TestMetricsCollection:
    """Test metrics collection functions."""

    def test_collect_current_metrics(self):
        """Test metrics collection returns expected structure."""
        metrics = _collect_current_metrics()
        
        assert "timestamp" in metrics
        assert "connection_pool" in metrics
        assert "cache" in metrics
        
        # Check timestamp is recent (within last second)
        import time
        assert abs(metrics["timestamp"] - time.time()) < 1.0

    def test_add_and_get_history(self):
        """Test adding metrics to history and retrieving."""
        # Clear history first
        from copilot_core.api.metrics import _metrics_history, _HISTORY_MAX_SIZE
        _metrics_history.clear()
        
        # Add test metrics with current timestamp
        import time
        test_metrics = {"timestamp": time.time(), "test": "data"}
        _add_to_history(test_metrics)
        
        # Retrieve history
        history = get_metrics_history(duration_hours=24)
        assert len(history) >= 1
        assert test_metrics in history
        
        # Restore history for other tests
        _metrics_history.clear()

    def test_history_rotation(self):
        """Test that history rotates old entries."""
        from copilot_core.api.metrics import _metrics_history, _HISTORY_MAX_SIZE
        
        # Clear history
        _metrics_history.clear()
        
        # Add more than max entries
        for i in range(_HISTORY_MAX_SIZE + 100):
            _add_to_history({"timestamp": i})
        
        # Should be capped at max size
        assert len(_metrics_history) <= _HISTORY_MAX_SIZE
        
        # Verify oldest entries were removed (first entry should be 100, not 0)
        assert _metrics_history[0]["timestamp"] == 100
        
        # Restore history for other tests
        _metrics_history.clear()


class TestMetricsEndpoints:
    """Test metrics API endpoints."""

    @pytest.mark.asyncio
    async def test_connection_pool_metrics(self, client):
        """Test GET /api/v1/metrics/connection-pool."""
        resp = await client.get("/api/v1/metrics/connection-pool")
        assert resp.status == 200
        
        data = await resp.json()
        assert "ha_pool" in data
        assert "ollama_pool" in data
        assert "config" in data
        
        # Check HA pool structure
        ha_pool = data["ha_pool"]
        assert "pool_size" in ha_pool
        assert "active_connections" in ha_pool
        assert "idle_connections" in ha_pool
        assert "reuse_rate_pct" in ha_pool
        assert "healthy" in ha_pool
        assert "session_active" in ha_pool

    @pytest.mark.asyncio
    async def test_cache_metrics(self, client):
        """Test GET /api/v1/metrics/cache."""
        resp = await client.get("/api/v1/metrics/cache")
        assert resp.status == 200
        
        data = await resp.json()
        # Cache stats should be returned (structure depends on cache implementation)
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_all_metrics(self, client):
        """Test GET /api/v1/metrics/all."""
        resp = await client.get("/api/v1/metrics/all")
        assert resp.status == 200
        
        data = await resp.json()
        assert "timestamp" in data
        assert "connection_pool" in data
        assert "cache" in data

    @pytest.mark.asyncio
    async def test_metrics_history(self, client):
        """Test GET /api/v1/metrics/history."""
        resp = await client.get("/api/v1/metrics/history")
        assert resp.status == 200
        
        data = await resp.json()
        assert "history" in data
        assert "count" in data
        assert isinstance(data["history"], list)
        assert isinstance(data["count"], int)

    @pytest.mark.asyncio
    async def test_metrics_history_with_duration(self, client):
        """Test GET /api/v1/metrics/history with duration parameter."""
        resp = await client.get("/api/v1/metrics/history?duration=12")
        assert resp.status == 200
        
        data = await resp.json()
        assert "history" in data
        assert "count" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test GET /api/v1/metrics/health."""
        resp = await client.get("/api/v1/metrics/health")
        assert resp.status == 200
        
        data = await resp.json()
        assert "healthy" in data
        assert "components" in data
        assert "timestamp" in data
        
        # Check components structure
        components = data["components"]
        assert "ha_pool" in components
        assert "ollama_pool" in components
        assert "cache" in components


class TestMetricsDashboard:
    """Test metrics dashboard integration."""

    @pytest.mark.asyncio
    async def test_metrics_for_dashboard(self, client):
        """Test that metrics endpoint returns dashboard-compatible data."""
        resp = await client.get("/api/v1/metrics/connection-pool")
        assert resp.status == 200
        
        data = await resp.json()
        
        # Dashboard expects specific fields
        ha_pool = data["ha_pool"]
        assert isinstance(ha_pool["pool_size"], int)
        assert isinstance(ha_pool["reuse_rate_pct"], (int, float))
        assert isinstance(ha_pool["healthy"], bool)
        assert isinstance(ha_pool["session_active"], bool)
