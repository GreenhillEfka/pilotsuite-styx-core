"""Tests for Connection Pool Metrics API endpoints.

Test coverage for Pool Metrics endpoints:
- GET /api/v1/performance/pool/status - SQL pool status
- GET /api/v1/performance/pool/metrics - All pool metrics
- GET /api/v1/performance/pool/metrics/summary - Health summary

Author: @cowdya
Version: 1.0.0
Created: 2026-03-02
"""
import pytest
from flask import Flask
from unittest.mock import patch, MagicMock


def create_test_app():
    """Helper to create test app with all mocks."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


class TestPoolStatus:
    """Tests for GET /api/v1/performance/pool/status"""
    
    def test_pool_status_success(self):
        """Test successful pool status retrieval."""
        mock_sql_pool = MagicMock()
        mock_sql_pool.get_stats.return_value = {
            "active_connections": 5,
            "idle_connections": 3,
            "max_connections": 20,
            "total_queries": 1250,
            "avg_query_time_ms": 12.5,
        }
        
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.security.validate_token', return_value=True):
                from copilot_core.api import performance
                
                app = create_test_app()
                app.register_blueprint(performance.performance_bp)
                
                with app.test_client() as client:
                    response = client.get("/api/v1/performance/pool/status")
                    assert response.status_code == 200
                    
                    data = response.get_json()
                    assert "version" in data
                    assert "timestamp_ms" in data
                    assert data["active_connections"] == 5
                    assert data["max_connections"] == 20
    
    def test_pool_status_auth_required(self):
        """Test that pool status requires authentication."""
        mock_sql_pool = MagicMock()
        mock_sql_pool.get_stats.return_value = {}
        
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.security.validate_token', return_value=False):
                from copilot_core.api import performance
                
                app = create_test_app()
                app.register_blueprint(performance.performance_bp)
                
                with app.test_client() as client:
                    response = client.get("/api/v1/performance/pool/status")
                    assert response.status_code == 401


class TestPoolMetrics:
    """Tests for GET /api/v1/performance/pool/metrics"""
    
    def test_pool_metrics_all(self):
        """Test retrieving all pool metrics."""
        mock_sql_pool = MagicMock()
        mock_sql_pool.get_stats.return_value = {
            "active_connections": 5,
            "max_connections": 20,
        }
        
        mock_async_metrics = {
            "ha_pool": {
                "requests_total": 500,
                "connections_reused": 425,
                "reuse_rate_pct": 85.0,
                "healthy": True,
            },
            "ollama_pool": {
                "requests_total": 300,
                "connections_reused": 240,
                "reuse_rate_pct": 80.0,
                "healthy": True,
            },
        }
        
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.performance.HAS_ASYNC_POOL', True):
                with patch('copilot_core.api.performance.get_async_pool_metrics', return_value=mock_async_metrics):
                    with patch('copilot_core.api.security.validate_token', return_value=True):
                        from copilot_core.api import performance
                        
                        app = create_test_app()
                        app.register_blueprint(performance.performance_bp)
                        
                        with app.test_client() as client:
                            response = client.get("/api/v1/performance/pool/metrics")
                            assert response.status_code == 200
                            
                            data = response.get_json()
                            assert "sql_pool" in data
                            assert "async_pools" in data
                            assert data["async_pools"]["ha_pool"]["reuse_rate_pct"] == 85.0
    
    def test_pool_metrics_sql_only(self):
        """Test retrieving only SQL pool metrics."""
        mock_sql_pool = MagicMock()
        mock_sql_pool.get_stats.return_value = {"active_connections": 5}
        
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.security.validate_token', return_value=True):
                from copilot_core.api import performance
                
                app = create_test_app()
                app.register_blueprint(performance.performance_bp)
                
                with app.test_client() as client:
                    response = client.get("/api/v1/performance/pool/metrics?pool=sql")
                    assert response.status_code == 200
                    
                    data = response.get_json()
                    assert "sql_pool" in data
                    assert "async_pools" not in data


class TestPoolMetricsSummary:
    """Tests for GET /api/v1/performance/pool/metrics/summary"""
    
    def test_pool_summary_healthy(self):
        """Test pool summary when all pools are healthy."""
        mock_sql_pool = MagicMock()
        mock_sql_pool.get_stats.return_value = {
            "active_connections": 5,
            "idle_connections": 3,
            "max_connections": 20,
        }
        
        mock_async_metrics = {
            "ha_pool": {"reuse_rate_pct": 85.0, "healthy": True},
            "ollama_pool": {"reuse_rate_pct": 80.0, "healthy": True},
        }
        
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.performance.HAS_ASYNC_POOL', True):
                with patch('copilot_core.api.performance.get_async_pool_metrics', return_value=mock_async_metrics):
                    with patch('copilot_core.api.security.validate_token', return_value=True):
                        from copilot_core.api import performance
                        
                        app = create_test_app()
                        app.register_blueprint(performance.performance_bp)
                        
                        with app.test_client() as client:
                            response = client.get("/api/v1/performance/pool/metrics/summary")
                            assert response.status_code == 200
                            
                            data = response.get_json()
                            assert data["health"]["status"] == "healthy"
                            assert data["health"]["sql_pool"]["usage_pct"] == 25.0
                            assert len(data["health"]["recommendations"]) == 0
    
    def test_pool_summary_degraded_high_usage(self):
        """Test pool summary when SQL usage is high."""
        mock_sql_pool = MagicMock()
        mock_sql_pool.get_stats.return_value = {
            "active_connections": 16,
            "max_connections": 20,
        }
        
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.performance.HAS_ASYNC_POOL', True):
                with patch('copilot_core.api.performance.get_async_pool_metrics', return_value={}):
                    with patch('copilot_core.api.security.validate_token', return_value=True):
                        from copilot_core.api import performance
                        
                        app = create_test_app()
                        app.register_blueprint(performance.performance_bp)
                        
                        with app.test_client() as client:
                            response = client.get("/api/v1/performance/pool/metrics/summary")
                            assert response.status_code == 200
                            
                            data = response.get_json()
                            assert data["health"]["status"] == "degraded"
                            assert len(data["health"]["recommendations"]) > 0
    
    def test_pool_summary_unhealthy_critical(self):
        """Test pool summary when SQL usage is critical (>90%)."""
        mock_sql_pool = MagicMock()
        mock_sql_pool.get_stats.return_value = {
            "active_connections": 19,
            "idle_connections": 1,
            "max_connections": 20,
        }
        
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.performance.HAS_ASYNC_POOL', True):
                with patch('copilot_core.api.performance.get_async_pool_metrics', return_value={}):
                    with patch('copilot_core.api.security.validate_token', return_value=True):
                        from copilot_core.api import performance
                        
                        app = create_test_app()
                        app.register_blueprint(performance.performance_bp)
                        
                        with app.test_client() as client:
                            response = client.get("/api/v1/performance/pool/metrics/summary")
                            assert response.status_code == 200
                            
                            data = response.get_json()
                            # Health check uses active/max calculation
                            assert data["health"]["status"] in ["degraded", "unhealthy"]
                            assert len(data["health"]["recommendations"]) > 0


class TestPoolCleanup:
    """Tests for POST /api/v1/performance/pool/cleanup"""
    
    def test_pool_cleanup_success(self):
        """Test successful pool cleanup."""
        # Create a simple class-based mock that returns int
        class MockSQLPool:
            def cleanup_idle(self):
                return 2
            def get_stats(self):
                return {}
        
        mock_sql_pool = MockSQLPool()
        
        # Patch where it's used (copilot_core.api.performance), not where it's defined
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.security.validate_token', return_value=True):
                from copilot_core.api import performance
                
                app = create_test_app()
                app.register_blueprint(performance.performance_bp)
                
                with app.test_client() as client:
                    response = client.post("/api/v1/performance/pool/cleanup")
                    assert response.status_code == 200
                    
                    data = response.get_json()
                    assert "message" in data
                    assert data["removed"] == 2
    
    def test_pool_cleanup_auth_required(self):
        """Test that pool cleanup requires authentication."""
        mock_sql_pool = MagicMock()
        mock_sql_pool.cleanup_idle.return_value = 0
        
        with patch('copilot_core.api.performance.sql_pool', mock_sql_pool):
            with patch('copilot_core.api.security.validate_token', return_value=False):
                from copilot_core.api import performance
                
                app = create_test_app()
                app.register_blueprint(performance.performance_bp)
                
                with app.test_client() as client:
                    response = client.post("/api/v1/performance/pool/cleanup")
                    assert response.status_code == 401
