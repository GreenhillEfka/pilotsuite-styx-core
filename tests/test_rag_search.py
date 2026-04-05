"""Contract tests for RAG Search API — Slice 137/183."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestRAGSearchAPI(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _create_test_app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_rag_semantic_search_missing_query(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/rag/search/semantic")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 400)
            self.assertFalse(data.get("ok"))
    def test_rag_search_analytics(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/rag/search/analytics")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("analytics", data)
    def test_rag_feedback_missing_params(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.post("/api/v1/rag/feedback", json={})
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 400)
            self.assertFalse(data.get("ok"))
if __name__ == "__main__": unittest.main()
