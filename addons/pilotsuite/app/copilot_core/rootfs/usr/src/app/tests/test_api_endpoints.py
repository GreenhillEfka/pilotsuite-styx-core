"""API Endpoint Tests for /api/v1/* endpoints."""

import tempfile
import unittest
from unittest.mock import patch, MagicMock

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestAPIEndpoints(unittest.TestCase):
    """Test all API v1 endpoints."""

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
        from copilot_core.api.v1 import events as events_api

        provider._STORE = None
        provider._SVC = None
        events_api._STORE = None

        return app

    def test_health_endpoint(self):
        """Test /health endpoint returns OK."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_version_endpoint(self):
        """Test /version endpoint returns version info."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        r = client.get("/version")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertIn("version", j)
        self.assertIn("time", j)

    def test_capabilities_endpoint(self):
        """Test /api/v1/capabilities endpoint."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("modules", j)
        self.assertIn("events", j["modules"])
        self.assertIn("brain_graph", j["modules"])

    def test_events_post_single(self):
        """Test POST /api/v1/events with single event."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        payload = {"type": "test_event", "entity_id": "light.test"}
        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_events_post_batch(self):
        """Test POST /api/v1/events with batch of events."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        payload = {
            "items": [
                {"type": "test_event", "entity_id": "light.test1"},
                {"type": "test_event", "entity_id": "light.test2"},
            ]
        }
        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("ingested", j)

    def test_events_get_list(self):
        """Test GET /api/v1/events list."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        # First post an event
        client.post("/api/v1/events", json={"type": "test", "entity_id": "light.test"})
        # Then list events
        r = client.get("/api/v1/events")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("items", j)

    def test_graph_state_endpoint(self):
        """Test GET /api/v1/graph/state."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/graph/state")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertIn("version", j)
        self.assertIn("nodes", j)
        self.assertIn("edges", j)

    def test_graph_state_with_filters(self):
        """Test GET /api/v1/graph/state with filters."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/graph/state?kind=entity&limitNodes=10")
        self.assertEqual(r.status_code, 200)

    def test_graph_snapshot_svg(self):
        """Test GET /api/v1/graph/snapshot.svg."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/graph/snapshot.svg")
        self.assertEqual(r.status_code, 200)
        self.assertIn("image/svg+xml", r.headers.get("Content-Type", ""))

    def test_candidates_post(self):
        """Test POST /api/v1/candidates."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        payload = {
            "id": "test_cand_1",
            "kind": "test",
            "label": "Test Candidate",
            "score": 0.8,
        }
        r = client.post("/api/v1/candidates", json=payload)
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_candidates_get_list(self):
        """Test GET /api/v1/candidates."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        # First post a candidate
        client.post("/api/v1/candidates", json={"id": "c1", "kind": "test", "label": "C1"})
        # Then list
        r = client.get("/api/v1/candidates")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("items", j)

    def test_candidates_get_by_id(self):
        """Test GET /api/v1/candidates/<id>."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        client.post("/api/v1/candidates", json={"id": "c1", "kind": "test", "label": "C1"})
        r = client.get("/api/v1/candidates/c1")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("candidate", j)

    def test_candidates_delete(self):
        """Test DELETE /api/v1/candidates/<id>."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        client.post("/api/v1/candidates", json={"id": "c1", "kind": "test", "label": "C1"})
        r = client.delete("/api/v1/candidates/c1")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_candidates_graph(self):
        """Test GET /api/v1/candidates/graph_candidates."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/candidates/graph_candidates")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_mood_score_post(self):
        """Test POST /api/v1/mood/score."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/mood/score", json={})
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("mood", j)

    def test_mood_state_get(self):
        """Test GET /api/v1/mood/state."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/mood/state")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_dev_status(self):
        """Test GET /api/v1/dev/status."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        r = client.get("/api/v1/dev/status")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_dev_logs_post(self):
        """Test POST /api/v1/dev/logs."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        payload = {"message": "test log"}
        r = client.post("/api/v1/dev/logs", json=payload)
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_dev_logs_get(self):
        """Test GET /api/v1/dev/logs."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        r = client.get("/api/v1/dev/logs")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))


if __name__ == "__main__":
    unittest.main()
