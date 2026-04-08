"""Tests for Collective Intelligence Workflow - Phase 5 Federated Learning.

Tests the service layer directly without requiring Flask.
"""

import pytest
import tempfile
import os

try:
    from copilot_core.collective_intelligence.service import (
        CollectiveIntelligenceService,
        CIStatus
    )
    SERVICE_AVAILABLE = True
except ModuleNotFoundError:
    SERVICE_AVAILABLE = False
    CollectiveIntelligenceService = None

# Try to import Flask components
try:
    from copilot_core.app import create_app
    from copilot_core.collective_intelligence.api import (
        federated_bp,
        init_federated_api
    )
    FLASK_AVAILABLE = True
except ModuleNotFoundError:
    FLASK_AVAILABLE = False
    create_app = None
    federated_bp = None


@pytest.fixture
def ci_service():
    """Create a fresh Collective Intelligence service."""
    if not SERVICE_AVAILABLE:
        pytest.skip("Collective Intelligence module not available")
    return CollectiveIntelligenceService()


@pytest.fixture
def app_with_federated(ci_service):
    """Create test app with federated learning API initialized."""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask not installed")
    
    app = create_app()
    if federated_bp:
        app.register_blueprint(federated_bp)
        init_federated_api(ci_service)
    return app


# ═══════════════════════════════════════════════════════════════════════════
# Service Initialization
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="CI Service not available")
class TestServiceInitialization:
    """Test service initialization and lifecycle."""
    
    def test_service_starts_inactive(self, ci_service):
        """Test that service starts in inactive state."""
        assert ci_service.is_active is False
        status = ci_service.get_status()
        assert status.is_active is False
    
    def test_service_start(self, ci_service):
        """Test starting the service."""
        ci_service.start()
        assert ci_service.is_active is True
        status = ci_service.get_status()
        assert status.is_active is True
    
    def test_service_stop(self, ci_service):
        """Test stopping the service."""
        ci_service.start()
        ci_service.stop()
        assert ci_service.is_active is False
        status = ci_service.get_status()
        assert status.is_active is False
    
    def test_status_to_dict(self, ci_service):
        """Test CIStatus conversion to dictionary."""
        ci_service.start()
        status = ci_service.get_status()
        status_dict = status.to_dict()
        
        assert "is_active" in status_dict
        assert "active_rounds" in status_dict
        assert "completed_rounds" in status_dict
        assert "total_updates" in status_dict
        assert "participating_nodes" in status_dict
        assert "aggregated_models" in status_dict
        assert "privacy_epsilon_used" in status_dict
        assert "knowledge_transferred" in status_dict


# ═══════════════════════════════════════════════════════════════════════════
# Node Registration
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="CI Service not available")
class TestNodeRegistration:
    """Test node registration for federated learning."""
    
    def test_register_node_inactive_service(self, ci_service):
        """Test node registration fails when service is inactive."""
        result = ci_service.register_node("node-1", max_epsilon=1.0)
        assert result is False
    
    def test_register_node_active_service(self, ci_service):
        """Test successful node registration."""
        ci_service.start()
        result = ci_service.register_node("node-1", max_epsilon=1.0)
        assert result is True
        
        status = ci_service.get_status()
        assert status.participating_nodes == 1
    
    def test_register_multiple_nodes(self, ci_service):
        """Test registering multiple nodes."""
        ci_service.start()
        ci_service.register_node("node-1", max_epsilon=1.0)
        ci_service.register_node("node-2", max_epsilon=0.5)
        ci_service.register_node("node-3", max_epsilon=2.0)
        
        status = ci_service.get_status()
        assert status.participating_nodes == 3


