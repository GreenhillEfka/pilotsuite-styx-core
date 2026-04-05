"""Camera & Media Tests — Slice 244 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestCameraMedia(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_camera_stream(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/camera/stream")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_list_media(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/media/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_upload_media(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/media/upload", json={"id": "test_media"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
