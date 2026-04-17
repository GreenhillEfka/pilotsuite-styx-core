"""Voice API Endpoints for Home Assistant Voice Assistant Integration.

Provides REST API for voice intent handling, context building, and proactive hints.

Endpoints:
- POST /api/v1/voice/intent - Process voice intent
- GET  /api/v1/voice/context - Get current voice context
- GET  /api/v1/voice/hints - Get proactive voice hints
- POST /api/v1/voice/speak - Generate TTS response
- GET  /api/v1/voice/status - Voice system status

Features:
- HA Voice Assistant Intent-Handling
- Kontextbewusste Antworten (Stimmung, Tageszeit, Raum)
- Proaktive Hinweise bei wichtigen Erkenntnissen
- DE/EN Sprachunterstützung
- Integration mit Mood Engine und Habitus
"""
import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, jsonify, request

from copilot_core.voice.command_router import VoiceCommandRouter
from copilot_core.voice.voice_handler import VoiceIntentHandler, VoiceIntent, IntentType, VoiceResponse
from copilot_core.voice.context_builder import VoiceContextBuilder, VoiceContext
from copilot_core.voice.proactive import ProactiveVoiceHints, HintConfig, HintPriority

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("voice", __name__, url_prefix="/api/v1/voice")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    """Require authentication for all voice endpoints."""
    if not _validate_token(request):
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required"
        }), 401


def _get_intent_handler() -> VoiceIntentHandler:
    """Get or create voice intent handler instance."""
    if not hasattr(current_app, '_voice_intent_handler'):
        # Initialize mood engine if available
        mood_engine = None
        try:
            from copilot_core.mood.engine import MoodEngine, MoodConfig, ZoneConfig
            
            # Create default mood config
            zone_config = ZoneConfig(
                name="wohnzimmer",
                motion_entities=["binary_sensor.wohnzimmer_motion"],
                light_entities=["light.wohnzimmer"],
                media_entities=["media_player.wohnzimmer"],
                illuminance_entity="sensor.wohnzimmer_illuminance",
            )
            
            mood_config = MoodConfig(zones={"wohnzimmer": zone_config})
            mood_engine = MoodEngine(mood_config)
            
        except Exception as e:
            _LOGGER.warning("Failed to initialize mood engine for voice: %s", e)
        
        # Initialize habitus service if available
        habitus_service = None
        try:
            from copilot_core.habitus.service import HabitusService
            from copilot_core.brain_graph.service import BrainGraphService
            from copilot_core.candidates.store import CandidateStore
            
            # Try to get existing instances
            if hasattr(current_app, '_habitus_service'):
                habitus_service = current_app._habitus_service
            
        except Exception as e:
            _LOGGER.warning("Failed to initialize habitus service for voice: %s", e)
        
        current_app._voice_intent_handler = VoiceIntentHandler(
            mood_engine=mood_engine,
            habitus_service=habitus_service,
            default_language="de",
        )
    
    return current_app._voice_intent_handler


def _get_context_builder() -> VoiceContextBuilder:
    """Get or create voice context builder instance."""
    if not hasattr(current_app, '_voice_context_builder'):
        current_app._voice_context_builder = VoiceContextBuilder()
    return current_app._voice_context_builder


def _get_proactive_hints() -> ProactiveVoiceHints:
    """Get or create proactive voice hints instance."""
    if not hasattr(current_app, '_voice_proactive_hints'):
        # Get mood engine and habitus service
        intent_handler = _get_intent_handler()
        
        config = HintConfig(
            enabled_types=[
                hint_type for hint_type in __import__('copilot_core.voice.proactive', fromlist=['HintType']).HintType
            ],
            min_priority=HintPriority.LOW,
            hint_cooldown_seconds=300,
            max_hints_per_hour=6,
        )
        
        current_app._voice_proactive_hints = ProactiveVoiceHints(
            mood_engine=intent_handler.mood_engine,
            habitus_service=intent_handler.habitus_service,
            config=config,
        )
    
    return current_app._voice_proactive_hints


def _serialize_dialog_state(state) -> Dict[str, Any]:
    """Serialize dialog state with router-facing metadata."""
    slot_values = dict(state.slot_values)
    return {
        "dialog_state": state.state,
        "active_intent": state.active_intent,
        "slot_values": slot_values,
        "session_id": state.session_id,
        "user_id": state.user_id,
        "last_status": slot_values.get("_last_status"),
        "pending_confirmation": state.state == "CONFIRMING" and bool(slot_values.get("_confirmation_token")),
        "pending_action_label": slot_values.get("_pending_action_label"),
        "pending_action_payload": slot_values.get("_pending_action_payload"),
        "clarification_question": slot_values.get("_clarification"),
        "confirmation_token": slot_values.get("_confirmation_token"),
        "confirmation_expires_at": slot_values.get("_confirmation_expires_at"),
    }


