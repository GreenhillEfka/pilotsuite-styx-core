"""Tests for Neuron Configuration and Synapse API endpoints (Iteration 2).

Tests:
  - PATCH /neurons/<id>/config  (update neuron parameters)
  - POST  /neurons/<id>/enable  (enable neuron)
  - POST  /neurons/<id>/disable (disable neuron)
  - POST  /neurons/batch-configure (bulk config)
  - GET   /api/v1/neurons/layers/synapses (list)
  - POST  /api/v1/neurons/layers/synapses/update (edit weight)
  - POST  /api/v1/neurons/layers/synapses/reset (reset)
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


def _make_neuron_app():
    """Create a Flask app with the neurons blueprint and auth bypassed."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    from copilot_core.api.v1.neurons import bp
    app.register_blueprint(bp)
    return app


def _make_synapse_app():
    """Create a Flask app with the neuron_layers blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    from copilot_core.api.v1.neuron_layers import neuron_layers_bp
    app.register_blueprint(neuron_layers_bp)
    return app


@pytest.fixture
def mock_neuron():
    """Create a mock neuron with config."""
    from copilot_core.neurons.base import NeuronConfig, NeuronType
    config = NeuronConfig(
        name="presence",
        neuron_type=NeuronType.CONTEXT,
        threshold=0.5,
        decay_rate=0.1,
        smoothing_factor=0.3,
        enabled=True,
    )
    neuron = MagicMock()
    neuron.config = config
    neuron.to_dict.return_value = {"name": "presence", "config": config.to_dict()}
    return neuron


@pytest.fixture
def mock_manager(mock_neuron):
    """Mock NeuronManager."""
    manager = MagicMock()
    manager.get_neuron.return_value = mock_neuron
    manager.get_all_neurons.return_value = {"context.presence": mock_neuron}
    return manager


@pytest.fixture
def neuron_client(mock_manager):
    """Flask test client for neuron endpoints."""
    with patch("copilot_core.api.v1.neurons._validate_token", return_value=True):
        with patch("copilot_core.api.v1.neurons.get_neuron_manager", return_value=mock_manager):
            app = _make_neuron_app()
            with app.test_client() as c:
                yield c


# ── Neuron Config PATCH Tests ────────────────────────────────────────

class TestNeuronConfigPatch:
    def test_patch_threshold(self, neuron_client, mock_neuron):
        resp = neuron_client.patch(
            "/neurons/context.presence/config",
            json={"threshold": 0.7},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert "threshold" in data["data"]["changed"]
        assert mock_neuron.config.threshold == 0.7

    def test_patch_decay_rate(self, neuron_client, mock_neuron):
        resp = neuron_client.patch(
            "/neurons/context.presence/config",
            json={"decay_rate": 0.2},
        )
        assert resp.status_code == 200
        assert mock_neuron.config.decay_rate == 0.2

    def test_patch_smoothing_factor(self, neuron_client, mock_neuron):
        resp = neuron_client.patch(
            "/neurons/context.presence/config",
            json={"smoothing_factor": 0.5},
        )
        assert resp.status_code == 200
        assert mock_neuron.config.smoothing_factor == 0.5

    def test_patch_weights(self, neuron_client, mock_neuron):
        resp = neuron_client.patch(
            "/neurons/context.presence/config",
            json={"weights": {"energy": 0.8}},
        )
        assert resp.status_code == 200
        assert mock_neuron.config.weights["energy"] == 0.8

    def test_patch_enabled(self, neuron_client, mock_neuron):
        resp = neuron_client.patch(
            "/neurons/context.presence/config",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert mock_neuron.config.enabled is False

    def test_patch_invalid_threshold(self, neuron_client):
        resp = neuron_client.patch(
            "/neurons/context.presence/config",
            json={"threshold": 1.5},
        )
        assert resp.status_code == 400

    def test_patch_invalid_id(self, neuron_client):
        resp = neuron_client.patch(
            "/neurons/INVALID_ID/config",
            json={"threshold": 0.5},
        )
        assert resp.status_code == 400

    def test_patch_empty_body(self, neuron_client):
        resp = neuron_client.patch(
            "/neurons/context.presence/config",
            json={},
        )
        assert resp.status_code == 400

    def test_patch_not_found(self, neuron_client, mock_manager):
        mock_manager.get_neuron.return_value = None
        resp = neuron_client.patch(
            "/neurons/context.missing/config",
            json={"threshold": 0.5},
        )
        assert resp.status_code == 404


# ── Enable/Disable Tests ─────────────────────────────────────────────

class TestNeuronEnableDisable:
    def test_enable(self, neuron_client, mock_neuron):
        mock_neuron.config.enabled = False
        resp = neuron_client.post("/neurons/context.presence/enable")
        assert resp.status_code == 200
        assert mock_neuron.config.enabled is True

    def test_disable(self, neuron_client, mock_neuron):
        resp = neuron_client.post("/neurons/context.presence/disable")
        assert resp.status_code == 200
        assert mock_neuron.config.enabled is False

    def test_enable_not_found(self, neuron_client, mock_manager):
        mock_manager.get_neuron.return_value = None
        resp = neuron_client.post("/neurons/context.nope/enable")
        assert resp.status_code == 404


# ── Batch Configure Tests ────────────────────────────────────────────

class TestBatchConfigure:
    def test_batch_configure(self, neuron_client, mock_neuron):
        resp = neuron_client.post(
            "/neurons/batch-configure",
            json={"neurons": {"context.presence": {"threshold": 0.8}}},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "context.presence" in data["data"]["updated"]

    def test_batch_empty(self, neuron_client):
        resp = neuron_client.post("/neurons/batch-configure", json={})
        assert resp.status_code == 400


# ── Synapse API Tests ────────────────────────────────────────────────

@pytest.fixture
def synapse_client():
    """Flask test client for synapse endpoints."""
    # Synapse endpoints don't have auth (they inherit from neuron_layers_bp)
    app = _make_synapse_app()
    with app.test_client() as c:
        yield c


class TestSynapseList:
    def test_list_synapses(self, synapse_client):
        resp = synapse_client.get("/api/v1/neurons/layers/synapses")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert data["count"] > 0
        assert len(data["data"]) > 0
        # Check structure
        s = data["data"][0]
        assert "from" in s
        assert "to" in s
        assert "weight" in s
        assert "default_weight" in s
        assert "overridden" in s


class TestSynapseUpdate:
    def test_update_weight(self, synapse_client):
        resp = synapse_client.post(
            "/api/v1/neurons/layers/synapses/update",
            json={"from": "context.presence", "to": "state.energy_level", "weight": 0.5},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert data["data"]["weight"] == 0.5

    def test_update_invalid_range(self, synapse_client):
        resp = synapse_client.post(
            "/api/v1/neurons/layers/synapses/update",
            json={"from": "context.presence", "to": "state.energy_level", "weight": 5.0},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_update_missing_fields(self, synapse_client):
        resp = synapse_client.post(
            "/api/v1/neurons/layers/synapses/update",
            json={"from": "context.presence"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_update_nonexistent_synapse(self, synapse_client):
        resp = synapse_client.post(
            "/api/v1/neurons/layers/synapses/update",
            json={"from": "x.y", "to": "a.b", "weight": 0.1},
            content_type="application/json",
        )
        assert resp.status_code == 404


class TestSynapseReset:
    def test_reset_single(self, synapse_client):
        # First set an override
        synapse_client.post(
            "/api/v1/neurons/layers/synapses/update",
            json={"from": "context.presence", "to": "state.energy_level", "weight": 0.9},
            content_type="application/json",
        )
        # Then reset it
        resp = synapse_client.post(
            "/api/v1/neurons/layers/synapses/reset",
            json={"from": "context.presence", "to": "state.energy_level"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["data"]["reset"] is True

    def test_reset_all(self, synapse_client):
        resp = synapse_client.post(
            "/api/v1/neurons/layers/synapses/reset",
            json={"all": True},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True

    def test_reset_missing_fields(self, synapse_client):
        resp = synapse_client.post(
            "/api/v1/neurons/layers/synapses/reset",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400


# ── NeuronManager Persistence Tests ──────────────────────────────────

class TestNeuronConfigPersistence:
    def test_persist_and_load(self, tmp_path):
        """Test that neuron configs can be persisted and loaded."""
        from copilot_core.neurons.manager import NeuronManager
        import os

        config_path = str(tmp_path / "neuron_configs.json")
        os.environ["NEURON_CONFIG_PATH"] = config_path

        try:
            manager = NeuronManager()
            # configure_from_ha creates default neurons
            manager.configure_from_ha({})

            # Modify a config
            neuron = manager.get_neuron("presence")
            if neuron:
                neuron.config.threshold = 0.8
                manager.persist_all_neuron_configs()

                # Verify file was created
                assert os.path.exists(config_path)

                # Load into a fresh manager
                manager2 = NeuronManager()
                manager2.configure_from_ha({})
                manager2.load_neuron_configs()

                neuron2 = manager2.get_neuron("presence")
                if neuron2:
                    assert neuron2.config.threshold == 0.8
        finally:
            os.environ.pop("NEURON_CONFIG_PATH", None)
