"""Vector Search Tests — Slice 225 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestVectorSearch(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_vector_search(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/vector/search?q=test")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_vector_collections(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/vector/collections")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_embedding(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/vector/embed", json={"id": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
