"""HomeAssistant Integration Package.

Provides async client, auto-discovery, entity mapping, and WebSocket event handling.

Usage:
    from copilot_core.homeassistant import (
        HomeAssistantClient,
        AutoDiscovery,
        EntityMapper,
        HomeAssistantWebSocketClient,
        EventHandler,
    )
    
    # Auto-discovery
    discovery = AutoDiscovery()
    instances = await discovery.discover()
    
    # Connect
    client = await discovery.connect(
        base_url="http://homeassistant.local:8123",
        access_token="your-token"
    )
    
    # Get data
    areas = await client.get_areas()
    states = await client.get_states()
    
    # Map entities
    mapper = EntityMapper()
    mapper.update_area_registry(areas)
    mappings = mapper.map_entities(states)
    
    # WebSocket events
    ws_client = HomeAssistantWebSocketClient()
    await ws_client.connect()
    await ws_client.subscribe_events(["state_changed"])
"""

from .client import (
    HomeAssistantClient,
    HAConnectionConfig,
    HAConnectionStatus,
)
from .auto_discovery import (
    AutoDiscovery,
    DiscoveredInstance,
)
from .entity_mapper import (
    EntityMapper,
    EntityMapping,
    WidgetType,
    SensorDeviceClass,
)
from .websocket_client import (
    HomeAssistantWebSocketClient,
    WebSocketConfig,
    WebSocketStatus,
    ConnectionState,
)
from .event_handler import (
    EventHandler,
    HAEvent,
    EventQueue,
    EventHistory,
    EventType,
    create_standard_subscriptions,
)
from .api import (
    ha_discovery_bp,
    init_ha_discovery_api,
)
from ..api.v1.ha_events import (
    ha_events_bp,
    init_ha_events_api,
    register_socketio_handlers,
)

__all__ = [
    # Client
    "HomeAssistantClient",
    "HAConnectionConfig",
    "HAConnectionStatus",
    
    # Auto-discovery
    "AutoDiscovery",
    "DiscoveredInstance",
    
    # Entity mapping
    "EntityMapper",
    "EntityMapping",
    "WidgetType",
    "SensorDeviceClass",
    
    # WebSocket client
    "HomeAssistantWebSocketClient",
    "WebSocketConfig",
    "WebSocketStatus",
    "ConnectionState",
    
    # Event handling
    "EventHandler",
    "HAEvent",
    "EventQueue",
    "EventHistory",
    "EventType",
    "create_standard_subscriptions",
    
    # API blueprints
    "ha_discovery_bp",
    "ha_events_bp",
    "init_ha_discovery_api",
    "init_ha_events_api",
    "register_socketio_handlers",
]
