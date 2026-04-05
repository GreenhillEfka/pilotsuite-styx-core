"""Pool & Spa Tests — Slice 257 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestPoolSpa(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_pool_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/pool/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_spa_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/spa/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_pool_pump_on(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/pool/pump/on")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_pool_pump_off(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/pool/pump/off")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
