"""Zone Truth Store — Canonical Core-owned zone topology storage.

This module provides the Single Source of Truth for zone definitions,
separate from config attributes. It stores:
- Zone archetypes (canonical zone types with default module configs)
- Zone instances (actual synced zones from HA with entity assignments)
- Topology revision tracking with provenance metadata
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from copilot_core.homeassistant.habitus_zones import ZoneType


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _normalize_zone_type(zone_type: str) -> str:
    """Normalize zone type against canonical ZoneType enum."""
    normalized = (zone_type or "").strip().lower()
    allowed = {item.value for item in ZoneType}
    return normalized if normalized in allowed else ""


@dataclass
class ZoneEntityAssignmentV1:
    """Typed entity assignment within a zone.

    This is the canonical representation of an entity belonging to a zone,
    with role, tags, and provenance tracking.
    """
    entity_id: str
    role: str
    tags: List[str] = field(default_factory=list)
    display_name: str = ""
    source: str = "manual"  # manual, ha_sync, import, auto_discovery
    added_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZoneEntityAssignmentV1":
        return cls(
            entity_id=data.get("entity_id", ""),
            role=data.get("role", "other"),
            tags=list(data.get("tags", [])),
            display_name=data.get("display_name", ""),
            source=data.get("source", "manual"),
            added_at=data.get("added_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
        )


@dataclass
class ZoneDefinitionV1:
    """Canonical zone definition — the Core truth record.

    This is separate from ZoneAutomationConfig (which holds automation settings).
    ZoneDefinitionV1 is the topology truth: what entities belong to what zone,
    with what roles, and where the data came from.
    """
    zone_id: str
    name: str
    zone_type: str
    icon: str = "mdi:room"
    priority: int = 0
    enabled: bool = True
    
    # Entity assignments (canonical truth)
    entities: List[ZoneEntityAssignmentV1] = field(default_factory=list)
    
    # Module applicability for this zone instance
    enabled_modules: Set[str] = field(default_factory=set)
    
    # Provenance tracking
    source: str = "core"  # core, ha_sync, import
    synced_at: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    
    # Revision tracking
    revision: int = 0
    
    # HA context (for sync round-trips)
    ha_area_id: Optional[str] = None
    ha_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "zone_type": self.zone_type,
            "icon": self.icon,
            "priority": self.priority,
            "enabled": self.enabled,
            "entities": [e.to_dict() for e in self.entities],
            "enabled_modules": sorted(self.enabled_modules),
            "source": self.source,
            "synced_at": self.synced_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revision": self.revision,
            "ha_area_id": self.ha_area_id,
            "ha_context": self.ha_context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZoneDefinitionV1":
        entities_data = data.get("entities", [])
        entities = [ZoneEntityAssignmentV1.from_dict(e) for e in entities_data if isinstance(e, dict)]
        
        enabled_modules = data.get("enabled_modules", [])
        if isinstance(enabled_modules, list):
            enabled_modules = set(str(m).strip() for m in enabled_modules if str(m).strip())
        
        return cls(
            zone_id=data.get("zone_id", ""),
            name=data.get("name", ""),
            zone_type=_normalize_zone_type(data.get("zone_type")) or "living",
            icon=data.get("icon", "mdi:room"),
            priority=int(data.get("priority") or 0),
            enabled=bool(data.get("enabled", True)),
            entities=entities,
            enabled_modules=enabled_modules,
            source=data.get("source", "core"),
            synced_at=data.get("synced_at"),
            created_at=data.get("created_at", _now_iso()),
            updated_at=data.get("updated_at", _now_iso()),
            revision=int(data.get("revision") or 0),
            ha_area_id=data.get("ha_area_id"),
            ha_context=dict(data.get("ha_context") or {}),
        )

    def touch(self, global_revision: int = None) -> None:
        """Update revision and timestamps.
        
        Args:
            global_revision: Optional global revision counter to sync with.
        """
        self.revision = global_revision if global_revision is not None else (self.revision + 1)
        self.updated_at = _now_iso()

    def add_entity(self, entity_id: str, role: str, tags: List[str] = None,
                   display_name: str = "", source: str = "manual") -> ZoneEntityAssignmentV1:
        """Add or update an entity assignment."""
        now = _now_iso()
        tags = tags or []
        
        # Check for existing assignment
        for existing in self.entities:
            if existing.entity_id == entity_id:
                existing.role = role
                existing.tags = list(tags)
                existing.display_name = display_name or existing.display_name
                existing.source = source
                existing.updated_at = now
                return existing
        
        # Create new assignment
        assignment = ZoneEntityAssignmentV1(
            entity_id=entity_id,
            role=role,
            tags=list(tags),
            display_name=display_name or entity_id.split(".")[-1].replace("_", " ").title(),
            source=source,
            added_at=now,
            updated_at=now,
        )
        self.entities.append(assignment)
        self.touch()
        return assignment

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity assignment."""
        before = len(self.entities)
        self.entities = [e for e in self.entities if e.entity_id != entity_id]
        if len(self.entities) < before:
            self.touch()
            return True
        return False

    def get_entities_by_role(self) -> Dict[str, List[ZoneEntityAssignmentV1]]:
        """Group entities by role."""
        by_role: Dict[str, List[ZoneEntityAssignmentV1]] = {}
        for entity in self.entities:
            by_role.setdefault(entity.role, []).append(entity)
        return by_role


