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


_DE_FOLLOW_UP_RESUME_PATTERNS = [
    r"\b(weiter|mach weiter|bitte weiter|weiter damit|mach damit weiter|noch offen|wie steht(?: es|['’]?s)(?: damit)?|was ist damit)\b",
]

_EN_FOLLOW_UP_RESUME_PATTERNS = [
    r"\b(continue|continue with|follow up|check on it|what about that|still open|go on|how(?: is|['’]?s) (?:that|it) going)\b",
]


def looks_like_follow_up_resume_request(text: str, language: "Language | str | None") -> bool:
    """Detect explicit proposal/closure follow-up resume phrasing.

    API and engine must share the same matcher so bilingual resume behavior
    cannot drift between `/voice/control/continue` validation and the actual
    dialog engine execution path.
    """
    text_clean = str(text or "").strip().lower()
    if not text_clean:
        return False

    normalized_language = language.value if isinstance(language, Language) else str(language or "").strip().lower()
    primary_patterns = (
        _DE_FOLLOW_UP_RESUME_PATTERNS
        if normalized_language == Language.DE.value
        else _EN_FOLLOW_UP_RESUME_PATTERNS
        if normalized_language == Language.EN.value
        else []
    )
    fallback_patterns = [
        pattern
        for pattern in _DE_FOLLOW_UP_RESUME_PATTERNS + _EN_FOLLOW_UP_RESUME_PATTERNS
        if pattern not in primary_patterns
    ]
    return any(re.search(pattern, text_clean) for pattern in primary_patterns + fallback_patterns)


def _normalize_follow_up_status(value: Any) -> str:
    """Normalize follow-up status values into a stable dialog contract token."""
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "open").strip().lower()).strip("_")
    return normalized or "open"


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


class VoiceDialogStatus(Enum):
    """State of a multi-turn voice dialog."""

    ACTIVE = "active"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    RESOLVED = "resolved"


@dataclass
class VoiceDialogFollowUpTarget:
    """Canonical follow-up target attached to a dialog session."""

    target_kind: str
    target_id: str
    zone_id: Optional[str] = None
    module_id: Optional[str] = None
    summary: Optional[str] = None
    status: str = "open"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "summary": self.summary,
            "status": self.status,
        }


@dataclass
class VoiceDialogSession:
    """Persistent multi-turn dialog state for voice interactions."""

    session_id: str
    language: Language
    status: VoiceDialogStatus = VoiceDialogStatus.ACTIVE
    current_zone_id: Optional[str] = None
    pending_command: Optional[VoiceCommand] = None
    last_command: Optional[VoiceCommand] = None
    last_response: Optional[VoiceResponse] = None
    active_follow_up: Optional[VoiceDialogFollowUpTarget] = None
    clarification_prompt: Optional[str] = None
    turn_count: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "language": self.language.value,
            "status": self.status.value,
            "current_zone_id": self.current_zone_id,
            "pending_command": self.pending_command.to_dict() if self.pending_command else None,
            "last_command": self.last_command.to_dict() if self.last_command else None,
            "last_response": self.last_response.to_dict() if self.last_response else None,
            "active_follow_up": self.active_follow_up.to_dict() if self.active_follow_up else None,
            "clarification_prompt": self.clarification_prompt,
            "turn_count": self.turn_count,
            "history": list(self.history),
            "updated_at": self.updated_at,
        }


