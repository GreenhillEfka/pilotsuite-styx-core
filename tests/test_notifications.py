"""Contract tests for Notifications API — Slice 138/184."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestNotificationsAPI(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _create_test_app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_notification_categories(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/notifications/categories")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("categories", data)
    def test_notification_priority_queue(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/notifications/priority-queue")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("queue", data)
    def test_notification_user_preferences(self):
        app = self._create_test_app()
        with app.test_client() as client:
            rv = client.get("/api/v1/notifications/user/preferences")
            data = json.loads(rv.data)
            self.assertEqual(rv.status_code, 200)
            self.assertTrue(data.get("ok"))
            self.assertIn("preferences", data)
if __name__ == "__main__": unittest.main()
