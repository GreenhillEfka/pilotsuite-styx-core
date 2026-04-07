"""Device Discovery — Auto-Discovery, Network Scan, Protocol Detection."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import time
import hashlib

logger = logging.getLogger(__name__)


class DeviceProtocol(Enum):
    """Device communication protocols."""
    MATTER = "matter"
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"
    WIFI = "wifi"
    BLE = "ble"
    THREAD = "thread"
    MQTT = "mqtt"
    HTTP = "http"
    MODBUS = "modbus"


class DeviceType(Enum):
    """Device types."""
    LIGHT = "light"
    SWITCH = "switch"
    SENSOR = "sensor"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    CAMERA = "camera"
    SPEAKER = "speaker"
    APPLIANCE = "appliance"
    HUB = "hub"
    UNKNOWN = "unknown"


@dataclass
class DiscoveredDevice:
    """Discovered device information."""
    id: str
    name: str
    device_type: DeviceType
    protocol: DeviceProtocol
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    port: Optional[int] = None
    manufacturer: str = ""
    model: str = ""
    firmware_version: str = ""
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: float = field(default_factory=lambda: time.time())
    last_seen: Optional[float] = None
    paired: bool = False


class DeviceDiscoveryEngine:
    """Automatic device discovery engine."""

    def __init__(self):
        self._discovered_devices: Dict[str, DiscoveredDevice] = {}
        self._discovery_history: List[Dict] = []
        self._scan_results: Dict[str, List] = {}
        self._protocol_handlers: Dict[DeviceProtocol, callable] = {}

    def register_protocol_handler(self, protocol: DeviceProtocol, handler: callable):
        """Register a discovery handler for a protocol."""
        self._protocol_handlers[protocol] = handler
        logger.info(f"Protocol handler registered: {protocol.value}")

    def scan_network(self, subnet: str = "192.168.1.0/24", timeout_seconds: int = 5) -> List[DiscoveredDevice]:
        """Scan network for devices."""
        logger.info(f"Starting network scan: {subnet}")
        
        discovered = []
        
        # Simulated network scan
        # In production, would use actual network scanning (nmap, arp-scan, etc.)
        simulated_devices = [
            {
                "ip": "192.168.1.10",
                "mac": "AA:BB:CC:DD:EE:01",
                "protocol": DeviceProtocol.WIFI,
                "type": DeviceType.LIGHT,
                "name": "Smart Bulb 1",
            },
            {
                "ip": "192.168.1.11",
                "mac": "AA:BB:CC:DD:EE:02",
                "protocol": DeviceProtocol.ZIGBEE,
                "type": DeviceType.SENSOR,
                "name": "Motion Sensor",
            },
            {
                "ip": "192.168.1.12",
                "mac": "AA:BB:CC:DD:EE:03",
                "protocol": DeviceProtocol.MATTER,
                "type": DeviceType.THERMOSTAT,
                "name": "Smart Thermostat",
            },
        ]
        
        for sim in simulated_devices:
            device = self._create_discovered_device(sim)
            discovered.append(device)
            self._discovered_devices[device.id] = device
        
        self._scan_results[subnet] = discovered
        self._discovery_history.append({
            "type": "network_scan",
            "subnet": subnet,
            "devices_found": len(discovered),
            "timestamp": time.time(),
        })
        
        logger.info(f"Network scan complete: {len(discovered)} devices found")
        return discovered

    def _create_discovered_device(self, device_info: Dict) -> DiscoveredDevice:
        """Create a discovered device object."""
        device_id = hashlib.sha256(
            f"{device_info.get('mac', '')}{device_info.get('ip', '')}".encode()
        ).hexdigest()[:16]
        
        return DiscoveredDevice(
            id=device_id,
            name=device_info.get("name", "Unknown Device"),
            device_type=device_info.get("type", DeviceType.UNKNOWN),
            protocol=device_info.get("protocol", DeviceProtocol.UNKNOWN),
            ip_address=device_info.get("ip"),
            mac_address=device_info.get("mac"),
            port=device_info.get("port"),
            manufacturer=device_info.get("manufacturer", ""),
            model=device_info.get("model", ""),
            firmware_version=device_info.get("firmware", ""),
            capabilities=device_info.get("capabilities", []),
        )

    def discover_matter_devices(self) -> List[DiscoveredDevice]:
        """Discover Matter devices on the network."""
        logger.info("Discovering Matter devices...")
        
        # Simulated Matter discovery via mDNS
        matter_devices = [
            {
                "name": "Matter Light",
                "protocol": DeviceProtocol.MATTER,
                "type": DeviceType.LIGHT,
                "ip": "192.168.1.20",
            },
            {
                "name": "Matter Lock",
                "protocol": DeviceProtocol.MATTER,
                "type": DeviceType.LOCK,
                "ip": "192.168.1.21",
            },
        ]
        
        discovered = []
        for sim in matter_devices:
            device = self._create_discovered_device(sim)
            discovered.append(device)
            self._discovered_devices[device.id] = device
        
        logger.info(f"Matter discovery: {len(discovered)} devices")
        return discovered

    def discover_zigbee_devices(self) -> List[DiscoveredDevice]:
        """Discover Zigbee devices via coordinator."""
        logger.info("Discovering Zigbee devices...")
        
        # Simulated Zigbee discovery
        zigbee_devices = [
            {
                "name": "Zigbee Switch",
                "protocol": DeviceProtocol.ZIGBEE,
                "type": DeviceType.SWITCH,
            },
            {
                "name": "Zigbee Sensor",
                "protocol": DeviceProtocol.ZIGBEE,
                "type": DeviceType.SENSOR,
            },
        ]
        
        discovered = []
        for sim in zigbee_devices:
            device = self._create_discovered_device(sim)
            discovered.append(device)
            self._discovered_devices[device.id] = device
        
        logger.info(f"Zigbee discovery: {len(discovered)} devices")
        return discovered

    def pair_device(self, device_id: str, pairing_data: Optional[Dict] = None) -> bool:
        """Pair a discovered device."""
        if device_id not in self._discovered_devices:
            return False
        
        device = self._discovered_devices[device_id]
        device.paired = True
        device.last_seen = time.time()
        
        if pairing_data:
            device.metadata.update(pairing_data)
        
        logger.info(f"Device paired: {device.name} ({device_id})")
        return True

    def unpair_device(self, device_id: str) -> bool:
        """Unpair a device."""
        if device_id not in self._discovered_devices:
            return False
        
        device = self._discovered_devices[device_id]
        device.paired = False
        
        logger.info(f"Device unpaired: {device.name} ({device_id})")
        return True

    def get_unpaired_devices(self) -> List[DiscoveredDevice]:
        """Get list of unpaired devices."""
        return [d for d in self._discovered_devices.values() if not d.paired]

    def get_devices_by_protocol(self, protocol: DeviceProtocol) -> List[DiscoveredDevice]:
        """Get devices by protocol."""
        return [d for d in self._discovered_devices.values() if d.protocol == protocol]

    def get_devices_by_type(self, device_type: DeviceType) -> List[DiscoveredDevice]:
        """Get devices by type."""
        return [d for d in self._discovered_devices.values() if d.device_type == device_type]

    def remove_device(self, device_id: str) -> bool:
        """Remove a device from discovery list."""
        if device_id in self._discovered_devices:
            del self._discovered_devices[device_id]
            logger.info(f"Device removed: {device_id}")
            return True
        return False

    def get_discovery_history(self, limit: int = 50) -> List[Dict]:
        """Get discovery history."""
        return self._discovery_history[-limit:]

    def export_devices(self) -> List[Dict]:
        """Export discovered devices for integration."""
        return [
            {
                "id": d.id,
                "name": d.name,
                "type": d.device_type.value,
                "protocol": d.protocol.value,
                "ip": d.ip_address,
                "mac": d.mac_address,
                "paired": d.paired,
                "capabilities": d.capabilities,
            }
            for d in self._discovered_devices.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get discovery statistics."""
        by_protocol = {}
        by_type = {}
        
        for d in self._discovered_devices.values():
            proto = d.protocol.value
            dtype = d.device_type.value
            
            by_protocol[proto] = by_protocol.get(proto, 0) + 1
            by_type[dtype] = by_type.get(dtype, 0) + 1
        
        return {
            "total_discovered": len(self._discovered_devices),
            "paired": len([d for d in self._discovered_devices.values() if d.paired]),
            "unpaired": len([d for d in self._discovered_devices.values() if not d.paired]),
            "by_protocol": by_protocol,
            "by_type": by_type,
            "scans_run": len(self._discovery_history),
        }


# Global default discovery engine
default_discovery: Optional[DeviceDiscoveryEngine] = None


def init_device_discovery() -> DeviceDiscoveryEngine:
    """Initialize global device discovery engine."""
    global default_discovery
    default_discovery = DeviceDiscoveryEngine()
    return default_discovery
