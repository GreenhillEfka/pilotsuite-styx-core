"""Calendar Expanded Tests — Slice 222 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestCalendarExpanded(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_calendar_events(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/calendar/events")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_calendar_availability(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/calendar/availability")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_calendar_event(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/calendar/events/create", json={"id": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
