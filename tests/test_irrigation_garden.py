"""Irrigation & Garden Tests — Slice 256 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestIrrigationGarden(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_irrigation_zones(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/irrigation/zones")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_start_irrigation(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/irrigation/start", json={"zone": 1})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_stop_irrigation(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/irrigation/stop")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_irrigation_schedule(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/irrigation/schedule")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
