"""Sauna & Wellness Tests — Slice 258 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestSaunaWellness(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_sauna_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/sauna/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_sauna_on(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/sauna/on")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_sauna_off(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/sauna/off")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_wellness_mood(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/wellness/mood")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
