"""Natural Language Interface — Intent Recognition, Entity Extraction, Multi-Language."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import re

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Supported intent types."""
    LIGHT_CONTROL = "light_control"
    CLIMATE_CONTROL = "climate_control"
    SCENE_ACTIVATE = "scene_activate"
    QUERY_STATUS = "query_status"
    AUTOMATION_CREATE = "automation_create"
    SCHEDULE_EVENT = "schedule_event"
    MEDIA_CONTROL = "media_control"
    SECURITY_COMMAND = "security_command"
    GENERAL_QUERY = "general_query"


@dataclass
class Entity:
    """Extracted entity from natural language."""
    entity_type: str
    value: str
    confidence: float
    unit: Optional[str] = None


@dataclass
class NLUResult:
    """Natural language understanding result."""
    intent: IntentType
    confidence: float
    entities: List[Entity] = field(default_factory=list)
    slots: Dict[str, Any] = field(default_factory=dict)
    language: str = "de"
    raw_text: str = ""


class NaturalLanguageInterface:
    """Natural language interface for voice and text commands."""

    def __init__(self):
        self._intent_patterns: Dict[IntentType, List[str]] = {}
        self._entity_extractors: Dict[str, callable] = {}
        self._supported_languages: List[str] = ["de", "en"]
        self._register_default_patterns()

    def _register_default_patterns(self):
        """Register default intent patterns for German and English."""
        self._intent_patterns = {
            IntentType.LIGHT_CONTROL: [
                r"(mach|schalte|stelle) (das )?licht (an|aus)",
                r"(light|turn) (the )?light (on|off)",
                r"(dimme|dimm) (das )?licht (auf|to) (\d+)",
                r"(change|set) (the )?(brightness|color)",
            ],
            IntentType.CLIMATE_CONTROL: [
                r"(stelle|setze) (die )?(heizung|temperatur) (auf|to) (\d+)",
                r"(set|adjust) (the )?(temperature|thermostat|heat) (to)? (\d+)",
                r"(mach|make) es (wärmer|warmer|kälter|colder)",
            ],
            IntentType.SCENE_ACTIVATE: [
                r"(aktiviere|activate) (die )?szene (|scene )?(\w+)",
                r"(start|begin) (the )?(\w+) (mode|scene)",
            ],
            IntentType.QUERY_STATUS: [
                r"(wie|what) (ist|'s) (der|the) (status|zustand)",
                r"(ist|is) (das|the) licht (an|on)",
                r"(wie|what) (ist|'s) (die|the) (temperatur|temperature)",
            ],
            IntentType.MEDIA_CONTROL: [
                r"(spiele|play) (musik|music)",
                r"(pause|stop|skip)",
                r"(lauter|leiser|louder|quieter)",
            ],
            IntentType.SECURITY_COMMAND: [
                r"(scharf|arm) (den|the) (alarm|alarmanlage)",
                r"(deaktiviere|disarm) (den|the) alarm",
                r"(schließe|lock) (die|the) (tür|door)",
            ],
        }

    def parse(self, text: str, language: str = "de") -> NLUResult:
        """Parse natural language text and extract intent."""
        text_lower = text.lower().strip()
        
        # Detect language
        detected_lang = self._detect_language(text)
        
        # Find matching intent
        best_intent = None
        best_confidence = 0.0
        
        for intent_type, patterns in self._intent_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    confidence = 0.9  # Base confidence for pattern match
                    # Boost confidence for exact matches
                    if match.group(0) == text_lower:
                        confidence = 0.95
                    
                    if confidence > best_confidence:
                        best_intent = intent_type
                        best_confidence = confidence
        
        # Default to general query if no match
        if not best_intent:
            best_intent = IntentType.GENERAL_QUERY
            best_confidence = 0.5
        
        # Extract entities
        entities = self._extract_entities(text, best_intent)
        
        # Extract slots
        slots = self._extract_slots(text, best_intent)
        
        result = NLUResult(
            intent=best_intent,
            confidence=best_confidence,
            entities=entities,
            slots=slots,
            language=detected_lang,
            raw_text=text,
        )
        
        logger.info(f"Parsed: '{text}' -> {best_intent.value} ({best_confidence:.2f})")
        return result

    def _detect_language(self, text: str) -> str:
        """Detect language of input text."""
        # Simple heuristic based on common words
        german_words = ["der", "die", "das", "und", "ist", "nicht", "auf", "an", "aus", "mach"]
        english_words = ["the", "and", "is", "not", "on", "off", "turn", "make", "set"]
        
        text_lower = text.lower()
        de_count = sum(1 for w in german_words if w in text_lower)
        en_count = sum(1 for w in english_words if w in text_lower)
        
        return "de" if de_count >= en_count else "en"

    def _extract_entities(self, text: str, intent: IntentType) -> List[Entity]:
        """Extract entities from text."""
        entities = []
        
        # Extract room/zone
        rooms = {
            "wohnzimmer": "living_room", "küche": "kitchen", "schlafzimmer": "bedroom",
            "bad": "bathroom", "flur": "hallway", "büro": "office",
            "living room": "living_room", "kitchen": "kitchen", "bedroom": "bedroom",
            "bathroom": "bathroom", "hallway": "hallway", "office": "office",
        }
        
        for room_de, room_en in rooms.items():
            if room_de in text.lower() or room_en in text.lower():
                entities.append(Entity(
                    entity_type="room",
                    value=room_en,
                    confidence=0.9,
                ))
        
        # Extract temperature
        temp_match = re.search(r"(\d+)[,\s°]*(grad|degree|c|°c)?", text.lower())
        if temp_match:
            entities.append(Entity(
                entity_type="temperature",
                value=temp_match.group(1),
                confidence=0.95,
                unit="celsius",
            ))
        
        # Extract brightness
        bright_match = re.search(r"(auf|to)\s*(\d+)\s*(%|percent)?", text.lower())
        if bright_match:
            entities.append(Entity(
                entity_type="brightness",
                value=bright_match.group(2),
                confidence=0.9,
                unit="percent",
            ))
        
        # Extract color
        colors = ["rot", "blau", "grün", "gelb", "weiß", "warm", "kalt",
                  "red", "blue", "green", "yellow", "white", "warm", "cold"]
        for color in colors:
            if color in text.lower():
                entities.append(Entity(
                    entity_type="color",
                    value=color,
                    confidence=0.85,
                ))
                break
        
        return entities

    def _extract_slots(self, text: str, intent: IntentType) -> Dict[str, Any]:
        """Extract slots for intent fulfillment."""
        slots = {}
        
        if intent == IntentType.LIGHT_CONTROL:
            if "an" in text.lower() or "on" in text.lower():
                slots["state"] = "on"
            elif "aus" in text.lower() or "off" in text.lower():
                slots["state"] = "off"
        
        elif intent == IntentType.CLIMATE_CONTROL:
            temp_match = re.search(r"(\d+)", text)
            if temp_match:
                slots["temperature"] = int(temp_match.group(1))
        
        elif intent == IntentType.MEDIA_CONTROL:
            if "spiel" in text.lower() or "play" in text.lower():
                slots["action"] = "play"
            elif "pause" in text.lower():
                slots["action"] = "pause"
            elif "stop" in text.lower():
                slots["action"] = "stop"
        
        return slots

    def generate_response(self, nlu_result: NLUResult, execution_result: Optional[Dict] = None) -> str:
        """Generate natural language response."""
        intent = nlu_result.intent
        
        responses = {
            IntentType.LIGHT_CONTROL: {
                "success": ["Licht wurde geschaltet", "Light has been switched", "Erledigt"],
                "failed": ["Licht konnte nicht geschaltet werden", "Failed to control light"],
            },
            IntentType.CLIMATE_CONTROL: {
                "success": ["Temperatur wurde eingestellt", "Temperature set", "Wird erledigt"],
                "failed": ["Temperatur konnte nicht eingestellt werden", "Failed to set temperature"],
            },
            IntentType.SCENE_ACTIVATE: {
                "success": ["Szene aktiviert", "Scene activated", "Szene läuft"],
                "failed": ["Szene konnte nicht aktiviert werden", "Failed to activate scene"],
            },
            IntentType.QUERY_STATUS: {
                "success": ["Hier ist der Status", "Here's the status", "Aktuell ist"],
                "failed": ["Status konnte nicht abgerufen werden", "Failed to get status"],
            },
        }
        
        response_set = responses.get(intent, responses[IntentType.GENERAL_QUERY])
        
        if execution_result and execution_result.get("success"):
            return response_set["success"][0] if nlu_result.language == "de" else response_set["success"][1]
        else:
            return response_set["failed"][0] if nlu_result.language == "de" else response_set["failed"][1]

    def add_training_data(self, intent: IntentType, patterns: List[str]):
        """Add training patterns for an intent."""
        if intent not in self._intent_patterns:
            self._intent_patterns[intent] = []
        self._intent_patterns[intent].extend(patterns)
        logger.info(f"Added {len(patterns)} patterns for {intent.value}")

    def get_supported_intents(self) -> List[IntentType]:
        """Get list of supported intents."""
        return list(self._intent_patterns.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get NLU statistics."""
        pattern_count = sum(len(patterns) for patterns in self._intent_patterns.values())
        return {
            "supported_intents": len(self._intent_patterns),
            "total_patterns": pattern_count,
            "supported_languages": self._supported_languages,
        }


# Global default NLU interface
default_nlu: Optional[NaturalLanguageInterface] = None


def init_natural_language_interface() -> NaturalLanguageInterface:
    """Initialize global NLU interface."""
    global default_nlu
    default_nlu = NaturalLanguageInterface()
    return default_nlu
