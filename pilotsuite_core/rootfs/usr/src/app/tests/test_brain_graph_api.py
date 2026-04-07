#!/usr/bin/env python3
"""Tests for /api/v1/graph/* endpoints (brain graph API)."""

import tempfile
import unittest
import json

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestBrainGraphAPI(unittest.TestCase):
    """Test brain graph API endpoints."""

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
        from copilot_core.brain_graph import provider
        provider._STORE = None
        provider._SVC = None
        
        return app

    def test_graph_state_empty(self):
        """Test GET /api/v1/graph/state with empty graph."""
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/graph/state")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertIn("version", j)
        self.assertIn("nodes", j)
        self.assertIn("edges", j)

    def test_graph_state_with_nodes(self):
        """Test GET /api/v1/graph/state with nodes."""
        app = self._create_test_app()
        client = app.test_client()
        
        # Add some events to create nodes
        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]}
                }
            ]
        }
        client.post("/api/v1/events", json=payload)
        
        # Get graph state
        r = client.get("/api/v1/graph/state")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        
        self.assertGreaterEqual(len(j["nodes"]), 1)
        self.assertGreaterEqual(len(j["edges"]), 0)

    def test_graph_state_with_kinds_filter(self):
        """Test GET /api/v1/graph/state with kind filter."""
        app = self._create_test_app()
        client = app.test_client()
        
        # Add various node types
        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]}
                }
            ]
        }
        client.post("/api/v1/events", json=payload)
        
        # Filter by kind
        r = client.get("/api/v1/graph/state?kind=entity")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        
        nodes = j.get("nodes", [])
        for node in nodes:
            self.assertEqual(node.get("kind"), "entity")

    def test_graph_state_with_domains_filter(self):
        """Test GET /api/v1/graph/state with domain filter."""
        app = self._create_test_app()
        client = app.test_client()
        
        # Add nodes
        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]}
                }
            ]
        }
        client.post("/api/v1/events", json=payload)
        
        # Filter by domain
        r = client.get("/api/v1/graph/state?domain=light")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        
        nodes = j.get("nodes", [])
        for node in nodes:
            self.assertEqual(node.get("domain"), "light")

    def test_graph_state_with_center_and_hops(self):
        """Test GET /api/v1/graph/state with center node and hops."""
        app = self._create_test_app()
        client = app.test_client()
        
        # Add nodes with relationships
        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]}
                },
                {
                    "type": "state_changed",
                    "entity_id": "switch.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]}
                }
            ]
        }
        client.post("/api/v1/events", json=payload)
        
        # Get 1-hop neighborhood from kitchen zone
        r = client.get("/api/v1/graph/state?center=zone:kitchen&hops=1")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        
        # Should include kitchen zone and related nodes
        node_ids = {n.get("id") for n in j.get("nodes", [])}
        self.assertIn("zone:kitchen", node_ids)

    def test_graph_stats(self):
        """Test GET /api/v1/graph/stats."""
        app = self._create_test_app()
        client = app.test_client()
        
        # Add some data
        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]}
                }
            ]
        }
        client.post("/api/v1/events", json=payload)
        
        # Get stats
        r = client.get("/api/v1/graph/stats")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        
        self.assertIn("version", j)
        self.assertIn("limits", j)

    def test_graph_patterns(self):
        """Test GET /api/v1/graph/patterns."""
        app = self._create_test_app()
        client = app.test_client()
        
        r = client.get("/api/v1/graph/patterns")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        
        self.assertIn("version", j)
        self.assertIn("patterns", j)

    def test_graph_snapshot_svg(self):
        """Test GET /api/v1/graph/snapshot.svg."""
        app = self._create_test_app()
        client = app.test_client()
        
        r = client.get("/api/v1/graph/snapshot.svg")
        self.assertEqual(r.status_code, 200)
        self.assertIn("image/svg+xml", r.headers.get("Content-Type", ""))


if __name__ == "__main__":
    unittest.main()
