"""Search Tests — Slice 299 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestSearch(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_search_query(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/search/query?q=test")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_index_document(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/search/index", json={"doc_id": "d1", "content": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_search_suggest(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/search/suggest?q=te")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_clear_index(self):
        with self._app().test_client() as c:
            r = c.delete("/api/v1/search/clear")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
