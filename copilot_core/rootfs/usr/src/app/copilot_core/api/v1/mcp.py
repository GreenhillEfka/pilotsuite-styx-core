"""
MCP REST API - HTTP endpoints for Model Context Protocol integration.

Provides REST endpoints to interact with MCP servers for Mood/Neuron data:
  - POST /api/v1/mcp/connect     — Connect to MCP server
  - GET  /api/v1/mcp/status      — Status of all MCP servers
  - GET  /api/v1/mcp/resources   — Available resources
  - POST /api/v1/mcp/query       — Execute resource query

These endpoints complement the JSON-RPC /mcp endpoint for simpler HTTP integration.
"""

from flask import Blueprint, current_app, jsonify, request

try:
    import requests as http_requests
except ImportError:  # pragma: no cover - depends on optional runtime deps
    http_requests = None  # type: ignore[assignment]

from copilot_core.api.security import validate_token as _validate_token
from copilot_core.mcp_server import mcp_bp as mcp_rpc_bp

bp = Blueprint("mcp_rest", __name__, url_prefix="/api/v1/mcp")
mcp_bp = mcp_rpc_bp

# In-memory MCP server connections
_MCP_CONNECTIONS: dict = {}


def _mcp_http_dependency_error():
    return jsonify({
        "ok": False,
        "error": "mcp_http_unavailable",
        "message": "Optional HTTP dependency 'requests' is not installed",
    }), 503


def _require_auth():
    """Auth filter for MCP endpoints."""
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


@bp.before_request
def _auth():
    """Apply auth to all MCP endpoints."""
    return _require_auth()


