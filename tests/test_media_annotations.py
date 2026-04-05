"""Media & Annotations Tests — Slice 215."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestMediaAnnotations(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_media_albums(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/media/albums")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_annotations_layers(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/annotations/layers")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_annotation(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/annotations/create", json={"key": "value"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
