"""API v1 Models - User Hints data structures."""

from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class HintStatus(str, Enum):
    """Hint status enumeration."""
    PENDING = "pending"
    ACTIVE = "active"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class HintType(str, Enum):
    """Hint type enumeration."""
    AUTOMATION = "automation"
    SUGGESTION = "suggestion"
    WARNING = "warning"
    INFO = "info"


@dataclass
class HintData:
    """Hint data structure."""
    hint_id: str
    title: str
    description: str
    hint_type: HintType
    status: HintStatus
    entity_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict."""
        return {
            "id": self.hint_id,
            "title": self.title,
            "description": self.description,
            "type": self.hint_type.value if self.hint_type else None,
            "status": self.status.value if self.status else None,
            "entity_ids": self.entity_ids,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    def to_automation(self) -> dict:
        """Convert to an automation suggestion dict for the API."""
        return {
            "id": self.hint_id,
            "antecedent": self.title,
            "consequent": self.description,
            "confidence": self.confidence,
            "type": self.hint_type.value if self.hint_type else "suggestion",
            "entity_ids": self.entity_ids,
        }
