"""Notifications Tests — Slice 228 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestNotifications(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_notification_categories(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/notifications/categories")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_priority_queue(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/notifications/priority-queue")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_send_notification(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/notifications/send", json={"id": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
