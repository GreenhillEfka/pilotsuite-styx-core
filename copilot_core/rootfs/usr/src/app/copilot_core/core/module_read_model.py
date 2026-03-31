"""
Module Read Model — First-class Core module state, config, and freshness.

Slice 3: Module First-Class Model
Goal: Expose modules as first-class in architecture and runtime, with truth-backed
read models for dashboard, policy, and Habitus zones.

Provides:
  - ModuleSnapshotV1: typed module state with config, freshness, applicability
  - ModuleReadModel: aggregated module view across all zones
  - get_module_read_model(): public API for dashboard/API consumption
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

_LOGGER = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ModuleFieldStateV1:
    """State of a single module field."""
    key: str
    value: Any
    field_type: str
    last_update: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "field_type": self.field_type,
            "last_update": self.last_update,
        }


@dataclass
class ModuleSnapshotV1:
    """
    Canonical module snapshot — the Core truth record for module state.

    This is separate from ZoneModuleConfig (which holds configuration).
    ModuleSnapshotV1 is the runtime truth: current state, freshness, and
    zone applicability.
    """
    module_id: str
    module_name_de: str
    module_icon: str
    module_color: str
    
    # Configuration state
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    field_states: List[ModuleFieldStateV1] = field(default_factory=list)
    
    # Runtime state
    state_summary: Dict[str, Any] = field(default_factory=dict)
    health: str = "ok"  # ok | degraded | error
    health_message: str = ""
    
    # Zone applicability
    applicable_zones: List[str] = field(default_factory=list)
    relevant_roles: List[str] = field(default_factory=list)
    relevant_tags: List[str] = field(default_factory=list)
    relevant_domains: List[str] = field(default_factory=list)
    
    # Freshness tracking
    last_update: str = field(default_factory=_now_iso)
    last_state_change: str = field(default_factory=_now_iso)
    revision: int = 0
    
    # Provenance
    source: str = "core"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_name_de": self.module_name_de,
            "module_icon": self.module_icon,
            "module_color": self.module_color,
            "enabled": self.enabled,
            "config": dict(self.config),
            "field_states": [f.to_dict() for f in self.field_states],
            "state_summary": dict(self.state_summary),
            "health": self.health,
            "health_message": self.health_message,
            "applicable_zones": list(self.applicable_zones),
            "relevant_roles": list(self.relevant_roles),
            "relevant_tags": list(self.relevant_tags),
            "relevant_domains": list(self.relevant_domains),
            "last_update": self.last_update,
            "last_state_change": self.last_state_change,
            "revision": self.revision,
            "source": self.source,
        }

    def touch(self) -> None:
        """Update revision and timestamps."""
        self.revision += 1
        self.last_update = _now_iso()

    def update_state(self, state_update: Dict[str, Any]) -> None:
        """Update runtime state and touch revision."""
        self.state_summary.update(state_update)
        self.last_state_change = _now_iso()
        self.touch()


@dataclass
class ModuleReadModel:
    """
    Aggregated read model for all modules across all zones.

    This is the canonical output for dashboard/API consumption.
    """
    generated_at: str = field(default_factory=_now_iso)
    modules: Dict[str, ModuleSnapshotV1] = field(default_factory=dict)
    zone_module_map: Dict[str, List[str]] = field(default_factory=dict)  # zone_id -> [module_ids]
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "modules": {mid: m.to_dict() for mid, m in self.modules.items()},
            "zone_module_map": {zid: list(mids) for zid, mids in self.zone_module_map.items()},
            "summary": dict(self.summary),
        }


# ── Internal State ────────────────────────────────────────────────────────────

_module_state: Dict[str, Any] = {
    "modules": {},  # module_id -> ModuleSnapshotV1
    "zone_module_map": {},  # zone_id -> set of module_ids
    "last_revision": 0,
}


# ── Public API ────────────────────────────────────────────────────────────────


def get_module_read_model(
    module_registry: Any = None,
    zone_automation_controller: Any = None,
    zone_truth_store: Any = None,
) -> Dict[str, Any]:
    """
    Build complete Module Read Model.

    Args:
        module_registry: ZoneModuleRegistry instance (optional)
        zone_automation_controller: ZoneAutomationController instance (optional)
        zone_truth_store: ZoneTruthStore instance (optional)

    Returns:
        Dict with modules, zone_module_map, and summary
    """
    model = build_module_read_model(
        module_registry=module_registry,
        zone_automation_controller=zone_automation_controller,
        zone_truth_store=zone_truth_store,
    )
    return model.to_dict()


def build_module_read_model(
    module_registry: Any = None,
    zone_automation_controller: Any = None,
    zone_truth_store: Any = None,
) -> ModuleReadModel:
    """
    Build ModuleReadModel from current services.

    This function can be called directly from api/v1/ endpoints.
    """
    now_str = _now_iso()
    modules: Dict[str, ModuleSnapshotV1] = {}
    zone_module_map: Dict[str, List[str]] = {}

    # ── Load module schemas from registry ─────────────────────────────────
    if module_registry is not None:
        try:
            schemas = module_registry.get_all_schemas()
            for module_id, schema in schemas.items():
                modules[module_id] = ModuleSnapshotV1(
                    module_id=module_id,
                    module_name_de=schema.get("name_de", module_id),
                    module_icon=schema.get("icon", "mdi:puzzle"),
                    module_color=schema.get("color", "#888888"),
                    relevant_roles=schema.get("relevant_roles", []),
                    relevant_tags=schema.get("relevant_tags", []),
                    relevant_domains=schema.get("relevant_domains", []),
                )
        except Exception:
            _LOGGER.debug("Failed to load module schemas from registry", exc_info=True)

    # ── Enrich with zone automation config state ──────────────────────────
    if zone_automation_controller is not None:
        try:
            all_configs = zone_automation_controller.get_all_configs()
            for zone_id, cfg in all_configs.items():
                zone_modules = []
                cfg_dict = cfg.to_dict() if hasattr(cfg, "to_dict") else cfg
                modules_dict = cfg_dict.get("modules", {})
                
                for module_id, mod_config in modules_dict.items():
                    zone_modules.append(module_id)
                    
                    if module_id in modules:
                        snapshot = modules[module_id]
                        snapshot.config.update(mod_config)
                        snapshot.enabled = mod_config.get("enabled", True)
                        
                        # Build field states from config
                        field_states = []
                        for key, value in mod_config.items():
                            if key != "enabled":
                                field_states.append(ModuleFieldStateV1(
                                    key=key,
                                    value=value,
                                    field_type="auto",
                                ))
                        snapshot.field_states = field_states
                    
                    # Track zone applicability
                    if module_id in modules:
                        if zone_id not in modules[module_id].applicable_zones:
                            modules[module_id].applicable_zones.append(zone_id)
                
                zone_module_map[zone_id] = zone_modules
        except Exception:
            _LOGGER.debug("Failed to load zone automation configs", exc_info=True)

    # ── Enrich with zone truth store ──────────────────────────────────────
    if zone_truth_store is not None:
        try:
            all_zones = zone_truth_store.get_all_zones()
            for zone in all_zones:
                zone_id = zone.zone_id
                enabled_modules = zone.enabled_modules or set()
                
                if zone_id not in zone_module_map:
                    zone_module_map[zone_id] = list(enabled_modules)
                else:
                    zone_module_map[zone_id] = list(set(zone_module_map[zone_id]) | enabled_modules)
                
                for module_id in enabled_modules:
                    if module_id in modules:
                        if zone_id not in modules[module_id].applicable_zones:
                            modules[module_id].applicable_zones.append(zone_id)
        except Exception:
            _LOGGER.debug("Failed to load zone truth", exc_info=True)

    # ── Build summary ─────────────────────────────────────────────────────
    total_enabled = sum(1 for m in modules.values() if m.enabled)
    total_zones = len(zone_module_map)
    
    summary = {
        "total_modules": len(modules),
        "enabled_modules": total_enabled,
        "total_zones": total_zones,
        "generated_at": now_str,
        "revision": _module_state.get("last_revision", 0),
    }

    return ModuleReadModel(
        generated_at=now_str,
        modules=modules,
        zone_module_map=zone_module_map,
        summary=summary,
    )


def update_module_state(
    module_id: str,
    state_update: Dict[str, Any],
    health: str = "ok",
    health_message: str = "",
) -> None:
    """
    Update runtime state for a module.

    Called by module engines to report current state.
    """
    if module_id not in _module_state["modules"]:
        _module_state["modules"][module_id] = ModuleSnapshotV1(
            module_id=module_id,
            module_name_de=module_id,
            module_icon="mdi:puzzle",
            module_color="#888888",
        )
    
    snapshot = _module_state["modules"][module_id]
    snapshot.update_state(state_update)
    snapshot.health = health
    snapshot.health_message = health_message
    
    _module_state["last_revision"] = snapshot.revision


def get_module_state(module_id: str) -> Optional[Dict[str, Any]]:
    """Get current state snapshot for a module."""
    snapshot = _module_state["modules"].get(module_id)
    if snapshot is None:
        return None
    return snapshot.to_dict()


def get_all_module_states() -> Dict[str, Dict[str, Any]]:
    """Get all module states."""
    return {mid: s.to_dict() for mid, s in _module_state["modules"].items()}


def reset_module_state() -> None:
    """Reset module state (for testing)."""
    _module_state["modules"] = {}
    _module_state["zone_module_map"] = {}
    _module_state["last_revision"] = 0


__all__ = [
    "ModuleSnapshotV1",
    "ModuleFieldStateV1",
    "ModuleReadModel",
    "build_module_read_model",
    "get_module_read_model",
    "update_module_state",
    "get_module_state",
    "get_all_module_states",
    "reset_module_state",
]
