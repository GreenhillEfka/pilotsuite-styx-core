# PS CORE STRUCT 101L — capability surface closeout sweep

## Context
`CORE-STRUCT-101H/I/J/K` removed duplicate `/api/v1/capabilities` handlers, aligned authentication truth on the repo-root FastAPI compatibility server, and brought the remaining shipped voice-module payload shape onto the shared canonical discovery contract.

The remaining question was whether any live repo-root or doc-backed capability references still described the old reduced voice-module shape or otherwise contradicted the now-canonical discovery truth.

## Sweep performed
Searched the active core worktree for:
- direct references to the old reduced voice list `['stt', 'nlu', 'tts', 'emotion']`
- stale wording around reduced voice-module discovery payloads
- live `/api/v1/capabilities` handlers and tests asserting payload structure

## Findings
- no remaining live shipped capability handler still returns the old reduced voice-module list
- no current tests or runtime docs still instruct consumers to expect that stale reduced shape
- remaining hits are historical analysis records documenting the fixed defect, plus the new defensive comment in `copilot_core/api/rest_server.py`

## Result
`CORE-STRUCT-101` capability-surface hardening is functionally closed for the `/api/v1/capabilities` parity chain. The remaining live surfaces now agree on the bounded truths that matter for discovery callers:
- one canonical route per Flask app factory
- token-gated discovery on shipped server variants
- shared structured voice discovery payload for the public `voice` module
- no fake `voice_context` capability surface invented on the repo-root compatibility server

## Verification
```bash
rg -n '\["stt", "nlu", "tts", "emotion"\]|stt.*, nlu.*, tts.*, emotion|older reduced voice-module shape|reduced voice-module list|voice module list|voice discovery block' \
  /config/clawd/team/worktrees/pilotsuite-styx-core-current \
  -g '!**/.venv*' -g '!**/__pycache__/**'

rg -n 'api/v1/capabilities|get_capabilities\(|capabilities"\]\)|payload\["modules"\]|payload\["capabilities"\]' \
  /config/clawd/team/worktrees/pilotsuite-styx-core-current \
  -g '!**/.venv*' -g '!**/__pycache__/**'
```

## Next single step
Advance the Core lane to `CORE-STRUCT-103 / State-Persistence hardening`, unless a fresher runtime/API regression appears first.
