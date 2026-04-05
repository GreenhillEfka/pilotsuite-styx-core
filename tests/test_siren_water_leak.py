"""Siren & Water Leak Tests — Slice 249 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestSirenWaterLeak(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_siren_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/siren/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_activate_siren(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/siren/activate", json={"tone": "alarm"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_water_leak_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/water_leak/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_test_water_leak(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/water_leak/test")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
