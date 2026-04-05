"""Batch Contract Tests Part 1 — Slices 135-150."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestBatchPart1(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_shopping(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/shopping/suggestions").data)
            self.assertEqual(r["status_code"], 200); self.assertTrue(r.get("ok"))
    def test_reminders(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/reminders/recurring").data)
            self.assertTrue(r.get("ok"))
    def test_vector(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/vector/collections").data)
            self.assertTrue(r.get("ok"))
    def test_metrics(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/metrics/custom").data)
            self.assertTrue(r.get("ok"))
    def test_events(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/events/filtered").data)
            self.assertTrue(r.get("ok"))
    def test_modules(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/modules/health").data)
            self.assertTrue(r.get("ok"))
    def test_config(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/config/history").data)
            self.assertTrue(r.get("ok"))
    def test_auth(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/auth/sessions").data)
            self.assertTrue(r.get("ok"))
    def test_health(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/health/components").data)
            self.assertTrue(r.get("ok"))
    def test_debug(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/debug/logs/stream").data)
            self.assertTrue(r.get("ok"))
if __name__ == "__main__": unittest.main()
