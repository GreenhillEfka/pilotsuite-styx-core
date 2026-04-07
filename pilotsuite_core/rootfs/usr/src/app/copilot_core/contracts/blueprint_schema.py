"""Blueprint Contract Schema (E1).

Pydantic v2-based schema validation for blueprint definitions.
Supports JSON Schema Draft 2020-12 for versioning and validation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from pydantic.json_schema import JsonSchemaMode


class BlueprintStatus(str, Enum):
    """Lifecycle status of a blueprint."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class BlueprintTier(str, Enum):
    """Stability tier for blueprints."""
    EXPERIMENTAL = "experimental"
    STABLE = "stable"
    LTS = "lts"  # Long-term support


class ConfigPropertySchema(BaseModel):
    """Schema for a single configuration property."""
    type: Literal["string", "integer", "number", "boolean", "array", "object", "null"]
    description: Optional[str] = None
    default: Optional[Any] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    pattern: Optional[str] = None
    enum: Optional[List[Any]] = None
    required: bool = False
    items: Optional["ConfigPropertySchema"] = None  # For array types
    properties: Optional[Dict[str, "ConfigPropertySchema"]] = None  # For object types

    model_config = ConfigDict(extra="forbid")


class BlueprintContract(BaseModel):
    """Canonical contract for a PilotSuite blueprint.

    This contract defines the complete interface and behavior specification
    for a blueprint module, including events, actions, configuration, and
    versioning metadata.

    JSON Schema Draft: 2020-12
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
    )

    # === Identity ===
    blueprint_id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]*_v\d+(\.[a-z0-9_]+)?$",
        description="Unique blueprint identifier with version suffix (e.g., motion_light_v1)",
        examples=["motion_light_v1", "climate_hvac_v2.1"],
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable name",
        examples=["Motion-Activated Lighting"],
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2048,
        description="Detailed description of blueprint purpose and behavior",
    )
    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*)?(\+[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*)?$",
        description="Semantic version (SemVer 2.0)",
        examples=["1.0.0", "2.1.0-beta.1", "1.0.0+build.123"],
    )

    # === Module Location ===
    module_path: str = Field(
        ...,
        pattern=r"^copilot_core\.[a-z_]+(\.[a-z_]+)*$",
        description="Python module path (must be under copilot_core)",
        examples=["copilot_core.automation.motion_light"],
    )
    module_class: Optional[str] = Field(
        None,
        pattern=r"^[A-Z][a-zA-Z0-9_]*$",
        description="Main class name if blueprint is class-based",
    )

    # === Event Interface ===
    events_published: List[str] = Field(
        default_factory=list,
        description="Events this blueprint emits",
        examples=[["motion_detected", "light_activated"]],
    )
    events_consumed: List[str] = Field(
        default_factory=list,
        description="Events this blueprint listens to",
        examples=[["state_changed", "homeassistant/started"]],
    )

    # === Action Interface ===
    actions_exposed: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Actions/services exposed by this blueprint",
        examples=[[{"name": "turn_on", "description": "Activate the device"}]],
    )

    # === Configuration Schema ===
    config_schema: Dict[str, ConfigPropertySchema] = Field(
        default_factory=dict,
        description="Configuration property definitions",
    )
    required_config: List[str] = Field(
        default_factory=list,
        description="List of required configuration keys",
    )

    # === Lifecycle ===
    status: BlueprintStatus = Field(
        default=BlueprintStatus.ACTIVE,
        description="Current lifecycle status",
    )
    tier: BlueprintTier = Field(
        default=BlueprintTier.STABLE,
        description="Stability tier",
    )
    deprecated_since: Optional[datetime] = Field(
        None,
        description="Deprecation date (if deprecated)",
    )
    retired_at: Optional[datetime] = Field(
        None,
        description="Retirement date (if retired)",
    )

    # === Metadata ===
    author: Optional[str] = Field(None, max_length=256)
    license: Optional[str] = Field("proprietary", max_length=128)
    tags: List[str] = Field(default_factory=list, max_length=20)
    dependencies: List[str] = Field(
        default_factory=list,
        description="Other blueprint_ids this depends on",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # === Validation ===
    @field_validator("events_published", "events_consumed")
    @classmethod
    def validate_event_names(cls, v: List[str]) -> List[str]:
        for event in v:
            if not event or not isinstance(event, str):
                raise ValueError("Event names must be non-empty strings")
            if len(event) > 256:
                raise ValueError(f"Event name too long: {event[:50]}...")
        return v

    @field_validator("actions_exposed")
    @classmethod
    def validate_actions(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for action in v:
            if not isinstance(action, dict):
                raise ValueError("Each action must be a dictionary")
            if "name" not in action:
                raise ValueError("Action must have a 'name' field")
            if not isinstance(action["name"], str) or not action["name"]:
                raise ValueError("Action name must be a non-empty string")
        return v

    @model_validator(mode="after")
    def validate_lifecycle_dates(self) -> "BlueprintContract":
        if self.deprecated_since and self.retired_at:
            if self.retired_at < self.deprecated_since:
                raise ValueError("retired_at must be after deprecated_since")
        if self.status == BlueprintStatus.RETIRED and not self.retired_at:
            raise ValueError("Retired blueprints must have retired_at set")
        if self.status == BlueprintStatus.DEPRECATED and not self.deprecated_since:
            raise ValueError("Deprecated blueprints must have deprecated_since set")
        return self

    @model_validator(mode="after")
    def validate_required_config(self) -> "BlueprintContract":
        for key in self.required_config:
            if key not in self.config_schema:
                raise ValueError(f"Required config key '{key}' not defined in config_schema")
        return self

    def to_json_schema(self, mode: JsonSchemaMode = "validation") -> Dict[str, Any]:
        """Generate JSON Schema Draft 2020-12 representation."""
        schema = self.model_json_schema(mode=mode)
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        return schema

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 hash of contract signature."""
        signature = {
            "blueprint_id": self.blueprint_id,
            "version": self.version,
            "module_path": self.module_path,
            "events_published": sorted(self.events_published),
            "events_consumed": sorted(self.events_consumed),
            "actions_exposed": self.actions_exposed,
            "config_schema": {k: v.model_dump() for k, v in self.config_schema.items()},
            "required_config": sorted(self.required_config),
        }
        dump = json.dumps(signature, sort_keys=True, default=str)
        return hashlib.sha256(dump.encode()).hexdigest()

    def is_compatible_with(self, other: "BlueprintContract") -> bool:
        """Check if this contract is compatible with another (same major version)."""
        if self.blueprint_id != other.blueprint_id:
            return False
        self_major = self.version.split(".")[0]
        other_major = other.version.split(".")[0]
        return self_major == other_major


