"""E2E Tests — Slice 194."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestE2E(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_full_hacs_update_journey(self):
        with self._app().test_client() as c:
            gate = json.loads(c.get("/api/v1/hacs/gate").data)
            self.assertTrue(gate.get("ok"))
            discovery = json.loads(c.get("/api/hacs/discovery").data)
            self.assertIn("version", discovery)
            versions = json.loads(c.get("/api/hacs/versions").data)
            self.assertIn("latest", versions)
    def test_user_preferences_journey(self):
        with self._app().test_client() as c:
            prefs = json.loads(c.get("/api/v1/users/test-user/preferences").data)
            self.assertTrue(prefs.get("ok"))
    def test_health_check_journey(self):
        with self._app().test_client() as c:
            health = json.loads(c.get("/api/v1/health").data)
            self.assertTrue(health.get("ok"))
            components = json.loads(c.get("/api/v1/health/components").data)
            self.assertTrue(components.get("ok"))
if __name__ == "__main__": unittest.main()
