"""Edge Case Tests — Slice 198."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestEdgeCases(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_empty_vector_search(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/vector/search?q=")
            self.assertEqual(r.status_code, 400)
    def test_malformed_json_body(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/hacs/lock", data="not-json", content_type="application/json")
            self.assertEqual(r.status_code, 400)
    def test_missing_required_param(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/users/preferences")
            self.assertEqual(r.status_code, 400)
    def test_invalid_entity_id(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/entities/invalid_entity_id/state")
            self.assertEqual(r.status_code, 404)
if __name__ == "__main__": unittest.main()
