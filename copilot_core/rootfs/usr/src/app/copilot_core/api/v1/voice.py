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
import logging
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, jsonify, request

from copilot_core.voice.voice_handler import VoiceIntentHandler, VoiceIntent, IntentType, VoiceResponse
from copilot_core.voice.context_builder import VoiceContextBuilder, VoiceContext
from copilot_core.voice.proactive import ProactiveVoiceHints, HintConfig, HintPriority

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("voice", __name__, url_prefix="/voice")

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
        
        # Get handler and parse intent
        handler = _get_intent_handler()
        intent = handler.parse_intent(text, language)
        
        # Build or use existing context
        context_builder = _get_context_builder()
        
        if "context" in data and isinstance(data["context"], dict):
            # Use provided context (simplified reconstruction)
            context = context_builder.build_context(
                mood_engine=handler.mood_engine,
                habitus_service=handler.habitus_service,
                zone_name=zone,
                force_refresh=True,
            )
        else:
            # Build fresh context
            context = context_builder.build_context(
                mood_engine=handler.mood_engine,
                habitus_service=handler.habitus_service,
                zone_name=zone,
                force_refresh=data.get("force_context", False),
            )
        
        # Handle intent
        response = handler.handle_intent(intent, context)
        
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
        
        # TODO: Integrate with TTS service
        # For now, return placeholder
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


# Register blueprint with app
def init_voice_api(app):
    """Initialize voice API endpoints."""
    app.register_blueprint(bp)
    _LOGGER.info("Voice API endpoints registered")
