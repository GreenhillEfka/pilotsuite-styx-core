"""Auth & Sessions Tests — Slice 230 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestAuthSessions(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_auth_sessions(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/auth/sessions")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_auth_login(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/auth/login", json={"user": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_auth_logout(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/auth/logout")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
