"""Notify & Message Tests — Slice 274 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestNotifyMessage(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_send_notification(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/notify/send", json={"message": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_notify_history(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/notify/history")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_messages_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/messages/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_send_message(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/messages/send", json={"text": "hello"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
