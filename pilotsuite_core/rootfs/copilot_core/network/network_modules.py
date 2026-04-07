"""Network Modules — ZigBee/Matter/Thread Integration (SOTA 2026).

Unterstützte Protokolle:
1. ZigBee (ZHA/ZigBee2MQTT)
2. Matter (IPv6-based)
3. Thread (Border Router)

Features:
- Topology Discovery
- Device Health Monitoring
- Network Visualization
- Protocol-aware Automation

Integration:
- Network → Health Monitor
- Network → Dashboard
- Network → Habitus (lernen von Network-Events)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
import threading

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# NETWORK PROTOCOLS
# =============================================================================

class NetworkProtocol(str, Enum):
    """Netzwerk-Protokolle."""
    
    ZIGBEE = "zigbee"
    MATTER = "matter"
    THREAD = "thread"
    ZWAVE = "zwave"
    WIFI = "wifi"
    ETHERNET = "ethernet"


class NetworkDeviceType(str, Enum):
    """Geräte-Typen."""
    
    COORDINATOR = "coordinator"
    ROUTER = "router"
    END_DEVICE = "end_device"
    BORDER_ROUTER = "border_router"
    COMMISSIONER = "commissioner"


# =============================================================================
# NETWORK DEVICES
# =============================================================================

@dataclass
class NetworkDevice:
    """Gerät im Netzwerk."""
    
    device_id: str
    protocol: NetworkProtocol
    device_type: NetworkDeviceType
    manufacturer: str = ""
    model: str = ""
    firmware_version: str = ""
    
    # Network metrics
    rssi: Optional[float] = None  # Signal strength (dBm)
    lqi: Optional[int] = None  # Link Quality Indicator (0-255)
    battery_level: Optional[float] = None  # 0-1
    
    # Topology
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    neighbors: List[str] = field(default_factory=list)
    
    # Status
    online: bool = True
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "protocol": self.protocol.value,
            "device_type": self.device_type.value,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "rssi": self.rssi,
            "lqi": self.lqi,
            "battery_level": round(self.battery_level * 100, 0) if self.battery_level else None,
            "parent_id": self.parent_id,
            "children": self.children,
            "neighbors": self.neighbors,
            "online": self.online,
            "last_seen": self.last_seen,
        }
    
    def get_signal_quality(self) -> str:
        """Signalqualität als String."""
        if self.rssi is None:
            return "unknown"
        elif self.rssi >= -50:
            return "excellent"
        elif self.rssi >= -65:
            return "good"
        elif self.rssi >= -80:
            return "fair"
        else:
            return "poor"


# =============================================================================
# NETWORK TOPOLOGY
# =============================================================================

@dataclass
class NetworkTopology:
    """Netzwerk-Topologie."""
    
    protocol: NetworkProtocol
    coordinator_id: Optional[str] = None
    devices: Dict[str, NetworkDevice] = field(default_factory=dict)
    edges: List[Dict[str, str]] = field(default_factory=list)  # {source, target}
    
    def to_dict(self) -> Dict[str, Any]:
        online_count = sum(1 for d in self.devices.values() if d.online)
        
        return {
            "protocol": self.protocol.value,
            "coordinator_id": self.coordinator_id,
            "total_devices": len(self.devices),
            "online_devices": online_count,
            "offline_devices": len(self.devices) - online_count,
            "device_types": {
                "coordinators": sum(1 for d in self.devices.values() if d.device_type == NetworkDeviceType.COORDINATOR),
                "routers": sum(1 for d in self.devices.values() if d.device_type == NetworkDeviceType.ROUTER),
                "end_devices": sum(1 for d in self.devices.values() if d.device_type == NetworkDeviceType.END_DEVICE),
                "border_routers": sum(1 for d in self.devices.values() if d.device_type == NetworkDeviceType.BORDER_ROUTER),
            },
            "edges": self.edges,
            "devices": {dev_id: dev.to_dict() for dev_id, dev in self.devices.items()},
        }
    
    def get_network_health_score(self) -> float:
        """Network Health Score (0-1)."""
        if not self.devices:
            return 0.0
        
        online_ratio = sum(1 for d in self.devices.values() if d.online) / len(self.devices)
        
        # Average signal quality
        signal_scores = []
        for device in self.devices.values():
            if device.rssi is not None:
                # Normalize RSSI to 0-1 (-100dBm = 0, -40dBm = 1)
                score = max(0.0, min(1.0, (device.rssi + 100) / 60.0))
                signal_scores.append(score)
        
        avg_signal = sum(signal_scores) / len(signal_scores) if signal_scores else 0.5
        
        # Topology health (routers vs end devices)
        routers = sum(1 for d in self.devices.values() if d.device_type == NetworkDeviceType.ROUTER)
        end_devices = sum(1 for d in self.devices.values() if d.device_type == NetworkDeviceType.END_DEVICE)
        
        if end_devices > 0:
            router_ratio = min(1.0, routers / (end_devices * 0.3))  # Ideal: 1 router per 3 end devices
        else:
            router_ratio = 1.0
        
        # Combined score
        score = (
            online_ratio * 0.40 +
            avg_signal * 0.35 +
            router_ratio * 0.25
        )
        
        return max(0.0, min(1.0, score))


# =============================================================================
# NETWORK MODULES MANAGER
# =============================================================================

class NetworkModulesManager:
    """Manager für Network Modules."""
    
    def __init__(self):
        self._topologies: Dict[NetworkProtocol, NetworkTopology] = {}
        self._health_monitor = None  # Will be set later
        self._lock = threading.Lock()
        _LOGGER.info("NetworkModulesManager initialized")
    
    def register_device(self, device: NetworkDevice) -> None:
        """Gerät registrieren."""
        with self._lock:
            if device.protocol not in self._topologies:
                self._topologies[device.protocol] = NetworkTopology(protocol=device.protocol)
            
            topology = self._topologies[device.protocol]
            topology.devices[device.device_id] = device
            
            # Update edges
            if device.parent_id:
                edge = {"source": device.parent_id, "target": device.device_id}
                if edge not in topology.edges:
                    topology.edges.append(edge)
            
            # Update coordinator
            if device.device_type == NetworkDeviceType.COORDINATOR:
                topology.coordinator_id = device.device_id
    
    def update_device_status(
        self,
        device_id: str,
        protocol: NetworkProtocol,
        online: bool,
        rssi: Optional[float] = None,
        lqi: Optional[int] = None,
        battery_level: Optional[float] = None,
    ) -> None:
        """Geräte-Status updaten."""
        with self._lock:
            topology = self._topologies.get(protocol)
            if not topology or device_id not in topology.devices:
                return
            
            device = topology.devices[device_id]
            device.online = online
            device.last_seen = datetime.now(timezone.utc).isoformat()
            
            if rssi is not None:
                device.rssi = rssi
            if lqi is not None:
                device.lqi = lqi
            if battery_level is not None:
                device.battery_level = battery_level
    
    def get_topology(self, protocol: NetworkProtocol) -> Optional[NetworkTopology]:
        """Topologie holen."""
        with self._lock:
            return self._topologies.get(protocol)
    
    def get_all_topologies(self) -> Dict[str, Dict[str, Any]]:
        """Alle Topologien."""
        with self._lock:
            return {
                proto.value: topo.to_dict()
                for proto, topo in self._topologies.items()
            }
    
    def get_network_map(self) -> Dict[str, Any]:
        """Kombinierte Netzwerk-Karte."""
        with self._lock:
            total_devices = sum(len(t.devices) for t in self._topologies.values())
            total_online = sum(
                sum(1 for d in t.devices.values() if d.online)
                for t in self._topologies.values()
            )
            avg_health = sum(
                t.get_network_health_score()
                for t in self._topologies.values()
            ) / max(len(self._topologies), 1)
            
            return {
                "total_protocols": len(self._topologies),
                "total_devices": total_devices,
                "total_online": total_online,
                "total_offline": total_devices - total_online,
                "overall_health": round(avg_health * 100, 1),
                "protocols": {
                    proto.value: {
                        "devices": len(topo.devices),
                        "online": sum(1 for d in topo.devices.values() if d.online),
                        "health_score": round(topo.get_network_health_score() * 100, 1),
                    }
                    for proto, topo in self._topologies.items()
                },
                "topologies": self.get_all_topologies(),
            }
    
    def get_device_health_for_monitor(self) -> Dict[str, Any]:
        """Device Health für Health Monitor."""
        with self._lock:
            device_health = {}
            
            for topology in self._topologies.values():
                for device in topology.devices.values():
                    device_health[device.device_id] = {
                        "device_id": device.device_id,
                        "device_type": f"network_{device.protocol.value}",
                        "online": device.online,
                        "rssi": device.rssi,
                        "lqi": device.lqi,
                        "battery_level": device.battery_level,
                        "last_seen": device.last_seen,
                    }
            
            return device_health
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_protocols": len(self._topologies),
                "total_devices": sum(len(t.devices) for t in self._topologies.values()),
                "protocols": list(self._topologies.keys()),
            }


# =============================================================================
# Singleton
# =============================================================================

_manager_instance: Optional[NetworkModulesManager] = None


def get_network_modules_manager() -> NetworkModulesManager:
    """Singleton-Zugriff."""
    global _manager_instance
    
    if _manager_instance is None:
        _manager_instance = NetworkModulesManager()
    
    return _manager_instance
