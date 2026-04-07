"""Tests for Brain Architecture Engine (v7.4.0)."""

import pytest
from copilot_core.hub.brain_architecture import (
    BrainArchitectureEngine,
    BrainRegion,
    Neuron,
    Synapse,
    SynapseState,
    RegionRole,
)


@pytest.fixture
def engine():
    return BrainArchitectureEngine()


# ── Region Tests ─────────────────────────────────────────────────────────────


class TestRegions:
    def test_default_regions_loaded(self, engine):
        regions = engine.get_all_regions()
        assert len(regions) == 15

    def test_region_has_color(self, engine):
        r = engine.get_region("anomaly")
        assert r is not None
        assert r.color == "#DC143C"
        assert r.name_de == "Anomalie-Amygdala"

    def test_all_regions_have_colors(self, engine):
        for r in engine.get_all_regions():
            assert r.color.startswith("#"), f"{r.region_id} missing colour"
            assert len(r.color) == 7, f"{r.region_id} invalid colour"

    def test_all_regions_have_icons(self, engine):
        for r in engine.get_all_regions():
            assert r.icon.startswith("mdi:"), f"{r.region_id} missing icon"

    def test_all_regions_have_roles(self, engine):
        valid_roles = {e.value for e in RegionRole}
        for r in engine.get_all_regions():
            assert r.role in valid_roles, f"{r.region_id} invalid role"

    def test_set_region_health(self, engine):
        assert engine.set_region_health("anomaly", 0.5)
        r = engine.get_region("anomaly")
        assert r.health == 0.5

    def test_set_region_health_clamped(self, engine):
        engine.set_region_health("anomaly", 1.5)
        assert engine.get_region("anomaly").health == 1.0
        engine.set_region_health("anomaly", -0.5)
        assert engine.get_region("anomaly").health == 0.0

    def test_set_region_health_unknown(self, engine):
        assert not engine.set_region_health("unknown_region", 0.5)

    def test_set_region_active(self, engine):
        engine.set_region_active("light", False)
        assert not engine.get_region("light").is_active
        engine.set_region_active("light", True)
        assert engine.get_region("light").is_active

    def test_get_unknown_region(self, engine):
        assert engine.get_region("nonexistent") is None

    def test_region_engine_keys_unique(self, engine):
        keys = [r.engine_key for r in engine.get_all_regions()]
        assert len(keys) == len(set(keys))


# ── Neuron Tests ─────────────────────────────────────────────────────────────


class TestNeurons:
    def test_register_neuron(self, engine):
        n = engine.register_neuron("anomaly", "AnomalyDetectionSensor",
                                   "sensor.pilotsuite_anomaly_detection")
        assert n is not None
        assert n.region_id == "anomaly"
        assert n.sensor_class == "AnomalyDetectionSensor"

    def test_register_neuron_unknown_region(self, engine):
        n = engine.register_neuron("fake_region", "Sensor", "sensor.fake")
        assert n is None

    def test_get_neurons(self, engine):
        engine.register_neuron("anomaly", "AnomalyDetectionSensor", "sensor.anomaly")
        engine.register_neuron("light", "LightIntelligenceSensor", "sensor.light")
        assert len(engine.get_neurons()) == 2

    def test_get_neurons_for_region(self, engine):
        engine.register_neuron("anomaly", "AnomalyDetectionSensor", "sensor.anomaly")
        engine.register_neuron("light", "LightIntelligenceSensor", "sensor.light")
        anomaly_neurons = engine.get_neurons_for_region("anomaly")
        assert len(anomaly_neurons) == 1
        assert anomaly_neurons[0].region_id == "anomaly"

    def test_update_neuron_state(self, engine):
        engine.register_neuron("anomaly", "AnomalyDetectionSensor", "sensor.anomaly")
        assert engine.update_neuron_state("neuron_anomaly", "3 Anomalien")
        n = engine.get_neurons()[0]
        assert n.state == "3 Anomalien"
        assert n.last_fired != ""

    def test_update_neuron_state_unknown(self, engine):
        assert not engine.update_neuron_state("nonexistent", "test")


# ── Synapse Tests ────────────────────────────────────────────────────────────


