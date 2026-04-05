"""Batch Contract Tests Part 3 — Slices 166-173."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestBatchPart3(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_annotations(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/annotations/layers").data)
            self.assertTrue(r.get("ok"))
    def test_scenes(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/scenes/schedules").data)
            self.assertTrue(r.get("ok"))
    def test_templates(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/templates/categories").data)
            self.assertTrue(r.get("ok"))
    def test_entities(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/entities/statistics/summary").data)
            self.assertTrue(r.get("ok"))
    def test_devices(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/devices/registry").data)
            self.assertTrue(r.get("ok"))
    def test_areas(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/areas/hierarchy").data)
            self.assertTrue(r.get("ok"))
    def test_labels(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/labels/filter").data)
            self.assertTrue(r.get("ok"))
    def test_options(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/options/groups").data)
            self.assertTrue(r.get("ok"))
    def test_system(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/system/resources").data)
            self.assertTrue(r.get("ok"))
    def test_ping(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/ping/latency").data)
            self.assertTrue(r.get("ok"))
    def test_services(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/services/registry").data)
            self.assertTrue(r.get("ok"))
    def test_blueprints(self):
        with self._app().test_client() as c:
            r = json.loads(c.get("/api/v1/blueprints/categories").data)
            self.assertTrue(r.get("ok"))
if __name__ == "__main__": unittest.main()
