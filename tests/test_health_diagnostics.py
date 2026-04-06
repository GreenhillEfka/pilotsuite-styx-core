"""Health & Diagnostics Tests — Slice 282 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestHealthDiagnostics(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_health_status(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/health/status")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_diagnostics_info(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/diagnostics/info")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_health_checks(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/health/checks")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_run_diagnostics(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/diagnostics/run")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
