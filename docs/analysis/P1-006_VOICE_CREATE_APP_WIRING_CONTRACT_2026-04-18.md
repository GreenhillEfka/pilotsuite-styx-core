# P1-006 Voice `create_app()` Wiring Contract (2026-04-18)

## Why this slice exists

The bounded `POST /api/v1/voice/transcribe`, `POST /api/v1/voice/synthesize`, and `POST /api/v1/voice/speak` route work had already landed on the `copilot_core.api.v1.voice` blueprint, but the lightweight add-on app factory still only nested `api_v1`.

That meant `create_app()` exposed the legacy `voice_context` helper routes under `/api/v1/voice/*`, while the public voice API endpoints restored in the rescue work were still missing from the default app-factory wiring.

## Bounded change

- registered `copilot_core.api.v1.voice.bp` directly in `create_app()` so the absolute-prefix voice blueprint is exposed on the lightweight add-on app factory
- kept `api_v1` nested registration intact, so legacy `voice_context` helper routes remain available alongside the public voice API surface
- added a focused route contract test that stubs the unrelated smoke-env gaps (`mcp`, `tags`) and verifies `create_app()` now includes the expected public voice endpoints

## Artifacts

- `addons/pilotsuite/app/copilot_core/app.py`
- `tests/test_voice_app_factory_route_contract.py`

## Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/app.py \
  addons/pilotsuite/app/copilot_core/api/v1/voice.py \
  tests/test_voice_app_factory_route_contract.py \
  tests/test_voice_api_endpoint_contracts.py \
  tests/test_voice_degraded_path_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_voice_app_factory_route_contract.py \
  tests/test_voice_api_endpoint_contracts.py \
  tests/test_voice_degraded_path_contract.py \
  tests/test_voice_api_transcribe_synthesize_contract.py \
  tests/test_voice_whisper_piper_contract.py
```

Expected result:
- `26 passed`

## Result

`create_app()` no longer exposes only the voice-context helper subset. The lightweight add-on app factory now wires the public voice API blueprint too, so callers can reach `/api/v1/voice/intent`, `/transcribe`, `/synthesize`, `/speak`, `/status`, `/audio/<id>`, `/zones`, and `/intents` on the same bounded rescue surface.
