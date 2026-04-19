# PS CORE-STRUCT-102N - helper-backed component parity proof

## Task
Land the bounded follow-on behind `CORE-STRUCT-102M` by restoring the proof ring around additive `components` parity on the shared helper-backed voice surfaces.

## Why this slice
`get_voice_health_block()` and `voice_capabilities_module()` already project additive `components` truth, but the focused helper/discovery contract ring still encoded the older runtime-only shape. That left the exact closeout seam under-proved and made the parity state ambiguous again during rechecks.

## Changes
- updated `tests/test_voice_health_block_contract.py` so the shared helper expectations now lock the additive `components` block across empty, fallback, partial-availability, and injected-runtime paths
- updated `tests/test_voice_health_surface_contract.py` so helper-backed `/health`, `/api/v1/status`, and `/api/v1/ready` proofs preserve the same `components` payload instead of silently accepting the pre-parity shape
- updated `tests/test_voice_discovery_surface_contract.py` so `voice_capabilities_module()` is explicitly locked to preserve helper-backed `components` parity in the exported runtime payload

## Verification
- `python3 -m py_compile tests/test_voice_health_block_contract.py tests/test_voice_discovery_surface_contract.py tests/test_voice_health_surface_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py` -> `23 passed in 2.67s`

## Result
The helper-backed voice proof ring now agrees with the shipped additive `components` contract instead of lagging on the older runtime-only payload shape, so `CORE-STRUCT-102` closeout can proceed from one file-backed parity baseline.
