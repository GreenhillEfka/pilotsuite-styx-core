"""Security Tests — Slice 192."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestSecurity(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_hacs_lock_requires_auth(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/hacs/lock", json={})
            self.assertIn(r.status_code, [401, 403])
    def test_admin_endpoint_requires_auth(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/admin/restart", json={})
            self.assertIn(r.status_code, [401, 403])
    def test_sql_injection_prevention(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/search/advanced?q='; DROP TABLE users;--")
            self.assertEqual(r.status_code, 400)
    def test_xss_prevention(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/search/advanced?q=<script>alert(1)</script>")
            self.assertEqual(r.status_code, 400)
    def test_rate_limit_headers(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/health")
            self.assertIn("X-RateLimit-Limit", r.headers)
if __name__ == "__main__": unittest.main()
