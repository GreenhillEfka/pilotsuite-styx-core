"""Entity to Widget Mapping.

Maps HomeAssistant entities to dashboard widgets based on:
- Entity domain (light, switch, sensor, etc.)
- Entity attributes
- Area/room assignment
- User preferences
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WidgetType(str, Enum):
    """Widget types for dashboard display."""
    
    LIGHT = "light"
    SWITCH = "switch"
    CLIMATE = "climate"
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    COVER = "cover"
    MEDIA_PLAYER = "media_player"
    CAMERA = "camera"
    LOCK = "lock"
    ALARM_CONTROL_PANEL = "alarm_control_panel"
    BUTTON = "button"
    SCENE = "scene"
    SCRIPT = "script"
    SELECT = "select"
    NUMBER = "number"
    TEXT = "text"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    NOTIFY = "notify"
    STATION = "station"
    WATER_HEATER = "water_heater"
    LAWN_MOWER = "lawn_mower"
    VACUUM = "vacuum"
    UNKNOWN = "unknown"


class SensorDeviceClass(str, Enum):
    """Sensor device classes."""
    
    APPARENT_POWER = "apparent_power"
    AQI = "aqi"
    ATMOSPHERIC_PRESSURE = "atmospheric_pressure"
    BATTERY = "battery"
    CO = "co"
    CO2 = "co2"
    CURRENT = "current"
    DATA_RATE = "data_rate"
    DATA_SIZE = "data_size"
    DATE = "date"
    DISTANCE = "distance"
    DURATION = "duration"
    ENERGY = "energy"
    ENERGY_STORAGE = "energy_storage"
    FREQUENCY = "frequency"
    GAS = "gas"
    HUMIDITY = "humidity"
    ILLUMINANCE = "illuminance"
    IRRADIANCE = "irradiance"
    MOISTURE = "moisture"
    MONETARY = "monetary"
    NITROGEN_DIOXIDE = "nitrogen_dioxide"
    NITROGEN_MONOXIDE = "nitrogen_monoxide"
    NITROUS_OXIDE = "nitrous_oxide"
    OZONE = "ozone"
    PH = "ph"
    PM1 = "pm1"
    PM10 = "pm10"
    PM25 = "pm25"
    POWER_FACTOR = "power_factor"
    POWER = "power"
    PRECIPITATION = "precipitation"
    PRECIPITATION_INTENSITY = "precipitation_intensity"
    PRESSURE = "pressure"
    REACTIVE_POWER = "reactive_power"
    SIGNAL_STRENGTH = "signal_strength"
    SOUND_PRESSURE = "sound_pressure"
    SPEED = "speed"
    SULPHUR_DIOXIDE = "sulphur_dioxide"
    TEMPERATURE = "temperature"
    TIMESTAMP = "timestamp"
    VOLATILE_ORGANIC_COMPOUNDS = "volatile_organic_compounds"
    VOLTAGE = "voltage"
    VOLUME = "volume"
    VOLUME_STORAGE = "volume_storage"
    VOLUME_FLOW_RATE = "volume_flow_rate"
    WATER = "water"
    WEIGHT = "weight"
    WIND_SPEED = "wind_speed"


@dataclass
class EntityMapping:
    """Mapping from HA entity to widget."""
    
    entity_id: str
    widget_type: WidgetType
    name: str
    area_id: Optional[str] = None
    area_name: Optional[str] = None
    device_class: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    icon: Optional[str] = None
    state: Optional[str] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher = more important
    metadata: dict[str, Any] = field(default_factory=dict)


class EntityMapper:
    """Maps HomeAssistant entities to widgets."""
    
    # Domain to widget type mapping
    DOMAIN_WIDGET_MAP = {
        "light": WidgetType.LIGHT,
        "switch": WidgetType.SWITCH,
        "climate": WidgetType.CLIMATE,
        "sensor": WidgetType.SENSOR,
        "binary_sensor": WidgetType.BINARY_SENSOR,
        "cover": WidgetType.COVER,
        "media_player": WidgetType.MEDIA_PLAYER,
        "camera": WidgetType.CAMERA,
        "lock": WidgetType.LOCK,
        "alarm_control_panel": WidgetType.ALARM_CONTROL_PANEL,
        "button": WidgetType.BUTTON,
        "scene": WidgetType.SCENE,
        "script": WidgetType.SCRIPT,
        "select": WidgetType.SELECT,
        "number": WidgetType.NUMBER,
        "text": WidgetType.TEXT,
        "date": WidgetType.DATE,
        "datetime": WidgetType.DATETIME,
        "time": WidgetType.TIME,
        "notify": WidgetType.NOTIFY,
        "station": WidgetType.STATION,
        "water_heater": WidgetType.WATER_HEATER,
        "lawn_mower": WidgetType.LAWN_MOWER,
        "vacuum": WidgetType.VACUUM,
    }
    
    # Icon mappings by domain
    DOMAIN_ICONS = {
        "light": "mdi:lightbulb",
        "switch": "mdi:toggle-switch",
        "climate": "mdi:thermostat",
        "sensor": "mdi:gauge",
        "binary_sensor": "mdi:motion-sensor",
        "cover": "mdi:blinds",
        "media_player": "mdi:television",
        "camera": "mdi:cctv",
        "lock": "mdi:lock",
        "alarm_control_panel": "mdi:shield",
        "button": "mdi:button",
        "scene": "mdi:palette",
        "script": "mdi:script",
        "vacuum": "mdi:robot-vacuum",
    }
    
    # Sensor device class to icon mapping
    SENSOR_ICONS = {
        SensorDeviceClass.TEMPERATURE: "mdi:thermometer",
        SensorDeviceClass.HUMIDITY: "mdi:water-percent",
        SensorDeviceClass.PRESSURE: "mdi:gauge",
        SensorDeviceClass.ILLUMINANCE: "mdi:brightness-6",
        SensorDeviceClass.POWER: "mdi:flash",
        SensorDeviceClass.ENERGY: "mdi:lightning-bolt",
        SensorDeviceClass.VOLTAGE: "mdi:current-ac",
        SensorDeviceClass.CURRENT: "mdi:current-dc",
        SensorDeviceClass.BATTERY: "mdi:battery",
        SensorDeviceClass.CO2: "mdi:molecule-co2",
        SensorDeviceClass.PM25: "mdi:air-filter",
        SensorDeviceClass.SOUND_PRESSURE: "mdi:volume-high",
    }
    
    def __init__(self):
        self._area_registry: dict[str, dict[str, Any]] = {}
        self._entity_mappings: dict[str, EntityMapping] = {}
    
    def update_area_registry(self, areas: list[dict[str, Any]]) -> None:
        """Update area registry from HA."""
        self._area_registry = {
            area["area_id"]: area
            for area in areas
            if isinstance(area, dict) and "area_id" in area
        }
    
    def map_entity(self, entity_state: dict[str, Any]) -> Optional[EntityMapping]:
        """Map a single entity state to a widget."""
        if not isinstance(entity_state, dict):
            return None
        
        entity_id = entity_state.get("entity_id", "")
        if not entity_id:
            return None
        
        # Parse domain from entity_id (e.g., "light.living_room" -> "light")
        parts = entity_id.split(".", 1)
        if len(parts) != 2:
            return None
        
        domain, object_id = parts
        widget_type = self.DOMAIN_WIDGET_MAP.get(domain, WidgetType.UNKNOWN)
        
        # Get entity attributes
        attributes = entity_state.get("attributes", {})
        state = entity_state.get("state")
        
        # Determine name
        name = attributes.get("friendly_name", object_id.replace("_", " ").title())
        
        # Get area
        area_id = attributes.get("area_id")
        area_name = None
        if area_id and area_id in self._area_registry:
            area_name = self._area_registry[area_id].get("name")
        
        # Get device class for sensors
        device_class = None
        if domain == "sensor":
            device_class = attributes.get("device_class")
        
        # Determine icon
        icon = attributes.get("icon")
        if not icon:
            icon = self._get_icon(domain, device_class)
        
        # Determine priority
        priority = self._calculate_priority(domain, device_class, attributes)
        
        # Get unit of measurement
        unit = attributes.get("unit_of_measurement")
        
        mapping = EntityMapping(
            entity_id=entity_id,
            widget_type=widget_type,
            name=name,
            area_id=area_id,
            area_name=area_name,
            device_class=device_class,
            unit_of_measurement=unit,
            icon=icon,
            state=state,
            attributes=attributes,
            priority=priority,
            metadata={
                "domain": domain,
                "object_id": object_id,
            }
        )
        
        self._entity_mappings[entity_id] = mapping
        return mapping
    
    def _get_icon(self, domain: str, device_class: Optional[str]) -> str:
        """Get icon for entity."""
        # Check domain-specific icon
        if domain == "sensor" and device_class:
            # Try device class specific icon
            try:
                sensor_class = SensorDeviceClass(device_class)
                return self.SENSOR_ICONS.get(sensor_class, "mdi:gauge")
            except ValueError:
                pass
        
        # Fallback to domain icon
        return self.DOMAIN_ICONS.get(domain, "mdi:help-circle")
    
    def _calculate_priority(
        self,
        domain: str,
        device_class: Optional[str],
        attributes: dict[str, Any]
    ) -> int:
        """Calculate widget priority (higher = more important)."""
        priority = 0
        
        # Critical domains
        if domain in ["alarm_control_panel", "lock", "camera"]:
            priority += 100
        
        # Climate control
        if domain == "climate":
            priority += 80
        
        # Lighting
        if domain == "light":
            priority += 60
        
        # Important sensors
        if domain == "sensor":
            important_classes = [
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.HUMIDITY,
                SensorDeviceClass.BATTERY,
                SensorDeviceClass.SMOKE,
                SensorDeviceClass.CO,
            ]
            if device_class in important_classes:
                priority += 50
        
        # Switches and plugs
        if domain == "switch":
            priority += 40
        
        return priority
    
    def map_entities(self, entities: list[dict[str, Any]]) -> list[EntityMapping]:
        """Map multiple entities."""
        mappings = []
        
        for entity_state in entities:
            mapping = self.map_entity(entity_state)
            if mapping:
                mappings.append(mapping)
        
        # Sort by priority (highest first)
        mappings.sort(key=lambda x: x.priority, reverse=True)
        
        return mappings
    
    def get_mapping(self, entity_id: str) -> Optional[EntityMapping]:
        """Get mapping for specific entity."""
        return self._entity_mappings.get(entity_id)
    
    def get_by_area(self, area_id: str) -> list[EntityMapping]:
        """Get all mappings for a specific area."""
        return [
            m for m in self._entity_mappings.values()
            if m.area_id == area_id
        ]
    
    def get_by_widget_type(self, widget_type: WidgetType) -> list[EntityMapping]:
        """Get all mappings for a specific widget type."""
        return [
            m for m in self._entity_mappings.values()
            if m.widget_type == widget_type
        ]
    
    def get_by_domain(self, domain: str) -> list[EntityMapping]:
        """Get all mappings for a specific domain."""
        return [
            m for m in self._entity_mappings.values()
            if m.metadata.get("domain") == domain
        ]
    
    def clear(self) -> None:
        """Clear all mappings."""
        self._entity_mappings.clear()
