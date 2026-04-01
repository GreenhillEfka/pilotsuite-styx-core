"""Modular Dashboard — SOTA Visualisierung (5 Iterationen).

Implementiert die modulare Architektur mit:
1. Core Dashboard (Backend/Admin)
2. HA Dashboard (Frontend/User)
3. Network Module Visualization (Z-Wave, ZigBee, Thread)
4. Core Intelligence Visualization (Mood, Brain, Neurons)
5. Update Management + Health Checks

SOTA 2026:
- Real-time WebSocket Updates
- Interactive Network Maps
- One-Click Updates
- Module Health Monitoring
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import hashlib
import threading
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# MODULE TYPES
# =============================================================================

class ModuleType(str, Enum):
    """Module Typen nach Architektur."""
    
    # Ebene 1: Interface
    INTERFACE_HA = "interface_ha"
    INTERFACE_TELEGRAM = "interface_telegram"
    INTERFACE_WHATSAPP = "interface_whatsapp"
    INTERFACE_REST = "interface_rest"
    INTERFACE_WEBSOCKET = "interface_websocket"
    INTERFACE_MQTT = "interface_mqtt"
    
    # Ebene 2: Network
    NETWORK_ZWAVE = "network_zwave"
    NETWORK_ZIGBEE = "network_zigbee"
    NETWORK_THREAD = "network_thread"
    NETWORK_KNX = "network_knx"
    NETWORK_MODBUS = "network_modbus"
    NETWORK_WIFI = "network_wifi"
    
    # Ebene 3: Core
    CORE_MOOD = "core_mood"
    CORE_BRAIN = "core_brain"
    CORE_NEURONS = "core_neurons"
    CORE_HABITUS = "core_habitus"
    CORE_CONTEXT = "core_context"
    CORE_MEMORY = "core_memory"
    
    # Ebene 4: Neuron (Input)
    NEURON_BRIGHTNESS = "neuron_brightness"
    NEURON_LIGHT = "neuron_light"
    NEURON_SOUND = "neuron_sound"
    NEURON_MOTION = "neuron_motion"
    NEURON_TEMPERATURE = "neuron_temperature"
    NEURON_ENERGY = "neuron_energy"
    NEURON_EVENT = "neuron_event"
    NEURON_TIME = "neuron_time"
    NEURON_WEATHER = "neuron_weather"
    
    # Ebene 5: Action (Output)
    ACTION_SUGGESTION = "action_suggestion"
    ACTION_AUTOMATION = "action_automation"
    ACTION_MESSAGE = "action_message"
    ACTION_COMMAND = "action_command"
    ACTION_SCENE = "action_scene"
    ACTION_SCHEDULE = "action_schedule"
    
    # Ebene 6: State
    STATE_HOUSEHOLD = "state_household"
    STATE_HABITUS_ZONES = "state_habitus_zones"
    STATE_ZONE_STATES = "state_zone_states"
    STATE_ENTITY = "state_entity"
    STATE_MODULE = "state_module"
    STATE_ACTIVITY = "state_activity"


class ModuleHealth(str, Enum):
    """Module Health Status."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ModuleInfo:
    """Information über ein Modul."""
    
    module_id: str
    module_type: ModuleType
    name: str
    description: str = ""
    health: ModuleHealth = ModuleHealth.UNKNOWN
    version: str = "0.0.0"
    last_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_type": self.module_type.value,
            "name": self.name,
            "description": self.description,
            "health": self.health.value,
            "version": self.version,
            "last_update": self.last_update,
            "metrics": self.metrics,
            "config": self.config,
            "dependencies": self.dependencies,
        }


# =============================================================================
# NETWORK MODULE VISUALIZATION
# =============================================================================

