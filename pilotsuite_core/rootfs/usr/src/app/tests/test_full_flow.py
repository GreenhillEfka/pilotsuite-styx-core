#!/usr/bin/env python3
"""Tests for full pipeline flow."""

import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestFullFlow(unittest.TestCase):
    """Test end-to-end pipeline flows."""

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
            events_jsonl_path=f"{self.tmpdir.name}/events.jsonl",
            candidates_json_path=f"{self.tmpdir.name}/candidates.json",
        )
        
        # Reset lazy singletons
        from copilot_core.brain_graph import provider
        provider._STORE = None
        provider._SVC = None
        
        return app

    def test_event_to_graph_flow(self):
        """Test event ingestion flowing into brain graph."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        # Post event
        payload = {
            "items": [
                {
                    "id": "evt-1",
                    "type": "state_changed",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]}
                }
            ]
        }
        
        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        
        # Check graph state
        r2 = client.get("/api/v1/graph/state")
        self.assertEqual(r2.status_code, 200)
        
        g = r2.get_json()
        nodes = g.get("nodes", [])
        
        # Should have entity node
        node_ids = {n.get("id") for n in nodes}
        self.assertIn("ha.entity:light.kitchen", node_ids)

    def test_state_changed_to_entity_node(self):
        """Test state_changed event creates entity node."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.living_room",
                    "old_state": {"state": "off"},
                    "new_state": {"state": "on"}
                }
            ]
        }
        
        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        
        r2 = client.get("/api/v1/graph/state")
        g = r2.get_json()
        
        node_ids = {n.get("id") for n in g.get("nodes", [])}
        self.assertIn("ha.entity:light.living_room", node_ids)

    def test_service_call_creates_intent(self):
        """Test call_service creates intent node."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {
                    "type": "call_service",
                    "entity_id": "light.porch",
                    "attributes": {
                        "domain": "light",
                        "service": "turn_on"
                    }
                }
            ]
        }
        
        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        
        r2 = client.get("/api/v1/graph/state")
        g = r2.get_json()
        
        node_ids = {n.get("id") for n in g.get("nodes", [])}
        self.assertIn("ha.intent:light.turn_on", node_ids)

    def test_zone_creation_from_attributes(self):
        """Test zones are created from event attributes."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.bedroom",
                    "attributes": {
                        "zone_ids": ["bedroom", "upstairs"]
                    }
                }
            ]
        }
        
        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        
        r2 = client.get("/api/v1/graph/state")
        g = r2.get_json()
        
        node_ids = {n.get("id") for n in g.get("nodes", [])}
        self.assertIn("zone:bedroom", node_ids)
        self.assertIn("zone:upstairs", node_ids)

    def test_entity_to_zone_edge_creation(self):
        """Test edges created between entity and zone."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]}
                }
            ]
        }
        
        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        
        r2 = client.get("/api/v1/graph/state")
        g = r2.get_json()
        
        edges = g.get("edges", [])
        
        # Should have at least one edge
        self.assertGreaterEqual(len(edges), 1)

    def test_multiple_events_batch(self):
        """Test batch event processing."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        payload = {
            "items": [
                {"type": "state_changed", "entity_id": "light.1"},
                {"type": "state_changed", "entity_id": "light.2"},
                {"type": "state_changed", "entity_id": "sensor.1"},
                {"type": "call_service", "entity_id": "climate.1", 
                 "attributes": {"domain": "climate", "service": "set_temperature"}},
            ]
        }
        
        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        
        j = r.get_json()
        self.assertEqual(j.get("ingested"), 4)
        
        r2 = client.get("/api/v1/graph/state")
        g = r2.get_json()
        
        # Should have multiple nodes
        self.assertGreaterEqual(len(g.get("nodes", [])), 4)

    def test_graph_stats_reflect_data(self):
        """Test graph stats reflect ingested data."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()

        # Add data
        payload = {
            "items": [
                {"type": "state_changed", "entity_id": "light.test"},
            ]
        }
        client.post("/api/v1/events", json=payload)
        
        # Get stats
        r = client.get("/api/v1/graph/stats")
        self.assertEqual(r.status_code, 200)
        
        stats = r.get_json()
        self.assertIn("limits", stats)


if __name__ == "__main__":
    unittest.main()
