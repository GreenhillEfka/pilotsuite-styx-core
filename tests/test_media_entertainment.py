"""Media & Entertainment Tests — Slice 262 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestMediaEntertainment(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_media_player(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/media/player")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_media_play(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/media/play")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_media_pause(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/media/pause")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_volume(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/media/volume", json={"level": 75})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_entertainment_scene(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/entertainment/scene")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