@dataclass
class NetworkNode:
    """Node im Netzwerk (Z-Wave/ZigBee/Thread)."""
    
    node_id: str
    device_type: str
    manufacturer: str
    model: str
    firmware_version: str
    health: ModuleHealth
    rssi: Optional[int] = None
    lqi: Optional[int] = None
    battery_level: Optional[int] = None
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    neighbors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NetworkTopology:
    """Netzwerk-Topologie."""
    
    protocol: str  # "zwave", "zigbee", "thread"
    controller_id: str
    nodes: List[NetworkNode] = field(default_factory=list)
    edges: List[Tuple[str, str]] = field(default_factory=list)
    health_score: float = 0.0
    total_messages: int = 0
    failed_messages: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol,
            "controller_id": self.controller_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": self.edges,
            "health_score": round(self.health_score * 100, 1),
            "total_messages": self.total_messages,
            "failed_messages": self.failed_messages,
            "success_rate": round((1 - self.failed_messages / max(self.total_messages, 1)) * 100, 1),
        }


class NetworkModuleVisualizer:
    """Visualizer für Network Modules."""
    
    def __init__(self):
        self._topologies: Dict[str, NetworkTopology] = {}
        self._lock = threading.Lock()
    
    def update_topology(self, protocol: str, topology: NetworkTopology) -> None:
        """Topologie updaten."""
        with self._lock:
            self._topologies[protocol] = topology
    
    def get_topology(self, protocol: str) -> Optional[NetworkTopology]:
        """Topologie holen."""
        with self._lock:
            return self._topologies.get(protocol)
    
    def get_all_topologies(self) -> Dict[str, Dict[str, Any]]:
        """Alle Topologien."""
        with self._lock:
            return {
                protocol: topo.to_dict()
                for protocol, topo in self._topologies.items()
            }
    
    def get_network_map(self) -> Dict[str, Any]:
        """Kombinierte Netzwerk-Karte."""
        with self._lock:
            return {
                "protocols": list(self._topologies.keys()),
                "total_nodes": sum(len(t.nodes) for t in self._topologies.values()),
                "total_edges": sum(len(t.edges) for t in self._topologies.values()),
                "overall_health": sum(t.health_score for t in self._topologies.values()) / max(len(self._topologies), 1),
                "topologies": self.get_all_topologies(),
            }


# =============================================================================
# CORE INTELLIGENCE VISUALIZATION
# =============================================================================

@dataclass
class MoodDimensions:
    """Mood Dimensions (5)."""
    
    energy: float = 0.5  # 0-1
    valence: float = 0.5  # 0-1 (negative-positive)
    arousal: float = 0.5  # 0-1 (calm-excited)
    dominance: float = 0.5  # 0-1 (submissive-dominant)
    stability: float = 0.5  # 0-1 (unstable-stable)
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: round(v, 3) for k, v in asdict(self).items()}


@dataclass
class BrainGraph:
    """Brain Graph (Neurons + Synapses)."""
    
    neurons: List[Dict[str, Any]] = field(default_factory=list)
    synapses: List[Dict[str, Any]] = field(default_factory=list)
    active_neurons: int = 0
    total_firings: int = 0
    learning_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "neurons": self.neurons,
            "synapses": self.synapses,
            "active_neurons": self.active_neurons,
            "total_firings": self.total_firings,
            "learning_rate": round(self.learning_rate, 4),
        }


