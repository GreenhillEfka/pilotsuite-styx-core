"""Stats & Analytics Tests — Slice 280 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestStatsAnalytics(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_stats_summary(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/stats/summary")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_analytics_daily(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/analytics/daily")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_analytics_trends(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/analytics/trends")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_export_analytics(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/analytics/export", json={"format": "csv"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
