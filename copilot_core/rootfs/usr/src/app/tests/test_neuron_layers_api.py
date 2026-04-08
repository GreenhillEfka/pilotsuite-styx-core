"""Tests for Neuron Layer Visualization API, SVG Renderer, and Heatmap."""

import unittest
from unittest.mock import MagicMock, patch

from copilot_core.neurons.manager import NeuronManager
from copilot_core.api.v1.neuron_layers import (
    neuron_layers_bp,
    init_neuron_layers_api,
    render_neuron_layer_svg,
    SYNAPSE_TOPOLOGY,
    _build_layer,
    _build_connections,
)
from copilot_core.integration.bus import IntegrationBus


class TestNeuronLayersVisualization(unittest.TestCase):
    """Tests for GET /api/v1/neurons/layers/visualization."""

    def setUp(self):
        from flask import Flask
        self.mgr = NeuronManager()
        self.mgr.configure_from_ha({}, {})
        self.mgr.evaluate()

        self.bus = IntegrationBus()
        init_neuron_layers_api(self.mgr, self.bus)

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(neuron_layers_bp)
        self.client = app.test_client()

    def test_visualization_structure(self):
        """Visualization endpoint returns correct structure."""
        resp = self.client.get("/api/v1/neurons/layers/visualization")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("layers", data)
        self.assertIn("connections", data)
        self.assertIn("pipeline_status", data)
        self.assertIn("timestamp_ms", data)

        # 3 layers
        self.assertEqual(len(data["layers"]), 3)
        self.assertEqual(data["layers"][0]["name"], "Context")
        self.assertEqual(data["layers"][1]["name"], "State")
        self.assertEqual(data["layers"][2]["name"], "Mood")

    def test_layer_neurons_populated(self):
        """Each layer has neurons with values."""
        resp = self.client.get("/api/v1/neurons/layers/visualization")
        data = resp.get_json()

        for layer in data["layers"]:
            self.assertGreater(len(layer["neurons"]), 0)
            for neuron in layer["neurons"]:
                self.assertIn("id", neuron)
                self.assertIn("value", neuron)
                self.assertIn("active", neuron)
                self.assertIsInstance(neuron["value"], float)

    def test_connections_have_signal_strength(self):
        """Connections include weight and signal_strength."""
        resp = self.client.get("/api/v1/neurons/layers/visualization")
        data = resp.get_json()

        self.assertGreater(len(data["connections"]), 10)
        for conn in data["connections"]:
            self.assertIn("from", conn)
            self.assertIn("to", conn)
            self.assertIn("weight", conn)
            self.assertIn("signal_strength", conn)
            self.assertIn("excitatory", conn)
            self.assertIsInstance(conn["excitatory"], bool)

    def test_pipeline_status(self):
        """Pipeline status includes mood and confidence."""
        resp = self.client.get("/api/v1/neurons/layers/visualization")
        data = resp.get_json()

        ps = data["pipeline_status"]
        self.assertIn("dominant_mood", ps)
        self.assertIn("mood_confidence", ps)
        self.assertIsNotNone(ps["dominant_mood"])


class TestNeuronLayersSVG(unittest.TestCase):
    """Tests for GET /api/v1/neurons/layers/snapshot.svg."""

    def setUp(self):
        from flask import Flask
        self.mgr = NeuronManager()
        self.mgr.configure_from_ha({}, {})
        self.mgr.evaluate()

        init_neuron_layers_api(self.mgr)

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(neuron_layers_bp)
        self.client = app.test_client()

    def test_svg_response(self):
        """SVG endpoint returns valid SVG."""
        resp = self.client.get("/api/v1/neurons/layers/snapshot.svg")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("image/svg+xml", resp.content_type)
        svg = resp.data.decode()
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_svg_contains_neurons(self):
        """SVG contains neuron circles and labels."""
        resp = self.client.get("/api/v1/neurons/layers/snapshot.svg")
        svg = resp.data.decode()
        self.assertIn("<circle", svg)
        self.assertIn("presence", svg)
        self.assertIn("Layer 0: Context", svg)
        self.assertIn("Layer 2: Mood", svg)

    def test_svg_contains_connections(self):
        """SVG contains connection lines."""
        resp = self.client.get("/api/v1/neurons/layers/snapshot.svg")
        svg = resp.data.decode()
        self.assertIn("<line", svg)

    def test_render_function_direct(self):
        """render_neuron_layer_svg works with real neurons."""
        all_neurons = self.mgr.get_all_neurons()
        result = self.mgr._last_result
        svg = render_neuron_layer_svg(all_neurons, result)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("Neural Pipeline", svg)


class TestHeatmap(unittest.TestCase):
    """Tests for GET /api/v1/neurons/connections/heatmap."""

    def setUp(self):
        from flask import Flask
        self.mgr = NeuronManager()
        self.mgr.configure_from_ha({}, {})
        self.mgr.evaluate()

        init_neuron_layers_api(self.mgr)

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(neuron_layers_bp)
        self.client = app.test_client()

    def test_heatmap_structure(self):
        """Heatmap returns matrix, labels, boundaries."""
        resp = self.client.get("/api/v1/neurons/layers/heatmap")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("matrix", data)
        self.assertIn("labels", data)
        self.assertIn("layer_boundaries", data)

    def test_heatmap_matrix_dimensions(self):
        """Matrix is N×N where N = number of neurons."""
        resp = self.client.get("/api/v1/neurons/layers/heatmap")
        data = resp.get_json()

        n = len(data["labels"])
        self.assertEqual(len(data["matrix"]), n)
        for row in data["matrix"]:
            self.assertEqual(len(row), n)

    def test_heatmap_layer_boundaries(self):
        """Layer boundaries sum to total neuron count."""
        resp = self.client.get("/api/v1/neurons/layers/heatmap")
        data = resp.get_json()

        n = len(data["labels"])
        self.assertEqual(data["layer_boundaries"][-1], n)
        self.assertEqual(len(data["layer_boundaries"]), 3)


class TestSynapseTopology(unittest.TestCase):
    """Tests for the synapse topology definition."""

    def test_topology_not_empty(self):
        """Topology has connections defined."""
        self.assertGreater(len(SYNAPSE_TOPOLOGY), 20)

    def test_topology_entries_valid(self):
        """Each entry has (from, to, weight) format."""
        for entry in SYNAPSE_TOPOLOGY:
            self.assertEqual(len(entry), 3)
            from_n, to_n, weight = entry
            self.assertIn(".", from_n)
            self.assertIn(".", to_n)
            self.assertIsInstance(weight, (int, float))

    def test_topology_cross_layer(self):
        """Topology has connections between different layers."""
        cross_layer = [
            (f, t) for f, t, _ in SYNAPSE_TOPOLOGY
            if f.split(".")[0] != t.split(".")[0]
        ]
        self.assertGreater(len(cross_layer), 15)


if __name__ == "__main__":
    unittest.main()
