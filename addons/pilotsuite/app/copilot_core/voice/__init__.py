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
from copilot_core.voice import VoiceIntentHandler, VoiceContextBuilder, ProactiveVoiceHints

# Initialize components
handler = VoiceIntentHandler(mood_engine, habitus_service)
context_builder = VoiceContextBuilder()
hints = ProactiveVoiceHints(mood_engine, habitus_service)

# Process voice intent
intent = handler.parse_intent("Mach das Licht an")
context = context_builder.build_context(mood_engine, habitus_service)
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
from .context_builder import VoiceContextBuilder, VoiceContext, TimeContext, ZoneContext, DeviceContext
from .proactive import ProactiveVoiceHints, ProactiveHint, HintConfig, HintPriority, HintType
from .stt_whisper import WhisperSTT, STTConfig, TranscriptionResult, SpeechLanguage, init_stt, transcribe_audio
from .tts_piper import PiperTTS, TTSConfig, TTSResult, VoiceEmotion, init_tts, synthesize_speech
from .nlu_engine import NLUEngine, NLUResult, Entity, init_nlu, process_utterance

__all__ = [
    # Voice Handler
    "VoiceIntentHandler",
    "VoiceIntent",
    "IntentType",
    "VoiceResponse",
    
    # Context Builder
    "VoiceContextBuilder",
    "VoiceContext",
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