@bp.post("/connect")
def connect():
    """Connect to an MCP server.
    
    Body:
    - server_url: str — URL of the MCP server (e.g., http://localhost:3000)
    - server_id: str  — Unique identifier for this connection
    - timeout: int    — Connection timeout in seconds (default 10)
    
    Returns:
    - success: bool
    - server_id: str
    - server_url: str
    - connected: bool
    - protocol: str
    """
    try:
        payload = request.get_json(silent=True) or {}
        
        server_url = payload.get("server_url")
        server_id = payload.get("server_id", "default")
        timeout = payload.get("timeout", 10)
        
        if not server_url:
            return jsonify({
                "ok": False,
                "error": "server_url required"
            }), 400
        
        # Attempt connection (simple connectivity check)
        if http_requests is None:
            return _mcp_http_dependency_error()

        try:
            response = http_requests.post(
                f"{server_url}/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                timeout=timeout
            )
            connected = response.status_code == 200
        except Exception as e:
            connected = False
            current_app.logger.warning(f"MCP connect failed: {e}")
        
        # Store connection info
        _MCP_CONNECTIONS[server_id] = {
            "server_url": server_url,
            "connected": connected,
            "timeout": timeout,
            "last_connected": None,
            "resources": []
        }
        
        if connected:
            _MCP_CONNECTIONS[server_id]["last_connected"] = payload.get("time")
            
            # Try to fetch resources
            try:
                resp = requests.post(
                    f"{server_url}/mcp",
                    json={"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
                    timeout=timeout
                )
                if resp.status_code == 200:
                    data = resp.json()
                    _MCP_CONNECTIONS[server_id]["resources"] = data.get("result", {}).get("resources", [])
            except Exception:
                pass
        
        return jsonify({
            "ok": True,
            "server_id": server_id,
            "server_url": server_url,
            "connected": connected,
            "protocol": "mcp-2025-03-26"
        })
    except Exception as e:
        current_app.logger.exception("MCP connect failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/status")
def status():
    """Get status of all MCP servers.
    
    Returns:
    - servers: dict — Map of server_id -> status info
    - total: int    — Number of connected servers
    """
    try:
        # Update connection status for all registered servers
        if http_requests is not None:
            for server_id, conn_info in _MCP_CONNECTIONS.items():
                try:
                    response = http_requests.post(
                        f"{conn_info['server_url']}/mcp",
                        json={"jsonrpc": "2.0", "id": 3, "method": "ping"},
                        timeout=conn_info.get("timeout", 10)
                    )
                    conn_info["connected"] = response.status_code == 200
                    conn_info["last_status_check"] = payload.get("time") if (payload := request.get_json(silent=True)) else None
                except Exception as e:
                    conn_info["connected"] = False
                    conn_info["last_error"] = str(e)
        else:
            for conn_info in _MCP_CONNECTIONS.values():
                conn_info.setdefault("last_error", "Optional HTTP dependency 'requests' is not installed")
        
        connected_count = sum(1 for c in _MCP_CONNECTIONS.values() if c.get("connected", False))
        
        return jsonify({
            "ok": True,
            "servers": _MCP_CONNECTIONS,
            "total_connected": connected_count,
            "total_registered": len(_MCP_CONNECTIONS)
        })
    except Exception as e:
        current_app.logger.exception("MCP status failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/resources")
def resources():
    """Get available resources from connected MCP servers.
    
    Query params:
    - server_id: str — Filter by specific server
    
    Returns:
    - resources: list — List of resource descriptors
    - server_id: str  — If filtered
    """
    try:
        server_id = request.args.get("server_id")
        
        if server_id and server_id in _MCP_CONNECTIONS:
            # Return resources for specific server
            conn_info = _MCP_CONNECTIONS[server_id]
            resources_list = conn_info.get("resources", [])
            
            # Try to refresh if not connected
            if not conn_info.get("connected", False):
                import requests
                try:
                    resp = requests.post(
                        f"{conn_info['server_url']}/mcp",
                        json={"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
                        timeout=conn_info.get("timeout", 10)
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        resources_list = data.get("result", {}).get("resources", [])
                        conn_info["resources"] = resources_list
                        conn_info["connected"] = True
                except Exception:
                    pass
            
            return jsonify({
                "ok": True,
                "server_id": server_id,
                "resources": resources_list,
                "count": len(resources_list)
            })
        else:
            # Return all resources from all servers
            all_resources = []
            for sid, conn in _MCP_CONNECTIONS.items():
                res = conn.get("resources", [])
                for r in res:
                    r["_server_id"] = sid
                all_resources.extend(res)
            
            return jsonify({
                "ok": True,
                "resources": all_resources,
                "count": len(all_resources)
            })
    except Exception as e:
        current_app.logger.exception("MCP resources failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/query")
def query():
    """Execute a resource query on MCP servers.
    
    Body:
    - server_id: str       — Target server
    - resource_uri: str    — Resource to query
    - parameters: dict     — Query parameters
    - search: str          — Search term (alternative to parameters)
    
    Returns:
    - content: list        — Query results
    - server_id: str
    - resource_uri: str
    """
    try:
        if http_requests is None:
            return _mcp_http_dependency_error()

        payload = request.get_json(silent=True) or {}
        
        server_id = payload.get("server_id")
        resource_uri = payload.get("resource_uri")
        parameters = payload.get("parameters", {})
        search = payload.get("search")
        
        if not server_id:
            return jsonify({
                "ok": False,
                "error": "server_id required"
            }), 400
        
        if not resource_uri:
            return jsonify({
                "ok": False,
                "error": "resource_uri required"
            }), 400
        
        if server_id not in _MCP_CONNECTIONS:
            return jsonify({
                "ok": False,
                "error": f"Unknown server: {server_id}"
            }), 404
        
        conn_info = _MCP_CONNECTIONS[server_id]
        if not conn_info.get("connected", False):
            return jsonify({
                "ok": False,
                "error": "Server not connected"
            }), 400
        
        # Build query
        if http_requests is None:
            return _mcp_http_dependency_error()

        import json
        
        query_data = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {
                "uri": resource_uri
            }
        }
        
        if parameters:
            query_data["params"]["parameters"] = parameters
        
        if search:
            query_data["params"]["search"] = search
        
        try:
            response = requests.post(
                f"{conn_info['server_url']}/mcp",
                json=query_data,
                timeout=conn_info.get("timeout", 10)
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                
                # Extract content from MCP response
                content = result.get("content", [])
                if isinstance(content, list) and len(content) > 0:
                    # Handle text content
                    text_content = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_content.append(item.get("text", ""))
                            else:
                                text_content.append(json.dumps(item))
                        elif isinstance(item, str):
                            text_content.append(item)
                    content = text_content
                
                return jsonify({
                    "ok": True,
                    "server_id": server_id,
                    "resource_uri": resource_uri,
                    "content": content,
                    "result": result
                })
            else:
                return jsonify({
                    "ok": False,
                    "error": f"MCP server error: {response.status_code}"
                }), response.status_code
                
        except Exception as e:
            current_app.logger.exception("MCP query failed")
            return jsonify({"ok": False, "error": str(e)}), 500
            
    except Exception as e:
        current_app.logger.exception("MCP query init failed")
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------------
# Utility endpoint: List available MCP tools via REST
# ------------------------------------------------------------------

@bp.get("/tools")
def tools():
    """List available MCP tools.
    
    Returns:
    - tools: list — List of tool definitions
    """
    try:
        from copilot_core.mcp_server import MCP_TOOLS
        
        return jsonify({
            "ok": True,
            "tools": MCP_TOOLS,
            "count": len(MCP_TOOLS)
        })
    except Exception as e:
        current_app.logger.exception("MCP tools list failed")
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------------
# Utility endpoint: Call MCP tool via REST
# ------------------------------------------------------------------

@bp.post("/tools/call")
def tools_call():
    """Call an MCP tool by name.
    
    Body:
    - tool_name: str    — Name of the tool to call
    - arguments: dict   — Tool arguments
    
    Returns:
    - result: dict      — Tool execution result
    - tool_name: str
    """
    try:
        payload = request.get_json(silent=True) or {}
        
        tool_name = payload.get("tool_name")
        arguments = payload.get("arguments", {})
        
        if not tool_name:
            return jsonify({
                "ok": False,
                "error": "tool_name required"
            }), 400
        
        # Execute via the existing MCP server logic
        from copilot_core.mcp_server import _execute_mcp_tool
        
        result = _execute_mcp_tool(tool_name, arguments)
        
        return jsonify({
            "ok": True,
            "tool_name": tool_name,
            "result": result
        })
    except Exception as e:
        current_app.logger.exception("MCP tool call failed")
        return jsonify({"ok": False, "error": str(e)}), 500
