"""Flask Integration Tests for Collective Intelligence (Federated Learning) API.

Tests the Flask blueprint endpoints for federated learning operations.
Requires Flask to be installed.
"""

import pytest
from unittest.mock import MagicMock, Mock

try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None

# Import federated learning components
try:
    from copilot_core.collective_intelligence.api import (
        federated_bp,
        init_federated_api,
        _get_service,
    )
    FEDERATED_AVAILABLE = True
except ImportError:
    FEDERATED_AVAILABLE = False
    federated_bp = None


@pytest.fixture
def mock_service():
    """Create a mock federated learning service."""
    service = MagicMock()
    
    # Mock status object
    status_mock = MagicMock()
    status_mock.to_dict.return_value = {
        'state': 'active',
        'nodes': 2,
        'rounds_completed': 5
    }
    service.get_status.return_value = status_mock
    
    # Mock round object
    round_mock = MagicMock()
    round_mock.round_id = 'round-test-123'
    round_mock.to_dict.return_value = {
        'round_id': 'round-test-123',
        'participants': 2,
        'metrics': {'accuracy': 0.95}
    }
    service.start_federated_round.return_value = 'round-test-123'
    
    # Mock aggregation result
    agg_mock = MagicMock()
    agg_mock.model_version = 'v1.0'
    agg_mock.participants = 2
    agg_mock.metrics = {'accuracy': 0.95}
    agg_mock.privacy_loss = 0.1
    service.execute_aggregation.return_value = agg_mock
    
    # Mock knowledge item
    knowledge_mock = MagicMock()
    knowledge_mock.knowledge_id = 'know-123'
    knowledge_mock.knowledge_hash = 'abc123hash'
    knowledge_mock.to_dict.return_value = {
        'knowledge_id': 'know-123',
        'knowledge_hash': 'abc123hash',
        'knowledge_type': 'pattern',
        'confidence': 0.95
    }
    service.extract_knowledge.return_value = knowledge_mock
    
    # Mock update object (for submit_local_update)
    update_mock = MagicMock()
    update_mock.update_id = 'update-test-456'
    update_mock.timestamp = '2024-01-01T00:00:00Z'
    service.submit_local_update.return_value = update_mock
    
    # Mock other methods
    service.register_node.return_value = True
    service.transfer_knowledge.return_value = True
    service.get_federated_round_history.return_value = [round_mock, round_mock]
    service.get_aggregated_models.return_value = {'v1.0': round_mock}
    # get_knowledge_base returns dict {id: knowledge_obj}, API converts to list
    knowledge_dict = {'know-123': knowledge_mock}
    service.get_knowledge_base.return_value = knowledge_dict
    service.get_statistics.return_value = {'total_rounds': 5, 'total_nodes': 2}
    service.save_state.return_value = True
    service.load_state.return_value = True
    
    return service


