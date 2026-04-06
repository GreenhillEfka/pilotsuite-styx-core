"""Tag & Label Tests — Slice 278 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestTagLabel(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_tags_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/tags/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_tag(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/tags/create", json={"name": "important"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_labels_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/labels/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_assign_label(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/labels/assign", json={"label_id": "label1", "entity": "light1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
