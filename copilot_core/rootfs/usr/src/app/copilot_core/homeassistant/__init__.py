"""HomeAssistant Integration Package.

Provides async client, auto-discovery, and entity mapping for HomeAssistant.

Usage:
    from copilot_core.homeassistant import HomeAssistantClient, AutoDiscovery, EntityMapper
    
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
"""

try:
    from .client import (
        HomeAssistantClient,
        HAConnectionConfig,
        HAConnectionStatus,
    )
except ImportError:
    HomeAssistantClient = None  # type: ignore[assignment,misc]
    HAConnectionConfig = None  # type: ignore[assignment,misc]
    HAConnectionStatus = None  # type: ignore[assignment,misc]

try:
    from .auto_discovery import (
        AutoDiscovery,
        DiscoveredInstance,
    )
except ImportError:
    AutoDiscovery = None  # type: ignore[assignment,misc]
    DiscoveredInstance = None  # type: ignore[assignment,misc]

from .entity_mapper import (
    EntityMapper,
    EntityMapping,
    WidgetType,
    SensorDeviceClass,
)

try:
    from .api import (
        ha_discovery_bp,
        init_ha_discovery_api,
    )
except ImportError:
    ha_discovery_bp = None  # type: ignore[assignment,misc]
    init_ha_discovery_api = None  # type: ignore[assignment,misc]

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
    
    # API
    "ha_discovery_bp",
    "init_ha_discovery_api",
]