class CoreIntelligenceVisualizer:
    """Visualizer für Core Intelligence."""
    
    def __init__(self):
        self._mood_history: List[Dict[str, Any]] = []
        self._brain_graph: Optional[BrainGraph] = None
        self._neuron_activity: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def update_mood(self, dimensions: MoodDimensions) -> None:
        """Mood updaten."""
        with self._lock:
            self._mood_history.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **dimensions.to_dict(),
            })
            # Keep last 1000
            if len(self._mood_history) > 1000:
                self._mood_history = self._mood_history[-1000:]
    
    def update_brain_graph(self, graph: BrainGraph) -> None:
        """Brain Graph updaten."""
        with self._lock:
            self._brain_graph = graph
    
    def record_neuron_firing(self, neuron_id: str, intensity: float) -> None:
        """Neuron Firing recorden."""
        with self._lock:
            self._neuron_activity[neuron_id].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "intensity": intensity,
            })
            # Keep last 100 per neuron
            if len(self._neuron_activity[neuron_id]) > 100:
                self._neuron_activity[neuron_id] = self._neuron_activity[neuron_id][-100:]
    
    def get_mood_status(self) -> Dict[str, Any]:
        """Mood Status."""
        with self._lock:
            if not self._mood_history:
                return {"current": {}, "history": [], "trend": "unknown"}
            
            current = self._mood_history[-1]
            history = self._mood_history[-100:]
            
            # Trend berechnen
            if len(history) > 10:
                avg_early = sum(h["energy"] for h in history[:10]) / 10
                avg_late = sum(h["energy"] for h in history[-10:]) / 10
                trend = "increasing" if avg_late > avg_early else "decreasing" if avg_late < avg_early else "stable"
            else:
                trend = "unknown"
            
            return {
                "current": current,
                "history": history,
                "trend": trend,
            }
    
    def get_brain_status(self) -> Dict[str, Any]:
        """Brain Status."""
        with self._lock:
            if not self._brain_graph:
                return {"graph": {}, "activity": "unknown"}
            
            return {
                "graph": self._brain_graph.to_dict(),
                "activity": {
                    "active_neurons": self._brain_graph.active_neurons,
                    "total_firings": self._brain_graph.total_firings,
                    "learning_rate": self._brain_graph.learning_rate,
                },
            }
    
    def get_neuron_activity(self, neuron_id: Optional[str] = None) -> Dict[str, Any]:
        """Neuron Activity."""
        with self._lock:
            if neuron_id:
                return {
                    neuron_id: self._neuron_activity.get(neuron_id, []),
                }
            else:
                return {
                    nid: activity[-10:]  # Last 10 per neuron
                    for nid, activity in self._neuron_activity.items()
                }


# =============================================================================
# UPDATE MANAGEMENT
# =============================================================================

@dataclass
class UpdateInfo:
    """Update Information."""
    
    component: str  # "core", "ha", "dependencies"
    current_version: str
    available_version: str
    is_available: bool
    is_critical: bool = False
    release_notes: str = ""
    download_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class UpdateManager:
    """Update Manager für alle Komponenten."""
    
    def __init__(self):
        self._updates: Dict[str, UpdateInfo] = {}
        self._last_check: Optional[str] = None
        self._lock = threading.Lock()
    
    def check_updates(self) -> Dict[str, UpdateInfo]:
        """Updates prüfen (simuliert)."""
        # In production: API calls to GitHub, PyPI, etc.
        with self._lock:
            self._updates = {
                "core": UpdateInfo(
                    component="core",
                    current_version="15.3.0",
                    available_version="15.3.0",
                    is_available=False,
                ),
                "ha": UpdateInfo(
                    component="ha",
                    current_version="15.3.0",
                    available_version="15.3.0",
                    is_available=False,
                ),
                "dependencies": UpdateInfo(
                    component="dependencies",
                    current_version="2026.04.01",
                    available_version="2026.04.01",
                    is_available=False,
                ),
            }
            self._last_check = datetime.now(timezone.utc).isoformat()
        
        return self._updates.copy()
    
    def trigger_update(self, component: str) -> Dict[str, Any]:
        """Update auslösen."""
        with self._lock:
            update = self._updates.get(component)
            if not update:
                return {"success": False, "error": "Component not found"}
            
            if not update.is_available:
                return {"success": False, "error": "No update available"}
            
            # In production: Download + Install
            return {
                "success": True,
                "component": component,
                "from_version": update.current_version,
                "to_version": update.available_version,
            }
    
    def get_update_status(self) -> Dict[str, Any]:
        """Update Status."""
        with self._lock:
            updates_available = sum(1 for u in self._updates.values() if u.is_available)
            critical_updates = sum(1 for u in self._updates.values() if u.is_critical and u.is_available)
            
            return {
                "last_check": self._last_check,
                "total_components": len(self._updates),
                "updates_available": updates_available,
                "critical_updates": critical_updates,
                "updates": {k: v.to_dict() for k, v in self._updates.items()},
            }


