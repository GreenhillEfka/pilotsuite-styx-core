"""Voice Control Integration — Slice 16.

Voice command processing for PilotSuite Core.

Features:
- Voice command parsing (natural language)
- Intent recognition for home automation
- Context-aware voice responses
- Multi-language support (DE/EN)
- Voice feedback loop (confirmation, correction)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class VoiceIntentType(Enum):
    """Type of voice intent."""
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    DIM = "dim"
    BRIGHTEN = "brighten"
    SET_COLOR = "set_color"
    SET_TEMPERATURE = "set_temperature"
    SCENE_ACTIVATE = "scene_activate"
    STATUS_QUERY = "status_query"
    CLIMATE_SET = "climate_set"
    CLIMATE_UP = "climate_up"
    CLIMATE_DOWN = "climate_down"
    COVER_OPEN = "cover_open"
    COVER_CLOSE = "cover_close"
    COVER_POSITION = "cover_position"
    UNKNOWN = "unknown"
    NEGATED = "negated"  # Explicit negation handling


class Language(Enum):
    """Supported languages."""
    DE = "de"
    EN = "en"


@dataclass
class VoiceCommand:
    """Parsed voice command."""
    command_id: str
    intent_type: VoiceIntentType
    language: Language
    raw_text: str
    zone_id: Optional[str] = None
    module_id: Optional[str] = None
    entity_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "intent_type": self.intent_type.value,
            "language": self.language.value,
            "raw_text": self.raw_text,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "entity_id": self.entity_id,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class VoiceResponse:
    """Voice response to user."""
    response_id: str
    command_id: str
    text_de: str  # German response
    text_en: str  # English response
    action_taken: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "command_id": self.command_id,
            "text_de": self.text_de,
            "text_en": self.text_en,
            "action_taken": self.action_taken,
            "requires_confirmation": self.requires_confirmation,
            "timestamp": self.timestamp,
        }


class VoiceControlEngine:
    """Voice command processing engine."""
    
    def __init__(self, default_language: Language = Language.DE):
        self._default_language = default_language
        self._command_counter = 0
        self._response_counter = 0
        self._command_history: List[VoiceCommand] = []
        self._responses: Dict[str, VoiceResponse] = {}
        
        # Intent patterns (German) - expanded with typos and variations
        self._de_patterns = {
            VoiceIntentType.TURN_ON: [
                r"mach.*an",
                r"schalt.*ein",
                r"licht.*an",
                r"anmachen",
                r"anmachn",  # Common typo
                r"einschalten",
                r"eischalten",  # Common typo
                r"anschalten",
                r"lampe.*an",
                r"beleuchtung.*an",
                r"leuchte.*an",
            ],
            VoiceIntentType.TURN_OFF: [
                r"mach.*aus",
                r"schalt.*aus",
                r"licht.*aus",
                r"ausmachen",
                r"ausschalten",
                r"auschalten",  # Common typo
                r"lampe.*aus",
                r"beleuchtung.*aus",
            ],
            VoiceIntentType.DIM: [
                r"dimmer",
                r"dunkler",
                r"weniger licht",
                r"leiser",
                r"runter",
            ],
            VoiceIntentType.BRIGHTEN: [
                r"heller",
                r"mehr licht",
                r"rauf",
                r"höher",
            ],
            VoiceIntentType.STATUS_QUERY: [
                r"ist.*an",
                r"zustand",
                r"status",
                r"wie ist.*",
                r"status.*abfrage",
            ],
            VoiceIntentType.CLIMATE_SET: [
                r"heizung.*\d{1,2}\s*grad",
                r"temperatur.*\d{1,2}\s*grad",
                r"auf\s*\d{1,2}\s*grad",
                r"heiz.*\d{1,2}\s*grad",
                r"wärme.*\d{1,2}\s*grad",
            ],
            VoiceIntentType.SET_TEMPERATURE: [
                r"stelle.*\d{1,2}\s*grad",
                r"setze.*\d{1,2}\s*grad",
                r"stell.*\d{1,2}\s*grad",  # Common typo
            ],
            VoiceIntentType.NEGATED: [
                r"nicht.*an",
                r"nicht.*aus",
                r"bitte nicht",
                r"nicht.*machen",
            ],
        }
        
        # Intent patterns (English) - expanded with variations
        self._en_patterns = {
            VoiceIntentType.TURN_ON: [
                r"turn.*on",
                r"switch.*on",
                r"light.*on",
                r"power.*on",
                r"lamp.*on",
                r"lights.*on",
            ],
            VoiceIntentType.TURN_OFF: [
                r"turn.*off",
                r"switch.*off",
                r"light.*off",
                r"power.*off",
                r"lamp.*off",
            ],
            VoiceIntentType.DIM: [
                r"dim",
                r"darker",
                r"less light",
                r"down",
            ],
            VoiceIntentType.BRIGHTEN: [
                r"brighter",
                r"more light",
                r"up",
            ],
            VoiceIntentType.STATUS_QUERY: [
                r"is.*on",
                r"status",
                r"state",
                r"what is.*",
            ],
            VoiceIntentType.CLIMATE_SET: [
                r"heat.*\d{1,2}\s*(?:degree|°)",
                r"temperature.*\d{1,2}\s*(?:degree|°)",
                r"to\s*\d{1,2}\s*(?:degree|°)",
            ],
            VoiceIntentType.SET_TEMPERATURE: [
                r"set.*\d{1,2}\s*(?:degree|°)",
            ],
            VoiceIntentType.NEGATED: [
                r"don't.*turn",
                r"do not.*turn",
                r"not.*on",
                r"not.*off",
            ],
        }
        
        # Zone/entity recognition patterns - expanded aliases
        self._zone_patterns = {
            "zone_living_room": [r"wohnzimmer", r"wohn.*raum", r"wohnbereich", r"living.*room", r"lounge"],
            "zone_kitchen": [r"küche", r"koch", r"kitchen", r"cooking"],
            "zone_bedroom": [r"schlafzimmer", r"schlaf.*raum", r"bedroom", r"sleeping"],
            "zone_bathroom": [r"badezimmer", r"bad", r"bathroom", r"bath"],
            "zone_hallway": [r"flur", r"diele", r"hallway", r"corridor", r"entry"],
            "zone_office": [r"büro", r"office", r"work", r"workspace", r"arbeitszimmer"],
        }
    
    def process_voice_command(self, text: str, language: Optional[Language] = None) -> VoiceCommand:
        """Process a voice command and return parsed intent.
        
        Handles edge cases:
        - Empty commands
        - Very long commands (truncated for parsing)
        - Special characters and Unicode
        - Noise/filler words
        """
        if language is None:
            language = self._default_language
        
        self._command_counter += 1
        
        # Handle empty command
        if not text or not text.strip():
            command = VoiceCommand(
                command_id=f"voice_{self._command_counter}",
                intent_type=VoiceIntentType.UNKNOWN,
                language=language,
                raw_text=text,
                confidence=0.3,  # Low confidence for empty
            )
            self._command_history.append(command)
            return command
        
        # Normalize text: strip, lowercase, handle special chars
        text_clean = text.strip().lower()
        
        # Truncate very long commands for parsing (keep full text in raw_text)
        text_parse = text_clean[:500] if len(text_clean) > 500 else text_clean
        
        # Detect intent
        intent_type = self._detect_intent(text_parse, language)
        
        # Detect zone
        zone_id = self._detect_zone(text_parse)
        
        # Detect parameters (brightness, color, temperature, etc.)
        parameters = self._detect_parameters(text_parse, intent_type)
        
        command = VoiceCommand(
            command_id=f"voice_{self._command_counter}",
            intent_type=intent_type,
            language=language,
            raw_text=text,
            zone_id=zone_id,
            parameters=parameters,
            confidence=self._calculate_confidence(intent_type, zone_id, text_parse),
        )
        
        self._command_history.append(command)
        
        # Keep last 100 commands
        if len(self._command_history) > 100:
            self._command_history = self._command_history[-100:]
        
        return command
    
    def _detect_intent(self, text: str, language: Language) -> VoiceIntentType:
        """Detect intent from text with noise word handling.
        
        Strips common filler/noise words before pattern matching.
        """
        # Remove common noise/filler words for better matching
        noise_words_de = ["äh", "ähm", "also", "bitte", "vielleicht", "eigentlich", "mal", "kurz", "hey", "ja", "nein"]
        noise_words_en = ["um", "uh", "so", "please", "maybe", "actually", "like", "just", "hey", "yeah", "nope"]
        
        noise_words = noise_words_de if language == Language.DE else noise_words_en
        text_clean = text
        for noise in noise_words:
            text_clean = re.sub(r'\b' + noise + r'\b', '', text_clean, flags=re.IGNORECASE)
        text_clean = re.sub(r'\s+', ' ', text_clean).strip()
        
        patterns = self._de_patterns if language == Language.DE else self._en_patterns
        
        # Check for negation first
        negation_patterns = patterns.get(VoiceIntentType.NEGATED, [])
        for pattern in negation_patterns:
            if re.search(pattern, text):
                return VoiceIntentType.NEGATED
        
        for intent_type, pattern_list in patterns.items():
            if intent_type == VoiceIntentType.NEGATED:
                continue
            for pattern in pattern_list:
                if re.search(pattern, text_clean):
                    return intent_type
        
        return VoiceIntentType.UNKNOWN
    
    def _detect_zone(self, text: str) -> Optional[str]:
        """Detect zone from text."""
        for zone_id, patterns in self._zone_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return zone_id
        return None
    
    def _detect_parameters(self, text: str, intent_type: VoiceIntentType) -> Dict[str, Any]:
        """Detect parameters from text."""
        params = {}
        
        # Brightness percentage
        brightness_match = re.search(r"(\d{1,3})\s*(?:%|prozent|percent)", text)
        if brightness_match and intent_type in (VoiceIntentType.DIM, VoiceIntentType.BRIGHTEN):
            params["brightness"] = int(brightness_match.group(1))
        
        # Color
        color_match = re.search(r"(rot|grün|blau|gelb|weiß|warm|kalt|red|green|blue|yellow|white|warm|cold)", text)
        if color_match and intent_type == VoiceIntentType.SET_COLOR:
            params["color"] = color_match.group(1)
        
        # Temperature
        temp_match = re.search(r"(\d{1,2})\s*(?:grad|degree|°)", text)
        if temp_match and intent_type in (VoiceIntentType.CLIMATE_SET, VoiceIntentType.SET_TEMPERATURE):
            params["temperature"] = int(temp_match.group(1))
        
        # Cover position
        position_match = re.search(r"(\d{1,3})\s*(?:%|prozent|percent)", text)
        if position_match and intent_type == VoiceIntentType.COVER_POSITION:
            params["position"] = int(position_match.group(1))
        
        return params
    
    def _calculate_confidence(self, intent_type: VoiceIntentType, zone_id: Optional[str], text: str) -> float:
        """Calculate confidence score for command.
        
        Factors:
        - Known intent vs unknown
        - Zone detection
        - Text length (very short = lower confidence)
        - Presence of action verbs
        """
        confidence = 0.5  # Base confidence
        
        # Higher confidence if intent is known
        if intent_type != VoiceIntentType.UNKNOWN:
            confidence += 0.3
        
        # Higher confidence if zone is detected
        if zone_id:
            confidence += 0.15
        
        # Lower confidence for very short text
        if len(text.split()) <= 1:
            confidence -= 0.2
        
        # Higher confidence for longer, more specific commands
        if len(text.split()) >= 4:
            confidence += 0.05
        
        return min(max(confidence, 0.0), 1.0)
    
    def generate_response(self, command: VoiceCommand) -> VoiceResponse:
        """Generate voice response for a command."""
        self._response_counter += 1
        
        # Response templates
        responses_de = {
            VoiceIntentType.TURN_ON: f"OK, ich schalte ein{f' in {command.zone_id}' if command.zone_id else ''}.",
            VoiceIntentType.TURN_OFF: f"OK, ich schalte aus{f' in {command.zone_id}' if command.zone_id else ''}.",
            VoiceIntentType.DIM: "OK, ich dimme das Licht.",
            VoiceIntentType.BRIGHTEN: "OK, ich mache heller.",
            VoiceIntentType.STATUS_QUERY: f"Der Status ist{f' in {command.zone_id}' if command.zone_id else ''}...",
            VoiceIntentType.UNKNOWN: "Ich habe das nicht verstanden. Können Sie das wiederholen?",
        }
        
        responses_en = {
            VoiceIntentType.TURN_ON: f"OK, turning on{f' in {command.zone_id}' if command.zone_id else ''}.",
            VoiceIntentType.TURN_OFF: f"OK, turning off{f' in {command.zone_id}' if command.zone_id else ''}.",
            VoiceIntentType.DIM: "OK, dimming the lights.",
            VoiceIntentType.BRIGHTEN: "OK, making it brighter.",
            VoiceIntentType.STATUS_QUERY: f"The status is{f' in {command.zone_id}' if command.zone_id else ''}...",
            VoiceIntentType.UNKNOWN: "I didn't understand that. Could you please repeat?",
        }
        
        response = VoiceResponse(
            response_id=f"resp_{self._response_counter}",
            command_id=command.command_id,
            text_de=responses_de.get(command.intent_type, responses_de[VoiceIntentType.UNKNOWN]),
            text_en=responses_en.get(command.intent_type, responses_en[VoiceIntentType.UNKNOWN]),
            action_taken={"intent": command.intent_type.value, "zone": command.zone_id},
            requires_confirmation=command.confidence < 0.7,
        )
        
        self._responses[response.response_id] = response
        return response
    
    def get_command_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent command history."""
        commands = self._command_history[-limit:]
        return [c.to_dict() for c in commands]
    
    def get_responses(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent responses."""
        responses = list(self._responses.values())[-limit:]
        return [r.to_dict() for r in responses]
    
    def set_language(self, language: Language) -> None:
        """Set default language."""
        self._default_language = language


def create_voice_control_engine(language: Language = Language.DE) -> VoiceControlEngine:
    """Factory function to create voice control engine."""
    return VoiceControlEngine(default_language=language)
