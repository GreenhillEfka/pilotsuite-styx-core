"""Voice command router for POST /api/v1/voice/command.

Implements the first bounded VFM-002 router slice with explicit
safe / clarify / confirm / reject decisions on top of the existing
voice intent parsing and response generation surfaces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import uuid
from typing import Any, Dict, List, Optional, Sequence

from .context_builder import VoiceContext
from .voice_handler import IntentType, VoiceIntent, VoiceIntentHandler, VoiceResponse


HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.60


SAFE_INTENTS = {
    IntentType.LIGHT_ON,
    IntentType.LIGHT_OFF,
    IntentType.LIGHT_DIM,
    IntentType.LIGHT_BRIGHTEN,
    IntentType.CLIMATE_SET,
    IntentType.MEDIA_PLAY,
    IntentType.MEDIA_PAUSE,
    IntentType.MEDIA_STOP,
    IntentType.STATUS_QUERY,
}


@dataclass
class VoiceCommandDecision:
    """Structured router result for the API layer."""

    status: str
    action: Optional[str]
    message: str
    session_state: Dict[str, Any] = field(default_factory=dict)
    confirmation_token: Optional[str] = None
    action_payload: Optional[Dict[str, Any]] = None


class VoiceCommandRouter:
    """Thin router that applies command safety policy to parsed intents."""

    def __init__(self, handler: VoiceIntentHandler):
        self.handler = handler

    def route(
        self,
        *,
        utterance: str,
        stt_confidence: Optional[float],
        context: Optional[VoiceContext] = None,
        intent_candidates: Optional[Sequence[Dict[str, Any]]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        zone_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Route a voice command into one of the contract states."""
        intent = self.handler.parse_intent(utterance)
        normalized_intent = self._normalize_intent(intent, intent_candidates, utterance)
        effective_confidence = self._effective_confidence(
            parsed_intent=intent,
            normalized_intent=normalized_intent,
            stt_confidence=stt_confidence,
            intent_candidates=intent_candidates,
            utterance=utterance,
        )

        if self._is_confirmation_intent(normalized_intent, utterance):
            confirmation_token = str(uuid.uuid4())
            action_payload = self._build_confirmation_action_payload(normalized_intent, utterance)
            return {
                "decision": VoiceCommandDecision(
                    status="confirmation_required",
                    action=(action_payload or {}).get("label") or self._stringify_action_name(normalized_intent),
                    message=self._build_confirmation_prompt(normalized_intent, utterance),
                    confirmation_token=confirmation_token,
                    action_payload=action_payload,
                    session_state={
                        "state": "CONFIRMING",
                        "intent": normalized_intent,
                        "session_id": session_id,
                        "user_id": user_id,
                        "zone_id": zone_id,
                        "confidence": effective_confidence,
                        "utterance": utterance,
                        "confirmation_token": confirmation_token,
                        "pending_action_payload": action_payload,
                        "pending_action_label": (action_payload or {}).get("label"),
                    },
                ),
                "intent": intent,
                "normalized_intent": normalized_intent,
                "effective_confidence": effective_confidence,
                "response": None,
            }

        if self._needs_clarification(utterance, normalized_intent, effective_confidence):
            clarification_question = self._build_clarification_prompt(normalized_intent, utterance)
            return {
                "decision": VoiceCommandDecision(
                    status="clarification_required",
                    action=None,
                    message=clarification_question,
                    session_state={
                        "state": "CLARIFYING",
                        "intent": normalized_intent.value,
                        "session_id": session_id,
                        "user_id": user_id,
                        "zone_id": zone_id,
                        "confidence": effective_confidence,
                        "utterance": utterance,
                        "clarification_question": clarification_question,
                    },
                ),
                "intent": intent,
                "normalized_intent": normalized_intent,
                "effective_confidence": effective_confidence,
                "response": None,
            }

        if normalized_intent is IntentType.UNKNOWN:
            return {
                "decision": VoiceCommandDecision(
                    status="rejected",
                    action=None,
                    message="Ich habe das nicht verstanden. Bitte wiederhole den Befehl.",
                    session_state={
                        "state": "IDLE",
                        "intent": IntentType.UNKNOWN.value,
                        "session_id": session_id,
                        "user_id": user_id,
                        "zone_id": zone_id,
                        "confidence": effective_confidence,
                        "utterance": utterance,
                    },
                ),
                "intent": intent,
                "normalized_intent": normalized_intent,
                "effective_confidence": effective_confidence,
                "response": None,
            }

        response = self.handler.handle_intent(intent, context)
        action = self._extract_action(response)
        return {
            "decision": VoiceCommandDecision(
                status="executed",
                action=action,
                message=response.tts_text,
                session_state={
                    "state": "ACTIVE",
                    "intent": normalized_intent.value,
                    "session_id": session_id,
                    "user_id": user_id,
                    "zone_id": zone_id,
                    "confidence": effective_confidence,
                    "utterance": utterance,
                },
            ),
            "intent": intent,
            "normalized_intent": normalized_intent,
            "effective_confidence": effective_confidence,
            "response": response,
        }

    def _normalize_intent(
        self,
        parsed_intent: VoiceIntent,
        intent_candidates: Optional[Sequence[Dict[str, Any]]],
        utterance: str,
    ) -> IntentType:
        candidate_intent = self._normalize_candidate_intent(intent_candidates, utterance)
        if candidate_intent is not None:
            return candidate_intent
        return parsed_intent.intent_type

    def _normalize_candidate_intent(
        self,
        intent_candidates: Optional[Sequence[Dict[str, Any]]],
        utterance: str,
    ) -> Optional[IntentType]:
        if not intent_candidates:
            return None

        sorted_candidates = sorted(
            [candidate for candidate in intent_candidates if isinstance(candidate, dict)],
            key=lambda candidate: float(candidate.get("confidence", 0.0) or 0.0),
            reverse=True,
        )
        if not sorted_candidates:
            return None

        name = str(sorted_candidates[0].get("intent", "")).strip().lower()
        mapping = {
            "lights.on": IntentType.LIGHT_ON,
            "light.on": IntentType.LIGHT_ON,
            "light.turn_on": IntentType.LIGHT_ON,
            "lights.off": IntentType.LIGHT_OFF,
            "light.off": IntentType.LIGHT_OFF,
            "light.turn_off": IntentType.LIGHT_OFF,
            "lights.brightness": IntentType.LIGHT_DIM,
            "light.brightness": IntentType.LIGHT_DIM,
            "climate.set_temp": IntentType.CLIMATE_SET,
            "climate.set_temperature": IntentType.CLIMATE_SET,
            "media.play": IntentType.MEDIA_PLAY,
            "media.pause": IntentType.MEDIA_PAUSE,
            "media.stop": IntentType.MEDIA_STOP,
            "status.query": IntentType.STATUS_QUERY,
        }
        resolved = mapping.get(name)
        if resolved is None and name in {"covers.open_close", "broadcast.all_lights"}:
            return IntentType.UNKNOWN
        if resolved is None and name == "locks.unlock":
            return IntentType.UNKNOWN
        if resolved is None and name == "covers.open_close":
            lowered = utterance.lower()
            if any(token in lowered for token in ("zu", "runter", "schließen", "schliessen")):
                return IntentType.UNKNOWN
        return resolved

    def _effective_confidence(
        self,
        *,
        parsed_intent: VoiceIntent,
        normalized_intent: IntentType,
        stt_confidence: Optional[float],
        intent_candidates: Optional[Sequence[Dict[str, Any]]],
        utterance: str,
    ) -> float:
        candidate_confidence = 0.0
        if intent_candidates:
            for candidate in intent_candidates:
                if not isinstance(candidate, dict):
                    continue
                try:
                    candidate_confidence = max(candidate_confidence, float(candidate.get("confidence", 0.0) or 0.0))
                except (TypeError, ValueError):
                    continue

        values = [parsed_intent.confidence, candidate_confidence]
        if isinstance(stt_confidence, (int, float)):
            values.append(float(stt_confidence))

        lowered = utterance.lower()
        if normalized_intent in SAFE_INTENTS and any(
            token in lowered for token in ("licht an", "licht aus", "temperatur", "musik", "status")
        ):
            values.append(HIGH_CONFIDENCE_THRESHOLD)
        if self._is_confirmation_intent(normalized_intent, utterance):
            values.append(HIGH_CONFIDENCE_THRESHOLD)
        if self._looks_ambiguous(lowered):
            values.append(0.7)

        return round(max(values or [0.0]), 2)

    def _needs_clarification(
        self,
        utterance: str,
        normalized_intent: IntentType,
        effective_confidence: float,
    ) -> bool:
        lowered = utterance.lower()
        if self._looks_ambiguous(lowered):
            return True
        if normalized_intent is IntentType.UNKNOWN and effective_confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
            return True
        return MEDIUM_CONFIDENCE_THRESHOLD <= effective_confidence < HIGH_CONFIDENCE_THRESHOLD

    @staticmethod
    def _looks_ambiguous(lowered_utterance: str) -> bool:
        ambiguous_patterns = (
            "mach es an",
            "mach das an",
            "schalt es an",
            "schalte es an",
            "mach an",
            "tu es an",
            "stell es",
        )
        return any(pattern in lowered_utterance for pattern in ambiguous_patterns)

    @staticmethod
    def _is_confirmation_intent(normalized_intent: IntentType, utterance: str) -> bool:
        lowered = utterance.lower()
        if normalized_intent not in SAFE_INTENTS and any(
            token in lowered
            for token in (
                "aufschließen",
                "aufschliessen",
                "garage öffnen",
                "garage oeffnen",
                "rollladen hoch",
                "rollladen runter",
                "fenster zu",
                "fenster auf",
                "alarm deaktivieren",
                "herd ausschalten",
                "alle lichter",
                "ganzes haus",
            )
        ):
            return True
        return False

    @staticmethod
    def _build_confirmation_prompt(normalized_intent: IntentType, utterance: str) -> str:
        lowered = utterance.lower()
        if "aufsch" in lowered or "garage" in lowered:
            return "Soll ich das wirklich aufschließen? Bitte bestätigen."
        if "rollladen" in lowered or "fenster" in lowered:
            return "Soll ich diese Abdeckung wirklich bewegen? Bitte bestätigen."
        if "alarm" in lowered or "herd" in lowered:
            return "Diese Aktion ist heikel. Soll ich sie wirklich ausführen?"
        if "alle lichter" in lowered or "ganzes haus" in lowered:
            return "Soll ich wirklich eine breite Haus-Aktion ausführen? Bitte bestätigen."
        return f"Soll ich {VoiceCommandRouter._stringify_action_name(normalized_intent) or utterance} ausführen?"

    @staticmethod
    def _build_clarification_prompt(normalized_intent: IntentType, utterance: str) -> str:
        lowered = utterance.lower()
        if VoiceCommandRouter._looks_ambiguous(lowered):
            return "Was genau soll ich anschalten oder ändern?"
        if normalized_intent is IntentType.UNKNOWN:
            return "Kannst du das bitte genauer beschreiben?"
        return "Ich bin mir nicht ganz sicher. Kannst du den Befehl bitte präzisieren?"

    @staticmethod
    def _build_confirmation_action_payload(
        normalized_intent: IntentType,
        utterance: str,
    ) -> Optional[Dict[str, Any]]:
        lowered = utterance.lower()

        if "alle lichter" in lowered or "ganzes haus" in lowered:
            service = "turn_off" if " aus" in lowered else "turn_on"
            return {
                "domain": "light",
                "service": service,
                "service_data": {"scope": "all_lights"},
                "label": f"light.{service}",
                "requires_confirmation": True,
                "risk_category": "broad_action",
            }

        if "rollladen" in lowered or "fenster" in lowered:
            service = "close_cover" if any(
                token in lowered for token in (" zu", "runter", "schließen", "schliessen")
            ) else "open_cover"
            return {
                "domain": "cover",
                "service": service,
                "service_data": {"scope": "voice_target"},
                "label": f"cover.{service}",
                "requires_confirmation": True,
                "risk_category": "cover_motion",
            }

        if "alarm" in lowered:
            return {
                "domain": "switch",
                "service": "turn_off",
                "service_data": {"target": "alarm_system"},
                "label": "switch.turn_off",
                "requires_confirmation": True,
                "risk_category": "dangerous_switch",
            }

        if "herd" in lowered:
            return {
                "domain": "switch",
                "service": "turn_off",
                "service_data": {"target": "stove"},
                "label": "switch.turn_off",
                "requires_confirmation": True,
                "risk_category": "dangerous_switch",
            }

        if "garage" in lowered or "aufsch" in lowered:
            target = "garage" if "garage" in lowered else "door"
            return {
                "domain": "lock",
                "service": "unlock",
                "service_data": {"target": target},
                "label": "lock.unlock",
                "requires_confirmation": True,
                "risk_category": "unsafe_unlock",
            }

        label = VoiceCommandRouter._stringify_action_name(normalized_intent)
        if not label:
            return None

        domain, service = label.split(".", 1)
        return {
            "domain": domain,
            "service": service,
            "service_data": {},
            "label": label,
            "requires_confirmation": True,
            "risk_category": "confirmation_required",
        }

    @staticmethod
    def _extract_action(response: VoiceResponse) -> Optional[str]:
        if not response.actions:
            return None
        first_action = response.actions[0]
        domain = first_action.get("domain")
        service = first_action.get("service")
        if domain and service:
            return f"{domain}.{service}"
        return None

    @staticmethod
    def _stringify_action_name(normalized_intent: IntentType) -> Optional[str]:
        mapping = {
            IntentType.LIGHT_ON: "light.turn_on",
            IntentType.LIGHT_OFF: "light.turn_off",
            IntentType.LIGHT_DIM: "light.turn_on",
            IntentType.LIGHT_BRIGHTEN: "light.turn_on",
            IntentType.CLIMATE_SET: "climate.set_temperature",
            IntentType.MEDIA_PLAY: "media_player.media_play",
            IntentType.MEDIA_PAUSE: "media_player.media_pause",
            IntentType.MEDIA_STOP: "media_player.media_stop",
            IntentType.STATUS_QUERY: "homeassistant.update_entity",
            IntentType.UNKNOWN: None,
        }
        return mapping.get(normalized_intent)
