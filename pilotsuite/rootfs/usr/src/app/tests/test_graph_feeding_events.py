import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestGraphFeedingFromEvents(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_graph_non_empty_after_ingest(self):
        if create_app is None:
            self.skipTest("Flask not installed")

        app = create_app()

        # Configure graph persistence to temp path
        from dataclasses import replace

        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            brain_graph_json_path=f"{self.tmpdir.name}/brain_graph.json",
        )

        # Reset lazy singletons between tests
        from copilot_core.api.v1 import events as events_api
        events_api._STORE = None
        from copilot_core.brain_graph import provider
        provider._STORE = None
        provider._SVC = None

        client = app.test_client()

        payload = {
            "items": [
                {
                    "id": "evt-1",
                    "ts": "2026-02-08T12:00:00Z",
                    "type": "state_changed",
                    "source": "home_assistant",
                    "entity_id": "light.kitchen",
                    "attributes": {"zone_ids": ["kitchen"]},
                },
                {
                    "id": "evt-2",
                    "ts": "2026-02-08T12:00:01Z",
                    "type": "call_service",
                    "source": "home_assistant",
                    "entity_id": "light.kitchen",
                    "attributes": {
                        "domain": "light",
                        "service": "turn_on",
                        "entity_ids": ["light.kitchen"],
                        "zone_ids": ["kitchen"],
                    },
                },
            ]
        }

        r = client.post("/api/v1/events", json=payload)
        self.assertEqual(r.status_code, 200)
        j = r.get_json() or {}
        self.assertTrue(j.get("ok"))
        self.assertEqual(j.get("ingested"), 2)

        r2 = client.get("/api/v1/graph/state")
        self.assertEqual(r2.status_code, 200)
        g = r2.get_json() or {}

        nodes = g.get("nodes") or []
        edges = g.get("edges") or []
        self.assertGreaterEqual(len(nodes), 2)
        self.assertGreaterEqual(len(edges), 1)

        node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
        self.assertIn("ha.entity:light.kitchen", node_ids)
        self.assertIn("zone:kitchen", node_ids)
        self.assertIn("ha.intent:light.turn_on", node_ids)


if __name__ == "__main__":
    unittest.main()
