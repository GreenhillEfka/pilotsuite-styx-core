# P1-006 Voice Speak Audio Delivery Contract (2026-04-18)

## Why this slice exists

After `POST /api/v1/voice/transcribe` and `POST /api/v1/voice/synthesize` were restored, the remaining public voice API contract gap was `POST /api/v1/voice/speak`.

The route still returned a fabricated `audio_url` derived from the input text, but the voice blueprint exposed no matching `/api/v1/voice/audio/<id>` route and the response bypassed the Piper compatibility seam entirely. That left the published API surface claiming successful TTS delivery without a retrievable artifact or truthful degraded-path behavior.

## Bounded change

- changed `POST /api/v1/voice/speak` to synthesize through the shared Piper compatibility wrapper instead of inventing a fake success payload
- when Piper returns `None`, the route now returns the same stable `503` degraded-path semantics used by the bounded `/synthesize` seam
- cached generated audio artifacts behind one thin in-process map and added `GET /api/v1/voice/audio/<audio_id>` so returned `audio_url` values now resolve to a real file
- made the response `format` field reflect the actual generated artifact suffix instead of echoing a requested but unsupported format

## Artifacts

- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `tests/test_voice_api_endpoint_contracts.py`

## Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/api/v1/voice.py \
  tests/test_voice_api_endpoint_contracts.py \
  tests/test_voice_degraded_path_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_voice_api_endpoint_contracts.py \
  tests/test_voice_degraded_path_contract.py \
  tests/test_voice_api_transcribe_synthesize_contract.py \
  tests/test_voice_whisper_piper_contract.py
```

Expected result:
- `25 passed`

## Result

`/api/v1/voice/speak` no longer claims success with an unreachable fake `audio_url`. The bounded voice API now returns a retrievable audio artifact when TTS succeeds and a stable `503` when the Piper backend is unavailable, without opening any second voice runtime path.
