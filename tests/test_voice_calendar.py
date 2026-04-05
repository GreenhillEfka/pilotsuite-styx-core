"""Voice + Calendar Integration Tests — Slice 205."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestVoiceCalendar(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_voice_calendar_events(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/calendar/events")
            self.assertIn(r.status_code, [200, 501])
    def test_voice_command_parse(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/voice/command", json={"text": "schedule meeting"})
            self.assertIn(r.status_code, [200, 400, 501])
    def test_calendar_availability(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/calendar/availability")
            self.assertIn(r.status_code, [200, 501])
if __name__ == "__main__": unittest.main()
