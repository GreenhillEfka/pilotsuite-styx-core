"""Search & Tags Tests — Slice 214."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestSearchTags(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_search_advanced(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/search/advanced?q=test")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_tags_hierarchies(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/tags/hierarchies")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_tag(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/tags/create", json={"name": "test-tag"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
