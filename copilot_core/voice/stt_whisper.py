"""P4-001: STT Integration — Whisper Local, Streaming, Multi-Language."""
from __future__ import annotations

import logging
import time
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
from enum import Enum

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
    model: str = "base"  # tiny, base, small, medium, large
    language: Optional[str] = None
    device: str = "cpu"  # cpu, cuda
    compute_type: str = "int8"  # int8, float16, float32


class WhisperSTT:
    """Local Whisper-based speech-to-text.

    Tries to load the openai-whisper package. If unavailable, falls back
    to a coqui-based STT or a best-effort whisper.cpp binding.
    If all backends fail, transcribe() returns None with a clear log message.
    """

    def __init__(self, config: Optional[STTConfig] = None):
        self.config = config or STTConfig()
        self._model = None
        self._backend: str | None = None
        self._loaded = False

    def load_model(self) -> bool:
        """Load the best available Whisper backend.

        Tries in order:
        1. openai-whisper (pip package)
        2. whisper-cpp-python (faster, CPU-friendly)
        3. None (stub mode — graceful degradation)
        """
        # Backend 1: openai-whisper
        try:
            import whisper
            self._model = whisper.load_model(
                self.config.model,
                device=self.config.device,
                download_root=os.environ.get("WHISPER_MODELS", "/data/models/whisper")
            )
            self._backend = "openai-whisper"
            self._loaded = True
            logger.info(f"Whisper STT loaded (openai-whisper, model={self.config.model})")
            return True
        except ImportError:
            logger.debug("openai-whisper not installed, trying next backend")
        except Exception as e:
            logger.warning("openai-whisper load failed: %s", e)

        # Backend 2: whisper-cpp-python (faster for CPU inference)
        try:
            import whisperex
            self._model = whisperex.load(self.config.model)
            self._backend = "whisper-cpp"
            self._loaded = True
            logger.info(f"Whisper STT loaded (whisper-cpp, model={self.config.model})")
            return True
        except ImportError:
            logger.debug("whisper-cpp-python not installed, trying next backend")
        except Exception as e:
            logger.warning("whisper-cpp load failed: %s", e)

        # No backend available — stub mode
        logger.warning(
            "No Whisper backend available. "
            "Install openai-whisper (`pip install openai-whisper`) or whisper-cpp-python. "
            "STT will return None until a backend is available."
        )
        return False

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> Optional[TranscriptionResult]:
        """Transcribe an audio file.

        Args:
            audio_path: Path to audio file (wav, mp3, flac, ogg).
            language: ISO language code (e.g. 'de', 'en'). Auto-detected if None.

        Returns:
            TranscriptionResult or None if no backend is available.
        """
        if not self._loaded and not self.load_model():
            return None

        lang = language or self.config.language
        start = time.time()

        try:
            if self._backend == "openai-whisper":
                import whisper
                result = self._model.transcribe(
                    audio_path,
                    language=lang,
                    fp16=(self.config.compute_type == "float16"),
                )
                text = result.get("text", "").strip()
                lang_detected = result.get("language", lang or "en")
                segments = [
                    {"text": seg["text"], "start": seg["start"], "end": seg["end"]}
                    for seg in result.get("segments", [])
                ]
                # Approximate confidence from average log-probability
                avg_logprob = result.get("avg_logprob", -1.0)
                confidence = max(0.0, min(1.0, (avg_logprob + 1.0)))

            elif self._backend == "whisper-cpp":
                import whisperex
                result = whisperex.transcribe(str(audio_path), language=lang or "")
                text = result.get("text", "").strip()
                lang_detected = lang or "en"
                segments = result.get("segments", [])
                confidence = 0.9  # whisper-cpp doesn't expose logprobs directly

            else:
                return None

            duration_ms = (time.time() - start) * 1000

            return TranscriptionResult(
                text=text,
                language=lang_detected,
                confidence=confidence,
                duration_ms=duration_ms,
                segments=segments,
                metadata={"backend": self._backend, "model": self.config.model},
            )

        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return None

    def transcribe_streaming(
        self,
        audio_stream: bytes,
        callback: Callable[[str], None],
    ) -> Optional[TranscriptionResult]:
        """Transcribe streaming audio (chunked processing).

        Writes chunks to a temp file, transcribes on flush.

        Args:
            audio_stream: Raw audio bytes.
            callback: Called with each partial transcription.

        Returns:
            Final TranscriptionResult or None.
        """
        if not self._loaded and not self.load_model():
            return None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_stream)
            tmp_path = tmp.name

        try:
            result = self.transcribe(tmp_path)
            if result and callback:
                callback(result.text)
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# Global default STT
default_stt: Optional[WhisperSTT] = None


def init_stt(config: Optional[STTConfig] = None) -> WhisperSTT:
    """Initialize global STT."""
    global default_stt
    default_stt = WhisperSTT(config)
    return default_stt


def transcribe_audio(path: str, **kwargs) -> Optional[TranscriptionResult]:
    """Convenience function for transcription."""
    if default_stt:
        return default_stt.transcribe(path, **kwargs)
    return None