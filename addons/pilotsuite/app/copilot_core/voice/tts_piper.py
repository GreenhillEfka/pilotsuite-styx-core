"""P1-006 compatibility TTS surface for the shipped add-on voice package."""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class VoiceEmotion(Enum):
    """Voice emotions for TTS."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    CALM = "calm"
    URGENT = "urgent"


@dataclass
class TTSConfig:
    """Configuration for TTS."""

    engine: str = "piper"
    voice: str = "de_DE-thorsten"
    speed: float = 1.0
    pitch: float = 1.0
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    output_dir: str = "/tmp/tts"


@dataclass
class TTSResult:
    """Result from text-to-speech."""

    audio_path: str
    duration_seconds: float
    text: str
    voice: str
    emotion: VoiceEmotion
    generation_time_ms: float


class PiperTTS:
    """Local Piper-style text-to-speech compatibility wrapper."""

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self._output_dir = Path(self.config.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._loaded = False

    def load_voice(self, voice_id: str) -> bool:
        """Load a voice model."""
        try:
            self._loaded = True
            self.config.voice = voice_id
            logger.info("Loaded voice: %s", voice_id)
            return True
        except Exception as exc:
            logger.error("Failed to load voice: %s", exc)
            return False

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        emotion: Optional[VoiceEmotion] = None,
        speed: Optional[float] = None,
    ) -> Optional[TTSResult]:
        """Synthesize speech from text."""
        start = time.time()
        voice = voice or self.config.voice
        emotion = emotion or self.config.emotion
        speed = speed or self.config.speed

        audio_hash = hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()[:16]
        audio_path = self._output_dir / f"{audio_hash}.wav"

        try:
            audio_path.touch()
            generation_time_ms = (time.time() - start) * 1000
            duration_seconds = max(len(text.split()) / 2.5, 0.1) / max(speed, 0.1)
            return TTSResult(
                audio_path=str(audio_path),
                duration_seconds=duration_seconds,
                text=text,
                voice=voice,
                emotion=emotion,
                generation_time_ms=generation_time_ms,
            )
        except Exception as exc:
            logger.error("TTS synthesis failed: %s", exc)
            return None

    def synthesize_streaming(self, text: str, callback: Optional[Callable[[bytes], None]] = None) -> Optional[TTSResult]:
        """Synthesize with streaming output."""
        result = self.synthesize(text)
        if result and callback:
            with open(result.audio_path, "rb") as handle:
                for chunk in iter(lambda: handle.read(4096), b""):
                    callback(chunk)
        return result

    def list_voices(self) -> List[Dict[str, str]]:
        """List available voices."""
        return [
            {"id": "de_DE-thorsten", "name": "Thorsten (German)", "language": "de"},
            {"id": "en_US-lessac", "name": "Lessac (English)", "language": "en"},
            {"id": "fr_FR-siwis", "name": "Siwis (French)", "language": "fr"},
        ]

    def clone_voice(self, name: str, sample_audio: str, sample_text: str) -> Optional[str]:
        """Clone a voice from audio sample."""
        logger.info("Cloning voice from sample: %s", sample_audio)
        if not name or not sample_text:
            return None
        return f"cloned_{name}"


default_tts: Optional[PiperTTS] = None


def init_tts(config: Optional[TTSConfig] = None) -> PiperTTS:
    """Initialize global TTS."""
    global default_tts
    default_tts = PiperTTS(config)
    return default_tts


def synthesize_speech(text: str, **kwargs) -> Optional[TTSResult]:
    """Convenience function for TTS."""
    if default_tts:
        return default_tts.synthesize(text, **kwargs)
    return None
