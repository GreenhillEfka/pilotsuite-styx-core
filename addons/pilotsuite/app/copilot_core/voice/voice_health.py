"""
Voice health block helper for health/readiness endpoints.

Returns the same capability truth block used by GET /api/v1/voice/status
without introducing circular dependencies on the voice blueprint.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable

from flask import has_app_context

from copilot_core.voice.runtime_access import get_voice_runtime

_DEFAULT_STT_RUNTIME = {
    "available": False,
    "engine": "whisper",
    "available_backends": [],
}

_DEFAULT_TTS_RUNTIME = {
    "available": False,
    "engine": "piper",
    "available_backends": [],
}

_DEFAULT_NLU_RUNTIME = {
    "available": False,
    "engine": "rule_based",
    "supported_languages": ["de", "en"],
}


_DEFAULT_INTENT_HANDLER_RUNTIME = {
    "available": False,
    "engine": "voice_handler",
    "default_language": "de",
}


def get_voice_health_block() -> dict:
    """Build the voice capability truth block for health/readiness endpoints.

    Detects Whisper STT and Piper TTS availability at call time.
    Gracefully degrades when backends are unavailable.
    """
    runtime_truth = _resolve_runtime_voice_truth()
    if runtime_truth is None:
        stt_runtime = _backend_runtime_payload(
            "copilot_core.voice.stt_whisper",
            "WhisperSTT",
            "can_transcribe",
            default_payload=_DEFAULT_STT_RUNTIME,
        )
        tts_runtime = _backend_runtime_payload(
            "copilot_core.voice.tts_piper",
            "PiperTTS",
            "can_synthesize",
            default_payload=_DEFAULT_TTS_RUNTIME,
        )
        nlu_runtime = _component_runtime_payload(
            "copilot_core.voice.nlu_engine",
            "NLUEngine",
            default_payload=_DEFAULT_NLU_RUNTIME,
        )
        intent_handler_runtime = _component_runtime_payload(
            "copilot_core.voice.voice_handler",
            "VoiceIntentHandler",
            default_payload=_DEFAULT_INTENT_HANDLER_RUNTIME,
        )
        intent_handler_available = _component_available(
            "copilot_core.voice.voice_handler",
            "VoiceIntentHandler",
        )
    else:
        stt_runtime = runtime_truth["stt_runtime"]
        tts_runtime = runtime_truth["tts_runtime"]
        nlu_runtime = runtime_truth["nlu_runtime"]
        intent_handler_runtime = runtime_truth["intent_handler_runtime"]
        intent_handler_available = runtime_truth["intent_handler_available"]

    stt_available = bool(stt_runtime.get("available"))
    tts_available = bool(tts_runtime.get("available"))
    nlu_available = bool(nlu_runtime.get("available"))

    available = []
    if stt_available:
        available.append(
            {
                "type": "stt",
                "backend": str(stt_runtime.get("engine") or "whisper"),
                "status": "available",
            }
        )
    if tts_available:
        available.append(
            {
                "type": "tts",
                "backend": str(tts_runtime.get("engine") or "piper"),
                "status": "available",
            }
        )

    return {
        "can_transcribe": stt_available,
        "can_synthesize": tts_available,
        "can_speak": tts_available,
        "can_dialog": bool(intent_handler_available and stt_available and tts_available and nlu_available),
        "available_backends": available,
        "runtime": {
            "stt": dict(stt_runtime),
            "tts": dict(tts_runtime),
            "nlu": dict(nlu_runtime),
            "intent_handler": dict(intent_handler_runtime),
        },
    }


def _resolve_runtime_voice_truth() -> dict[str, Any] | None:
    if not has_app_context():
        return None

    try:
        runtime = get_voice_runtime()
    except Exception:
        return None

    return {
        "stt_runtime": _resolve_runtime_backend_payload(
            runtime.get_stt_engine,
            "can_transcribe",
            default_payload=_DEFAULT_STT_RUNTIME,
        ),
        "tts_runtime": _resolve_runtime_backend_payload(
            runtime.get_tts_engine,
            "can_synthesize",
            default_payload=_DEFAULT_TTS_RUNTIME,
        ),
        "nlu_runtime": _resolve_runtime_component_payload(
            runtime.get_nlu_engine,
            default_payload=_DEFAULT_NLU_RUNTIME,
        ),
        "intent_handler_runtime": _resolve_runtime_intent_handler_payload(
            runtime.get_intent_handler,
            default_payload=_DEFAULT_INTENT_HANDLER_RUNTIME,
        ),
        "intent_handler_available": _resolve_runtime_component(runtime.get_intent_handler),
    }


def _resolve_runtime_component(factory: Callable[[], Any], method_name: str | None = None) -> bool:
    try:
        component = factory()
    except Exception:
        return False

    if method_name is not None:
        return _resolve_backend_availability(component, method_name)

    return component is not None


def _resolve_runtime_backend_payload(
    factory: Callable[[], Any],
    method_name: str,
    *,
    default_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        engine = factory()
    except Exception:
        return dict(default_payload)

    return _resolve_backend_payload(engine, method_name, default_payload=default_payload)


def _resolve_runtime_component_payload(
    factory: Callable[[], Any],
    *,
    default_payload: dict[str, Any],
) -> dict[str, Any]:
    if not _resolve_runtime_component(factory):
        return dict(default_payload)

    payload = dict(default_payload)
    payload["available"] = True
    return payload


def _resolve_runtime_intent_handler_payload(
    factory: Callable[[], Any],
    *,
    default_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        handler = factory()
    except Exception:
        return dict(default_payload)

    payload = dict(default_payload)
    payload["available"] = True
    payload["default_language"] = getattr(handler, "default_language", default_payload.get("default_language", "de"))
    return payload


def _component_runtime_payload(
    module_path: str,
    class_name: str,
    *,
    default_payload: dict[str, Any],
) -> dict[str, Any]:
    if not _component_available(module_path, class_name):
        return dict(default_payload)

    payload = dict(default_payload)
    payload["available"] = True
    return payload


def _backend_runtime_payload(
    module_path: str,
    class_name: str,
    method_name: str,
    *,
    default_payload: dict[str, Any],
) -> dict[str, Any]:
    backend_class = _load_backend_class(module_path, class_name)
    if backend_class is None:
        return dict(default_payload)

    try:
        engine = backend_class()
    except Exception:
        return dict(default_payload)

    return _resolve_backend_payload(engine, method_name, default_payload=default_payload)


def _component_available(module_path: str, class_name: str) -> bool:
    component_class = _load_backend_class(module_path, class_name)
    if component_class is None:
        return False

    try:
        return component_class() is not None
    except Exception:
        return False


def _resolve_backend_payload(engine: Any, method_name: str, *, default_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(default_payload)

    try:
        if hasattr(engine, "availability_payload"):
            runtime_payload = engine.availability_payload()
            if isinstance(runtime_payload, dict) and "available" in runtime_payload:
                payload.update(runtime_payload)
                return payload

        payload["available"] = _resolve_backend_availability(engine, method_name)
    except Exception:
        return payload

    return payload


def _resolve_backend_availability(engine: Any, method_name: str) -> bool:
    """Read backend availability from the current engine surface.

    Prefer the shipped availability payload / helpers and keep the older
    `can_*` compatibility probe only as a final fallback.
    """
    try:
        if hasattr(engine, "availability_payload"):
            payload = engine.availability_payload()
            if isinstance(payload, dict) and "available" in payload:
                return bool(payload["available"])

        checker = getattr(engine, "is_available", None)
        if callable(checker):
            return bool(checker())

        checker = getattr(engine, method_name, None)
        if callable(checker):
            return bool(checker())

        available_backends = getattr(engine, "available_backends", None)
        if callable(available_backends):
            return bool(available_backends())
    except Exception:
        return False

    return False


def _load_backend_class(module_path: str, class_name: str):
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except Exception:
        return None


def _empty_block() -> dict:
    return {
        "can_transcribe": False,
        "can_synthesize": False,
        "can_speak": False,
        "can_dialog": False,
        "available_backends": [],
        "runtime": {
            "stt": dict(_DEFAULT_STT_RUNTIME),
            "tts": dict(_DEFAULT_TTS_RUNTIME),
            "nlu": dict(_DEFAULT_NLU_RUNTIME),
            "intent_handler": dict(_DEFAULT_INTENT_HANDLER_RUNTIME),
        },
    }
