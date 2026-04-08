import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestGraphApi(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_graph_state_empty(self):
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

        # Reset lazy singleton between tests
        from copilot_core.brain_graph import provider

        provider._STORE = None
        provider._SVC = None

        client = app.test_client()
        r = client.get("/api/v1/graph/state")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual(j.get("version"), 1)
        self.assertIn("nodes", j)
        self.assertIn("edges", j)

    def test_snapshot_svg_placeholder(self):
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        r = client.get("/api/v1/graph/snapshot.svg")
        self.assertEqual(r.status_code, 200)
        self.assertIn("image/svg+xml", r.headers.get("Content-Type", ""))
        self.assertIn("no nodes yet", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
