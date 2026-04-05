# Module Read-Models: Backend-UI Projection

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Overview
This document specifies the data structure for module-specific read models in the Backend-UI. Each module (Light, Climate, Media, Presence) must provide a consistent summary and detailed state object to avoid frontend-side heuristics.

## 2. Global Data Contract (The Envelope)
All module read models must adhere to this structure when returned via `/api/v1/backend/zones` or `/api/v1/backend/modules`.

```json
{
  "summary": "String (e.g., '3 Lights on')",
  "detailed_states": [
    {
      "entity_id": "String",
      "state": "String",
      "attributes": "Object (Module-specific)"
    }
  ],
  "active_features": ["List of strings"],
  "anomalies": ["List of strings/objects"]
}
```

## 3. Module Specifics

### Light Module (`light`)
- **Attributes:** `brightness` (0-255), `color_temp`, `is_override` (bool).
- **Features:** "Adaptive Lighting", "Motion-Sync", "Brightness-Filter".

### Climate Module (`climate`)
- **Attributes:** `current_temp` (float), `target_temp` (float), `hvac_action` (idle/heating/cooling).
- **Features:** "Eco-Mode", "Window-Detection".

### Media Module (`media`)
- **Attributes:** `source` (string), `volume` (0-100), `is_group_master` (bool).
- **Features:** "Multiroom-Sync", "Auto-Pause".

### Presence Module (`presence`)
- **Attributes:** `is_present` (bool), `last_motion` (timestamp), `confidence` (0.0-1.0).
- **Features:** "Bayesian-Fusion", "mmWave-Precision".

## 4. Implementation Goal (Slice 136)
PilotClaw will implement these structures in the respective `get_summary()` methods of the Core services.

## 5. Success Signal
Backend-UI displays consistent detailed data for all four modules without needing to fetch raw entity states from HA.