class VoiceControlEngine:
    """Voice command processing engine."""
    
    def __init__(self, default_language: Language = Language.DE):
        self._default_language = default_language
        self._command_counter = 0
        self._response_counter = 0
        self._command_history: List[VoiceCommand] = []
        self._responses: Dict[str, VoiceResponse] = {}
        self._dialog_sessions: Dict[str, VoiceDialogSession] = {}
        
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

    def _normalize_follow_up_target(self, follow_up_target: Dict[str, Any]) -> Optional[VoiceDialogFollowUpTarget]:
        """Normalize proposal/action-closure follow-up payloads."""
        if not isinstance(follow_up_target, dict):
            return None

        target_kind = str(
            follow_up_target.get("target_kind")
            or follow_up_target.get("kind")
            or ""
        ).strip().lower()
        if target_kind not in {"proposal", "action_closure"}:
            return None

        target_id = str(
            follow_up_target.get("target_id")
            or follow_up_target.get("proposal_id")
            or follow_up_target.get("closure_id")
            or follow_up_target.get("id")
            or ""
        ).strip()
        if not target_id:
            return None

        return VoiceDialogFollowUpTarget(
            target_kind=target_kind,
            target_id=target_id,
            zone_id=str(follow_up_target.get("zone_id") or "").strip() or None,
            module_id=str(follow_up_target.get("module_id") or "").strip() or None,
            summary=str(follow_up_target.get("summary") or "").strip() or None,
            status=_normalize_follow_up_status(follow_up_target.get("status")),
        )

    def _get_or_create_dialog_session(
        self,
        session_id: str,
        language: Optional[Language],
    ) -> VoiceDialogSession:
        """Get or create a dialog session."""
        normalized_id = str(session_id or "default").strip() or "default"
        session = self._dialog_sessions.get(normalized_id)
        if session is None:
            session = VoiceDialogSession(
                session_id=normalized_id,
                language=language or self._default_language,
            )
            self._dialog_sessions[normalized_id] = session
        elif language is not None:
            session.language = language
        return session

    def _is_low_confidence_command(self, command: VoiceCommand) -> bool:
        """Decide whether a command needs clarification."""
        return command.intent_type == VoiceIntentType.UNKNOWN or command.confidence < 0.7

    def _merge_dialog_turn_text(self, base_text: str, clarification_text: str) -> str:
        """Merge ambiguous prior text with a clarification turn."""
        base = str(base_text or "").strip()
        clarification = str(clarification_text or "").strip()
        if not base:
            return clarification
        if not clarification:
            return base
        return f"{base} {clarification}".strip()

    def _looks_like_follow_up_request(self, text: str, language: Language) -> bool:
        """Detect generic follow-up phrasing that targets a proposal/closure."""
        return looks_like_follow_up_resume_request(text, language)

    def _build_clarification_response(
        self,
        command: VoiceCommand,
        session: VoiceDialogSession,
    ) -> VoiceResponse:
        """Build explicit clarification response for low-confidence turns."""
        self._response_counter += 1
        zone_hint = session.current_zone_id or command.zone_id
        zone_suffix_de = f" in {zone_hint}" if zone_hint else ""
        zone_suffix_en = f" in {zone_hint}" if zone_hint else ""

        follow_up = session.active_follow_up
        if follow_up:
            if follow_up.target_kind == "proposal":
                text_de = (
                    f"Ich bin noch nicht sicher. Meinst du den Vorschlag {follow_up.target_id}"
                    f"{zone_suffix_de} oder etwas anderes?"
                )
                text_en = (
                    f"I'm not certain yet. Do you mean proposal {follow_up.target_id}"
                    f"{zone_suffix_en} or something else?"
                )
            else:
                text_de = (
                    f"Ich bin noch nicht sicher. Soll ich den Abschluss {follow_up.target_id}"
                    f"{zone_suffix_de} prüfen?"
                )
                text_en = (
                    f"I'm not certain yet. Should I review closure {follow_up.target_id}"
                    f"{zone_suffix_en}?"
                )
        else:
            text_de = (
                "Ich bin noch nicht sicher. Bitte präzisiere Aktion oder Zone"
                f"{zone_suffix_de}."
            )
            text_en = (
                "I'm not certain yet. Please clarify the action or zone"
                f"{zone_suffix_en}."
            )

        return VoiceResponse(
            response_id=f"resp_{self._response_counter}",
            command_id=command.command_id,
            text_de=text_de,
            text_en=text_en,
            action_taken={
                "intent": "clarification_required",
                "zone": zone_hint,
                "follow_up_target": follow_up.to_dict() if follow_up else None,
            },
            requires_confirmation=True,
        )

    def _build_follow_up_response(
        self,
        session: VoiceDialogSession,
        command: VoiceCommand,
    ) -> VoiceResponse:
        """Build explicit proposal/action-closure follow-up response."""
        self._response_counter += 1
        target = session.active_follow_up
        assert target is not None

        if target.target_kind == "proposal":
            text_de = f"OK, ich mache mit Vorschlag {target.target_id} weiter."
            text_en = f"OK, I'll continue with proposal {target.target_id}."
        else:
            text_de = f"OK, ich prüfe Abschluss {target.target_id} weiter."
            text_en = f"OK, I'll continue reviewing closure {target.target_id}."

        if target.summary:
            text_de = f"{text_de} {target.summary}".strip()
            text_en = f"{text_en} {target.summary}".strip()

        return VoiceResponse(
            response_id=f"resp_{self._response_counter}",
            command_id=command.command_id,
            text_de=text_de,
            text_en=text_en,
            action_taken={
                "intent": "dialog_follow_up",
                "target_kind": target.target_kind,
                "target_id": target.target_id,
                "status": target.status,
                "zone": target.zone_id or session.current_zone_id,
            },
            requires_confirmation=False,
        )

    def process_dialog_turn(
        self,
        text: str,
        session_id: str = "default",
        language: Optional[Language] = None,
        follow_up_target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a multi-turn voice dialog with clarification + follow-up state.

        Keeps zone context across turns, merges clarification text into ambiguous
        prior commands, and allows proposal/action-closure follow-up targets to be
        attached to the same dialog session.
        """
        session = self._get_or_create_dialog_session(session_id, language)
        normalized_target = self._normalize_follow_up_target(follow_up_target or {})
        if normalized_target is not None:
            session.active_follow_up = normalized_target
            if normalized_target.zone_id:
                session.current_zone_id = normalized_target.zone_id

        command = self._parse_voice_command(text, language=language or session.language)

        if (
            session.status == VoiceDialogStatus.AWAITING_CLARIFICATION
            and session.pending_command is not None
        ):
            merged_text = self._merge_dialog_turn_text(session.pending_command.raw_text, text)
            merged_command = self._parse_voice_command(merged_text, language=language or session.language)
            if (
                merged_command.intent_type != VoiceIntentType.UNKNOWN
                or merged_command.confidence > command.confidence
            ):
                command = merged_command

        if command.zone_id is None and session.current_zone_id and command.intent_type != VoiceIntentType.UNKNOWN:
            command.zone_id = session.current_zone_id
            command.confidence = min(command.confidence + 0.1, 1.0)

        if (
            session.active_follow_up is not None
            and self._looks_like_follow_up_request(text, language or session.language)
        ):
            response = self._build_follow_up_response(session, command)
            session.status = VoiceDialogStatus.RESOLVED
            session.pending_command = None
            session.clarification_prompt = None
        elif self._is_low_confidence_command(command):
            response = self._build_clarification_response(command, session)
            session.status = VoiceDialogStatus.AWAITING_CLARIFICATION
            session.pending_command = command
            session.clarification_prompt = response.text_de
        else:
            response = self.generate_response(command)
            session.status = VoiceDialogStatus.ACTIVE
            session.pending_command = None
            session.clarification_prompt = None

        if command.zone_id:
            session.current_zone_id = command.zone_id

        self._record_command(command)

        session.turn_count += 1
        session.last_command = command
        session.last_response = response
        session.updated_at = datetime.now(timezone.utc).isoformat()
        session.history.append(
            {
                "turn": session.turn_count,
                "raw_text": text,
                "command": command.to_dict(),
                "response": response.to_dict(),
                "status": session.status.value,
            }
        )

        return {
            "command": command.to_dict(),
            "response": response.to_dict(),
            "dialog": session.to_dict(),
        }

    def get_dialog_session(self, session_id: str = "default") -> Optional[Dict[str, Any]]:
        """Return serialized dialog session state."""
        session = self._dialog_sessions.get(str(session_id or "default").strip() or "default")
        return session.to_dict() if session is not None else None

    def clear_dialog_session(self, session_id: str = "default") -> None:
        """Reset a dialog session."""
        self._dialog_sessions.pop(str(session_id or "default").strip() or "default", None)
    
    def process_voice_command(self, text: str, language: Optional[Language] = None) -> VoiceCommand:
        """Process a voice command and return parsed intent.
        
        Handles edge cases:
        - Empty commands
        - Very long commands (truncated for parsing)
        - Special characters and Unicode
        - Noise/filler words
        """
        command = self._parse_voice_command(text, language=language)
        self._record_command(command)
        return command

    def _parse_voice_command(self, text: str, language: Optional[Language] = None) -> VoiceCommand:
        """Parse a voice command without mutating command history."""
        if language is None:
            language = self._default_language

        self._command_counter += 1

        # Handle empty command
        if not text or not text.strip():
            return VoiceCommand(
                command_id=f"voice_{self._command_counter}",
                intent_type=VoiceIntentType.UNKNOWN,
                language=language,
                raw_text=text,
                confidence=0.3,  # Low confidence for empty
            )

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

        return VoiceCommand(
            command_id=f"voice_{self._command_counter}",
            intent_type=intent_type,
            language=language,
            raw_text=text,
            zone_id=zone_id,
            parameters=parameters,
            confidence=self._calculate_confidence(intent_type, zone_id, text_parse),
        )

    def _record_command(self, command: VoiceCommand) -> None:
        """Persist parsed command in bounded history."""
        self._command_history.append(command)
        if len(self._command_history) > 100:
            self._command_history = self._command_history[-100:]
    
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
