"""P1-006 compatibility NLU surface for the shipped add-on voice package."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

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
    turn_context: list[str] = None  # Previous utterance snippets (F3.3)

    def __post_init__(self):
        if self.turn_context is None:
            self.turn_context = []


class NLUEngine:
    """Natural language understanding engine."""

    MAX_TURN_CONTEXT: int = 5  # F3.3 — keep last 5 turns for context

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
                r"mach\s+(.+)\s+h[öo]her",
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
        }  # close _intent_patterns dict

        self._entity_types = {
            "light": ["licht", "lampe", "light", "lights"],
            "thermostat": ["thermostat", "heizung", "temperature"],
            "cover": ["rollo", "vorhang", "blind", "cover"],
            "switch": ["schalter", "switch"],
        }  # F3.3 — entity type keywords
        self._recent_turns: list[str] = []  # F3.3 — rolling turn buffer

    def _push_turn(self, text: str) -> None:
        self._recent_turns.append(text)
        if len(self._recent_turns) > self.MAX_TURN_CONTEXT:
            self._recent_turns.pop(0)

    def get_turn_context(self) -> list[str]:
        return list(self._recent_turns)

    def process(self, text: str, language: str = "de") -> NLUResult:
        """Process utterance and extract intent plus entities."""
        del language
        text_lower = text.lower().strip()
        intent, confidence = self._match_intent(text_lower)
        entities = self._extract_entities(text_lower)
        slots = self._fill_slots(entities)
        self._push_turn(text)
        return NLUResult(
            intent=intent,
            intent_confidence=confidence,
            entities=entities,
            slots=slots,
            raw_text=text,
            turn_context=self.get_turn_context(),
        )

    def extract_intent(self, text: str, language: str = "de") -> Dict[str, Any]:
        """Compatibility helper expected by the integration smoke tests."""
        result = self.process(text, language=language)
        domain = result.slots.get("entity_type") or self._infer_domain(result.entities)
        return {
            "intent": result.intent.value,
            "action": result.intent.value,
            "domain": domain or "unknown",
            "confidence": result.intent_confidence,
            "slots": result.slots,
            "raw_text": result.raw_text,
            "turn_context": result.turn_context,
        }

    def _match_intent(self, text: str) -> Tuple[IntentType, float]:
        for intent_type, patterns in self._intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return intent_type, 0.9
        return IntentType.UNKNOWN, 0.3

    def _extract_entities(self, text: str) -> List[Entity]:
        entities: List[Entity] = []
        for entity_type, keywords in self._entity_types.items():
            for keyword in keywords:
                if keyword in text:
                    entities.append(
                        Entity(
                            name=keyword.rstrip("s"),
                            type=entity_type,
                            value=keyword.rstrip("s"),
                            confidence=0.8,
                        )
                    )
                    break

        for number in re.findall(r"\d+", text):
            entities.append(Entity(name="value", type="number", value=int(number), confidence=0.9))

        return entities

    def _fill_slots(self, entities: List[Entity]) -> Dict[str, Any]:
        slots: Dict[str, Any] = {}
        for entity in entities:
            if entity.type == "number":
                slots["value"] = entity.value
            elif entity.type in {"light", "thermostat", "cover", "switch"}:
                slots["entity_type"] = entity.type
                slots["entity_name"] = entity.name
        return slots

    @staticmethod
    def _infer_domain(entities: List[Entity]) -> Optional[str]:
        for entity in entities:
            if entity.type in {"light", "thermostat", "cover", "switch"}:
                return entity.type
        return None

    def add_training_data(self, intent: IntentType, patterns: List[str]):
        """Add training patterns for an intent."""
        if intent not in self._intent_patterns:
            self._intent_patterns[intent] = []
        self._intent_patterns[intent].extend(patterns)
        logger.info("Added %s patterns for %s", len(patterns), intent)


default_nlu: Optional[NLUEngine] = None


def init_nlu() -> NLUEngine:
    """Initialize global NLU engine."""
    global default_nlu
    default_nlu = NLUEngine()
    return default_nlu


def process_utterance(text: str, **kwargs: Any) -> NLUResult:
    """Convenience function for NLU processing."""
    if default_nlu:
        return default_nlu.process(text, **kwargs)
    return NLUResult(
        intent=IntentType.UNKNOWN,
        intent_confidence=0.0,
        entities=[],
        slots={},
        raw_text=text,
    )
