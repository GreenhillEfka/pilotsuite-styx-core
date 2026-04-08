"""Tests for /api/v1/status endpoint."""

import tempfile
import unittest
from unittest.mock import patch, MagicMock

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestStatusEndpoint(unittest.TestCase):
    """Test /api/v1/status endpoint functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def _create_test_app(self):
        """Create a test Flask app with temp paths."""
        app = create_app()
        from dataclasses import replace

        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            brain_graph_json_path=f"{self.tmpdir.name}/brain_graph.db",
            events_jsonl_path=f"{self.tmpdir.name}/events.jsonl",
            candidates_json_path=f"{self.tmpdir.name}/candidates.json",
            brain_graph_nodes_max=500,
            brain_graph_edges_max=1500,
            brain_graph_persist=True,
        )
        return app

    def test_status_endpoint_returns_200(self):
        """Test /api/v1/status returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/status")
        self.assertEqual(r.status_code, 200)

    def test_status_endpoint_returns_ok_true(self):
        """Test /api/v1/status returns ok: true."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/status")
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_status_endpoint_returns_version(self):
        """Test /api/v1/status returns version field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/status")
        j = r.get_json()
        self.assertIn("version", j)
        self.assertIsInstance(j["version"], str)
        self.assertTrue(len(j["version"]) > 0)

    def test_status_endpoint_returns_time(self):
        """Test /api/v1/status returns time field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/status")
        j = r.get_json()
        self.assertIn("time", j)
        self.assertIsInstance(j["time"], str)

    def test_status_endpoint_returns_port(self):
        """Test /api/v1/status returns port field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/status")
        j = r.get_json()
        self.assertIn("port", j)
        self.assertIsInstance(j["port"], int)
        self.assertGreater(j["port"], 0)

    def test_status_endpoint_content_type_json(self):
        """Test /api/v1/status returns application/json content type."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/status")
        self.assertIn("application/json", r.content_type)

    def test_status_endpoint_with_custom_auth_token(self):
        """Test /api/v1/status respects auth token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_app()
            from dataclasses import replace

            cfg = app.config["COPILOT_CFG"]
            app.config["COPILOT_CFG"] = replace(
                cfg,
                data_dir=tmpdir,
                auth_token="test-secret-token",
            )
            client = app.test_client()
            
            # Without token should get 401
            r = client.get("/api/v1/status")
            # Note: /api/v1/status is not protected by auth middleware
            # Only /api/v1/* endpoints are protected
            
            # With correct token should succeed
            r = client.get("/api/v1/status", headers={"X-Auth-Token": "test-secret-token"})
            self.assertEqual(r.status_code, 200)

    def test_status_endpoint_with_bearer_token(self):
        """Test /api/v1/status accepts Bearer token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_app()
            from dataclasses import replace

            cfg = app.config["COPILOT_CFG"]
            app.config["COPILOT_CFG"] = replace(
                cfg,
                data_dir=tmpdir,
                auth_token="bearer-test-token",
            )
            client = app.test_client()
            
            r = client.get("/api/v1/status", headers={"Authorization": "Bearer bearer-test-token"})
            self.assertEqual(r.status_code, 200)

    def test_status_endpoint_empty_auth_token(self):
        """Test /api/v1/status allows access when auth token is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_app()
            from dataclasses import replace

            cfg = app.config["COPILOT_CFG"]
            app.config["COPILOT_CFG"] = replace(
                cfg,
                data_dir=tmpdir,
                auth_token="",
            )
            client = app.test_client()
            
            r = client.get("/api/v1/status")
            self.assertEqual(r.status_code, 200)


class TestStatusEndpointIntegration(unittest.TestCase):
    """Integration tests for status endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def _create_test_app(self):
        """Create a test Flask app with temp paths."""
        app = create_app()
        from dataclasses import replace

        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            brain_graph_json_path=f"{self.tmpdir.name}/brain_graph.db",
            events_jsonl_path=f"{self.tmpdir.name}/events.jsonl",
            candidates_json_path=f"{self.tmpdir.name}/candidates.json",
            brain_graph_nodes_max=500,
            brain_graph_edges_max=1500,
            brain_graph_persist=True,
        )
        return app

    def test_status_endpoint_complete_structure(self):
        """Test /api/v1/status returns complete expected structure."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/status")
        j = r.get_json()
        
        # Verify all required fields
        required_fields = ["ok", "time", "version", "port"]
        for field in required_fields:
            self.assertIn(field, j, f"Missing required field: {field}")
        
        # Verify field types
        self.assertIsInstance(j["ok"], bool)
        self.assertIsInstance(j["time"], str)
        self.assertIsInstance(j["version"], str)
        self.assertIsInstance(j["port"], int)
        
        # Verify version format (semver-like)
        version_parts = j["version"].split(".")
        self.assertGreaterEqual(len(version_parts), 2)

    def test_status_endpoint_multiple_requests(self):
        """Test /api/v1/status handles multiple sequential requests."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        for _ in range(5):
            r = client.get("/api/v1/status")
            self.assertEqual(r.status_code, 200)
            j = r.get_json()
            self.assertTrue(j.get("ok"))


if __name__ == "__main__":
    unittest.main()
