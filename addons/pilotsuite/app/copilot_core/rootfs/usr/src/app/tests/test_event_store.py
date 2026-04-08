"""Tests for copilot_core.ingest.event_store – standalone (no Flask needed)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

# Ensure copilot_core is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copilot_core.ingest.event_store import EventStore


def _make_event(
    entity_id: str = "light.test",
    kind: str = "state_changed",
    src: str = "ha",
    ts: str = "2026-02-10T03:00:00Z",
    old_state: str = "off",
    new_state: str = "on",
    event_id: str | None = None,
    zone_ids: list[str] | None = None,
) -> dict:
    """Helper to build a valid forwarder-style event envelope."""
    ev: dict = {
        "ts": ts,
        "type": kind,
        "source": src,
        "entity_id": entity_id,
        "attributes": {
            "domain": entity_id.split(".", 1)[0],
            "old_state": old_state,
            "new_state": new_state,
            "zone_ids": zone_ids or ["test_zone"],
            "state_attributes": {},
        },
    }
    if event_id:
        ev["id"] = event_id
    return ev


class TestEventStoreValidation(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.store = EventStore(
            store_path=os.path.join(self._tmpdir, "events.jsonl"),
            max_events=100,
            dedup_ttl=60,
        )

    def test_valid_event_passes(self):
        ev = _make_event()
        err = self.store.validate_event(ev)
        self.assertIsNone(err)

    def test_missing_kind_rejected(self):
        ev = {"ts": "2026-01-01T00:00:00Z", "source": "ha", "entity_id": "light.x"}
        err = self.store.validate_event(ev)
        self.assertIn("kind", err)

    def test_missing_source_rejected(self):
        ev = {"ts": "2026-01-01T00:00:00Z", "type": "state_changed", "entity_id": "light.x"}
        err = self.store.validate_event(ev)
        self.assertIn("src", err)

    def test_missing_entity_id_rejected(self):
        ev = {"ts": "2026-01-01T00:00:00Z", "type": "state_changed", "source": "ha"}
        err = self.store.validate_event(ev)
        self.assertIn("entity_id", err)

    def test_heartbeat_without_entity_id_ok(self):
        ev = {"ts": "2026-01-01T00:00:00Z", "kind": "heartbeat", "src": "ha", "entity_count": 42}
        err = self.store.validate_event(ev)
        self.assertIsNone(err)

    def test_unsupported_source_rejected(self):
        ev = {"ts": "2026-01-01T00:00:00Z", "type": "state_changed", "source": "evil", "entity_id": "x.y"}
        err = self.store.validate_event(ev)
        self.assertIn("source", err)


class TestEventStoreIngest(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.store = EventStore(
            store_path=os.path.join(self._tmpdir, "events.jsonl"),
            max_events=50,
            dedup_ttl=60,
        )

    def test_ingest_single_event(self):
        result = self.store.ingest_batch([_make_event()])
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["rejected"], 0)
        self.assertEqual(result["deduped"], 0)

    def test_ingest_dedup(self):
        ev = _make_event(event_id="test:123")
        r1 = self.store.ingest_batch([ev])
        self.assertEqual(r1["accepted"], 1)
        r2 = self.store.ingest_batch([ev])
        self.assertEqual(r2["deduped"], 1)
        self.assertEqual(r2["accepted"], 0)

    def test_ingest_mixed_valid_invalid(self):
        good = _make_event()
        bad = {"ts": "x"}  # missing kind, source, entity_id
        result = self.store.ingest_batch([good, bad])
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["rejected"], 1)

    def test_ingest_batch_persists_jsonl(self):
        events = [_make_event(entity_id=f"light.test_{i}", event_id=f"id:{i}") for i in range(5)]
        self.store.ingest_batch(events)

        path = os.path.join(self._tmpdir, "events.jsonl")
        with open(path, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 5)

        # Verify JSON validity
        for line in lines:
            parsed = json.loads(line)
            self.assertIn("kind", parsed)
            self.assertIn("ingested_at", parsed)

    def test_ring_buffer_bounded(self):
        # Store max=50, ingest 60 events
        events = [
            _make_event(entity_id=f"light.t_{i}", event_id=f"ev:{i}")
            for i in range(60)
        ]
        self.store.ingest_batch(events)
        stats = self.store.stats()
        self.assertLessEqual(stats["buffered"], 50)


class TestEventStoreQuery(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.store = EventStore(
            store_path=os.path.join(self._tmpdir, "events.jsonl"),
            max_events=100,
            dedup_ttl=60,
        )
        # Seed events
        events = [
            _make_event(entity_id="light.kitchen", event_id="e:1", zone_ids=["kitchen"]),
            _make_event(entity_id="light.bedroom", event_id="e:2", zone_ids=["bedroom"]),
            _make_event(entity_id="sensor.temp", event_id="e:3", kind="state_changed"),
        ]
        self.store.ingest_batch(events)

    def test_query_all(self):
        results = self.store.query()
        self.assertEqual(len(results), 3)

    def test_query_by_domain(self):
        results = self.store.query(domain="light")
        self.assertEqual(len(results), 2)

    def test_query_by_entity_id(self):
        results = self.store.query(entity_id="light.kitchen")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["entity_id"], "light.kitchen")

    def test_query_by_zone(self):
        results = self.store.query(zone_id="bedroom")
        self.assertEqual(len(results), 1)

    def test_query_limit(self):
        results = self.store.query(limit=2)
        self.assertEqual(len(results), 2)


class TestEventStoreNormalization(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.store = EventStore(
            store_path=os.path.join(self._tmpdir, "events.jsonl"),
            max_events=100,
            dedup_ttl=0,  # disable dedup for normalization tests
        )

    def test_forwarder_format_normalized(self):
        """Current HA forwarder format (type/source/attributes) is normalized to canonical."""
        ev = _make_event(old_state="off", new_state="on")
        self.store.ingest_batch([ev])
        stored = self.store.query()[0]

        self.assertEqual(stored["kind"], "state_changed")
        self.assertEqual(stored["src"], "ha")
        self.assertIn("old", stored)
        self.assertIn("new", stored)
        self.assertEqual(stored["old"]["state"], "off")
        self.assertEqual(stored["new"]["state"], "on")
        self.assertIn("ingested_at", stored)
        self.assertEqual(stored["v"], 1)

    def test_n3_spec_format_normalized(self):
        """N3 spec format (kind/src/old/new objects) is also accepted."""
        ev = {
            "v": 1,
            "ts": "2026-02-10T03:00:00Z",
            "kind": "state_changed",
            "src": "ha",
            "entity_id": "light.test",
            "domain": "light",
            "old": {"state": "off", "attrs": {}},
            "new": {"state": "on", "attrs": {"brightness": 180}},
            "context_id": "abcdef123456789",
            "trigger": "user",
        }
        self.store.ingest_batch([ev])
        stored = self.store.query()[0]

        self.assertEqual(stored["kind"], "state_changed")
        self.assertEqual(stored["new"]["state"], "on")
        self.assertEqual(stored["new"]["attrs"]["brightness"], 180)
        # Context ID truncated to 12 chars
        self.assertEqual(stored["context_id"], "abcdef123456")
        self.assertEqual(stored["trigger"], "user")

    def test_call_service_normalized(self):
        ev = {
            "ts": "2026-02-10T03:00:00Z",
            "type": "call_service",
            "source": "ha",
            "entity_id": "light.test",
            "id": "cs:1",
            "attributes": {
                "domain": "light",
                "service": "turn_on",
                "entity_ids": ["light.test"],
                "zone_ids": ["living_room"],
            },
        }
        self.store.ingest_batch([ev])
        stored = self.store.query()[0]

        self.assertEqual(stored["kind"], "call_service")
        self.assertEqual(stored["service"]["service"], "turn_on")
        self.assertEqual(stored["zone_ids"], ["living_room"])


if __name__ == "__main__":
    unittest.main()
