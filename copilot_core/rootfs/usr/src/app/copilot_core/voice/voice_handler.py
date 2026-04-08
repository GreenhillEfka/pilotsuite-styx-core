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

from .confidence_router import ConfidenceRouter, RoutingDecision
from .context_builder import VoiceContextBuilder, VoiceContext
from .intent_parser import IntentParser
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
    missing_slots: List[str] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_prompt: Optional[str] = None
    suggested_intents: List[str] = field(default_factory=list)
    route: Optional[str] = None
    route_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "slots": self.slots,
            "language": self.language,
            "raw_text": self.raw_text,
            "missing_slots": self.missing_slots,
            "clarification_needed": self.clarification_needed,
            "clarification_prompt": self.clarification_prompt,
            "suggested_intents": self.suggested_intents,
            "route": self.route,
            "route_reason": self.route_reason,
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
    clarification_needed: bool = False
    missing_slots: List[str] = field(default_factory=list)
    route: Optional[str] = None
    route_reason: Optional[str] = None
    
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
            "clarification_needed": self.clarification_needed,
            "missing_slots": self.missing_slots,
            "route": self.route,
            "route_reason": self.route_reason,
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
        self._intent_parser = IntentParser()
        self._confidence_router = ConfidenceRouter()
    
    def parse_intent(self, text: str, language: Optional[str] = None) -> VoiceIntent:
        """Parse voice text into structured intent.
        
        Args:
            text: Voice input text
            language: Language code (de/en), auto-detected if None
            
        Returns:
            Parsed VoiceIntent
        """
        language = language or self._detect_language(text)

        if language == "de":
            parsed = self._intent_parser.parse(text)
            routing = self._confidence_router.route(parsed)
            mapped_intent = self._map_parsed_intent(parsed.intent)
            suggested_intents = routing.suggested_intents or parsed.suggested_intents

            if mapped_intent is not None:
                return VoiceIntent(
                    intent_type=mapped_intent,
                    confidence=parsed.confidence,
                    slots=self._map_parsed_slots(parsed.intent, parsed.slots),
                    language=language,
                    raw_text=text,
                    missing_slots=list(parsed.missing_slots),
                    clarification_needed=routing.decision == RoutingDecision.CLARIFY,
                    clarification_prompt=routing.clarification_prompt,
                    suggested_intents=suggested_intents,
                    route=routing.processing_tier.value,
                    route_reason=routing.reason,
                )

            return VoiceIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=parsed.confidence,
                language=language,
                raw_text=text,
                suggested_intents=suggested_intents,
                route=routing.processing_tier.value,
                route_reason=routing.reason,
            )

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
                route="tier3_llm",
                route_reason="unknown_intent",
            )

        route, route_reason, clarification_needed = self._legacy_route_from_confidence(best_confidence)
        clarification_prompt = None
        if clarification_needed:
            clarification_prompt = (
                "Kannst du das bitte genauer sagen?"
                if language == "de"
                else "Could you clarify that a bit more?"
            )
        
        return VoiceIntent(
            intent_type=best_match,
            confidence=best_confidence,
            slots=best_slots,
            language=language,
            raw_text=text,
            clarification_needed=clarification_needed,
            clarification_prompt=clarification_prompt,
            route=route,
            route_reason=route_reason,
        )

    def _map_parsed_intent(self, parsed_intent: str) -> Optional[IntentType]:
        """Map task-2 intent ids to legacy voice handler enums."""
        mapping = {
            "light.turn_on": IntentType.LIGHT_ON,
            "light.turn_off": IntentType.LIGHT_OFF,
            "light.set_brightness": IntentType.LIGHT_DIM,
            "climate.set_temperature": IntentType.CLIMATE_SET,
            "scene.activate": IntentType.SCENE_ACTIVATE,
        }
        return mapping.get(parsed_intent)

    def _map_parsed_slots(self, parsed_intent: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Translate new parser slots to existing handler slot names."""
        mapped = dict(slots)
        if parsed_intent == "climate.set_temperature" and "target_temp" in mapped:
            mapped["temperature"] = mapped.pop("target_temp")
        return mapped
    
    def _legacy_route_from_confidence(self, confidence: float) -> Tuple[str, str, bool]:
        """Route legacy non-German matches using the same approved thresholds."""
        if confidence >= self._confidence_router.DIRECT_THRESHOLD:
            return "tier1_regex", "high_confidence", False
        if confidence >= self._confidence_router.CLARIFY_THRESHOLD:
            return "tier2_ml", "medium_confidence", True
        return "tier3_llm", "low_confidence", False

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

        self._hydrate_missing_slots_from_context(intent, context)
        
        # Get mood-based response templates
        mood_state = context.mood_state if context.mood_state else MoodState.NEUTRAL
        templates = (
            self.DE_MOOD_RESPONSES if intent.language == "de" else self.EN_MOOD_RESPONSES
        )
        mood_template = templates.get(mood_state, templates[MoodState.NEUTRAL])
        
        # Handle intent based on type
        actions = []
        tts_text = ""
        suggestions = list(intent.suggested_intents)

        if intent.clarification_needed:
            return VoiceResponse(
                tts_text=intent.clarification_prompt or (
                    "Kannst du das bitte genauer sagen?"
                    if intent.language == "de"
                    else "Could you clarify that a bit more?"
                ),
                actions=[],
                intent_type=intent.intent_type,
                confidence=intent.confidence,
                mood_context=str(mood_state.value) if hasattr(mood_state, "value") else str(mood_state),
                language=intent.language,
                clarification_needed=True,
                missing_slots=list(intent.missing_slots),
                route=intent.route,
                route_reason=intent.route_reason,
                suggestions=suggestions,
            )
        
        if intent.route == "tier3_llm" or intent.intent_type == IntentType.UNKNOWN:
            tts_text = (
                "Ich bin mir noch nicht sicher. Sag es bitte noch einmal einfacher, zum Beispiel: "
                + ", ".join(self._suggest_examples(intent.language, suggestions))
                if intent.language == "de"
                else "I'm not confident yet. Please try again more directly, for example: "
                + ", ".join(self._suggest_examples(intent.language, suggestions))
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
            clarification_needed=False,
            missing_slots=list(intent.missing_slots),
            route=intent.route,
            route_reason=intent.route_reason,
            suggestions=suggestions,
        )

    def _hydrate_missing_slots_from_context(self, intent: VoiceIntent, context: VoiceContext) -> None:
        """Use zone context to resolve common missing slots before clarifying."""
        if "room" not in intent.missing_slots:
            return

        zone_name = context.zone_name or ""
        if not zone_name or zone_name == "unknown":
            return

        intent.slots.setdefault("room", zone_name)
        intent.missing_slots = [slot for slot in intent.missing_slots if slot != "room"]
        if not intent.missing_slots:
            intent.clarification_needed = False
            intent.clarification_prompt = None
            intent.confidence = min(0.92, round(intent.confidence + 0.12, 2))
            if intent.route == "tier2_ml":
                intent.route = "tier1_regex"
                intent.route_reason = "context_resolved_slot"

    def _resolve_target_zone(self, intent: VoiceIntent, context: VoiceContext, default: str = "wohnzimmer") -> str:
        """Resolve room slot first, then fall back to context/default."""
        room = intent.slots.get("room")
        if room:
            return str(room).replace(" ", "_")
        if context.zone_name and context.zone_name != "unknown":
            return str(context.zone_name).replace(" ", "_")
        return default

    def _suggest_examples(self, language: str, suggestions: List[str]) -> List[str]:
        """Map intent suggestions to short example utterances."""
        example_map = {
            "light.turn_on": "Mach das Licht im Wohnzimmer an" if language == "de" else "Turn on the living room light",
            "light.turn_off": "Mach das Licht im Wohnzimmer aus" if language == "de" else "Turn off the living room light",
            "climate.set_temperature": "Stell die Temperatur im Wohnzimmer auf 21 Grad" if language == "de" else "Set the living room temperature to 21 degrees",
            "scene.activate": "Aktiviere die Szene Abend" if language == "de" else "Activate the evening scene",
            "cover.open_cover": "Öffne den Rollladen im Wohnzimmer" if language == "de" else "Open the living room shutter",
            "cover.close_cover": "Schließe den Rollladen im Wohnzimmer" if language == "de" else "Close the living room shutter",
        }
        resolved = [example_map[item] for item in suggestions if item in example_map]
        if resolved:
            return resolved[:3]
        if language == "de":
            return [
                "Mach das Licht an",
                "Stell die Temperatur auf 21 Grad",
                "Spiel Musik",
            ]
        return [
            "Turn on the light",
            "Set temperature to 21 degrees",
            "Play music",
        ]
    
    def _handle_light(
        self,
        intent: VoiceIntent,
        context: VoiceContext,
        mood_template: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Handle light on/off intents."""
        actions = []
        
        # Determine target entity
        zone = self._resolve_target_zone(intent, context)
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
        
        zone = self._resolve_target_zone(intent, context)
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
        climate_entity = f"climate.{self._resolve_target_zone(intent, context)}"
        
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
        
        media_entity = f"media_player.{self._resolve_target_zone(intent, context)}"
        
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
