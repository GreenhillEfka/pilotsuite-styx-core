"""Integration tests for end-to-end flows."""

import tempfile
import unittest
import os

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestEndToEndPipeline(unittest.TestCase):
    """Test complete event processing pipeline."""

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

        events_path = os.path.join(self.tmpdir.name, "events.jsonl")
        brain_path = os.path.join(self.tmpdir.name, "brain.db")
        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            events_persist=True,
            events_jsonl_path=events_path,
            events_cache_max=50,
            brain_graph_persist=True,
            brain_graph_json_path=brain_path,
        )

        # Reset lazy singletons between tests
        from copilot_core.api.v1 import events as events_api
        events_api._STORE = None
        from copilot_core.brain_graph import provider as graph_provider
        graph_provider._STORE = None
        graph_provider._SVC = None

        return app

    def test_event_ingest_to_brain_graph_flow(self):
        """Test event flows from ingest to brain graph."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        # Ingest event
        r = client.post("/api/v1/events", json={
            "type": "state_changed",
            "entity_id": "light.living_room",
            "domain": "light",
            "new_state": "on"
        })
        
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        
        # Check graph was updated
        self.assertIn("graph", j)
        self.assertIn("nodes_touched", j["graph"])

    def test_event_batch_to_brain_graph_flow(self):
        """Test batch events flow to brain graph."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        # Ingest batch events
        r = client.post("/api/v1/events", json={
            "items": [
                {"type": "state_changed", "entity_id": "light.kitchen", "domain": "light", "new_state": "on"},
                {"type": "state_changed", "entity_id": "light.bedroom", "domain": "light", "new_state": "off"},
                {"type": "state_changed", "entity_id": "switch.fan", "domain": "switch", "new_state": "on"}
            ]
        })
        
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual(j.get("ingested"), 3)

    def test_event_list_after_ingest(self):
        """Test events can be listed after ingestion."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        # Ingest events
        client.post("/api/v1/events", json={"type": "test1", "data": "hello"})
        client.post("/api/v1/events", json={"type": "test2", "data": "world"})

        # List events
        r = client.get("/api/v1/events")
        j = r.get_json()
        
        self.assertEqual(j.get("count"), 2)
        self.assertEqual(len(j.get("items", [])), 2)

    def test_event_idempotency_in_pipeline(self):
        """Test idempotency works in full pipeline."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        payload = {"type": "test", "data": "unique"}
        
        # First request
        r1 = client.post("/api/v1/events", json=payload, headers={"Idempotency-Key": "test-idemp-123"})
        self.assertTrue(r1.get_json().get("stored"))
        
        # Duplicate request
        r2 = client.post("/api/v1/events", json=payload, headers={"Idempotency-Key": "test-idemp-123"})
        self.assertFalse(r2.get_json().get("stored"))
        self.assertTrue(r2.get_json().get("deduped"))

        # Only one event should be stored
        r = client.get("/api/v1/events")
        self.assertEqual(r.get_json().get("count"), 1)


