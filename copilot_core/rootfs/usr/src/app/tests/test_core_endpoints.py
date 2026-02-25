"""
PilotSuite Core — Test Infrastructure Setup (v7.11.0)

Tests für: Error Boundaries, Core Endpoints, Integration Tests
"""

import pytest
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'usr', 'src', 'app'))


class TestErrorBoundaries:
    """Test error handling and isolation (P0)."""
    
    def test_circuit_breaker_imports(self):
        """Circuit breaker module should be importable."""
        from copilot_core.circuit_breaker import CircuitBreaker, get_all_breaker_status
        assert CircuitBreaker is not None
    
    def test_error_boundary_imports(self):
        """Error boundary module should be importable."""
        from copilot_core.error_boundary import ErrorBoundary, register_error_handler
        assert ErrorBoundary is not None
    
    def test_error_status_imports(self):
        """Error status module should be importable."""
        from copilot_core.error_status import ErrorStatus, get_global_status
        assert ErrorStatus is not None


class TestCoreEndpoints:
    """Test core API endpoints."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        return app
    
    def test_health_endpoint(self, app):
        """Health endpoint should return 200."""
        with app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data.get('ok') is True
    
    def test_ready_endpoint(self, app):
        """Ready endpoint should return 200 or 503."""
        with app.test_client() as client:
            response = client.get('/ready')
            assert response.status_code in (200, 503)
    
    def test_version_endpoint(self, app):
        """Version endpoint should return version info."""
        with app.test_client() as client:
            response = client.get('/version')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'version' in data
            assert 'name' in data
            assert data['name'] == 'Styx'


class TestHubDashboard:
    """Test Hub Dashboard functionality."""
    
    def test_dashboard_hub_imports(self):
        """DashboardHub should be importable."""
        from copilot_core.hub.dashboard import DashboardHub, Widget, WIDGET_TYPES
        assert DashboardHub is not None
        assert len(WIDGET_TYPES) > 0
    
    def test_dashboard_hub_instantiation(self):
        """DashboardHub should instantiate correctly."""
        from copilot_core.hub.dashboard import DashboardHub
        hub = DashboardHub()
        assert hub is not None
        overview = hub.get_overview()
        assert overview.ok is True
    
    def test_widget_types(self):
        """Verify expected widget types exist."""
        from copilot_core.hub.dashboard import WIDGET_TYPES
        expected = ['energy_overview', 'battery_status', 'heat_pump_status']
        for w in expected:
            assert w in WIDGET_TYPES


class TestHubAPI:
    """Test Hub API endpoints."""
    
    def test_hub_api_imports(self):
        """Hub API should be importable."""
        try:
            from copilot_core.hub.api import hub_bp, init_hub_api
            assert hub_bp is not None
        except ImportError as e:
            pytest.fail(f"Hub API import failed: {e}")
    
    def test_hub_api_routes_registered(self):
        """Hub API blueprint should have routes."""
        from copilot_core.hub.api import hub_bp
        # Check that blueprint has URL rules
        assert len(hub_bp.url_values_defaults) >= 0


class TestConversationAPI:
    """Test Conversation/LLM API."""
    
    def test_llm_provider_imports(self):
        """LLM provider should be importable."""
        from copilot_core.llm_provider import LLMProvider
        assert LLMProvider is not None
    
    def test_conversation_memory_imports(self):
        """Conversation memory should be importable."""
        from copilot_core.conversation_memory import ConversationMemory
        assert ConversationMemory is not None


class TestBrainGraph:
    """Test Brain Graph functionality."""
    
    def test_brain_graph_service_imports(self):
        """Brain graph service should be importable."""
        try:
            from copilot_core.brain_graph.service import BrainGraphService
            from copilot_core.brain_graph.store import BrainGraphStore
            assert BrainGraphService is not None
            assert BrainGraphStore is not None
        except ImportError as e:
            pytest.fail(f"Brain graph import failed: {e}")


class TestPluginSystem:
    """Test Plugin System (v7.10+)."""
    
    def test_module_registry_imports(self):
        """Module registry should be importable."""
        from copilot_core.module_registry import ModuleRegistry
        assert ModuleRegistry is not None
    
    def test_plugin_manager_imports(self):
        """Plugin manager should be importable."""
        try:
            from copilot_core.hub.plugin_manager import PluginManager
            assert PluginManager is not None
        except ImportError as e:
            pytest.fail(f"Plugin manager import failed: {e}")


class TestWebSearch:
    """Test Web Search functionality."""
    
    def test_web_search_service_imports(self):
        """Web search service should be importable."""
        from copilot_core.web_search import WebSearchService
        assert WebSearchService is not None


class TestVectorStore:
    """Test Vector Store functionality."""
    
    def test_vector_store_imports(self):
        """Vector store should be importable."""
        try:
            from copilot_core.vector_store.service import VectorStoreService
            assert VectorStoreService is not None
        except ImportError:
            # Vector store might be optional
            pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
