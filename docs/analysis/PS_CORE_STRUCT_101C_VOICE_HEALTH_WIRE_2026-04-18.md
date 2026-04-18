# PS Core — CORE-STRUCT-101C Voice Health Block Wire

**Date:** 2026-04-18 14:35 Europe/Berlin
**Lane:** PilotClaw / Core
**Status:** ✅ DONE

## Why this slice exists

After `CORE-STRUCT-101B` deduplicated voice health into a shared helper, three surfaces still lacked the real-time voice block:
- `/api/v1/capabilities` returned static discovery metadata only
- `/api/v1/status` returned version/port without voice runtime truth

This slice closes the last bounded gaps so every Core health/readiness surface carries the same canonical voice block.

## Artifacts changed

- `addons/pilotsuite/app/copilot_core/api/voice_discovery.py`
  - `voice_capabilities_module()` now embeds live `get_voice_health_block()` runtime truth
  - `/api/v1/capabilities` → real-time Whisper/Piper availability
- `addons/pilotsuite/app/copilot_core/app.py`
  - `/api/v1/status` now includes `voice: get_voice_health_block()`
  - aligns with `/health`, `/ready`, `/capabilities` voice block pattern

## Resulting canonical surfaces

| Endpoint | Voice Block |
|----------|-------------|
| `GET /health` | ✅ `get_voice_health_block()` |
| `GET /ready` (`/api/v1/metrics/ready`) | ✅ `get_voice_health_block()` |
| `GET /api/v1/capabilities` | ✅ `voice_capabilities_module()` → `runtime` |
| `GET /api/v1/status` | ✅ `get_voice_health_block()` |

## Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/app.py \
  addons/pilotsuite/app/copilot_core/api/voice_discovery.py
# ✅ ALL OK
python -m pytest tests/ -q
# 492 passed, 20 skipped
```

## Next exact step

`CORE-STRUCT-101D / Runtime health checker — wire health-checker dependency truth into voice surfaces` — extend the existing `HealthChecker` dependency model to consume `get_voice_health_block()` for its dependency graph so the monitoring layer knows which voice backends are present before surfacing readiness to HA callers.