"""Automation & Webhooks Tests — Slice 216 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestAutomationWebhooks(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_webhooks_triggers(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/webhooks/triggers")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_webhook(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/webhooks/create", json={"id": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_automation_templates(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/automation/templates")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
