# PS Core — VFM-002 / CORE-VFM-002-B voice command confirmation follow-through

**Date:** 2026-04-18 Europe/Berlin  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Landed the next bounded `POST /api/v1/voice/command` follow-through slice by persisting the first real confirmation payloads in the canonical dialog state and exposing explicit confirm/reject endpoints on the same command surface.

## Why

`CORE-VFM-002-A` opened the router entrypoint, but unsafe commands still stopped at `confirmation_required` without a real persisted action payload or a way to finish the flow through `/api/v1/voice/command` itself. That left the confirmation contract incomplete for both restart-safe Core state and upcoming HA bridge wiring.

## Change

Added the first real confirmation follow-through on top of the live router surface:

- extended `addons/pilotsuite/app/copilot_core/voice/command_router.py` so confirmation-required decisions now carry a real pending action payload (`lock.unlock`, `cover.open_cover` / `close_cover`, `switch.turn_off`, broad `light.turn_on` / `turn_off`) instead of only heuristics plus a token
- extended `addons/pilotsuite/app/copilot_core/voice/dialog_state.py` so explicit confirmation prompts survive in the persisted dialog state and stay available to the existing dialog-state read path
- extended `addons/pilotsuite/app/copilot_core/api/v1/voice.py` so `/api/v1/voice/command` persists pending action payloads, labels, tokens, and expiry metadata inside the canonical dialog state surface
- added new routes:
  - `POST /api/v1/voice/command/confirm`
  - `POST /api/v1/voice/command/reject`
- widened `GET /api/v1/voice/dialog/state` with explicit pending-action metadata so follow-on HA projection does not need to infer everything from opaque slot data
- extended `tests/test_voice_command_api.py` with follow-through coverage for confirm, reject, and mismatched-token rejection

## Verification

- `/config/clawd/.venv_smoke_gate/bin/python -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py addons/pilotsuite/app/copilot_core/voice/command_router.py addons/pilotsuite/app/copilot_core/voice/dialog_state.py tests/test_voice_command_api.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py` → `8 passed in 0.24s`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_intent_slice396_contract.py tests/test_voice_intent_slice398_active_devices_replay_contract.py tests/test_voice_intent_slice400_nested_zone_replay_contract.py tests/test_voice_language_preference_slice402_contract.py tests/test_voice_status_query_slice401_context_rendering_contract.py` → `28 passed in 0.40s`

## Files touched

- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `addons/pilotsuite/app/copilot_core/voice/command_router.py`
- `addons/pilotsuite/app/copilot_core/voice/dialog_state.py`
- `tests/test_voice_command_api.py`
- `docs/analysis/PS_CORE_VFM_002B_VOICE_COMMAND_CONFIRMATION_FOLLOW_THROUGH_2026-04-18.md`

## Blocker removed

`/api/v1/voice/command` no longer stops at a dead-end `confirmation_required` token. The Core runtime now persists the first real pending confirmation payloads and can close the unsafe-command loop through explicit confirm/reject endpoints on the same command surface.

## Next single step

Land one thin `GET /api/v1/voice/command/state` session read surface with explicit `last_status`, `pending_confirmation`, `pending_action_label`, and `confirmation_expires_at` fields so the HA bridge can project router state without parsing raw dialog-slot internals.
