"""Matter/Thread Integration — Smart Home Standard, Multi-Protocol Bridge."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MatterDeviceType(Enum):
    """Matter device types."""
    ON_OFF_LIGHT = "on_off_light"
    DIMMABLE_LIGHT = "dimmable_light"
    COLOR_LIGHT = "color_light"
    ON_OFF_PLUGIN = "on_off_plugin"
    THERMOSTAT = "thermostat"
    DOOR_LOCK = "door_lock"
    WINDOW_COVERING = "window_covering"
    MOTION_SENSOR = "motion_sensor"
    CONTACT_SENSOR = "contact_sensor"
    TEMPERATURE_SENSOR = "temperature_sensor"
    PRESENCE_SENSOR = "presence_sensor"


class ProtocolType(Enum):
    """Supported protocols."""
    MATTER = "matter"
    THREAD = "thread"
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"
    WIFI = "wifi"
    BLE = "ble"


@dataclass
class MatterDevice:
    """Matter device representation."""
    node_id: int
    endpoint_id: int
    device_type: MatterDeviceType
    vendor_id: int
    product_id: int
    unique_id: str
    label: str
    protocols: List[ProtocolType] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    online: bool = True


@dataclass
class MatterCluster:
    """Matter cluster configuration."""
    cluster_id: int
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    commands: List[str] = field(default_factory=list)
    events: List[str] = field(default_factory=list)


class MatterBridge:
    """Matter/Thread protocol bridge for PilotSuite."""

    # Standard Matter clusters
    MATTER_CLUSTERS = {
        0x0006: MatterCluster(0x0006, "On/Off", 
            attributes={"on_off": bool},
            commands=["on", "off", "toggle"]),
        0x0008: MatterCluster(0x0008, "Level Control",
            attributes={"current_level": int, "target_level": int},
            commands=["move_to_level", "move", "step", "stop"]),
        0x0300: MatterCluster(0x0300, "Color Control",
            attributes={"current_hue": int, "current_saturation": int, "color_temperature": int},
            commands=["move_to_hue", "move_to_saturation", "move_to_color_temperature"]),
        0x0102: MatterCluster(0x0102, "Door Lock",
            attributes={"lock_state": int, "locked": bool},
            commands=["lock", "unlock"]),
        0x0101: MatterCluster(0x0101, "Thermostat",
            attributes={"system_mode": int, "occupied_heating_setpoint": float, "local_temperature": float},
            commands=["set_heating_setpoint", "set_cooling_setpoint", "set_mode"]),
    }

    def __init__(self):
        self._devices: Dict[int, MatterDevice] = {}
        self._commissioned: bool = False
        self._fabric_id: Optional[int] = None
        self._operational_credentials: Optional[Dict] = None
        self._thread_network: Optional[Dict] = None

    def commission_device(self, setup_code: str, label: str) -> Optional[MatterDevice]:
        """Commission a new Matter device."""
        logger.info(f"Commissioning device with setup code: {setup_code[:4]}****")
        
        # Simulated commissioning
        # In production, would use real Matter commissioning flow
        self._commissioned = True
        self._fabric_id = 1
        
        device = MatterDevice(
            node_id=len(self._devices) + 1,
            endpoint_id=1,
            device_type=MatterDeviceType.ON_OFF_LIGHT,
            vendor_id=0x1234,
            product_id=0x5678,
            unique_id=f"matter_{setup_code[-8:]}",
            label=label,
            protocols=[ProtocolType.MATTER, ProtocolType.THREAD],
            attributes={"on_off": False},
        )
        
        self._devices[device.node_id] = device
        logger.info(f"Device commissioned: {label} (node {device.node_id})")
        
        return device

    def decommission_device(self, node_id: int) -> bool:
        """Decommission a Matter device."""
        if node_id not in self._devices:
            return False
        
        del self._devices[node_id]
        logger.info(f"Device decommissioned: node {node_id}")
        return True

    def discover_devices(self) -> List[MatterDevice]:
        """Discover Matter devices on the network."""
        logger.info("Discovering Matter devices...")
        
        # Simulated discovery
        # In production, would use mDNS/BLE discovery
        return list(self._devices.values())

    def read_attribute(self, node_id: int, endpoint_id: int, cluster_id: int, attribute_id: int) -> Optional[Any]:
        """Read a Matter attribute."""
        if node_id not in self._devices:
            return None
        
        device = self._devices[node_id]
        
        # Map cluster/attribute to device attribute
        if cluster_id == 0x0006 and attribute_id == 0:  # On/Off
            return device.attributes.get("on_off")
        elif cluster_id == 0x0008 and attribute_id == 0:  # Level
            return device.attributes.get("current_level", 255)
        
        return None

    def write_attribute(self, node_id: int, endpoint_id: int, cluster_id: int, attribute_id: int, value: Any) -> bool:
        """Write a Matter attribute."""
        if node_id not in self._devices:
            return False
        
        device = self._devices[node_id]
        
        if cluster_id == 0x0006 and attribute_id == 0:  # On/Off
            device.attributes["on_off"] = bool(value)
            logger.info(f"Device {node_id} set to {'on' if value else 'off'}")
            return True
        
        return False

    def invoke_command(self, node_id: int, endpoint_id: int, cluster_id: int, command_id: int, payload: Dict) -> bool:
        """Invoke a Matter command."""
        if node_id not in self._devices:
            return False
        
        cluster = self.MATTER_CLUSTERS.get(cluster_id)
        if not cluster:
            logger.warning(f"Unknown cluster: 0x{cluster_id:04X}")
            return False
        
        device = self._devices[node_id]
        
        if cluster_id == 0x0006:  # On/Off
            if command_id == 0:  # On
                device.attributes["on_off"] = True
            elif command_id == 1:  # Off
                device.attributes["on_off"] = False
            elif command_id == 2:  # Toggle
                device.attributes["on_off"] = not device.attributes.get("on_off", False)
        
        logger.info(f"Command {command_id} invoked on device {node_id}")
        return True

    def setup_thread_network(self, network_name: str, password: str, channel: int = 15) -> Dict:
        """Setup Thread network for Matter devices."""
        self._thread_network = {
            "network_name": network_name,
            "channel": channel,
            "pan_id": 0x1234,
            "extended_pan_id": "0x1234567890ABCDEF",
            "network_key": "0x" + "00" * 16,  # Placeholder
            "active": True,
        }
        
        logger.info(f"Thread network setup: {network_name} (channel {channel})")
        return self._thread_network

    def get_border_agent_info(self) -> Dict:
        """Get border agent information."""
        return {
            "id": "border_agent_1",
            "status": "active",
            "thread_network": self._thread_network,
            "fabric_id": self._fabric_id,
            "commissioned_devices": len(self._devices),
        }

    def export_device_list(self) -> List[Dict]:
        """Export device list for HA integration."""
        return [
            {
                "node_id": d.node_id,
                "endpoint_id": d.endpoint_id,
                "device_type": d.device_type.value,
                "label": d.label,
                "unique_id": d.unique_id,
                "online": d.online,
                "protocols": [p.value for p in d.protocols],
                "attributes": d.attributes,
            }
            for d in self._devices.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get Matter bridge statistics."""
        return {
            "commissioned": self._commissioned,
            "fabric_id": self._fabric_id,
            "devices": len(self._devices),
            "thread_network_active": self._thread_network is not None,
            "device_types": list(set(d.device_type.value for d in self._devices.values())),
        }


# Global default Matter bridge
default_matter_bridge: Optional[MatterBridge] = None


def init_matter_bridge() -> MatterBridge:
    """Initialize global Matter bridge."""
    global default_matter_bridge
    default_matter_bridge = MatterBridge()
    return default_matter_bridge
