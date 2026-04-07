"""
MCP-style Tool Server for PilotSuite Core

Proof-of-Concept: MCP-compatible function definitions
for Home Assistant services.

This provides structured tool definitions similar to MCP
that can be used by LLM-powered conversations.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# MCP-style Tool Definitions
class MCPTool:
    """Represents an MCP tool"""
    def __init__(self, name: str, description: str, input_schema: Dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


# Home Assistant Tools (MCP-style)
HA_TOOLS = [
    MCPTool(
        name="ha.call_service",
        description="Call a Home Assistant service to control devices",
        input_schema={
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The domain of the service (e.g., light, switch, climate, fan)"
                },
                "service": {
                    "type": "string", 
                    "description": "The service to call (e.g., turn_on, turn_off, set_temperature)"
                },
                "service_data": {
                    "type": "object",
                    "description": "Data to pass to the service",
                    "properties": {
                        "entity_id": {"type": "string", "description": "The entity to control"},
                        "brightness_pct": {"type": "number", "description": "Brightness 0-100"},
                        "temperature": {"type": "number", "description": "Target temperature"},
                        "color": {"type": "string", "description": "Color in hex format"}
                    }
                },
                "target": {
                    "type": "object",
                    "description": "Target area or device",
                    "properties": {
                        "area_id": {"type": "string"},
                        "device_id": {"type": "string"},
                        "entity_id": {"type": "string"}
                    }
                }
            },
            "required": ["domain", "service"]
        }
    ),
    
    MCPTool(
        name="ha.get_states",
        description="Get the current state of Home Assistant entities",
        input_schema={
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Filter by domain (e.g., light, sensor, switch)"
                },
                "entity_id": {
                    "type": "string", 
                    "description": "Filter by entity ID (supports wildcards)"
                },
                "area_id": {
                    "type": "string",
                    "description": "Filter by area"
                }
            }
        }
    ),
    
    MCPTool(
        name="ha.get_history",
        description="Get historical data for entities",
        input_schema={
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entity IDs to get history for"
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time (ISO 8601 format)"
                },
                "end_time": {
                    "type": "string",
                    "description": "End time (ISO 8601 format)"
                },
                "significant_changes_only": {
                    "type": "boolean",
                    "default": True,
                    "description": "Only return significant state changes"
                }
            },
            "required": ["entity_ids"]
        }
    ),
    
    MCPTool(
        name="ha.activate_scene",
        description="Activate a Home Assistant scene",
        input_schema={
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The scene entity to activate"
                }
            },
            "required": ["entity_id"]
        }
    ),
    
    MCPTool(
        name="ha.get_config",
        description="Get Home Assistant configuration information",
        input_schema={
            "type": "object",
            "properties": {}
        }
    ),
    
    MCPTool(
        name="ha.get_services",
        description="Get list of available Home Assistant services",
        input_schema={
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Filter services by domain"
                }
            }
        }
    ),
    
    MCPTool(
        name="ha.fire_event",
        description="Fire a custom event in Home Assistant",
        input_schema={
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "description": "The type of event to fire"
                },
                "event_data": {
                    "type": "object",
                    "description": "Data to include with the event"
                }
            },
            "required": ["event_type"]
        }
    ),
    
    MCPTool(
        name="calendar.get_events",
        description="Get calendar events from Home Assistant",
        input_schema={
            "type": "object",
            "properties": {
                "start_date_time": {
                    "type": "string",
                    "description": "Start datetime (ISO 8601)"
                },
                "end_date_time": {
                    "type": "string",
                    "description": "End datetime (ISO 8601)"
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Specific calendar entity ID"
                }
            }
        }
    ),
    
    MCPTool(
        name="weather.get_forecast",
        description="Get weather forecast",
        input_schema={
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Weather entity ID"
                },
                "type": {
                    "type": "string",
                    "enum": ["hourly", "daily", "twice_daily"],
                    "description": "Type of forecast"
                }
            },
            "required": ["entity_id"]
        }
    ),

    # -- PilotSuite Automation Tools -----------------------------------------

    MCPTool(
        name="pilotsuite.create_automation",
        description=(
            "Create a Home Assistant automation. Use this when the user asks to "
            "set up a rule like 'when X happens, do Y'. You MUST parse the user's "
            "intent into structured trigger and action data. Supports state, time, "
            "sun, and numeric_state triggers with turn_on/turn_off/scene/notify "
            "actions. Use numeric_state for sensor thresholds (e.g. humidity > 70%). "
            "Conditions can restrict when the automation fires."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "alias": {
                    "type": "string",
                    "description": "Human-readable name for the automation (e.g. 'Coffee grinder sync')"
                },
                "trigger_type": {
                    "type": "string",
                    "enum": ["state", "time", "sun", "numeric_state"],
                    "description": "Type of trigger: state (entity changes), time (at HH:MM), sun (sunset/sunrise), numeric_state (sensor crosses threshold)"
                },
                "trigger_entity": {
                    "type": "string",
                    "description": "Entity ID that triggers the automation (required for state and numeric_state triggers)"
                },
                "trigger_to": {
                    "type": "string",
                    "description": "Target state for state trigger (e.g. 'on', 'off', 'home', 'not_home')"
                },
                "trigger_from": {
                    "type": "string",
                    "description": "Optional: previous state for state trigger (e.g. 'off' -> 'on')"
                },
                "trigger_time": {
                    "type": "string",
                    "description": "Time for time trigger in HH:MM:SS format (e.g. '06:30:00')"
                },
                "trigger_sun_event": {
                    "type": "string",
                    "enum": ["sunset", "sunrise"],
                    "description": "Sun event for sun trigger"
                },
                "trigger_sun_offset": {
                    "type": "string",
                    "description": "Optional offset for sun trigger (e.g. '-00:30:00' for 30 min before)"
                },
                "trigger_above": {
                    "type": "number",
                    "description": "Trigger when sensor rises ABOVE this value (numeric_state only, e.g. 70 for 70% humidity)"
                },
                "trigger_below": {
                    "type": "number",
                    "description": "Trigger when sensor falls BELOW this value (numeric_state only, e.g. 20 for 20% battery)"
                },
                "conditions": {
                    "type": "array",
                    "description": "Optional list of conditions that must ALL pass for the automation to run. Use to restrict triggers (e.g. only fire if outdoor humidity < 80%).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["numeric_state", "template"],
                                "description": "Condition type: numeric_state checks a sensor value, template evaluates a Jinja2 expression"
                            },
                            "entity_id": {
                                "type": "string",
                                "description": "Entity to check (for numeric_state conditions)"
                            },
                            "above": {
                                "type": "number",
                                "description": "Condition passes when entity state is above this value"
                            },
                            "below": {
                                "type": "number",
                                "description": "Condition passes when entity state is below this value"
                            },
                            "value_template": {
                                "type": "string",
                                "description": "Jinja2 template for template condition (must evaluate to true/false)"
                            }
                        },
                        "required": ["type"]
                    }
                },
                "action_service": {
                    "type": "string",
                    "description": "HA service to call (e.g. 'light.turn_on', 'switch.turn_off', 'scene.turn_on', 'notify.persistent_notification')"
                },
                "action_entity": {
                    "type": "string",
                    "description": "Entity ID to act on (e.g. 'switch.coffee_grinder', 'light.living_room')"
                },
                "action_data": {
                    "type": "object",
                    "description": "Optional service data (e.g. {\"brightness_pct\": 50, \"color_temp\": 300})"
                }
            },
            "required": ["alias", "trigger_type", "action_service", "action_entity"]
        }
    ),

    MCPTool(
        name="pilotsuite.list_automations",
        description="List automations created by PilotSuite/Styx. Use this to show the user what automations have been created.",
        input_schema={
            "type": "object",
            "properties": {}
        }
    ),

    # -- Web Search & News Tools (v3.1.0) ------------------------------------

    MCPTool(
        name="pilotsuite.web_search",
        description=(
            "Search the web for current information. Use this when the user asks "
            "a question that requires up-to-date knowledge, research, or facts "
            "that you don't have. Returns titles, URLs, and snippets."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g. 'best smart home sensors 2026')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5, max 10)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    ),

    MCPTool(
        name="pilotsuite.get_news",
        description=(
            "Get current news headlines from German news sources (Tagesschau, Spiegel). "
            "Use this when the user asks about current events, news, or what's happening."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "max_items": {
                    "type": "integer",
                    "description": "Maximum number of news items (default 10)",
                    "default": 10
                }
            }
        }
    ),

    MCPTool(
        name="pilotsuite.get_warnings",
        description=(
            "Get regional warnings and alerts for the home's area. Includes civil protection "
            "warnings (NINA/BBK) and weather warnings (DWD). Use this when the user asks "
            "about safety, severe weather, or regional alerts."
        ),
        input_schema={
            "type": "object",
            "properties": {}
        }
    ),

    # -- Media Zone Tools (v3.1.0) -------------------------------------------

    MCPTool(
        name="pilotsuite.play_zone",
        description=(
            "Control media playback in a habitus zone. Can play, pause, set volume, "
            "or start specific media in a zone (e.g. 'play music in Wohnzimmer')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "zone_id": {
                    "type": "string",
                    "description": "The zone ID (e.g. 'wohnzimmer', 'kueche', 'schlafzimmer')"
                },
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "volume", "play_media"],
                    "description": "What to do: play (resume), pause, volume (set level), play_media (specific content)"
                },
                "volume": {
                    "type": "number",
                    "description": "Volume level 0.0-1.0 (only for action=volume)"
                },
                "media_content_id": {
                    "type": "string",
                    "description": "Media content to play (only for action=play_media)"
                },
                "media_content_type": {
                    "type": "string",
                    "description": "Type: music, video, playlist (only for action=play_media)",
                    "default": "music"
                }
            },
            "required": ["zone_id", "action"]
        }
    ),

    MCPTool(
        name="pilotsuite.musikwolke",
        description=(
            "Musikwolke (Smart Audio Follow): Music follows a person through habitus zones. "
            "Start a session to have audio follow a person, or stop an active session. "
            "Use when user says things like 'Musik soll mir folgen' or 'Musikwolke starten'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "status"],
                    "description": "start: begin following, stop: end session, status: list active sessions"
                },
                "person_id": {
                    "type": "string",
                    "description": "HA person entity (e.g. 'person.alice'). Required for start."
                },
                "source_zone": {
                    "type": "string",
                    "description": "Zone where music is currently playing. Required for start."
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID to stop. Required for stop."
                }
            },
            "required": ["action"]
        }
    ),

    MCPTool(
        name="pilotsuite.waste_status",
        description=(
            "Get waste collection schedule and status. Shows which waste types "
            "are being collected today, tomorrow, and in the coming days. "
            "Use when user asks about Müllabfuhr, waste collection, recycling, "
            "or when the next pickup is."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),

    MCPTool(
        name="pilotsuite.birthday_status",
        description=(
            "Get upcoming birthdays from the calendar. Shows today's birthdays "
            "and upcoming ones within 14 days. Use when user asks about birthdays, "
            "Geburtstage, or who has a birthday soon."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),

    MCPTool(
        name="pilotsuite.save_scene",
        description=(
            "Save the current state of a habitus zone as a scene. Captures lights, "
            "covers, climate, switches, and media states. Use when user says things "
            "like 'save this as a scene', 'speichere die aktuelle Stimmung', "
            "'Szene speichern', or 'merke dir diese Einstellung'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "zone_id": {
                    "type": "string",
                    "description": "The habitus zone ID (e.g., 'zone:wohnzimmer')"
                },
                "zone_name": {
                    "type": "string",
                    "description": "Display name of the zone (e.g., 'Wohnzimmer')"
                },
                "name": {
                    "type": "string",
                    "description": "Optional name for the scene (e.g., 'Filmabend')"
                },
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity IDs to capture (lights, switches, covers, climate, etc.)"
                },
            },
            "required": ["zone_id", "entity_ids"]
        }
    ),

    MCPTool(
        name="pilotsuite.apply_scene",
        description=(
            "Apply a previously saved scene to restore entity states in a zone. "
            "Use when user says 'apply the evening scene', 'Szene anwenden', "
            "'stelle die Filmabend-Szene ein', or 'wende Szene X an'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "scene_id": {
                    "type": "string",
                    "description": "The scene ID to apply"
                },
                "name": {
                    "type": "string",
                    "description": "Alternative: scene name to search for"
                },
            },
            "required": []
        }
    ),

    # v3.5.0 — Calendar, Shopping List, Reminders
    MCPTool(
        name="pilotsuite.calendar_events",
        description=(
            "Get calendar events for today or upcoming days. "
            "Use when user asks 'what's on my calendar?', 'Termine heute?', "
            "'was steht diese Woche an?', or 'habe ich morgen Termine?'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default 1 for today, max 30)"
                },
            },
            "required": []
        }
    ),

    MCPTool(
        name="pilotsuite.shopping_list",
        description=(
            "Manage the shopping list: add, list, or complete items. "
            "Use when user says 'add milk to shopping list', 'Einkaufsliste zeigen', "
            "'was muss ich einkaufen?', or 'Milch auf die Liste'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "complete", "clear_completed"],
                    "description": "Action: list items, add new item, complete item, or clear done items"
                },
                "name": {
                    "type": "string",
                    "description": "Item name (for 'add' action)"
                },
                "quantity": {
                    "type": "string",
                    "description": "Quantity (for 'add' action, e.g. '2 Liter', '500g')"
                },
                "item_id": {
                    "type": "string",
                    "description": "Item ID (for 'complete' action)"
                },
                "items": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"name": {"type": "string"}, "quantity": {"type": "string"}}},
                    "description": "Multiple items to add at once"
                },
            },
            "required": ["action"]
        }
    ),

    MCPTool(
        name="pilotsuite.reminder",
        description=(
            "Manage reminders: add, list, complete, or snooze. "
            "Use when user says 'remind me to...', 'Erinnerung erstellen', "
            "'erinnere mich an...', 'was sind meine Erinnerungen?', "
            "'Erinnerung in 30 Minuten', or 'snooze reminder'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "complete", "snooze"],
                    "description": "Action: list, add, complete, or snooze a reminder"
                },
                "title": {
                    "type": "string",
                    "description": "Reminder title (for 'add' action)"
                },
                "description": {
                    "type": "string",
                    "description": "Optional description"
                },
                "due_at": {
                    "type": "string",
                    "description": "Due date/time as ISO string or epoch (for 'add' action)"
                },
                "reminder_id": {
                    "type": "string",
                    "description": "Reminder ID (for 'complete' or 'snooze' action)"
                },
                "snooze_minutes": {
                    "type": "integer",
                    "description": "Minutes to snooze (for 'snooze' action, default 30)"
                },
            },
            "required": ["action"]
        }
    ),
]


def get_tools() -> List[Dict]:
    """Get all available tools in MCP format"""
    return [tool.to_dict() for tool in HA_TOOLS]


def get_tool_by_name(name: str) -> Optional[MCPTool]:
    """Get a specific tool by name"""
    for tool in HA_TOOLS:
        if tool.name == name:
            return tool
    return None


def get_openai_functions() -> List[Dict]:
    """Get tools in OpenAI function calling format"""
    functions = []
    for tool in HA_TOOLS:
        functions.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema
            }
        })
    return functions
