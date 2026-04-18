"""Voice API Endpoints for Home Assistant Voice Assistant Integration.

Provides REST API for voice intent handling, context building, and proactive hints.

Endpoints:
- POST /api/v1/voice/intent - Process voice intent
- POST /api/v1/voice/transcribe - Transcribe audio through Whisper compatibility
- POST /api/v1/voice/synthesize - Synthesize audio through Piper compatibility
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
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request, send_file

from copilot_core.voice.voice_handler import VoiceIntent, IntentType
from copilot_core.voice.context_builder import VoiceContext, VoiceContextBuilder
from copilot_core.voice.proactive import HintConfig, HintPriority
from copilot_core.voice.runtime_access import get_voice_runtime

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


def _get_generated_audio_cache() -> Dict[str, str]:
    """Get the bounded generated-audio cache for `/voice/speak`."""
    return get_voice_runtime().get_generated_audio_cache()


def _get_intent_handler():
    """Resolve the shared voice intent handler from the runtime seam."""
    return get_voice_runtime().get_intent_handler()


def _get_context_builder():
    """Resolve the shared voice context builder from the runtime seam."""
    return get_voice_runtime().get_context_builder()


def _get_context_runtime():
    """Resolve the shared voice context runtime bundle from the runtime seam."""
    return get_voice_runtime().get_context_runtime()


def _get_stt_engine():
    """Resolve the shared STT engine from the runtime seam."""
    return get_voice_runtime().get_stt_engine()


def _get_tts_engine():
    """Resolve the shared TTS engine from the runtime seam."""
    return get_voice_runtime().get_tts_engine()


def _get_nlu_engine():
    """Resolve the shared NLU engine from the runtime seam."""
    return get_voice_runtime().get_nlu_engine()


def _get_command_router():
    """Resolve the shared voice command router from the runtime seam."""
    return get_voice_runtime().get_command_router()


def _get_command_flow():
    """Resolve the shared voice command-flow service from the runtime seam."""
    return get_voice_runtime().get_command_flow()


def _get_dialog_flow():
    """Resolve the shared voice dialog-flow service from the runtime seam."""
    return get_voice_runtime().get_dialog_flow()


def _cache_generated_audio(audio_path: str) -> str:
    """Cache a generated audio file path and return its stable route id."""
    return get_voice_runtime().cache_generated_audio(audio_path)


def _build_voice_runtime_status() -> Dict[str, Any]:
    """Summarize the bounded STT/TTS runtime exposed by this API surface."""
    runtime: Dict[str, Any] = {}

    try:
        stt_engine = _get_stt_engine()
        if hasattr(stt_engine, "availability_payload"):
            runtime["stt"] = stt_engine.availability_payload()
        else:
            runtime["stt"] = {
                "available": True,
                "engine": "whisper",
                "model": stt_engine.config.model,
                "default_language": stt_engine.config.language or "de",
            }
    except Exception:
        runtime["stt"] = {
            "available": False,
            "engine": "whisper",
            "available_backends": [],
        }

    try:
        tts_engine = _get_tts_engine()
        if hasattr(tts_engine, "availability_payload"):
            runtime["tts"] = tts_engine.availability_payload()
        else:
            runtime["tts"] = {
                "available": True,
                "engine": tts_engine.config.engine,
                "voice": tts_engine.config.voice,
            }
    except Exception:
        runtime["tts"] = {
            "available": False,
            "engine": "piper",
            "available_backends": [],
        }

    try:
        _get_nlu_engine()
        runtime["nlu"] = {
            "available": True,
            "engine": "rule_based",
            "supported_languages": ["de", "en"],
        }
    except Exception:
        runtime["nlu"] = {
            "available": False,
            "engine": "rule_based",
            "supported_languages": [],
        }

    return runtime


def _build_voice_capabilities(runtime: Dict[str, Any], *, intent_handler_available: bool) -> Dict[str, bool]:
    """Project backend/runtime truth into one bounded HA-consumable capability gate."""
    stt_available = bool(runtime.get("stt", {}).get("available"))
    tts_available = bool(runtime.get("tts", {}).get("available"))
    nlu_available = bool(runtime.get("nlu", {}).get("available"))

    return {
        "can_transcribe": stt_available,
        "can_synthesize": tts_available,
        "can_speak": tts_available,
        "can_dialog": bool(intent_handler_available and stt_available and tts_available and nlu_available),
    }


def _build_voice_status_config() -> Dict[str, Any]:
    """Return stable voice config metadata even when proactive hints are unavailable."""
    try:
        config = _get_proactive_hints().config
    except Exception:
        config = HintConfig()

    return {
        "default_language": "de",
        "supported_languages": ["de", "en"],
        "hint_cooldown_seconds": config.hint_cooldown_seconds,
        "max_hints_per_hour": config.max_hints_per_hour,
        "min_priority": config.min_priority.value,
    }


def _collect_available_voice_backends(*, skip: Optional[str] = None) -> list[str]:
    """Collect other currently available voice backends for degraded responses."""
    factories = [
        ("stt", "whisper", _get_stt_engine),
        ("tts", "piper", _get_tts_engine),
    ]
    available: list[str] = []
    for kind, fallback_label, factory in factories:
        if kind == skip:
            continue
        try:
            engine = factory()
            if hasattr(engine, "available_backends"):
                available.extend(engine.available_backends())
            elif hasattr(engine, "is_available") and engine.is_available():
                available.append(fallback_label)
        except Exception:
            continue
    return sorted(set(available))


def _voice_backend_unavailable_response(*, message: str, detail: str, backend: str, available_backends: Optional[list[str]] = None):
    """Build the stable degraded-path contract for missing voice backends."""
    return jsonify({
        "status": "error",
        "message": message,
        "error": "service_unavailable",
        "code": "backend_missing",
        "detail": detail,
        "backend": backend,
        "available_backends": sorted(set(available_backends or [])),
        "retry_after_seconds": None,
    }), 503


def _get_proactive_hints():
    """Resolve proactive voice hints from the runtime seam."""
    return get_voice_runtime().get_proactive_hints()


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
        context_runtime = _get_context_runtime()

        if "context" in data and isinstance(data["context"], dict):
            # Use provided context (simplified reconstruction)
            context = context_builder.build_context(
                context_runtime=context_runtime,
                zone_name=zone,
                force_refresh=True,
                user_preferences=user_prefs,
                active_devices=active_devs,
            )
        else:
            # Build fresh context
            context = context_builder.build_context(
                context_runtime=context_runtime,
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

        req_context = data.get("context", {}) if isinstance(data.get("context"), dict) else {}
        zone = _resolve_requested_zone(data.get("zone_id") or data.get("zone"), req_context)

        response_payload = _get_command_flow().process(
            utterance=utterance,
            confidence=confidence,
            intent_candidates=intent_candidates,
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            zone_id=zone,
            request_context=req_context,
        )
        return jsonify(response_payload.to_dict())

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
        context_runtime = _get_context_runtime()

        context = context_builder.build_context(
            context_runtime=context_runtime,
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
        context_runtime = _get_context_runtime()

        context = context_builder.build_context(
            context_runtime=context_runtime,
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


@bp.route("/transcribe", methods=["POST"])
def transcribe_speech():
    """Transcribe audio through the shipped Whisper compatibility surface."""
    try:
        data = request.get_json(silent=True) or {}
        audio_path = data.get("audio_path") or "memory://voice-input"
        language = data.get("language", "de")

        try:
            stt_engine = _get_stt_engine()
        except Exception as exc:
            _LOGGER.warning("Whisper STT bootstrap unavailable: %s", exc)
            return _voice_backend_unavailable_response(
                message="Voice transcription unavailable",
                detail="Whisper STT backend not available",
                backend="whisper",
                available_backends=_collect_available_voice_backends(skip="stt"),
            )

        result = stt_engine.transcribe(audio_path, language=language)
        if not result:
            return _voice_backend_unavailable_response(
                message="Voice transcription unavailable",
                detail="Whisper STT backend not available",
                backend="whisper",
                available_backends=_collect_available_voice_backends(skip="stt"),
            )

        return jsonify({
            "status": "ok",
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "duration_ms": result.duration_ms,
            "metadata": result.metadata,
        })
    except Exception as e:
        _LOGGER.exception("Failed to transcribe speech")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/synthesize", methods=["POST"])
def synthesize_speech_route():
    """Synthesize speech through the shipped Piper compatibility surface."""
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text")
        if not text:
            return jsonify({
                "status": "error",
                "message": "Missing 'text' in request body"
            }), 400

        voice = data.get("voice")
        try:
            tts_engine = _get_tts_engine()
        except Exception as exc:
            _LOGGER.warning("Piper TTS bootstrap unavailable: %s", exc)
            return _voice_backend_unavailable_response(
                message="Voice synthesis unavailable",
                detail="Piper TTS backend not available",
                backend="piper",
                available_backends=_collect_available_voice_backends(skip="tts"),
            )

        result = tts_engine.synthesize(text, voice=voice)
        if not result:
            return _voice_backend_unavailable_response(
                message="Voice synthesis unavailable",
                detail="Piper TTS backend not available",
                backend="piper",
                available_backends=_collect_available_voice_backends(skip="tts"),
            )

        return jsonify({
            "status": "ok",
            "audio_path": result.audio_path,
            "text": result.text,
            "voice": result.voice,
            "duration_seconds": result.duration_seconds,
            "generation_time_ms": result.generation_time_ms,
        })
    except Exception as e:
        _LOGGER.exception("Failed to synthesize speech")
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
        voice = data.get("voice")

        try:
            tts_engine = _get_tts_engine()
        except Exception as exc:
            _LOGGER.warning("Piper TTS bootstrap unavailable for /speak: %s", exc)
            return _voice_backend_unavailable_response(
                message="Voice synthesis unavailable",
                detail="Piper TTS backend not available",
                backend="piper",
                available_backends=_collect_available_voice_backends(skip="tts"),
            )

        result = tts_engine.synthesize(text, voice=voice)
        if not result:
            return _voice_backend_unavailable_response(
                message="Voice synthesis unavailable",
                detail="Piper TTS backend not available",
                backend="piper",
                available_backends=_collect_available_voice_backends(skip="tts"),
            )

        audio_path = Path(result.audio_path)
        audio_id = _cache_generated_audio(result.audio_path)
        audio_format = audio_path.suffix.lstrip(".").lower() or "wav"

        return jsonify({
            "status": "ok",
            "audio_url": f"/api/v1/voice/audio/{audio_id}",
            "text": result.text,
            "language": language,
            "format": audio_format,
            "duration_seconds": result.duration_seconds,
        })

    except Exception as e:
        _LOGGER.exception("Failed to generate speech")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/audio/<audio_id>", methods=["GET"])
def get_generated_audio(audio_id: str):
    """Serve a generated audio artifact previously created via `/voice/speak`."""
    try:
        audio_path = _get_generated_audio_cache().get(audio_id)
        if not audio_path:
            return jsonify({
                "status": "error",
                "message": "Audio not found"
            }), 404

        path = Path(audio_path)
        if not path.exists():
            _get_generated_audio_cache().pop(audio_id, None)
            return jsonify({
                "status": "error",
                "message": "Audio not found"
            }), 404

        mimetype = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
        }.get(path.suffix.lower(), "application/octet-stream")

        return send_file(
            path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=path.name,
        )

    except Exception as e:
        _LOGGER.exception("Failed to fetch generated speech audio")
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
            "habitus_service": "unavailable",
            "stt_engine": "available",
            "tts_engine": "available",
            "nlu_engine": "available"
        },
        "runtime": {
            "stt": {"available": true, "engine": "whisper"},
            "tts": {"available": true, "engine": "piper"},
            "nlu": {"available": true, "engine": "rule_based"}
        },
        "capabilities": {
            "can_transcribe": true,
            "can_synthesize": true,
            "can_speak": true,
            "can_dialog": true
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
        intent_handler_available = False
        
        try:
            handler = _get_intent_handler()
            components["intent_handler"] = "available"
            components["mood_engine"] = "available" if handler.mood_engine else "unavailable"
            components["habitus_service"] = "available" if handler.habitus_service else "unavailable"
            intent_handler_available = True
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
        
        runtime = _build_voice_runtime_status()
        components["stt_engine"] = "available" if runtime["stt"]["available"] else "unavailable"
        components["tts_engine"] = "available" if runtime["tts"]["available"] else "unavailable"
        components["nlu_engine"] = "available" if runtime["nlu"]["available"] else "unavailable"
        capabilities = _build_voice_capabilities(runtime, intent_handler_available=intent_handler_available)

        return jsonify({
            "status": "ok",
            "version": "1.0.0",
            "components": components,
            "runtime": runtime,
            "capabilities": capabilities,
            "config": _build_voice_status_config(),
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
    """Resolve the shared dialog state machine from the runtime seam."""
    return get_voice_runtime().get_dialog_machine()


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
        context_runtime = _get_context_runtime()

        if "context" in data and isinstance(data["context"], dict):
            context = context_builder.build_context(
                context_runtime=context_runtime,
                zone_name=zone,
                force_refresh=True,
                user_preferences=user_prefs,
                active_devices=active_devs,
            )
        else:
            context = context_builder.build_context(
                context_runtime=context_runtime,
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
        return jsonify(_get_dialog_flow().get_state().to_dict())
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

        return jsonify(_get_command_flow().get_state(session_id=str(session_id)).to_dict())
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
        try:
            # Delegate through command_flow seam (which now delegates to dialog_flow for transition mechanics)
            return jsonify(
                _get_command_flow().confirm(
                    session_id=str(session_id),
                    confirmation_token=str(confirmation_token),
                ).to_dict()
            )
        except ValueError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400
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
        try:
            # Delegate through command_flow seam (which now delegates to dialog_flow for transition mechanics)
            return jsonify(
                _get_command_flow().reject(
                    session_id=str(session_id),
                    confirmation_token=str(confirmation_token),
                ).to_dict()
            )
        except ValueError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400
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
        return jsonify(
            _get_dialog_flow().activate_intent(
                intent=str(intent),
                slots=data.get("slots") if isinstance(data.get("slots"), dict) else {},
                session_id=data.get("session_id"),
                user_id=data.get("user_id"),
            ).to_dict()
        )
    except Exception as e:
        _LOGGER.exception("Failed to activate dialog intent")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/dialog/confirm", methods=["POST"])
def confirm_dialog_action():
    """Confirm or cancel the pending dialog action."""
    try:
        data = request.get_json(silent=True) or {}
        return jsonify(
            _get_dialog_flow().confirm_action(
                confirmed=bool(data.get("confirmed", False)),
            ).to_dict()
        )
    except Exception as e:
        _LOGGER.exception("Failed to confirm dialog action")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/dialog/clarify", methods=["POST"])
def clarify_dialog():
    """Set a clarification prompt and transition to clarifying state."""
    try:
        data = request.get_json(silent=True) or {}
        clarification_text = str(data.get("clarification_text", "Kannst du das bitte genauer beschreiben?"))
        return jsonify(_get_dialog_flow().clarify(clarification_text=clarification_text).to_dict())
    except Exception as e:
        _LOGGER.exception("Failed to clarify dialog")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/dialog/reset", methods=["POST"])
def reset_dialog():
    """Reset dialog state to IDLE."""
    try:
        return jsonify(_get_dialog_flow().reset().to_dict())
    except Exception as e:
        _LOGGER.exception("Failed to reset dialog state")
        return jsonify({"status": "error", "message": str(e)}), 500


# Register blueprint with app
def init_voice_api(app):
    """Initialize voice API endpoints."""
    app.register_blueprint(bp)
    _LOGGER.info("Voice API endpoints registered")
