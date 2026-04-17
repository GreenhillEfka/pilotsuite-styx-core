# PS Core — P-CORE-001 Closure: Voice Replay Chain DONE

**Date:** 2026-04-17  
**Status:** ✅ CLOSED

## Was

Alle bounded `/api/v1/voice/intent` + `/ha/assist` Replay-Seams sind jetzt file-backed und mit Tests bewiesen.

## Erledigte Slices

| Slice | Feature | Commit |
|-------|---------|--------|
| 392 | `timestamp` + `context_version` Replay | `36e3b6fd` |
| 393 | `mood` Replay | `fc3c6e83` |
| 394 | `time` Replay | `1ed3a6b2` |
| 395 | `language_preference` Replay | `4b3c82df` |
| 396 | `user_preferences` Replay + Double-Zone | `36590bcf` |
| 397 | Replay Chain Exit Rule Doc | `181a3056` |
| 398 | `active_devices` Replay + Zone Canon | `3728f038` |
| 399 | HA Assist Bridge `/ha/assist` | `ab1688d9` |
| 400 | `language_preference` → `response.language` | `e99e8153` |

## Exit Criteria erfüllt

- ✅ `context.timestamp` replay → file-backed
- ✅ `context.context_version` replay → file-backed
- ✅ `context.mood` replay → file-backed (built fresh, no gap)
- ✅ `context.time` replay → file-backed
- ✅ `context.language_preference` replay → file-backed
- ✅ `context.user_preferences` replay → file-backed
- ✅ `context.active_devices` replay → file-backed
- ✅ Zone Canonicalization → implementiert
- ✅ HA Assist Bridge → `/ha/assist` Endpoint
- ✅ `language_preference` → `response.language` → implementiert

## Smoke Gate

**30/30** ✅ (5 Test-Files)

## Verbliebene low-priority Seams (kein Replay-Problem)

| Seam | Grund |
|------|-------|
| `relevant_patterns` | Live service derivation |
| `recent_actions` | kein Replay-Pfad |
| `sensor_data` | nicht in returned context |

## Nächster Pull

**P-CORE-002**: Restliche Core-Adjacent-Seams — Bucket A/B aus dem Loop-Dokument:
- VFM-006 boundary cleanup continuation
- F10.5 usage pattern reporting
- Oder: nächster von Orakel/DesignClaw genannter Task

Core-Lane ist bereit für den nächsten bounded Task.
