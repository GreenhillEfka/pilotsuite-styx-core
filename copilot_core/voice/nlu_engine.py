"""P4-002: NLU Engine — Intent Recognition, Entity Extraction."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Common intent types."""
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    SET_VALUE = "set_value"
    INCREASE = "increase"
    DECREASE = "decrease"
    QUERY_STATUS = "query_status"
    SCENE_ACTIVATE = "scene_activate"
    SCHEDULE_CREATE = "schedule_create"
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """Extracted entity from utterance."""
    name: str
    type: str
    value: Any
    confidence: float


@dataclass
class NLUResult:
    """Result from NLU processing."""
    intent: IntentType
    intent_confidence: float
    entities: List[Entity]
    slots: Dict[str, Any]
    raw_text: str


class NLUEngine:
    """Natural Language Understanding engine."""

    def __init__(self):
        self._intent_patterns: Dict[IntentType, List[str]] = {
            IntentType.TURN_ON: [
                r"mach\s+(?:das|den|die)\s+(.+)\s+an",
                r"schalte\s+(.+)\s+ein",
                r"turn\s+on\s+(.+)",
            ],
            IntentType.TURN_OFF: [
                r"mach\s+(?:das|den|die)\s+(.+)\s+aus",
                r"schalte\s+(.+)\s+aus",
                r"turn\s+off\s+(.+)",
            ],
            IntentType.SET_VALUE: [
                r"stelle\s+(.+)\s+auf\s+(\d+)",
                r"set\s+(.+)\s+to\s+(\d+)",
            ],
            IntentType.INCREASE: [
                r"erhöhe\s+(.+)",
                r"mach\s+(.+)\s+höher",
                r"increase\s+(.+)",
            ],
            IntentType.DECREASE: [
                r"verringere\s+(.+)",
                r"mach\s+(.+)\s+niedriger",
                r"decrease\s+(.+)",
            ],
            IntentType.QUERY_STATUS: [
                r"wie\s+ist\s+(.+)",
                r"status\s+(.+)",
                r"what\s+is\s+(.+)",
            ],
        }
        
        self._entity_types = {
            "light": ["licht", "lampe", "light"],
            "thermostat": ["thermostat", "heizung", "temperature"],
            "cover": ["rollo", "vorhang", "blind", "cover"],
            "switch": ["schalter", "switch"],
        }

    def process(self, text: str, language: str = "de") -> NLUResult:
        """Process utterance and extract intent + entities."""
        text_lower = text.lower().strip()
        
        # Match intent
        intent, intent_confidence = self._match_intent(text_lower)
        
        # Extract entities
        entities = self._extract_entities(text_lower)
        
        # Fill slots
        slots = self._fill_slots(intent, entities)
        
        return NLUResult(
            intent=intent,
            intent_confidence=intent_confidence,
            entities=entities,
            slots=slots,
            raw_text=text
        )

    def _match_intent(self, text: str) -> Tuple[IntentType, float]:
        """Match text to intent."""
        for intent_type, patterns in self._intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return intent_type, 0.9
        
        return IntentType.UNKNOWN, 0.3

    def _extract_entities(self, text: str) -> List[Entity]:
        """Extract entities from text."""
        entities = []
        
        for entity_type, keywords in self._entity_types.items():
            for keyword in keywords:
                if keyword in text:
                    entities.append(Entity(
                        name=keyword,
                        type=entity_type,
                        value=keyword,
                        confidence=0.8
                    ))
        
        # Extract numbers
        numbers = re.findall(r'\d+', text)
        for num in numbers:
            entities.append(Entity(
                name="value",
                type="number",
                value=int(num),
                confidence=0.9
            ))
        
        return entities

    def _fill_slots(self, intent: IntentType, entities: List[Entity]) -> Dict[str, Any]:
        """Fill intent slots from entities."""
        slots = {}
        
        for entity in entities:
            if entity.type == "number":
                slots["value"] = entity.value
            elif entity.type in ["light", "thermostat", "cover", "switch"]:
                slots["entity_type"] = entity.type
                slots["entity_name"] = entity.name
        
        return slots

    def add_training_data(self, intent: IntentType, patterns: List[str]):
        """Add training patterns for an intent."""
        if intent not in self._intent_patterns:
            self._intent_patterns[intent] = []
        self._intent_patterns[intent].extend(patterns)
        logger.info(f"Added {len(patterns)} patterns for {intent}")


# Global default NLU
default_nlu: Optional[NLUEngine] = None


def init_nlu() -> NLUEngine:
    """Initialize global NLU engine."""
    global default_nlu
    default_nlu = NLUEngine()
    return default_nlu


def process_utterance(text: str, **kwargs) -> NLUResult:
    """Convenience function for NLU processing."""
    if default_nlu:
        return default_nlu.process(text, **kwargs)
    return NLUResult(
        intent=IntentType.UNKNOWN,
        intent_confidence=0.0,
        entities=[],
        slots={},
        raw_text=text
    )
