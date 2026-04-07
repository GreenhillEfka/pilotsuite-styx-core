#!/usr/bin/env python3
"""Tests for API integration."""

import tempfile
import unittest
import json

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestAPIIntegration(unittest.TestCase):
    """Test API integration and cross-endpoint functionality."""

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

    def test_health_and_version_integrated(self):
        """Test health and version endpoints work together."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Get health
        r1 = client.get("/health")
        self.assertEqual(r1.status_code, 200)
        
        # Get version
        r2 = client.get("/version")
        self.assertEqual(r2.status_code, 200)
        
        # Both should have timestamps
        health_data = r1.get_json()
        version_data = r2.get_json()
        
        self.assertIn("time", health_data)
        self.assertIn("time", version_data)
        self.assertIn("version", version_data)

    def test_capabilities_reflects_system(self):
        """Test capabilities endpoint reflects available modules."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        r = client.get("/api/v1/capabilities")
        data = r.get_json()
        
        modules = data.get("modules", {})
        
        # Check key modules are listed
        self.assertIn("events", modules)
        self.assertIn("brain_graph", modules)

    def test_events_to_graph_integration(self):
        """Test events endpoint integrates with graph endpoint."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Post event
        payload = {
            "items": [
                {
                    "type": "state_changed",
                    "entity_id": "light.integration_test"
                }
            ]
        }
        r1 = client.post("/api/v1/events", json=payload)
        self.assertEqual(r1.status_code, 200)
        
        # Get graph state
        r2 = client.get("/api/v1/graph/state")
        self.assertEqual(r2.status_code, 200)
        
        # Verify data flowed through
        graph_data = r2.get_json()
        node_ids = {n.get("id") for n in graph_data.get("nodes", [])}
        self.assertIn("ha.entity:light.integration_test", node_ids)

    def test_dashboard_uses_brain_graph(self):
        """Test dashboard endpoint uses brain graph data."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Add some data
        payload = {
            "items": [
                {"type": "state_changed", "entity_id": "light.dashboard"}
            ]
        }
        client.post("/api/v1/events", json=payload)
        
        # Get dashboard
        r = client.get("/api/v1/dashboard/brain-summary")
        self.assertEqual(r.status_code, 200)
        
        data = r.get_json()
        self.assertTrue(data.get("ok"))
        self.assertIn("summary", data)

    def test_multiple_endpoints_json_format(self):
        """Test multiple endpoints return consistent JSON format."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        endpoints = [
            "/health",
            "/version",
            "/api/v1/capabilities",
            "/api/v1/graph/state",
            "/api/v1/graph/stats",
            "/api/v1/dashboard/health",
        ]
        
        for endpoint in endpoints:
            r = client.get(endpoint)
            self.assertEqual(r.status_code, 200, f"Endpoint {endpoint} failed")
            
            # Should be valid JSON
            data = r.get_json()
            self.assertIsInstance(data, dict, f"Endpoint {endpoint} not returning dict")

    def test_events_crud_operations(self):
        """Test events can be created and retrieved."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Create events
        payload = {
            "items": [
                {"type": "test", "data": "crud-test-1"},
                {"type": "test", "data": "crud-test-2"}
            ]
        }
        r1 = client.post("/api/v1/events", json=payload)
        self.assertEqual(r1.status_code, 200)
        
        # List events
        r2 = client.get("/api/v1/events")
        self.assertEqual(r2.status_code, 200)
        
        data = r2.get_json()
        self.assertIn("items", data)

    def test_candidates_integration(self):
        """Test candidates endpoint integration."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Create candidate
        candidate = {
            "id": "test-candidate-1",
            "kind": "automation",
            "label": "Test Candidate",
            "score": 0.9
        }
        r1 = client.post("/api/v1/candidates", json=candidate)
        self.assertEqual(r1.status_code, 200)
        
        # Get candidate
        r2 = client.get("/api/v1/candidates/test-candidate-1")
        self.assertEqual(r2.status_code, 200)
        
        data = r2.get_json()
        self.assertIn("candidate", data)

    def test_error_handling_consistency(self):
        """Test error handling is consistent across endpoints."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Test 404 for non-existent resource
        r = client.get("/api/v1/candidates/nonexistent-id-12345")
        
        # Should either be 404 or return error in JSON
        if r.status_code == 404:
            self.assertIn("error", r.get_json())
        else:
            data = r.get_json()
            self.assertIn("ok", data)

    def test_index_lists_all_endpoints(self):
        """Test index endpoint lists available endpoints."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        
        text = r.get_data(as_text=True)
        
        # Should mention key endpoints
        self.assertIn("/health", text)
        self.assertIn("/version", text)
        self.assertIn("/api/v1", text)


if __name__ == "__main__":
    unittest.main()
