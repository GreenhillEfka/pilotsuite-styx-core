"""Tests for /api/v1/events endpoint (canonical events_ingest lane).

This test suite validates the canonical event ingest endpoint at POST /api/v1/events
as implemented in copilot_core.api.v1.events_ingest.

Slice 1 Acceptance Criteria:
- one authoritative ingest route (/api/v1/events via events_ingest blueprint)
- one authoritative event store implementation (ingest/event_store.py)
- one authoritative path into Brain Graph / mining / module routing
"""

import json
import os
import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestEventsIngestEndpoint(unittest.TestCase):
    """Test /api/v1/events canonical ingest endpoint functionality."""

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

        # Reset lazy singletons between tests (canonical events_ingest module)
        from copilot_core.api.v1 import events_ingest as events_ingest_api
        events_ingest_api._store = None
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
        r = client.post("/api/v1/events", json={"items": [{"type": "test", "text": "hello"}]})
        self.assertEqual(r.status_code, 200)

    def test_events_endpoint_returns_accepted_count(self):
        """Test /api/v1/events returns accepted count."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"items": [{"type": "test", "text": "hello"}]})
        j = r.get_json()
        self.assertIn("accepted", j)
        self.assertEqual(j["accepted"], 1)

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
        self.assertEqual(j.get("accepted"), 2)

    def test_events_endpoint_empty_batch(self):
        """Test /api/v1/events handles empty batch gracefully."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.post("/api/v1/events", json={"items": []})
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual(j.get("accepted"), 0)
        self.assertEqual(j.get("rejected"), 0)
        self.assertEqual(j.get("deduped"), 0)

    def test_events_endpoint_get_list_returns_200(self):
        """Test /api/v1/events GET returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/events")
        self.assertEqual(r.status_code, 200)

    def test_events_endpoint_get_returns_events_array(self):
        """Test /api/v1/events GET returns events array."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Add some events first
        client.post("/api/v1/events", json={"items": [{"type": "test1", "text": "hello"}]})
        client.post("/api/v1/events", json={"items": [{"type": "test2", "text": "world"}]})
        
        r = client.get("/api/v1/events")
        j = r.get_json()
        self.assertIn("events", j)
        self.assertIsInstance(j["events"], list)
        self.assertEqual(len(j["events"]), 2)

    def test_events_endpoint_get_respects_limit(self):
        """Test /api/v1/events GET respects limit parameter."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Add 5 events
        for i in range(5):
            client.post("/api/v1/events", json={"items": [{"type": "test", "index": i}]})
        
        r = client.get("/api/v1/events?limit=2")
        j = r.get_json()
        self.assertEqual(len(j["events"]), 2)

    def test_events_endpoint_stats_returns_200(self):
        """Test /api/v1/events/stats returns HTTP 200."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        r = client.get("/api/v1/events/stats")
        self.assertEqual(r.status_code, 200)

    def test_events_endpoint_stats_returns_buffered(self):
        """Test /api/v1/events/stats returns buffered count."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        # Add some events
        client.post("/api/v1/events", json={"items": [{"type": "test", "text": "hello"}]})
        
        r = client.get("/api/v1/events/stats")
        j = r.get_json()
        self.assertIn("buffered", j)
        self.assertGreaterEqual(j["buffered"], 1)


class TestEventsIngestValidation(unittest.TestCase):
    """Test event validation and normalization in canonical ingest lane."""

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
        )

        from copilot_core.api.v1 import events_ingest as events_ingest_api
        events_ingest_api._store = None
        return app

    def test_state_changed_event_accepted(self):
        """Test state_changed event is accepted and normalized."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        event = {
            "kind": "state_changed",
            "type": "state_changed",
            "source": "ha",
            "entity_id": "light.living_room",
            "ts": "2026-03-31T10:00:00Z",
            "attributes": {
                "domain": "light",
                "old_state": "off",
                "new_state": "on",
            }
        }
        r = client.post("/api/v1/events", json={"items": [event]})
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual(j["accepted"], 1)
        self.assertEqual(j["rejected"], 0)

    def test_call_service_event_accepted(self):
        """Test call_service event is accepted and normalized."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        event = {
            "kind": "call_service",
            "type": "call_service",
            "source": "ha",
            "ts": "2026-03-31T10:00:00Z",
            "attributes": {
                "domain": "light",
                "service": "turn_on",
                "entity_ids": ["light.living_room"],
            }
        }
        r = client.post("/api/v1/events", json={"items": [event]})
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual(j["accepted"], 1)

    def test_missing_kind_rejected(self):
        """Test event without kind/type is rejected."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        event = {"source": "ha", "ts": "2026-03-31T10:00:00Z"}
        r = client.post("/api/v1/events", json={"items": [event]})
        j = r.get_json()
        self.assertEqual(j["rejected"], 1)
        self.assertIn("errors", j)
        self.assertEqual(len(j["errors"]), 1)

    def test_missing_source_rejected(self):
        """Test event without source is rejected."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        event = {"kind": "state_changed", "ts": "2026-03-31T10:00:00Z"}
        r = client.post("/api/v1/events", json={"items": [event]})
        j = r.get_json()
        self.assertEqual(j["rejected"], 1)

    def test_missing_timestamp_rejected(self):
        """Test event without timestamp is rejected."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        event = {"kind": "state_changed", "source": "ha"}
        r = client.post("/api/v1/events", json={"items": [event]})
        j = r.get_json()
        self.assertEqual(j["rejected"], 1)


class TestEventsIngestIdempotency(unittest.TestCase):
    """Test idempotency/deduplication in canonical ingest lane."""

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

        from copilot_core.api.v1 import events_ingest as events_ingest_api
        events_ingest_api._store = None
        return app

    def test_duplicate_event_deduped(self):
        """Test duplicate event (same dedup key) is deduped."""
        if create_app is None:
            self.skipTest("Flask not installed")
        app = self._create_test_app()
        client = app.test_client()
        
        event = {
            "id": "unique-event-123",
            "kind": "state_changed",
            "source": "ha",
            "entity_id": "light.test",
            "ts": "2026-03-31T10:00:00Z",
        }
        
        # First submission
        r1 = client.post("/api/v1/events", json={"items": [event]})
        j1 = r1.get_json()
        self.assertEqual(j1["accepted"], 1)
        self.assertEqual(j1["deduped"], 0)
        
        # Second submission (same id)
        r2 = client.post("/api/v1/events", json={"items": [event]})
        j2 = r2.get_json()
        self.assertEqual(j2["accepted"], 0)
        self.assertEqual(j2["deduped"], 1)


if __name__ == "__main__":
    unittest.main()
