"""Module Configuration API Endpoint

Defines the schema and API endpoint for module configuration.
Supports 7 module types with triggers, actions, zone overrides, and priority rules.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/module-config", tags=["module-config"])

class ModuleType(str, Enum):
    """Supported module types"""
    LIGHT = "LIGHT"
    AUDIO = "AUDIO"
    CLIMATE = "CLIMATE"
    COVER = "COVER"
    ENERGY = "ENERGY"
    SCENE = "SCENE"
    SECURITY = "SECURITY"

class Trigger(BaseModel):
    """Trigger definition for a module"""
    id: str = Field(..., description="Unique identifier for the trigger")
    name: str = Field(..., description="Human-readable name of the trigger")
    description: Optional[str] = Field(None, description="Description of what the trigger does")
    conditions: List[Dict[str, Any]] = Field(..., description="List of conditions that must be met for the trigger")

class Action(BaseModel):
    """Action definition for a module"""
    id: str = Field(..., description="Unique identifier for the action")
    name: str = Field(..., description="Human-readable name of the action")
    description: Optional[str] = Field(None, description="Description of what the action does")
    parameters: Dict[str, Any] = Field(..., description="Parameters for the action")

class ZoneOverride(BaseModel):
    """Zone override configuration"""
    zone_id: str = Field(..., description="Identifier of the zone to override")
    enabled: bool = Field(..., description="Whether this override is active")
    settings: Dict[str, Any] = Field(..., description="Zone-specific settings")

class PriorityRule(BaseModel):
    """Priority rule for conflict resolution"""
    id: str = Field(..., description="Unique identifier for the priority rule")
    name: str = Field(..., description="Human-readable name of the rule")
    condition: str = Field(..., description="Condition under which this rule applies")
    priority: int = Field(..., description="Priority level (higher number = higher priority)")
    action: str = Field(..., description="Action to take when rule applies")

class ModuleConfig(BaseModel):
    """Configuration for a single module"""
    id: str = Field(..., description="Unique identifier for the module")
    name: str = Field(..., description="Human-readable name of the module")
    type: ModuleType = Field(..., description="Type of module")
    enabled: bool = Field(True, description="Whether the module is enabled")
    triggers: List[Trigger] = Field([], description="List of triggers for this module")
    actions: List[Action] = Field([], description="List of actions for this module")
    zone_overrides: List[ZoneOverride] = Field([], description="Zone-specific overrides")
    priority_rules: List[PriorityRule] = Field([], description="Priority rules for conflict resolution")

class ModuleConfigResponse(BaseModel):
    """Response model for module configuration"""
    modules: List[ModuleConfig] = Field(..., description="List of module configurations")

# In-memory storage for module configurations (would be replaced with database in production)
_module_configs: Dict[str, ModuleConfig] = {}

@router.get("/schema", response_model=ModuleConfigResponse)
async def get_module_schema():
    """Get the current module configuration schema"""
    return ModuleConfigResponse(modules=list(_module_configs.values()))

@router.get("/{module_id}", response_model=ModuleConfig)
async def get_module_config(module_id: str):
    """Get configuration for a specific module"""
    if module_id not in _module_configs:
        raise HTTPException(status_code=404, detail="Module not found")
    return _module_configs[module_id]

@router.post("/", response_model=ModuleConfig)
async def create_module_config(config: ModuleConfig):
    """Create a new module configuration"""
    _module_configs[config.id] = config
    return config

@router.put("/{module_id}", response_model=ModuleConfig)
async def update_module_config(module_id: str, config: ModuleConfig):
    """Update an existing module configuration"""
    if module_id != config.id:
        raise HTTPException(status_code=400, detail="Module ID mismatch")
    _module_configs[module_id] = config
    return config

@router.delete("/{module_id}")
async def delete_module_config(module_id: str):
    """Delete a module configuration"""
    if module_id in _module_configs:
        del _module_configs[module_id]
        return {"message": "Module configuration deleted"}
    else:
        raise HTTPException(status_code=404, detail="Module not found")

# Example module configurations
def initialize_example_configs():
    """Initialize with example configurations for each module type"""
    examples = [
        ModuleConfig(
            id="light-001",
            name="Living Room Lights",
            type=ModuleType.LIGHT,
            enabled=True,
            triggers=[
                Trigger(
                    id="motion-trigger",
                    name="Motion Detected",
                    description="Trigger when motion is detected in living room",
                    conditions=[{"sensor": "motion.living_room", "state": "on"}]
                )
            ],
            actions=[
                Action(
                    id="turn-on",
                    name="Turn On Lights",
                    description="Turn on all living room lights",
                    parameters={"brightness": 100, "color_temp": 4000}
                )
            ],
            zone_overrides=[],
            priority_rules=[]
        ),
        ModuleConfig(
            id="audio-001",
            name="Living Room Audio",
            type=ModuleType.AUDIO,
            enabled=True,
            triggers=[
                Trigger(
                    id="time-trigger",
                    name="Evening Time",
                    description="Trigger at 7pm every day",
                    conditions=[{"time": "19:00"}]
                )
            ],
            actions=[
                Action(
                    id="play-playlist",
                    name="Play Jazz Playlist",
                    description="Play relaxing jazz playlist",
                    parameters={"playlist": "relaxing-jazz", "volume": 30}
                )
            ],
            zone_overrides=[],
            priority_rules=[]
        ),
        ModuleConfig(
            id="climate-001",
            name="Main Thermostat",
            type=ModuleType.CLIMATE,
            enabled=True,
            triggers=[
                Trigger(
                    id="temp-change",
                    name="Temperature Drop",
                    description="Trigger when temperature drops below 18°C",
                    conditions=[{"sensor": "temperature.main", "operator": "<", "value": 18}]
                )
            ],
            actions=[
                Action(
                    id="heat-on",
                    name="Turn On Heating",
                    description="Set thermostat to heating mode",
                    parameters={"target_temp": 22, "mode": "heat"}
                )
            ],
            zone_overrides=[],
            priority_rules=[]
        ),
        ModuleConfig(
            id="cover-001",
            name="Living Room Blinds",
            type=ModuleType.COVER,
            enabled=True,
            triggers=[
                Trigger(
                    id="sun-position",
                    name="Bright Sun",
                    description="Trigger when sun is bright and high",
                    conditions=[{"sensor": "sun.brightness", "operator": ">", "value": 80}]
                )
            ],
            actions=[
                Action(
                    id="close-blinds",
                    name="Close Blinds",
                    description="Close living room blinds",
                    parameters={"position": 0}  # 0 = closed
                )
            ],
            zone_overrides=[],
            priority_rules=[]
        ),
        ModuleConfig(
            id="energy-001",
            name="Energy Monitor",
            type=ModuleType.ENERGY,
            enabled=True,
            triggers=[
                Trigger(
                    id="high-consumption",
                    name="High Energy Usage",
                    description="Trigger when energy consumption exceeds 2kW",
                    conditions=[{"sensor": "power.total", "operator": ">", "value": 2000}]
                )
            ],
            actions=[
                Action(
                    id="notify-user",
                    name="Send Notification",
                    description="Notify user of high energy consumption",
                    parameters={"message": "Energy consumption is high", "priority": "medium"}
                )
            ],
            zone_overrides=[],
            priority_rules=[]
        ),
        ModuleConfig(
            id="scene-001",
            name="Movie Night Scene",
            type=ModuleType.SCENE,
            enabled=True,
            triggers=[
                Trigger(
                    id="time-and-input",
                    name="TV Input Active",
                    description="Trigger when TV input is active after 6pm",
                    conditions=[{"sensor": "media.tv_input", "state": "active"}, {"time": "18:00+"}]
                )
            ],
            actions=[
                Action(
                    id="activate-scene",
                    name="Activate Movie Scene",
                    description="Dim lights and set audio",
                    parameters={
                        "lights": {"brightness": 10},
                        "audio": {"playlist": "ambient", "volume": 15}
                    }
                )
            ],
            zone_overrides=[],
            priority_rules=[]
        ),
        ModuleConfig(
            id="security-001",
            name="Front Door Security",
            type=ModuleType.SECURITY,
            enabled=True,
            triggers=[
                Trigger(
                    id="door-unlocked",
                    name="Door Unlocked",
                    description="Trigger when front door is unlocked at night",
                    conditions=[{"sensor": "lock.front_door", "state": "unlocked"}, {"time": "22:00-06:00"}]
                )
            ],
            actions=[
                Action(
                    id="notify-security",
                    name="Send Security Alert",
                    description="Send notification about unlocked door",
                    parameters={"message": "Front door unlocked at night", "priority": "high"}
                )
            ],
            zone_overrides=[],
            priority_rules=[]
        )
    ]
    
    for config in examples:
        _module_configs[config.id] = config

# Initialize example configurations
initialize_example_configs()