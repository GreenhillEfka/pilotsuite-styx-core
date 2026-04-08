# Migrated from pilotsuite-styx-ha
"""User Hints Models — pure dataclasses, no HA dependencies."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class HintStatus(Enum):
    """Status of a user hint."""
    PENDING = "pending"
    ANALYZED = "analyzed"
    SUGGESTION_CREATED = "suggestion_created"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


class HintType(Enum):
    """Type of user hint."""
    AUTOMATION = "automation"          # "Schalte X mit Y"
    RELATIONSHIP = "relationship"      # "X und Y gehoeren zusammen"
    PREFERENCE = "preference"          # "Ich mag X nicht"
    SCHEDULE = "schedule"              # "X soll um Y Uhr passieren"
    OPTIMIZATION = "optimization"      # "X koennte effizienter sein"
    FEATURE_REQUEST = "feature_request" # "Ich wuensche mir X"


@dataclass
class UserHint:
    """A user-provided hint for automation or improvement."""

    id: str
    text: str                           # Original user text
    hint_type: HintType
    status: HintStatus = HintStatus.PENDING

    # Parsed information
    entities: List[str] = field(default_factory=list)      # Extracted entity names
    actions: List[str] = field(default_factory=list)       # Extracted actions
    conditions: List[str] = field(default_factory=list)    # Extracted conditions
    schedule: Optional[str] = None                          # Parsed schedule

    # Generated suggestion
    suggested_automation: Optional[Dict[str, Any]] = None
    confidence: float = 0.0

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    analyzed_at: Optional[datetime] = None
    user_feedback: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "hint_type": self.hint_type.value,
            "status": self.status.value,
            "entities": self.entities,
            "actions": self.actions,
            "conditions": self.conditions,
            "schedule": self.schedule,
            "suggested_automation": self.suggested_automation,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "user_feedback": self.user_feedback,
        }


@dataclass
class HintSuggestion:
    """A generated automation suggestion from a hint."""

    hint_id: str
    name: str
    description: str
    trigger: Dict[str, Any]
    action: Dict[str, Any]
    condition: Optional[Dict[str, Any]] = None

    # Automation config
    automation_config: Dict[str, Any] = field(default_factory=dict)

    # Confidence and reasoning
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hint_id": self.hint_id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "action": self.action,
            "condition": self.condition,
            "automation_config": self.automation_config,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }
