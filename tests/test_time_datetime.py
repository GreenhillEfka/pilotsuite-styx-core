"""Time & DateTime Tests — Slice 271 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestTimeDateTime(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_time_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/time/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_time(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/time/set", json={"time": "14:30"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_datetime_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/datetime/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_datetime(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/datetime/set", json={"datetime": "2026-04-06T14:30:00"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
