"""Battery & Storage Tests — Slice 254 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestBatteryStorage(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_battery_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/battery/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_battery_health(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/battery/health")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_battery_charge(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/battery/charge")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_set_battery_discharge(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/battery/discharge")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
