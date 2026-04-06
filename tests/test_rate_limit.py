"""Rate Limit Tests — Slice 291 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestRateLimit(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_ratelimit_status(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/ratelimit/status")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_reset_ratelimit(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/ratelimit/reset")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_quota(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/ratelimit/quota")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_ratelimit(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/ratelimit/set", json={"limit": 200})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
