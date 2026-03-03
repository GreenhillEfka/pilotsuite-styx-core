"""Tests for MCP REST API endpoints (/api/v1/mcp/*)."""

import tempfile
import unittest
from unittest.mock import patch, MagicMock

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


class TestMCPRestAPI(unittest.TestCase):
    """Test MCP REST API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def _create_test_app(self):
        """Create a test Flask app with temp paths."""
        app = create_app()
        from dataclasses import replace

        cfg = app.config["COPILOT_CFG"]
        app.config["COPILOT_CFG"] = replace(
            cfg,
            data_dir=self.tmpdir.name,
            brain_graph_json_path=f"{self.tmpdir.name}/brain_graph.db",
            events_jsonl_path=f"{self.tmpdir.name}/events.jsonl",
            candidates_json_path=f"{self.tmpdir.name}/candidates.json",
            brain_graph_nodes_max=500,
            brain_graph_edges_max=1500,
            brain_graph_persist=True,
        )

        # Reset lazy singletons
        from copilot_core.brain_graph import provider
        from copilot_core.api.v1 import events as events_api

        provider._STORE = None
        provider._SVC = None
        events_api._STORE = None

        return app

    def _get_auth_headers(self):
        """Get authentication headers."""
        return {
            "X-Auth-Token": "test-token",
            "Content-Type": "application/json"
        }

    def test_mcp_connect_endpoint(self):
        """Test POST /api/v1/mcp/connect."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Test with mock MCP server
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
        
        with patch("requests.post", return_value=mock_response):
            payload = {
                "server_url": "http://localhost:3000",
                "server_id": "test-server",
                "timeout": 5
            }
            r = client.post("/api/v1/mcp/connect", json=payload, headers=self._get_auth_headers())
            
            self.assertEqual(r.status_code, 200)
            j = r.get_json()
            self.assertTrue(j.get("ok"))
            self.assertEqual(j.get("server_id"), "test-server")
            self.assertEqual(j.get("server_url"), "http://localhost:3000")
            self.assertEqual(j.get("connected"), True)
            self.assertEqual(j.get("protocol"), "mcp-2025-03-26")

    def test_mcp_connect_missing_server_url(self):
        """Test POST /api/v1/mcp/connect with missing server_url."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {"server_id": "test-server"}
        r = client.post("/api/v1/mcp/connect", json=payload, headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 400)
        j = r.get_json()
        self.assertFalse(j.get("ok"))
        self.assertIn("error", j)

    def test_mcp_status_endpoint(self):
        """Test GET /api/v1/mcp/status."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # First connect a server
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
        
        with patch("requests.post", return_value=mock_response):
            client.post("/api/v1/mcp/connect", json={
                "server_url": "http://localhost:3000",
                "server_id": "status-test"
            }, headers=self._get_auth_headers())
        
        # Then check status
        r = client.get("/api/v1/mcp/status", headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("servers", j)
        self.assertIn("total_connected", j)
        self.assertIn("total_registered", j)

    def test_mcp_resources_endpoint(self):
        """Test GET /api/v1/mcp/resources."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # First connect a server with mock resources
        mock_resources = [
            {"uri": "resource://test", "name": "Test Resource"}
        ]
        
        connect_response = MagicMock()
        connect_response.status_code = 200
        connect_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
        
        resources_response = MagicMock()
        resources_response.status_code = 200
        resources_response.json.return_value = {
            "jsonrpc": "2.0", "id": 2,
            "result": {"resources": mock_resources}
        }
        
        with patch("requests.post", side_effect=[connect_response, resources_response]):
            client.post("/api/v1/mcp/connect", json={
                "server_url": "http://localhost:3000",
                "server_id": "resources-test"
            }, headers=self._get_auth_headers())
        
        # Get resources
        r = client.get("/api/v1/mcp/resources", headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("resources", j)
        self.assertGreaterEqual(j.get("count", 0), 0)

    def test_mcp_resources_filtered_by_server(self):
        """Test GET /api/v1/mcp/resources with server_id filter."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # First connect a server
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
        
        with patch("requests.post", return_value=mock_response):
            client.post("/api/v1/mcp/connect", json={
                "server_url": "http://localhost:3000",
                "server_id": "filtered-server"
            }, headers=self._get_auth_headers())
        
        # Get resources for specific server
        r = client.get("/api/v1/mcp/resources?server_id=filtered-server", headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertEqual(j.get("server_id"), "filtered-server")

    def test_mcp_query_endpoint(self):
        """Test POST /api/v1/mcp/query."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # First connect a server
        connect_response = MagicMock()
        connect_response.status_code = 200
        connect_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
        
        query_response = MagicMock()
        query_response.status_code = 200
        query_response.json.return_value = {
            "jsonrpc": "2.0", "id": 5,
            "result": {
                "content": [{"type": "text", "text": "Query result"}]
            }
        }
        
        with patch("requests.post", side_effect=[connect_response, query_response]):
            client.post("/api/v1/mcp/connect", json={
                "server_url": "http://localhost:3000",
                "server_id": "query-test"
            }, headers=self._get_auth_headers())
        
        # Execute query
        payload = {
            "server_id": "query-test",
            "resource_uri": "resource://test",
            "parameters": {"limit": 10}
        }
        r = client.post("/api/v1/mcp/query", json=payload, headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("content", j)
        self.assertIn("result", j)

    def test_mcp_query_missing_params(self):
        """Test POST /api/v1/mcp/query with missing parameters."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Missing server_id
        payload = {"resource_uri": "resource://test"}
        r = client.post("/api/v1/mcp/query", json=payload, headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 400)
        j = r.get_json()
        self.assertFalse(j.get("ok"))
        self.assertIn("error", j)
        
        # Missing resource_uri
        payload = {"server_id": "query-test"}
        r = client.post("/api/v1/mcp/query", json=payload, headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 400)
        j = r.get_json()
        self.assertFalse(j.get("ok"))
        self.assertIn("error", j)

    def test_mcp_tools_list_endpoint(self):
        """Test GET /api/v1/mcp/tools."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        r = client.get("/api/v1/mcp/tools", headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("tools", j)
        self.assertIn("count", j)
        self.assertGreater(j.get("count", 0), 0)

    def test_mcp_tools_call_endpoint(self):
        """Test POST /api/v1/mcp/tools/call."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {"tool_name": "pilotsuite.get_mood"}
        r = client.post("/api/v1/mcp/tools/call", json=payload, headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        self.assertIn("result", j)
        self.assertIn("tool_name", j)

    def test_mcp_tools_call_missing_name(self):
        """Test POST /api/v1/mcp/tools/call with missing tool_name."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        payload = {"arguments": {}}
        r = client.post("/api/v1/mcp/tools/call", json=payload, headers=self._get_auth_headers())
        
        self.assertEqual(r.status_code, 400)
        j = r.get_json()
        self.assertFalse(j.get("ok"))
        self.assertIn("error", j)

    def test_mcp_auth_required(self):
        """Test that MCP endpoints require authentication."""
        if create_app is None:
            self.skipTest("Flask not installed")
        
        app = self._create_test_app()
        client = app.test_client()
        
        # Connect endpoint without auth
        r = client.post("/api/v1/mcp/connect", json={"server_url": "http://test"})
        self.assertEqual(r.status_code, 401)
        
        # Status endpoint without auth
        r = client.get("/api/v1/mcp/status")
        self.assertEqual(r.status_code, 401)
        
        # Resources endpoint without auth
        r = client.get("/api/v1/mcp/resources")
        self.assertEqual(r.status_code, 401)
        
        # Query endpoint without auth
        r = client.post("/api/v1/mcp/query", json={"server_id": "x", "resource_uri": "y"})
        self.assertEqual(r.status_code, 401)
        
        # Tools endpoint without auth
        r = client.get("/api/v1/mcp/tools")
        self.assertEqual(r.status_code, 401)
        
        # Tools call endpoint without auth
        r = client.post("/api/v1/mcp/tools/call", json={"tool_name": "x"})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
