# Slice 165: Devices API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** devices.py (21KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/devices | ✅ List devices |
| GET /api/v1/devices/<id> | ✅ Get device |

## Expansion Needed

1. **Device Registry** — Full registry management
2. **Device Entities** — List entities per device
3. **Device Diagnostics** — Diagnostic information
4. **Device Cleanup** — Remove orphaned devices

## Decision

**Action:** Add registry + entities + diagnostics endpoints

**Priority:**
1. Device registry management
2. Device entities listing
3. Device diagnostics
4. Device cleanup

