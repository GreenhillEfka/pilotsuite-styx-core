"""Tagging primitives for PilotSuite."""

from .models import Tag, TagDisplay, TagGovernance, TagHAConfig
from .registry import TagRegistry, TagRegistryError
from .assignments import (
    ALLOWED_SUBJECT_KINDS,
    TagAssignment,
    TagAssignmentStore,
    TagAssignmentStoreError,
    TagAssignmentValidationError,
)
from .zone_integration import (
    TagZoneIntegration,
    ZoneGovernance,
    HabitusZoneConfig,
    create_tag_zone_integration,
)

__all__ = [
    # Models
    "Tag",
    "TagDisplay",
    "TagGovernance",
    "TagHAConfig",
    # Registry
    "TagRegistry",
    "TagRegistryError",
    # Assignments
    "ALLOWED_SUBJECT_KINDS",
    "TagAssignment",
    "TagAssignmentStore",
    "TagAssignmentStoreError",
    "TagAssignmentValidationError",
    # Zone Integration
    "TagZoneIntegration",
    "ZoneGovernance",
    "HabitusZoneConfig",
    "create_tag_zone_integration",
]
