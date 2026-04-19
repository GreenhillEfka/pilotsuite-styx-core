"""Voice Integration Module for Home Assistant Voice Assistant.

This module provides deep voice assistant integration with:
- Voice Intent Handling (DE/EN)
- Context Building (Mood, Time, Zone)
- Proactive Voice Hints
- REST API Endpoints

Modules:
- voice_handler: Intent parsing and response generation
- context_builder: Context aggregation (mood, time, zone, devices)
- proactive: Proactive hint generation based on patterns and events

Integration Points:
- Home Assistant Assist Pipeline
- Mood Engine (copilot_core.mood)
- Habitus Service (copilot_core.habitus)
- User Preferences

Usage:
```python
from copilot_core.voice import VoiceIntentHandler, VoiceContextBuilder, ProactiveVoiceHints, VoiceContextRuntime

# Initialize components
handler = VoiceIntentHandler(mood_engine, habitus_service)
context_builder = VoiceContextBuilder()
hints = ProactiveVoiceHints(mood_engine, habitus_service)
context_runtime = VoiceContextRuntime(mood_engine=mood_engine, habitus_service=habitus_service)

# Process voice intent
intent = handler.parse_intent("Mach das Licht an")
context = context_builder.build_context(context_runtime=context_runtime)
response = handler.handle_intent(intent, context)

# Generate proactive hints
hint_list = hints.generate_hints(context)
```

API Endpoints:
- POST /api/v1/voice/intent - Process voice intent
- GET  /api/v1/voice/context - Get current voice context
- GET  /api/v1/voice/hints - Get proactive voice hints
- POST /api/v1/voice/speak - Generate TTS response
- GET  /api/v1/voice/status - Voice system status
"""

from .voice_handler import VoiceIntentHandler, VoiceIntent, IntentType, VoiceResponse
from .context_builder import (
    VoiceContextBuilder,
    VoiceContext,
    VoiceContextRuntime,
    TimeContext,
    ZoneContext,
    DeviceContext,
)
from .proactive import ProactiveVoiceHints, ProactiveHint, HintConfig, HintPriority, HintType
from .stt_whisper import WhisperSTT, STTConfig, TranscriptionResult, SpeechLanguage, init_stt, transcribe_audio
from .tts_piper import PiperTTS, TTSConfig, TTSResult, VoiceEmotion, init_tts, synthesize_speech
from .nlu_engine import NLUEngine, NLUResult, Entity, init_nlu, process_utterance

from typing import Any, Dict, List, Optional, Protocol


# =============================================================================
# HEXAGONAL PORT INTERFACES — Voice Engine Layer
# These Protocols define the minimal contract that all voice engine adapters
# (Whisper STT, Piper TTS, rule-based NLU, and future replacements) must satisfy.
# VoiceRuntimeAccess depends only on these interfaces, never on concrete classes.
# =============================================================================


class SttEnginePort(Protocol):
    """Port interface for speech-to-text engines.

    Adapters that satisfy this port: WhisperSTT, any STT replacement.
    """

    def is_available(self) -> bool: ...

    def availability_payload(self) -> Dict[str, Any]: ...

    def transcribe(self, audio_stream: Any, **kwargs: Any) -> Any: ...


class TtsEnginePort(Protocol):
    """Port interface for text-to-speech engines.

    Adapters that satisfy this port: PiperTTS, any TTS replacement.
    """

    def is_available(self) -> bool: ...

    def availability_payload(self) -> Dict[str, Any]: ...

    def synthesize(self, text: str, **kwargs: Any) -> Any: ...


class NluEnginePort(Protocol):
    """Port interface for natural-language-understanding engines.

    Adapters that satisfy this port: NLUEngine, any NLU replacement.
    """

    def is_available(self) -> bool: ...

    def availability_payload(self) -> Dict[str, Any]: ...

    def process(self, text: str, language: str = "de") -> Any: ...


# =============================================================================
# CONCRETE ENGINE FACTORIES
# These are the standard adapters for the voice engine ports.
# VoiceRuntimeAccess calls these when no injected override is provided.
# =============================================================================


def _create_stt_engine() -> SttEnginePort:
    from .stt_whisper import init_stt, STTConfig

    return init_stt(STTConfig(language="de"))


def _create_tts_engine() -> TtsEnginePort:
    from .tts_piper import init_tts, TTSConfig

    return init_tts(TTSConfig())


def _create_nlu_engine() -> NluEnginePort:
    from .nlu_engine import init_nlu

    return init_nlu()

__all__ = [
    # Voice Handler
    "VoiceIntentHandler",
    "VoiceIntent",
    "IntentType",
    "VoiceResponse",
    
    # Context Builder
    "VoiceContextBuilder",
    "VoiceContext",
    "VoiceContextRuntime",
    "TimeContext",
    "ZoneContext",
    "DeviceContext",
    
    # Proactive Hints
    "ProactiveVoiceHints",
    "ProactiveHint",
    "HintConfig",
    "HintPriority",
    "HintType",

    # STT
    "WhisperSTT",
    "STTConfig",
    "TranscriptionResult",
    "SpeechLanguage",
    "init_stt",
    "transcribe_audio",

    # TTS
    "PiperTTS",
    "TTSConfig",
    "TTSResult",
    "VoiceEmotion",
    "init_tts",
    "synthesize_speech",

    # NLU
    "NLUEngine",
    "NLUResult",
    "Entity",
    "init_nlu",
    "process_utterance",
]

__version__ = "1.0.0"
