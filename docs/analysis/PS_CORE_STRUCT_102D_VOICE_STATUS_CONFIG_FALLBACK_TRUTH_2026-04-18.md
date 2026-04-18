# PS CORE STRUCT 102D — voice status config fallback truth

## Context
After `CORE-STRUCT-102-C` closed the dialog-runtime persistence seam, the next bounded follow-on check stayed on the same hardened voice/runtime path and re-validated `GET /api/v1/voice/status` as the public truth surface for runtime health.

## Exact defect removed
`addons/pilotsuite/app/copilot_core/api/v1/voice.py` still built the `config` block for `/api/v1/voice/status` by calling `_get_proactive_hints().config` directly after component probing.

That meant the route could correctly mark `proactive_hints` as `unavailable`, but then still throw a 500 while serializing the response whenever the proactive-hints seam itself was offline. The status surface stopped being truthful exactly in the degraded case where operators and downstream consumers needed it most.

## Bounded fix
- added one small `_build_voice_status_config()` helper in `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- reused the existing proactive-hints config when available
- fell back to the canonical `HintConfig()` defaults when the proactive-hints seam cannot be resolved
- kept the existing runtime/capability truth unchanged while ensuring `/api/v1/voice/status` still returns a stable additive `config` block during degraded operation
- extended `tests/test_voice_api_transcribe_synthesize_contract.py` with a focused regression proving the route stays `200` and reports `proactive_hints: unavailable` plus default config values when the hints seam raises

## Result
`GET /api/v1/voice/status` now remains a truthful degraded-path surface instead of collapsing into a 500 when proactive hints are unavailable.

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
.venv-validate/bin/python -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_api_transcribe_synthesize_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py
# 6 passed in 0.22s
```

## Next single step
Keep the voice status truth ring active and inspect the next bounded degraded-path mismatch on the public voice surface, most likely another case where a status/discovery response can still over-couple itself to an optional runtime seam.
