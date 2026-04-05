"""Search Advanced Tests — Slice 235 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestSearchAdvanced(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_search_advanced(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/search/advanced?q=test&filters=type:entity")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_index_search(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/search/index", json={"id": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_search_suggestions(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/search/suggestions?q=light")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
