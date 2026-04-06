"""Lighting & Scenes Tests — Slice 264 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestLightingScenes(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_lights_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/lights/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_lights(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/lights/set", json={"brightness": 80})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_scenes_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/scenes/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_activate_scene(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/scenes/activate", json={"scene_id": "movie"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
