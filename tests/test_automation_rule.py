"""Automation & Rule Tests — Slice 275 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestAutomationRule(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_automations_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/automations/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_create_automation(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/automations/create", json={"name": "test"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_rules_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/rules/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_execute_rule(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/rules/execute", json={"rule_id": "rule1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