def _normalize_last_status(state) -> str:
    """Project dialog state into the public voice-command status vocabulary."""
    slot_values = dict(state.slot_values)
    explicit = slot_values.get("_last_status")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    fallback = {
        "ACTIVE": "executed",
        "CONFIRMING": "confirmation_required",
        "CLARIFYING": "clarification_required",
        "IDLE": "idle",
    }
    return fallback.get(state.state, "idle")


def _format_command_state_timestamp(value: Optional[Any]) -> Optional[str]:
    """Normalize optional epoch timestamps to ISO 8601 UTC for API consumers."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _build_idle_command_state() -> Dict[str, Any]:
    """Return the truthful empty command-state shape."""
    return {
        "last_status": "idle",
        "pending_confirmation": False,
        "pending_action_label": None,
        "confirmation_expires_at": None,
    }


def _serialize_command_state(state, *, session_id: str) -> Dict[str, Any]:
    """Serialize the session-scoped command-state surface for HA consumers."""
    if not state.session_id or state.session_id != session_id:
        return _build_idle_command_state()

    slot_values = dict(state.slot_values)
    pending_confirmation = state.state == "CONFIRMING" and bool(slot_values.get("_confirmation_token"))
    return {
        "last_status": _normalize_last_status(state),
        "pending_confirmation": pending_confirmation,
        "pending_action_label": slot_values.get("_pending_action_label"),
        "confirmation_expires_at": _format_command_state_timestamp(slot_values.get("_confirmation_expires_at")),
    }


def _build_command_follow_through_response(action_payload: Optional[Dict[str, Any]]) -> VoiceResponse:
    """Build the first bounded execution payload for a confirmed action."""
    actions = [dict(action_payload)] if action_payload else []
    return VoiceResponse(
        tts_text="Bestätigt. Ich führe die Aktion jetzt aus.",
        actions=actions,
        confidence=1.0,
        language="de",
    )


def _validate_pending_confirmation(
    machine,
    *,
    session_id: Optional[str],
    confirmation_token: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Validate the currently persisted pending confirmation state."""
    if machine.check_timeout():
        machine.decay()
        return None

    state = machine.get_state()
    if state.state != "CONFIRMING":
        return None

    slot_values = dict(state.slot_values)
    pending_token = slot_values.get("_confirmation_token")
    pending_session_id = state.session_id

    if not confirmation_token or confirmation_token != pending_token:
        return None
    if pending_session_id and session_id and session_id != pending_session_id:
        return None

    return {
        "state": state,
        "slot_values": slot_values,
        "action_payload": slot_values.get("_pending_action_payload"),
        "action_label": slot_values.get("_pending_action_label") or slot_values.get("_pending_action"),
    }


