"""Regression Tests — Slice 195."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestRegression(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_p0_001_token_auth_solid(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/hacs/gate")
            self.assertIn(r.status_code, [200, 401])
    def test_p0_002_vector_blueprint_registered(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/vector/collections")
            self.assertEqual(r.status_code, 200)
    def test_p0_003_manifest_parity(self):
        with self._app().test_client() as c:
            r = c.get("/api/hacs/discovery")
            d = json.loads(r.data)
            self.assertIn("version", d)
    def test_p0_004_dev_surface_imports(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/health")
            self.assertEqual(r.status_code, 200)
    def test_b1_b4_zone_sync(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/presence/state")
            self.assertEqual(r.status_code, 200)
    def test_b5_b6_event_wiring(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/events/filtered")
            self.assertEqual(r.status_code, 200)
if __name__ == "__main__": unittest.main()
