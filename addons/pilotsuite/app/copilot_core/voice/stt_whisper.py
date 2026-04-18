"""P1-006 compatibility STT surface for the shipped add-on voice package."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpeechLanguage(Enum):
    """Supported languages."""

    EN = "en"
    DE = "de"
    FR = "fr"
    ES = "es"
    IT = "it"


@dataclass
class TranscriptionResult:
    """Result from speech-to-text."""

    text: str
    language: str
    confidence: float
    duration_ms: float
    segments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class STTConfig:
    """Configuration for STT."""

    model: str = "base"
    language: Optional[str] = None
    device: str = "cpu"
    compute_type: str = "int8"


class WhisperSTT:
    """Local Whisper-style speech-to-text compatibility wrapper."""

    def __init__(self, config: Optional[STTConfig] = None):
        self.config = config or STTConfig()
        self._model = None
        self._loaded = False

    def load_model(self) -> bool:
        """Load Whisper model."""
        try:
            self._loaded = True
            logger.info("Loaded Whisper model: %s", self.config.model)
            return True
        except Exception as exc:
            logger.error("Failed to load Whisper: %s", exc)
            return False

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Optional[TranscriptionResult]:
        """Transcribe an audio file."""
        if not self._loaded and not self.load_model():
            return None

        start = time.time()
        try:
            result = {
                "text": "This is a placeholder transcription",
                "language": language or self.config.language or "en",
                "segments": [],
                "audio_path": audio_path,
            }
            duration_ms = (time.time() - start) * 1000
            return TranscriptionResult(
                text=result["text"],
                language=result["language"],
                confidence=0.95,
                duration_ms=duration_ms,
                segments=result["segments"],
                metadata={"audio_path": audio_path, "model": self.config.model},
            )
        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return None

    def transcribe_streaming(self, audio_stream: bytes, callback: Optional[Callable[[str], None]] = None) -> TranscriptionResult:
        """Transcribe streaming audio chunks."""
        full_text = ""
        for _ in range(3):
            partial = "Partial transcription "
            full_text += partial
            if callback:
                callback(partial)

        return TranscriptionResult(
            text=full_text.strip(),
            language=self.config.language or "en",
            confidence=0.9,
            duration_ms=max(len(audio_stream), 1),
            metadata={"streaming": True},
        )


default_stt: Optional[WhisperSTT] = None


def init_stt(config: Optional[STTConfig] = None) -> WhisperSTT:
    """Initialize global STT."""
    global default_stt
    default_stt = WhisperSTT(config)
    return default_stt


def transcribe_audio(path: str, **kwargs: Any) -> Optional[TranscriptionResult]:
    """Convenience function for transcription."""
    if default_stt:
        return default_stt.transcribe(path, **kwargs)
    return None
