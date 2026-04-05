# UX-129: Voice-Context-Matrix

**Status:** Finalized (2026-04-05 22:32)
**Owner:** DesignClaw
**Basis:** R4-States + Voice-Context-API

## Voice-Context States

| State | Description | Primary CTA | Secondary CTA | Terminal |
|-------|-------------|-------------|---------------|----------|
| `voice.listening` | Active speech input | — | Cancel | Nein |
| `voice.processing` | NLP inference running | — | — | Nein |
| `voice.response_ready` | Response prepared | Play Response | Show Text | Nein |
| `voice.follow_up_open` | Awaiting user response | Speak | Dismiss | Nein |
| `voice.follow_up_terminal` | Conversation complete | — | History | Ja |
| `voice.error` | Recognition failed | Retry | Text Input | Ja |

## Priority Rule

1. voice.error
2. voice.listening
3. voice.processing
4. voice.response_ready
5. voice.follow_up_*
6. neutral

## Core-Truth Fields

```json
{
  "voice_state": "listening|processing|response_ready|follow_up_open|follow_up_terminal|error",
  "transcript": "string|null",
  "confidence": "0.0-1.0",
  "response_text": "string|null",
  "response_tts_url": "string|null",
  "conversation_id": "uuid"
}
```

## HA-Projection

- Entity: `binary_sensor.voice_active`
- Attribute: `voice_state`, `transcript`, `confidence`
- Service: `voice.respond`, `voice.cancel`

