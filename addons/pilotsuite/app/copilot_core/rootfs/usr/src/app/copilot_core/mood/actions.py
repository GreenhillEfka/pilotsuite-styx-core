"""Action engine for mood-based automation.

Converts mood states into Home Assistant service calls for lights and media.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union

from .engine import MoodState, MoodResult

_LOGGER = logging.getLogger(__name__)


@dataclass
class LightAction:
    """Light action configuration."""
    
    action: str  # "turn_on", "turn_off", "scene"
    brightness_pct: Optional[int] = None
    color_temp: Optional[int] = None
    rgb_color: Optional[List[int]] = None
    scene: Optional[str] = None
    transition: Optional[int] = None


@dataclass
class MediaAction:
    """Media action configuration."""
    
    action: str  # "play_media", "pause", "stop", "volume_set", "off"
    media_content_type: Optional[str] = None
    media_content_id: Optional[str] = None
    volume_level: Optional[float] = None


@dataclass
class MoodActionConfig:
    """Complete action configuration for a mood state."""
    
    lights: Optional[LightAction] = None
    media: Optional[MediaAction] = None


@dataclass
class ZoneActionConfig:
    """Action configuration for a specific zone."""
    
    name: str
    light_entities: List[str] = field(default_factory=list)
    media_entities: List[str] = field(default_factory=list)
    moods: Dict[MoodState, MoodActionConfig] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of an action execution."""
    
    success: bool
    service_calls: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ActionEngine:
    """Converts mood states to Home Assistant service calls."""
    
    def __init__(self):
        self._last_actions: Dict[str, ActionResult] = {}
        self._user_initiated_media: Dict[str, datetime] = {}
        self._action_cooldowns: Dict[str, datetime] = {}
        
        # Default action configurations
        self._default_mood_actions = self._create_default_actions()
    
    def _create_default_actions(self) -> Dict[MoodState, MoodActionConfig]:
        """Create default action configurations for each mood state."""
        
        return {
            MoodState.AWAY: MoodActionConfig(
                lights=LightAction(action="turn_off"),
                media=MediaAction(action="pause")
            ),
            MoodState.NIGHT: MoodActionConfig(
                lights=LightAction(
                    action="turn_on",
                    brightness_pct=20,
                    color_temp=400,  # warm
                    transition=5
                ),
                media=MediaAction(action="pause")
            ),
            MoodState.RELAX: MoodActionConfig(
                lights=LightAction(
                    action="turn_on",
                    brightness_pct=40,
                    color_temp=380,  # warm
                    transition=10
                ),
                media=MediaAction(
                    action="volume_set",
                    volume_level=0.18
                )
            ),
            MoodState.FOCUS: MoodActionConfig(
                lights=LightAction(
                    action="turn_on",
                    brightness_pct=80,
                    color_temp=350,  # neutral/cool
                    transition=3
                ),
                media=MediaAction(action="pause")
            ),
            MoodState.ACTIVE: MoodActionConfig(
                lights=LightAction(
                    action="turn_on",
                    brightness_pct=90,
                    color_temp=320,  # bright/cool
                    transition=2
                )
            ),
            MoodState.NEUTRAL: MoodActionConfig(
                lights=LightAction(
                    action="turn_on",
                    brightness_pct=60,
                    color_temp=350,
                    transition=5
                )
            )
        }
    
    def generate_actions(
        self,
        zone_name: str,
        mood_result: MoodResult,
        zone_config: ZoneActionConfig,
        current_states: Dict[str, Any],
        cooldown_seconds: int = 120
    ) -> ActionResult:
        """Generate service calls for a mood transition."""
        
        # Check cooldown
        last_action = self._action_cooldowns.get(zone_name)
        if last_action:
            cooldown_remaining = (
                (last_action + timedelta(seconds=cooldown_seconds)) - 
                datetime.now(timezone.utc)
            ).total_seconds()
            
            if cooldown_remaining > 0:
                return ActionResult(
                    success=False,
                    errors=[f"Action cooldown active: {cooldown_remaining:.1f}s remaining"]
                )
        
        service_calls = []
        errors = []
        
        # Get mood configuration
        mood_config = zone_config.moods.get(mood_result.mood)
        if not mood_config:
            mood_config = self._default_mood_actions.get(mood_result.mood)
        
        if not mood_config:
            errors.append(f"No action configuration for mood: {mood_result.mood.value}")
            return ActionResult(success=False, errors=errors)
        
        # Generate light actions
        if mood_config.lights and zone_config.light_entities:
            light_calls = self._generate_light_calls(
                mood_config.lights,
                zone_config.light_entities,
                current_states
            )
            service_calls.extend(light_calls)
        
        # Generate media actions (with user-initiated protection)
        if mood_config.media and zone_config.media_entities:
            media_calls = self._generate_media_calls(
                mood_config.media,
                zone_config.media_entities,
                current_states,
                zone_name
            )
            service_calls.extend(media_calls)
        
        # Record action time
        self._action_cooldowns[zone_name] = datetime.now(timezone.utc)
        
        result = ActionResult(
            success=len(errors) == 0,
            service_calls=service_calls,
            errors=errors
        )
        
        self._last_actions[zone_name] = result
        return result
    
    def _generate_light_calls(
        self,
        light_action: LightAction,
        entities: List[str],
        current_states: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate light service calls."""
        
        calls = []
        
        for entity_id in entities:
            if light_action.action == "turn_off":
                calls.append({
                    "domain": "light",
                    "service": "turn_off",
                    "target": {"entity_id": entity_id},
                    "service_data": {
                        "transition": light_action.transition or 2
                    }
                })
            
            elif light_action.action == "turn_on":
                service_data = {}
                
                if light_action.brightness_pct is not None:
                    service_data["brightness_pct"] = light_action.brightness_pct
                
                if light_action.color_temp is not None:
                    service_data["color_temp"] = light_action.color_temp
                
                if light_action.rgb_color is not None:
                    service_data["rgb_color"] = light_action.rgb_color
                
                if light_action.transition is not None:
                    service_data["transition"] = light_action.transition
                
                calls.append({
                    "domain": "light",
                    "service": "turn_on",
                    "target": {"entity_id": entity_id},
                    "service_data": service_data
                })
            
            elif light_action.action == "scene" and light_action.scene:
                calls.append({
                    "domain": "scene",
                    "service": "turn_on",
                    "target": {"entity_id": light_action.scene},
                    "service_data": {}
                })
        
        return calls
    
    def _generate_media_calls(
        self,
        media_action: MediaAction,
        entities: List[str],
        current_states: Dict[str, Any],
        zone_name: str
    ) -> List[Dict[str, Any]]:
        """Generate media player service calls."""
        
        calls = []
        
        # Check for user-initiated media (protection)
        for entity_id in entities:
            if self._is_user_initiated_media(entity_id, current_states, zone_name):
                _LOGGER.debug("Skipping media action for %s - user initiated", entity_id)
                continue
        
        for entity_id in entities:
            if media_action.action == "pause":
                calls.append({
                    "domain": "media_player",
                    "service": "media_pause",
                    "target": {"entity_id": entity_id},
                    "service_data": {}
                })
            
            elif media_action.action == "stop":
                calls.append({
                    "domain": "media_player",
                    "service": "media_stop",
                    "target": {"entity_id": entity_id},
                    "service_data": {}
                })
            
            elif media_action.action == "volume_set" and media_action.volume_level is not None:
                calls.append({
                    "domain": "media_player",
                    "service": "volume_set",
                    "target": {"entity_id": entity_id},
                    "service_data": {
                        "volume_level": media_action.volume_level
                    }
                })
            
            elif media_action.action == "play_media":
                if media_action.media_content_id and media_action.media_content_type:
                    service_data = {
                        "media_content_id": media_action.media_content_id,
                        "media_content_type": media_action.media_content_type
                    }
                    
                    calls.append({
                        "domain": "media_player",
                        "service": "play_media",
                        "target": {"entity_id": entity_id},
                        "service_data": service_data
                    })
                    
                    # Set gentle volume first if specified
                    if media_action.volume_level is not None:
                        calls.insert(-1, {
                            "domain": "media_player",
                            "service": "volume_set",
                            "target": {"entity_id": entity_id},
                            "service_data": {
                                "volume_level": media_action.volume_level
                            }
                        })
        
        return calls
    
    def _is_user_initiated_media(
        self,
        entity_id: str,
        current_states: Dict[str, Any],
        zone_name: str
    ) -> bool:
        """Check if media was recently started by user (not automation)."""
        
        # Simple heuristic: if media state changed to playing without our action
        current_state = current_states.get(entity_id, {}).get("state")
        
        if current_state == "playing":
            last_changed = current_states.get(entity_id, {}).get("last_changed")
            if last_changed:
                try:
                    if isinstance(last_changed, str):
                        change_time = datetime.fromisoformat(last_changed.replace('Z', '+00:00'))
                    else:
                        change_time = last_changed
                    
                    # If media started playing recently and we didn't trigger it
                    time_diff = (datetime.now(timezone.utc) - change_time).total_seconds()
                    if time_diff < 300:  # 5 minutes
                        last_action = self._last_actions.get(zone_name)
                        if not last_action or change_time > last_action.timestamp:
                            # Mark as user-initiated for next 30 minutes
                            self._user_initiated_media[entity_id] = datetime.now(timezone.utc)
                            return True
                            
                except (ValueError, TypeError):
                    pass
        
        # Check if still in user-initiated window
        user_init_time = self._user_initiated_media.get(entity_id)
        if user_init_time:
            time_diff = (datetime.now(timezone.utc) - user_init_time).total_seconds()
            if time_diff < 1800:  # 30 minutes
                return True
            else:
                # Expired
                del self._user_initiated_media[entity_id]
        
        return False
    
    def clear_user_initiated_media(self, entity_id: str) -> None:
        """Clear user-initiated flag for a media entity."""
        self._user_initiated_media.pop(entity_id, None)
    
    def get_last_action(self, zone_name: str) -> Optional[ActionResult]:
        """Get the last action result for a zone."""
        return self._last_actions.get(zone_name)
    
    def create_zone_config(
        self,
        zone_name: str,
        light_entities: List[str],
        media_entities: List[str],
        custom_moods: Optional[Dict[MoodState, MoodActionConfig]] = None
    ) -> ZoneActionConfig:
        """Create a zone action configuration."""
        
        moods = custom_moods.copy() if custom_moods else {}
        
        # Fill in missing moods with defaults
        for mood_state in MoodState:
            if mood_state not in moods:
                moods[mood_state] = self._default_mood_actions[mood_state]
        
        return ZoneActionConfig(
            name=zone_name,
            light_entities=light_entities,
            media_entities=media_entities,
            moods=moods
        )