# === Example Usage ===
EXAMPLE_BLUEPRINT = BlueprintContract(
    blueprint_id="motion_light_v1",
    display_name="Motion-Activated Lighting",
    description="Automatically turns on lights when motion is detected and off after a configurable timeout.",
    version="1.0.0",
    module_path="copilot_core.automation.motion_light",
    module_class="MotionLightBlueprint",
    events_published=["motion_detected", "light_activated", "light_deactivated"],
    events_consumed=["state_changed", "motion_sensor/update"],
    actions_exposed=[
        {"name": "activate", "description": "Manually activate the motion lighting"},
        {"name": "deactivate", "description": "Manually deactivate the motion lighting"},
    ],
    config_schema={
        "light_entity": ConfigPropertySchema(
            type="string",
            description="Entity ID of the light to control",
            required=True,
        ),
        "timeout_s": ConfigPropertySchema(
            type="integer",
            description="Seconds to wait before turning off light",
            default=60,
            minimum=10,
            maximum=3600,
        ),
        "lux_threshold": ConfigPropertySchema(
            type="number",
            description="Only activate if ambient lux is below this threshold",
            default=50.0,
            minimum=0,
        ),
    },
    required_config=["light_entity"],
    status=BlueprintStatus.ACTIVE,
    tier=BlueprintTier.STABLE,
    author="PilotSuite Core Team",
    tags=["automation", "lighting", "motion", "energy-saving"],
    dependencies=[],
)
