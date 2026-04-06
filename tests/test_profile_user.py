"""Profile & User Tests — Slice 288 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestProfileUser(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_profiles_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/profiles/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_profile(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/profiles/create", json={"name": "admin"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_current_user(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/users/current")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_switch_user(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/users/switch", json={"user_id": "user1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
