"""Text & Date Tests — Slice 270 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestTextDate(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_text_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/text/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_text(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/text/set", json={"value": "hello"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_dates_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/dates/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_date(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/dates/set", json={"date": "2026-04-06"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
