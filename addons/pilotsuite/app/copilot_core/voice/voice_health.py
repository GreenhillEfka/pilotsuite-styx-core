"""
Voice health block helper for health/readiness endpoints.

Returns the same capability truth block used by GET /api/v1/voice/status
without introducing circular dependencies on the voice blueprint.
"""
from __future__ import annotations


def get_voice_health_block() -> dict:
    """Build the voice capability truth block for health/readiness endpoints.

    Detects Whisper STT and Piper TTS availability at call time.
    Gracefully degrades when backends are unavailable.
    """
    try:
        from copilot_core.voice.stt_whisper import WhisperSTT
        from copilot_core.voice.tts_piper import PiperTTS
    except Exception:
        return _empty_block()

    try:
        stt_engine = WhisperSTT()
        stt_available = stt_engine.can_transcribe()
    except Exception:
        stt_available = False

    try:
        tts_engine = PiperTTS()
        tts_available = tts_engine.can_synthesize()
    except Exception:
        tts_available = False

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


def _empty_block() -> dict:
    return {
        "can_transcribe": False,
        "can_synthesize": False,
        "can_speak": False,
        "available_backends": [],
    }
