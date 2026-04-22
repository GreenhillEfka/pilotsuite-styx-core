# PS_CORE_SLICE_301_CORE_AUTO_203_A_ZONE_AUTOMATION_DASHBOARD

**Datum:** 2026-04-22  
**Core-Pfad:** CORE-AUTO-203-A — Zone Automation Dashboard  
**Vorgänger:** CORE-HABITUS-202-E ✅

## Context

CORE-HABITUS-202 (A→B→C→D→E) hat Zone-Definitionen und Presence-Daten ins Core gelandet. CORE-AUTO-203 zieht die erste echte Automation: **Zone/Habitus → Core Decision → sichtbare Aktion**. Startpunkt ist das Zone Automation Dashboard.

## Contract-Matrix

### GET /api/v1/zone-automation/dashboard

**Auth:** Optional (`@optional_token`)

**Success:**
```
GET /api/v1/zone-automation/dashboard
→ 200 {
    "ok": true,
    "zones": [
        {"zone_id": "wohnzimmer", "state": "active", "automation_mode": "autonomy"}
    ]
}
```

**Controller not initialized:**
```
GET /api/v1/zone-automation/dashboard
→ 503 {"ok": false, "error": "Controller not initialized"}
```

### GET /api/v1/zone-automation/zones/<zone_id>

**Auth:** Optional (`@optional_token`)

**Success:**
```
GET /api/v1/zone-automation/zones/wohnzimmer
→ 200 {
    "ok": true,
    "zone_id": "wohnzimmer",
    "state": "active",
    "automation_mode": "autonomy",
    "config": {...}
}
```

**Unknown Zone:**
```
GET /api/v1/zone-automation/zones/unknown
→ 404 {"ok": false, "error": "Zone not found"}
```

### POST /api/v1/zone-automation/zones/<zone_id>/mode

**Auth:** Required (`@require_token`)

**Request:**
```json
{"mode": "off" | "learning" | "autonomy"}
```

**Success:**
```
→ 200 {"ok": true, "zone_id": "wohnzimmer", "automation_mode": "autonomy"}
```

**Invalid Mode:**
```
→ 400 {"ok": false, "error": "Invalid mode 'invalid'. Valid: off, learning, autonomy"}
```

## Test-Ergebnisse

**Live-Probe:**
```
=== GET /api/v1/zone-automation/dashboard ===
status: 200
response: {'ok': True, 'zones': [{'automation_mode': 'autonomy', 'state': 'active', 'zone_id': 'wohnzimmer'}]}
```

**Contract-Assertions (zu ergänzen in `tests/test_zone_automation_api_contract.py`):**
1. Dashboard ohne Auth → 200 (optional_token)
2. Dashboard mit Controller → 200 mit `ok: true`, `zones[]`
3. Zone-State → 200 mit `zone_id`, `state`, `automation_mode`, `config`
4. Set Mode ohne Auth → 401
5. Set Mode mit invalid mode → 400
6. Set Mode mit valid mode → 200

## Files

- `addons/pilotsuite/app/copilot_core/api/v1/zone_automation.py` — shipped spine
- `tests/test_zone_automation_api_contract.py` — Contract-Tests (neu zu erstellen)

## CORE-AUTO-203 Fortschritt

- **CORE-AUTO-203-A:** `/api/v1/zone-automation/dashboard` — Automation Overview ✅
- **Nächste:** CORE-AUTO-203-B (Presence-Trigger → Light/Music Action)

## Shared Queue Truth

- HA-SURFACE-302 ✅
- CORE-HABITUS-202 (A→B→C→D→E) ✅
- **CORE-AUTO-203-A ✅** (21:35)

**Nächster:** CORE-AUTO-203-B (erste echte Presence→Action Automation)
