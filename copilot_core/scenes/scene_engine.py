"""PilotSuite Scene Management — Complex Multi-Device Scenes."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# SCENE TYPES
# =============================================================================

class SceneTriggerType(Enum):
    """Scene trigger types."""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    PRESENCE = "presence"
    WEATHER = "weather"
    ENERGY = "energy"
    CALENDAR = "calendar"
    AUTOMATION = "automation"


@dataclass
class SceneAction:
    """Single action within a scene."""
    service: str
    entity_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    delay_seconds: float = 0.0


@dataclass
class Scene:
    """Scene definition."""
    scene_id: str
    name: str
    description: Optional[str] = None
    icon: str = "mdi:palette"
    actions: List[SceneAction] = field(default_factory=list)
    trigger_type: SceneTriggerType = SceneTriggerType.MANUAL
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0  # Higher = more important
    cooldown_seconds: int = 0
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# SCENE ENGINE
# =============================================================================

class SceneEngine:
    """
    Scene Management Engine
    
    Features:
    - Multi-device scenes
    - Sequential/parallel execution
    - Trigger-based activation
    - Cooldown management
    - Scene chaining
    
    Usage:
    ```python
    from copilot_core.scenes import SceneEngine, Scene, SceneAction
    
    engine = SceneEngine(hass)
    
    # Create scene
    scene = Scene(
        scene_id="morning_routine",
        name="Morning Routine",
        actions=[
            SceneAction("light.turn_on", "light.bedroom", {"brightness_pct": 50}),
            SceneAction("climate.set_temperature", "climate.bedroom", {"temperature": 21}),
            SceneAction("media_player.play_media", "media_player.bedroom", {
                "media_content_id": "playlist:morning",
                "media_content_type": "playlist",
            }, delay_seconds=5),
        ],
    )
    
    engine.add_scene(scene)
    
    # Activate scene
    await engine.activate_scene("morning_routine")
    ```
    """

    def __init__(self, hass):
        self.hass = hass
        self._scenes: Dict[str, Scene] = {}
        self._active_scenes: Dict[str, datetime] = {}

    def add_scene(self, scene: Scene):
        """Add a scene."""
        self._scenes[scene.scene_id] = scene
        logger.info(f"Added scene: {scene.name} ({scene.scene_id})")

    def remove_scene(self, scene_id: str) -> bool:
        """Remove a scene."""
        if scene_id in self._scenes:
            del self._scenes[scene_id]
            logger.info(f"Removed scene: {scene_id}")
            return True
        return False

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """Get scene by ID."""
        return self._scenes.get(scene_id)

    def get_all_scenes(self) -> List[Scene]:
        """Get all scenes."""
        return list(self._scenes.values())

    async def activate_scene(self, scene_id: str, source: str = "manual") -> Dict[str, Any]:
        """
        Activate a scene.
        
        Args:
            scene_id: Scene to activate
            source: What triggered the activation
        
        Returns:
            Execution result
        """
        scene = self.get_scene(scene_id)
        
        if not scene:
            return {"success": False, "error": f"Scene not found: {scene_id}"}
        
        if not scene.enabled:
            return {"success": False, "error": f"Scene disabled: {scene_id}"}
        
        # Check cooldown
        if scene.last_triggered:
            elapsed = (datetime.now() - scene.last_triggered).total_seconds()
            if elapsed < scene.cooldown_seconds:
                remaining = scene.cooldown_seconds - elapsed
                return {"success": False, "error": f"Cooldown active ({remaining:.0f}s remaining)"}
        
        logger.info(f"Activating scene: {scene.name}")
        
        # Execute actions
        results = []
        for action in scene.actions:
            if action.delay_seconds > 0:
                await asyncio.sleep(action.delay_seconds)
            
            result = await self._execute_action(action)
            results.append(result)
        
        # Update scene state
        scene.last_triggered = datetime.now()
        scene.trigger_count += 1
        scene.updated_at = datetime.now()
        
        self._active_scenes[scene_id] = datetime.now()
        
        success_count = sum(1 for r in results if r.get("success", False))
        
        return {
            "success": True,
            "scene_id": scene_id,
            "scene_name": scene.name,
            "actions_executed": len(results),
            "actions_successful": success_count,
            "source": source,
        }

    async def _execute_action(self, action: SceneAction) -> Dict[str, Any]:
        """Execute a single scene action."""
        try:
            domain, service = action.service.split(".", 1)
            
            await self.hass.services.async_call(
                domain,
                service,
                {"entity_id": action.entity_id, **action.data},
                blocking=False,
            )
            
            return {"success": True, "action": action.service}
            
        except Exception as e:
            logger.error(f"Action failed: {action.service} - {e}")
            return {"success": False, "action": action.service, "error": str(e)}

    async def deactivate_scene(self, scene_id: str) -> bool:
        """Deactivate a scene (reverse actions if possible)."""
        if scene_id not in self._active_scenes:
            return False
        
        del self._active_scenes[scene_id]
        logger.info(f"Deactivated scene: {scene_id}")
        return True

    def get_active_scenes(self) -> List[str]:
        """Get list of currently active scenes."""
        return list(self._active_scenes.keys())


# =============================================================================
# PREDEFINED SCENES
# =============================================================================

def get_predefined_scenes() -> List[Scene]:
    """Get library of predefined scenes."""
    return [
        # Morning scenes
        Scene(
            scene_id="morning_wakeup",
            name="Morning Wakeup",
            description="Gradual wake-up sequence",
            icon="mdi:sun-rise",
            actions=[
                SceneAction("light.turn_on", "light.bedroom", {"brightness_pct": 10, "color_temp": 400}),
                SceneAction("light.turn_on", "light.bedroom", {"brightness_pct": 30}, delay_seconds=60),
                SceneAction("cover.open_cover", "cover.bedroom", delay_seconds=120),
                SceneAction("light.turn_on", "light.bedroom", {"brightness_pct": 80}, delay_seconds=180),
                SceneAction("climate.set_temperature", "climate.home", {"temperature": 21}, delay_seconds=240),
            ],
            trigger_type=SceneTriggerType.SCHEDULED,
            trigger_config={"time": "07:00"},
            cooldown_seconds=300,
        ),
        
        # Evening scenes
        Scene(
            scene_id="evening_relax",
            name="Evening Relax",
            description="Cozy evening atmosphere",
            icon="mdi:moon-waning-crescent",
            actions=[
                SceneAction("light.turn_off", "light.kitchen"),
                SceneAction("light.turn_off", "light.hallway"),
                SceneAction("light.turn_on", "light.living_room", {"brightness_pct": 30, "color_temp": 300}),
                SceneAction("media_player.turn_on", "media_player.living_room"),
                SceneAction("climate.set_temperature", "climate.home", {"temperature": 20}),
            ],
            trigger_type=SceneTriggerType.PRESENCE,
            trigger_config={"state": "home", "time_after": "18:00"},
        ),
        
        # Night scenes
        Scene(
            scene_id="good_night",
            name="Good Night",
            description="Turn everything off for sleep",
            icon="mdi:sleep",
            actions=[
                SceneAction("light.turn_off", "light.all_lights"),
                SceneAction("cover.close_cover", "cover.all_covers"),
                SceneAction("switch.turn_off", "switch.tv"),
                SceneAction("switch.turn_off", "switch.amplifier"),
                SceneAction("alarm_control_panel.alarm_arm_night", "alarm_control_panel.home"),
                SceneAction("climate.set_temperature", "climate.home", {"temperature": 18}, delay_seconds=60),
            ],
            trigger_type=SceneTriggerType.MANUAL,
        ),
        
        # Away scenes
        Scene(
            scene_id="leaving_home",
            name="Leaving Home",
            description="Secure home when leaving",
            icon="mdi:exit-run",
            actions=[
                SceneAction("light.turn_off", "light.all_lights"),
                SceneAction("switch.turn_off", "switch.all_switches"),
                SceneAction("climate.set_temperature", "climate.home", {"temperature": 16}),
                SceneAction("alarm_control_panel.alarm_arm_away", "alarm_control_panel.home"),
                SceneAction("notify.notify", None, {"message": "Home secured, have a great day!"}),
            ],
            trigger_type=SceneTriggerType.PRESENCE,
            trigger_config={"state": "away"},
            cooldown_seconds=600,
        ),
        
        # Energy saving scenes
        Scene(
            scene_id="energy_save",
            name="Energy Save Mode",
            description="Minimize energy consumption",
            icon="mdi:leaf",
            actions=[
                SceneAction("light.turn_off", "light.all_lights"),
                SceneAction("climate.set_temperature", "climate.home", {"temperature": 19}),
                SceneAction("switch.turn_off", "switch.standby_devices"),
                SceneAction("water_heater.set_operation_mode", "water_heater.home", {"operation_mode": "eco"}),
            ],
            trigger_type=SceneTriggerType.ENERGY,
            trigger_config={"price_threshold": 0.40},
        ),
        
        # Party scenes
        Scene(
            scene_id="party_mode",
            name="Party Mode",
            description="Light and music for parties",
            icon="mdi:party-popper",
            actions=[
                SceneAction("light.turn_on", "light.living_room", {"brightness_pct": 100, "effect": "colorloop"}),
                SceneAction("light.turn_on", "light.kitchen", {"brightness_pct": 80}),
                SceneAction("media_player.volume_set", "media_player.living_room", {"volume_level": 0.6}),
                SceneAction("scene.turn_on", "scene.party_lights"),
            ],
            trigger_type=SceneTriggerType.MANUAL,
        ),
        
        # Movie scenes
        Scene(
            scene_id="movie_night",
            name="Movie Night",
            description="Perfect movie watching environment",
            icon="mdi:movie",
            actions=[
                SceneAction("light.turn_off", "light.living_room"),
                SceneAction("light.turn_on", "light.living_room_bias", {"brightness_pct": 10}),
                SceneAction("cover.close_cover", "cover.living_room"),
                SceneAction("media_player.turn_on", "media_player.tv"),
                SceneAction("climate.set_temperature", "climate.home", {"temperature": 22}),
                SceneAction("switch.turn_on", "switch.popcorn_machine"),
            ],
            trigger_type=SceneTriggerType.MANUAL,
        ),
        
        # Welcome home
        Scene(
            scene_id="welcome_home",
            name="Welcome Home",
            description="Warm welcome when arriving",
            icon="mdi:home-heart",
            actions=[
                SceneAction("light.turn_on", "light.entrance", {"brightness_pct": 80}),
                SceneAction("light.turn_on", "light.hallway", {"brightness_pct": 50}),
                SceneAction("climate.set_temperature", "climate.home", {"temperature": 21}),
                SceneAction("media_player.play_media", "media_player.kitchen", {
                    "media_content_id": "playlist:welcome",
                    "media_content_type": "playlist",
                }),
                SceneAction("notify.notify", None, {"message": "Welcome home!"}),
            ],
            trigger_type=SceneTriggerType.PRESENCE,
            trigger_config={"state": "home", "was_away": True},
            cooldown_seconds=300,
        ),
    ]


# =============================================================================
# SCENE AUTOMATIONS
# =============================================================================

class SceneAutomationManager:
    """Manage automatic scene activation based on triggers."""

    def __init__(self, hass, scene_engine: SceneEngine):
        self.hass = hass
        self.scene_engine = scene_engine

    async def evaluate_triggers(self):
        """Evaluate all scene triggers."""
        for scene in self.scene_engine.get_all_scenes():
            if not scene.enabled or scene.trigger_type == SceneTriggerType.MANUAL:
                continue
            
            should_activate = await self._check_trigger(scene)
            
            if should_activate:
                result = await self.scene_engine.activate_scene(scene.scene_id, source=f"auto:{scene.trigger_type.value}")
                
                if result.get("success"):
                    logger.info(f"Auto-activated scene: {scene.name}")

    async def _check_trigger(self, scene: Scene) -> bool:
        """Check if scene trigger conditions are met."""
        if scene.trigger_type == SceneTriggerType.SCHEDULED:
            return self._check_schedule_trigger(scene.trigger_config)
        
        elif scene.trigger_type == SceneTriggerType.PRESENCE:
            return await self._check_presence_trigger(scene.trigger_config)
        
        elif scene.trigger_type == SceneTriggerType.WEATHER:
            return await self._check_weather_trigger(scene.trigger_config)
        
        elif scene.trigger_type == SceneTriggerType.ENERGY:
            return await self._check_energy_trigger(scene.trigger_config)
        
        elif scene.trigger_type == SceneTriggerType.CALENDAR:
            return await self._check_calendar_trigger(scene.trigger_config)
        
        return False

    def _check_schedule_trigger(self, config: Dict[str, Any]) -> bool:
        """Check scheduled time trigger."""
        now = datetime.now()
        scheduled_time = config.get("time", "00:00")
        
        current_time = now.strftime("%H:%M")
        
        return current_time == scheduled_time

    async def _check_presence_trigger(self, config: Dict[str, Any]) -> bool:
        """Check presence-based trigger."""
        required_state = config.get("state")
        
        # Get presence state from HA
        presence_state = self.hass.states.get("presence.home")
        
        if not presence_state:
            return False
        
        is_present = presence_state.state == "home"
        
        if required_state == "home":
            return is_present
        elif required_state == "away":
            return not is_present
        
        return False

    async def _check_weather_trigger(self, config: Dict[str, Any]) -> bool:
        """Check weather-based trigger."""
        # Would check weather conditions
        return False

    async def _check_energy_trigger(self, config: Dict[str, Any]) -> bool:
        """Check energy-based trigger."""
        price_threshold = config.get("price_threshold")
        
        # Would check current energy price
        if price_threshold:
            # current_price = get_current_energy_price()
            # return current_price > price_threshold
            pass
        
        return False

    async def _check_calendar_trigger(self, config: Dict[str, Any]) -> bool:
        """Check calendar-based trigger."""
        # Would check calendar events
        return False


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_scenes(hass, config: Dict[str, Any]):
    """Set up scene management in Home Assistant."""
    engine = SceneEngine(hass)
    
    # Add predefined scenes
    predefined = get_predefined_scenes()
    for scene in predefined:
        engine.add_scene(scene)
    
    # Add custom scenes from config
    custom_scenes = config.get("custom_scenes", [])
    for scene_config in custom_scenes:
        scene = Scene(
            scene_id=scene_config["scene_id"],
            name=scene_config["name"],
            description=scene_config.get("description"),
            actions=[
                SceneAction(
                    service=a["service"],
                    entity_id=a["entity_id"],
                    data=a.get("data", {}),
                    delay_seconds=a.get("delay_seconds", 0),
                )
                for a in scene_config.get("actions", [])
            ],
        )
        engine.add_scene(scene)
    
    # Set up automation manager
    automation_manager = SceneAutomationManager(hass, engine)
    
    # Store in hass.data
    hass.data["pilotsuite_scene_engine"] = engine
    hass.data["pilotsuite_scene_automation"] = automation_manager
    
    # Set up periodic trigger evaluation
    from homeassistant.helpers.event import async_track_time_interval
    async_track_time_interval(hass, lambda now: automation_manager.evaluate_triggers(), timedelta(seconds=30))
    
    logger.info(f"Scene management set up with {len(engine.get_all_scenes())} scenes")
    
    return engine, automation_manager
