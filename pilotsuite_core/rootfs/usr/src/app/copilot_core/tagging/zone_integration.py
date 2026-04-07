"""Tag → Zone Integration - Automatic zone membership from tags.

Philosophy: Tags are semantics. When an entity is tagged with aicp.place.X,
it automatically joins HabitusZone("X"). This bridges tagging with pattern mining.

Architecture:
    Tag Assignment → TagZoneIntegration → HabitusZone update
                                  ↓
                           Habitus Miner (zone-filtered)

See: docs/HABITUS_PHILOSOPHY.md
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ZoneGovernance:
    """Security rules for a zone."""
    requires_confirmation: bool = True  # Always ask before applying
    safety_critical_entities: list[str] = field(default_factory=list)
    auto_learning_enabled: bool = True  # Learn patterns automatically
    max_suggestions_per_day: int = 5  # Limit suggestions to avoid spam


@dataclass
class HabitusZoneConfig:
    """Configuration for zone behavior."""
    min_entities: int = 1  # Minimum entities to form a zone
    min_events_for_pattern: int = 10  # Minimum events before mining
    confidence_threshold: float = 0.7  # Minimum confidence for suggestions
    lift_threshold: float = 1.5  # Minimum lift for suggestions
    time_window_hours: int = 24  # Hours to look back for patterns


class TagZoneIntegration:
    """Integrates Tag System with HabitusZones.
    
    When an entity is tagged with aicp.place.X:
    1. Auto-create HabitusZone("X") if not exists
    2. Add entity to zone's member_entity_ids
    3. Notify Habitus Miner to re-evaluate zone patterns
    
    When an entity is tagged with aicp.role.safety_critical:
    1. Set requires_confirmation=True for that entity
    2. Never auto-apply patterns involving this entity
    
    Philosophy: Tags give meaning, Zones give context.
    """
    
    # Tag prefixes that trigger zone membership
    PLACE_TAG_PREFIX = "aicp.place."
    ROLE_TAG_PREFIX = "aicp.role."
    STATE_TAG_PREFIX = "aicp.state."
    
    # Safety-critical roles that always require confirmation
    SAFETY_CRITICAL_ROLES = {
        "aicp.role.safety_critical",
        "aicp.role.security",
        "aicp.role.critical",
    }
    
    def __init__(
        self,
        tag_registry: Any,  # TagRegistry from tags/__init__.py
        on_zone_changed: Optional[Callable[[str, list[str]], None]] = None,
    ):
        self.tag_registry = tag_registry
        self.on_zone_changed = on_zone_changed
        self._zone_configs: dict[str, HabitusZoneConfig] = {}
        self._zone_governance: dict[str, ZoneGovernance] = {}
        
    def on_tag_assigned(
        self,
        entity_id: str,
        tag_id: str,
        confidence: float = 1.0,
        source: str = "manual",
    ) -> dict[str, Any]:
        """Handle tag assignment event.
        
        Called when a tag is assigned to an entity.
        Updates zone membership and governance accordingly.
        
        Args:
            entity_id: The entity receiving the tag
            tag_id: The tag being assigned (e.g., "aicp.place.küche")
            confidence: Assignment confidence (0-1)
            source: Who assigned the tag ("manual", "learned", "inferred")
            
        Returns:
            Dict with zone updates and governance changes
        """
        result = {
            "entity_id": entity_id,
            "tag_id": tag_id,
            "zones_added": [],
            "zones_removed": [],
            "governance_changes": [],
        }
        
        # Handle place tags → zone membership
        if tag_id.startswith(self.PLACE_TAG_PREFIX):
            zone_name = tag_id[len(self.PLACE_TAG_PREFIX):]
            zone_id = f"zone:{zone_name}"
            
            # Add entity to zone
            if self.tag_registry.add_to_zone(zone_id, entity_id):
                result["zones_added"].append(zone_id)
                logger.info(
                    "TagZoneIntegration: Added %s to zone %s via tag %s",
                    entity_id, zone_id, tag_id
                )
                
                # Create zone config if new
                if zone_id not in self._zone_configs:
                    self._zone_configs[zone_id] = HabitusZoneConfig()
                    self._zone_governance[zone_id] = ZoneGovernance()
                
                # Notify listeners
                if self.on_zone_changed:
                    members = self.tag_registry.get_zone_members(zone_id)
                    self.on_zone_changed(zone_id, members)
        
        # Handle role tags → governance
        if tag_id.startswith(self.ROLE_TAG_PREFIX):
            if tag_id in self.SAFETY_CRITICAL_ROLES:
                # Mark entity as safety-critical
                for zone_id in self._zone_governance:
                    if entity_id not in self._zone_governance[zone_id].safety_critical_entities:
                        self._zone_governance[zone_id].safety_critical_entities.append(entity_id)
                        result["governance_changes"].append({
                            "zone_id": zone_id,
                            "change": "safety_critical_added",
                            "entity_id": entity_id,
                        })
                        logger.info(
                            "TagZoneIntegration: Marked %s as safety-critical in zone %s",
                            entity_id, zone_id
                        )
        
        # Handle state tags → pattern filtering
        if tag_id.startswith(self.STATE_TAG_PREFIX):
            state = tag_id[len(self.STATE_TAG_PREFIX):]
            if state == "needs_repair":
                # Don't learn patterns from broken entities
                result["governance_changes"].append({
                    "entity_id": entity_id,
                    "change": "pattern_learning_disabled",
                    "reason": "needs_repair",
                })
        
        return result
    
    def on_tag_removed(
        self,
        entity_id: str,
        tag_id: str,
    ) -> dict[str, Any]:
        """Handle tag removal event.
        
        Args:
            entity_id: The entity losing the tag
            tag_id: The tag being removed
            
        Returns:
            Dict with zone updates and governance changes
        """
        result = {
            "entity_id": entity_id,
            "tag_id": tag_id,
            "zones_added": [],
            "zones_removed": [],
            "governance_changes": [],
        }
        
        # Handle place tags → zone membership removal
        if tag_id.startswith(self.PLACE_TAG_PREFIX):
            zone_name = tag_id[len(self.PLACE_TAG_PREFIX):]
            zone_id = f"zone:{zone_name}"
            
            # Remove entity from zone
            if self.tag_registry.remove_from_zone(zone_id, entity_id):
                result["zones_removed"].append(zone_id)
                logger.info(
                    "TagZoneIntegration: Removed %s from zone %s via tag removal %s",
                    entity_id, zone_id, tag_id
                )
                
                # Notify listeners
                if self.on_zone_changed:
                    members = self.tag_registry.get_zone_members(zone_id)
                    self.on_zone_changed(zone_id, members)
        
        # Handle role tags → governance removal
        if tag_id.startswith(self.ROLE_TAG_PREFIX):
            if tag_id in self.SAFETY_CRITICAL_ROLES:
                for zone_id in self._zone_governance:
                    if entity_id in self._zone_governance[zone_id].safety_critical_entities:
                        self._zone_governance[zone_id].safety_critical_entities.remove(entity_id)
                        result["governance_changes"].append({
                            "zone_id": zone_id,
                            "change": "safety_critical_removed",
                            "entity_id": entity_id,
                        })
        
        return result
    
    def get_zone_for_entity(self, entity_id: str) -> Optional[str]:
        """Get the primary zone for an entity based on its place tag.
        
        Args:
            entity_id: The entity to look up
            
        Returns:
            Zone ID if found, None otherwise
        """
        tags = self.tag_registry.get_subject_tags(entity_id)
        for tag in tags:
            if tag.startswith(self.PLACE_TAG_PREFIX):
                zone_name = tag[len(self.PLACE_TAG_PREFIX):]
                return f"zone:{zone_name}"
        return None
    
    def get_entities_for_zone(self, zone_id: str) -> list[str]:
        """Get all entities in a zone.
        
        Args:
            zone_id: The zone to look up
            
        Returns:
            List of entity IDs in the zone
        """
        return self.tag_registry.get_zone_members(zone_id)
    
    def requires_confirmation(self, entity_id: str, zone_id: Optional[str] = None) -> bool:
        """Check if an entity requires confirmation before pattern application.
        
        Args:
            entity_id: The entity to check
            zone_id: Optional zone context
            
        Returns:
            True if confirmation is required
        """
        # Check if entity has safety-critical role
        tags = self.tag_registry.get_subject_tags(entity_id)
        for tag in tags:
            if tag in self.SAFETY_CRITICAL_ROLES:
                return True
        
        # Check zone governance
        if zone_id and zone_id in self._zone_governance:
            if entity_id in self._zone_governance[zone_id].safety_critical_entities:
                return True
        
        # Check zone default
        if zone_id and zone_id in self._zone_governance:
            return self._zone_governance[zone_id].requires_confirmation
        
        return True  # Safe default: always confirm
    
    def can_auto_apply(self, antecedent: str, consequent: str, zone_id: str) -> tuple[bool, str]:
        """Check if a pattern can be auto-applied.
        
        Args:
            antecedent: The triggering entity/action
            consequent: The resulting entity/action
            zone_id: The zone context
            
        Returns:
            Tuple of (can_apply, reason)
        """
        if zone_id not in self._zone_governance:
            return False, "Zone not configured"
        
        governance = self._zone_governance[zone_id]
        
        # Check safety-critical entities
        if antecedent in governance.safety_critical_entities:
            return False, f"Antecedent {antecedent} is safety-critical"
        
        if consequent in governance.safety_critical_entities:
            return False, f"Consequent {consequent} is safety-critical"
        
        # Check auto-learning flag
        if not governance.auto_learning_enabled:
            return False, "Auto-learning disabled for this zone"
        
        return True, "OK"
    
    def get_zone_config(self, zone_id: str) -> HabitusZoneConfig:
        """Get zone configuration.
        
        Args:
            zone_id: The zone to get config for
            
        Returns:
            Zone configuration (default if not set)
        """
        return self._zone_configs.get(zone_id, HabitusZoneConfig())
    
    def set_zone_config(
        self,
        zone_id: str,
        config: HabitusZoneConfig,
    ) -> None:
        """Set zone configuration.
        
        Args:
            zone_id: The zone to configure
            config: New configuration
        """
        self._zone_configs[zone_id] = config
        logger.info("TagZoneIntegration: Updated config for zone %s", zone_id)
    
    def get_zone_governance(self, zone_id: str) -> ZoneGovernance:
        """Get zone governance rules.
        
        Args:
            zone_id: The zone to get governance for
            
        Returns:
            Zone governance (default if not set)
        """
        return self._zone_governance.get(zone_id, ZoneGovernance())
    
    def set_zone_governance(
        self,
        zone_id: str,
        governance: ZoneGovernance,
    ) -> None:
        """Set zone governance rules.
        
        Args:
            zone_id: The zone to set governance for
            governance: New governance rules
        """
        self._zone_governance[zone_id] = governance
        logger.info("TagZoneIntegration: Updated governance for zone %s", zone_id)
    
    def get_all_zones(self) -> list[str]:
        """Get all zone IDs that have entities.
        
        Returns:
            List of zone IDs
        """
        return self.tag_registry.get_zones()
    
    def get_zone_stats(self, zone_id: str) -> dict[str, Any]:
        """Get statistics for a zone.
        
        Args:
            zone_id: The zone to get stats for
            
        Returns:
            Dict with zone statistics
        """
        members = self.get_entities_for_zone(zone_id)
        config = self.get_zone_config(zone_id)
        governance = self.get_zone_governance(zone_id)
        
        return {
            "zone_id": zone_id,
            "member_count": len(members),
            "members": members[:20],  # Truncate for display
            "config": {
                "min_entities": config.min_entities,
                "min_events_for_pattern": config.min_events_for_pattern,
                "confidence_threshold": config.confidence_threshold,
                "lift_threshold": config.lift_threshold,
            },
            "governance": {
                "requires_confirmation": governance.requires_confirmation,
                "safety_critical_count": len(governance.safety_critical_entities),
                "auto_learning_enabled": governance.auto_learning_enabled,
                "max_suggestions_per_day": governance.max_suggestions_per_day,
            },
        }


def create_tag_zone_integration(
    tag_registry: Any,
    on_zone_changed: Optional[Callable[[str, list[str]], None]] = None,
) -> TagZoneIntegration:
    """Factory function to create TagZoneIntegration.
    
    Args:
        tag_registry: The TagRegistry instance from tags/__init__.py
        on_zone_changed: Optional callback when zone membership changes
        
    Returns:
        Configured TagZoneIntegration instance
    """
    return TagZoneIntegration(
        tag_registry=tag_registry,
        on_zone_changed=on_zone_changed,
    )