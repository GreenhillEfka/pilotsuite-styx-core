"""
Voice health block helper for health/readiness endpoints.

Returns the same capability truth block used by GET /api/v1/voice/status
without introducing circular dependencies on the voice blueprint.
"""
from __future__ import annotations

import importlib


def get_voice_health_block() -> dict:
    """Build the voice capability truth block for health/readiness endpoints.

    Detects Whisper STT and Piper TTS availability at call time.
    Gracefully degrades when backends are unavailable.
    """
    stt_available = _backend_available(
        "copilot_core.voice.stt_whisper",
        "WhisperSTT",
        "can_transcribe",
    )
    tts_available = _backend_available(
        "copilot_core.voice.tts_piper",
        "PiperTTS",
        "can_synthesize",
    )

    available = []
    if stt_available:
        available.append({"type": "stt", "backend": "whisper", "status": "available"})
    if tts_available:
        available.append({"type": "tts", "backend": "piper", "status": "available"})

    return {
        "can_transcribe": stt_available,
        "can_synthesize": tts_available,
        "can_speak": tts_available,
        "available_backends": available,
    }


def _backend_available(module_path: str, class_name: str, method_name: str) -> bool:
    backend_class = _load_backend_class(module_path, class_name)
    if backend_class is None:
        return False

    try:
        engine = backend_class()
        checker = getattr(engine, method_name)
        return bool(checker())
    except Exception:
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
        "available_backends": [],
    }
