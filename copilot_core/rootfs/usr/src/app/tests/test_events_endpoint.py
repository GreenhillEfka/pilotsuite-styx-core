"""Tests for /api/v1/events endpoint."""

import json
import os
import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestEventsEndpoint(unittest.TestCase):
    """Test /api/v1/events endpoint functionality."""

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
        events_path = os.path.join(self.tmpdir.name, "events.jsonl")
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            events_persist=True,
            events_jsonl_path=events_path,
            events_cache_max=50,
            events_idempotency_ttl_seconds=20 * 60,
            events_idempotency_lru_max=10_000,
        )

        # Reset lazy singletons between tests
        from copilot_core.api.v1 import events as events_api
        events_api._STORE = None
        from copilot_core.brain_graph import provider as graph_provider
        graph_provider._STORE = None
        graph_provider._SVC = None

        return app

    def test_events_endpoint_returns_200(self):
        """Test /api/v1/events POST returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        self.assertEqual(r.status_code, 200)

    def test_events_endpoint_returns_ok_true(self):
        """Test /api/v1/events returns ok: true."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_events_endpoint_returns_stored_true(self):
        """Test /api/v1/events returns stored: true for new event."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        j = r.get_json()
        self.assertTrue(j.get("stored"))

    def test_events_endpoint_returns_event(self):
        """Test /api/v1/events returns event object."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        j = r.get_json()
        self.assertIn("event", j)
        self.assertIsInstance(j["event"], dict)

    def test_events_endpoint_event_has_type(self):
        """Test returned event has type field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test_event", "text": "hello"})
        j = r.get_json()
        self.assertEqual(j["event"]["type"], "test_event")

    def test_events_endpoint_event_has_timestamp(self):
        """Test returned event has timestamp field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        j = r.get_json()
        # Event has 'ts' or 'timestamp' field
        event = j["event"]
        self.assertTrue("ts" in event or "timestamp" in event)

    def test_events_endpoint_event_has_id(self):
        """Test returned event has id field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        j = r.get_json()
        self.assertIn("id", j["event"])
        self.assertIsInstance(j["event"]["id"], str)
        self.assertTrue(len(j["event"]["id"]) > 0)

    def test_events_endpoint_returns_graph_stats(self):
        """Test /api/v1/events returns graph stats."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        j = r.get_json()
        self.assertIn("graph", j)
        self.assertIn("nodes_touched", j["graph"])

    def test_events_endpoint_content_type_json(self):
        """Test /api/v1/events returns application/json content type."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        self.assertIn("application/json", r.content_type)

    def test_events_endpoint_batch_items(self):
        """Test /api/v1/events accepts batch items."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={
            "items": [
                {"type": "test1", "text": "hello"},
                {"type": "test2", "text": "world"}
            ]
        })
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertEqual(j.get("ingested"), 2)

    def test_events_endpoint_batch_stores_all(self):
        """Test /api/v1/events batch stores all valid events."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={
            "items": [
                {"type": "test1", "text": "hello"},
                {"type": "test2", "text": "world"},
                {"type": "test3"}  # Valid dict
            ]
        })
        j = r.get_json()
        self.assertEqual(j.get("ingested"), 3)

    def test_events_endpoint_ignores_invalid_batch_items(self):
        """Test /api/v1/events ignores invalid items in batch."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={
            "items": [
                "not a dict",
                123,
                {"type": "valid", "text": "hello"}
            ]
        })
        j = r.get_json()
        self.assertEqual(j.get("ingested"), 1)

    def test_events_endpoint_rejects_non_dict(self):
        """Test /api/v1/events rejects non-dict payload."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json="just a string")
        self.assertEqual(r.status_code, 400)

    def test_events_endpoint_rejects_non_dict_in_batch(self):
        """Test /api/v1/events rejects non-dict in batch items."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"items": ["string", 123]})
        self.assertEqual(r.status_code, 200)  # Invalid items are filtered

    def test_events_endpoint_idempotency_key_header(self):
        """Test /api/v1/events supports Idempotency-Key header."""
        if create_app is None:
            self.skipTest("Flassk not installed")
        app = self._create_test_app()
        client = app.test_client()

        r1 = client.post(
            "/api/v1/events",
            json={"type": "test", "text": "hello"},
            headers={"Idempotency-Key": "unique-key-123"}
        )
        self.assertTrue(r1.get_json().get("stored"))

        r2 = client.post(
            "/api/v1/events",
            json={"type": "test", "text": "hello"},
            headers={"Idempotency-Key": "unique-key-123"}
        )
        self.assertFalse(r2.get_json().get("stored"))
        self.assertTrue(r2.get_json().get("deduped"))

    def test_events_endpoint_x_idempotency_key_header(self):
        """Test /api/v1/events supports X-Idempotency-Key header."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r1 = client.post(
            "/api/v1/events",
            json={"type": "test", "text": "hello"},
            headers={"X-Idempotency-Key": "x-key-456"}
        )
        self.assertTrue(r1.get_json().get("stored"))

        r2 = client.post(
            "/api/v1/events",
            json={"type": "test", "text": "hello"},
            headers={"X-Idempotency-Key": "x-key-456"}
        )
        self.assertFalse(r2.get_json().get("stored"))

    def test_events_endpoint_x_event_id_header(self):
        """Test /api/v1/events supports X-Event-Id header."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        r1 = client.post(
            "/api/v1/events",
            json={"type": "test", "text": "hello"},
            headers={"X-Event-Id": "event-id-789"}
        )
        self.assertTrue(r1.get_json().get("stored"))

        r2 = client.post(
            "/api/v1/events",
            json={"type": "test", "text": "hello"},
            headers={"X-Event-Id": "event-id-789"}
        )
        self.assertFalse(r2.get_json().get("stored"))

    def test_events_endpoint_get_list_returns_200(self):
        """Test /api/v1/events GET returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/events")
        self.assertEqual(r.status_code, 200)

    def test_events_endpoint_get_returns_ok_true(self):
        """Test /api/v1/events GET returns ok: true."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/events")
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_events_endpoint_get_returns_count(self):
        """Test /api/v1/events GET returns count field."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Add some events first
        client.post("/api/v1/events", json={"type": "test1", "text": "hello"})
        client.post("/api/v1/events", json={"type": "test2", "text": "world"})
        
        r = client.get("/api/v1/events")
        j = r.get_json()
        self.assertIn("count", j)
        self.assertEqual(j["count"], 2)

    def test_events_endpoint_get_returns_items(self):
        """Test /api/v1/events GET returns items array."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        client.post("/api/v1/events", json={"type": "test", "text": "hello"})
        
        r = client.get("/api/v1/events")
        j = r.get_json()
        self.assertIn("items", j)
        self.assertIsInstance(j["items"], list)

    def test_events_endpoint_get_respects_limit(self):
        """Test /api/v1/events GET respects limit parameter."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Add 5 events
        for i in range(5):
            client.post("/api/v1/events", json={"type": "test", "index": i})
        
        r = client.get("/api/v1/events?limit=2")
        j = r.get_json()
        self.assertEqual(len(j["items"]), 2)

    def test_events_endpoint_get_default_limit(self):
        """Test /api/v1/events GET has default limit of 50."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Add 60 events
        for i in range(60):
            client.post("/api/v1/events", json={"type": "test", "index": i})
        
        r = client.get("/api/v1/events")
        j = r.get_json()
        # Should return at most 50 (default limit)
        self.assertLessEqual(len(j["items"]), 50)