def _resolve_requested_zone(
    explicit_zone: Optional[str],
    req_context: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Resolve the canonical requested zone from explicit or replayed context."""
    zone = explicit_zone
    if not zone and isinstance(req_context, dict):
        zone = req_context.get("zone_name")
        if not zone:
            nested_zone = req_context.get("zone")
            if isinstance(nested_zone, dict):
                zone = nested_zone.get("zone_name")

    return zone.lower() if isinstance(zone, str) and zone else zone


@bp.route("/intent", methods=["POST"])
def process_intent():
    """Process voice intent and return response.
    
    Request body:
    {
        "text": "Mach das Licht an",
        "language": "de",  // optional, auto-detected if not provided
        "zone": "wohnzimmer",  // optional, current zone
        "context": {...},  // optional, existing context
    }
    
    Response:
    {
        "status": "ok",
        "intent": {
            "intent_type": "light_on",
            "confidence": 0.95,
            "slots": {},
            "language": "de",
        },
        "response": {
            "tts_text": "Entspannt. Alles klar, ich mache das. Licht ist an.",
            "actions": [
                {
                    "domain": "light",
                    "service": "turn_on",
                    "entity_id": "light.wohnzimmer"
                }
            ],
            "mood_context": "relax",
            "language": "de",
            "suggestions": ["Möchtest du eine Entspannungs-Playlist?"]
        }
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        text = data.get("text")
        if not text:
            return jsonify({
                "status": "error",
                "message": "Missing 'text' in request body"
            }), 400
        
        language = data.get("language")
        zone = data.get("zone")

        handler = _get_intent_handler()
        intent = handler.parse_intent(text, language)

        # Extract accepted context replay fields from request body
        req_context = data.get("context", {}) if isinstance(data.get("context"), dict) else {}
        user_prefs = req_context.get("user_preferences")
        active_devs = req_context.get("active_devices")

        zone = _resolve_requested_zone(zone, req_context)

        context_builder = _get_context_builder()

        if "context" in data and isinstance(data["context"], dict):
            # Use provided context (simplified reconstruction)
            context = context_builder.build_context(
                mood_engine=handler.mood_engine,
                habitus_service=handler.habitus_service,
                zone_name=zone,
                force_refresh=True,
                user_preferences=user_prefs,
                active_devices=active_devs,
            )
        else:
            # Build fresh context
            context = context_builder.build_context(
                mood_engine=handler.mood_engine,
                habitus_service=handler.habitus_service,
                zone_name=zone,
                force_refresh=data.get("force_context", False),
                user_preferences=user_prefs,
                active_devices=active_devs,
            )
        
        # Handle intent
        response = handler.handle_intent(intent, context)

        # Honor language_preference from context (e.g., preferred_language from HA user profile)
        ctx_lang = getattr(context, 'language_preference', None)
        if ctx_lang:
            response.language = ctx_lang

        return jsonify({
            "status": "ok",
            "intent": intent.to_dict(),
            "response": response.to_dict(),
            "context": context.to_dict(),
        })
    
    except Exception as e:
        _LOGGER.exception("Voice intent processing failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/command", methods=["POST"])
def process_command():
    """Route full voice commands through safe / clarify / confirm / reject policy."""
    try:
        data = request.get_json(silent=True) or {}

        utterance = data.get("utterance") or data.get("text")
        if not utterance:
            return jsonify({
                "status": "error",
                "message": "Missing 'utterance' in request body"
            }), 400

        confidence = data.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                return jsonify({
                    "status": "error",
                    "message": "Field 'confidence' must be numeric"
                }), 400

        intent_candidates = data.get("intent_candidates")
        if intent_candidates is not None and not isinstance(intent_candidates, list):
            return jsonify({
                "status": "error",
                "message": "Field 'intent_candidates' must be a list"
            }), 400

        session_id = data.get("session_id")
        user_id = data.get("user_id")
        zone = data.get("zone_id") or data.get("zone")
        req_context = data.get("context", {}) if isinstance(data.get("context"), dict) else {}
        user_prefs = req_context.get("user_preferences")
        active_devs = req_context.get("active_devices")
        zone = _resolve_requested_zone(zone, req_context)

        handler = _get_intent_handler()
        context_builder = _get_context_builder()
        context = context_builder.build_context(
            mood_engine=handler.mood_engine,
            habitus_service=handler.habitus_service,
            zone_name=zone,
            force_refresh=bool(req_context),
            user_preferences=user_prefs,
            active_devices=active_devs,
        )

        router = VoiceCommandRouter(handler)
        routed = router.route(
            utterance=utterance,
            stt_confidence=confidence,
            context=context,
            intent_candidates=intent_candidates,
            session_id=session_id,
            user_id=user_id,
            zone_id=zone,
        )

        decision = routed["decision"]
        normalized_intent = routed["normalized_intent"]
        intent_name = normalized_intent.value if hasattr(normalized_intent, "value") else str(normalized_intent)

        machine = _get_dialog_machine()
        if decision.status == "executed":
            state = machine.activate_intent(
                intent=decision.action or intent_name,
                slots={"_last_utterance": utterance},
                session_id=session_id,
                user_id=user_id,
            )
        elif decision.status == "confirmation_required":
            machine.activate_intent(
                intent=decision.action or intent_name,
                slots={"_last_utterance": utterance},
                session_id=session_id,
                user_id=user_id,
            )
            confirmation_metadata = {
                "_last_utterance": utterance,
                "_pending_action": decision.action,
                "_pending_action_label": decision.action,
                "_pending_action_payload": decision.action_payload,
                "_confirmation_prompt": decision.message,
                "_confirmation_expires_at": time.time() + machine.TIMEOUT_SECONDS,
                "_confirmation_token": decision.confirmation_token,
            }
            state = machine.set_confirming(metadata={
                **confirmation_metadata,
            })
        elif decision.status == "clarification_required":
            machine.activate_intent(
                intent=intent_name,
                slots={"_last_utterance": utterance},
                session_id=session_id,
                user_id=user_id,
            )
            state = machine.set_clarifying(
                decision.message,
                metadata={
                    "_last_utterance": utterance,
                    "_intent": intent_name,
                },
            )
        else:
            state = machine.reset(session_id=session_id, user_id=user_id)

        state = machine.merge_metadata({"_last_status": decision.status})

        session_state = dict(decision.session_state)
        session_state.update(_serialize_dialog_state(state))

        response_payload = {
            "status": decision.status,
            "action": decision.action,
            "message": decision.message,
            "confirmation_token": decision.confirmation_token,
            "session_state": session_state,
            "intent": routed["intent"].to_dict(),
            "context": context.to_dict(),
            "effective_confidence": routed["effective_confidence"],
        }
        if routed.get("response") is not None:
            response_payload["response"] = routed["response"].to_dict()

        return jsonify(response_payload)

    except Exception as e:
        _LOGGER.exception("Voice command routing failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/context", methods=["GET"])
def get_context():
    """Get current voice context.
    
    Query parameters:
    - zone: Optional zone name (default: auto-detect)
    - force: Force refresh (default: false)
    
    Response:
    {
        "status": "ok",
        "context": {
            "mood": {
                "state": "relax",
                "confidence": 0.85,
                "reasons": ["Media playing in dark environment"]
            },
            "time": {
                "time_of_day": "evening",
                "day_type": "weekday",
                "hour": 20,
                "is_quiet_hours": false,
                "description_de": "Guten Abend"
            },
            "zone": {
                "zone_name": "wohnzimmer",
                "zone_type": "living_room",
                "is_occupied": true,
                "occupancy_confidence": 0.9
            },
            "active_devices": [...],
            "language_preference": "de"
        }
    }
    """
    try:
        zone = request.args.get("zone")
        force = request.args.get("force", "false").lower() == "true"
        
        context_builder = _get_context_builder()
        handler = _get_intent_handler()
        
        context = context_builder.build_context(
            mood_engine=handler.mood_engine,
            habitus_service=handler.habitus_service,
            zone_name=zone,
            force_refresh=force,
        )
        
        return jsonify({
            "status": "ok",
            "context": context.to_dict(),
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get voice context")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/hints", methods=["GET"])
def get_hints():
    """Get proactive voice hints.
    
    Query parameters:
    - zone: Optional zone name
    - priority: Filter by minimum priority (low, medium, high, critical)
    - force: Force generation (ignore cooldowns)
    - type: Filter by hint type
    
    Response:
    {
        "status": "ok",
        "hints": [
            {
                "hint_type": "mood_change",
                "priority": "medium",
                "title_de": "Entspannte Stimmung erkannt",
                "title_en": "Relaxed mood detected",
                "message_de": "Die Stimmung ist entspannt. Möchtest du eine Chill-Playlist?",
                "message_en": "The mood is relaxed. Would you like a chill playlist?",
                "suggested_action": {...},
                "context": {...}
            }
        ],
        "critical_count": 0,
        "queued_count": 1
    }
    """
    try:
        zone = request.args.get("zone")
        priority = request.args.get("priority")
        force = request.args.get("force", "false").lower() == "true"
        hint_type = request.args.get("type")
        
        # Get proactive hints
        hints_service = _get_proactive_hints()
        context_builder = _get_context_builder()
        handler = _get_intent_handler()
        
        context = context_builder.build_context(
            mood_engine=handler.mood_engine,
            habitus_service=handler.habitus_service,
            zone_name=zone,
        )
        
        # Generate hints
        all_hints = hints_service.generate_hints(context, force=force)
        
        # Filter by priority
        if priority:
            priority_map = {
                "low": HintPriority.LOW,
                "medium": HintPriority.MEDIUM,
                "high": HintPriority.HIGH,
                "critical": HintPriority.CRITICAL,
            }
            min_priority = priority_map.get(priority.lower(), HintPriority.LOW)
            priority_order = {
                HintPriority.LOW: 0,
                HintPriority.MEDIUM: 1,
                HintPriority.HIGH: 2,
                HintPriority.CRITICAL: 3,
            }
            all_hints = [
                h for h in all_hints
                if priority_order[h.priority] >= priority_order[min_priority]
            ]
        
        # Filter by type
        if hint_type:
            from copilot_core.voice.proactive import HintType
            try:
                filter_type = HintType(hint_type)
                all_hints = [h for h in all_hints if h.hint_type == filter_type]
            except ValueError:
                pass
        
        # Count by priority
        critical_count = sum(1 for h in all_hints if h.priority == HintPriority.CRITICAL)
        queued_count = len(all_hints) - critical_count
        
        return jsonify({
            "status": "ok",
            "hints": [h.to_dict() for h in all_hints],
            "critical_count": critical_count,
            "queued_count": queued_count,
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get voice hints")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/speak", methods=["POST"])
def generate_speech():
    """Generate TTS response for voice output.
    
    Request body:
    {
        "text": "Licht ist an",
        "language": "de",  // optional
        "mood": "relax",  // optional, for tone adjustment
        "format": "mp3"  // optional: mp3, wav, ogg
    }
    
    Response:
    {
        "status": "ok",
        "audio_url": "/api/v1/voice/audio/abc123",
        "text": "Licht ist an",
        "language": "de",
        "duration_seconds": 1.5
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        text = data.get("text")
        if not text:
            return jsonify({
                "status": "error",
                "message": "Missing 'text' in request body"
            }), 400
        
        language = data.get("language", "de")
        audio_format = data.get("format", "mp3")
        
        # Use Styx TTS endpoint if available, otherwise generate a reference ID
        audio_id = f"tts_{hash(text) % 100000}"
        
        return jsonify({
            "status": "ok",
            "audio_url": f"/api/v1/voice/audio/{audio_id}",
            "text": text,
            "language": language,
            "format": audio_format,
            "duration_seconds": len(text) / 15.0,  # Rough estimate
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to generate speech")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/status", methods=["GET"])
def get_status():
    """Get voice system status.
    
    Response:
    {
        "status": "ok",
        "version": "1.0.0",
        "components": {
            "intent_handler": "available",
            "context_builder": "available",
            "proactive_hints": "available",
            "mood_engine": "available",
            "habitus_service": "unavailable"
        },
        "config": {
            "default_language": "de",
            "supported_languages": ["de", "en"],
            "hint_cooldown_seconds": 300,
            "max_hints_per_hour": 6
        }
    }
    """
    try:
        # Check component availability
        components = {}
        
        try:
            handler = _get_intent_handler()
            components["intent_handler"] = "available"
            components["mood_engine"] = "available" if handler.mood_engine else "unavailable"
            components["habitus_service"] = "available" if handler.habitus_service else "unavailable"
        except Exception:
            components["intent_handler"] = "unavailable"
        
        try:
            _get_context_builder()
            components["context_builder"] = "available"
        except Exception:
            components["context_builder"] = "unavailable"
        
        try:
            _get_proactive_hints()
            components["proactive_hints"] = "available"
        except Exception:
            components["proactive_hints"] = "unavailable"
        
        # Get config from proactive hints
        hints_service = _get_proactive_hints()
        config = hints_service.config
        
        return jsonify({
            "status": "ok",
            "version": "1.0.0",
            "components": components,
            "config": {
                "default_language": "de",
                "supported_languages": ["de", "en"],
                "hint_cooldown_seconds": config.hint_cooldown_seconds,
                "max_hints_per_hour": config.max_hints_per_hour,
                "min_priority": config.min_priority.value,
            },
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get voice status")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/zones", methods=["GET"])
def get_zones():
    """Get available zones for voice context.
    
    Response:
    {
        "status": "ok",
        "zones": [
            {
                "name": "wohnzimmer",
                "type": "living_room",
                "aliases": ["wohnzimmer", "wohn", "lounge"],
                "default_action": "Licht anpassen"
            },
            ...
        ]
    }
    """
    try:
        from copilot_core.voice.context_builder import VoiceContextBuilder
        
        zones = []
        zone_aliases = getattr(VoiceContextBuilder, "ZONE_ALIASES", {})
        for zone_name, zone_type in VoiceContextBuilder.ZONE_TYPE_MAP.items():
            zones.append({
                "name": zone_name,
                "type": zone_type,
                "aliases": zone_aliases.get(zone_name, [zone_name]),
            })
        
        return jsonify({
            "status": "ok",
            "zones": zones,
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get zones")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/intents", methods=["GET"])
def get_supported_intents():
    """Get list of supported voice intents.
    
    Response:
    {
        "status": "ok",
        "intents": [
            {
                "type": "light_on",
                "description_de": "Licht einschalten",
                "description_en": "Turn on light",
                "examples_de": ["Mach das Licht an", "Licht an"],
                "examples_en": ["Turn on the light", "Light on"]
            },
            ...
        ]
    }
    """
    try:
        from copilot_core.voice.voice_handler import IntentType
        
        intent_info = {
            IntentType.LIGHT_ON: {
                "description_de": "Licht einschalten",
                "description_en": "Turn on light",
                "examples_de": ["Mach das Licht an", "Licht an", "Schalte das Licht ein"],
                "examples_en": ["Turn on the light", "Light on", "Switch the light on"],
            },
            IntentType.LIGHT_OFF: {
                "description_de": "Licht ausschalten",
                "description_en": "Turn off light",
                "examples_de": ["Mach das Licht aus", "Licht aus"],
                "examples_en": ["Turn off the light", "Light off"],
            },
            IntentType.LIGHT_DIM: {
                "description_de": "Licht dimmen",
                "description_en": "Dim light",
                "examples_de": ["Dimm das Licht", "Mach das Licht dunkler"],
                "examples_en": ["Dim the light", "Make the light darker"],
            },
            IntentType.CLIMATE_SET: {
                "description_de": "Temperatur einstellen",
                "description_en": "Set temperature",
                "examples_de": ["Stell die Temperatur auf 21 Grad", "Heiz auf 22 Grad"],
                "examples_en": ["Set temperature to 21 degrees", "Heat to 22 degrees"],
            },
            IntentType.MEDIA_PLAY: {
                "description_de": "Musik abspielen",
                "description_en": "Play music",
                "examples_de": ["Spiel Musik", "Starte Musik"],
                "examples_en": ["Play music", "Start music"],
            },
            IntentType.MEDIA_PAUSE: {
                "description_de": "Musik pausieren",
                "description_en": "Pause music",
                "examples_de": ["Pause", "Musik pause"],
                "examples_en": ["Pause", "Pause music"],
            },
            IntentType.MEDIA_STOP: {
                "description_de": "Musik stoppen",
                "description_en": "Stop music",
                "examples_de": ["Stopp", "Musik aus"],
                "examples_en": ["Stop", "Stop music"],
            },
            IntentType.STATUS_QUERY: {
                "description_de": "Status abfragen",
                "description_en": "Query status",
                "examples_de": ["Wie ist der Status", "Was läuft"],
                "examples_en": ["What's the status", "What's happening"],
            },
            IntentType.MOOD_QUERY: {
                "description_de": "Stimmung abfragen",
                "description_en": "Query mood",
                "examples_de": ["Wie ist die Stimmung", "Stimmungsbericht"],
                "examples_en": ["How's the mood", "What's the atmosphere"],
            },
            IntentType.TIME_QUERY: {
                "description_de": "Uhrzeit abfragen",
                "description_en": "Query time",
                "examples_de": ["Wie viel Uhr ist es", "Wie spät ist es"],
                "examples_en": ["What time is it", "Time"],
            },
        }
        
        intents = []
        for intent_type in IntentType:
            info = intent_info.get(intent_type, {
                "description_de": intent_type.value,
                "description_en": intent_type.value,
                "examples_de": [],
                "examples_en": [],
            })
            intents.append({
                "type": intent_type.value,
                **info,
            })
        
        return jsonify({
            "status": "ok",
            "intents": intents,
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get supported intents")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


def _get_dialog_machine():
    """Get or create dialog state machine."""
    from copilot_core.voice.dialog_state import get_dialog_machine
    return get_dialog_machine()


# ── HA Assist Bridge ──────────────────────────────────────────────────────────


@bp.route("/ha/assist", methods=["POST"])
def ha_assist_intent():
    """Bridge endpoint for Home Assistant Assist pipeline.

    Accepts HA Assist's transcribed sentence JSON and routes it through
    the canonical process_intent() flow so HA voice commands use the same
    intent resolution, context building, and response generation as all other
    voice callers.

    HA payload (from Assist intent pipeline):
    {
        "text": "Mach das Licht an",        # transcribed sentence (required)
        "language": "de",                  # optional, auto-detected if not provided
        "zone": "wohnzimmer",              # optional, auto-detected if not provided
        "context": {...},                  # optional, existing voice context
        "ha_entity_id": "light.wohnzimmer" # optional, HA entity that triggered
    }

    Response: same as POST /api/v1/voice/intent
    {
        "status": "ok",
        "intent": {...},
        "response": {...},
        "context": {...}
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        text = data.get("text") or data.get("sentence")
        if not text:
            return jsonify({
                "status": "error",
                "message": "Missing 'text' or 'sentence' in request body"
            }), 400

        language = data.get("language")
        zone = data.get("zone")

        handler = _get_intent_handler()
        intent = handler.parse_intent(text, language)

        req_context = data.get("context", {}) if isinstance(data.get("context"), dict) else {}
        user_prefs = req_context.get("user_preferences")
        active_devs = req_context.get("active_devices")

        zone = _resolve_requested_zone(zone, req_context)

        context_builder = _get_context_builder()

        if "context" in data and isinstance(data["context"], dict):
            context = context_builder.build_context(
                mood_engine=handler.mood_engine,
                habitus_service=handler.habitus_service,
                zone_name=zone,
                force_refresh=True,
                user_preferences=user_prefs,
                active_devices=active_devs,
            )
        else:
            context = context_builder.build_context(
                mood_engine=handler.mood_engine,
                habitus_service=handler.habitus_service,
                zone_name=zone,
                force_refresh=data.get("force_context", False),
                user_preferences=user_prefs,
                active_devices=active_devs,
            )

        response = handler.handle_intent(intent, context)

        # Honor language_preference from context
        ctx_lang = getattr(context, 'language_preference', None)
        if ctx_lang:
            response.language = ctx_lang

        return jsonify({
            "status": "ok",
            "intent": intent.to_dict(),
            "response": response.to_dict(),
            "context": context.to_dict(),
            "source": "ha_assist",
        })

    except Exception as e:
        _LOGGER.exception("HA Assist intent processing failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/dialog/state", methods=["GET"])
def get_dialog_state():
    """Get current dialog state."""
    try:
        machine = _get_dialog_machine()
        state = machine.get_state()
        timed_out = machine.check_timeout()
        if timed_out:
            machine.decay()
            state = machine.get_state()
        return jsonify({
            "status": "ok",
            "state": state.state,
            "last_status": _normalize_last_status(state),
            "active_intent": state.active_intent,
            "slot_values": state.slot_values,
            "context_stack_size": len(state.context_stack),
            "last_activity_ts": state.last_activity_ts,
            "session_id": state.session_id,
            "user_id": state.user_id,
            "timed_out": timed_out,
            "confirmation_question": machine.generate_confirmation_question(),
            "clarification_question": machine.generate_clarification_question(),
            "pending_confirmation": state.state == "CONFIRMING" and bool(state.slot_values.get("_confirmation_token")),
            "pending_action_label": state.slot_values.get("_pending_action_label"),
            "pending_action_payload": state.slot_values.get("_pending_action_payload"),
            "confirmation_token": state.slot_values.get("_confirmation_token"),
            "confirmation_expires_at": state.slot_values.get("_confirmation_expires_at"),
        })
    except Exception as e:
        _LOGGER.exception("Failed to get dialog state")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/command/state", methods=["GET"])
def get_command_state():
    """Read the thin session-scoped state surface for the voice command router."""
    try:
        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({
                "status": "error",
                "message": "Query parameter 'session_id' is required",
            }), 400

        machine = _get_dialog_machine()
        if machine.check_timeout():
            machine.decay()
        state = machine.get_state()

        return jsonify({
            "status": "ok",
            "session_id": session_id,
            "state": _serialize_command_state(state, session_id=str(session_id)),
        })
    except Exception as e:
        _LOGGER.exception("Failed to get command state")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/command/confirm", methods=["POST"])
def confirm_command_action():
    """Confirm the currently pending /command action and emit its execution payload."""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        confirmation_token = data.get("confirmation_token")
        if not session_id or not confirmation_token:
            return jsonify({
                "status": "error",
                "message": "Fields 'session_id' and 'confirmation_token' are required",
            }), 400

        machine = _get_dialog_machine()
        pending = _validate_pending_confirmation(
            machine,
            session_id=str(session_id),
            confirmation_token=str(confirmation_token),
        )
        if pending is None:
            return jsonify({
                "status": "error",
                "message": "No matching pending confirmation found",
            }), 400

        action_payload = pending["action_payload"]
        action_label = pending["action_label"]
        state = machine.confirm_action()
        state = machine.merge_metadata({"_last_status": "executed"})
        response = _build_command_follow_through_response(action_payload)

        return jsonify({
            "status": "executed",
            "action": action_label,
            "message": response.tts_text,
            "confirmation_token": confirmation_token,
            "session_state": _serialize_dialog_state(state),
            "response": response.to_dict(),
        })
    except Exception as e:
        _LOGGER.exception("Failed to confirm command action")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/command/reject", methods=["POST"])
def reject_command_action():
    """Reject the currently pending /command action and clear confirmation state."""
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        confirmation_token = data.get("confirmation_token")
        if not session_id or not confirmation_token:
            return jsonify({
                "status": "error",
                "message": "Fields 'session_id' and 'confirmation_token' are required",
            }), 400

        machine = _get_dialog_machine()
        pending = _validate_pending_confirmation(
            machine,
            session_id=str(session_id),
            confirmation_token=str(confirmation_token),
        )
        if pending is None:
            return jsonify({
                "status": "error",
                "message": "No matching pending confirmation found",
            }), 400

        action_label = pending["action_label"]
        state = machine.cancel_action()
        state = machine.merge_metadata({"_last_status": "rejected"})
        return jsonify({
            "status": "rejected",
            "action": action_label,
            "message": "Okay, ich verwerfe die angefragte Aktion.",
            "confirmation_token": confirmation_token,
            "session_state": _serialize_dialog_state(state),
        })
    except Exception as e:
        _LOGGER.exception("Failed to reject command action")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/dialog/activate", methods=["POST"])
def activate_dialog_intent():
    """Activate a new dialog intent, preserving any current active context."""
    try:
        data = request.get_json(silent=True) or {}
        intent = data.get("intent")
        if not intent:
            return jsonify({"status": "error", "message": "Missing 'intent'"}), 400
        machine = _get_dialog_machine()
        state = machine.activate_intent(
            intent=str(intent),
            slots=data.get("slots") if isinstance(data.get("slots"), dict) else {},
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
        )
        return jsonify({
            "status": "ok",
            "state": state.state,
            "active_intent": state.active_intent,
            "slot_values": state.slot_values,
            "context_stack_size": len(state.context_stack),
            "last_activity_ts": state.last_activity_ts,
            "session_id": state.session_id,
            "user_id": state.user_id,
        })
    except Exception as e:
        _LOGGER.exception("Failed to activate dialog intent")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/dialog/confirm", methods=["POST"])
def confirm_dialog_action():
    """Confirm or cancel the pending dialog action."""
    try:
        data = request.get_json(silent=True) or {}
        confirmed = bool(data.get("confirmed", False))
        machine = _get_dialog_machine()
        state = machine.confirm_action() if confirmed else machine.cancel_action()
        return jsonify({
            "status": "ok",
            "state": state.state,
            "active_intent": state.active_intent,
            "slot_values": state.slot_values,
            "context_stack_size": len(state.context_stack),
            "last_activity_ts": state.last_activity_ts,
            "session_id": state.session_id,
            "user_id": state.user_id,
        })
    except Exception as e:
        _LOGGER.exception("Failed to confirm dialog action")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/dialog/clarify", methods=["POST"])
def clarify_dialog():
    """Set a clarification prompt and transition to clarifying state."""
    try:
        data = request.get_json(silent=True) or {}
        clarification_text = str(data.get("clarification_text", "Kannst du das bitte genauer beschreiben?"))
        machine = _get_dialog_machine()
        state = machine.set_clarifying(clarification_text)
        return jsonify({
            "status": "ok",
            "state": state.state,
            "active_intent": state.active_intent,
            "slot_values": state.slot_values,
            "context_stack_size": len(state.context_stack),
            "last_activity_ts": state.last_activity_ts,
            "session_id": state.session_id,
            "user_id": state.user_id,
            "clarification_question": machine.generate_clarification_question(),
        })
    except Exception as e:
        _LOGGER.exception("Failed to clarify dialog")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/dialog/reset", methods=["POST"])
def reset_dialog():
    """Reset dialog state to IDLE."""
    try:
        machine = _get_dialog_machine()
        state = machine.reset()
        return jsonify({"status": "ok", "state": state.state})
    except Exception as e:
        _LOGGER.exception("Failed to reset dialog state")
        return jsonify({"status": "error", "message": str(e)}), 500


# Register blueprint with app
def init_voice_api(app):
    """Initialize voice API endpoints."""
    app.register_blueprint(bp)
    _LOGGER.info("Voice API endpoints registered")
