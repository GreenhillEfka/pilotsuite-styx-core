"""Audit & Log Tests — Slice 290 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestAuditLog(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_audit_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/audit/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_log_audit(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/audit/log", json={"action": "login"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_search_audit(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/audit/search")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_export_audit(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/audit/export")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
