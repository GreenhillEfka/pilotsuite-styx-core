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
    {
        "name": "pilotsuite.get_zone_health",
        "description": "Get environmental health metrics for zones (temperature, humidity, CO2, lux, health score 0-100).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Optional zone name to filter"},
            },
        },
    },
    {
        "name": "pilotsuite.zones_list",
        "description": "List all Habitus zones with current occupancy, mode, and neuron state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Optional zone name filter"},
            },
        },
    },
    {
        "name": "pilotsuite.lights_control",
        "description": "Control lights in a zone (on/off, brightness, color temperature).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Zone name"},
                "action": {"type": "string", "enum": ["on", "off", "dim", "brighten"], "description": "Action to perform"},
                "brightness": {"type": "integer", "description": "Brightness 0-100 (for dim)"},
            },
            "required": ["zone", "action"],
        },
    },
    {
        "name": "pilotsuite.climate_control",
        "description": "Set climate/temperature for a zone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Zone name"},
                "temperature": {"type": "number", "description": "Target temperature in °C"},
                "action": {"type": "string", "enum": ["set", "up", "down"], "description": "Temperature action"},
            },
            "required": ["zone"],
        },
    },
    {
        "name": "pilotsuite.presence_status",
        "description": "Get current presence status for all zones (who is where, confidence).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Optional zone name"},
            },
        },
    },
    {
        "name": "pilotsuite.habits_get",
        "description": "Get discovered habits/routines (time-based, device-based, mood-based).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Filter by type: time, device, mood"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "pilotsuite.energy_detailed",
        "description": "Get detailed energy breakdown: consumption by device, solar, battery, cost forecast.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Period: day, week, month"},
                "zone": {"type": "string", "description": "Optional zone filter"},
            },
        },
    },
    {
        "name": "pilotsuite.rag_search",
        "description": "Search the RAG knowledge base for relevant documents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 5},
                "rerank": {"type": "boolean", "default": True},
            },
            "required": ["query"],
        },
    },
    {
        "name": "pilotsuite.voice_command",
        "description": "Execute a voice command (text-based, returns intent + response).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Voice command text (German or English)"},
                "language": {"type": "string", "default": "de"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "pilotsuite.automation_rules",
        "description": "List active automation rules, their triggers, and last evaluation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Optional zone filter"},
                "status": {"type": "string", "description": "Filter by status: active, disabled, error"},
            },
        },
    },
    {
        "name": "pilotsuite.media_control",
        "description": "Control media playback (play, pause, stop, volume, transfer between zones).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Zone name"},
                "action": {"type": "string", "enum": ["play", "pause", "stop", "transfer"], "description": "Media action"},
                "target_zone": {"type": "string", "description": "Target zone for transfer action"},
                "volume": {"type": "integer", "description": "Volume 0-100"},
            },
            "required": ["zone", "action"],
        },
    },
    {
        "name": "pilotsuite.events_query",
        "description": "Query recent events from the WAL (zone transitions, intents, rule evaluations).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Event type filter: zone_transition, intent_completion, rule_evaluation, learning_update"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "pilotsuite.brain_query",
        "description": "Query the Brain Graph for entity relationships and co-occurrence patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Entity ID to query neighbors for"},
                "relation_type": {"type": "string", "description": "Filter by relation type"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "pilotsuite.anomaly_status",
        "description": "Get current anomaly detection summary (critical, warning, info alerts).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sensor_type": {"type": "string", "description": "Filter by type: maintenance, media, gas, habit"},
            },
        },
    },
    {
        "name": "pilotsuite.system_status",
        "description": "Get PilotSuite Core system status (uptime, version, health, API latency).",
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

        elif name == "pilotsuite.get_zone_health":
            from ..zone_health import get_store, ZoneHealthMetrics
            store = get_store()
            zone_name = arguments.get("zone")
            all_metrics = store.get_all()
            if zone_name:
                filtered = {
                    zid: m for zid, m in all_metrics.items()
                    if zone_name.lower() in m.zone_name.lower()
                }
                result_zones = filtered
            else:
                result_zones = all_metrics

            if not result_zones:
                return {
                    "zones": 0,
                    "average_health_score": store.get_average_score(),
                    "message": "No zone health data available yet. Data arrives via HA→Core sync when HA is online."
                }

            return {
                "zones": len(result_zones),
                "average_health_score": round(store.get_average_score(), 1),
                "zones_data": {
                    zid: {
                        "zone_name": m.zone_name,
                        "health_score": round(m.health_score, 1),
                        "temperature": m.temperature,
                        "humidity": m.humidity,
                        "co2": m.co2,
                        "lux": m.lux,
                        "air_quality": m.air_quality,
                        "temp_comfort": m.temperature_comfort,
                        "humid_comfort": m.humidity_comfort,
                        "last_updated": m.last_updated.isoformat(),
                    }
                    for zid, m in result_zones.items()
                },
            }

        elif name == "pilotsuite.zones_list":
            zones_svc = services.get("habitus_service")
            if not zones_svc:
                return {"error": "HabitusService not available"}
            filter_zone = arguments.get("filter", "")
            zones = zones_svc.list_zones()
            if filter_zone:
                zones = [z for z in zones if filter_zone.lower() in str(z.get("name", "")).lower()]
            return {"zones": zones, "count": len(zones)}

        elif name == "pilotsuite.lights_control":
            zone = arguments.get("zone", "")
            action = arguments.get("action", "")
            brightness = arguments.get("brightness", 50)
            hs = services.get("habitus_service")
            if not hs:
                return {"error": "HabitusService not available"}
            if action == "on":
                hs.set_light(zone, True)
            elif action == "off":
                hs.set_light(zone, False)
            elif action == "dim":
                hs.set_light_brightness(zone, brightness)
            elif action == "brighten":
                hs.set_light_brightness(zone, min(100, brightness + 20))
            else:
                return {"error": f"Unknown action: {action}"}
            return {"ok": True, "zone": zone, "action": action, "brightness": brightness}

        elif name == "pilotsuite.climate_control":
            zone = arguments.get("zone", "")
            temperature = arguments.get("temperature")
            action = arguments.get("action", "set")
            hs = services.get("habitus_service")
            if not hs:
                return {"error": "HabitusService not available"}
            hs.set_climate(zone, temperature, action)
            return {"ok": True, "zone": zone, "temperature": temperature, "action": action}

        elif name == "pilotsuite.presence_status":
            presence_svc = services.get("presence_service")
            if not presence_svc:
                return {"error": "PresenceService not available"}
            zone = arguments.get("zone")
            if zone:
                status = presence_svc.get_zone_status(zone)
                return {"zone": zone, "status": status}
            return presence_svc.get_all_zones_status()

        elif name == "pilotsuite.habits_get":
            habitus_svc = services.get("habitus_service")
            if not habitus_svc:
                return {"error": "HabitusService not available"}
            habit_type = arguments.get("type")
            limit = arguments.get("limit", 10)
            habits = habitus_svc.get_habits(habit_type=habit_type, limit=limit)
            return {"habits": habits, "count": len(habits)}

        elif name == "pilotsuite.energy_detailed":
            energy_svc = services.get("energy_service")
            if not energy_svc:
                return {"error": "EnergyService not available"}
            period = arguments.get("period", "day")
            zone = arguments.get("zone")
            stats = energy_svc.get_detailed_stats(period=period, zone=zone)
            return stats

        elif name == "pilotsuite.rag_search":
            from ..rag.ollama_client import OllamaRAGClient
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            rerank = arguments.get("rerank", True)
            try:
                client = OllamaRAGClient()
                results = client.search(query, top_k=limit, rerank=rerank)
                return {"results": results, "query": query, "count": len(results)}
            except Exception as exc:
                return {"error": str(exc), "results": []}

        elif name == "pilotsuite.voice_command":
            from ..voice.voice_handler import VoiceIntentHandler
            text = arguments.get("text", "")
            language = arguments.get("language", "de")
            handler = services.get("voice_handler") or VoiceIntentHandler()
            result = handler.process_voice_command(text, language=language)
            return {"ok": True, **result}

        elif name == "pilotsuite.automation_rules":
            rules_svc = services.get("automation_service")
            if not rules_svc:
                return {"error": "AutomationService not available"}
            zone = arguments.get("zone")
            status = arguments.get("status")
            rules = rules_svc.list_rules(zone=zone, status=status)
            return {"rules": rules, "count": len(rules)}

        elif name == "pilotsuite.media_control":
            zone = arguments.get("zone", "")
            action = arguments.get("action", "")
            target_zone = arguments.get("target_zone")
            volume = arguments.get("volume")
            mw_svc = services.get("music_wolke_engine")
            if not mw_svc:
                return {"error": "MusicWolkeEngine not available"}
            if action == "play":
                sid = mw_svc.start_session(zone_id=zone, source_entity=f"sonos.{zone}", media_type="music", follow_enabled=False)
                return {"ok": True, "session_id": sid}
            elif action == "stop":
                stopped = mw_svc.stop_zone(zone)
                return {"ok": True, "stopped": stopped}
            elif action == "transfer":
                if not target_zone:
                    return {"error": "target_zone required for transfer"}
                transfers = mw_svc.on_zone_entry("user", target_zone)
                return {"ok": True, "transfers": transfers}
            elif volume is not None:
                mw_svc.set_volume(zone, volume)
                return {"ok": True, "volume": volume}
            return {"error": f"Unknown action: {action}"}

        elif name == "pilotsuite.events_query":
            from ..events.wal import WALReader
            event_type = arguments.get("type")
            limit = arguments.get("limit", 50)
            try:
                reader = WALReader()
                events = reader.read_events(event_type=event_type, limit=limit)
                return {"events": events, "count": len(events)}
            except Exception as exc:
                return {"error": str(exc), "events": []}

        elif name == "pilotsuite.brain_query":
            bg_svc = services.get("brain_graph_service")
            if not bg_svc:
                return {"error": "BrainGraphService not available"}
            entity_id = arguments.get("entity_id")
            relation_type = arguments.get("relation_type")
            limit = arguments.get("limit", 20)
            if entity_id:
                neighbors = bg_svc.get_neighbors(entity_id, limit=limit, relation_type=relation_type)
                return {"entity_id": entity_id, "neighbors": neighbors}
            return {"error": "entity_id required"}

        elif name == "pilotsuite.anomaly_status":
            sensor_type = arguments.get("sensor_type")
            from ..anomaly.detection_engine import AnomalyDetectionEngine
            engine = services.get("anomaly_engine") or AnomalyDetectionEngine.get_instance()
            summary = engine.get_summary()
            if sensor_type:
                filtered = [a for a in summary.get("alerts", []) if a.get("sensor_type") == sensor_type]
                summary["alerts"] = filtered
            return summary

        elif name == "pilotsuite.system_status":
            import psutil
            from datetime import datetime
            uptime_seconds = psutil.boot_time()
            now = datetime.now().timestamp()
            return {
                "uptime_seconds": int(now - uptime_seconds),
                "version": COPILOT_VERSION,
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
            }

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
