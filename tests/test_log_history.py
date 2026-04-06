"""Log & History Tests — Slice 279 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestLogHistory(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_logs_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/logs/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_recent_logs(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/logs/recent")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_history_events(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/history/events")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_history_stats(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/history/stats")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
