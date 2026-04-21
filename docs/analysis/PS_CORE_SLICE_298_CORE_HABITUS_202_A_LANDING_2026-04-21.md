# PS_CORE_SLICE_298_CORE_HABITUS_202_A_LANDING

**Datum:** 2026-04-21  
**Core-Pfad:** CORE-HABITUS-202-A — `/api/v1/habitus/zones` Contract gelandet  
**VM-02 abgeschlossen:** Slices 293→294→295→296→297 alle grün

## Context

HomeClaw hat `HA-SURFACE-302` um 14:15 geschlossen — `HabitusZoneSensor` konsumiert jetzt echten `/api/v1/habitus/zones`-Endpoint. CommonUnlockGate für CORE-HABITUS-202-A ist gefallen.

## Contract-Matrix

### 1. Auth-Gate (Front Door)

**Unauthenticated:**
```
GET /api/v1/habitus/zones
→ 401 {"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}
```

### 2. Authenticated Default (include_metrics=true)

**Request:**
```
GET /api/v1/habitus/zones
Headers: X-Auth-Token: <token>
```

**Response:**
```json
{
  "status": "ok",
  "total_zones": 10,
  "zones": [
    {
      "id": "living",
      "zone_type": "living",
      "name_de": "Wohnzimmer",
      "name_en": "Living Room",
      "module_overrides": {"light": {...}, "motion": {...}, "music": {...}, "volume": {...}, "tv": {...}, "climate": {...}, "camera": {...}},
      "metrics": {"entity_count": 3, "active_lights": 1, "avg_temperature": 21.5, ...}
    },
    ...
  ]
}
```

**Canonical Zone-IDs:** `living`, `bath`, `kitchen`, `office`, `hallway`, `bedroom`, `room_mira`, `room_paul`, `terrace`, `outside`

**Canonical Module-Override-Keys:** `light`, `motion`, `music`, `volume`, `tv`, `climate`, `camera`

### 3. Authenticated ohne Metrics

**Request:**
```
GET /api/v1/habitus/zones?include_metrics=false
Headers: X-Auth-Token: <token>
```

**Response:**
- `total_zones: 10` (unchanged)
- `zones[].metrics` nicht present
- `zones[].module_overrides` bleibt vollständig

### 4. Invalid Zone-Type

**Request:**
```
GET /api/v1/habitus/zones?zone_type=garage
Headers: X-Auth-Token: <token>
```

**Response:**
```json
{
  "error": "invalid_zone_type",
  "message": "Invalid zone type: garage. Valid values: ['living', 'bath', 'kitchen', ...]"
}
```
→ **400 Bad Request**

## Test-Ergebnisse

```
tests/test_habitus_zones_api_contract.py: 4 passed in 0.22s
```

**Assertions:**
1. `test_get_habitus_zones_requires_auth_front_door` — 401 ohne Auth ✅
2. `test_get_habitus_zones_returns_default_metrics_and_canonical_module_overrides` — 10 Zonen, 7 module_override_keys, metrics present ✅
3. `test_get_habitus_zones_can_omit_metrics_without_changing_zone_count` — 10 Zonen, keine metrics ✅
4. `test_get_habitus_zones_rejects_invalid_zone_type_with_existing_400_path` — 400 bei invalid zone_type ✅

## Files

- `addons/pilotsuite/app/copilot_core/api/v1/habitus_zones.py` — shipped spine, keine Änderungen nötig
- `tests/test_habitus_zones_api_contract.py` — Contract-Tests für CORE-HABITUS-202-A

## Shared Queue Truth

- **HA-SURFACE-302:** geschlossen 2026-04-21 14:15 ✅
- **CORE-HABITUS-202-A:** gelandet 2026-04-21 14:40 ✅
- **Nächster Core-Pull:** CORE-HABITUS-202-B (nächste Seam auf bound 48h order) oder warten auf Andreas-Zug

## VM-02 Status

VM-02 Kette (293→294→295→296→297) bleibt grün und abgeschlossen. Core-Pfad wechselt von VM-02 auf CORE-HABITUS-202-A. Blöcke 4/5 bleiben geparkt.
