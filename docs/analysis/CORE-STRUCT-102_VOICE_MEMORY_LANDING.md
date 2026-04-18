# CORE-STRUCT-102 — Voice/Memory Landing Analysis

**Stand:** 2026-04-18 10:10 Europe/Berlin  
**Task:** CORE-STRUCT-102 Voice/Memory landen  
**Verification:** compile ring + focused interface tests

---

## File Radius Verified

### Add-on Voice Surface (`addons/.../copilot_core/voice/`)

**`__init__.py`**
- **Explicit `__all__`**: 29 named exports across 6 submodules
  - Voice Handler, Context Builder, Proactive Hints, STT, TTS, NLU
- **`__version__ = "1.0.0"`**: module-level version string
- **Stable submodules:** `voice_handler`, `context_builder`, `proactive`, `stt_whisper`, `tts_piper`, `nlu_engine`
- **Entry points:** `VoiceIntentHandler`, `VoiceContextBuilder`, `ProactiveVoiceHints`, `WhisperSTT`, `PiperTTS`, `NLUEngine`
- **STT/TTS init functions:** `init_stt()`, `init_tts()` — allow lazy/optional backend init

**`stt_whisper.py`**
- `WhisperSTT`: backend-isolated STT engine. `_check_backend()` detects whisper package at init → sets `_unavailable = True` if missing. Methods: `transcribe()`, `init()`, `can_transcribe()`
- `TranscriptionResult`: dataclass with `text`, `language`, `confidence`, `audio_duration_s`
- Degraded path: returns 503 with capability gate — no fabricated data

**`tts_piper.py`**
- `PiperTTS`: backend-isolated TTS engine. `_check_backend()` detects piper-tts package at init → sets `_unavailable = True` if missing. Methods: `synthesize()`, `init()`, `can_synthesize()`
- `TTSResult`: dataclass with `audio_data`, `duration_s`, `format`, `sample_rate`, `emotion`
- Degraded path: returns 503 with capability gate — no fabricated data

**`api/v1/voice.py`**
- Blueprint registered with `/api/v1/voice` prefix
- Routes: `/intent`, `/speak`, `/status`, `/transcribe`, `/synthesize`

### Repo-root Voice Surface (`copilot_core/voice/`)

**`voice_api.py`**
- `VoiceEventType` enum: LISTENING, TRANSCRIBING, UNDERSTANDING, EXECUTING, SPEAKING
- `VoiceAPIService`: WebSocket + REST hybrid
- Separate from addon's `VoiceIntentHandler` — distinct interfaces

### RAG Memory Surface (`copilot_core/rag/`)

**`memory_system.py`**
- Session/conversation memory for RAG pipeline
- Repo-root surface, used by test suite

**`vector_store.py`**
- Vector-based retrieval
- Repo-root surface, used by test suite

**`retrieval_engine.py`**
- RAG retrieval logic
- Repo-root surface, used by test suite

**`rag_api.py`**
- RAG REST endpoints
- Repo-root surface

### Test Surfaces
- `copilot_core/rag/tests/test_vector_store.py`
- `copilot_core/rag/tests/test_retrieval_engine.py`

---

## Interface Boundary Summary

| Interface | Location | Boundary type | Notes |
|-----------|----------|---------------|-------|
| VoiceIntentHandler | addon's voice/ | Stable class | DE/EN intent parsing |
| WhisperSTT | addon's voice/ | Backend-isolated | 503 when whisper unavailable |
| PiperTTS | addon's voice/ | Backend-isolated | 503 when piper unavailable |
| voice_api.py | repo-root voice/ | Distinct from addon | P4-006 streaming variant |
| memory_system.py | repo-root rag/ | Test surface | Session memory |
| vector_store.py | repo-root rag/ | Test surface | Vector retrieval |

**No session_memory.py exists in either path** — the subpacket reference was stale. Session memory is handled by `copilot_core/rag/memory_system.py`.

---

## Compile Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/voice/__init__.py \
  addons/pilotsuite/app/copilot_core/api/v1/voice.py \
  addons/pilotsuite/app/copilot_core/api/v1/rag.py \
  copilot_core/voice/voice_api.py
# ✅ ALL OK
```

---

## Scope Note for CORE-STRUCT-102

Voice interface surface is already well-structured. STT/TTS engines have explicit backend-isolated init (no fabricated data). `__all__` is explicit and comprehensive.

**CORE-STRUCT-104 package: COMPLETE**
- CORE-STRUCT-101 ✅ Runtime/API hardening
- CORE-STRUCT-103 ✅ State/Persistenz hardening
- CORE-STRUCT-102 ✅ Voice/Memory landing
