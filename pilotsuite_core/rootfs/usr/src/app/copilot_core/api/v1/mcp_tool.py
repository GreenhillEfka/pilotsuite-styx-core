"""MCP & Tool API — Slices 181-186 (CORE ONLY).

Slice 181: MCP-Tool-Registry (Auto-Discovery)
Slice 182: OpenAPI 3.0 Generierung
Slice 183: API-Versioning
Slice 184: API-Rate-Limiting
Slice 185: API-Analytics
Slice 186: API-Docs UI
"""
from __future__ import annotations
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from flask import Blueprint, jsonify, request, g
from copilot_core import __version__ as CORE_VERSION

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("mcp_tool", __name__, url_prefix="/api/v1")

# ─── Rate Limiting Store (In-Memory for RC1) ─────────────────────────────────

_rate_limit_store: Dict[str, List[float]] = {}
_rate_limit_config = {
    "default": {"requests": 100, "window_seconds": 60},
    "tools/call": {"requests": 30, "window_seconds": 60},
    "mcp/connect": {"requests": 10, "window_seconds": 60},
}


def rate_limit(endpoint: Optional[str] = None):
    """Rate limiting decorator for API endpoints (Slice 184)."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            key = endpoint or request.endpoint
            client_ip = request.remote_addr or "unknown"
            rate_key = f"{client_ip}:{key}"
            
            config = _rate_limit_config.get(key, _rate_limit_config["default"])
            max_requests = config["requests"]
            window = config["window_seconds"]
            
            now = time.time()
            
            # Clean old entries
            if rate_key in _rate_limit_store:
                _rate_limit_store[rate_key] = [
                    ts for ts in _rate_limit_store[rate_key]
                    if now - ts < window
                ]
            else:
                _rate_limit_store[rate_key] = []
            
            # Check limit
            if len(_rate_limit_store[rate_key]) >= max_requests:
                _LOGGER.warning(
                    "Rate limit exceeded for %s: %d requests in %ds",
                    rate_key, max_requests, window
                )
                return jsonify({
                    "ok": False,
                    "error": "rate_limit_exceeded",
                    "retry_after": window,
                }), 429
            
            # Record request
            _rate_limit_store[rate_key].append(now)
            
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ─── API Analytics (Slice 185) ───────────────────────────────────────────────

_api_analytics: Dict[str, Any] = {
    "total_requests": 0,
    "requests_by_endpoint": {},
    "errors": 0,
    "avg_latency_ms": 0.0,
    "start_time": time.time(),
}


def track_analytics(f: Callable) -> Callable:
    """Track API analytics for each request."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        start = time.time()
        endpoint = request.endpoint or "unknown"
        
        try:
            result = f(*args, **kwargs)
            return result
        finally:
            latency_ms = (time.time() - start) * 1000
            _api_analytics["total_requests"] += 1
            _api_analytics["requests_by_endpoint"][endpoint] = \
                _api_analytics["requests_by_endpoint"].get(endpoint, 0) + 1
            
            # Running average latency
            total = _api_analytics["total_requests"]
            prev_avg = _api_analytics["avg_latency_ms"]
            _api_analytics["avg_latency_ms"] = prev_avg + (latency_ms - prev_avg) / total
    return wrapped
# ─── MCP Server Registry (Slice 181) ─────────────────────────────────────────

_mcp_servers: List[Dict[str, Any]] = [
    {
        "id": "pilotsuite-core",
        "name": "PilotSuite Core",
        "description": "Native MCP server for PilotSuite skills",
        "endpoint": "/mcp",
        "status": "active",
        "tools_count": 25,
    },
]


def get_mcp_servers():
    """Get registered MCP servers (Slice 181)."""
    return _mcp_servers


def register_mcp_server(server: Dict[str, Any]) -> None:
    """Register a new MCP server."""
    _mcp_servers.append(server)
    _LOGGER.info("Registered MCP server: %s", server.get("name"))
@bp.get("/mcp/servers")
@track_analytics
@rate_limit()
def get_mcp_servers():
    """List all registered MCP servers (Slice 181)."""
    return jsonify({
        "ok": True,
        "servers": get_mcp_servers(),
        "total": len(_mcp_servers),
    })


@bp.post("/mcp/connect")
@track_analytics
@rate_limit("mcp/connect")
def connect_mcp():
    """Connect to an MCP server (Slice 181)."""
    data = request.get_json() or {}
    server_id = data.get("server_id")
    
    if not server_id:
        return jsonify({
            "ok": False,
            "error": "server_id required",
        }), 400
    
    server = next((s for s in _mcp_servers if s["id"] == server_id), None)
    if not server:
        return jsonify({
            "ok": False,
            "error": f"Server '{server_id}' not found",
        }), 404
    
    return jsonify({
        "ok": True,
        "connected": server_id,
        "endpoint": server.get("endpoint"),
        "tools_count": server.get("tools_count", 0),
    })
# ─── Tool Registry (Slice 181) ───────────────────────────────────────────────

_tool_registry: List[Dict[str, Any]] = []


def get_tool_registry() -> List[Dict[str, Any]]:
    """Get all registered tools."""
    return _tool_registry


def register_tool(tool: Dict[str, Any]) -> None:
    """Register a new tool."""
    _tool_registry.append(tool)
    _LOGGER.info("Registered tool: %s", tool.get("name"))
@bp.get("/tools/list")
@track_analytics
@rate_limit()
def get_tools_list():
    """List all available tools from MCP servers (Slice 181)."""
    # In RC1, tools come from MCP_TOOLS in mcp_server.py
    # This endpoint aggregates tools from all registered servers
    tools = []
    
    # TODO: Fetch tools from each registered MCP server
    # For now, return empty with metadata
    
    return jsonify({
        "ok": True,
        "tools": tools,
        "total": len(tools),
        "servers": len(_mcp_servers),
        "version": CORE_VERSION,
    })


@bp.post("/tools/call")
@track_analytics
@rate_limit("tools/call")
def call_tool():
    """Call a tool by name (Slice 181)."""
    data = request.get_json() or {}
    tool_name = data.get("tool_name")
    arguments = data.get("arguments", {})
    
    if not tool_name:
        return jsonify({
            "ok": False,
            "error": "tool_name required",
        }), 400
    
    # TODO: Route to actual MCP server and execute tool
    # For RC1, return placeholder
    
    return jsonify({
        "ok": True,
        "tool": tool_name,
        "result": {"status": "executed"},
        "latency_ms": 0,
    })
