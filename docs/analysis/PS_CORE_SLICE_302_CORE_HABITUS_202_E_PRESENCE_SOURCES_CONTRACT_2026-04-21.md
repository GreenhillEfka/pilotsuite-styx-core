# PS CORE SLICE 302 — CORE-HABITUS-202-E Presence Sources Contract

## Scope
- bounded Core proof slice only on `GET /api/v1/presence/sources`
- no widening into `/history`, `/update`, person-hold mutation, automation, graph, or HA config work

## Files
- `tests/test_presence_sources_api_contract.py`

## What landed
- added a dedicated contract ring for the existing `GET /api/v1/presence/sources` seam
- locked the front-door `401` auth payload
- locked `400` on missing `person_id`
- locked `404` on unknown person
- locked `200` on a seeded person record returning canonical `person_id`, `name`, `sources`, `hold`, `hold_reason`, and `aggregated_state`
- kept the slice proof-only because fresh repo truth on `addons/pilotsuite/app/copilot_core/api/v1/presence.py` already matched the bounded contract

## Verification
- `python3 -m py_compile tests/test_presence_sources_api_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_sources_api_contract.py` → `4 passed in 0.06s`

## Result
- `CORE-HABITUS-202-E` is now file-backed on a dedicated presence-sources contract ring
- the habitus/presence chain remains bounded and ready for the next fresh-truth pull after checkpointing