@dataclass
class ZoneArchetypeV1:
    """Zone archetype definition — template for zone instances.

    Archetypes define the default structure for a zone type:
    - Default enabled modules
    - Default entity roles expected
    - Default policy overrides
    """
    zone_type: str
    name_template: str
    description: str = ""
    default_modules: Set[str] = field(default_factory=set)
    default_icon: str = "mdi:room"
    default_priority: int = 0
    expected_roles: List[str] = field(default_factory=list)
    policy_overrides: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_type": self.zone_type,
            "name_template": self.name_template,
            "description": self.description,
            "default_modules": sorted(self.default_modules),
            "default_icon": self.default_icon,
            "default_priority": self.default_priority,
            "expected_roles": list(self.expected_roles),
            "policy_overrides": self.policy_overrides,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZoneArchetypeV1":
        default_modules = data.get("default_modules", [])
        if isinstance(default_modules, list):
            default_modules = set(str(m).strip() for m in default_modules if str(m).strip())
        
        return cls(
            zone_type=data.get("zone_type", ""),
            name_template=data.get("name_template", ""),
            description=data.get("description", ""),
            default_modules=default_modules,
            default_icon=data.get("default_icon", "mdi:room"),
            default_priority=int(data.get("default_priority") or 0),
            expected_roles=list(data.get("expected_roles", [])),
            policy_overrides=dict(data.get("policy_overrides") or {}),
        )


