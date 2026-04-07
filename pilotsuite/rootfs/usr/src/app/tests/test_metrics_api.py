"""
Tests for Metrics API endpoints

Tests Flask endpoints in /api/v1/metrics/*
- /metrics - Prometheus metrics endpoint
- /health - Extended health check endpoint
- /ready - Readiness probe
"""

import pytest
from copilot_core.api.metrics import (
    _collect_current_metrics,
    _add_to_history,
    get_metrics_history,
)

# No aiohttp imports needed - using Flask test client


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
    """Test metrics API endpoints via Flask Blueprint."""

    def test_metrics_prometheus(self, test_client):
        """Test GET /api/v1/metrics (Prometheus endpoint)."""
        resp = test_client.get("/api/v1/metrics")
        assert resp.status_code == 200
        
        data = resp.get_data(as_text=True)
        # Prometheus format: metrics with labels
        assert "# HELP" in data or "# TYPE" in data or "prometheus" in data.lower()

    def test_health_extended(self, test_client):
        """Test GET /api/v1/health (extended health check from metrics_bp)."""
        resp = test_client.get("/api/v1/health")
        assert resp.status_code == 200
        
        data = resp.get_json()
        assert "healthy" in data or "status" in data

    def test_ready_probe(self, test_client):
        """Test GET /api/v1/ready (readiness probe from metrics_bp)."""
        resp = test_client.get("/api/v1/ready")
        assert resp.status_code == 200
        
        data = resp.get_json()
        assert "ready" in data or "status" in data


class TestMetricsDashboard:
    """Test metrics dashboard integration."""

    def test_metrics_structure(self, test_client):
        """Test that metrics endpoint returns dashboard-compatible data."""
        resp = test_client.get("/api/v1/metrics")
        assert resp.status_code == 200
        
        data = resp.get_data(as_text=True)
        
        # Prometheus format should contain metric names
        assert len(data) > 0
