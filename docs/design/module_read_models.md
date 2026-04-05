# Module Read Models Specification (Backend-UI)

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Zweck:** Einheitliche Projektion der 4 Haupt-Module für das Backend-UI.

## 1. Gemeinsame Struktur (Envelope)
Jede Modul-Summary in `GET /api/v1/backend/zones` oder `GET /api/v1/backend/modules` muss folgende Felder liefern:

- `summary`: String (Human-readable Status)
- `detailed_states`: List (Entitäten-Zustände)
- `active_features`: List (Aktivierte Logiken/Filter)
- `anomalies`: List (Probleme/Warnungen)

## 2. Modul-Spezifikationen

### Licht (light)
- **Summary:** e.g., "2 Lichter an, 1 Override"
- **Detailed States:** `entity_id`, `state` (on/off), `brightness` (0-255), `is_override` (bool)
- **Features:** "Flux/Adaptive Lighting", "Motion-Trigger", "Brightness-Filter"

### Klima (climate)
- **Summary:** e.g., "Schnitt 21.8°C, Heizen aktiv"
- **Detailed States:** `entity_id`, `temp` (float), `target` (float), `action` (idle/heating/cooling)
- **Features:** "Eco-Mode", "Window-Detection", "Schedule-Active"

### Musik (media)
- **Summary:** e.g., "Wohnzimmer: Spotify (70%)"
- **Detailed States:** `entity_id`, `state` (playing/paused/idle), `source`, `volume` (0-100)
- **Features:** "Multiroom-Sync", "Night-Mode-Volume", "Auto-Pause-on-Leave"

### Presence (presence)
- **Summary:** e.g., "Zone belegt (95% Confidence)"
- **Detailed States:** `zone_id`, `presence` (bool), `last_motion` (ISO-Timestamp), `confidence` (0.0-1.0)
- **Features:** "Bayesian-Fusion", "mmWave-Precision", "Static-Presence-Detection"

## 3. Zone-Level Module Override Integration

### State Resolution Logic
- **Global State:** Retrieved from ModuleRegistry (`get_state(module_id)`)
- **Zone Override State:** Retrieved from ModuleRegistry (`get_zone_state(zone_id, module_id)`)
- **Effective State:** Zone override takes precedence; fallback to global if no override exists

### API Integration Points
- **Read:** `GET /api/v1/backend/zones/<zone_id>/entities` returns consolidated module states
- **Write:** `POST /api/v1/backend/zones/<zone_id>/modules` updates zone-level overrides
- **Reset:** `POST` with `state == global_state` removes override via automatic cleanup

## 4. Implementierungs-Regel
PilotClaw zieht diese Strukturen in Slice 136+ schlag auf schlag in die jeweiligen Core-Service-Projektionen.
- Fallback bei fehlenden Daten: Leere Listen/Null-Werte, kein Crash.
- Success Signal: Backend-UI zeigt für alle 4 Module konsistente Detail-Daten ohne Heuristik-Drift.