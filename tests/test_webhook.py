"""Webhook Tests — Slice 300 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestWebhook(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_webhooks_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/webhooks/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_webhook(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/webhooks/create", json={"url": "http://test.com"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_trigger_webhook(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/webhooks/trigger", json={"webhook_id": "w1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_delete_webhook(self):
        with self._app().test_client() as c:
            r = c.delete("/api/v1/webhooks/delete", json={"webhook_id": "w1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
