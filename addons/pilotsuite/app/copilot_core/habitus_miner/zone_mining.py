"""Zone-based A→B rule mining for Habitus Miner.

Extends the base mining with zone-awareness:
- Filter events by zone (only mine patterns for entities in the same zone)
- Apply zone governance rules (confirmation, safety-critical entities)
- Per-zone configuration (confidence thresholds, etc.)

Architecture:
    Events → Zone Filter → Zone-Scoped Mining → Governance Check → Suggestions

See: docs/HABITUS_PHILOSOPHY.md
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Optional

from .model import NormEvent, Rule, MiningConfig, EventStreamType, RulesType
from .mining import mine_ab_rules

_LOGGER = logging.getLogger(__name__)


class ZoneMiningConfig:
    """Configuration for zone-based mining."""
    
    def __init__(
        self,
        zone_id: str,
        min_events: int = 10,
        confidence_threshold: float = 0.7,
        lift_threshold: float = 1.5,
        requires_confirmation: bool = True,
        safety_critical_entities: Optional[set[str]] = None,
    ):
        self.zone_id = zone_id
        self.min_events = min_events
        self.confidence_threshold = confidence_threshold
        self.lift_threshold = lift_threshold
        self.requires_confirmation = requires_confirmation
        self.safety_critical_entities = safety_critical_entities or set()


class ZoneMiningResult:
    """Result of zone-based mining."""
    
    def __init__(self, zone_id: str):
        self.zone_id = zone_id
        self.rules: list[Rule] = []
        self.filtered_rules: list[Rule] = []
        self.safety_blocked: list[dict[str, Any]] = []
        self.stats: dict[str, Any] = {}
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "rules_count": len(self.rules),
            "filtered_count": len(self.filtered_rules),
            "safety_blocked_count": len(self.safety_blocked),
            "stats": self.stats,
            "top_rules": [
                {
                    "A": r.A,
                    "B": r.B,
                    "confidence": round(r.confidence, 3),
                    "lift": round(r.lift, 2),
                    "score": round(r.score(), 3),
                }
                for r in self.filtered_rules[:5]
            ],
        }


class ZoneBasedMiner:
    """Zone-aware pattern miner.
    
    Integrates with TagZoneIntegration to:
    1. Filter events by zone membership
    2. Apply zone-specific governance
    3. Generate zone-scoped suggestions
    
    Usage:
        miner = ZoneBasedMiner(tag_zone_integration)
        results = miner.mine_all_zones(events, configs)
    """
    
    def __init__(
        self,
        tag_zone_integration: Any,  # TagZoneIntegration from tagging/
        base_config: Optional[MiningConfig] = None,
    ):
        self.tag_zone = tag_zone_integration
        self.base_config = base_config or MiningConfig()
        self._zone_configs: dict[str, ZoneMiningConfig] = {}
    
    def set_zone_config(self, zone_id: str, config: ZoneMiningConfig) -> None:
        """Set mining configuration for a zone."""
        self._zone_configs[zone_id] = config
        _LOGGER.info("ZoneBasedMiner: Set config for zone %s", zone_id)
    
    def get_zone_config(self, zone_id: str) -> ZoneMiningConfig:
        """Get mining configuration for a zone (returns default if not set)."""
        return self._zone_configs.get(zone_id, ZoneMiningConfig(zone_id))
    
    def filter_events_by_zone(
        self,
        events: EventStreamType,
        zone_id: str,
    ) -> EventStreamType:
        """Filter events to only include entities in the specified zone.
        
        Args:
            events: All events
            zone_id: Zone to filter by
            
        Returns:
            Events from entities in the zone
        """
        zone_entities = self.tag_zone.get_entities_for_zone(zone_id)
        if not zone_entities:
            return []
        
        zone_entity_set = set(zone_entities)
        filtered = [
            e for e in events
            if e.entity_id in zone_entity_set
        ]
        
        _LOGGER.debug(
            "ZoneBasedMiner: Filtered %d events to %d for zone %s (%d entities)",
            len(events), len(filtered), zone_id, len(zone_entities)
        )
        
        return filtered
    
    def mine_zone(
        self,
        events: EventStreamType,
        zone_id: str,
        zone_config: Optional[ZoneMiningConfig] = None,
    ) -> ZoneMiningResult:
        """Mine rules for a specific zone.
        
        Args:
            events: All events
            zone_id: Zone to mine
            zone_config: Optional zone-specific config
            
        Returns:
            ZoneMiningResult with rules and stats
        """
        config = zone_config or self.get_zone_config(zone_id)
        result = ZoneMiningResult(zone_id)
        
        # Filter events by zone
        zone_events = self.filter_events_by_zone(events, zone_id)
        
        if len(zone_events) < config.min_events:
            _LOGGER.info(
                "ZoneBasedMiner: Zone %s has only %d events (min: %d), skipping",
                zone_id, len(zone_events), config.min_events
            )
            result.stats = {
                "events": len(zone_events),
                "skipped": True,
                "reason": "insufficient_events",
            }
            return result
        
        # Mine rules with zone-filtered events
        result.rules = mine_ab_rules(zone_events, self.base_config)
        
        # Apply zone governance filtering
        result.filtered_rules = []
        
        for rule in result.rules:
            # Check confidence threshold
            if rule.confidence < config.confidence_threshold:
                continue
            
            # Check lift threshold
            if rule.lift < config.lift_threshold:
                continue
            
            # Check safety-critical entities
            a_entity = rule.A.split(":")[0] if ":" in rule.A else rule.A
            b_entity = rule.B.split(":")[0] if ":" in rule.B else rule.B
            
            a_critical = a_entity in config.safety_critical_entities
            b_critical = b_entity in config.safety_critical_entities
            
            if a_critical or b_critical:
                result.safety_blocked.append({
                    "rule": f"{rule.A} → {rule.B}",
                    "confidence": round(rule.confidence, 3),
                    "lift": round(rule.lift, 2),
                    "blocked_by": "safety_critical",
                    "entities": [e for e in [a_entity, b_entity] if e in config.safety_critical_entities],
                })
                continue
            
            # Rule passed all filters
            result.filtered_rules.append(rule)
        
        # Update stats
        result.stats = {
            "events": len(zone_events),
            "raw_rules": len(result.rules),
            "filtered_rules": len(result.filtered_rules),
            "safety_blocked": len(result.safety_blocked),
            "confidence_threshold": config.confidence_threshold,
            "lift_threshold": config.lift_threshold,
            "requires_confirmation": config.requires_confirmation,
        }
        
        _LOGGER.info(
            "ZoneBasedMiner: Zone %s mined %d rules -> %d filtered (%d safety-blocked)",
            zone_id, len(result.rules), len(result.filtered_rules), len(result.safety_blocked)
        )
        
        return result
    
    def mine_all_zones(
        self,
        events: EventStreamType,
        zone_configs: Optional[dict[str, ZoneMiningConfig]] = None,
    ) -> dict[str, ZoneMiningResult]:
        """Mine rules for all zones.
        
        Args:
            events: All events
            zone_configs: Optional dict of zone_id -> config
            
        Returns:
            Dict of zone_id -> ZoneMiningResult
        """
        results = {}
        
        # Get all zones
        all_zones = self.tag_zone.get_all_zones()
        
        if not all_zones:
            _LOGGER.warning("ZoneBasedMiner: No zones found")
            return results
        
        _LOGGER.info(
            "ZoneBasedMiner: Mining %d zones with %d total events",
            len(all_zones), len(events)
        )
        
        for zone_id in all_zones:
            config = (zone_configs or {}).get(zone_id, self.get_zone_config(zone_id))
            results[zone_id] = self.mine_zone(events, zone_id, config)
        
        return results
    
    def get_top_suggestions(
        self,
        results: dict[str, ZoneMiningResult],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get top suggestions across all zones.
        
        Args:
            results: Results from mine_all_zones
            limit: Maximum suggestions to return
            
        Returns:
            Sorted list of top suggestions
        """
        all_rules = []
        
        for zone_id, result in results.items():
            config = self.get_zone_config(zone_id)
            
            for rule in result.filtered_rules:
                all_rules.append({
                    "zone_id": zone_id,
                    "A": rule.A,
                    "B": rule.B,
                    "confidence": rule.confidence,
                    "lift": rule.lift,
                    "score": rule.score(),
                    "requires_confirmation": config.requires_confirmation,
                    "safety_critical": False,
                })
        
        # Sort by score
        all_rules.sort(key=lambda x: x["score"], reverse=True)
        
        return all_rules[:limit]
    
    def explain_suggestion(self, suggestion: dict[str, Any]) -> str:
        """Generate human-readable explanation for a suggestion.
        
        Args:
            suggestion: Suggestion dict from get_top_suggestions
            
        Returns:
            Human-readable explanation
        """
        zone = suggestion["zone_id"].replace("zone:", "")
        a_entity, a_state = suggestion["A"].rsplit(":", 1) if ":" in suggestion["A"] else (suggestion["A"], "?")
        b_entity, b_state = suggestion["B"].rsplit(":", 1) if ":" in suggestion["B"] else (suggestion["B"], "?")
        
        explanation = (
            f"Im Zone '{zone}': Wenn {a_entity} → {a_state}, "
            f"dann meistens {b_entity} → {b_state} "
            f"(Konfidenz: {suggestion['confidence']:.0%}, Lift: {suggestion['lift']:.1f}x)"
        )
        
        if suggestion["requires_confirmation"]:
            explanation += " [Bestätigung erforderlich]"
        
        return explanation
    
    def export_results(
        self,
        results: dict[str, ZoneMiningResult],
    ) -> dict[str, Any]:
        """Export all results for API/UI.
        
        Args:
            results: Results from mine_all_zones
            
        Returns:
            Dict with all zone results and top suggestions
        """
        return {
            "zones": {zid: r.to_dict() for zid, r in results.items()},
            "top_suggestions": self.get_top_suggestions(results),
            "summary": {
                "total_zones": len(results),
                "total_rules": sum(len(r.rules) for r in results.values()),
                "total_filtered": sum(len(r.filtered_rules) for r in results.values()),
                "total_safety_blocked": sum(len(r.safety_blocked) for r in results.values()),
            },
        }