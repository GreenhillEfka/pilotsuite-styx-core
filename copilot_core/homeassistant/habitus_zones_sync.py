"""Habitus Zones Sync — Core ↔ HA Synchronization.

Single Source of Truth: ZoneType Enum (this module)

Features:
- ZoneType Enum als AUTHORITY für beide Seiten (Core + HA)
- Sync-Mechanismus für Zone-Konfiguration
- Module-Konfiguration pro Zone (active/learning/off)
- Tag-basierte Entity-Zuordnung
- Persistence in Core + HA Storage

Architecture:
┌─────────────────────┐         ┌─────────────────────┐
│   Core (Hub)        │         │   HA Integration    │
│  HabitusZoneEngine  │◄───────►│  HabitusZoneStoreV2 │
│  - ZoneType Enum    │  Sync   │  - ZoneType Import  │
│  - Module Registry  │  API    │  - Entity Mapping   │
└─────────────────────┘         └─────────────────────┘
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import aiohttp

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# SINGLE SOURCE OF TRUTH — ZoneType Enum
# =============================================================================

class ZoneType(str, Enum):
    """ZoneType Enum — AUTHORITY für Core UND HA Integration.
    
    Diese Enum ist die EINZIGE WAHRHEIT für Zone-Typen.
    Beide Seiten (Core + HA) importieren von hier.
    """
    LIVING = "living"           # Wohnbereich
    BATH = "bath"               # Badbereich
    KITCHEN = "kitchen"         # Kochbereich
    OFFICE = "office"           # Bürobereich
    HALLWAY = "hallway"         # Gangbereich
    BEDROOM = "bedroom"         # Schlafbereich
    ROOM_MIRA = "room_mira"     # Kinderzimmer Mira
    ROOM_PAUL = "room_paul"     # Kinderzimmer Paul
    TERRACE = "terrace"         # Terrassenbereich
    OUTSIDE = "outside"         # Außenbereich


# =============================================================================
# Zone Modes (State Machine)
# =============================================================================

class ZoneMode(str, Enum):
    """Zone Mode — Betriebszustand einer Zone."""
    ACTIVE = "active"           # Voll aktiv
    IDLE = "idle"               # Inaktiv
    SLEEPING = "sleeping"       # Schlafmodus
    PARTY = "party"             # Party-Modus
    AWAY = "away"               # Abwesend
    CUSTOM = "custom"           # Benutzerdefiniert


# =============================================================================
# Module Autonomy States
# =============================================================================

class ModuleAutonomyState(str, Enum):
    """Module Autonomy State — 3-Tier System."""
    ACTIVE = "active"           # Voll autonom (auto-apply)
    LEARNING = "learning"       # Beobachtend (suggest only)
    OFF = "off"                 # Deaktiviert


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ModuleConfig:
    """Konfiguration eines Moduls in einer Zone."""
    
    module_id: str
    state: ModuleAutonomyState = ModuleAutonomyState.LEARNING
    enabled: bool = True
    priority: int = 50
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "state": self.state.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "config": self.config,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModuleConfig:
        return cls(
            module_id=data["module_id"],
            state=ModuleAutonomyState(data.get("state", "learning")),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 50),
            config=data.get("config", {}),
        )


@dataclass
class ZoneConfig:
    """Konfiguration einer Habitus Zone.
    
    Single Source of Truth für Zone-Konfiguration.
    Wird zwischen Core und HA synchronisiert.
    """
    
    zone_id: str
    zone_type: ZoneType
    name: str
    icon: str = "mdi:home"
    mode: ZoneMode = ZoneMode.ACTIVE
    enabled: bool = True
    priority: int = 0
    
    # Module-Konfiguration pro Zone
    modules: Dict[str, ModuleConfig] = field(default_factory=dict)
    
    # Entity-Zuordnung (Tags)
    entity_ids: List[str] = field(default_factory=list)
    tags: Dict[str, Any] = field(default_factory=dict)
    
    # Zone-spezifische Einstellungen
    settings: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_type": self.zone_type.value,
            "name": self.name,
            "icon": self.icon,
            "mode": self.mode.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "modules": {k: v.to_dict() for k, v in self.modules.items()},
            "entity_ids": self.entity_ids,
            "tags": self.tags,
            "settings": self.settings,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ZoneConfig:
        modules = {
            k: ModuleConfig.from_dict(v)
            for k, v in data.get("modules", {}).items()
        }
        return cls(
            zone_id=data["zone_id"],
            zone_type=ZoneType(data["zone_type"]),
            name=data["name"],
            icon=data.get("icon", "mdi:home"),
            mode=ZoneMode(data.get("mode", "active")),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
            modules=modules,
            entity_ids=data.get("entity_ids", []),
            tags=data.get("tags", {}),
            settings=data.get("settings", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )


# =============================================================================
# Zone Templates (Default Configs)
# =============================================================================

_ZONE_TEMPLATES: Dict[ZoneType, Dict[str, Any]] = {
    ZoneType.LIVING: {
        "name": "Wohnbereich",
        "icon": "mdi:sofa",
        "default_modules": {"light", "motion", "music", "volume", "tv", "climate"},
        "settings": {
            "presence_hold_minutes": 5,
            "light_auto_off_minutes": 10,
            "media_volume_max": 60,
        },
    },
    ZoneType.BATH: {
        "name": "Badbereich",
        "icon": "mdi:shower-head",
        "default_modules": {"light", "motion", "climate", "humidity"},
        "settings": {
            "humidity_threshold": 70,
            "ventilation_auto_on": True,
        },
    },
    ZoneType.KITCHEN: {
        "name": "Kochbereich",
        "icon": "mdi:stove",
        "default_modules": {"light", "motion", "music", "climate", "energy"},
        "settings": {
            "energy_tracking": True,
            "motion_light_timeout": 5,
        },
    },
    ZoneType.OFFICE: {
        "name": "Bürobereich",
        "icon": "mdi:desk",
        "default_modules": {"light", "motion", "music", "climate", "timeofday"},
        "settings": {
            "focus_mode_enabled": True,
            "break_reminders": True,
        },
    },
    ZoneType.HALLWAY: {
        "name": "Gangbereich",
        "icon": "mdi:door-open",
        "default_modules": {"light", "motion", "camera"},
        "settings": {
            "light_auto_off_seconds": 30,
            "camera_motion_detection": True,
        },
    },
    ZoneType.BEDROOM: {
        "name": "Schlafbereich",
        "icon": "mdi:bed",
        "default_modules": {"light", "motion", "music", "climate", "timeofday"},
        "settings": {
            "sleep_mode_enabled": True,
            "sunrise_alarm": True,
        },
    },
    ZoneType.ROOM_MIRA: {
        "name": "Kinderzimmer Mira",
        "icon": "mdi:baby-face-outline",
        "default_modules": {"light", "motion", "music", "climate"},
        "settings": {
            "night_light_enabled": True,
            "volume_limit": 50,
        },
    },
    ZoneType.ROOM_PAUL: {
        "name": "Kinderzimmer Paul",
        "icon": "mdi:teddy-bear",
        "default_modules": {"light", "motion", "music", "climate"},
        "settings": {
            "night_light_enabled": True,
            "volume_limit": 50,
        },
    },
    ZoneType.TERRACE: {
        "name": "Terrassenbereich",
        "icon": "mdi:tree",
        "default_modules": {"light", "motion", "music", "camera"},
        "settings": {
            "weather_dependent": True,
            "sunset_light_auto": True,
        },
    },
    ZoneType.OUTSIDE: {
        "name": "Außenbereich",
        "icon": "mdi:home-outline",
        "default_modules": {"light", "motion", "camera"},
        "settings": {
            "security_mode": True,
            "motion_light_flood": True,
        },
    },
}


# =============================================================================
# Sync Client (Core ↔ HA)
# =============================================================================

class HabitusZonesSyncClient:
    """Sync-Client für Zone-Konfiguration zwischen Core und HA.
    
    Usage:
        client = HabitusZonesSyncClient(core_url="http://localhost:8909")
        
        # Zones von Core laden
        zones = await client.load_zones()
        
        # Zone aktualisieren
        zone.modules["light"].state = ModuleAutonomyState.ACTIVE
        await client.save_zone(zone)
        
        # Sync zu HA auslösen
        await client.trigger_ha_sync()
    """
    
    def __init__(
        self,
        core_url: str = "http://localhost:8909",
        api_token: Optional[str] = None,
        timeout: int = 10,
    ):
        self.core_url = core_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def load_zones(self) -> List[ZoneConfig]:
        """Alle Zones von Core laden."""
        session = await self._get_session()
        url = f"{self.core_url}/api/v1/habitus/zones"
        
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()
        
        return [ZoneConfig.from_dict(z) for z in data.get("zones", [])]
    
    async def save_zone(self, zone: ZoneConfig) -> ZoneConfig:
        """Zone speichern (Core + HA Sync)."""
        session = await self._get_session()
        url = f"{self.core_url}/api/v1/habitus/zones/{zone.zone_id}"
        
        zone.updated_at = datetime.now(timezone.utc).isoformat()
        
        async with session.put(url, json=zone.to_dict()) as resp:
            resp.raise_for_status()
            data = await resp.json()
        
        return ZoneConfig.from_dict(data)
    
    async def delete_zone(self, zone_id: str) -> bool:
        """Zone löschen."""
        session = await self._get_session()
        url = f"{self.core_url}/api/v1/habitus/zones/{zone_id}"
        
        async with session.delete(url) as resp:
            resp.raise_for_status()
            return True
    
    async def trigger_ha_sync(self) -> Dict[str, Any]:
        """Sync zu HA Integration auslösen."""
        session = await self._get_session()
        url = f"{self.core_url}/api/v1/habitus/zones/sync"
        
        async with session.post(url) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def get_zone_module_state(
        self,
        zone_id: str,
        module_id: str,
    ) -> ModuleAutonomyState:
        """Aktuellen Module-State für eine Zone abrufen."""
        zones = await self.load_zones()
        zone = next((z for z in zones if z.zone_id == zone_id), None)
        
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        module = zone.modules.get(module_id)
        if not module:
            return ModuleAutonomyState.LEARNING
        
        return module.state
    
    async def set_zone_module_state(
        self,
        zone_id: str,
        module_id: str,
        state: ModuleAutonomyState,
    ) -> ZoneConfig:
        """Module-State für eine Zone setzen."""
        zones = await self.load_zones()
        zone = next((z for z in zones if z.zone_id == zone_id), None)
        
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")
        
        if module_id not in zone.modules:
            zone.modules[module_id] = ModuleConfig(module_id=module_id)
        
        zone.modules[module_id].state = state
        return await self.save_zone(zone)


# =============================================================================
# Tag System (Entity-Zuordnung)
# =============================================================================

class TagCategory(str, Enum):
    """Tag-Kategorien für Entity-Zuordnung."""
    DOMAIN = "domain"           # light, climate, motion, etc.
    ZONE = "zone"               # zone_living, zone_bath, etc.
    MODULE = "module"           # module_light, module_climate, etc.
    STATUS = "status"           # auto_assign, needs_review, manual_override


class TagRegistry:
    """Registry für Entity-Tags.
    
    Tags ermöglichen automatische Entity→Zone Zuordnung.
    
    Usage:
        registry = TagRegistry()
        tags = registry.get_tags_for_entity("light.wohnzimmer")
        # → ["domain:light", "zone:living", "auto_assign"]
    """
    
    # Domain-Tags (11 Kategorien)
    DOMAIN_TAGS = {
        "light": ["light", "switch.light", "scene.light"],
        "climate": ["climate", "sensor.temperature", "sensor.humidity"],
        "motion": ["binary_sensor.motion", "binary_sensor.presence", "binary_sensor.occupancy"],
        "media": ["media_player", "remote"],
        "energy": ["sensor.power", "sensor.energy", "sensor.voltage"],
        "humidity": ["sensor.humidity", "binary_sensor.moisture"],
        "camera": ["camera"],
        "cover": ["cover", "cover.shutter", "cover.blind"],
        "lock": ["lock", "lock.door"],
        "sensor": ["sensor"],
        "switch": ["switch"],
    }
    
    # Zone-Tags (10 Zonen)
    ZONE_TAGS = {
        "living": "zone_living",
        "bath": "zone_bath",
        "kitchen": "zone_kitchen",
        "office": "zone_office",
        "hallway": "zone_hallway",
        "bedroom": "zone_bedroom",
        "room_mira": "zone_room_mira",
        "room_paul": "zone_room_paul",
        "terrace": "zone_terrace",
        "outside": "zone_outside",
    }
    
    # Status-Tags
    STATUS_TAGS = ["auto_assign", "needs_review", "manual_override"]
    
    def get_tags_for_entity(
        self,
        entity_id: str,
        zone_type: Optional[ZoneType] = None,
    ) -> List[str]:
        """Tags für ein Entity generieren."""
        tags = []
        
        # Domain-Tag erkennen
        domain = entity_id.split(".")[0]
        for domain_name, patterns in self.DOMAIN_TAGS.items():
            if any(p in entity_id for p in patterns):
                tags.append(f"domain:{domain_name}")
                break
        
        # Zone-Tag
        if zone_type:
            zone_tag = self.ZONE_TAGS.get(zone_type.value)
            if zone_tag:
                tags.append(zone_tag)
        
        # Status-Tag (default: auto_assign)
        tags.append("auto_assign")
        
        return tags
    
    def get_entities_by_tag(
        self,
        entities: List[Dict[str, Any]],
        tag: str,
    ) -> List[Dict[str, Any]]:
        """Entities nach Tag filtern."""
        tag_type, tag_value = tag.split(":", 1) if ":" in tag else ("", tag)
        
        result = []
        for entity in entities:
            entity_tags = entity.get("tags", [])
            
            if tag_type == "domain":
                if any(f"domain:{t}" in entity_tags for t in self.DOMAIN_TAGS.get(tag_value, [])):
                    result.append(entity)
            elif tag_type == "zone":
                if tag_value in entity_tags:
                    result.append(entity)
            elif tag_type == "status":
                if tag_value in entity_tags:
                    result.append(entity)
        
        return result


# =============================================================================
# Helpers
# =============================================================================

def get_default_zone_config(zone_type: ZoneType) -> ZoneConfig:
    """Default-Konfiguration für einen ZoneType."""
    template = _ZONE_TEMPLATES.get(zone_type, {})
    
    modules = {}
    for module_id in template.get("default_modules", set()):
        modules[module_id] = ModuleConfig(
            module_id=module_id,
            state=ModuleAutonomyState.LEARNING,
            enabled=True,
        )
    
    return ZoneConfig(
        zone_id=zone_type.value,
        zone_type=zone_type,
        name=template.get("name", zone_type.value),
        icon=template.get("icon", "mdi:home"),
        modules=modules,
        settings=template.get("settings", {}),
    )


def get_all_zone_types() -> List[Dict[str, Any]]:
    """Alle ZoneTypes mit Metadata."""
    return [
        {
            "id": zt.value,
            "name": _ZONE_TEMPLATES.get(zt, {}).get("name", zt.value),
            "icon": _ZONE_TEMPLATES.get(zt, {}).get("icon", "mdi:home"),
            "default_modules": list(_ZONE_TEMPLATES.get(zt, {}).get("default_modules", set())),
        }
        for zt in ZoneType
    ]


def get_all_module_states() -> List[Dict[str, Any]]:
    """Alle ModuleAutonomyStates."""
    return [
        {"id": s.value, "name": s.value.capitalize()}
        for s in ModuleAutonomyState
    ]


def get_all_zone_modes() -> List[Dict[str, Any]]:
    """Alle ZoneModes."""
    return [
        {"id": m.value, "name": m.value.capitalize()}
        for m in ZoneMode
    ]
