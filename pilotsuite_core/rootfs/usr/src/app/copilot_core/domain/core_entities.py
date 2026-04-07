"""Domain Layer (Clean Core Logic).

Pure Python classes without infrastructure dependencies.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

@dataclass
class ZoneEntity:
    """Pure domain entity for a zone."""
    zone_id: str
    name: str
    zone_type: str
    state: str = "idle"
    last_updated: datetime = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now(timezone.utc)

@dataclass
class SceneEntity:
    """Pure domain entity for a scene."""
    name: str
    states: Dict[str, Any]
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

class TaskEntity:
    """Pure domain entity for a background task."""
    def __init__(self, task_id: str, name: str, payload: Dict[str, Any]):
        self.task_id = task_id
        self.name = name
        self.payload = payload
        self.status = "pending"
        self.result = None
        self.created_at = datetime.now(timezone.utc)
