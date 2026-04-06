"""Backup & Restore Tests — Slice 281 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestBackupRestore(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_backups_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/backups/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_backup(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/backups/create", json={"name": "backup1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_restore_backup(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/backups/restore", json={"backup_id": "backup1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_backup_status(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/backups/status")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
