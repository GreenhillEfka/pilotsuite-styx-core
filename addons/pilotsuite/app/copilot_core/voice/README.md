# Voice Integration Module (v12.4.0)

Complete voice assistant integration for Home Assistant with context-aware responses.

## Features

- ✅ **HA Voice Assistant Intent-Handling** — Pattern-based intent recognition
- ✅ **Kontextbewusste Antworten** — Mood, time of day, zone context
- ✅ **Proaktive Hinweise** — Smart suggestions based on patterns and events
- ✅ **DE/EN Sprachunterstützung** — Bilingual German/English support
- ✅ **Integration mit Mood Engine** — Mood-aware response generation
- ✅ **Integration mit Habitus** — Pattern-based suggestions

## Module Structure

```
copilot_core/voice/
├── __init__.py              # Module exports
├── voice_handler.py         # Intent parsing & response generation (793 lines)
├── context_builder.py       # Context aggregation (554 lines)
├── proactive.py             # Proactive hint generation (674 lines)
└── README.md                # This file
```

## API Endpoints

All endpoints are under `/api/v1/voice/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/intent` | POST | Process voice intent |
| `/context` | GET | Get current voice context |
| `/hints` | GET | Get proactive voice hints |
| `/speak` | POST | Generate TTS response |
| `/status` | GET | Voice system status |
| `/zones` | GET | Available zones |
| `/intents` | GET | Supported intents |

## Usage Examples

### Process Voice Intent

```bash
curl -X POST http://localhost:8123/api/v1/voice/intent \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Mach das Licht an",
    "language": "de",
    "zone": "wohnzimmer"
  }'
```

Response:
```json
{
  "status": "ok",
  "intent": {
    "intent_type": "light_on",
    "confidence": 0.95,
    "slots": {},
    "language": "de"
  },
  "response": {
    "tts_text": "Entspannt. Alles klar, ich mache das. Licht ist an.",
    "actions": [
      {
        "domain": "light",
        "service": "turn_on",
        "entity_id": "light.wohnzimmer"
      }
    ],
    "mood_context": "relax",
    "language": "de",
    "suggestions": ["Möchtest du eine Entspannungs-Playlist?"]
  }
}
```

### Get Context

```bash
curl -X GET "http://localhost:8123/api/v1/voice/context?zone=wohnzimmer&force=false" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Proactive Hints

```bash
curl -X GET "http://localhost:8123/api/v1/voice/hints?priority=medium&force=false" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Python API

```python
from copilot_core.voice import VoiceIntentHandler, VoiceContextBuilder, ProactiveVoiceHints

# Initialize components
handler = VoiceIntentHandler(mood_engine, habitus_service)
context_builder = VoiceContextBuilder()
hints = ProactiveVoiceHints(mood_engine, habitus_service)

# Process voice intent
intent = handler.parse_intent("Mach das Licht an")
context = context_builder.build_context(mood_engine, habitus_service, zone_name="wohnzimmer")
response = handler.handle_intent(intent, context)

# Generate proactive hints
hint_list = hints.generate_hints(context)
```

## Supported Intents

### Control Intents
- `light_on` / `light_off` — Light control
- `light_dim` / `light_brighten` — Dimming
- `climate_set` / `climate_up` / `climate_down` — Temperature
- `media_play` / `media_pause` / `media_stop` — Media control
- `scene_activate` — Scene activation

### Query Intents
- `status_query` — General status
- `mood_query` — Mood/atmosphere query
- `time_query` / `date_query` — Time/date
- `weather_query` — Weather

## Context Building

The context builder aggregates:

1. **Mood Context** — Current zone mood (relax, focus, active, etc.)
2. **Time Context** — Time of day, day type, quiet hours
3. **Zone Context** — Room type, occupancy, devices
4. **Device Context** — Active devices and states
5. **Habitus Patterns** — Relevant behavioral patterns

## Proactive Hints

Hint types:
- `mood_change` — Mood-based suggestions
- `time_routine` — Time-based routines
- `habitus_pattern` — Pattern predictions
- `important_event` — Event reminders
- `comfort_suggestion` — Comfort improvements
- `energy_saving` — Energy efficiency tips

Hint priorities:
- `critical` — Must mention immediately
- `high` — Important, should mention
- `medium` — Useful suggestion
- `low` — Nice to know

## Configuration

Voice integration is auto-registered in `core_setup.py`. No additional configuration required.

Optional environment variables:
- `VOICE_DEFAULT_LANGUAGE` — Default language (default: "de")
- `VOICE_HINT_COOLDOWN` — Hint cooldown seconds (default: 300)
- `VOICE_MAX_HINTS_PER_HOUR` — Max hints per hour (default: 6)

## Dependencies

- `copilot_core.mood.engine` — Mood Engine
- `copilot_core.habitus.service` — Habitus Service
- `copilot_core.brain_graph.service` — Brain Graph (for patterns)

## Testing

```bash
cd /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app
python3 -c "
from copilot_core.voice import VoiceIntentHandler, VoiceContextBuilder, ProactiveVoiceHints
print('✓ Voice module imports successfully')
"
```

## Version

**v1.0.0** — Initial release (v12.4.0 iteration)

## Author

PilotSuite Styx Core Team
