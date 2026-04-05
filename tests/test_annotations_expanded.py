"""Annotations API Tests — Slice 207."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestAnnotationsExpanded(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_entity_annotations(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/annotations/entity/sensor.test")
            d = json.loads(r.data)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(d.get("ok"))
    def test_add_entity_annotation(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/annotations/entity/sensor.test", json={"key": "value"})
            d = json.loads(r.data)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(d.get("ok"))
    def test_get_annotation_layers(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/annotations/layers")
            d = json.loads(r.data)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
