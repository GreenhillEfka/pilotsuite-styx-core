# PS_CORE_P3_011L_HEX_VOICE_ENGINE_PORT_INTERFACES

## Task
Define minimal hex Port interfaces for the three voice engines (STT, TTS, NLU) and wire
them into VoiceRuntimeAccess so the runtime no longer directly imports or instantiates
WhisperSTT / PiperTTS — it receives them through the port abstraction instead.

## Why this slice
`hexagonal.py` defines InputPort/OutputPort/Repository Protocols but they are not used
by the voice module. VoiceRuntimeAccess.get_stt_engine() / get_tts_engine() /
get_nlu_engine() all do `override or ConcreteClass(...)` — direct instantiation with
no port boundary. This slice introduces the port boundary for the three engine accessors.

## Exact defect removed
VoiceRuntimeAccess no longer imports `WhisperSTT`/`PiperTTS` at all. Engines are
received through the service dict or created by a factory that the runtime calls.
The concrete engine classes remain unchanged; only the wiring moves one layer out.

## Files touched
- `addons/pilotsuite/app/copilot_core/voice/__init__.py` — export port interfaces + concrete engines
- `addons/pilotsuite/app/copilot_core/voice/runtime_access.py` — use engine port types

## Verification
```
python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/__init__.py
python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/runtime_access.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest tests/ -q  →  523 passed, 19 skipped
```
