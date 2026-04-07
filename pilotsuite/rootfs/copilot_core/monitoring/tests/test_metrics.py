"""Tests for monitoring metrics module."""
import pytest


class TestPrometheusMetrics:
    """Test Prometheus metrics collection."""
    
    def test_metrics_collector_init(self):
        """Test metrics collector initialization."""
        # Module import might fail if psutil not installed, so just check import works
        try:
            from copilot_core.monitoring.metrics import PrometheusMetrics
            metrics = PrometheusMetrics()
            assert metrics is not None
        except ImportError:
            pytest.skip("psutil not installed")
    
    def test_get_metrics_collector_singleton(self):
        """Test singleton pattern for metrics collector."""
        try:
            from copilot_core.monitoring.metrics import get_metrics_collector
            
            collector1 = get_metrics_collector()
            collector2 = get_metrics_collector()
            assert collector1 is collector2
        except ImportError:
            pytest.skip("psutil not installed")


class TestTrackRequestLatency:
    """Test request latency tracking decorator."""
    
    def test_decorator_exists(self):
        """Test decorator exists."""
        try:
            from copilot_core.monitoring.metrics import track_request_latency
            assert callable(track_request_latency)
        except ImportError:
            pytest.skip("psutil not installed")


class TestGetPrometheusMetrics:
    """Test Prometheus metrics retrieval."""
    
    def test_get_prometheus_metrics(self):
        """Test getting Prometheus metrics."""
        try:
            from copilot_core.monitoring.metrics import get_prometheus_metrics
            
            metrics = get_prometheus_metrics()
            assert metrics is not None
        except ImportError:
            pytest.skip("psutil not installed")
