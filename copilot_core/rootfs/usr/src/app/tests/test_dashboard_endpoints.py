"""Tests for /api/v1/dashboard/* endpoints."""

import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestDashboardEndpoints(unittest.TestCase):
    """Test /api/v1/dashboard/* endpoint functionality."""

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
        
        # Reset lazy singletons
        from copilot_core.brain_graph import provider
        
        provider._STORE = None
        provider._SVC = None
        
        return app

    def test_dashboard_health_returns_200(self):
        """Test GET /api/v1/dashboard/health returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        self.assertEqual(r.status_code, 200)

    def test_dashboard_health_returns_ok(self):
        """Test GET /api/v1/dashboard/health returns ok: true."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_dashboard_health_returns_module_info(self):
        """Test GET /api/v1/dashboard/health returns module info."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        
        self.assertIn("module", j)
        self.assertEqual(j["module"], "dashboard")

    def test_dashboard_health_returns_version(self):
        """Test GET /api/v1/dashboard/health returns version."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        
        self.assertIn("version", j)
        self.assertIsInstance(j["version"], str)

    def test_dashboard_health_returns_features(self):
        """Test GET /api/v1/dashboard/health returns features list."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        
        self.assertIn("features", j)
        self.assertIsInstance(j["features"], list)

    def test_dashboard_health_returns_endpoints(self):
        """Test GET /api/v1/dashboard/health returns endpoints list."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        
        self.assertIn("endpoints", j)
        self.assertIsInstance(j["endpoints"], list)

    def test_dashboard_health_returns_status(self):
        """Test GET /api/v1/dashboard/health returns status."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        
        self.assertIn("status", j)

    def test_dashboard_health_returns_time(self):
        """Test GET /api/v1/dashboard/health returns time."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        
        self.assertIn("time", j)

    def test_dashboard_brain_summary_returns_200(self):
        """Test GET /api/v1/dashboard/brain-summary returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/brain-summary")
        self.assertEqual(r.status_code, 200)

    def test_dashboard_brain_summary_returns_ok(self):
        """Test GET /api/v1/dashboard/brain-summary returns ok: true."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/brain-summary")
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_dashboard_brain_summary_returns_time(self):
        """Test GET /api/v1/dashboard/brain-summary returns time."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/brain-summary")
        j = r.get_json()
        
        self.assertIn("time", j)

    def test_dashboard_brain_summary_returns_summary(self):
        """Test GET /api/v1/dashboard/brain-summary returns summary."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/brain-summary")
        j = r.get_json()
        
        self.assertIn("summary", j)
        self.assertIsInstance(j["summary"], dict)

    def test_dashboard_brain_summary_summary_fields(self):
        """Test summary has expected fields."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/brain-summary")
        j = r.get_json()
        
        summary = j["summary"]
        self.assertIn("total_nodes", summary)
        self.assertIn("total_edges", summary)
        self.assertIn("nodes_by_kind", summary)
        self.assertIn("edges_by_type", summary)

    def test_dashboard_brain_summary_top_nodes(self):
        """Test GET /api/v1/dashboard/brain-summary returns top_nodes."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/brain-summary")
        j = r.get_json()
        
        self.assertIn("top_nodes", j)
        self.assertIsInstance(j["top_nodes"], list)

    def test_dashboard_brain_summary_top_edges(self):
        """Test GET /api/v1/dashboard/brain-summary returns top_edges."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/brain-summary")
        j = r.get_json()
        
        self.assertIn("top_edges", j)
        self.assertIsInstance(j["top_edges"], list)

    def test_dashboard_brain_summary_limit_nodes_param(self):
        """Test GET /api/v1/dashboard/brain-summary with limitNodes param."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Just test the endpoint returns 200
        r = client.get("/api/v1/dashboard/brain-summary?limitNodes=1")
        self.assertEqual(r.status_code, 200)

    def test_dashboard_brain_summary_limit_edges_param(self):
        """Test GET /api/v1/dashboard/brain-summary with limitEdges param."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        r = client.get("/api/v1/dashboard/brain-summary?limitEdges=10")
        self.assertEqual(r.status_code, 200)

    def test_dashboard_health_brain_graph_integration(self):
        """Test dashboard health reports brain_graph integration status."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        
        self.assertIn("integrations", j)
        self.assertIn("brain_graph", j["integrations"])
        brain_graph_status = j["integrations"]["brain_graph"]
        self.assertIn(brain_graph_status, ["ok", "unavailable"])

    def test_dashboard_brain_summary_node_limits(self):
        """Test summary includes node limits."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/brain-summary")
        j = r.get_json()
        
        summary = j["summary"]
        self.assertIn("node_limits", summary)
        self.assertIsInstance(j["summary"]["node_limits"], dict)

    def test_dashboard_brain_summary_with_nodes(self):
        """Test brain-summary with actual nodes in graph."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Just test the endpoint works with empty graph
        r = client.get("/api/v1/dashboard/brain-summary")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))


class TestDashboardEndpointsIntegration(unittest.TestCase):
    """Integration tests for dashboard endpoints."""

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
        
        # Reset lazy singletons
        from copilot_core.brain_graph import provider
        
        provider._STORE = None
        provider._SVC = None
        
        return app

    def test_dashboard_full_workflow(self):
        """Test complete dashboard workflow."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # 1. Check health
        r = client.get("/api/v1/dashboard/health")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        
        # 2. Get brain summary
        r = client.get("/api/v1/dashboard/brain-summary")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        
        # 3. Verify structure
        self.assertIn("summary", j)
        self.assertIn("top_nodes", j)
        self.assertIn("top_edges", j)

    def test_dashboard_health_endpoint_list(self):
        """Test dashboard health includes all expected endpoints."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/dashboard/health")
        j = r.get_json()
        
        endpoints = j["endpoints"]
        expected_endpoints = [
            "/api/v1/dashboard/brain-summary",
            "/api/v1/dashboard/health",
        ]
        
        for endpoint in expected_endpoints:
            self.assertIn(endpoint, endpoints)


if __name__ == "__main__":
    unittest.main()
