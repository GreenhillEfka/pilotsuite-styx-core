"""Mood orchestrator - coordinates inference and actions.

Main entry point for the mood_module v0.1 implementation.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable

from .engine import MoodEngine, MoodConfig, ZoneConfig, MoodResult
from .actions import ActionEngine, ZoneActionConfig, ActionResult

_LOGGER = logging.getLogger(__name__)


@dataclass
class MoodOrchestrationResult:
    """Result of a complete mood orchestration cycle."""
    
    zone_name: str
    mood_result: MoodResult
    action_result: Optional[ActionResult] = None
    skipped_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "zone_name": self.zone_name,
            "mood": self.mood_result.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }
        
        if self.action_result:
            result["actions"] = {
                "success": self.action_result.success,
                "service_calls": self.action_result.service_calls,
                "errors": self.action_result.errors,
                "timestamp": self.action_result.timestamp.isoformat()
            }
        
        if self.skipped_reason:
            result["skipped_reason"] = self.skipped_reason
        
        return result


class MoodOrchestrator:
    """Main orchestrator for mood-based automation."""
    
    def __init__(
        self,
        mood_config: MoodConfig,
        get_sensor_data: Callable[[List[str]], Dict[str, Any]],
        execute_service_calls: Optional[Callable[[List[Dict[str, Any]]], bool]] = None
    ):
        self.mood_engine = MoodEngine(mood_config)
        self.action_engine = ActionEngine()
        self.get_sensor_data = get_sensor_data
        self.execute_service_calls = execute_service_calls
        
        self._zone_action_configs: Dict[str, ZoneActionConfig] = {}
        self._last_orchestration: Dict[str, MoodOrchestrationResult] = {}
        
        # Auto-create basic action configs for zones
        for zone_name, zone_config in mood_config.zones.items():
            self._zone_action_configs[zone_name] = self.action_engine.create_zone_config(
                zone_name=zone_name,
                light_entities=zone_config.light_entities,
                media_entities=zone_config.media_entities
            )
    
    def set_zone_action_config(self, zone_name: str, config: ZoneActionConfig) -> None:
        """Override action configuration for a zone."""
        self._zone_action_configs[zone_name] = config
    
    def orchestrate_zone(
        self,
        zone_name: str,
        dry_run: bool = False,
        force_actions: bool = False
    ) -> MoodOrchestrationResult:
        """Run complete mood orchestration for a zone."""
        
        if zone_name not in self.mood_engine.config.zones:
            raise ValueError(f"Unknown zone: {zone_name}")
        
        zone_config = self.mood_engine.config.zones[zone_name]
        
        # Collect required sensor entities
        required_entities = []
        required_entities.extend(zone_config.motion_entities)
        required_entities.extend(zone_config.light_entities)
        required_entities.extend(zone_config.media_entities)
        
        if zone_config.illuminance_entity:
            required_entities.append(zone_config.illuminance_entity)
        
        # Add override entity
        override_entity = f"input_boolean.mood_manual_override_{zone_name}"
        required_entities.append(override_entity)
        
        # Get current sensor data
        try:
            sensor_data = self.get_sensor_data(required_entities)
        except Exception as e:
            _LOGGER.error("Failed to get sensor data for zone %s: %s", zone_name, e)
            # Return error result
            dummy_features = self.mood_engine.compute_zone_features(zone_name, {})
            dummy_mood = self.mood_engine.infer_mood(zone_name, dummy_features)
            return MoodOrchestrationResult(
                zone_name=zone_name,
                mood_result=dummy_mood,
                skipped_reason=f"Sensor data unavailable: {e}"
            )
        
        # Compute features and infer mood
        features = self.mood_engine.compute_zone_features(zone_name, sensor_data)
        mood_result = self.mood_engine.infer_mood(zone_name, features)
        
        _LOGGER.debug("Zone %s mood inference: %s (confidence: %.2f)", 
                     zone_name, mood_result.mood.value, mood_result.confidence)
        
        # Check if actions should be executed
        action_result = None
        skipped_reason = None
        
        if features.user_override:
            skipped_reason = "User manual override active"
        
        elif not force_actions:
            # Check if mood actually changed
            last_result = self._last_orchestration.get(zone_name)
            if (last_result and 
                last_result.mood_result.mood == mood_result.mood and
                last_result.action_result and
                last_result.action_result.success):
                skipped_reason = "Mood unchanged and actions already applied"
        
        # Execute actions if not skipped
        if not skipped_reason:
            zone_action_config = self._zone_action_configs.get(zone_name)
            if zone_action_config:
                try:
                    action_result = self.action_engine.generate_actions(
                        zone_name=zone_name,
                        mood_result=mood_result,
                        zone_config=zone_action_config,
                        current_states=sensor_data,
                        cooldown_seconds=self.mood_engine.config.action_cooldown_seconds
                    )
                    
                    # Execute service calls if not dry run
                    if not dry_run and action_result.success and self.execute_service_calls:
                        if action_result.service_calls:
                            _LOGGER.info("Executing %d service calls for zone %s mood %s", 
                                       len(action_result.service_calls), zone_name, mood_result.mood.value)
                            
                            try:
                                success = self.execute_service_calls(action_result.service_calls)
                                if not success:
                                    action_result.success = False
                                    action_result.errors.append("Service call execution failed")
                            except Exception as e:
                                _LOGGER.error("Failed to execute service calls: %s", e)
                                action_result.success = False
                                action_result.errors.append(f"Service call execution error: {e}")
                    
                except Exception as e:
                    _LOGGER.error("Action generation failed for zone %s: %s", zone_name, e)
                    action_result = ActionResult(
                        success=False,
                        errors=[f"Action generation failed: {e}"]
                    )
            else:
                skipped_reason = "No action configuration for zone"
        
        # Create result
        result = MoodOrchestrationResult(
            zone_name=zone_name,
            mood_result=mood_result,
            action_result=action_result,
            skipped_reason=skipped_reason
        )
        
        self._last_orchestration[zone_name] = result
        return result
    
    def orchestrate_all_zones(
        self,
        dry_run: bool = False,
        force_actions: bool = False
    ) -> List[MoodOrchestrationResult]:
        """Run orchestration for all configured zones."""
        
        results = []
        for zone_name in self.mood_engine.list_zones():
            try:
                result = self.orchestrate_zone(zone_name, dry_run, force_actions)
                results.append(result)
            except Exception as e:
                _LOGGER.error("Orchestration failed for zone %s: %s", zone_name, e)
                # Create error result
                dummy_features = self.mood_engine.compute_zone_features(zone_name, {})
                dummy_mood = self.mood_engine.infer_mood(zone_name, dummy_features)
                results.append(MoodOrchestrationResult(
                    zone_name=zone_name,
                    mood_result=dummy_mood,
                    skipped_reason=f"Orchestration error: {e}"
                ))
        
        return results
    
    def get_zone_status(self, zone_name: str) -> Optional[Dict[str, Any]]:
        """Get current status for a zone."""
        
        last_result = self._last_orchestration.get(zone_name)
        if not last_result:
            return None
        
        return {
            "zone_name": zone_name,
            "current_mood": last_result.mood_result.mood.value,
            "confidence": last_result.mood_result.confidence,
            "last_update": last_result.timestamp.isoformat(),
            "last_action_success": (
                last_result.action_result.success 
                if last_result.action_result 
                else None
            ),
            "features": last_result.mood_result.features.__dict__
        }
    
    def get_all_zones_status(self) -> List[Dict[str, Any]]:
        """Get status for all zones."""
        
        statuses = []
        for zone_name in self.mood_engine.list_zones():
            status = self.get_zone_status(zone_name)
            if status:
                statuses.append(status)
        
        return statuses
    
    def force_mood(self, zone_name: str, mood_state: str, duration_minutes: Optional[int] = None) -> bool:
        """Force a specific mood for a zone (admin override)."""
        
        # This would typically set a temporary override flag
        # Implementation depends on how overrides are stored
        _LOGGER.info("Force mood %s for zone %s (duration: %s min)", 
                    mood_state, zone_name, duration_minutes)
        
        # For now, just trigger immediate orchestration
        try:
            self.orchestrate_zone(zone_name, dry_run=False, force_actions=True)
            return True
        except Exception as e:
            _LOGGER.error("Failed to force mood for zone %s: %s", zone_name, e)
            return False
    
    def clear_zone_overrides(self, zone_name: str) -> bool:
        """Clear user overrides for a zone."""
        
        try:
            # Clear user-initiated media flags
            zone_action_config = self._zone_action_configs.get(zone_name)
            if zone_action_config:
                for entity_id in zone_action_config.media_entities:
                    self.action_engine.clear_user_initiated_media(entity_id)
            
            _LOGGER.info("Cleared overrides for zone %s", zone_name)
            return True
        except Exception as e:
            _LOGGER.error("Failed to clear overrides for zone %s: %s", zone_name, e)
            return False


def create_default_config() -> MoodConfig:
    """Create a default mood configuration for testing."""
    
    # This would typically be loaded from configuration
    wohnbereich = ZoneConfig(
        name="wohnbereich",
        motion_entities=["binary_sensor.motion_wohnzimmer"],
        light_entities=["light.wohnzimmer"],
        media_entities=["media_player.wohnbereich"],
        illuminance_entity="sensor.illuminance_wohnzimmer"
    )
    
    schlafbereich = ZoneConfig(
        name="schlafbereich",
        motion_entities=["binary_sensor.motion_schlafzimmer"],
        light_entities=["light.schlafzimmer"],
        media_entities=["media_player.schlafbereich"],
        illuminance_entity=None  # fallback to time-based
    )
    
    return MoodConfig(
        zones={
            "wohnbereich": wohnbereich,
            "schlafbereich": schlafbereich
        },
        min_dwell_time_seconds=600,  # 10 minutes
        action_cooldown_seconds=120  # 2 minutes
    )