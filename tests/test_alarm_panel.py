"""Alarm Control Panel Tests — Slice 248 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestAlarmPanel(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_alarm_state(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/alarm/state")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_arm_alarm(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/alarm/arm", json={"mode": "away"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_disarm_alarm(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/alarm/disarm")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