class TestStatusCapabilitiesPipeline(unittest.TestCase):
    """Test status and capabilities endpoints together."""

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
            brain_graph_json_path=f"{self.tmpdir.name}/brain.db",
            events_jsonl_path=f"{self.tmpdir.name}/events.jsonl",
            candidates_json_path=f"{self.tmpdir.name}/candidates.json",
        )
        return app

    def test_status_and_capabilities_consistent(self):
        """Test status and capabilities return consistent info."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        # Get status
        status_r = client.get("/api/v1/status")
        status_j = status_r.get_json()
        
        # Get capabilities
        caps_r = client.get("/api/v1/capabilities")
        caps_j = caps_r.get_json()
        
        # Both should succeed
        self.assertEqual(status_r.status_code, 200)
        self.assertEqual(caps_r.status_code, 200)
        
        # Version should match
        self.assertEqual(status_j.get("version"), caps_j.get("version"))

    def test_status_has_all_required_fields(self):
        """Test status endpoint has all required fields."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r = client.get("/api/v1/status")
        j = r.get_json()
        
        required = ["ok", "version", "time", "port"]
        for field in required:
            self.assertIn(field, j)

    def test_capabilities_has_all_modules(self):
        """Test capabilities returns all expected modules."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r = client.get("/api/v1/capabilities")
        j = r.get_json()
        
        # API returns capabilities as list and features as dict
        capabilities = j.get("capabilities", [])
        features = j.get("features", {})
        
        # Check we have capabilities
        self.assertIsInstance(capabilities, list)
        self.assertGreater(len(capabilities), 0)
        
        # Check expected capabilities are present
        expected_caps = ["events", "candidates", "mood", "habitus"]
        for cap in expected_caps:
            self.assertIn(cap, capabilities)
        
        # Check features
        self.assertIn("brain_graph", features)


class TestMultiEndpointFlow(unittest.TestCase):
    """Test flows involving multiple endpoints."""

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

        events_path = os.path.join(self.tmpdir.name, "events.jsonl")
        brain_path = os.path.join(self.tmpdir.name, "brain.db")
        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            events_persist=True,
            events_jsonl_path=events_path,
            events_cache_max=50,
            brain_graph_persist=True,
            brain_graph_json_path=brain_path,
        )

        # Reset lazy singletons
        from copilot_core.api.v1 import events as events_api
        events_api._STORE = None

        return app

    def test_health_check_flow(self):
        """Test health check works."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r = client.get("/health")
        j = r.get_json()
        
        self.assertEqual(r.status_code, 200)
        self.assertTrue(j.get("ok"))

    def test_version_endpoint(self):
        """Test version endpoint."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r = client.get("/version")
        j = r.get_json()
        
        self.assertEqual(r.status_code, 200)
        self.assertIn("version", j)

    def test_root_endpoint(self):
        """Test root endpoint returns info."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r = client.get("/")
        
        self.assertEqual(r.status_code, 200)
        # Should contain some expected strings
        self.assertIn(b"PilotSuite", r.data)

    def test_events_with_invalid_payload(self):
        """Test events endpoint handles invalid payload."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        # String payload should fail
        r = client.post("/api/v1/events", json="not an object")
        self.assertEqual(r.status_code, 400)

    def test_events_list_with_limit(self):
        """Test events list respects limit parameter."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        # Add 10 events
        for i in range(10):
            client.post("/api/v1/events", json={"type": "test", "index": i})

        # Request only 3
        r = client.get("/api/v1/events?limit=3")
        j = r.get_json()
        
        self.assertEqual(len(j.get("items", [])), 3)


class TestErrorHandling(unittest.TestCase):
    """Test error handling across endpoints."""

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
            brain_graph_json_path=f"{self.tmpdir.name}/brain.db",
            events_jsonl_path=f"{self.tmpdir.name}/events.jsonl",
            candidates_json_path=f"{self.tmpdir.name}/candidates.json",
        )
        return app

    def test_status_returns_json(self):
        """Test status returns proper JSON."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r = client.get("/api/v1/status")
        
        self.assertIn("application/json", r.content_type)

    def test_capabilities_returns_json(self):
        """Test capabilities returns proper JSON."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r = client.get("/api/v1/capabilities")
        
        self.assertIn("application/json", r.content_type)

    def test_events_returns_json_on_error(self):
        """Test events returns proper JSON on error."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r = client.post("/api/v1/events", json="string")
        
        self.assertIn("application/json", r.content_type)


class TestConcurrentRequests(unittest.TestCase):
    """Test handling of concurrent requests."""

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

        events_path = os.path.join(self.tmpdir.name, "events.jsonl")
        brain_path = os.path.join(self.tmpdir.name, "brain.db")
        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            events_persist=True,
            events_jsonl_path=events_path,
            events_cache_max=50,
            brain_graph_persist=True,
            brain_graph_json_path=brain_path,
        )

        # Reset lazy singletons
        from copilot_core.api.v1 import events as events_api
        events_api._STORE = None
        from copilot_core.brain_graph import provider as graph_provider
        graph_provider._STORE = None
        graph_provider._SVC = None

        return app

    def test_sequential_event_ingestion(self):
        """Test sequential event ingestion works correctly."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        # Ingest 5 events sequentially
        for i in range(5):
            r = client.post("/api/v1/events", json={"type": "test", "index": i})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.get_json().get("ok"))

        # Verify all stored
        r = client.get("/api/v1/events")
        self.assertEqual(r.get_json().get("count"), 5)

    def test_sequential_status_requests(self):
        """Test multiple status requests return consistent data."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        versions = []
        for _ in range(3):
            r = client.get("/api/v1/status")
            versions.append(r.get_json().get("version"))

        # All versions should be the same
        self.assertEqual(len(set(versions)), 1)


if __name__ == "__main__":
    unittest.main()
