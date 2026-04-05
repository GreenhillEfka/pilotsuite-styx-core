"""Fan & Light Tests — Slice 246 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestFanLight(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_fan_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/fan/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_fan(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/fan/set", json={"speed": 50})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_light_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/light/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_light(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/light/set", json={"brightness": 128})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
