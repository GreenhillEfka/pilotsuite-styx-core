import json
import os
import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestEventsIdempotency(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ingest_dedupes_by_idempotency_key_header_and_does_not_persist_duplicates(self):
        if create_app is None:
            self.skipTest("Flask not installed")

        app = create_app()

        # Configure events persistence to temp path
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

        client = app.test_client()
        payload = {"type": "test", "text": "hello"}

        r1 = client.post(
            "/api/v1/events",
            json=payload,
            headers={"Idempotency-Key": "abc123"},
        )
        self.assertEqual(r1.status_code, 200)
        j1 = r1.get_json()
        self.assertTrue(j1.get("ok"))
        self.assertTrue(j1.get("stored"))
        self.assertFalse(j1.get("deduped"))

        r2 = client.post(
            "/api/v1/events",
            json=payload,
            headers={"Idempotency-Key": "abc123"},
        )
        self.assertEqual(r2.status_code, 200)
        j2 = r2.get_json()
        self.assertTrue(j2.get("ok"))
        self.assertFalse(j2.get("stored"))
        self.assertTrue(j2.get("deduped"))

        # JSONL should have only one line
        with open(events_path, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]

        self.assertEqual(len(lines), 1)
        evt = json.loads(lines[0])
        self.assertEqual(evt.get("idempotency_key"), "abc123")


if __name__ == "__main__":
    unittest.main()
