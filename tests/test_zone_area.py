"""Zone & Area Tests — Slice 277 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestZoneArea(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_zones_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/zones/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_zone(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/zones/create", json={"name": "living"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_areas_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/areas/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_zones_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/zones/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
