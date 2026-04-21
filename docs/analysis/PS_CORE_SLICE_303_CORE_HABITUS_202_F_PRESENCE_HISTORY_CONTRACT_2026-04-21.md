# PS_CORE_SLICE_303_CORE_HABITUS_202_F_PRESENCE_HISTORY_CONTRACT_2026-04-21

## Scope
One bounded Core slice only on `GET /api/v1/presence/history`, with one dedicated proof ring `tests/test_presence_history_api_contract.py` and no widening into `/update`, person hold mutation, timeout handling, automation, graph, or HA config work.

## What landed
- locked the front-door `401` auth gate on `/api/v1/presence/history`
- locked the default `200` payload shape with newest-first event ordering
- locked the bounded `limit` clamp so oversized requests stop at the route max of `200`
- stayed on the existing shipped `presence.py` seam without production-code widening

## Verification
- `python3 -m py_compile tests/test_presence_history_api_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_history_api_contract.py`
- Result: `3 passed`

## Next exact pull
`CORE-HABITUS-202-G` on `POST /api/v1/presence/hold`, with one dedicated `tests/test_presence_hold_api_contract.py` proof ring only for the existing `401` auth gate, `400` on missing `person_id`, canonical hold-set payload on create/update, and no widening into hold-clear, update ingestion, or timeout handling.