@pytest.fixture
def test_app(mock_service, isolated_blueprint_test):
    """Create test Flask app with federated blueprint.
    
    Uses isolated_blueprint_test fixture to ensure blueprint registry
    is reset before and after this test, preventing conflicts with
    other tests that may register the same blueprint.
    """
    if not FLASK_AVAILABLE:
        pytest.skip("Flask not installed")
    if not FEDERATED_AVAILABLE:
        pytest.skip("Federated module not available")
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(federated_bp, url_prefix="/api/v1")
    
    # Initialize with mock service
    init_federated_api(mock_service)
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return test_app.test_client()


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
@pytest.mark.skipif(not FEDERATED_AVAILABLE, reason="Federated module not available")
class TestFederatedFlaskIntegration:
    """Test Flask integration for federated learning API."""
    
    def test_get_status(self, client, mock_service):
        """Test getting federated learning status."""
        response = client.get('/api/v1/federated')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['state'] == 'active'
        assert data['nodes'] == 2
        mock_service.get_status.assert_called_once()
    
    def test_start_service(self, client, mock_service):
        """Test starting the federated service."""
        response = client.post('/api/v1/federated/start')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['message'] == 'Federated service started'
        mock_service.start.assert_called_once()
    
    def test_stop_service(self, client, mock_service):
        """Test stopping the federated service."""
        response = client.post('/api/v1/federated/stop')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['message'] == 'Federated service stopped'
        mock_service.stop.assert_called_once()
    
    def test_register_node(self, client, mock_service):
        """Test registering a new node."""
        response = client.post('/api/v1/federated/register', json={
            'node_id': 'home-node-1',
            'max_epsilon': 0.5
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['node_id'] == 'home-node-1'
        mock_service.register_node.assert_called_once_with('home-node-1', 0.5)
    
    def test_register_node_missing_id(self, client, mock_service):
        """Test registering node without node_id fails."""
        response = client.post('/api/v1/federated/register', json={
            'max_epsilon': 0.5
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'node_id required'
    
    def test_submit_update(self, client, mock_service):
        """Test submitting a model update."""
        response = client.post('/api/v1/federated/update', json={
            'node_id': 'home-node-1',
            'weights': {'layer1': [0.1, 0.2, 0.3]},
            'metrics': {'loss': 0.05}
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert 'update_id' in data
        mock_service.submit_local_update.assert_called_once()
    
    def test_submit_update_missing_fields(self, client, mock_service):
        """Test submitting update without required fields fails."""
        response = client.post('/api/v1/federated/update', json={
            'node_id': 'home-node-1'
            # Missing weights
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'node_id and weights required'
    
    def test_start_round(self, client, mock_service):
        """Test starting a federated learning round."""
        response = client.post('/api/v1/federated/round')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['round_id'] == 'round-test-123'
        mock_service.start_federated_round.assert_called_once()
    
    def test_execute_aggregation(self, client, mock_service):
        """Test executing aggregation for a round."""
        response = client.post('/api/v1/federated/aggregate', json={
            'round_id': 'round-test-123'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['model_version'] == 'v1.0'
        assert data['participants'] == 2
        mock_service.execute_aggregation.assert_called_once_with('round-test-123')
    
    def test_execute_aggregation_missing_round_id(self, client, mock_service):
        """Test aggregation without round_id fails."""
        response = client.post('/api/v1/federated/aggregate', json={})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'round_id required'
    
    def test_extract_knowledge(self, client, mock_service):
        """Test extracting knowledge from a node."""
        response = client.post('/api/v1/federated/knowledge', json={
            'node_id': 'home-node-1',
            'knowledge_type': 'pattern',
            'payload': {'data': [1, 2, 3]},
            'confidence': 0.9
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert 'knowledge_id' in data
        mock_service.extract_knowledge.assert_called_once()
    
    def test_extract_knowledge_missing_fields(self, client, mock_service):
        """Test knowledge extraction without required fields fails."""
        response = client.post('/api/v1/federated/knowledge', json={
            'node_id': 'home-node-1'
            # Missing knowledge_type and payload
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'node_id, knowledge_type, and payload required'
    
    def test_transfer_knowledge(self, client, mock_service):
        """Test transferring knowledge to another node."""
        response = client.post('/api/v1/federated/knowledge/know-123/transfer', json={
            'target_node_id': 'home-node-2'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['knowledge_id'] == 'know-123'
        assert data['target_node_id'] == 'home-node-2'
    
    def test_transfer_knowledge_missing_target(self, client, mock_service):
        """Test knowledge transfer without target_node_id fails."""
        response = client.post('/api/v1/federated/knowledge/know-123/transfer', json={})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'target_node_id required'
    
    def test_get_round_history(self, client, mock_service):
        """Test getting round history."""
        response = client.get('/api/v1/federated/rounds')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 2
        assert 'rounds' in data
        mock_service.get_federated_round_history.assert_called_once()
    
    def test_get_aggregated_models(self, client, mock_service):
        """Test getting aggregated models."""
        response = client.get('/api/v1/federated/models')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 1
        assert 'models' in data
        mock_service.get_aggregated_models.assert_called_once()
    
    def test_get_knowledge_base(self, client, mock_service):
        """Test getting knowledge base."""
        response = client.get('/api/v1/federated/knowledge-base')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 1
        assert 'items' in data
        mock_service.get_knowledge_base.assert_called_once()
    
    def test_get_statistics(self, client, mock_service):
        """Test getting statistics."""
        response = client.get('/api/v1/federated/statistics')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['total_rounds'] == 5
        assert data['total_nodes'] == 2
        mock_service.get_statistics.assert_called_once()
    
    def test_save_state(self, client, mock_service):
        """Test saving state to file."""
        response = client.post('/api/v1/federated/save', json={
            'path': '/tmp/test_state.json'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['path'] == '/tmp/test_state.json'
        mock_service.save_state.assert_called_once_with('/tmp/test_state.json')
    
    def test_save_state_default_path(self, client, mock_service):
        """Test saving state with default path."""
        response = client.post('/api/v1/federated/save', json={})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['path'] == '/config/.copilot/federated_state.json'
    
    def test_load_state(self, client, mock_service):
        """Test loading state from file."""
        response = client.post('/api/v1/federated/load', json={
            'path': '/tmp/test_state.json'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert data['path'] == '/tmp/test_state.json'
        mock_service.load_state.assert_called_once_with('/tmp/test_state.json')
    
    def test_service_not_initialized(self):
        """Test endpoints when service is not initialized."""
        if not FLASK_AVAILABLE:
            pytest.skip("Flask not installed")
        if not FEDERATED_AVAILABLE:
            pytest.skip("Federated module not available")
        
        # Create a fresh app without initializing the service
        init_federated_api(None)  # Clear any existing service
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(federated_bp, url_prefix="/api/v1")
        
        client = app.test_client()
        response = client.get('/api/v1/federated')
        
        assert response.status_code == 503
        data = response.get_json()
        assert data['error'] == 'Federated service not initialized'


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
@pytest.mark.skipif(not FEDERATED_AVAILABLE, reason="Federated module not available")
class TestFederatedErrorCases:
    """Test error cases for federated learning API."""
    
    def test_503_service_not_initialized_all_endpoints(self, mock_service):
        """Test 503 when service is not initialized on various endpoints."""
        init_federated_api(None)  # Clear service
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(federated_bp, url_prefix="/api/v1")
        client = app.test_client()
        
        # Test GET /api/v1/federated
        response = client.get('/api/v1/federated')
        assert response.status_code == 503
        assert response.get_json()['error'] == 'Federated service not initialized'
        
        # Test POST /api/v1/federated/start
        response = client.post('/api/v1/federated/start')
        assert response.status_code == 503
        
        # Test POST /api/v1/federated/stop
        response = client.post('/api/v1/federated/stop')
        assert response.status_code == 503
        
        # Test POST /api/v1/federated/register
        response = client.post('/api/v1/federated/register', json={'node_id': 'test'})
        assert response.status_code == 503
        
        # Restore service
        init_federated_api(mock_service)
    
    def test_400_register_missing_node_id(self, client, mock_service):
        """Test 400 when registering node without node_id."""
        response = client.post('/api/v1/federated/register', json={
            'max_epsilon': 0.5
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'node_id required'
    
    def test_400_submit_update_missing_fields(self, client, mock_service):
        """Test 400 when submitting update without required fields."""
        # Missing weights
        response = client.post('/api/v1/federated/update', json={
            'node_id': 'home-node-1'
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'node_id and weights required'
        
        # Missing node_id
        response = client.post('/api/v1/federated/update', json={
            'weights': {'layer1': [0.1, 0.2]}
        })
        
        assert response.status_code == 400
    
    def test_400_aggregate_missing_round_id(self, client, mock_service):
        """Test 400 when aggregating without round_id."""
        response = client.post('/api/v1/federated/aggregate', json={})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'round_id required'
    
    def test_400_extract_knowledge_missing_fields(self, client, mock_service):
        """Test 400 when extracting knowledge without required fields."""
        response = client.post('/api/v1/federated/knowledge', json={
            'node_id': 'home-node-1'
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'node_id, knowledge_type, and payload required'
    
    def test_400_transfer_knowledge_missing_target(self, client, mock_service):
        """Test 400 when transferring knowledge without target_node_id."""
        response = client.post('/api/v1/federated/knowledge/know-123/transfer', json={})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'target_node_id required'
    
    def test_500_save_state_failure(self, client, mock_service):
        """Test 500 when save_state fails."""
        # Mock service to simulate failure
        def raise_exception(*args, **kwargs):
            raise Exception("Save failed")
        
        mock_service.save_state.side_effect = raise_exception
        
        response = client.post('/api/v1/federated/save', json={
            'path': '/tmp/state.json'
        })
        
        assert response.status_code == 500
        
        # Reset mock
        mock_service.save_state.side_effect = None
        mock_service.save_state.return_value = True
    
    def test_401_auth_failure_with_env_required(self, client, mock_service, monkeypatch):
        """Test 401 authentication failure when auth is required and token is invalid."""
        # Force auth to be required
        monkeypatch.setenv('COPILOT_AUTH_REQUIRED', 'true')
        monkeypatch.setenv('COPILOT_AUTH_TOKEN', 'test-secret-token')
        
        # Make request without valid token
        response = client.get('/api/v1/federated')
        
        # Should get 401 because no valid token is provided
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data or 'message' in data
    
    def test_405_method_not_allowed(self, client, mock_service):
        """Test 405 method not allowed."""
        # GET on POST-only endpoint
        response = client.get('/api/v1/federated/start')
        assert response.status_code == 405
    
    def test_415_unsupported_media_type(self, client, mock_service):
        """Test 415 unsupported media type."""
        response = client.post('/api/v1/federated/register',
                              data='node_id=test',
                              content_type='application/x-www-form-urlencoded')
        
        # Flask may return 400 or 415 depending on configuration
        assert response.status_code in [400, 415]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