class TestSynapses:
    def test_default_synapses_loaded(self, engine):
        synapses = engine.get_all_synapses()
        assert len(synapses) == 14

    def test_synapse_has_source_target(self, engine):
        s = engine.get_all_synapses()[0]
        assert s.source_region in [r.region_id for r in engine.get_all_regions()]
        assert s.target_region in [r.region_id for r in engine.get_all_regions()]

    def test_get_synapses_from(self, engine):
        from_presence = engine.get_synapses_from("presence")
        assert len(from_presence) >= 3  # presence_changed + person_arrived + person_departed

    def test_get_synapses_to(self, engine):
        to_notifications = engine.get_synapses_to("notifications")
        assert len(to_notifications) >= 4  # multiple event types target notifications

    def test_fire_synapse(self, engine):
        s = engine.get_all_synapses()[0]
        s.state = SynapseState.ACTIVE.value
        s.strength = 0.5  # start below max so Hebbian increase is visible
        assert engine.fire_synapse(s.synapse_id)
        assert s.fire_count == 1
        assert s.last_fired != ""
        assert s.strength > 0.5  # Hebbian strengthening

    def test_fire_synapse_blocked(self, engine):
        s = engine.get_all_synapses()[0]
        engine.set_synapse_state(s.synapse_id, SynapseState.BLOCKED.value)
        assert not engine.fire_synapse(s.synapse_id)
        assert s.fire_count == 0

    def test_fire_synapse_unknown(self, engine):
        assert not engine.fire_synapse("nonexistent")

    def test_add_synapse(self, engine):
        s = engine.add_synapse("anomaly", "light", "custom_event",
                               "Anomalie dimmt Licht")
        assert s is not None
        assert s.source_region == "anomaly"
        assert s.target_region == "light"
        assert len(engine.get_all_synapses()) == 15

    def test_add_synapse_unknown_region(self, engine):
        s = engine.add_synapse("fake", "light", "event")
        assert s is None

    def test_remove_synapse(self, engine):
        s = engine.get_all_synapses()[0]
        assert engine.remove_synapse(s.synapse_id)
        assert len(engine.get_all_synapses()) == 13

    def test_remove_synapse_unknown(self, engine):
        assert not engine.remove_synapse("nonexistent")

    def test_set_synapse_state(self, engine):
        s = engine.get_all_synapses()[0]
        engine.set_synapse_state(s.synapse_id, SynapseState.DORMANT.value)
        assert s.state == SynapseState.DORMANT.value

    def test_set_synapse_state_unknown(self, engine):
        assert not engine.set_synapse_state("nonexistent", "active")


# ── Sync with Integration Hub ───────────────────────────────────────────────


class TestSyncWithHub:
    def test_sync_marks_active(self, engine):
        class FakeHub:
            _engines = {"anomaly_detection": object(), "light_intelligence": object()}
            def get_wiring_diagram(self):
                return {"anomaly_detected": ["notification_intelligence"]}

        result = engine.sync_with_hub(FakeHub())
        assert result["synced"]
        assert result["engines_found"] == 2
        assert engine.get_region("anomaly").is_active
        assert engine.get_region("light").is_active
        assert not engine.get_region("media").is_active

    def test_sync_no_engines_attr(self, engine):
        result = engine.sync_with_hub(object())
        assert not result["synced"]


# ── Graph Data ───────────────────────────────────────────────────────────────


class TestGraphData:
    def test_graph_has_nodes_and_edges(self, engine):
        graph = engine.get_graph_data()
        assert len(graph["nodes"]) == 15
        assert len(graph["edges"]) == 14

    def test_node_has_required_fields(self, engine):
        graph = engine.get_graph_data()
        node = graph["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert "color" in node
        assert "icon" in node
        assert "role" in node
        assert "health" in node

    def test_edge_has_required_fields(self, engine):
        graph = engine.get_graph_data()
        edge = graph["edges"][0]
        assert "id" in edge
        assert "source" in edge
        assert "target" in edge
        assert "event_type" in edge
        assert "color" in edge
        assert "strength" in edge


# ── Status & Dashboard ───────────────────────────────────────────────────────


class TestStatus:
    def test_status_regions(self, engine):
        status = engine.get_status()
        assert status.total_regions == 15
        assert status.active_regions == 15

    def test_status_synapses(self, engine):
        status = engine.get_status()
        assert status.total_synapses == 14
        assert status.active_synapses == 14

    def test_status_connectivity(self, engine):
        status = engine.get_status()
        assert status.connectivity_score > 0

    def test_status_health(self, engine):
        status = engine.get_status()
        assert status.health_score == 100.0

    def test_status_health_degraded(self, engine):
        engine.set_region_health("anomaly", 0.0)
        engine.set_region_health("light", 0.5)
        status = engine.get_status()
        assert status.health_score < 100.0

    def test_dashboard(self, engine):
        d = engine.get_dashboard()
        assert d["ok"]
        assert d["total_regions"] == 15
        assert "graph" in d
        assert "nodes" in d["graph"]
        assert "edges" in d["graph"]
        assert len(d["regions"]) == 15
        assert len(d["synapses"]) == 14
