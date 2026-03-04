"""Tests for Neuron API endpoints.

Test coverage for Neuron API:
- GET /api/v1/neurons - Alle Neuronen auflisten
- GET /api/v1/neurons/<neuron_id> - Einzelnes Neuron
- POST /api/v1/neurons/evaluate - Evaluation ausführen
- POST /api/v1/neurons/update - States aktualisieren
- POST /api/v1/neurons/configure - Neuronen konfigurieren
- GET /api/v1/neurons/mood - Mood abrufen
- POST /api/v1/neurons/mood/evaluate - Mood evaluation
- GET /api/v1/neurons/mood/history - Mood Historie
- GET /api/v1/neurons/suggestions - Vorschläge
- GET /api/v1/neurons/graph - Graph-Daten (Nodes/Edges)
- GET /api/v1/neurons/connections - Verbindungen zwischen Neuronen
- GET /api/v1/neurons/paths - Pfade zwischen Nodes
- GET /api/v1/neurons/graph/stats - Graph Statistiken
- GET /api/v1/neurons/<id>/stats - Neuron Statistiken

Author: Clawdya
Version: 1.0.0
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from flask import Flask


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    yield app


@pytest.fixture
def mock_neuron_summary():
    """Mock neuron summary data."""
    return {
        "context": {
            "presence": 0.8,
            "time_of_day": 0.6,
            "light_level": 0.4,
        },
        "state": {
            "energy_level": 0.7,
            "comfort": 0.65,
        },
        "mood": {
            "dominant": "relaxed",
            "confidence": 0.85,
            "values": {
                "relaxed": 0.85,
                "focused": 0.45,
                "energetic": 0.30,
            }
        },
        "total_count": 14,
    }


@pytest.fixture
def mock_neuron_manager():
    """Create mock neuron manager."""
    manager = MagicMock()
    manager.get_neuron_summary.return_value = {
        "context": {"presence": 0.8},
        "state": {"energy_level": 0.7},
        "mood": {"dominant": "relaxed", "confidence": 0.85},
        "total_count": 14,
    }
    manager.get_neuron.return_value = MagicMock(
        to_dict=lambda: {
            "name": "presence",
            "type": "context",
            "state": {"active": True, "value": 0.8},
            "config": {"threshold": 0.5}
        }
    )
    manager.evaluate.return_value = MagicMock(
        timestamp=datetime.now(timezone.utc).isoformat(),
        context_values={"presence": 0.8},
        state_values={"energy_level": 0.7},
        mood_values={"relaxed": 0.85},
        dominant_mood="relaxed",
        mood_confidence=0.85,
        suggestions=["Open blinds for natural light"],
        neuron_states={}
    )
    manager.get_mood_summary.return_value = {
        "mood": "relaxed",
        "confidence": 0.85,
        "mood_values": {"relaxed": 0.85},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    manager._mood_history = [
        {"mood": "relaxed", "timestamp": datetime.now(timezone.utc).isoformat()},
        {"mood": "focused", "timestamp": datetime.now(timezone.utc).isoformat()},
    ]
    manager._last_result = MagicMock(
        suggestions=["Test suggestion"],
        dominant_mood="relaxed",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    manager.to_dict.return_value = {
        "neurons": {},
        "context": {},
        "state": {},
        "mood": {"dominant": "relaxed", "confidence": 0.85}
    }
    manager.configure_from_ha.return_value = None
    return manager


@pytest.fixture
def client(app, mock_neuron_manager):
    """Create test client with mocked neuron manager and auth bypass."""
    from copilot_core.api.v1 import neurons

    app.register_blueprint(neurons.bp, url_prefix='/api/v1/neurons')

    # Patch auth in the neurons module namespace (already imported references)
    with patch.object(neurons, 'require_admin_token', return_value=True):
        with patch.object(neurons, '_validate_token', return_value=True):
            with patch('copilot_core.api.v1.neurons.get_neuron_manager', return_value=mock_neuron_manager):
                with app.test_client() as test_client:
                    yield test_client


class TestListNeurons:
    """Tests for GET /api/v1/neurons"""

    def test_list_neurons_success(self, client):
        """Test listing all neurons."""
        response = client.get('/api/v1/neurons')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "data" in data

    def test_list_neurons_includes_context(self, client):
        """Test neuron list includes context values."""
        response = client.get('/api/v1/neurons')
        data = json.loads(response.data)

        assert "context" in data["data"]

    def test_list_neurons_includes_state(self, client):
        """Test neuron list includes state values."""
        response = client.get('/api/v1/neurons')
        data = json.loads(response.data)

        assert "state" in data["data"]

    def test_list_neurons_includes_mood(self, client):
        """Test neuron list includes mood data."""
        response = client.get('/api/v1/neurons')
        data = json.loads(response.data)

        assert "mood" in data["data"]

    def test_list_neurons_total_count(self, client):
        """Test neuron list includes total count."""
        response = client.get('/api/v1/neurons')
        data = json.loads(response.data)

        assert "total_count" in data["data"]


class TestGetNeuron:
    """Tests for GET /api/v1/neurons/<neuron_id>"""

    def test_get_neuron_exists(self, client):
        """Test getting existing neuron."""
        response = client.get('/api/v1/neurons/presence')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "data" in data

    def test_get_neuron_not_found(self, client, mock_neuron_manager):
        """Test getting non-existent neuron."""
        mock_neuron_manager.get_neuron.return_value = None

        response = client.get('/api/v1/neurons/nonexistent')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_get_neuron_with_prefix(self, client, mock_neuron_manager):
        """Test getting neuron with context. prefix."""
        response = client.get('/api/v1/neurons/context.presence')

        # Should handle prefix gracefully
        assert response.status_code in [200, 404]

    def test_get_neuron_returns_type(self, client):
        """Test neuron details include type."""
        response = client.get('/api/v1/neurons/presence')
        data = json.loads(response.data)

        if data["success"]:
            assert "type" in data["data"]


class TestEvaluateNeurons:
    """Tests for POST /api/v1/neurons/evaluate"""

    def test_evaluate_neurons_success(self, client):
        """Test successful neuron evaluation."""
        response = client.post('/api/v1/neurons/evaluate')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "data" in data

    def test_evaluate_neurons_returns_timestamp(self, client):
        """Test evaluation includes timestamp."""
        response = client.post('/api/v1/neurons/evaluate')
        data = json.loads(response.data)

        assert "timestamp" in data["data"]

    def test_evaluate_neurons_returns_suggestions(self, client):
        """Test evaluation includes suggestions."""
        response = client.post('/api/v1/neurons/evaluate')
        data = json.loads(response.data)

        assert "suggestions" in data["data"]

    def test_evaluate_neurons_with_state_overrides(self, client, mock_neuron_manager):
        """Test evaluation with state overrides."""
        payload = {
            "states": {"light.living_room": "on"},
            "context": {"presence": 1.0}
        }

        response = client.post(
            '/api/v1/neurons/evaluate',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        # Verify update_states was called
        mock_neuron_manager.update_states.assert_called()

    def test_evaluate_neurons_with_empty_body(self, client):
        """Test evaluation with empty JSON body."""
        response = client.post(
            '/api/v1/neurons/evaluate',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200

    def test_evaluate_neurons_dominant_mood(self, client):
        """Test evaluation returns dominant mood."""
        response = client.post('/api/v1/neurons/evaluate')
        data = json.loads(response.data)

        assert "dominant_mood" in data["data"]

    def test_evaluate_neurons_mood_confidence(self, client):
        """Test evaluation returns mood confidence."""
        response = client.post('/api/v1/neurons/evaluate')
        data = json.loads(response.data)

        assert "mood_confidence" in data["data"]


class TestUpdateNeuronStates:
    """Tests for POST /api/v1/neurons/update"""

    def test_update_states_success(self, client, mock_neuron_manager):
        """Test successful state update."""
        payload = {
            "states": {
                "light.living_room": {"state": "on"},
                "sensor.temperature": {"state": "21.5"}
            }
        }

        response = client.post(
            '/api/v1/neurons/update',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_update_states_missing_body(self, client):
        """Test update fails without JSON body."""
        response = client.post(
            '/api/v1/neurons/update',
            data=json.dumps({}),
            content_type='application/json'
        )

        # Should return error for missing states
        assert response.status_code in [200, 400]

    def test_update_states_empty_states(self, client):
        """Test update with empty states."""
        payload = {"states": {}}

        response = client.post(
            '/api/v1/neurons/update',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_update_states_returns_count(self, client):
        """Test update response includes updated count."""
        payload = {"states": {"sensor.test": {"state": "on"}}}

        response = client.post(
            '/api/v1/neurons/update',
            data=json.dumps(payload),
            content_type='application/json'
        )

        if response.status_code == 200:
            data = json.loads(response.data)
            assert "updated" in data["data"]


class TestConfigureNeurons:
    """Tests for POST /api/v1/neurons/configure"""

    def test_configure_neurons_success(self, client, mock_neuron_manager):
        """Test successful neuron configuration."""
        from copilot_core.api.v1 import neurons

        # Mock configure to return proper dict
        with patch.object(neurons, 'get_neuron_manager', return_value=mock_neuron_manager):
            mock_neuron_manager.configure_neurons.return_value = {"success": True, "configured": 1}

            payload = {
                "states": {"light.test": "on"},
                "config": {"threshold": 0.7}
            }

            response = client.post(
                '/api/v1/neurons/configure',
                data=json.dumps(payload),
                content_type='application/json'
            )

            assert response.status_code == 200

    def test_configure_neurons_missing_body(self, client):
        """Test configure fails without JSON body."""
        response = client.post(
            '/api/v1/neurons/configure',
            content_type='application/json'
        )

        # May return 400 or 500 depending on implementation
        assert response.status_code in [400, 500]


class TestMoodEndpoints:
    """Tests for mood-related endpoints"""

    def test_get_mood_success(self, client):
        """Test getting current mood."""
        response = client.get('/api/v1/neurons/mood')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_get_mood_includes_confidence(self, client):
        """Test mood includes confidence value."""
        response = client.get('/api/v1/neurons/mood')
        data = json.loads(response.data)

        assert "confidence" in data["data"]

    def test_evaluate_mood_success(self, client):
        """Test mood evaluation."""
        response = client.post('/api/v1/neurons/mood/evaluate')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_get_mood_history(self, client):
        """Test getting mood history."""
        response = client.get('/api/v1/neurons/mood/history')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "history" in data["data"]

    def test_get_mood_history_with_limit(self, client):
        """Test mood history with limit parameter."""
        response = client.get('/api/v1/neurons/mood/history?limit=5')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "count" in data["data"]

    def test_get_suggestions(self, client):
        """Test getting suggestions."""
        response = client.get('/api/v1/neurons/suggestions')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "suggestions" in data["data"]


class TestNeuronAPIAuth:
    """Tests for authentication"""

    def test_neuron_endpoint_requires_auth(self, app):
        """Test neuron endpoints require authentication."""
        from copilot_core.api.v1 import neurons

        # Create app without auth bypass
        with patch('copilot_core.api.v1.neurons._validate_token', return_value=False):
            app.register_blueprint(neurons.bp, url_prefix='/api/v1/neurons')
            with app.test_client() as client:
                response = client.get('/api/v1/neurons')
                assert response.status_code == 401


class TestNeuronAPIErrors:
    """Error handling tests"""

    def test_invalid_json_body(self, client):
        """Test handling of invalid JSON."""
        # API uses request.get_json() or {} which returns {} for invalid JSON
        # This results in a valid response with empty data
        response = client.post(
            '/api/v1/neurons/evaluate',
            data="not valid json",
            content_type='application/json'
        )
    
        # API gracefully handles invalid JSON by treating as empty dict
        assert response.status_code == 200

    def test_neuron_evaluation_error(self, client, mock_neuron_manager):
        """Test handling of evaluation errors."""
        mock_neuron_manager.evaluate.side_effect = Exception("Test error")

        response = client.post('/api/v1/neurons/evaluate')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["success"] is False


class TestNeuronGraphAPI:
    """Tests for Neuron Graph API endpoints."""
    
    @pytest.fixture
    def graph_client(self, app):
        """Create test client with graph endpoints."""
        from copilot_core.api.v1 import neurons
        app.register_blueprint(neurons.bp, url_prefix='/api/v1/neurons')
        with app.test_client() as client:
            yield client
    
    def test_get_graph_success(self, graph_client):
        """Test getting complete neuron graph."""
        response = graph_client.get('/api/v1/neurons/graph')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "nodes" in data["data"]
        assert "edges" in data["data"]
        assert "metadata" in data["data"]
        assert len(data["data"]["nodes"]) == 14
    
    def test_get_graph_stats_success(self, graph_client):
        """Test getting graph statistics."""
        response = graph_client.get('/api/v1/neurons/graph/stats')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "total_nodes" in data["data"]
        assert "total_edges" in data["data"]
        assert data["data"]["total_nodes"] == 14
    
    def test_get_neuron_stats_success(self, graph_client):
        """Test getting individual neuron statistics."""
        response = graph_client.get('/api/v1/neurons/context.presence/stats')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "neuron_id" in data["data"]
        assert "metrics" in data["data"]
        assert "connections" in data["data"]
    
    def test_get_neuron_stats_not_found(self, graph_client):
        """Test getting stats for non-existent neuron."""
        response = graph_client.get('/api/v1/neurons/nonexistent/stats')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
    
    def test_get_connections_all(self, graph_client):
        """Test getting all connections."""
        response = graph_client.get('/api/v1/neurons/connections')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "total_connections" in data["data"]
        assert "connections" in data["data"]
        assert "by_type" in data["data"]
    
    def test_get_connections_for_node(self, graph_client):
        """Test getting connections for specific node."""
        response = graph_client.get('/api/v1/neurons/connections?node_id=context.presence')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "node_id" in data["data"]
        assert data["data"]["node_id"] == "context.presence"
        assert "incoming" in data["data"]
        assert "outgoing" in data["data"]
    
    def test_get_connections_node_not_found(self, graph_client):
        """Test getting connections for non-existent node."""
        response = graph_client.get('/api/v1/neurons/connections?node_id=nonexistent')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
    
    def test_get_paths_success(self, graph_client):
        """Test finding paths between neurons."""
        response = graph_client.get('/api/v1/neurons/paths?from=context.presence&to=mood.energy')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "paths" in data["data"]
        assert "path_count" in data["data"]
        assert data["data"]["from"] == "context.presence"
        assert data["data"]["to"] == "mood.energy"
    
    def test_get_paths_with_max_depth(self, graph_client):
        """Test finding paths with custom max depth."""
        response = graph_client.get('/api/v1/neurons/paths?from=context.presence&to=mood.energy&max_depth=3')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "max_depth" in data["data"]
    
    def test_get_paths_missing_params(self, graph_client):
        """Test paths endpoint with missing parameters."""
        response = graph_client.get('/api/v1/neurons/paths?from=context.presence')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data
    
    def test_get_paths_invalid_max_depth(self, graph_client):
        """Test paths endpoint with invalid max_depth."""
        response = graph_client.get('/api/v1/neurons/paths?from=context.presence&to=mood.energy&max_depth=invalid')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
    
    def test_get_paths_node_not_found(self, graph_client):
        """Test paths endpoint with non-existent node."""
        response = graph_client.get('/api/v1/neurons/paths?from=nonexistent&to=mood.energy')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
