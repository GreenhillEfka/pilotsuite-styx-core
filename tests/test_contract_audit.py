"""Contract Audit — Slice 201."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestContractAudit(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_all_endpoints_return_ok_field(self):
        endpoints = ["/api/v1/health", "/api/v1/hacs/gate", "/api/v1/presence/state", "/api/v1/vector/collections"]
        with self._app().test_client() as c:
            for ep in endpoints:
                r = json.loads(c.get(ep).data)
                self.assertIn("ok", r)
    def test_all_endpoints_return_status_code(self):
        endpoints = ["/api/v1/health", "/api/v1/hacs/gate"]
        with self._app().test_client() as c:
            for ep in endpoints:
                r = json.loads(c.get(ep).data)
                self.assertIn("status_code", r)
    def test_error_responses_have_message(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/search/advanced?q=")
            self.assertEqual(r.status_code, 400)
            d = json.loads(r.data)
            self.assertIn("error", d)
if __name__ == "__main__": unittest.main()
