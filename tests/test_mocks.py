"""Mock Tests — Slice 197."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestMocks(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_weather_api_mock(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/weather/forecast")
            self.assertIn(r.status_code, [200, 501])
    def test_energy_pricing_mock(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/energy/pricing")
            self.assertIn(r.status_code, [200, 501])
    def test_calendar_api_mock(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/calendar/events")
            self.assertIn(r.status_code, [200, 501])
if __name__ == "__main__": unittest.main()