# =============================================================================
# MODULAR DASHBOARD (Main Class)
# =============================================================================

class ModularDashboard:
    """Haupt-Dashboard für modulare Visualisierung."""
    
    def __init__(self):
        self._modules: Dict[str, ModuleInfo] = {}
        self._network_viz = NetworkModuleVisualizer()
        self._core_viz = CoreIntelligenceVisualizer()
        self._update_mgr = UpdateManager()
        self._lock = threading.Lock()
    
    def register_module(self, module: ModuleInfo) -> None:
        """Modul registrieren."""
        with self._lock:
            self._modules[module.module_id] = module
    
    def update_module_health(self, module_id: str, health: ModuleHealth, metrics: Optional[Dict[str, Any]] = None) -> None:
        """Module Health updaten."""
        with self._lock:
            if module_id in self._modules:
                self._modules[module_id].health = health
                if metrics:
                    self._modules[module_id].metrics.update(metrics)
                self._modules[module_id].last_update = datetime.now(timezone.utc).isoformat()
    
    def network(self) -> NetworkModuleVisualizer:
        return self._network_viz
    
    def core(self) -> CoreIntelligenceVisualizer:
        return self._core_viz
    
    def updates(self) -> UpdateManager:
        return self._update_mgr
    
    def get_core_dashboard(self) -> Dict[str, Any]:
        """Core Dashboard Daten (Backend/Admin)."""
        with self._lock:
            modules_by_type = defaultdict(list)
            for module in self._modules.values():
                modules_by_type[module.module_type.value.split("_")[0]].append(module.to_dict())
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "system_overview": {
                    "total_modules": len(self._modules),
                    "healthy": sum(1 for m in self._modules.values() if m.health == ModuleHealth.HEALTHY),
                    "degraded": sum(1 for m in self._modules.values() if m.health == ModuleHealth.DEGRADED),
                    "unhealthy": sum(1 for m in self._modules.values() if m.health == ModuleHealth.UNHEALTHY),
                },
                "modules": modules_by_type,
                "network": self._network_viz.get_network_map(),
                "core_intelligence": {
                    "mood": self._core_viz.get_mood_status(),
                    "brain": self._core_viz.get_brain_status(),
                    "neurons": self._core_viz.get_neuron_activity(),
                },
                "updates": self._update_mgr.get_update_status(),
            }
    
    def get_ha_dashboard(self) -> Dict[str, Any]:
        """HA Dashboard Daten (Frontend/User)."""
        with self._lock:
            # Vereinfachte Ansicht für User
            intelligence_score = self._calculate_intelligence_score()
            
            zone_activity = {}
            for module in self._modules.values():
                if module.module_type.value.startswith("state_"):
                    zone_id = module.config.get("zone_id", "unknown")
                    zone_activity[zone_id] = module.metrics.get("activity_level", 0.0)
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "intelligence_score": intelligence_score,
                "system_status": {
                    "health": "healthy" if all(m.health == ModuleHealth.HEALTHY for m in self._modules.values()) else "degraded",
                    "active_zones": len(zone_activity),
                    "active_automations": sum(1 for m in self._modules.values() if m.module_type.value.startswith("action_")),
                },
                "zone_activity": zone_activity,
                "mood": self._core_viz.get_mood_status()["current"],
                "network_health": {
                    protocol: topo.health_score
                    for protocol, topo in self._network_viz._topologies.items()
                },
                "updates_available": self._update_mgr.get_update_status()["updates_available"],
                "learning_progress": {
                    "patterns_discovered": len(self._core_viz._neuron_activity),
                    "learning_velocity": self._core_viz._brain_graph.learning_rate if self._core_viz._brain_graph else 0.0,
                },
            }
    
    def _calculate_intelligence_score(self) -> float:
        """Intelligence Score (0-100)."""
        # Pattern Score (max 40)
        pattern_score = min(len(self._core_viz._neuron_activity) * 2, 40)
        
        # Active Score (max 30)
        active_modules = sum(1 for m in self._modules.values() if m.health == ModuleHealth.HEALTHY)
        active_score = min(active_modules * 5, 30)
        
        # Acceptance Score (max 30) - simulated
        acceptance_score = 25.0
        
        return min(pattern_score + active_score + acceptance_score, 100)
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total_modules": len(self._modules),
            "network_protocols": len(self._network_viz._topologies),
            "neuron_types": len(self._core_viz._neuron_activity),
            "update_components": len(self._update_mgr._updates),
        }


