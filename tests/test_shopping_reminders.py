"""Shopping & Reminders Tests — Slice 223 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestShoppingReminders(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_shopping_suggestions(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/shopping/suggestions")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_reminders_recurring(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/reminders/recurring")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_reminder(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/reminders/create", json={"id": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
