# PS CORE STRUCT 102L — voice status null optional-component truth

## Context
After `CORE-STRUCT-102K` removed the null injected intent-handler drift, the next bounded follow-on stayed on the same hardened voice/runtime seam and checked whether `/api/v1/voice/status` still stayed truthful when the injected runtime returned missing optional collaborators without raising.

## Exact defect removed
`addons/pilotsuite/app/copilot_core/api/v1/voice.py` treated `_get_context_builder()` and `_get_proactive_hints()` as available whenever those runtime accessors returned without raising.

That reopened one degraded-path truth gap:
- `/api/v1/voice/status` could report `components.context_builder = available` even when the injected runtime explicitly returned `None`
- the same route could also report `components.proactive_hints = available` while falling back to default hint config because the injected runtime had no live hints service

## Bounded fix
- tightened `_build_voice_status_config()` so a null proactive-hints runtime returns canonical `HintConfig()` defaults instead of relying on an attribute access failure
- added `_resolve_optional_voice_component(...)` and switched the status component checks to treat both raised exceptions and explicit `None` returns as unavailable truth
- widened `tests/test_voice_api_transcribe_synthesize_contract.py` with one focused injected-runtime regression locking `context_builder` and `proactive_hints` to `unavailable` when the seam returns `None`

## Result
`/api/v1/voice/status` no longer turns null optional runtime collaborators into false-positive component availability. The public status surface now stays truthful when the injected runtime keeps STT/TTS/NLU and dialog capability alive but omits the context-builder or proactive-hints helper.

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_api_transcribe_synthesize_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py
```

## Next single step
Run the bounded `CORE-STRUCT-102` closeout sweep now that the last discovered null-return degraded-path packet on `/api/v1/voice/status` is closed, then roll directly into `P3-011` if no further voice/runtime truth drift remains.