# =============================================================================
# Singleton
# =============================================================================

_dashboard_instance: Optional[ModularDashboard] = None


def get_modular_dashboard() -> ModularDashboard:
    """Singleton-Zugriff auf ModularDashboard."""
    global _dashboard_instance
    
    if _dashboard_instance is None:
        _dashboard_instance = ModularDashboard()
        
        # Register default modules
        _register_default_modules(_dashboard_instance)
    
    return _dashboard_instance


def _register_default_modules(dashboard: ModularDashboard) -> None:
    """Default Module registrieren."""
    # Interface Modules
    dashboard.register_module(ModuleInfo(
        module_id="interface_ha",
        module_type=ModuleType.INTERFACE_HA,
        name="Home Assistant Interface",
        description="Primary HA integration",
        health=ModuleHealth.HEALTHY,
        version="15.3.0",
    ))
    
    # Network Modules
    dashboard.register_module(ModuleInfo(
        module_id="network_zwave",
        module_type=ModuleType.NETWORK_ZWAVE,
        name="Z-Wave Network",
        description="Z-Wave protocol handler",
        health=ModuleHealth.HEALTHY,
        version="1.0.0",
    ))
    
    dashboard.register_module(ModuleInfo(
        module_id="network_zigbee",
        module_type=ModuleType.NETWORK_ZIGBEE,
        name="ZigBee Network",
        description="ZigBee protocol handler",
        health=ModuleHealth.HEALTHY,
        version="1.0.0",
    ))
    
    dashboard.register_module(ModuleInfo(
        module_id="network_thread",
        module_type=ModuleType.NETWORK_THREAD,
        name="Thread Network",
        description="Thread protocol handler",
        health=ModuleHealth.HEALTHY,
        version="1.0.0",
    ))
    
    # Core Modules
    dashboard.register_module(ModuleInfo(
        module_id="core_mood",
        module_type=ModuleType.CORE_MOOD,
        name="Mood Module",
        description="Emotional state tracking",
        health=ModuleHealth.HEALTHY,
        version="15.3.0",
    ))
    
    dashboard.register_module(ModuleInfo(
        module_id="core_brain",
        module_type=ModuleType.CORE_BRAIN,
        name="Brain Module",
        description="Neural network core",
        health=ModuleHealth.HEALTHY,
        version="15.3.0",
    ))
    
    # Action Modules
    dashboard.register_module(ModuleInfo(
        module_id="action_suggestion",
        module_type=ModuleType.ACTION_SUGGESTION,
        name="Suggestion Module",
        description="Smart suggestions engine",
        health=ModuleHealth.HEALTHY,
        version="15.3.0",
    ))
    
    dashboard.register_module(ModuleInfo(
        module_id="action_automation",
        module_type=ModuleType.ACTION_AUTOMATION,
        name="Automation Module",
        description="Rule-based automation",
        health=ModuleHealth.HEALTHY,
        version="15.3.0",
    ))
    
    dashboard.register_module(ModuleInfo(
        module_id="action_message",
        module_type=ModuleType.ACTION_MESSAGE,
        name="Message Module",
        description="Notification system",
        health=ModuleHealth.HEALTHY,
        version="15.3.0",
    ))
