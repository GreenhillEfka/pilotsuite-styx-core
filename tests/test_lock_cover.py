"""Lock & Cover Tests — Slice 247 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestLockCover(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_lock_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/lock/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_lock(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/lock/set", json={"state": "unlocked"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_cover_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/cover/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_cover(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/cover/set", json={"position": 50})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
