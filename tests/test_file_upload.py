"""File Upload Tests — Slice 298 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestFileUpload(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_files_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/files/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_upload_file(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/files/upload")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_download_file(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/files/download")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_delete_file(self):
        with self._app().test_client() as c:
            r = c.delete("/api/v1/files/delete")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