class TestEventsEndpointPersistence(unittest.TestCase):
    """Test events persistence functionality."""

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
        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            events_persist=True,
            events_jsonl_path=events_path,
            events_cache_max=50,
        )

        # Reset lazy singletons between tests
        from copilot_core.api.v1 import events as events_api
        events_api._STORE = None
        from copilot_core.brain_graph import provider as graph_provider
        graph_provider._STORE = None
        graph_provider._SVC = None

        return app

    def test_events_persist_to_jsonl(self):
        """Test events are persisted to JSONL file."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        events_path = os.path.join(self.tmpdir.name, "events.jsonl")

        client.post("/api/v1/events", json={"type": "test", "text": "hello"})

        # Check file exists and has content
        self.assertTrue(os.path.exists(events_path))
        with open(events_path, "r") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1)

    def test_events_persistence_multiple_events(self):
        """Test multiple events are persisted correctly."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        events_path = os.path.join(self.tmpdir.name, "events.jsonl")

        client.post("/api/v1/events", json={"type": "test1", "text": "hello"})
        client.post("/api/v1/events", json={"type": "test2", "text": "world"})

        with open(events_path, "r") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 2)

    def test_events_persistence_contains_valid_json(self):
        """Test persisted events are valid JSON."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()

        events_path = os.path.join(self.tmpdir.name, "events.jsonl")

        client.post("/api/v1/events", json={"type": "test", "text": "hello"})

        with open(events_path, "r") as f:
            line = f.readline()
        evt = json.loads(line)
        self.assertEqual(evt["type"], "test")
        self.assertEqual(evt["text"], "hello")


if __name__ == "__main__":
    unittest.main()
