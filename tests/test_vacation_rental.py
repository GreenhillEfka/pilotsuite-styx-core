"""Vacation & Rental Tests — Slice 259 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestVacationRental(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_vacation_mode(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/vacation/mode")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_vacation_mode_on(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/vacation/on")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_vacation_mode_off(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/vacation/off")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_guest_info(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/rental/guest")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
