"""Brain Architecture — Hirnregionen, Neuronen & Synapsen (v7.4.0).

Maps the PilotSuite engine topology to a brain metaphor:
- **Hirnregionen (Brain Regions)** = Hub Engines, each with a colour & role
- **Neuronen (Neurons)** = HA Sensors that emerge from each region
- **Synapsen (Synapses)** = Approved automations / event-wiring between regions

Provides a full connectivity map, health status, and the data model
for the Brain Graph visualization in the frontend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────


class RegionRole(str, Enum):
    """Functional role of a brain region."""

    PERCEPTION = "perception"      # sensing / input
    COGNITION = "cognition"        # analysis / decision
    MOTOR = "motor"                # output / action
    MEMORY = "memory"              # storage / recall
    COORDINATION = "coordination"  # orchestration


class SynapseState(str, Enum):
    """State of a synapse (automation link)."""

    ACTIVE = "active"        # approved & firing
    DORMANT = "dormant"      # exists but inactive
    PENDING = "pending"      # waiting for approval
    BLOCKED = "blocked"      # disabled by user


# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class BrainRegion:
    """A brain region representing one hub engine."""

    region_id: str
    name_de: str
    name_en: str
    color: str                          # hex colour
    icon: str                           # mdi icon
    role: str                           # RegionRole value
    engine_key: str                     # key in SystemIntegrationHub
    neuron_sensor: str                  # HA sensor class name
    description_de: str = ""
    is_active: bool = True
    health: float = 1.0                 # 0.0 – 1.0


@dataclass
class Neuron:
    """A neuron — an HA sensor emerging from a brain region."""

    neuron_id: str
    region_id: str
    sensor_class: str
    entity_id: str                      # e.g. sensor.pilotsuite_anomaly_detection
    state: str = ""
    last_fired: str = ""


@dataclass
class Synapse:
    """A synapse — an approved automation link between two regions."""

    synapse_id: str
    source_region: str
    target_region: str
    event_type: str
    state: str = SynapseState.ACTIVE.value
    strength: float = 1.0               # 0.0 – 1.0 (firing frequency)
    fire_count: int = 0
    last_fired: str = ""
    description_de: str = ""


@dataclass
class BrainStatus:
    """Overall brain health & connectivity."""

    total_regions: int = 0
    active_regions: int = 0
    total_neurons: int = 0
    total_synapses: int = 0
    active_synapses: int = 0
    connectivity_score: float = 0.0     # 0 – 100%
    health_score: float = 0.0           # 0 – 100%
    regions: list[dict[str, Any]] = field(default_factory=list)
    neurons: list[dict[str, Any]] = field(default_factory=list)
    synapses: list[dict[str, Any]] = field(default_factory=list)


# ── Default Region Registry ─────────────────────────────────────────────────

_DEFAULT_REGIONS: list[dict[str, Any]] = [
    {
        "region_id": "dashboard",
        "name_de": "Kommandozentrale",
        "name_en": "Command Center",
        "color": "#4A90D9",
        "icon": "mdi:view-dashboard",
        "role": RegionRole.COORDINATION.value,
        "engine_key": "dashboard",
        "neuron_sensor": "CopilotStatusSensor",
        "description_de": "Zentrale Steuerung und Übersicht aller Systeme",
    },
    {
        "region_id": "plugins",
        "name_de": "Erweiterungskortex",
        "name_en": "Extension Cortex",
        "color": "#7B68EE",
        "icon": "mdi:puzzle",
        "role": RegionRole.COGNITION.value,
        "engine_key": "plugin_manager",
        "neuron_sensor": "PluginManagerSensor",
        "description_de": "Plugin-Verwaltung und Erweiterungs-Ökosystem",
    },
    {
        "region_id": "multi_home",
        "name_de": "Netzwerk-Kortex",
        "name_en": "Network Cortex",
        "color": "#20B2AA",
        "icon": "mdi:home-group",
        "role": RegionRole.COORDINATION.value,
        "engine_key": "multi_home",
        "neuron_sensor": "MultiHomeSensor",
        "description_de": "Multi-Home Synchronisation und Cross-Home Sharing",
    },
    {
        "region_id": "maintenance",
        "name_de": "Wartungs-Hippocampus",
        "name_en": "Maintenance Hippocampus",
        "color": "#FF8C00",
        "icon": "mdi:wrench-clock",
        "role": RegionRole.MEMORY.value,
        "engine_key": "predictive_maintenance",
        "neuron_sensor": "PredictiveMaintenanceSensor",
        "description_de": "Vorausschauende Wartung und Geräte-Lebensdauer",
    },
    {
        "region_id": "anomaly",
        "name_de": "Anomalie-Amygdala",
        "name_en": "Anomaly Amygdala",
        "color": "#DC143C",
        "icon": "mdi:alert-octagon",
        "role": RegionRole.PERCEPTION.value,
        "engine_key": "anomaly_detection",
        "neuron_sensor": "AnomalyDetectionSensor",
        "description_de": "Anomalie-Erkennung und Sicherheits-Monitoring",
    },
    {
        "region_id": "zones",
        "name_de": "Zonen-Thalamus",
        "name_en": "Zone Thalamus",
        "color": "#32CD32",
        "icon": "mdi:floor-plan",
        "role": RegionRole.PERCEPTION.value,
        "engine_key": "habitus_zones",
        "neuron_sensor": "HabitusZoneSensor",
        "description_de": "Raum- und Zonen-Erkennung, Gewohnheits-Mapping",
    },
    {
        "region_id": "light",
        "name_de": "Licht-Visueller-Kortex",
        "name_en": "Light Visual Cortex",
        "color": "#FFD700",
        "icon": "mdi:lightbulb-group",
        "role": RegionRole.MOTOR.value,
        "engine_key": "light_intelligence",
        "neuron_sensor": "LightIntelligenceSensor",
        "description_de": "Intelligente Lichtsteuerung und Szenen",
    },
    {
        "region_id": "modes",
        "name_de": "Modus-Präfrontalkortex",
        "name_en": "Mode Prefrontal Cortex",
        "color": "#9370DB",
        "icon": "mdi:tune-variant",
        "role": RegionRole.COGNITION.value,
        "engine_key": "zone_modes",
        "neuron_sensor": "ZoneModeSensor",
        "description_de": "Zonen-Modi und Verhaltens-Steuerung",
    },
    {
        "region_id": "media",
        "name_de": "Medien-Auditorischer-Kortex",
        "name_en": "Media Auditory Cortex",
        "color": "#FF69B4",
        "icon": "mdi:speaker-multiple",
        "role": RegionRole.MOTOR.value,
        "engine_key": "media_follow",
        "neuron_sensor": "MediaFollowSensor",
        "description_de": "Media-Follow und Audio-Routing zwischen Räumen",
    },
    {
        "region_id": "energy",
        "name_de": "Energie-Hypothalamus",
        "name_en": "Energy Hypothalamus",
        "color": "#00CED1",
        "icon": "mdi:lightning-bolt",
        "role": RegionRole.PERCEPTION.value,
        "engine_key": "energy_advisor",
        "neuron_sensor": "EnergyAdvisorSensor",
        "description_de": "Energieberatung, Eco-Score und Verbrauchsanalyse",
    },
    {
        "region_id": "templates",
        "name_de": "Automations-Broca-Areal",
        "name_en": "Automation Broca Area",
        "color": "#8B4513",
        "icon": "mdi:robot",
        "role": RegionRole.MOTOR.value,
        "engine_key": "automation_templates",
        "neuron_sensor": "AutomationTemplateSensor",
        "description_de": "Automations-Vorlagen und Template-Engine",
    },
    {
        "region_id": "scenes",
        "name_de": "Szenen-Wernicke-Areal",
        "name_en": "Scene Wernicke Area",
        "color": "#FF6347",
        "icon": "mdi:palette",
        "role": RegionRole.COGNITION.value,
        "engine_key": "scene_intelligence",
        "neuron_sensor": "SceneIntelligenceSensor",
        "description_de": "Szenen-Intelligence und Kontext-basierte Vorschläge",
    },
    {
        "region_id": "presence",
        "name_de": "Anwesenheits-Somatosensorik",
        "name_en": "Presence Somatosensory",
        "color": "#3CB371",
        "icon": "mdi:account-group",
        "role": RegionRole.PERCEPTION.value,
        "engine_key": "presence_intelligence",
        "neuron_sensor": "PresenceIntelligenceSensor",
        "description_de": "Anwesenheits-Tracking und Raum-Belegung",
    },
    {
        "region_id": "notifications",
        "name_de": "Benachrichtigungs-Insula",
        "name_en": "Notification Insula",
        "color": "#FF4500",
        "icon": "mdi:bell-ring",
        "role": RegionRole.MOTOR.value,
        "engine_key": "notification_intelligence",
        "neuron_sensor": "NotificationIntelligenceSensor",
        "description_de": "Smart Notifications mit DND und Priority-Routing",
    },
    {
        "region_id": "integration",
        "name_de": "Integrations-Corpus-Callosum",
        "name_en": "Integration Corpus Callosum",
        "color": "#C0C0C0",
        "icon": "mdi:hub",
        "role": RegionRole.COORDINATION.value,
        "engine_key": "integration_hub",
        "neuron_sensor": "SystemIntegrationSensor",
        "description_de": "Cross-Engine Verdrahtung und Event-Dispatch",
    },
]


# ── Default Synapse Wiring ───────────────────────────────────────────────────

_DEFAULT_SYNAPSES: list[dict[str, str]] = [
    # Presence → Scene, Media, Notification
    {"source": "presence", "target": "scenes", "event": "presence_changed",
     "desc": "Anwesenheitsänderung löst Szenen-Vorschläge aus"},
    {"source": "presence", "target": "media", "event": "presence_changed",
     "desc": "Person wechselt Raum → Media folgt"},
    {"source": "presence", "target": "notifications", "event": "presence_changed",
     "desc": "Ankunft/Abfahrt → Benachrichtigung"},
    # Zone Mode → Light, Notification DND
    {"source": "modes", "target": "light", "event": "zone_mode_changed",
     "desc": "Modus-Wechsel steuert Licht-Szene"},
    {"source": "modes", "target": "notifications", "event": "zone_mode_changed",
     "desc": "Nacht/Fokus-Modus → DND aktivieren"},
    # Scene → Zone Mode, Notification
    {"source": "scenes", "target": "modes", "event": "scene_activated",
     "desc": "Szene aktiviert → Zonen-Modus Kaskade"},
    {"source": "scenes", "target": "notifications", "event": "scene_activated",
     "desc": "Szene aktiviert → Benachrichtigung"},
    # Anomaly → Notification, Maintenance
    {"source": "anomaly", "target": "notifications", "event": "anomaly_detected",
     "desc": "Anomalie erkannt → Warnung senden"},
    {"source": "anomaly", "target": "maintenance", "event": "anomaly_detected",
     "desc": "Anomalie → Wartungs-Check auslösen"},
    # Energy → Notification, Scene
    {"source": "energy", "target": "notifications", "event": "energy_threshold",
     "desc": "Hoher Verbrauch → Warnung senden"},
    {"source": "energy", "target": "scenes", "event": "energy_threshold",
     "desc": "Hoher Verbrauch → Eco-Szene vorschlagen"},
    # Person arrived/departed → Scene, Energy
    {"source": "presence", "target": "scenes", "event": "person_arrived",
     "desc": "Person kommt → Willkommens-Szene"},
    {"source": "presence", "target": "scenes", "event": "person_departed",
     "desc": "Alle weg → Away-Szene aktivieren"},
    {"source": "presence", "target": "energy", "event": "person_departed",
     "desc": "Person geht → Eco-Score aktualisieren"},
]


# ── Engine ───────────────────────────────────────────────────────────────────


class BrainArchitectureEngine:
    """Maps PilotSuite to a brain metaphor with regions, neurons & synapses."""

    def __init__(self) -> None:
        self._regions: dict[str, BrainRegion] = {}
        self._neurons: dict[str, Neuron] = {}
        self._synapses: dict[str, Synapse] = {}
        self._synapse_counter = 0

        # Boot with default regions
        self._init_default_regions()
        self._init_default_synapses()

    # ── Initialisation ────────────────────────────────────────────────────

    def _init_default_regions(self) -> None:
        for rd in _DEFAULT_REGIONS:
            region = BrainRegion(**rd)
            self._regions[region.region_id] = region

    def _init_default_synapses(self) -> None:
        for sd in _DEFAULT_SYNAPSES:
            self._synapse_counter += 1
            sid = f"syn_{self._synapse_counter:03d}"
            synapse = Synapse(
                synapse_id=sid,
                source_region=sd["source"],
                target_region=sd["target"],
                event_type=sd["event"],
                description_de=sd.get("desc", ""),
            )
            self._synapses[sid] = synapse

    # ── Region management ─────────────────────────────────────────────────

    def get_region(self, region_id: str) -> BrainRegion | None:
        return self._regions.get(region_id)

    def get_all_regions(self) -> list[BrainRegion]:
        return list(self._regions.values())

    def set_region_health(self, region_id: str, health: float) -> bool:
        region = self._regions.get(region_id)
        if not region:
            return False
        region.health = max(0.0, min(1.0, health))
        return True

    def set_region_active(self, region_id: str, active: bool) -> bool:
        region = self._regions.get(region_id)
        if not region:
            return False
        region.is_active = active
        return True

    # ── Neuron management ─────────────────────────────────────────────────

    def register_neuron(self, region_id: str, sensor_class: str,
                        entity_id: str) -> Neuron | None:
        """Register a neuron (HA sensor) for a brain region."""
        if region_id not in self._regions:
            return None
        nid = f"neuron_{region_id}"
        neuron = Neuron(
            neuron_id=nid,
            region_id=region_id,
            sensor_class=sensor_class,
            entity_id=entity_id,
        )
        self._neurons[nid] = neuron
        return neuron

    def get_neurons(self) -> list[Neuron]:
        return list(self._neurons.values())

    def get_neurons_for_region(self, region_id: str) -> list[Neuron]:
        return [n for n in self._neurons.values() if n.region_id == region_id]

    def update_neuron_state(self, neuron_id: str, state: str) -> bool:
        neuron = self._neurons.get(neuron_id)
        if not neuron:
            return False
        neuron.state = state
        neuron.last_fired = datetime.now(tz=timezone.utc).isoformat()
        return True

    # ── Synapse management ────────────────────────────────────────────────

    def get_all_synapses(self) -> list[Synapse]:
        return list(self._synapses.values())

    def get_synapses_from(self, region_id: str) -> list[Synapse]:
        return [s for s in self._synapses.values() if s.source_region == region_id]

    def get_synapses_to(self, region_id: str) -> list[Synapse]:
        return [s for s in self._synapses.values() if s.target_region == region_id]

    def set_synapse_state(self, synapse_id: str, state: str) -> bool:
        synapse = self._synapses.get(synapse_id)
        if not synapse:
            return False
        synapse.state = state
        return True

    def fire_synapse(self, synapse_id: str) -> bool:
        """Record a synapse firing (event dispatched along this link)."""
        synapse = self._synapses.get(synapse_id)
        if not synapse:
            return False
        if synapse.state != SynapseState.ACTIVE.value:
            return False
        synapse.fire_count += 1
        synapse.last_fired = datetime.now(tz=timezone.utc).isoformat()
        # Strengthen frequently-used synapses (Hebbian learning analogy)
        synapse.strength = min(1.0, synapse.strength + 0.01)
        return True

    def add_synapse(self, source: str, target: str, event_type: str,
                    description_de: str = "") -> Synapse | None:
        """Add a custom synapse between two regions."""
        if source not in self._regions or target not in self._regions:
            return None
        self._synapse_counter += 1
        sid = f"syn_{self._synapse_counter:03d}"
        synapse = Synapse(
            synapse_id=sid,
            source_region=source,
            target_region=target,
            event_type=event_type,
            description_de=description_de,
        )
        self._synapses[sid] = synapse
        return synapse

    def remove_synapse(self, synapse_id: str) -> bool:
        if synapse_id in self._synapses:
            del self._synapses[synapse_id]
            return True
        return False

    # ── Sync with SystemIntegrationHub ────────────────────────────────────

    def sync_with_hub(self, integration_hub: object) -> dict[str, Any]:
        """Sync region health based on which engines are registered in the hub.

        Returns a dict with sync results.
        """
        if not hasattr(integration_hub, "_engines"):
            return {"synced": False, "reason": "no _engines attribute"}

        engines = integration_hub._engines  # type: ignore[attr-defined]
        synced_count = 0

        for region in self._regions.values():
            engine = engines.get(region.engine_key)
            if engine is not None:
                region.is_active = True
                region.health = 1.0
                synced_count += 1
            else:
                region.is_active = False
                region.health = 0.0

        # Sync synapses with hub's wiring diagram
        if hasattr(integration_hub, "get_wiring_diagram"):
            wiring = integration_hub.get_wiring_diagram()
            for synapse in self._synapses.values():
                subs = wiring.get(synapse.event_type, [])
                target_region = self._regions.get(synapse.target_region)
                if target_region and target_region.engine_key in subs:
                    synapse.state = SynapseState.ACTIVE.value
                else:
                    synapse.state = SynapseState.DORMANT.value

        return {"synced": True, "engines_found": synced_count}

    # ── Connectivity graph for visualization ──────────────────────────────

    def get_graph_data(self) -> dict[str, Any]:
        """Return nodes + edges for the Brain Graph visualization."""
        nodes = []
        for r in self._regions.values():
            neuron_count = len(self.get_neurons_for_region(r.region_id))
            outgoing = len(self.get_synapses_from(r.region_id))
            incoming = len(self.get_synapses_to(r.region_id))
            nodes.append({
                "id": r.region_id,
                "label": r.name_de,
                "label_en": r.name_en,
                "color": r.color,
                "icon": r.icon,
                "role": r.role,
                "active": r.is_active,
                "health": r.health,
                "neurons": neuron_count,
                "outgoing_synapses": outgoing,
                "incoming_synapses": incoming,
            })

        edges = []
        for s in self._synapses.values():
            src = self._regions.get(s.source_region)
            tgt = self._regions.get(s.target_region)
            edges.append({
                "id": s.synapse_id,
                "source": s.source_region,
                "target": s.target_region,
                "event_type": s.event_type,
                "state": s.state,
                "strength": s.strength,
                "fire_count": s.fire_count,
                "color": src.color if src else "#888",
                "target_color": tgt.color if tgt else "#888",
                "description_de": s.description_de,
            })

        return {"nodes": nodes, "edges": edges}

    # ── Status ────────────────────────────────────────────────────────────

    def get_status(self) -> BrainStatus:
        regions = self.get_all_regions()
        active = [r for r in regions if r.is_active]
        synapses = self.get_all_synapses()
        active_synapses = [s for s in synapses if s.state == SynapseState.ACTIVE.value]
        neurons = self.get_neurons()

        # Connectivity: % of possible region pairs that have at least one synapse
        n = len(regions)
        max_pairs = n * (n - 1) if n > 1 else 1
        connected_pairs = set()
        for s in synapses:
            connected_pairs.add((s.source_region, s.target_region))
        connectivity = (len(connected_pairs) / max_pairs * 100) if max_pairs > 0 else 0

        # Health: average region health
        avg_health = (sum(r.health for r in regions) / len(regions) * 100) if regions else 0

        return BrainStatus(
            total_regions=len(regions),
            active_regions=len(active),
            total_neurons=len(neurons),
            total_synapses=len(synapses),
            active_synapses=len(active_synapses),
            connectivity_score=round(connectivity, 1),
            health_score=round(avg_health, 1),
            regions=[
                {
                    "region_id": r.region_id,
                    "name_de": r.name_de,
                    "color": r.color,
                    "icon": r.icon,
                    "role": r.role,
                    "active": r.is_active,
                    "health": r.health,
                }
                for r in regions
            ],
            neurons=[
                {
                    "neuron_id": n.neuron_id,
                    "region_id": n.region_id,
                    "sensor_class": n.sensor_class,
                    "entity_id": n.entity_id,
                    "state": n.state,
                }
                for n in neurons
            ],
            synapses=[
                {
                    "synapse_id": s.synapse_id,
                    "source": s.source_region,
                    "target": s.target_region,
                    "event_type": s.event_type,
                    "state": s.state,
                    "strength": s.strength,
                    "fire_count": s.fire_count,
                    "description_de": s.description_de,
                }
                for s in synapses
            ],
        )

    # ── Dashboard ─────────────────────────────────────────────────────────

    def get_dashboard(self) -> dict[str, Any]:
        """Full brain dashboard for API response."""
        status = self.get_status()
        graph = self.get_graph_data()
        return {
            "ok": True,
            "total_regions": status.total_regions,
            "active_regions": status.active_regions,
            "total_neurons": status.total_neurons,
            "total_synapses": status.total_synapses,
            "active_synapses": status.active_synapses,
            "connectivity_score": status.connectivity_score,
            "health_score": status.health_score,
            "regions": status.regions,
            "neurons": status.neurons,
            "synapses": status.synapses,
            "graph": graph,
        }
