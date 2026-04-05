"""Blueprints & Categories Tests — Slice 241 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestBlueprintsCategories(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_blueprints_categories(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/blueprints/categories")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_import_blueprint(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/blueprints/import", json={"id": "test_bp"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_list_blueprints(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/blueprints/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
