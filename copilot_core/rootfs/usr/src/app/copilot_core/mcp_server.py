"""
PilotSuite MCP Server -- exposes PilotSuite skills as MCP tools.

Implements the Model Context Protocol (Streamable HTTP transport) so external
clients (OpenClaw, Claude Desktop, any MCP client) can access:
  - Brain Graph queries (entity relationships, patterns)
  - Habitus patterns (behavioral rules)
  - Mood Engine (zone comfort/joy/frugality)
  - Neuron pipeline (energy, weather, presence, etc.)
  - Conversation memory (learned preferences)

Endpoint: /mcp  (JSON-RPC 2.0 over HTTP POST)

The MCP protocol uses JSON-RPC 2.0 with these methods:
  initialize       -> server capabilities
  tools/list       -> available tools
  tools/call       -> execute a tool
  prompts/list     -> system prompts
  prompts/get      -> get a prompt
"""

import json
import logging
import time

from flask import Blueprint, request, jsonify
from copilot_core import __version__ as COPILOT_VERSION

logger = logging.getLogger(__name__)

mcp_bp = Blueprint('mcp', __name__, url_prefix='/mcp')

# MCP Server info
MCP_SERVER_INFO = {
    "name": "pilotsuite",
    "version": COPILOT_VERSION,
}

MCP_CAPABILITIES = {
    "tools": {},
    "prompts": {},
}

# ------------------------------------------------------------------
# MCP Tool definitions
# ------------------------------------------------------------------

MCP_TOOLS = [
    {
        "name": "pilotsuite.get_mood",
        "description": "Get current mood scores (Comfort, Joy, Frugality) for all zones or a specific zone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Optional zone name to filter"},
            },
        },
    },
    {
        "name": "pilotsuite.get_brain_graph",
        "description": "Query the Brain Graph for entity relationships and co-occurrence patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Optional entity_id to get neighbors"},
                "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
            },
        },
    },
    {
        "name": "pilotsuite.get_habitus_patterns",
        "description": "Get discovered behavioral patterns (association rules). Shows A->B patterns with support, confidence, and lift.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max patterns to return (default 10)", "default": 10},
                "min_confidence": {"type": "number", "description": "Min confidence threshold (0-1)", "default": 0.5},
            },
        },
    },
    {
        "name": "pilotsuite.get_neuron_summary",
        "description": "Get summary from the Neural Pipeline (mood, energy, weather, presence context).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "pilotsuite.get_preferences",
        "description": "Get learned user preferences from conversation memory (lifelong learning).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_confidence": {"type": "number", "description": "Min confidence (0-1)", "default": 0.3},
            },
        },
    },
    {
        "name": "pilotsuite.get_household",
        "description": "Get household profile (members, roles, preferences).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "pilotsuite.search_memory",
        "description": "Search conversation memory for relevant past interactions by topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topic or keyword to search for"},
                "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "pilotsuite.get_energy_stats",
        "description": "Get current energy statistics (consumption, solar, battery if available).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

# MCP Prompts
MCP_PROMPTS = [
    {
        "name": "pilotsuite_context",
        "description": "System prompt with full PilotSuite context (mood, habits, preferences)",
        "arguments": [],
    },
]


# ------------------------------------------------------------------
# Tool execution
# ------------------------------------------------------------------

