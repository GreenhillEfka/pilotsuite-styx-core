"""State Versioning for Conflict Prevention (Slice 165).

Adds `state_version` to all mutable entities to prevent race conditions.
"""

from __future__ import annotations

import logging
from typing import Dict, Any

_LOGGER = logging.getLogger(__name__)

class VersionedEntity:
    """Mixin for entities with state versioning."""
    
    def __init__(self, initial_version: int = 1):
        self.state_version = initial_version

    def update_state(self, new_data: Dict[str, Any], expected_version: int) -> bool:
        """Update state only if version matches."""
        if self.state_version != expected_version:
            _LOGGER.warning("Version mismatch: %d != %d", self.state_version, expected_version)
            return False
            
        # Apply changes
        for key, value in new_data.items():
            setattr(self, key, value)
            
        self.state_version += 1
        return True

# Example integration with HabitusZone
def patch_zone_with_versioning(zone_class):
    """Patch HabitusZone class with versioning support."""
    original_init = zone_class.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        VersionedEntity.__init__(self)
        
    zone_class.__init__ = new_init
    zone_class.update_with_version = VersionedEntity.update_state
    
# API Conflict Handler (Flask)
def handle_version_conflict(expected: int, actual: int):
    """Return Flask response for version conflict."""
    from flask import jsonify
    return jsonify({
        "error": "conflict", 
        "message": f"State version mismatch: expected {expected}, got {actual}",
        "expected_version": expected,
        "actual_version": actual
    }), 409
