# P1-006 — Voice Whisper/Piper Route Contract

**Stand:** 2026-04-18 10:20 Europe/Berlin  
**Task:** CORE-RESCUE-004-A — Whisper-Piper voice route contract restore  
**Verification:** compile ring + contract test ring

---

## Route Contract Summary

### `POST /api/v1/voice/transcribe` — Whisper Compatibility Surface
- **Request:** `{ "audio_path": "...", "language": "de" }`
- **Success (200):** `{ "status": "ok", "text": "...", "language": "...", "confidence": 0.x, "duration_ms": N, "metadata": {...} }`
- **Backend unavailable (503):** `{ "status": "error", "code": "BACKEND_UNAVAILABLE", "message": "Voice transcription unavailable", "backend": "whisper", ... }`
- **Implementation:** `stt_engine.transcribe(audio_path, language=language)` via `WhisperSTT`
- **Backend check:** `_check_backend()` at engine init → sets `_unavailable = True` if whisper package missing → 503 via `_voice_backend_unavailable_response()`

### `POST /api/v1/voice/synthesize` — Piper Compatibility Surface
- **Request:** `{ "text": "...", "voice": "..." }`
- **Success (200):** `{ "status": "ok", "audio_path": "...", "text": "...", "voice": "...", "duration_seconds": N, "generation_time_ms": N }`
- **Backend unavailable (503):** `{ "status": "error", "code": "BACKEND_UNAVAILABLE", "message": "Voice synthesis unavailable", "backend": "piper", ... }`
- **Missing text (400):** `{ "status": "error", "message": "Missing 'text' in request body" }`
- **Implementation:** `tts_engine.synthesize(text, voice=voice)` via `PiperTTS`
- **Backend check:** `_check_backend()` at engine init → sets `_unavailable = True` if piper-tts package missing → 503 via `_voice_backend_unavailable_response()`

### `GET /api/v1/voice/status` — Capability Gate
- **Response:** `{ "can_transcribe": bool, "can_synthesize": bool, "can_speak": bool, "available_backends": [...], ... }`
- **Behavior:** `can_transcribe` = `stt_available` (True if WhisperSTT backend available) → `False` when `_unavailable = True`
- **Behavior:** `can_synthesize` = `tts_available` (True if PiperTTS backend available) → `False` when `_unavailable = True`

---

## Contract Test Verification

```bash
python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py copilot_core/voice/stt_whisper.py copilot_core/voice/tts_piper.py tests/test_voice_api_transcribe_synthesize_contract.py
# ✅ ALL OK

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py
# 4 passed in 0.23s ✅
```

**Test coverage:**
1. `test_voice_transcribe_degraded_when_whisper_unavailable` — 503 when whisper unavailable ✅
2. `test_voice_synthesize_route_returns_audio_path` — synthesize route contract ✅
3. `test_voice_status_exposes_stt_tts_runtime` — status endpoint capability exposure ✅
4. `test_voice_status_capabilities_turn_false_when_backends_missing` — capability gate behavior ✅

---

## Scope Boundary

**In scope:** request validation, stable JSON response shapes, truthful failure handling (503 degraded path), capability gate

**Out of scope:**
- streaming STT
- websocket voice updates
- voice cloning, emotion tuning, adaptive TTS
- HA entity migration, upload storage redesign, multipart ingest expansion
- reopening of old voice replay chain

---

## Key Design Decision

**No fabricated data.** When Whisper/Piper backends are unavailable:
- `can_transcribe` / `can_synthesize` → `False` in status endpoint
- Routes return 503 with explicit `BACKEND_UNAVAILABLE` code
- No silent fallback or fake transcription/synthesis

**Next:** HA-VOICE-CONSUMER-001 — HA STT-TTS endpoint parity on restored Core voice routes
