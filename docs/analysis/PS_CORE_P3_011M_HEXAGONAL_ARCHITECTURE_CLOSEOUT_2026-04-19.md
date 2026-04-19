# PS_CORE_P3_011M_HEXAGONAL_ARCHITECTURE_CLOSEOUT_2026-04-19

## Task
Declare P3-011 functionally and formally closed, map remaining open seams to their correct owners, and hand off cleanly to the next serial queue item.

---

## P3-011 Summary

**Goal:** Introduce hexagonal architecture boundaries in the voice module — separating the HTTP adapter (input), the domain logic (command flow, dialog flow), and the concrete engine adapters (WhisperSTT, PiperTTS, NLUEngine) behind port interfaces.

### Sub-slices landed

| ID | Slice | Commit | Status |
|----|-------|--------|--------|
| P3-011-A | Voice route boundary extraction | `7e34bbd6` | ✅ |
| P3-011-B | Command-router runtime extraction | `8bef8ccb` | ✅ |
| P3-011-C | Command flow port shaping | `8bef8ccb` | ✅ |
| P3-011-D | Dialog state flow extraction | `75ff6e02` | ✅ |
| P3-011-E | VoiceCommandFlow result/serializer boundary | `017d26d7` | ✅ |
| P3-011-F | Dialog state flow extraction (follow-through) | `1e314d62` | ✅ |
| P3-011-G | Dialog mutation seam extraction | `babf91a0` | ✅ |
| P3-011-H | Dialog snapshot boundary consolidation | `1e314d62` | ✅ |
| P3-011-I | Confirmation transition seam tightening | `babf91a0` | ✅ |
| P3-011-J | Context/runtime seam — adapter-owned deps | `489f9533` | ✅ |
| P3-011-K | Residual context-runtime closeout audit | `c46e76fa` | ✅ |
| P3-011-L | Hex port interface definitions (STT/TTS/NLU) | `05e74f4f` | ✅ |

### What was achieved
1. `VoiceRuntimeAccess` is now the single entry point for all voice services — routes no longer build their own collaborators.
2. `VoiceCommandFlow` / `VoiceDialogFlow` are injected into the route seam, not instantiated there.
3. Context building always passes a `VoiceContextRuntime` bundle; no loose `mood_engine` / `habitus_service` params.
4. Engine accessors (`get_stt_engine`, `get_tts_engine`, `get_nlu_engine`) delegate to factory functions that satisfy `SttEnginePort`, `TtsEnginePort`, `NluEnginePort` Protocols.
5. Suite-wide test state leaks eliminated; full suite clean: **523 passed, 19 skipped**.

### What was NOT in scope (correctly deferred)
- Persistence contract documentation → `CORE-CONTRACT-201`
- HA voice command router integration → `HA-558` (HomeClaw owns)
- Mobile responsive / Lovelace cards → `HA-559` (HomeClaw)
- MQTT broker integration → future backlog
- Plugin Hub / SDK → v2.0.0 backlog

---

## Remaining Hexagonal Seams (documented, not blocking)

| Seam | Location | Owner | Status |
|------|----------|-------|--------|
| `VoiceContextBuilder` → `MoodEngine` | `voice/context_builder.py` | PilotClaw | ⚠️ Runtime injection, not port |
| `VoiceContextBuilder` → `HabitusService` | `voice/context_builder.py` | PilotClaw | ⚠️ Runtime injection, not port |
| STT/TTS engine config params | `voice/runtime_access.py` factories | PilotClaw | ⚠️ Hardcoded defaults in factory |

These are **known trade-offs**: the builders receive real runtime instances (not raw scalars), which is the core hexagonal intent. Formal port interfaces for MoodEngine and HabitusService would require a larger refactor of those modules and are deferred to a future hex-deepening pass.

---

## Closeout Decision

**P3-011 is functionally closed.**

- All originally filed hex boundary defects are resolved or deliberately deferred with documented rationale.
- No remaining blocker in the Core queue.
- Suite is green.
- Next serial item: `CORE-CONTRACT-201-A` (Persistence contract domain mapping).

---

## Serial Queue (updated)

```
1. P3-011 ✅ CLOSED  ← this document
2. CORE-CONTRACT-201-A  [PilotClaw]  ← next
3. CORE-CONTRACT-201-B  [PilotClaw]
4. CORE-CONTRACT-201-C  [PilotClaw]
5. CORE-CONTRACT-201-D  [PilotClaw]
6. CORE-CONTRACT-201-E  [PilotClaw] ← closeout
```

---

## Verification
```
523 passed, 19 skipped
```
