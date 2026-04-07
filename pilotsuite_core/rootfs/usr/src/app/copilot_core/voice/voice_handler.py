"""Voice Intent Handler for Home Assistant Voice Assistant.

Handles voice intents with context-aware responses, integrating mood, habitus,
and user preferences for personalized voice interactions.

Features:
- HA Voice Assistant Intent-Handling
- DE/EN Sprachunterstützung
- Integration mit Mood Engine und Habitus
- Kontextbewusste Antworten
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .context_builder import VoiceContextBuilder, VoiceContext
from ..mood.engine import MoodEngine, MoodState, MoodConfig
from ..habitus.service import HabitusService

_LOGGER = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Supported voice intent types."""
    
    # Control intents
    LIGHT_ON = "light_on"
    LIGHT_OFF = "light_off"
    LIGHT_DIM = "light_dim"
    LIGHT_BRIGHTEN = "light_brighten"
    LIGHT_COLOR = "light_color"
    
    CLIMATE_SET = "climate_set"
    CLIMATE_UP = "climate_up"
    CLIMATE_DOWN = "climate_down"
    
    MEDIA_PLAY = "media_play"
    MEDIA_PAUSE = "media_pause"
    MEDIA_STOP = "media_stop"
    MEDIA_NEXT = "media_next"
    MEDIA_PREVIOUS = "media_previous"
    MEDIA_VOLUME_UP = "media_volume_up"
    MEDIA_VOLUME_DOWN = "media_volume_down"
    
    SCENE_ACTIVATE = "scene_activate"
    
    # Query intents
    STATUS_QUERY = "status_query"
    WEATHER_QUERY = "weather_query"
    TIME_QUERY = "time_query"
    DATE_QUERY = "date_query"
    MOOD_QUERY = "mood_query"
    
    # Navigation intents
    NAVIGATE = "navigate"
    
    # Custom intents
    CUSTOM = "custom"
    UNKNOWN = "unknown"


@dataclass
class VoiceIntent:
    """Parsed voice intent."""
    
    intent_type: IntentType
    confidence: float
    slots: Dict[str, Any] = field(default_factory=dict)
    language: str = "de"
    raw_text: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "slots": self.slots,
            "language": self.language,
            "raw_text": self.raw_text,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VoiceResponse:
    """Voice response with TTS text and actions."""
    
    # TTS response text (DE or EN)
    tts_text: str
    
    # Actions to execute
    actions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Response metadata
    intent_type: Optional[IntentType] = None
    confidence: float = 0.0
    mood_context: Optional[str] = None
    language: str = "de"
    
    # Optional: proactive suggestions
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tts_text": self.tts_text,
            "actions": self.actions,
            "intent_type": self.intent_type.value if self.intent_type else None,
            "confidence": self.confidence,
            "mood_context": self.mood_context,
            "language": self.language,
            "suggestions": self.suggestions,
        }


