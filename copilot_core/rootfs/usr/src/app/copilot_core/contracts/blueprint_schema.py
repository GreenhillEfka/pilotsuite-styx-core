"""Blueprint Contract Schema (Orakel SotA Run 2026-04-07).

Pydantic-based schema validation for blueprint definitions.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any

class BlueprintContract(BaseModel):
    """Canonical contract for a blueprint."""
    blueprint_id: str = Field(pattern=r'^[a-z_]+_v\d+$')
    module_path: str = Field(pattern=r'^copilot_core\.[a-z_]+\.[a-z_]+$')
    events_published: List[str] = Field(default_factory=list)
    events_consumed: List[str] = Field(default_factory=list)
    actions_exposed: List[str] = Field(default_factory=list)
    config_schema: Dict[str, Any] = Field(default_factory=dict)

# Example Usage
EXAMPLE_BLUEPRINT = BlueprintContract(
    blueprint_id="motion_light_v1",
    module_path="copilot_core.automation.motion_light",
    events_published=["motion_detected"],
    actions_exposed=["turn_on_light", "turn_off_light"],
    config_schema={
        "type": "object",
        "properties": {
            "light_entity": {"type": "string"},
            "timeout_s": {"type": "integer", "minimum": 10}
        }
    }
)
