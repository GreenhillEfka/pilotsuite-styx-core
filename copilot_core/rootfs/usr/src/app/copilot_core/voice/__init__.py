"""Voice Integration Module for Home Assistant Voice Assistant.

This module provides deep voice assistant integration with:
- Voice Intent Handling (DE/EN)
- Context Building (Mood, Time, Zone)
- Proactive Voice Hints
- REST API Endpoints
- Dialog State Machine (Multi-Turn, Persistence, Timeout)

Modules:
- voice_handler: Intent parsing & response generation
- intent_parser: Intent parsing with slot extraction
- confidence_router: Three-tier confidence routing
- context_builder: Context aggregation (mood, time, zone, devices)
- proactive: Proactive hint generation based on patterns and events
- dialog_state: Multi-turn dialog FSM with persistence

Integration Points:
- Home Assistant Assist Pipeline
- Mood Engine (copilot_core.mood)
- Habitus Service (copilot_core.habitus)
- User Preferences

Usage:
```python
from copilot_core.voice import VoiceIntentHandler, VoiceContextBuilder
from copilot_core.voice import ProactiveVoiceHints
from copilot_core.voice import DialogStateMachine, get_dialog_machine

# Dialog State Machine
machine = get_dialog_machine()
state = machine.activate_intent('climate.set_temperature', {'room': 'kitchen', 'target_temp': 22})
question = machine.generate_confirmation_question()  # German, spoken + dashboard

# Process voice intent
handler = VoiceIntentHandler(mood_engine, habitus_service)
context = VoiceContextBuilder().build_context(mood_engine, habitus_service)
intent = handler.parse_intent("Mach das Licht an")
response = handler.handle_intent(intent, context)

# Generate proactive hints
hints = ProactiveVoiceHints(mood_engine, habitus_service)
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
from .intent_parser import IntentParser, IntentParseResult
from .confidence_router import ConfidenceRouter, RoutingDecision, ProcessingTier, RouteResult
from .context_builder import VoiceContextBuilder, VoiceContext, TimeContext, ZoneContext, DeviceContext
from .proactive import ProactiveVoiceHints, ProactiveHint, HintConfig, HintPriority, HintType
from .dialog_state import DialogStateMachine, DialogState, get_dialog_machine

__all__ = [
    # Voice Handler
    "VoiceIntentHandler",
    "VoiceIntent",
    "IntentType",
    "VoiceResponse",
    "IntentParser",
    "IntentParseResult",
    
    # Confidence Router
    "ConfidenceRouter",
    "RoutingDecision",
    "ProcessingTier",
    "RouteResult",
    
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
    
    # Dialog State Machine
    "DialogStateMachine",
    "DialogState",
    "get_dialog_machine",
]

__version__ = "1.1.0"
