"""MCP & Tool Tests — Slice 284 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestMCPTool(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_mcp_servers(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/mcp/servers")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_connect_mcp(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/mcp/connect", json={"server": "local"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_tools_list(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/tools/list")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_call_tool(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/tools/call", json={"tool_id": "tool1", "args": {}})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