# ═══════════════════════════════════════════════════════════════════════════
# Model Updates
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="CI Service not available")
class TestModelUpdates:
    """Test submitting local model updates."""
    
    def test_submit_update_inactive_service(self, ci_service):
        """Test update submission fails when service is inactive."""
        weights = {"layer1": [0.1, 0.2], "layer2": [0.3, 0.4]}
        result = ci_service.submit_local_update("node-1", weights)
        assert result is None
    
    def test_submit_update_active_service(self, ci_service):
        """Test successful update submission."""
        ci_service.start()
        ci_service.register_node("node-1")
        
        weights = {"layer1": [0.1, 0.2], "layer2": [0.3, 0.4]}
        metrics = {"accuracy": 0.95, "loss": 0.05}
        
        update = ci_service.submit_local_update("node-1", weights, metrics)
        assert update is not None
        assert update.node_id == "node-1"
        
        status = ci_service.get_status()
        assert status.total_updates == 1


# ═══════════════════════════════════════════════════════════════════════════
# Federated Rounds
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="CI Service not available")
class TestFederatedRounds:
    """Test federated learning round management."""
    
    def test_start_round_inactive_service(self, ci_service):
        """Test round start fails when service is inactive."""
        round_id = ci_service.start_federated_round()
        assert round_id == ""
    
    def test_start_round_active_service(self, ci_service):
        """Test successful round start."""
        ci_service.start()
        round_id = ci_service.start_federated_round()
        
        assert round_id != ""
        assert len(round_id) == 16  # SHA256 hex hash truncated to 16 chars
        
        status = ci_service.get_status()
        assert status.active_rounds == 1
    
    def test_execute_aggregation(self, ci_service):
        """Test successful aggregation execution."""
        ci_service.start()
        
        # Start round first
        round_id = ci_service.start_federated_round()
        
        # Register nodes and submit updates (they go to the latest active round)
        ci_service.register_node("node-1")
        ci_service.register_node("node-2")
        
        ci_service.submit_local_update("node-1", {"layer1": [0.1, 0.2]})
        ci_service.submit_local_update("node-2", {"layer1": [0.3, 0.4]})
        
        # Execute aggregation
        aggregated = ci_service.execute_aggregation(round_id)
        
        assert aggregated is not None
        assert aggregated.model_version is not None
        
        status = ci_service.get_status()
        assert status.completed_rounds == 1
        assert status.active_rounds == 0
        assert status.aggregated_models >= 1
    
    def test_round_history(self, ci_service):
        """Test getting round history."""
        ci_service.start()
        
        # Start and complete rounds to add them to history
        # Need 2 nodes to meet min_participants requirement
        ci_service.register_node("node-1")
        ci_service.register_node("node-2")
        
        round_id1 = ci_service.start_federated_round()
        ci_service.submit_local_update("node-1", {"layer1": [0.1, 0.2]})
        ci_service.submit_local_update("node-2", {"layer1": [0.3, 0.4]})
        ci_service.execute_aggregation(round_id1)
        
        round_id2 = ci_service.start_federated_round()
        ci_service.submit_local_update("node-1", {"layer1": [0.5, 0.6]})
        ci_service.submit_local_update("node-2", {"layer1": [0.7, 0.8]})
        ci_service.execute_aggregation(round_id2)
        
        history = ci_service.get_federated_round_history()
        assert len(history) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Knowledge Transfer
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="CI Service not available")
class TestKnowledgeTransfer:
    """Test knowledge extraction and transfer."""
    
    def test_extract_knowledge_inactive_service(self, ci_service):
        """Test knowledge extraction fails when service is inactive."""
        result = ci_service.extract_knowledge(
            "node-1",
            "automation_pattern",
            {"pattern": "morning_routine"},
            confidence=0.9
        )
        assert result is None
    
    def test_extract_knowledge(self, ci_service):
        """Test successful knowledge extraction."""
        ci_service.start()
        
        payload = {
            "pattern_type": "automation",
            "entities": ["light.living_room", "sensor.motion"],
            "trigger": "motion_detected",
            "action": "turn_on_light"
        }
        
        item = ci_service.extract_knowledge(
            "node-1",
            "automation_pattern",
            payload,
            confidence=0.85
        )
        
        assert item is not None
        assert item.knowledge_id is not None
        assert item.knowledge_hash is not None
        assert item.source_node_id == "node-1"
    
    def test_transfer_knowledge(self, ci_service):
        """Test successful knowledge transfer."""
        ci_service.start()
        
        # Extract knowledge first
        item = ci_service.extract_knowledge(
            "node-1",
            "energy_pattern",
            {"type": "peak_hours", "hours": [18, 19, 20]},
            confidence=0.9
        )
        
        # Transfer to another node
        success = ci_service.transfer_knowledge(item.knowledge_id, "node-2")
        assert success is True
        
        status = ci_service.get_status()
        assert status.knowledge_transferred == 1
    
    def test_get_knowledge_base(self, ci_service):
        """Test getting knowledge base."""
        ci_service.start()
        
        ci_service.extract_knowledge("node-1", "type1", {"data": "a"})
        ci_service.extract_knowledge("node-2", "type2", {"data": "b"})
        
        knowledge_base = ci_service.get_knowledge_base()
        assert len(knowledge_base) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Statistics and State
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not SERVICE_AVAILABLE, reason="CI Service not available")
class TestStatisticsAndState:
    """Test statistics and state persistence."""
    
    def test_get_statistics(self, ci_service):
        """Test getting comprehensive statistics."""
        ci_service.start()
        ci_service.register_node("node-1")
        ci_service.submit_local_update("node-1", {"layer1": [0.1]})
        ci_service.extract_knowledge("node-1", "test", {"data": "test"})
        
        stats = ci_service.get_statistics()
        
        assert "status" in stats
        assert "federated_rounds" in stats
        assert "aggregated_models" in stats
        assert "knowledge_base_size" in stats
    
    def test_save_state(self, ci_service):
        """Test saving system state to file."""
        ci_service.start()
        ci_service.register_node("node-1")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "ci_state.json")
            success = ci_service.save_state(state_path)
            assert success is True
            assert os.path.exists(state_path)
    
    def test_load_state(self, ci_service):
        """Test loading system state from file."""
        ci_service.start()
        ci_service.register_node("node-1")
        ci_service.start_federated_round()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "ci_state.json")
            
            # Save state
            ci_service.save_state(state_path)
            
            # Create new service and load
            ci_service2 = CollectiveIntelligenceService()
            success = ci_service2.load_state(state_path)
            assert success is True
    
    def test_aggregated_models(self, ci_service):
        """Test getting aggregated models."""
        ci_service.start()
        
        # Run a full round to create aggregated model
        round_id = ci_service.start_federated_round()
        ci_service.register_node("node-1")
        ci_service.register_node("node-2")
        ci_service.submit_local_update("node-1", {"layer1": [0.1, 0.2]})
        ci_service.submit_local_update("node-2", {"layer1": [0.3, 0.4]})
        ci_service.execute_aggregation(round_id)
        
        models = ci_service.get_aggregated_models()
        assert len(models) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# API Endpoints (Flask Required)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestFederatedAPIEndpoints:
    """Test federated learning API endpoints."""
    
    def test_get_status_endpoint(self, app_with_federated, ci_service):
        """Test GET /api/v1/federated status endpoint."""
        ci_service.start()
        ci_service.register_node("node-1")
        
        client = app_with_federated.test_client()
        r = client.get("/api/v1/federated")
        assert r.status_code == 200
        j = r.get_json()
        assert j["is_active"] is True
        assert j["participating_nodes"] == 1
    
    def test_start_service_endpoint(self, app_with_federated):
        """Test POST /api/v1/federated/start."""
        client = app_with_federated.test_client()
        r = client.post("/api/v1/federated/start")
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
    
    def test_stop_service_endpoint(self, app_with_federated, ci_service):
        """Test POST /api/v1/federated/stop."""
        ci_service.start()
        
        client = app_with_federated.test_client()
        r = client.post("/api/v1/federated/stop")
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True
    
    def test_get_statistics_endpoint(self, app_with_federated, ci_service):
        """Test GET /api/v1/federated/statistics."""
        ci_service.start()
        
        client = app_with_federated.test_client()
        r = client.get("/api/v1/federated/statistics")
        assert r.status_code == 200
        j = r.get_json()
        assert "status" in j


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
