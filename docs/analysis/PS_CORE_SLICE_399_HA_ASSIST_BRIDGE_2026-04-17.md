# PS Core — Slice 399: HA Assist Bridge Endpoint

**Date:** 2026-04-17  
**Commit:** `ab1688d9`  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Neuer Endpoint **`POST /api/v1/voice/ha/assist`** — Core-seitiger Boundary für Home Assistant's Assist-Pipeline.

## Warum

HA's Assist-Interface sendet typischerweise `{"text": "...", "sentence": "..."}`-Payloads. Dieser Endpoint:
1. Akzeptiert beide Felder (`text` oder `sentence`)
2. Routet durch denselben `process_intent()` Flow wie alle anderen Voice Caller
3. Unterstützt vollen Context-Replay (`user_preferences`, `active_devices`, `zone`)
4. Gibt `source: "ha_assist"` in der Response zurück

## API

```
POST /api/v1/voice/ha/assist
```

**Request:**
```json
{
  "text": "Mach das Licht an",        // transcribed text (required)
  "sentence": "...",                  // or alias for text
  "language": "de",                   // optional
  "zone": "wohnzimmer",              // optional
  "context": {...},                  // optional, existing voice context
  "ha_entity_id": "light.wohnzimmer"  // optional, HA entity
}
```

**Response:** Same as `POST /api/v1/voice/intent` + `"source": "ha_assist"`

## Exit Criteria

| Kriterium | Status |
|-----------|--------|
| `/ha/assist` akzeptiert `text` Feld | ✅ |
| `/ha/assist` akzeptiert `sentence` Feld | ✅ |
| 400 bei fehlendem text/sentence | ✅ |
| Context Replay funktioniert | ✅ |
| Zone canonicalization | ✅ |
| Smoke Gate 27/27 | ✅ |

## Geänderte Files

- `addons/pilotsuite/app/copilot_core/api/v1/voice.py` (+92)
- `tests/test_voice_ha_assist_bridge_contract.py` (+128, neu)

## Smoke Gate

```
27 passed (4 test files)
```

## HA-seitiger Teil (HA-Lane)

Der HA-seitige Voice Router (HomeClaw's Slice 163) muss jetzt:
1. `POST https://core:18792/api/v1/voice/ha/assist` aufrufen mit dem transcribed text
2. Die Response an HA's Assist-Pipeline zurückgeben

Core-Boundary ist jetzt fertig.
