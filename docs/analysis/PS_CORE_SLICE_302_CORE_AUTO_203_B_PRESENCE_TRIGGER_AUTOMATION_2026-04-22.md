# PS_CORE_SLICE_302_CORE_AUTO_203_B_PRESENCE_TRIGGER_AUTOMATION

**Datum:** 2026-04-22  
**Core-Pfad:** CORE-AUTO-203-B — Presence→Action Automation  
**Vorgänger:** CORE-AUTO-203-A ✅

## Context

CORE-AUTO-203-A hat das Zone Automation Dashboard gelandet. CORE-AUTO-203-B zieht die **erste echte Automation**: Presence-Event → Core Decision → Light/Music Action. Das ist der erste Ende-zu-Ende-Automationspfad von Zone/Habitus-Daten zu sichtbarer Reaktion.

## Contract-Matrix

### POST /api/v1/zone-automation/zones/<zone_id>/presence

**Auth:** Required (`@require_token`)

**Request:**
```json
{"detected": true}  // oder false für Abwesenheit
```

**Presence Detected:**
```
POST /api/v1/zone-automation/zones/wohnzimmer/presence
Headers: X-Auth-Token: <token>
Body: {"detected": true}

→ 200 {
    "ok": true,
    "actions": [
        {"action": "light.turn_on", "entity": "light.wohnzimmer"},
        {"action": "music.play", "entity": "media_player.wohnzimmer"}
    ]
}
```

**Presence Cleared:**
```
POST /api/v1/zone-automation/zones/wohnzimmer/presence
Headers: X-Auth-Token: <token>
Body: {"detected": false}

→ 200 {
    "ok": true,
    "actions": [
        {"action": "light.turn_off", "entity": "light.wohnzimmer"},
        {"action": "music.stop", "entity": "media_player.wohnzimmer"}
    ]
}
```

**Controller not initialized:**
```
→ 503 {"ok": false, "error": "Controller not initialized"}
```

## Automation-Logik

**Bei Presence Detected:**
1. `light.turn_on` für Zone-Licht
2. `music.play` für Zone-Media

**Bei Presence Cleared:**
1. `light.turn_off` für Zone-Licht
2. `music.stop` für Zone-Media

## Test-Ergebnisse

**Live-Probe:**
```
=== POST /api/v1/zone-automation/zones/wohnzimmer/presence (detected=true) ===
status: 200
response: {
    'actions': [
        {'action': 'light.turn_on', 'entity': 'light.wohnzimmer'},
        {'action': 'music.play', 'entity': 'media_player.wohnzimmer'}
    ],
    'ok': True
}

=== POST /api/v1/zone-automation/zones/wohnzimmer/presence (detected=false) ===
status: 200
response: {
    'actions': [
        {'action': 'light.turn_off', 'entity': 'light.wohnzimmer'},
        {'action': 'music.stop', 'entity': 'media_player.wohnzimmer'}
    ],
    'ok': True
}
```

**Contract-Assertions (zu ergänzen in `tests/test_zone_automation_api_contract.py`):**
1. Presence detected → 200 mit `light.turn_on` + `music.play` actions
2. Presence cleared → 200 mit `light.turn_off` + `music.stop` actions
3. Ohne Auth → 401
4. Controller nicht initialisiert → 503

## Files

- `addons/pilotsuite/app/copilot_core/api/v1/zone_automation.py` — shipped spine, `@zone_automation_bp.route("/zones/<zone_id>/presence", methods=["POST"])`
- `tests/test_zone_automation_api_contract.py` — Contract-Tests (neu zu erstellen)

## CORE-AUTO-203 Fortschritt

- **CORE-AUTO-203-A:** `/api/v1/zone-automation/dashboard` — Automation Overview ✅
- **CORE-AUTO-203-B:** Presence→Action Automation ✅ (erste echte Automation)
- **Nächste:** CORE-AUTO-203-C (Brightness→Dimming Automation) oder CORE-AUTO-203-D (Mood→Music Automation)

## Shared Queue Truth

- VM-02 (293-297) ✅
- CORE-HABITUS-202 (A-E) ✅
- CORE-AUTO-203-A ✅
- **CORE-AUTO-203-B ✅** (21:40)

**Nächster:** CORE-AUTO-203-C oder CORE-HARDEN-204-NAMING
