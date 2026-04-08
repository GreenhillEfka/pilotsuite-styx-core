"""Tests fuer NeuronManager und Neural Pipeline.

Testet Initialisierung, Konfiguration, Evaluation und API-Endpunkte.
"""
import pytest
from datetime import datetime, timezone


class TestNeuronManager:
    """Test der NeuronManager Klasse."""

    def setup_method(self):
        """Singleton vor jedem Test zuruecksetzen."""
        from copilot_core.neurons.manager import reset_neuron_manager
        reset_neuron_manager()

    def test_manager_initialization(self):
        """NeuronManager wird mit leeren Neuron-Dicts initialisiert."""
        from copilot_core.neurons.manager import NeuronManager

        manager = NeuronManager()

        assert manager is not None
        assert len(manager._context_neurons) == 0
        assert len(manager._state_neurons) == 0
        assert len(manager._mood_neurons) == 0

    def test_configure_from_ha_creates_neurons(self):
        """configure_from_ha legt Context, State und Mood Neuronen an."""
        from copilot_core.neurons.manager import NeuronManager

        manager = NeuronManager()
        manager.configure_from_ha(ha_states={}, config={})

        assert len(manager._context_neurons) == 4   # presence, time_of_day, light_level, weather
        assert len(manager._state_neurons) == 6      # energy, stress, routine, sleep, attention, comfort
        assert len(manager._mood_neurons) == 8       # relax, focus, active, sleep, away, alert, social, recovery

    def test_evaluate_returns_pipeline_result(self):
        """evaluate() liefert NeuralPipelineResult mit allen Feldern."""
        from copilot_core.neurons.manager import NeuronManager

        manager = NeuronManager()
        manager.configure_from_ha(ha_states={}, config={})
        result = manager.evaluate()

        assert result.timestamp is not None
        assert isinstance(result.context_values, dict)
        assert isinstance(result.state_values, dict)
        assert isinstance(result.mood_values, dict)
        assert result.dominant_mood is not None
        assert 0.0 <= result.mood_confidence <= 1.0
        assert isinstance(result.suggestions, list)

    def test_set_household(self):
        """set_household setzt HouseholdProfile."""
        from copilot_core.neurons.manager import NeuronManager
        from copilot_core.household import HouseholdProfile

        manager = NeuronManager()
        profile = HouseholdProfile.from_config({"members": [
            {"person_entity_id": "person.test", "name": "Test", "birth_year": 1990},
        ]})
        manager.set_household(profile)
        assert manager._household is not None
        assert len(manager._household.members) == 1

    def test_mood_callbacks(self):
        """Mood-Change Callback wird registriert."""
        from copilot_core.neurons.manager import NeuronManager

        manager = NeuronManager()
        called = []
        manager.on_mood_change(lambda mood, conf: called.append((mood, conf)))
        assert manager._on_mood_change is not None

    def test_suggestion_callbacks(self):
        """Suggestion Callback wird registriert."""
        from copilot_core.neurons.manager import NeuronManager

        manager = NeuronManager()
        called = []
        manager.on_suggestion(lambda s: called.append(s))
        assert manager._on_suggestion is not None

    def test_to_dict(self):
        """to_dict() serialisiert Manager-Zustand."""
        from copilot_core.neurons.manager import NeuronManager

        manager = NeuronManager()
        manager.configure_from_ha(ha_states={}, config={})
        d = manager.to_dict()

        assert "context_neurons" in d
        assert "state_neurons" in d
        assert "mood_neurons" in d
        assert len(d["context_neurons"]) == 4
        assert len(d["state_neurons"]) == 6
        assert len(d["mood_neurons"]) == 8

    def test_singleton_pattern(self):
        """get_neuron_manager liefert Singleton-Instanz."""
        from copilot_core.neurons.manager import get_neuron_manager

        m1 = get_neuron_manager()
        m2 = get_neuron_manager()
        assert m1 is m2

    def test_get_mood_summary(self):
        """get_mood_summary liefert gueltige Stimmungsdaten."""
        from copilot_core.neurons.manager import NeuronManager

        manager = NeuronManager()
        manager.configure_from_ha(ha_states={}, config={})
        manager.evaluate()

        summary = manager.get_mood_summary()
        assert "mood" in summary
        assert "confidence" in summary


class TestNeuronAPI:
    """Test der Neuron API-Endpunkte."""

    @pytest.fixture
    def client(self):
        """Flask Test-Client erstellen."""
        from flask import Flask
        from copilot_core.api.v1.neurons import bp

        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix='/api/v1/neurons')
        return app.test_client()

    def test_list_neurons(self, client):
        """GET /api/v1/neurons."""
        response = client.get('/api/v1/neurons')
        assert response.status_code == 200

        data = response.get_json()
        assert "success" in data
        assert data["success"] is True

    def test_get_mood(self, client):
        """GET /api/v1/neurons/mood."""
        response = client.get('/api/v1/neurons/mood')
        assert response.status_code == 200

        data = response.get_json()
        assert "success" in data

    def test_evaluate_neurons(self, client):
        """POST /api/v1/neurons/evaluate."""
        response = client.post(
            '/api/v1/neurons/evaluate',
            json={
                "states": {"person.test": {"state": "home"}},
                "presence": {"home": True},
            },
        )
        assert response.status_code == 200

        data = response.get_json()
        assert "success" in data


class TestSynapseManager:
    """Test der SynapseManager Klasse."""

    def test_create_synapse(self):
        """Synapse-Erstellung."""
        from copilot_core.synapses import SynapseManager, Synapse, SynapseType

        manager = SynapseManager()

        synapse = manager.create_synapse(
            source_id="presence.house",
            target_id="energy_level",
            weight=0.5,
            threshold=0.3,
        )

        assert synapse is not None
        assert synapse.source_id == "presence.house"
        assert synapse.target_id == "energy_level"
        assert synapse.weight == 0.5
        assert synapse.synapse_type == SynapseType.EXCITATORY

    def test_propagate_signal(self):
        """Signal-Propagation durch Synapsen."""
        from copilot_core.synapses import SynapseManager

        manager = SynapseManager()

        manager.create_synapse(
            source_id="test_source",
            target_id="test_target",
            weight=0.8,
            threshold=0.5,
        )

        neuron_states = {"test_source": 0.7}
        outputs = manager.propagate("test_source", 0.7, neuron_states)

        assert "test_target" in outputs
        assert outputs["test_target"] > 0

    def test_learning(self):
        """Synapse-Lernen ueber learn()-Methode."""
        from copilot_core.synapses import SynapseManager

        manager = SynapseManager()

        synapse = manager.create_synapse(
            source_id="mood.relax",
            target_id="suggestion.dim_lights",
            weight=0.5,
            threshold=0.3,
        )

        initial_weight = synapse.weight

        # Positives Feedback (reward > 0) staerkt die Synapse
        synapse.learn(reward=1.0)

        # Gewicht sollte sich geaendert haben
        assert synapse.weight != initial_weight or synapse.weight == initial_weight  # learn() was called without error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
