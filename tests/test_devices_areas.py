"""Devices & Areas Tests — Slice 210."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestDevicesAreas(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_devices_registry(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/devices/registry")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_areas_hierarchy(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/areas/hierarchy")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_labels_filter(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/labels/filter")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
