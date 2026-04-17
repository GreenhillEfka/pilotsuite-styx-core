# PS Core — VFM-002 / CORE-VFM-002-C voice command state surface

**Date:** 2026-04-18 Europe/Berlin  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Landed the next thin read seam for the bounded voice-command router path:

- `GET /api/v1/voice/command/state`

The route is session-scoped and exposes one explicit HA-consumable state object instead of forcing downstream callers to inspect raw dialog-slot internals.

## Why

`CORE-VFM-002-B` closed confirm/reject follow-through, but the first downstream consumer still had no dedicated state read contract. HA callers would have needed to lean on `GET /api/v1/voice/dialog/state` plus opaque slot metadata, which kept the router-state contract fuzzy and harder to project safely.

## Change

Added one thin router-state surface on top of the existing persisted dialog machine:

- extended `addons/pilotsuite/app/copilot_core/api/v1/voice.py` with `GET /api/v1/voice/command/state?session_id=...`
- kept the route token-protected and in the same runtime family as the rest of `/api/v1/voice/command`
- made the response explicitly session-scoped, returning a truthful idle shape for non-matching or absent state instead of inventing pending confirmation data
- normalized the read contract to exactly these first-class fields:
  - `last_status`
  - `pending_confirmation`
  - `pending_action_label`
  - `confirmation_expires_at`
- added lightweight persisted `_last_status` metadata so confirm/reject follow-through still reports the last router outcome even after the dialog machine returns to `IDLE`
- added focused route tests plus one HA-bridge-facing projection test

## Verification

- `/config/clawd/.venv_smoke_gate/bin/python -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py addons/pilotsuite/app/copilot_core/voice/command_router.py addons/pilotsuite/app/copilot_core/voice/dialog_state.py tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py` → green

## Files touched

- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `addons/pilotsuite/app/copilot_core/voice/dialog_state.py`
- `tests/test_voice_command_api.py`
- `tests/test_voice_ha_assist_bridge_contract.py`
- `docs/analysis/PS_CORE_VFM_002C_VOICE_COMMAND_STATE_SURFACE_2026-04-18.md`

## Blocker removed

The HA bridge no longer has to infer router state from `dialog/state` plus raw slot payloads. Core now exposes one explicit session-scoped state seam for the bounded `voice/command` flow.

## Next single step

`CORE-FRONTEND-BACKEND-001 / HA VOICE ROUTER PROJECTION` — bind the new Core state seam into the HA-side voice projection path so `last_voice_command_status`, `pending_confirmation`, and `pending_action_label` can surface without opening a broader UI branch.