class VoiceIntentHandler:
    """Handles voice intents with context-aware responses.
    
    Integration with:
    - Home Assistant Assist Pipeline
    - Mood Engine (for mood-based responses)
    - Habitus Service (for pattern-based suggestions)
    - User preferences (language, tone)
    """
    
    # Intent patterns (DE)
    DE_INTENT_PATTERNS = {
        IntentType.LIGHT_ON: [
            r"mach\s+das\s+licht\s+(an|ein)",
            r"licht\s+(an|ein)",
            r"schalt\s+(das\s+)?licht\s+(an|ein)",
            r"es\s+ist\s+(zu\s+)?dunkel",
            r"kannst\s+du\s+(das\s+)?licht\s+(an)?machen",
        ],
        IntentType.LIGHT_OFF: [
            r"mach\s+das\s+licht\s+aus",
            r"licht\s+aus",
            r"schalt\s+(das\s+)?licht\s+aus",
            r"es\s+ist\s+(zu\s+)?hell",
            r"kannst\s+du\s+(das\s+)?licht\s+ausmachen",
        ],
        IntentType.LIGHT_DIM: [
            r"dimm\s+(das\s+)?licht",
            r"mach\s+das\s+licht\s+(dunkler|gedimmt)",
            r"licht\s+(dunkler|runter)",
        ],
        IntentType.LIGHT_BRIGHTEN: [
            r"mach\s+das\s+licht\s+(heller|stärker)",
            r"licht\s+(heller|rauf)",
            r"mehr\s+licht",
        ],
        IntentType.CLIMATE_SET: [
            r"stell\s+(die\s+)?temperatur\s+(auf\s+)?(\d+)",
            r"temperatur\s+(\d+)\s+grad",
            r"heiz\s+(auf\s+)?(\d+)\s+grad",
        ],
        IntentType.MEDIA_PLAY: [
            r"spiel\s+(musik|etwas)",
            r"starte\s+musik",
            r"musik\s+(an|starten)",
            r"spiele\s+(von\s+)?(.+)",
        ],
        IntentType.MEDIA_PAUSE: [
            r"pause",
            r"musik\s+pause",
            r"unterbrich\s+(die\s+)?wiedergabe",
        ],
        IntentType.MEDIA_STOP: [
            r"stopp",
            r"musik\s+aus",
            r"beende\s+(die\s+)?wiedergabe",
        ],
        IntentType.STATUS_QUERY: [
            r"wie\s+ist\s+der\s+status",
            r"was\s+läuft",
            r"was\s+ist\s+(gerade\s+)?los",
            r"status",
        ],
        IntentType.MOOD_QUERY: [
            r"wie\s+ist\s+(die\s+)?stimmung",
            r"wie\s+ist\s+(der\s+)?mood",
            r"stimmungsbericht",
        ],
        IntentType.TIME_QUERY: [
            r"wie\s+viel\s+uhr\s+ist\s+es",
            r"wie\s+spät\s+ist\s+es",
            r"uhrzeit",
            r"zeit",
        ],
    }
    
    # Intent patterns (EN)
    EN_INTENT_PATTERNS = {
        IntentType.LIGHT_ON: [
            r"turn\s+(the\s+)?light\s+on",
            r"light\s+on",
            r"switch\s+(the\s+)?light\s+on",
            r"turn\s+on\s+(the\s+)?light",
            r"it's\s+(too\s+)?dark",
        ],
        IntentType.LIGHT_OFF: [
            r"turn\s+(the\s+)?light\s+off",
            r"light\s+off",
            r"switch\s+(the\s+)?light\s+off",
            r"turn\s+off\s+(the\s+)?light",
            r"it's\s+(too\s+)?bright",
        ],
        IntentType.LIGHT_DIM: [
            r"dim\s+(the\s+)?light",
            r"make\s+(the\s+)?light\s+darker",
        ],
        IntentType.LIGHT_BRIGHTEN: [
            r"make\s+(the\s+)?light\s+brighter",
            r"more\s+light",
        ],
        IntentType.CLIMATE_SET: [
            r"set\s+temperature\s+to\s+(\d+)",
            r"temperature\s+(\d+)\s+degrees",
            r"heat\s+to\s+(\d+)\s+degrees",
        ],
        IntentType.MEDIA_PLAY: [
            r"play\s+(music|something)",
            r"start\s+music",
            r"music\s+on",
            r"play\s+some\s+music",
            r"play\s+music",
        ],
        IntentType.MEDIA_PAUSE: [
            r"pause",
            r"pause\s+music",
        ],
        IntentType.MEDIA_STOP: [
            r"stop",
            r"stop\s+music",
            r"music\s+off",
        ],
        IntentType.STATUS_QUERY: [
            r"what's\s+the\s+status",
            r"what's\s+happening",
            r"status",
        ],
        IntentType.MOOD_QUERY: [
            r"how's\s+the\s+mood",
            r"what's\s+the\s+atmosphere",
        ],
        IntentType.TIME_QUERY: [
            r"what\s+time\s+is\s+it",
            r"time",
        ],
    }
    
    # Mood-based response templates (DE)
    DE_MOOD_RESPONSES = {
        MoodState.RELAX: {
            "greeting": "Entspannt",
            "tone": "ruhig",
            "acknowledgments": [
                "Alles klar, ich mache das.",
                "Gerne, entspann dich weiter.",
                "Mache ich gerne für dich.",
            ],
        },
        MoodState.FOCUS: {
            "greeting": "Fokussiert",
            "tone": "konzentriert",
            "acknowledgments": [
                "Erledigt.",
                "Wird gemacht.",
                "Kein Problem.",
            ],
        },
        MoodState.ACTIVE: {
            "greeting": "Aktiv",
            "tone": "energetisch",
            "acknowledgments": [
                "Los geht's!",
                "Mache ich sofort!",
                "Alles klar, packen wir's an!",
            ],
        },
        MoodState.NIGHT: {
            "greeting": "Gute Nacht",
            "tone": "leise",
            "acknowledgments": [
                "Gute Nacht.",
                "Schlaf gut.",
                "Ich mache das leise.",
            ],
        },
        MoodState.AWAY: {
            "greeting": "Abwesend",
            "tone": "neutral",
            "acknowledgments": [
                "Verstanden.",
                "Ich kümmere mich darum.",
                "Erledigt.",
            ],
        },
        MoodState.NEUTRAL: {
            "greeting": "Hallo",
            "tone": "freundlich",
            "acknowledgments": [
                "Alles klar.",
                "Mache ich.",
                "Gerne.",
            ],
        },
    }
    
    # Mood-based response templates (EN)
    EN_MOOD_RESPONSES = {
        MoodState.RELAX: {
            "greeting": "Relaxed",
            "tone": "calm",
            "acknowledgments": [
                "Sure thing, I'm on it.",
                "Happy to help, relax.",
                "Consider it done.",
            ],
        },
        MoodState.FOCUS: {
            "greeting": "Focused",
            "tone": "concise",
            "acknowledgments": [
                "Done.",
                "On it.",
                "No problem.",
            ],
        },
        MoodState.ACTIVE: {
            "greeting": "Active",
            "tone": "energetic",
            "acknowledgments": [
                "Let's go!",
                "Doing it now!",
                "Got it!",
            ],
        },
        MoodState.NIGHT: {
            "greeting": "Good night",
            "tone": "quiet",
            "acknowledgments": [
                "Good night.",
                "Sleep well.",
                "I'll keep it quiet.",
            ],
        },
        MoodState.AWAY: {
            "greeting": "Away",
            "tone": "neutral",
            "acknowledgments": [
                "Understood.",
                "I'll take care of it.",
                "Done.",
            ],
        },
        MoodState.NEUTRAL: {
            "greeting": "Hello",
            "tone": "friendly",
            "acknowledgments": [
                "Alright.",
                "Will do.",
                "Sure.",
            ],
        },
    }
    
    def __init__(
        self,
        mood_engine: Optional[MoodEngine] = None,
        habitus_service: Optional[HabitusService] = None,
        default_language: str = "de",
    ):
        """Initialize voice intent handler.
        
        Args:
            mood_engine: Mood engine for context-aware responses
            habitus_service: Habitus service for pattern-based suggestions
            default_language: Default language (de/en)
        """
        self.mood_engine = mood_engine
        self.habitus_service = habitus_service
        self.default_language = default_language
        self._context_builder = VoiceContextBuilder()
    
    def parse_intent(self, text: str, language: Optional[str] = None) -> VoiceIntent:
        """Parse voice text into structured intent.
        
        Args:
            text: Voice input text
            language: Language code (de/en), auto-detected if None
            
        Returns:
            Parsed VoiceIntent
        """
        language = language or self._detect_language(text)
        
        # Select pattern set based on language
        patterns = self.DE_INTENT_PATTERNS if language == "de" else self.EN_INTENT_PATTERNS
        
        best_match = None
        best_confidence = 0.0
        best_slots = {}
        
        text_lower = text.lower()
        
        for intent_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text_lower)
                if match:
                    # Extract slots from groups
                    slots = self._extract_slots(intent_type, match, text)
                    
                    # Calculate confidence based on match quality
                    confidence = self._calculate_confidence(match, text_lower)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = intent_type
                        best_slots = slots
        
        if best_match is None:
            return VoiceIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                language=language,
                raw_text=text,
            )
        
        return VoiceIntent(
            intent_type=best_match,
            confidence=best_confidence,
            slots=best_slots,
            language=language,
            raw_text=text,
        )
    
    def _detect_language(self, text: str) -> str:
        """Detect language from text (simple heuristic)."""
        # German indicators - common German words and commands
        de_indicators = [
            "das", "der", "die", "und", "ist", "es", "ich", "du",
            "mach", "licht", "aus", "an", "wie", "was", "gerade",
            "spiel", "musik", "bitte", "kannst", "du", "schalt",
            "stell", "temperatur", "grad", "heiz", "stimm",
        ]
        
        # English indicators - common English words and commands
        en_indicators = [
            "the", "and", "is", "it", "i", "you",
            "make", "light", "off", "on", "how", "what",
            "play", "music", "please", "can", "switch",
            "set", "temperature", "degrees", "heat",
        ]
        
        text_lower = text.lower()
        de_count = sum(1 for word in de_indicators if word in text_lower)
        en_count = sum(1 for word in en_indicators if word in text_lower)
        
        return "de" if de_count >= en_count else "en"
    
    def _extract_slots(
        self,
        intent_type: IntentType,
        match: re.Match,
        text: str,
    ) -> Dict[str, Any]:
        """Extract slots from regex match."""
        slots = {}
        groups = match.groups()
        
        if intent_type in (IntentType.CLIMATE_SET,):
            # Extract temperature value
            for group in groups:
                if group and group.isdigit():
                    slots["temperature"] = int(group)
                    break
        
        elif intent_type in (IntentType.MEDIA_PLAY,):
            # Extract media title/artist if present
            if len(groups) > 1 and groups[1]:
                slots["media_title"] = groups[1].strip()
        
        elif intent_type in (IntentType.LIGHT_DIM, IntentType.LIGHT_BRIGHTEN):
            # Extract brightness level if mentioned
            brightness_match = re.search(r"(\d+)\s*(%|prozent|percent)?", text)
            if brightness_match:
                slots["brightness"] = int(brightness_match.group(1))
        
        return slots
    
    def _calculate_confidence(self, match: re.Match, text: str) -> float:
        """Calculate confidence score for intent match."""
        # Base confidence from match span
        match_len = match.end() - match.start()
        text_len = len(text)
        
        # Higher confidence for longer matches relative to text
        base_confidence = min(1.0, match_len / max(10, text_len) * 2)
        
        # Boost for exact phrase matches
        if match.start() == 0 and match.end() == text_len:
            base_confidence = min(1.0, base_confidence + 0.3)
        
        return round(base_confidence, 2)
    
    def handle_intent(
        self,
        intent: VoiceIntent,
        context: Optional[VoiceContext] = None,
    ) -> VoiceResponse:
        """Handle parsed intent and generate response.
        
        Args:
            intent: Parsed voice intent
            context: Current voice context (mood, zone, etc.)
            
        Returns:
            VoiceResponse with TTS text and actions
        """
        # Build context if not provided
        if context is None:
            context = self._context_builder.build_context(
                mood_engine=self.mood_engine,
                habitus_service=self.habitus_service,
            )
        
        # Get mood-based response templates
        mood_state = context.mood_state if context.mood_state else MoodState.NEUTRAL
        templates = (
            self.DE_MOOD_RESPONSES if intent.language == "de" else self.EN_MOOD_RESPONSES
        )
        mood_template = templates.get(mood_state, templates[MoodState.NEUTRAL])
        
        # Handle intent based on type
        actions = []
        tts_text = ""
        suggestions = []
        
        if intent.intent_type == IntentType.UNKNOWN:
            tts_text = (
                "Ich habe dich nicht verstanden. Kannst du das bitte wiederholen?"
                if intent.language == "de"
                else "I didn't understand. Could you repeat that?"
            )
        
        elif intent.intent_type in (IntentType.LIGHT_ON, IntentType.LIGHT_OFF):
            actions, tts_text = self._handle_light(intent, context, mood_template)
        
        elif intent.intent_type in (IntentType.LIGHT_DIM, IntentType.LIGHT_BRIGHTEN):
            actions, tts_text = self._handle_light_dim(intent, context, mood_template)
        
        elif intent.intent_type == IntentType.CLIMATE_SET:
            actions, tts_text = self._handle_climate(intent, context, mood_template)
        
        elif intent.intent_type in (IntentType.MEDIA_PLAY, IntentType.MEDIA_PAUSE, IntentType.MEDIA_STOP):
            actions, tts_text = self._handle_media(intent, context, mood_template)
        
        elif intent.intent_type == IntentType.STATUS_QUERY:
            tts_text = self._handle_status_query(context, mood_template)
            suggestions = self._generate_suggestions(context)
        
        elif intent.intent_type == IntentType.MOOD_QUERY:
            tts_text = self._handle_mood_query(context, mood_template)
        
        elif intent.intent_type == IntentType.TIME_QUERY:
            tts_text = self._handle_time_query(intent.language)
        
        else:
            tts_text = (
                "Ich bearbeite deine Anfrage."
                if intent.language == "de"
                else "I'm processing your request."
            )
        
        # Add mood-based acknowledgment if we have actions
        if actions and not tts_text:
            ack = mood_template["acknowledgments"][0]
            tts_text = f"{mood_template['greeting']}. {ack}"
        
        return VoiceResponse(
            tts_text=tts_text,
            actions=actions,
            intent_type=intent.intent_type,
            confidence=intent.confidence,
            mood_context=mood_state.value,
            language=intent.language,
            suggestions=suggestions,
        )
    
    def _handle_light(
        self,
        intent: VoiceIntent,
        context: VoiceContext,
        mood_template: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Handle light on/off intents."""
        actions = []
        
        # Determine target entity
        zone = context.current_zone if context.current_zone != "unknown" else "wohnzimmer"
        light_entity = f"light.{zone}"
        
        if intent.intent_type == IntentType.LIGHT_ON:
            actions.append({
                "domain": "light",
                "service": "turn_on",
                "entity_id": light_entity,
            })
            ack = mood_template["acknowledgments"][0]
            tts_text = f"{mood_template['greeting']}. {ack} Licht ist an."
        
        else:  # LIGHT_OFF
            actions.append({
                "domain": "light",
                "service": "turn_off",
                "entity_id": light_entity,
            })
            ack = mood_template["acknowledgments"][0]
            tts_text = f"{mood_template['greeting']}. {ack} Licht ist aus."
        
        return actions, tts_text
    
    def _handle_light_dim(
        self,
        intent: VoiceIntent,
        context: VoiceContext,
        mood_template: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Handle light dim/brighten intents."""
        actions = []
        
        zone = context.current_zone if context.current_zone != "unknown" else "wohnzimmer"
        light_entity = f"light.{zone}"
        
        brightness = intent.slots.get("brightness", 50 if intent.intent_type == IntentType.LIGHT_DIM else 100)
        
        actions.append({
            "domain": "light",
            "service": "turn_on",
            "entity_id": light_entity,
            "service_data": {
                "brightness_pct": brightness,
            },
        })
        
        ack = mood_template["acknowledgments"][0]
        tts_text = f"{mood_template['greeting']}. {ack} Licht ist auf {brightness}%."
        
        return actions, tts_text
    
    def _handle_climate(
        self,
        intent: VoiceIntent,
        context: VoiceContext,
        mood_template: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Handle climate control intents."""
        actions = []
        
        temperature = intent.slots.get("temperature", 21)
        
        # Default climate entity
        climate_entity = "climate.wohnzimmer"
        
        actions.append({
            "domain": "climate",
            "service": "set_temperature",
            "entity_id": climate_entity,
            "service_data": {
                "temperature": temperature,
            },
        })
        
        ack = mood_template["acknowledgments"][0]
        tts_text = f"{mood_template['greeting']}. {ack} Temperatur ist auf {temperature}°C."
        
        return actions, tts_text
    
    def _handle_media(
        self,
        intent: VoiceIntent,
        context: VoiceContext,
        mood_template: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Handle media control intents."""
        actions = []
        
        media_entity = "media_player.wohnzimmer"
        
        if intent.intent_type == IntentType.MEDIA_PLAY:
            actions.append({
                "domain": "media_player",
                "service": "media_play",
                "entity_id": media_entity,
            })
            tts_text = f"{mood_template['greeting']}. Spiele Musik."
        
        elif intent.intent_type == IntentType.MEDIA_PAUSE:
            actions.append({
                "domain": "media_player",
                "service": "media_pause",
                "entity_id": media_entity,
            })
            tts_text = f"{mood_template['greeting']}. Pause."
        
        else:  # MEDIA_STOP
            actions.append({
                "domain": "media_player",
                "service": "media_stop",
                "entity_id": media_entity,
            })
            tts_text = f"{mood_template['greeting']}. Stopp."
        
        return actions, tts_text
    
    def _handle_status_query(
        self,
        context: VoiceContext,
        mood_template: Dict[str, Any],
    ) -> str:
        """Handle status query intent."""
        parts = [f"{mood_template['greeting']}."]
        
        # Add mood info
        if context.mood_state:
            parts.append(f"Stimmung: {context.mood_state.value}.")
        
        # Add zone info
        if context.current_zone != "unknown":
            parts.append(f"Zone: {context.current_zone}.")
        
        # Add active devices
        if context.active_devices:
            parts.append(f"Aktive Geräte: {', '.join(context.active_devices[:3])}.")
        
        return " ".join(parts)
    
    def _handle_mood_query(
        self,
        context: VoiceContext,
        mood_template: Dict[str, Any],
    ) -> str:
        """Handle mood query intent."""
        if context.mood_state:
            confidence_pct = int(context.mood_confidence * 100)
            return (
                f"{mood_template['greeting']}. Die Stimmung ist "
                f"{context.mood_state.value} ({confidence_pct}% Sicherheit)."
            )
        return "Ich habe keine Stimmungsdaten."
    
    def _handle_time_query(self, language: str) -> str:
        """Handle time query intent."""
        now = datetime.now(timezone.utc)
        time_str = now.strftime("%H:%M")
        
        if language == "de":
            return f"Es ist {time_str} Uhr."
        else:
            return f"It's {time_str}."
    
    def _generate_suggestions(self, context: VoiceContext) -> List[str]:
        """Generate proactive suggestions based on context."""
        suggestions = []
        
        # Use habitus patterns if available
        if self.habitus_service and context.current_zone != "unknown":
            try:
                # Get recent patterns for this zone
                patterns = self.habitus_service.list_recent_patterns(limit=3)
                for pattern in patterns[:2]:
                    if pattern.get("metadata", {}).get("zone_filter") == context.current_zone:
                        # Convert pattern to suggestion
                        antecedent = pattern.get("metadata", {}).get("antecedent", {})
                        if antecedent:
                            suggestions.append(f"Basierend auf Mustern: {antecedent.get('full', '')}")
            except Exception as e:
                _LOGGER.debug("Failed to generate habitus suggestions: %s", e)
        
        # Mood-based suggestions
        if context.mood_state == MoodState.RELAX:
            suggestions.append("Möchtest du eine Entspannungs-Playlist?")
        elif context.mood_state == MoodState.FOCUS:
            suggestions.append("Soll ich Ablenkungen minimieren?")
        elif context.mood_state == MoodState.NIGHT:
            suggestions.append("Soll ich alle Lichter ausschalten?")
        
        return suggestions[:3]  # Limit to 3 suggestions