def _execute_mcp_tool(name: str, arguments: dict) -> dict:
    """Execute a PilotSuite MCP tool."""
    from flask import current_app
    services = current_app.config.get("COPILOT_SERVICES", {})

    try:
        if name == "pilotsuite.get_mood":
            mood_svc = services.get("mood_service")
            if not mood_svc:
                return {"error": "MoodService not available"}
            zone = arguments.get("zone")
            if zone:
                zone_data = mood_svc.get_zone(zone)
                return {"zone": zone, "data": zone_data} if zone_data else {"error": f"Zone '{zone}' not found"}
            return mood_svc.get_summary()

        elif name == "pilotsuite.get_brain_graph":
            bg_svc = services.get("brain_graph_service")
            if not bg_svc:
                return {"error": "BrainGraphService not available"}
            entity_id = arguments.get("entity_id")
            limit = arguments.get("limit", 20)
            if entity_id:
                neighbors = bg_svc.get_neighbors(entity_id, limit=limit)
                return {"entity_id": entity_id, "neighbors": neighbors}
            stats = bg_svc.get_stats()
            return stats

        elif name == "pilotsuite.get_habitus_patterns":
            habitus_svc = services.get("habitus_service")
            if not habitus_svc:
                return {"error": "HabitusService not available"}
            limit = arguments.get("limit", 10)
            patterns = habitus_svc.list_recent_patterns(limit=limit)
            min_conf = arguments.get("min_confidence", 0.5)
            filtered = [p for p in patterns
                        if p.get("metadata", {}).get("confidence", 0) >= min_conf]
            return {"patterns": filtered, "total": len(patterns)}

        elif name == "pilotsuite.get_neuron_summary":
            neuron_mgr = services.get("neuron_manager")
            if not neuron_mgr:
                return {"error": "NeuronManager not available"}
            return neuron_mgr.get_mood_summary()

        elif name == "pilotsuite.get_preferences":
            conv_memory = services.get("conversation_memory")
            if not conv_memory:
                return {"error": "ConversationMemory not available"}
            prefs = conv_memory.get_user_preferences()
            min_conf = arguments.get("min_confidence", 0.3)
            result = [
                {"key": p.key, "value": p.value, "confidence": p.confidence,
                 "mentions": p.mention_count}
                for p in prefs if p.confidence >= min_conf
            ]
            return {"preferences": result}

        elif name == "pilotsuite.get_household":
            household = services.get("household_profile")
            if not household:
                return {"error": "HouseholdProfile not available"}
            return household.to_dict()

        elif name == "pilotsuite.search_memory":
            conv_memory = services.get("conversation_memory")
            if not conv_memory:
                return {"error": "ConversationMemory not available"}
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            results = conv_memory.get_relevant_context(query, limit=limit)
            return {"results": results, "query": query}

        elif name == "pilotsuite.get_energy_stats":
            energy_svc = services.get("energy_service")
            if not energy_svc:
                return {"error": "EnergyService not available"}
            return energy_svc.get_summary()

        else:
            return {"error": f"Unknown tool: {name}"}

    except Exception as exc:
        logger.warning("MCP tool execution failed (%s): %s", name, exc)
        return {"error": str(exc)}


def _get_pilotsuite_context_prompt() -> str:
    """Build the full PilotSuite context prompt."""
    from copilot_core.api.v1.conversation import _get_user_context, HA_SYSTEM_PROMPT
    context = _get_user_context()
    return HA_SYSTEM_PROMPT + (context or "")


# ------------------------------------------------------------------
# JSON-RPC 2.0 handler
# ------------------------------------------------------------------

@mcp_bp.route('', methods=['POST'])
def mcp_endpoint():
    """MCP Streamable HTTP endpoint (JSON-RPC 2.0)."""
    try:
        data = request.get_json()
        if not data:
            return _jsonrpc_error(None, -32700, "Parse error")

        method = data.get("method", "")
        params = data.get("params", {})
        req_id = data.get("id")

        if method == "initialize":
            return _jsonrpc_result(req_id, {
                "protocolVersion": "2025-03-26",
                "capabilities": MCP_CAPABILITIES,
                "serverInfo": MCP_SERVER_INFO,
            })

        elif method == "notifications/initialized":
            return _jsonrpc_result(req_id, {})

        elif method == "tools/list":
            return _jsonrpc_result(req_id, {"tools": MCP_TOOLS})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result = _execute_mcp_tool(tool_name, tool_args)
            return _jsonrpc_result(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, default=str)}],
                "isError": "error" in result,
            })

        elif method == "prompts/list":
            return _jsonrpc_result(req_id, {"prompts": MCP_PROMPTS})

        elif method == "prompts/get":
            prompt_name = params.get("name", "")
            if prompt_name == "pilotsuite_context":
                return _jsonrpc_result(req_id, {
                    "description": "PilotSuite system context",
                    "messages": [{
                        "role": "user",
                        "content": {"type": "text", "text": _get_pilotsuite_context_prompt()},
                    }],
                })
            return _jsonrpc_error(req_id, -32602, f"Unknown prompt: {prompt_name}")

        elif method == "ping":
            return _jsonrpc_result(req_id, {})

        else:
            return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    except Exception as exc:
        logger.exception("MCP endpoint error")
        return _jsonrpc_error(None, -32603, "Internal server error")


def _jsonrpc_result(req_id, result):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})


def _jsonrpc_error(req_id, code, message):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})
