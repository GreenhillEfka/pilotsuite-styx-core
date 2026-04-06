"""Button & Switch Tests — Slice 267 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestButtonSwitch(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_buttons_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/buttons/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_press_button(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/buttons/press", json={"button_id": "scene1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_switches_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/switches/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_switch(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/switches/set", json={"on": True})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
