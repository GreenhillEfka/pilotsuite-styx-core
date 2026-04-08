#!/usr/bin/env python3
"""Tests for brain graph feeding from events."""

import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestBrainGraphFeeding(unittest.TestCase):
    """Test brain graph feeding from events."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def _create_test_app(self):
        """Create a test Flask app with temp paths."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        from dataclasses import replace
        
        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            brain_graph_json_path=f"{self.tmpdir.name}/brain_graph.json",
        )
        
        # Reset lazy singletons
        from copilot_core.api.v1 import events as events_api
        events_api._STORE = None
        from copilot_core.brain_graph import provider as graph_provider
        graph_provider._STORE = None
        graph_provider._SVC = None
        
        return app

    def test_graph_non_empty_after_ingest(self):
        """Test that graph has nodes after event ingestion."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {
                    "id": "evt-1",
                    "ts": "2026-02-08T12:00:00Z",
                    "type": "state_changed",
                    "source": "home_assistant",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]},
                },
                {
                    "id": "evt-2",
                    "ts": "2026-02-08T12:00:01Z",
                    "type": "call_service",
                    "source": "home_assistant",
                    "entity_id": "light.kitchen",
                    "attributes": {
                        "domain": "light",
                        "service": "turn_on",
                        "entity_ids": ["light.kitchen"],
                        "zone_ids": ["kitchen"],
                    },
                },
            ]
        }

        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        j = r.get_json() or {}
        self.assertTrue(j.get("ok"))
        self.assertEqual(j.get("ingested"), 2)

        r2 = client.get("/api/v1/graph/state")
        self.assertEqual(r2.status_code, 200)
        g = r2.get_json() or {}

        nodes = g.get("nodes") or []
        edges = g.get("edges") or []
        self.assertGreaterEqual(len(nodes), 2)
        self.assertGreaterEqual(len(edges), 1)

        node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
        self.assertIn("ha.entity:light.kitchen", node_ids)

    def test_graph_with_zones(self):
        """Test that zones are created from event attributes."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {
                    "id": "evt-zone-1",
                    "type": "state_changed",
                    "entity_id": "light.living_room",
                    "attributes": {"zone_ids": ["living_room", "downstairs"]},
                }
            ]
        }

        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)

        r2 = client.get("/api/v1/graph/state")
        g = r2.get_json() or {}
        nodes = g.get("nodes") or []
        
        node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
        self.assertIn("zone:living_room", node_ids)
        self.assertIn("zone:downstairs", node_ids)

    def test_graph_service_intents(self):
        """Test that service intents are tracked."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {
                    "id": "evt-service-1",
                    "type": "call_service",
                    "entity_id": "light.kitchen",
                    "attributes": {
                        "domain": "light",
                        "service": "turn_on",
                    },
                }
            ]
        }

        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)

        r2 = client.get("/api/v1/graph/state")
        g = r2.get_json() or {}
        nodes = g.get("nodes") or []
        
        node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
        self.assertIn("ha.intent:light.turn_on", node_ids)

    def test_graph_multiple_events(self):
        """Test that multiple events create multiple nodes."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {"id": "evt-1", "type": "state_changed", "entity_id": "light.kitchen"},
                {"id": "evt-2", "type": "state_changed", "entity_id": "light.bedroom"},
                {"id": "evt-3", "type": "state_changed", "entity_id": "sensor.temperature"},
                {"id": "evt-4", "type": "state_changed", "entity_id": "switch.garage"},
            ]
        }

        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)

        r2 = client.get("/api/v1/graph/state")
        g = r2.get_json() or {}
        nodes = g.get("nodes") or []
        
        # Should have at least 4 entity nodes
        entity_nodes = [n for n in nodes if isinstance(n, dict) and n.get("kind") == "entity"]
        self.assertGreaterEqual(len(entity_nodes), 4)


if __name__ == "__main__":
    unittest.main()
