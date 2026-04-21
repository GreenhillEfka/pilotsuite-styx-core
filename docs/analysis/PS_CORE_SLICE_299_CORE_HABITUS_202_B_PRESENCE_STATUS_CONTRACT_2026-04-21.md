# PS_CORE_SLICE_299_CORE_HABITUS_202_B_PRESENCE_STATUS_CONTRACT

**Datum:** 2026-04-21  
**Core-Pfad:** CORE-HABITUS-202-B — `/api/v1/presence/status` Contract  
**Vorgänger:** CORE-HABITUS-202-A (`/api/v1/habitus/zones`) ✅

## Context

CORE-HABITUS-202-A hat die Zone/Habitus-Definitionssurface gelandet (`/api/v1/habitus/zones`). CORE-HABITUS-202-B zieht die nächste Seam: **Presence/Zone-Daten laufen ins Core und sind lesbar**.

## Contract-Matrix

### GET /api/v1/presence/status

**Auth-Gate:**
```
GET /api/v1/presence/status
→ 401 {"error": "Authentication required", "message": "Valid X-Auth-Token header or Bearer token required", "ok": False}
```

**Authenticated Success:**
```
GET /api/v1/presence/status
Headers: X-Auth-Token: <token>

→ 200 {
    "ok": true,
    "persons_home": [{"person_id": "person.alice", "name": "Alice", "state": "home", "zone": "wohnzimmer"}],
    "persons_away": [{"person_id": "person.bob", "name": "Bob", "state": "away", "zone": null}],
    "total_home": 1,
    "total_tracked": 2,
    "last_updated": 1776774000.0,
    "hold_active": {}
}
```

**Response-Felder:**
- `ok: true` — Success-Flag
- `persons_home` — Array aller Personen im Zustand `home` (sortiert nach Name)
- `persons_away` — Array aller Personen im Zustand `away` (sortiert nach Name)
- `total_home` — Count der Personen zuhause
- `total_tracked` — Gesamtzahl getrackter Personen
- `last_updated` — Unix-Timestamp des letzten Updates
- `hold_active` — Map von `person_id` → `hold_state` für manuelle Override-Zustände

**Hold-State-Integration:**
- Wenn `hold` aktiv ist, wird der Hold-Zustand statt des berechneten Zustands verwendet
- `hold_active` zeigt alle aktiven Holds im Response

## Test-Ergebnisse

**Live-Probe:**
```
=== GET /api/v1/presence/status ===
status: 200
ok: True
persons_home: ['Alice']
persons_away: ['Bob']
total_home: 1
total_tracked: 2
```

**Contract-Assertions (zu ergänzen in `tests/test_presence_api_contract.py`):**
1. Unauthenticated → 401 mit canonical error shape
2. Authenticated → 200 mit `ok: true`, `persons_home`, `persons_away`, `total_home`, `total_tracked`
3. `persons_home` und `persons_away` sind nach Name sortiert
4. `hold_active` zeigt aktive Hold-Overrides

## Files

- `addons/pilotsuite/app/copilot_core/api/v1/presence.py` — shipped spine, `@presence_bp.route("/status", methods=["GET"])`
- `tests/test_presence_api_contract.py` — Contract-Tests (zu ergänzen)

## CORE-HABITUS-202 Fortschritt

- **CORE-HABITUS-202-A:** `/api/v1/habitus/zones` — Zone-Definitionen mit module_overrides ✅
- **CORE-HABITUS-202-B:** `/api/v1/presence/status` — Presence-Read-Surface ✅
- **Nächste Seam:** Zone-Presence-State (`/api/v1/presence/zone/presence/<zone_id>/state`) oder Automation (`/api/v1/zone/automation`)

## Shared Queue Truth

- HA-SURFACE-302 ✅ (14:15)
- CORE-HABITUS-202-A ✅ (14:40)
- **CORE-HABITUS-202-B ✅** (14:45)

**Nächster:** CORE-HABITUS-202-C (Zone-Presence-State) oder CORE-AUTO-203 (erste Automation)
