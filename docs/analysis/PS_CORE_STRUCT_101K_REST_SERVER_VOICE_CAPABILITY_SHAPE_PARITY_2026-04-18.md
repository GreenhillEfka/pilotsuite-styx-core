# PS CORE STRUCT 101K — Repo-root REST server voice capability shape parity

## Context
`CORE-STRUCT-101H/I/J` aligned the live Flask capability surfaces on one canonical auth-gated contract and then removed the remaining auth mismatch from the repo-root FastAPI compatibility server.

The next bounded truth gap was payload shape. The repo-root FastAPI server still returned a reduced legacy voice module list (`["stt", "nlu", "tts", "emotion"]`) even though the canonical runtime now exposes a structured public voice discovery contract with status surface, endpoints, features, and runtime health truth.

## Change
- imported `voice_capabilities_module()` into `copilot_core/api/rest_server.py`
- changed the repo-root FastAPI `GET /api/v1/capabilities` voice module payload to reuse that shared discovery contract instead of the stale reduced list
- kept the rest of the compatibility server intentionally narrow, including the absence of legacy `voice_context`, so this slice only fixes the misleading voice-module shape
- added focused REST-server coverage proving the authenticated capabilities payload now exposes the shared voice discovery block while preserving the reduced non-voice compatibility modules

## Result
The repo-root FastAPI compatibility server no longer advertises an older voice-module shape than the canonical runtime. Voice discovery callers now see the same truthful public voice contract on every remaining `/api/v1/capabilities` surface touched in `CORE-STRUCT-101`.

## Verification
```bash
python3 -m py_compile \
  copilot_core/api/rest_server.py \
  copilot_core/api/tests/test_rest_server.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  copilot_core/api/tests/test_rest_server.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_voice_discovery_surface_contract.py \
  tests/test_voice_health_block_contract.py \
  tests/test_voice_health_surface_contract.py \
  tests/test_voice_api_transcribe_synthesize_contract.py \
  tests/test_voice_app_factory_route_contract.py \
  copilot_core/api/tests/test_rest_server.py
```

## Next single step
`CORE-STRUCT-101L / capability surface closeout sweep` — check whether any remaining repo-root or doc-level capability references still describe the old reduced voice-module shape or whether `CORE-STRUCT-101` can now be explicitly closed on capability-surface truth.
