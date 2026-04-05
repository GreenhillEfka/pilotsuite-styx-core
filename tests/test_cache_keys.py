"""Cache & Keys Tests — Slice 234 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestCacheKeys(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_cache_keys(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/cache/keys")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_delete_cache_key(self):
        with self._app().test_client() as c:
            r = c.delete("/api/v1/cache/keys/test_key")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_clear_cache(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/cache/clear")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
