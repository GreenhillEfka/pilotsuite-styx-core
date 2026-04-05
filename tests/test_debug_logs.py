"""Debug & Logs Tests — Slice 219 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestDebugLogs(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_logs_stream(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/debug/logs/stream")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_debug_metrics(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/debug/metrics")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
