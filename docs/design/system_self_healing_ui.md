# System Self-Healing & Proactive Diagnostics UI

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Overview
This document specifies the UI for the PilotSuite's self-healing capabilities. The system should detect drifts (e.g., entity 404, integration timeout) and attempt to fix them autonomously.

## 2. Dashboard Component: The "Health Pulse"
- **Visual:** A pulsating circle in the system status bar.
- **States:**
  - 🟢 **Healthy:** All systems operational.
  - 🟡 **Healing:** An issue was detected; repair is in progress (e.g., "Re-matching orphaned entity").
  - 🔴 **Action Required:** Auto-repair failed; manual intervention needed.

## 3. The "Repair Timeline"
A chronological view of autonomous fixes:
- **08:15:** Sonos speaker "living_room" unreachable -> Restarting `sonos-http-api`.
- **08:16:** Success: Sonos connection restored.
- **09:42:** Ghost presence detected in "hallway" -> Re-calibrating motion sensor prior probabilities.

## 4. API-Contract (Slice 155)
`GET /api/v1/system/healing/status`
```json
{
  "active_repairs": [
    {"id": "fix_99", "target": "sonos_bridge", "strategy": "service_restart", "progress": 0.4}
  ],
  "history": [
    {"id": "fix_98", "timestamp": "ISO-8601", "result": "resolved", "impact": "low"}
  ]
}
```

## 5. Success Signal
Decreased "Downtime per Module" and zero manual maintenance tasks for the end-user regarding technical drift.
