"""System & Resources Tests — Slice 238 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestSystemResources(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_system_resources(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/system/resources")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
            self.assertIn("cpu_percent", d)
    def test_get_system_info(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/system/info")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_system_uptime(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/system/uptime")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
