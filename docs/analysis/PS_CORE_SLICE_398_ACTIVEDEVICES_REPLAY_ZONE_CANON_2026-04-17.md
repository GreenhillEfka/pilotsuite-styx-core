# PS Core — Slice 398: `active_devices` Replay + Zone Canonicalization

**Date:** 2026-04-17  
**Commit:** `3728f038`  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Problem

Auf dem Same-Zone Replay-Chain Seam (`POST /api/v1/voice/intent` mit `context` Body) fehlten zwei Features:

1. **`active_devices`** wurden aus dem Request Body nicht gereplayt — `build_context()` kannte den Parameter nicht, und `process_intent()` extrahierte ihn nicht
2. **Zone-Namen** wurden nicht canonicalisiert — `"Wohnzimmer"` blieb `"Wohnzimmer"`, nicht `"wohnzimmer"`

## Fix

### `voice.py` — `process_intent()`

- `active_devices` aus `req_context` extrahiert
- Zone-Canonicalisierung: `zone = zone.lower() if zone else zone`
- Zone-Fallback: `context.zone_name` → `zone` wenn nicht explizit gesetzt
- Duplizierte `_get_context_builder()` Calls entfernt

### `context_builder.py` — `build_context()`

- `active_devices: Optional[List[Dict[str, Any]]] = None` zur Signatur hinzugefügt
- Wenn `active_devices` übergeben: konvertiere Dict-Liste zu `DeviceContext`-Objekten
- Wenn nicht übergeben: baue aus `sensor_data` wie zuvor

## Exit Criteria (erfüllt)

| Kriterium | Status |
|-----------|--------|
| `active_devices` aus Body in Response | ✅ |
| `active_devices` empty list → empty list | ✅ |
| kein Body-Context → built context (kein crash) | ✅ |
| Zone canonicalized (Wohnzimmer → wohnzimmer) | ✅ |
| `user_preferences` weiterhin funktional | ✅ |
| Smoke Gate 22/22 | ✅ |

## Geänderte Files

- `addons/pilotsuite/app/copilot_core/api/v1/voice.py` (+12/-17)
- `addons/pilotsuite/app/copilot_core/voice/context_builder.py` (+21)
- `tests/test_voice_intent_slice398_active_devices_replay_contract.py` (+108, neu)

## Smoke Gate

```
22 passed — 3 files (test_energy_forecast, test_sensors, test_voice_intent_slice396, test_voice_intent_slice398)
```

## Verbliebene Replay-Seams (separate Fixes)

| Seam | Grund | Priorität |
|------|-------|-----------|
| `relevant_patterns` | Live service derivation (pattern_detection) | Low |
| `recent_actions` | habitus_service call, kein Replay-Pfad | Low |
| `sensor_data` | Nicht in returned context | Low |
