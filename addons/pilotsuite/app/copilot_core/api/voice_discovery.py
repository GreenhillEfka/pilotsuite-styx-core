"""Shared public voice discovery metadata.

Keeps app-level capability surfaces aligned with the restored public voice API.
"""
from __future__ import annotations

from typing import Any

VOICE_DISCOVERY_ENDPOINTS: tuple[str, ...] = (
    "/api/v1/voice/intent",
    "/api/v1/voice/transcribe",
    "/api/v1/voice/synthesize",
    "/api/v1/voice/speak",
    "/api/v1/voice/status",
    "/api/v1/voice/audio/<audio_id>",
    "/api/v1/voice/zones",
    "/api/v1/voice/intents",
)

VOICE_DISCOVERY_FEATURES: tuple[str, ...] = (
    "bounded intent routing",
    "whisper-compatible transcription",
    "piper-compatible synthesis",
    "retrievable speak-audio artifacts",
    "runtime status truth",
    "capability-gated consumer branching",
)


def voice_capabilities_module() -> dict[str, Any]:
    return {
        "enabled": True,
        "version": "1.0.0",
        "description": "Public voice runtime surface with truthful status and route discovery",
        "status_surface": "/api/v1/voice/status",
        "endpoints": list(VOICE_DISCOVERY_ENDPOINTS),
        "features": list(VOICE_DISCOVERY_FEATURES),
    }
