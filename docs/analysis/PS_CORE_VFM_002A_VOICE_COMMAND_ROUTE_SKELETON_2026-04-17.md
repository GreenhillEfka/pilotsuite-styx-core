# PS Core — VFM-002 / CORE-VFM-002-A voice command route skeleton

**Date:** 2026-04-17 23:08 Europe/Berlin  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Opened the first bounded `POST /api/v1/voice/command` implementation slice on the active Core runtime surface.

## Why

Core needed a real Step-4 entrypoint for the VFM-001 HA voice router contract instead of leaving `/api/v1/voice/command` as planning-only scope. The immediate blocker was the absence of one live route with explicit `safe / clarify / confirm / reject` behavior and proof that it coexists cleanly with the already-shipped `/api/v1/voice/*` surfaces.

## Change

Added a thin command-router seam and wired it into the canonical voice API:

- new route `POST /api/v1/voice/command` in `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- new focused policy module `addons/pilotsuite/app/copilot_core/voice/command_router.py`
- dialog-state metadata support in `addons/pilotsuite/app/copilot_core/voice/dialog_state.py` so confirmation and clarification state can carry the first router metadata payloads
- focused contract coverage in `tests/test_voice_command_api.py`

The bounded v1 behavior now proven in Core:

- **safe** high-confidence commands execute and expose the HA action surface
- **clarify** catches medium-confidence ambiguous commands
- **confirm** catches high-confidence unsafe/broad commands and emits a confirmation token
- **reject** handles low-confidence unknown commands without silent execution

The route also returns the normalized session/dialog snapshot so the existing dialog machinery remains the single state surface for follow-on router slices.

## Verification

- `/config/clawd/.venv_smoke_gate/bin/python -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py addons/pilotsuite/app/copilot_core/voice/command_router.py addons/pilotsuite/app/copilot_core/voice/dialog_state.py tests/test_voice_command_api.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_intent_slice396_contract.py tests/test_voice_intent_slice398_active_devices_replay_contract.py tests/test_voice_intent_slice400_nested_zone_replay_contract.py tests/test_voice_language_preference_slice402_contract.py tests/test_voice_status_query_slice401_context_rendering_contract.py` → `25 passed in 0.36s`

## Files touched

- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `addons/pilotsuite/app/copilot_core/voice/command_router.py`
- `addons/pilotsuite/app/copilot_core/voice/dialog_state.py`
- `tests/test_voice_command_api.py`
- `docs/analysis/PS_CORE_VFM_002A_VOICE_COMMAND_ROUTE_SKELETON_2026-04-17.md`

## Blocker removed

`/api/v1/voice/command` is no longer a missing Core contract surface. The active runtime now has one real router entrypoint with explicit decision states and proof-backed coexistence with the existing voice API.

## Next single step

Start the next bounded VFM-002 router slice by mapping the first real unsafe/safe family payloads beyond heuristics, specifically confirmation persistence plus confirm/reject follow-through on the new `/api/v1/voice/command` state surface.
