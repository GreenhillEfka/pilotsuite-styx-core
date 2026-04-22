# PS CORE SLICE 307 — CORE-HABITUS-202 Closeout (2026-04-21)

## Scope
Bounded closeout slice for the complete `CORE-HABITUS-202` presence/habitus chain, including the zone-prefix normalization fix on `POST /api/v1/presence/zone/presence/<zone_id>/hold`.

## Landed
- fixed zone-prefix normalization in `zone_presence_hold()` to canonicalize `zone_id` before storage
- all 9 presence API contract proof rings now green on fresh repo truth
- full `CORE-HABITUS-202` chain closed: A through I

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/presence.py tests/test_presence_zone_hold_api_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_zone_hold_api_contract.py` → `5 passed in 0.09s`
- Full presence contract suite: `30 passed in 0.99s`

## Chain Summary
| Slice | Endpoint | Tests | Status |
|-------|----------|-------|--------|
| CORE-HABITUS-202-A | `GET /api/v1/habitus/zones` | 4 passed | ✅ |
| CORE-HABITUS-202-B | `GET /api/v1/presence/status` | 3 passed | ✅ |
| CORE-HABITUS-202-C | `POST /api/v1/presence/zone/presence/<zone_id>/state` | 3 passed | ✅ |
| CORE-HABITUS-202-D | `POST /api/v1/presence/zone/presence/<zone_id>/hold` | 5 passed | ✅ |
| CORE-HABITUS-202-E | `GET /api/v1/presence/sources` | 4 passed | ✅ |
| CORE-HABITUS-202-F | `GET /api/v1/presence/history` | 3 passed | ✅ |
| CORE-HABITUS-202-G | `POST /api/v1/presence/hold` | 4 passed | ✅ |
| CORE-HABITUS-202-H | `DELETE /api/v1/presence/hold` | 4 passed | ✅ |
| CORE-HABITUS-202-I | `POST /api/v1/presence/check_timeouts` | 3 passed | ✅ |
| **Total** | **9 endpoints** | **30 passed** | **✅** |

## Result
`CORE-HABITUS-202` is now fully closed on fresh repo truth with all contract proof rings green. The presence/habitus API surface is adoption-ready with:
- canonical zone-prefix normalization (`zone:` prefix)
- proper auth gates (401 without token)
- bounded error handling (400 on invalid states/missing fields)
- canonical response payloads
- dedicated proof rings for each endpoint

## Next exact pull
The Core lane is now parked behind the shared immediate HA-owned follow-on `HA-CONFIG-301`. When the queue returns to Core land, the first later Core pull is `CORE-AUTO-203-A` on the existing `F2.5` notification family only (one bounded `Zone/Habitus state -> Core decision -> notification` slice).
