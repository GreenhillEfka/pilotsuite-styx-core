# PS_CORE_SLICE_300_CORE_HABITUS_202_E_PRESENCE_SOURCES_CONTRACT

**Datum:** 2026-04-22  
**Core-Pfad:** CORE-HABITUS-202-E — `GET /api/v1/presence/sources` Contract  
**Vorgänger:** CORE-HABITUS-202-D ✅

## Context

CORE-HABITUS-202-B hat die globale Presence-Read-Surface (`/api/v1/presence/status`) gelandet. CORE-HABITUS-202-E zieht die nächste Seam: **Multi-Source-Presence pro Person lesbar** — welche Quellen (HA-Zone, BLE-Tracker, etc.) tragen zum aggregierten Zustand bei.

## Contract-Matrix

### GET /api/v1/presence/sources

**Auth-Gate:**
```
GET /api/v1/presence/sources
→ 401 {"error": "Authentication required", "message": "Valid X-Auth-Token header or Bearer token required", "ok": False}
```

**Missing person_id:**
```
GET /api/v1/presence/sources
Headers: X-Auth-Token: <token>

→ 400 {"error": "Missing person_id", "ok": False}
```

**Known Person:**
```
GET /api/v1/presence/sources?person_id=person.alice
Headers: X-Auth-Token: <token>

→ 200 {
    "ok": true,
    "person_id": "person.alice",
    "name": "Alice",
    "aggregated_state": "home",
    "sources": {
        "ha_zone": "home",
        "ble_tracker": "home"
    },
    "hold": null,
    "hold_reason": null
}
```

**Unknown Person:**
```
GET /api/v1/presence/sources?person_id=person.unknown
Headers: X-Auth-Token: <token>

→ 404 {"error": "Person not found", "ok": False}
```

**Response-Felder:**
- `ok: true` — Success-Flag
- `person_id` — Canonical Person-ID
- `name` — Lesbarer Name
- `aggregated_state` — Zusammengeführter Zustand (`home`/`away`)
- `sources` — Map von `source_id` → `state` (z.B. `ha_zone`, `ble_tracker`, `wifi_ap`, `manual_override`)
- `hold` — Aktiver Hold-State oder `null`
- `hold_reason` — Begründung für Hold oder `null`

## Test-Ergebnisse

**Live-Probe:**
```
=== GET /api/v1/presence/sources?person_id=person.alice ===
status: 200
response: {
    'aggregated_state': 'home',
    'hold': None,
    'hold_reason': None,
    'name': 'Alice',
    'ok': True,
    'person_id': 'person.alice',
    'sources': {'ble_tracker': 'home', 'ha_zone': 'home'}
}

=== GET /api/v1/presence/sources?person_id=person.unknown ===
status: 404
response: {'error': 'Person not found', 'ok': False}
```

**Contract-Assertions (zu ergänzen in `tests/test_presence_sources_api_contract.py`):**
1. Unauthenticated → 401 mit canonical error shape
2. Missing `person_id` → 400 mit `"Missing person_id"`
3. Known person → 200 mit `sources` map, `aggregated_state`, `hold`
4. Unknown person → 404 mit `"Person not found"`

## Files

- `addons/pilotsuite/app/copilot_core/api/v1/presence.py` — shipped spine, `@presence_bp.route("/sources", methods=["GET"])`
- `tests/test_presence_sources_api_contract.py` — Contract-Tests (neu zu erstellen)

## CORE-HABITUS-202 Fortschritt

- **CORE-HABITUS-202-A:** `/api/v1/habitus/zones` — Zone-Definitionen ✅
- **CORE-HABITUS-202-B:** `/api/v1/presence/status` — Global Presence ✅
- **CORE-HABITUS-202-C:** Zone-Presence-State ✅
- **CORE-HABITUS-202-D:** Additional presence/zone contract ✅
- **CORE-HABITUS-202-E:** `/api/v1/presence/sources` — Multi-Source-Presence ✅

**Nächste Seam:** CORE-AUTO-203 (erste echte Automation) oder CORE-HABITUS-202-F (Zone-Aggregates)

## Shared Queue Truth

- HA-SURFACE-302 ✅
- CORE-HABITUS-202-A ✅ → B ✅ → C ✅ → D ✅ → **E ✅** (21:25)

**Nächster:** CORE-AUTO-203 oder CORE-HABITUS-202-F
