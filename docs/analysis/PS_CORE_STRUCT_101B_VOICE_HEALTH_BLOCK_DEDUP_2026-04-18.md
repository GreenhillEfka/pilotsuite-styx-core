# PS Core — CORE-STRUCT-101B Voice Health Block Deduplication

**Date:** 2026-04-18 14:27 Europe/Berlin
**Lane:** PilotClaw / Core
**Status:** ✅ DONE

## Why this slice exists

`CORE-RESCUE-004-D` (e37444d2) embedded voice capability truth in both `/health` and `/ready` endpoints, but did so via inlined logic duplicated across `app.py` (root health) and `metrics.py` (readiness probe).

Two copies of the same capability-detection pattern meant future changes to voice backend detection had to be applied twice, increasing the risk of drift.

## Artifacts changed

- `addons/pilotsuite/app/copilot_core/voice/voice_health.py` — NEW shared helper
  - `get_voice_health_block()`: single source of truth for voice capability detection
  - Graceful degradation when Whisper/Piper unavailable
  - Called by both `app.py` and `metrics.py` endpoints
- `addons/pilotsuite/app/copilot_core/app.py` — replaced inline block with shared helper call
- `addons/pilotsuite/app/copilot_core/api/v1/metrics.py` — removed `_build_voice_health_block`, now calls shared helper

## Blocker removed

One canonical `get_voice_health_block()` now serves all health/readiness surfaces. Voice backend detection logic is no longer duplicated.

## Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/voice/voice_health.py \
  addons/pilotsuite/app/copilot_core/app.py \
  addons/pilotsuite/app/copilot_core/api/v1/metrics.py
# ✅ ALL OK
python -m pytest tests/ -q
# 489 passed, 20 skipped
```

## Next exact step

`CORE-STRUCT-101C / Runtime health checker wired to shared voice block` — extend the shared voice health helper into `/api/v1/status` and `/api/v1/capabilities` so the same canonical block reaches more consumers without further duplication.