@dataclass
class ZoneTopologyRevision:
    """Revision record for zone topology changes.

    Tracks what changed, when, and why — for audit and sync purposes.
    """
    revision: int
    timestamp: str
    zone_id: str
    change_type: str  # created, updated, deleted, entity_added, entity_removed, sync
    change_summary: str = ""
    source: str = "core"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ZoneTruthStore:
    """Canonical store for zone topology truth.

    This is the Single Source of Truth for:
    - Zone definitions (what zones exist)
    - Entity assignments (what belongs to each zone)
    - Topology revisions (what changed and when)

    Storage:
    - In-memory with optional JSON persistence
    - Revision tracking for delta sync
    - Provenance metadata for all changes
    """

    def __init__(
        self,
        *,
        persist: bool = True,
        storage_path: str = "/data/zone_truth.json",
    ):
        self.persist = bool(persist)
        self.storage_path = storage_path
        
        # Zone definitions keyed by zone_id
        self._zones: Dict[str, ZoneDefinitionV1] = {}
        
        # Zone archetypes keyed by zone_type
        self._archetypes: Dict[str, ZoneArchetypeV1] = {}
        
        # Revision history (in-memory, last N revisions)
        self._revisions: List[ZoneTopologyRevision] = []
        self._max_revisions = 1000
        
        # Current topology revision counter
        self._revision_counter: int = 0
        
        # Make directly constructed stores the active singleton as well.
        # This keeps API handlers, sync flows, and contract tests on the same
        # canonical store instead of accidentally reading stale /data state.
        global _zone_truth_store
        _zone_truth_store = self
        
        # Load from disk if persistence enabled
        if self.persist:
            self._load()

    def _load(self) -> None:
        """Load zone truth from disk."""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                
                zones_data = data.get("zones", {})
                for zone_id, zone_data in zones_data.items():
                    if isinstance(zone_data, dict):
                        self._zones[zone_id] = ZoneDefinitionV1.from_dict(zone_data)
                
                archetypes_data = data.get("archetypes", {})
                for zone_type, arch_data in archetypes_data.items():
                    if isinstance(arch_data, dict):
                        self._archetypes[zone_type] = ZoneArchetypeV1.from_dict(arch_data)
                
                self._revision_counter = int(data.get("revision_counter", 0))
                
                revisions_data = data.get("revisions", [])
                self._revisions = [
                    ZoneTopologyRevision(**r) if isinstance(r, dict) else r
                    for r in revisions_data[-self._max_revisions:]
                ]
        except Exception:
            # Silent fail — start fresh
            pass

    def _save(self) -> None:
        """Persist zone truth to disk."""
        if not self.persist:
            return
        
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {
                "zones": {zid: z.to_dict() for zid, z in self._zones.items()},
                "archetypes": {zt: a.to_dict() for zt, a in self._archetypes.items()},
                "revision_counter": self._revision_counter,
                "revisions": [r.to_dict() for r in self._revisions[-self._max_revisions:]],
                "saved_at": _now_iso(),
            }
            with open(self.storage_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _record_revision(self, zone_id: str, change_type: str,
                         change_summary: str = "", source: str = "core",
                         metadata: Dict[str, Any] = None) -> ZoneTopologyRevision:
        """Record a topology revision."""
        self._revision_counter += 1
        revision = ZoneTopologyRevision(
            revision=self._revision_counter,
            timestamp=_now_iso(),
            zone_id=zone_id,
            change_type=change_type,
            change_summary=change_summary,
            source=source,
            metadata=metadata or {},
        )
        self._revisions.append(revision)
        if len(self._revisions) > self._max_revisions:
            self._revisions = self._revisions[-self._max_revisions:]
        return revision

    def get_zone(self, zone_id: str) -> Optional[ZoneDefinitionV1]:
        """Get a zone definition by ID."""
        return self._zones.get(zone_id)

    def get_all_zones(self) -> List[ZoneDefinitionV1]:
        """Get all zone definitions."""
        return list(self._zones.values())

    def get_zone_ids(self) -> List[str]:
        """Get all zone IDs."""
        return list(self._zones.keys())

    def create_zone(
        self,
        zone_id: str,
        name: str,
        zone_type: str,
        icon: str = "mdi:room",
        priority: int = 0,
        enabled_modules: Set[str] = None,
        source: str = "core",
        ha_area_id: str = None,
    ) -> ZoneDefinitionV1:
        """Create a new zone definition."""
        if zone_id in self._zones:
            raise ValueError(f"Zone '{zone_id}' already exists")
        
        zone = ZoneDefinitionV1(
            zone_id=zone_id,
            name=name,
            zone_type=_normalize_zone_type(zone_type) or "living",
            icon=icon,
            priority=priority,
            enabled_modules=enabled_modules or set(),
            source=source,
            ha_area_id=ha_area_id,
        )
        zone.touch(self._revision_counter)
        
        self._zones[zone_id] = zone
        self._record_revision(
            zone_id=zone_id,
            change_type="created",
            change_summary=f"Created zone '{name}' ({zone_type})",
            source=source,
            metadata={"name": name, "zone_type": zone_type},
        )
        self._save()
        return zone

    def update_zone(
        self,
        zone_id: str,
        name: str = None,
        zone_type: str = None,
        icon: str = None,
        priority: int = None,
        enabled_modules: Set[str] = None,
        ha_context: Dict[str, Any] = None,
        source: str = "core",
    ) -> ZoneDefinitionV1:
        """Update an existing zone definition."""
        zone = self._zones.get(zone_id)
        if zone is None:
            raise ValueError(f"Zone '{zone_id}' not found")
        
        changes: Dict[str, Any] = {}
        
        if name is not None and name != zone.name:
            changes["name"] = {"old": zone.name, "new": name}
            zone.name = name
        
        if zone_type is not None:
            normalized = _normalize_zone_type(zone_type)
            if normalized and normalized != zone.zone_type:
                changes["zone_type"] = {"old": zone.zone_type, "new": normalized}
                zone.zone_type = normalized
        
        if icon is not None and icon != zone.icon:
            changes["icon"] = {"old": zone.icon, "new": icon}
            zone.icon = icon
        
        if priority is not None and priority != zone.priority:
            changes["priority"] = {"old": zone.priority, "new": priority}
            zone.priority = priority
        
        if enabled_modules is not None:
            changes["enabled_modules"] = {
                "old": sorted(zone.enabled_modules),
                "new": sorted(enabled_modules),
            }
            zone.enabled_modules = enabled_modules
        
        if ha_context is not None:
            zone.ha_context = dict(ha_context)
        
        if source != zone.source:
            zone.source = source
        
        zone.touch(self._revision_counter)
        
        if ha_context:
            zone.ha_context = ha_context
            zone.synced_at = _now_iso()
        
        self._record_revision(
            zone_id=zone_id,
            change_type="updated",
            change_summary=f"Updated zone '{zone.name}'",
            source=source,
            metadata={"changes": changes},
        )
        self._save()
        return zone

    def delete_zone(self, zone_id: str, source: str = "core") -> bool:
        """Delete a zone definition."""
        zone = self._zones.pop(zone_id, None)
        if zone is None:
            return False
        
        self._record_revision(
            zone_id=zone_id,
            change_type="deleted",
            change_summary=f"Deleted zone '{zone.name}'",
            source=source,
            metadata={"zone_type": zone.zone_type},
        )
        self._save()
        return True

    def add_entity(
        self,
        zone_id: str,
        entity_id: str,
        role: str,
        tags: List[str] = None,
        display_name: str = "",
        source: str = "manual",
    ) -> ZoneEntityAssignmentV1:
        """Add an entity to a zone."""
        zone = self._zones.get(zone_id)
        if zone is None:
            raise ValueError(f"Zone '{zone_id}' not found")
        
        self._revision_counter += 1
        assignment = zone.add_entity(
            entity_id=entity_id,
            role=role,
            tags=tags,
            display_name=display_name,
            source=source,
        )
        zone.touch(self._revision_counter)
        
        self._record_revision(
            zone_id=zone_id,
            change_type="entity_added",
            change_summary=f"Added entity '{entity_id}' to zone '{zone.name}'",
            source=source,
            metadata={"entity_id": entity_id, "role": role},
        )
        self._save()
        return assignment

    def remove_entity(self, zone_id: str, entity_id: str, source: str = "core") -> bool:
        """Remove an entity from a zone."""
        zone = self._zones.get(zone_id)
        if zone is None:
            return False
        
        removed = zone.remove_entity(entity_id)
        if removed:
            self._record_revision(
                zone_id=zone_id,
                change_type="entity_removed",
                change_summary=f"Removed entity '{entity_id}' from zone '{zone.name}'",
                source=source,
                metadata={"entity_id": entity_id},
            )
            self._save()
        return removed

    def sync_zones(
        self,
        zones: List[Dict[str, Any]],
        full_sync: bool = False,
        source: str = "ha_sync",
    ) -> Dict[str, Any]:
        """Sync zone definitions from HA.

        This is the canonical HA → Core topology sync point.

        Args:
            zones: List of zone specs from HA. Each dict may contain:
                - zone_id (str): unique zone identifier
                - name (str): display name
                - zone_type (str): zone type
                - entities (list): entity assignments (list or role-map)
                - icon (str): Material Design icon
                - priority (int): matching priority
                - ha_area_id (str): HA area ID
            full_sync: If True, delete zones not in the payload.
            source: Source marker for provenance.

        Returns:
            dict with keys: synced, created, updated, deleted, zone_ids
        """
        result = {
            "synced": 0,
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "zone_ids": [],
        }
        
        seen_ids: Set[str] = set()
        
        for spec in zones:
            zone_id = str(spec.get("zone_id") or "").strip()
            if not zone_id:
                continue
            
            seen_ids.add(zone_id)
            result["zone_ids"].append(zone_id)
            
            # Normalize entities from various input formats
            entities_payload = spec.get("entities")
            entity_ids: List[str] = []
            role_by_entity: Dict[str, str] = {}
            
            if isinstance(entities_payload, dict):
                # Role-map format: {"lights": ["light.x"], "motion": [...]}
                for role, ids in entities_payload.items():
                    for eid in ids if isinstance(ids, list) else []:
                        eid = str(eid).strip()
                        if eid:
                            entity_ids.append(eid)
                            role_by_entity[eid] = str(role).strip()
            elif isinstance(entities_payload, list):
                # List format: ["light.x", "sensor.y"] or [{"entity_id": "...", "role": "..."}]
                for item in entities_payload:
                    if isinstance(item, str):
                        eid = item.strip()
                        if eid:
                            entity_ids.append(eid)
                    elif isinstance(item, dict):
                        eid = str(item.get("entity_id") or "").strip()
                        if eid:
                            entity_ids.append(eid)
                            role = str(item.get("role") or "").strip()
                            if role:
                                role_by_entity[eid] = role
            
            # Normalize enabled_modules
            enabled_modules: Set[str] = set()
            raw_modules = spec.get("enabled_modules")
            if isinstance(raw_modules, (list, set, tuple)):
                enabled_modules = {
                    str(m).strip() for m in raw_modules if str(m).strip()
                }
            
            # Create or update zone
            existing = self._zones.get(zone_id)
            
            if existing is None:
                # Create new zone
                self.create_zone(
                    zone_id=zone_id,
                    name=str(spec.get("name") or zone_id).strip(),
                    zone_type=str(spec.get("zone_type") or "living").strip(),
                    icon=str(spec.get("icon") or "mdi:room").strip(),
                    priority=int(spec.get("priority") or 0),
                    enabled_modules=enabled_modules,
                    source=source,
                    ha_area_id=str(spec.get("ha_area_id") or spec.get("area_id") or "").strip() or None,
                )
                result["created"] += 1
                zone = self._zones[zone_id]
            else:
                # Update existing zone
                self.update_zone(
                    zone_id=zone_id,
                    name=str(spec.get("name") or existing.name).strip(),
                    zone_type=str(spec.get("zone_type") or existing.zone_type).strip(),
                    icon=str(spec.get("icon") or existing.icon).strip(),
                    priority=int(spec.get("priority") or existing.priority),
                    enabled_modules=enabled_modules if enabled_modules else None,
                    ha_context={
                        "area_id": spec.get("area_id"),
                        "icon": spec.get("icon"),
                        "priority": spec.get("priority"),
                    },
                    source=source,
                )
                zone = self._zones[zone_id]
                result["updated"] += 1
            
            # Sync entity assignments
            for entity_id in entity_ids:
                role = role_by_entity.get(entity_id, "other")
                zone.add_entity(
                    entity_id=entity_id,
                    role=role,
                    source=source,
                )
            
            result["synced"] += 1
        
        # Full sync: delete zones not in payload
        if full_sync:
            to_delete = set(self._zones.keys()) - seen_ids
            for zone_id in to_delete:
                if self.delete_zone(zone_id, source=source):
                    result["deleted"] += 1
        
        return result

    def get_revision_history(
        self,
        zone_id: str = None,
        limit: int = 100,
        since_revision: int = None,
    ) -> List[ZoneTopologyRevision]:
        """Get revision history, optionally filtered by zone."""
        revisions = self._revisions
        
        if zone_id:
            revisions = [r for r in revisions if r.zone_id == zone_id]
        
        if since_revision is not None:
            revisions = [r for r in revisions if r.revision > since_revision]
        
        return revisions[-limit:]

    def get_current_revision(self) -> int:
        """Get current topology revision counter."""
        return self._revision_counter

    def get_entities_by_role(self, zone_id: str) -> Dict[str, List[ZoneEntityAssignmentV1]]:
        """Get entities grouped by role for a zone."""
        zone = self._zones.get(zone_id)
        if zone is None:
            return {}
        return zone.get_entities_by_role()

    def get_all_entities_read_model(
        self,
        since_revision: int = None,
        deltas: bool = False,
        compact: bool = False,
    ) -> Dict[str, Any]:
        """Get deterministic read-model for all zone entity assignments.

        Supports delta queries since a given revision.
        """
        zone_ids = sorted(self._zones.keys())
        all_zones = []
        
        for zone_id in zone_ids:
            zone = self._zones[zone_id]
            zone_data = {
                "zone_id": zone.zone_id,
                "zone_name": zone.name,
                "entity_count": len(zone.entities),
                "role_count": {
                    role: len(entities)
                    for role, entities in zone.get_entities_by_role().items()
                },
                "revision": zone.revision,
                "updated_at": zone.updated_at,
                "compact": compact,
            }
            
            if not compact:
                zone_data["entities"] = [e.to_dict() for e in zone.entities]
                zone_data["entities_by_role"] = {
                    role: [e.to_dict() for e in entities]
                    for role, entities in zone.get_entities_by_role().items()
                }
            
            all_zones.append(zone_data)
        
        summary = {
            "zone_count": len(all_zones),
            "entity_count": sum(z["entity_count"] for z in all_zones),
            "revision": self._revision_counter,
            "updated_at": _now_iso(),
            "compact": compact,
        }

        # Delta filtering
        if since_revision is not None and deltas:
            changed_zones = [z for z in all_zones if z["revision"] > since_revision]
            return {
                "zones": changed_zones,
                "summary": {
                    **summary,
                    "returned_zone_count": len(changed_zones),
                    "returned_entity_count": sum(z["entity_count"] for z in changed_zones),
                    "delta_from_revision": since_revision,
                    "delta_to_revision": self._revision_counter,
                },
                "delta": {
                    "enabled": True,
                    "zone_ids": [z["zone_id"] for z in changed_zones],
                },
            }

        return {
            "zones": all_zones,
            "summary": summary,
        }

    def register_archetype(self, archetype: ZoneArchetypeV1) -> None:
        """Register a zone archetype."""
        self._archetypes[archetype.zone_type] = archetype
        self._save()

    def get_archetype(self, zone_type: str) -> Optional[ZoneArchetypeV1]:
        """Get archetype for a zone type."""
        return self._archetypes.get(zone_type)

    def get_all_archetypes(self) -> List[ZoneArchetypeV1]:
        """Get all registered archetypes."""
        return list(self._archetypes.values())


# Singleton instance
_zone_truth_store: Optional[ZoneTruthStore] = None


def get_zone_truth_store() -> ZoneTruthStore:
    """Get or create the ZoneTruthStore singleton."""
    global _zone_truth_store
    if _zone_truth_store is None:
        _zone_truth_store = ZoneTruthStore()
    return _zone_truth_store


def reset_zone_truth_store() -> None:
    """Reset the singleton (for testing)."""
    global _zone_truth_store
    _zone_truth_store = None
