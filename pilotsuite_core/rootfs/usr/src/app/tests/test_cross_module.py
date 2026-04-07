"""Tests for CrossModuleAnalyzer and Module Health Dashboard."""

import unittest
from unittest.mock import MagicMock

from copilot_core.integration.bus import IntegrationBus
from copilot_core.integration.cross_module import (
    CrossModuleAnalyzer,
    CrossPattern,
    ProposedSynapse,
)


class TestCrossModuleAnalyzer(unittest.TestCase):
    """Tests for the CrossModuleAnalyzer."""

    def setUp(self):
        self.bus = IntegrationBus()
        self.analyzer = CrossModuleAnalyzer(
            self.bus, window_size=50, min_correlation=0.5
        )

    def test_collects_snapshots(self):
        """Analyzer collects snapshots from neuron.evaluated events."""
        self.bus.publish("neuron.evaluated", {
            "context_values": {"presence": 0.8, "time_of_day": 0.5},
            "state_values": {"energy_level": 0.7},
            "mood_values": {"focus": 0.6},
        }, source="test")

        stats = self.analyzer.get_stats()
        self.assertEqual(stats["snapshots_collected"], 1)

    def test_analyze_needs_minimum_snapshots(self):
        """Analysis requires at least 10 snapshots."""
        for _ in range(5):
            self.bus.publish("neuron.evaluated", {
                "context_values": {"presence": 0.8},
                "state_values": {"energy_level": 0.7},
                "mood_values": {"focus": 0.6},
            }, source="test")

        patterns = self.analyzer.analyze_correlations()
        self.assertEqual(len(patterns), 0)

    def test_finds_correlations(self):
        """Finds correlated neuron pairs across layers."""
        # Publish strongly correlated values
        for i in range(20):
            val = (i % 10) / 10.0
            self.bus.publish("neuron.evaluated", {
                "context_values": {"presence": val},
                "state_values": {"energy_level": val * 0.9},
                "mood_values": {"focus": val * 0.8},
            }, source="test")

        patterns = self.analyzer.analyze_correlations()
        # Should find correlations between context.presence and state/mood
        self.assertGreater(len(patterns), 0)
        for p in patterns:
            self.assertIsInstance(p, CrossPattern)
            self.assertNotEqual(p.module_a.split(".")[0], p.module_b.split(".")[0])

    def test_patterns_stored(self):
        """Discovered patterns are stored and retrievable."""
        for i in range(20):
            val = (i % 10) / 10.0
            self.bus.publish("neuron.evaluated", {
                "context_values": {"presence": val},
                "state_values": {"energy_level": val},
                "mood_values": {},
            }, source="test")

        self.analyzer.analyze_correlations()
        patterns = self.analyzer.get_patterns()
        self.assertIsInstance(patterns, list)
        if patterns:
            self.assertIn("pattern_id", patterns[0])
            self.assertIn("correlation", patterns[0])

    def test_suggest_new_connections(self):
        """Can suggest new synapses from patterns."""
        for i in range(20):
            val = (i % 10) / 10.0
            self.bus.publish("neuron.evaluated", {
                "context_values": {"presence": val, "weather": 1.0 - val},
                "state_values": {"energy_level": val},
                "mood_values": {"focus": val},
            }, source="test")

        self.analyzer.analyze_correlations()
        proposals = self.analyzer.suggest_new_connections()
        self.assertIsInstance(proposals, list)

    def test_stats(self):
        """Stats return correct metrics."""
        stats = self.analyzer.get_stats()
        self.assertEqual(stats["snapshots_collected"], 0)
        self.assertEqual(stats["window_size"], 50)
        self.assertEqual(stats["patterns_discovered"], 0)

    def test_pearson_identical(self):
        """Pearson correlation of identical series is 1.0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = CrossModuleAnalyzer._pearson(x, x)
        self.assertAlmostEqual(r, 1.0, places=5)

    def test_pearson_opposite(self):
        """Pearson correlation of inverted series is -1.0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]
        r = CrossModuleAnalyzer._pearson(x, y)
        self.assertAlmostEqual(r, -1.0, places=5)

    def test_pearson_constant_returns_zero(self):
        """Pearson with constant series returns 0."""
        x = [1.0, 1.0, 1.0, 1.0]
        y = [1.0, 2.0, 3.0, 4.0]
        r = CrossModuleAnalyzer._pearson(x, y)
        self.assertEqual(r, 0.0)


class TestModuleHealthAPI(unittest.TestCase):
    """Tests for the Module Health Dashboard API."""

    def setUp(self):
        from flask import Flask
        from copilot_core.api.v1.module_health import (
            module_health_bp,
            init_module_health_api,
        )

        self.bus = IntegrationBus()
        self.mock_registry = MagicMock()
        self.mock_registry.get_all_states.return_value = {
            "mood_engine": "active",
            "habitus_miner": "learning",
        }

        init_module_health_api(
            module_registry=self.mock_registry,
            integration_bus=self.bus,
        )

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(module_health_bp)
        self.client = app.test_client()

    def test_dashboard_endpoint(self):
        """GET /dashboard returns full health data."""
        resp = self.client.get("/api/v1/modules/health/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("modules", data)
        self.assertIn("bus", data)
        self.assertIn("timestamp_ms", data)
        self.assertEqual(data["modules"]["mood_engine"], "active")

    def test_learning_endpoint_no_learner(self):
        """GET /learning returns 503 when no learner is configured."""
        resp = self.client.get("/api/v1/modules/health/learning")
        self.assertEqual(resp.status_code, 503)

    def test_patterns_endpoint_no_analyzer(self):
        """GET /patterns returns 503 when no analyzer is configured."""
        resp = self.client.get("/api/v1/modules/health/patterns")
        self.assertEqual(resp.status_code, 503)


if __name__ == "__main__":
    unittest.main()
