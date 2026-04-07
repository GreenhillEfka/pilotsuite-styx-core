"""
Truth-Backed Dashboard Read Models (P1).

Frei nach: "Slice 6 — Truth-Backed Dashboard Read Models"
Goal: Dashboard不再是Ad-hoc-Datenkonstruktion — es soll von Core-Truth-Read-Models
gespeist werden.

Liefert:
  - ZoneSummaryReadModel:     Leichtgewichtige Zone-Übersicht (aus HabitusZoneEngine)
  - ZoneDetailReadModel:      Detaillierte Zone-Daten (aus HabitusZoneEngine + ZoneAutomation)
  - ModuleReadModel:          Modul-Zustände aus ModuleRegistry
  - SystemOverviewReadModel:  Globale System-Übersicht

Jedes Read Model enthält:
  - freshness:  ISO-Timestamp der letzten Aktualisierung
  - source:     Welcher Service die Daten liefert (z.B. "habitus_zones", "module_registry")

Wiring:
  - ZoneSummary:    hub/habitus_zones.py  (HabitusZoneEngine — Zone Truth)
  - ZoneDetail:      hub/habitus_zones.py  + hub/zone_automation.py
  - ModuleReadModel: module_registry.py    (ModuleRegistry)
  - SystemOverview:  Kombination aller Quellen
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from copilot_core.core.taxonomy import classify_entity

_LOGGER = logging.getLogger(__name__)

# ── Read Model Base ───────────────────────────────────────────────────────────


@dataclass
class ReadModelMeta:
    """Metadaten für jedes Read Model."""

    freshness: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = "unknown"           # Welcher Service liefert die Daten
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "freshness": self.freshness,
            "source": self.source,
            "generated_at": self.generated_at,
            "version": self.version,
        }


class _ReadModelCompatMixin:
    """Small dict-like compatibility layer for read models."""

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def copy(self) -> Dict[str, Any]:
        return self.to_dict().copy()

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]


# ── ZoneSummaryReadModel ─────────────────────────────────────────────────────


@dataclass
class ZoneSummaryReadModel(_ReadModelCompatMixin):
    """
    Leichtgewichtige Zone-Übersicht für das Dashboard.

    Source of Truth: hub/habitus_zones.py (HabitusZoneEngine)
    """

    meta: ReadModelMeta
    zones: List[Dict[str, Any]] = field(default_factory=list)
    total_zones: int = 0
    active_zones: int = 0
    total_entities: int = 0
    zone_types: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.meta.to_dict(),
            "zones": self.zones,
            "total_zones": self.total_zones,
            "active_zones": self.active_zones,
            "total_entities": self.total_entities,
            "zone_types": self.zone_types,
        }

    @classmethod
    def from_habitus_zones(
        cls,
        engine: Any,
        *,
        example_data: Optional[Dict[str, Any]] = None,
    ) -> "ZoneSummaryReadModel":
        """Baue ZoneSummary aus HabitusZoneEngine + optionalem example_data."""
        meta = ReadModelMeta(source="habitus_zones")
        zones: List[Dict[str, Any]] = []
        zone_types: Dict[str, int] = {}

        if engine is not None:
            try:
                overview = engine.get_overview()
                overview_zones = overview.zones
                for z in overview_zones:
                    zone_type = z.get("zone_type", "unknown")
                    zones.append({
                        "zone_id": z.get("zone_id", ""),
                        "name": z.get("name", ""),
                        "zone_type": zone_type,
                        "icon": z.get("icon", ""),
                        "mode": z.get("mode", "idle"),
                        "enabled": z.get("enabled", True),
                        "room_count": z.get("room_count", 0),
                        "entity_count": z.get("entity_count", 0),
                        "priority": z.get("priority", 0),
                    })
                    zone_types[zone_type] = zone_types.get(zone_type, 0) + 1

                total_entities = overview.total_entities
                active_zones = overview.active_zones
                total_zones = overview.total_zones
            except Exception as e:
                _LOGGER.warning("HabitusZoneEngine.get_overview failed: %s", e)
                overview_zones = []
                if hasattr(engine, "get_all_zones"):
                    try:
                        overview_zones = list(engine.get_all_zones() or [])
                    except Exception as inner_exc:
                        _LOGGER.warning("HabitusZoneEngine.get_all_zones failed: %s", inner_exc)

                for z in overview_zones:
                    zone_type = z.get("zone_type", "unknown")
                    entity_ids = z.get("entities", []) or z.get("entity_ids", []) or []
                    entity_count = z.get("entity_count", len(entity_ids))
                    zones.append({
                        "zone_id": z.get("zone_id", ""),
                        "name": z.get("name", ""),
                        "zone_type": zone_type,
                        "icon": z.get("icon", ""),
                        "mode": z.get("mode", "idle"),
                        "enabled": z.get("enabled", True),
                        "room_count": z.get("room_count", 0),
                        "entity_count": entity_count,
                        "priority": z.get("priority", 0),
                        "entity_ids": entity_ids,
                    })
                    zone_types[zone_type] = zone_types.get(zone_type, 0) + 1

                total_zones = len(zones)
                active_zones = sum(1 for z in zones if z.get("enabled", True))
                total_entities = sum(z.get("entity_count", 0) for z in zones)
        else:
            # Fallback: Enrich with example_data
            total_zones = 0
            active_zones = 0
            total_entities = 0
            if example_data:
                zone_entities = example_data.get("zone_entities", {})
                zone_display = example_data.get("zone_display", {})
                for zid, ents in zone_entities.items():
                    display = zone_display.get(zid, {})
                    zone_type = display.get("zone_type", "unknown")
                    zones.append({
                        "zone_id": zid,
                        "name": display.get("name", zid.replace("_", " ").title()),
                        "zone_type": zone_type,
                        "icon": display.get("icon", "mdi:home"),
                        "mode": "idle",
                        "enabled": True,
                        "room_count": 0,
                        "entity_count": sum(len(v) for v in ents.values() if isinstance(v, list)),
                        "priority": 0,
                    })
                    zone_types[zone_type] = zone_types.get(zone_type, 0) + 1
                total_zones = len(zones)
                active_zones = total_zones
                total_entities = sum(z.get("entity_count", 0) for z in zones)

        return cls(
            meta=meta,
            zones=zones,
            total_zones=total_zones,
            active_zones=active_zones,
            total_entities=total_entities,
            zone_types=zone_types,
        )


# ── ZoneDetailReadModel ───────────────────────────────────────────────────────


@dataclass
class ZoneDetailReadModel(_ReadModelCompatMixin):
    """
    Detaillierte Zone-Daten.

    Source of Truth: hub/habitus_zones.py (HabitusZoneEngine)
                    + hub/zone_automation.py (ZoneAutomationController)
    """

    meta: ReadModelMeta
    zone_id: str = ""
    name: str = ""
    zone_type: str = "living"
    icon: str = ""
    color: str = ""
    mode: str = "active"
    enabled: bool = True
    priority: int = 0
    enabled_modules: List[str] = field(default_factory=list)
    entity_count: int = 0
    room_count: int = 0
    entity_ids: List[str] = field(default_factory=list)
    entities_by_role: Dict[str, List[str]] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)   # ZoneState aus Engine
    mood: Dict[str, Any] = field(default_factory=dict)     # Mood-Daten
    modules: Dict[str, Any] = field(default_factory=dict)  # Modul-Daten

    @property
    def zone_name(self) -> str:
        return self.name

    @property
    def module_states(self) -> Dict[str, Any]:
        return self.modules

    @property
    def freshness(self) -> str:
        return self.meta.freshness

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.meta.to_dict(),
            "zone_id": self.zone_id,
            "name": self.name,
            "zone_type": self.zone_type,
            "icon": self.icon,
            "color": self.color,
            "mode": self.mode,
            "enabled": self.enabled,
            "priority": self.priority,
            "enabled_modules": self.enabled_modules,
            "entity_count": self.entity_count,
            "room_count": self.room_count,
            "entity_ids": self.entity_ids,
            "entities_by_role": self.entities_by_role,
            "state": self.state,
            "mood": self.mood,
            "modules": self.modules,
        }

    @classmethod
    def from_habitus_zone(
        cls,
        engine: Any,
        zone_id: str,
        *,
        zone_automation: Any = None,
        example_data: Optional[Dict[str, Any]] = None,
        example_zone: Optional[Dict[str, Any]] = None,
    ) -> Optional["ZoneDetailReadModel"]:
        """Baue ZoneDetail aus HabitusZoneEngine + ZoneAutomationController."""
        meta = ReadModelMeta(source="habitus_zones")

        if engine is not None:
            try:
                zone = engine.get_zone(zone_id)
                if zone is None:
                    return None

                # Zone-State aus Engine
                zone_state = engine.get_zone_state(zone_id)
                state_dict: Dict[str, Any] = {}
                if zone_state:
                    state_dict = {
                        "avg_temperature": zone_state.avg_temperature,
                        "avg_humidity": zone_state.avg_humidity,
                        "occupancy": zone_state.occupancy,
                        "light_on_count": zone_state.light_on_count,
                        "active_devices": zone_state.active_devices,
                    }

                entity_ids = zone.get("entities", [])
                entities_by_role: Dict[str, List[str]] = {}
                for entity_id in entity_ids:
                    try:
                        classification = classify_entity(str(entity_id))
                        role = classification.role.value
                    except Exception:
                        role = "other"
                    entities_by_role.setdefault(role, []).append(str(entity_id))

                enabled_modules = list(zone.get("enabled_modules", []))
                module_data: Dict[str, Any] = {}
                if zone_automation is not None:
                    try:
                        cfg = zone_automation.get_zone_config(zone_id)
                        if cfg is not None:
                            source_modules = getattr(cfg, "modules", {}) or {}
                            candidate_ids = enabled_modules or list(source_modules.keys())
                            for module_id in candidate_ids:
                                mod = source_modules.get(module_id)
                                if mod is not None and hasattr(mod, "to_dict"):
                                    module_data[module_id] = mod.to_dict()
                    except Exception as e:
                        _LOGGER.warning("Zone automation config lookup failed for %s: %s", zone_id, e)

                return cls(
                    meta=meta,
                    zone_id=zone.get("zone_id", zone_id),
                    name=zone.get("name", ""),
                    zone_type=zone.get("zone_type", "living"),
                    icon=zone.get("icon", ""),
                    color="",
                    mode=zone.get("mode", "idle"),
                    enabled=zone.get("enabled", True),
                    priority=zone.get("priority", 0),
                    enabled_modules=enabled_modules,
                    entity_count=zone.get("entity_count", 0),
                    room_count=zone.get("room_count", 0),
                    entity_ids=entity_ids,
                    entities_by_role=entities_by_role,
                    state=state_dict,
                    mood={},
                    modules=module_data,
                )
            except Exception as e:
                _LOGGER.warning("HabitusZoneEngine.get_zone(%s) failed: %s", zone_id, e)

        # Fallback: from example_data
        if example_data and example_zone:
            return cls(
                meta=meta,
                zone_id=example_zone.get("zone_id", zone_id),
                name=example_zone.get("name", zone_id.replace("_", " ").title()),
                zone_type=example_zone.get("zone_type", "living"),
                icon=example_zone.get("icon", ""),
                color=example_zone.get("color", ""),
                mode="idle",
                enabled=True,
                priority=example_zone.get("priority", 0),
                enabled_modules=list(example_zone.get("enabled_modules", [])),
                entity_count=len(example_zone.get("entity_ids", [])),
                room_count=0,
                entity_ids=example_zone.get("entity_ids", []),
                entities_by_role=example_zone.get("entities", {}),
                state={},
                mood={},
                modules={},
            )

        return None


# ── ModuleReadModel ──────────────────────────────────────────────────────────


@dataclass
class ModuleReadModel(_ReadModelCompatMixin):
    """
    Modul-Zustände aus ModuleRegistry.

    Source of Truth: module_registry.py (ModuleRegistry)
    """

    meta: ReadModelMeta
    modules: Dict[str, str] = field(default_factory=dict)  # module_id → state
    by_zone: Dict[str, Dict[str, str]] = field(default_factory=dict)  # zone_id → module_id → state
    zone_states: Dict[str, str] = field(default_factory=dict)  # zone_id → dominant state

    # Bekannte Hub-Module mit Display-Metadaten
    MODULE_META: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "licht": {"name_de": "Licht", "icon": "mdi:lightbulb", "category": "habitat"},
        "bewegung": {"name_de": "Bewegung", "icon": "mdi:motion-sensor", "category": "habitat"},
        "heiz": {"name_de": "Heizung/Klima", "icon": "mdi:thermometer", "category": "habitat"},
        "musik": {"name_de": "Musik", "icon": "mdi:music", "category": "habitat"},
        "medien": {"name_de": "Medien", "icon": "mdi:speaker", "category": "habitat"},
        "kamera": {"name_de": "Kamera", "icon": "mdi:camera", "category": "habitat"},
        "praesenz": {"name_de": "Präsenz", "icon": "mdi:account-group", "category": "habitat"},
        "helligkeit": {"name_de": "Helligkeit", "icon": "mdi:white-balance-sunny", "category": "habitat"},
        "energie": {"name_de": "Energie", "icon": "mdi:flash", "category": "habitat"},
        "mood_engine": {"name_de": "Stimmung", "icon": "mdi:emoticon", "category": "intelligence"},
        "habitus_miner": {"name_de": "Habitus Miner", "icon": "mdi:brain", "category": "intelligence"},
        "brain_graph": {"name_de": "Brain Graph", "icon": "mdi:graph", "category": "intelligence"},
        "tv": {"name_de": "TV", "icon": "mdi:television", "category": "habitat"},
        "volume": {"name_de": "Lautstärke", "icon": "mdi:volume-high", "category": "habitat"},
        "cover": {"name_de": "Rollläden", "icon": "mdi:window-shutter", "category": "habitat"},
        "sicherheit": {"name_de": "Sicherheit", "icon": "mdi:shield", "category": "habitat"},
    })

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def modules_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for module_id in self.modules:
            module_type = str(module_id).split(".", 1)[0].split("_", 1)[0]
            counts[module_type] = counts.get(module_type, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.meta.to_dict(),
            "modules": self.modules,
            "by_zone": self.by_zone,
            "zone_states": self.zone_states,
            "module_meta": self.MODULE_META,
        }

    @classmethod
    def from_module_registry(
        cls,
        registry: Any,
        *,
        all_zone_states: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> "ModuleReadModel":
        """Baue ModuleReadModel aus ModuleRegistry."""
        meta = ReadModelMeta(source="module_registry")
        modules: Dict[str, str] = {}

        if registry is not None:
            try:
                modules = registry.get_all_states()
            except Exception as e:
                _LOGGER.warning("ModuleRegistry.get_all_states failed: %s", e)

        # Zone-states
        by_zone: Dict[str, Dict[str, str]] = {}
        zone_states: Dict[str, str] = {}
        if all_zone_states:
            by_zone = all_zone_states
            # Compute dominant state per zone
            for zid, state_map in all_zone_states.items():
                if state_map:
                    counts: Dict[str, int] = {}
                    for raw_state in state_map.values():
                        state = str(raw_state or "unknown")
                        counts[state] = counts.get(state, 0) + 1

                    dominant_state = max(
                        counts.items(),
                        key=lambda item: (
                            item[1],
                            item[0] == "active",
                            item[0] == "off",
                            item[0] == "learning",
                        ),
                    )[0]
                    zone_states[zid] = dominant_state

        return cls(
            meta=meta,
            modules=modules,
            by_zone=by_zone,
            zone_states=zone_states,
        )


# ── SystemOverviewReadModel ──────────────────────────────────────────────────


@dataclass
class SystemOverviewReadModel(_ReadModelCompatMixin):
    """
    Globale System-Übersicht.

    Kombiniert ZoneSummary + ModuleContext + BrainActivitySnapshot.
    """

    meta: ReadModelMeta
    zones: ZoneSummaryReadModel = field(
        default_factory=lambda: ZoneSummaryReadModel(meta=ReadModelMeta(source="system_overview.zones"))
    )
    modules: ModuleReadModel = field(
        default_factory=lambda: ModuleReadModel(meta=ReadModelMeta(source="system_overview.modules"))
    )
    brain: Dict[str, Any] = field(default_factory=dict)     # Brain Read Model
    energy: Dict[str, Any] = field(default_factory=dict)      # Energie-Daten
    persons_home: int = 0
    sun_phase: str = ""
    uptime_seconds: float = 0.0

    @property
    def total_zones(self) -> int:
        return self.zones.total_zones

    @property
    def total_modules(self) -> int:
        return self.modules.module_count

    @property
    def system_health(self) -> str:
        return "ok"

    @property
    def last_updated(self) -> str:
        return self.meta.generated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.meta.to_dict(),
            "zones": self.zones.to_dict(),
            "modules": self.modules.to_dict(),
            "brain": self.brain,
            "energy": self.energy,
            "persons_home": self.persons_home,
            "sun_phase": self.sun_phase,
            "uptime_seconds": self.uptime_seconds,
        }

    @classmethod
    def build(
        cls,
        *,
        zone_engine: Any = None,
        module_registry: Any = None,
        zone_automation: Any = None,
        all_zone_states: Optional[Dict[str, Dict[str, str]]] = None,
        brain_summary: Any = None,
        energy_data: Optional[Dict[str, Any]] = None,
        persons_home: int = 0,
        sun_phase: str = "",
        example_data: Optional[Dict[str, Any]] = None,
    ) -> "SystemOverviewReadModel":
        """Baue die komplette SystemOverview aus allen verfügbaren Quellen."""
        meta = ReadModelMeta(source="system_overview")

        zone_summary = ZoneSummaryReadModel.from_habitus_zones(
            zone_engine, example_data=example_data
        )

        if all_zone_states is None:
            all_zone_states = _derive_zone_module_states(zone_automation)

        module_read_model = ModuleReadModel.from_module_registry(
            module_registry,
            all_zone_states=all_zone_states,
        )

        normalized_brain = _normalize_brain_summary(brain_summary, meta)

        return cls(
            meta=meta,
            zones=zone_summary,
            modules=module_read_model,
            brain=normalized_brain,
            energy=energy_data or {},
            persons_home=persons_home,
            sun_phase=sun_phase,
        )


# ── Dashboard Builder ────────────────────────────────────────────────────────


def _normalize_brain_summary(brain_summary: Any, meta: ReadModelMeta) -> Dict[str, Any]:
    """Normalize brain summary input into a stable dict with freshness metadata."""
    if brain_summary is None:
        return {}

    payload: Dict[str, Any]
    if isinstance(brain_summary, dict):
        payload = dict(brain_summary)
    elif hasattr(brain_summary, "to_dict"):
        try:
            payload = dict(brain_summary.to_dict())
        except Exception:
            payload = {}
    else:
        return {}

    payload.setdefault("generated_at", meta.generated_at)
    payload.setdefault("source", "brain_read_model")
    return payload


def _derive_zone_module_states(zone_automation: Any) -> Dict[str, Dict[str, str]]:
    """Derive per-zone module states from ZoneAutomationController configs."""
    if zone_automation is None:
        return {}

    configs = getattr(zone_automation, "_configs", None)
    if not isinstance(configs, dict):
        return {}

    zone_states: Dict[str, Dict[str, str]] = {}
    for zone_id, cfg in configs.items():
        modules = getattr(cfg, "modules", {}) or {}
        mode = str(getattr(cfg, "automation_mode", "learning") or "learning")
        enabled_filter = set(getattr(cfg, "enabled_modules", set()) or set())
        state_map: Dict[str, str] = {}

        for module_id, module_cfg in modules.items():
            if enabled_filter and module_id not in enabled_filter:
                continue

            enabled = bool(getattr(module_cfg, "enabled", True))
            if not enabled or mode == "off":
                state_map[module_id] = "off"
            elif mode == "autonomy":
                state_map[module_id] = "active"
            else:
                state_map[module_id] = "learning"

        if state_map:
            zone_states[str(zone_id)] = state_map

    return zone_states


def build_zone_summary_read_model(
    zone_engine: Any,
    *,
    example_data: Optional[Dict[str, Any]] = None,
) -> ZoneSummaryReadModel:
    """API-freundlicher Wrapper für ZoneSummaryReadModel."""
    return ZoneSummaryReadModel.from_habitus_zones(
        zone_engine, example_data=example_data
    )


def build_zone_detail_read_model(
    zone_engine: Any,
    zone_id: str,
    *,
    zone_automation: Any = None,
    example_data: Optional[Dict[str, Any]] = None,
) -> Optional[ZoneDetailReadModel]:
    """API-freundlicher Wrapper für ZoneDetailReadModel."""
    # Versuche zone_id aus example_data zu finden
    example_zone = None
    if example_data:
        zone_entities = example_data.get("zone_entities", {})
        zone_display = example_data.get("zone_display", {})
        if zone_id in zone_entities:
            example_zone = {
                "zone_id": zone_id,
                "name": zone_display.get(zone_id, {}).get("name", zone_id),
                "icon": zone_display.get(zone_id, {}).get("icon", ""),
                "zone_type": zone_display.get(zone_id, {}).get("zone_type", "living"),
                "enabled_modules": zone_display.get(zone_id, {}).get("enabled_modules", []),
                "entities": zone_entities.get(zone_id, {}),
                "entity_ids": [
                    eid
                    for role_list in zone_entities.get(zone_id, {}).values()
                    if isinstance(role_list, list)
                    for eid in role_list
                ],
                "priority": 0,
            }

    model = ZoneDetailReadModel.from_habitus_zone(
        zone_engine, zone_id,
        zone_automation=zone_automation,
        example_data=example_data,
        example_zone=example_zone,
    )
    return model


def build_module_read_model(
    module_registry: Any,
    *,
    all_zone_states: Optional[Dict[str, Dict[str, str]]] = None,
) -> ModuleReadModel:
    """API-freundlicher Wrapper für ModuleReadModel."""
    return ModuleReadModel.from_module_registry(
        module_registry, all_zone_states=all_zone_states
    )


def build_system_overview_read_model(
    *,
    zone_engine: Any = None,
    module_registry: Any = None,
    zone_automation: Any = None,
    all_zone_states: Optional[Dict[str, Dict[str, str]]] = None,
    brain_summary: Any = None,
    energy_data: Optional[Dict[str, Any]] = None,
    persons_home: int = 0,
    sun_phase: str = "",
    example_data: Optional[Dict[str, Any]] = None,
) -> SystemOverviewReadModel:
    """API-freundlicher Wrapper für SystemOverviewReadModel."""
    return SystemOverviewReadModel.build(
        zone_engine=zone_engine,
        module_registry=module_registry,
        zone_automation=zone_automation,
        all_zone_states=all_zone_states,
        brain_summary=brain_summary,
        energy_data=energy_data,
        persons_home=persons_home,
        sun_phase=sun_phase,
        example_data=example_data,
    )


__all__ = [
    "ReadModelMeta",
    "ZoneSummaryReadModel",
    "ZoneDetailReadModel",
    "ModuleReadModel",
    "SystemOverviewReadModel",
    "build_zone_summary_read_model",
    "build_zone_detail_read_model",
    "build_module_read_model",
    "build_system_overview_read_model",
]
