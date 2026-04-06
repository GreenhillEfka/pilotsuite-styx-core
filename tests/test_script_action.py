"""Script & Action Tests — Slice 276 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestScriptAction(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_scripts_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/scripts/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_run_script(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/scripts/run", json={"script_id": "script1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_actions_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/actions/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_trigger_action(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/actions/trigger", json={"action_id": "action1"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
